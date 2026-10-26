from datetime import timedelta
from pathlib import Path
import io
import zipfile
import warnings
import hashlib
from uuid import uuid4

from PIL import Image
from app.core.config import get_settings
from app.core.exceptions import ApiError
from app.core.security import utcnow
from app.integrations.storage import minio

Image.MAX_IMAGE_PIXELS=40_000_000
MIMES={'JPEG':'image/jpeg','PNG':'image/png','WEBP':'image/webp'}


def inspect_file(stream,name,purpose,size,limits):
    if size<1: raise ApiError(422,'FILE_VALIDATION_FAILED','不能上传空文件')
    stream.seek(0);head=stream.read(32);stream.seek(0)
    width=height=duration=None
    if purpose=='import':
        if size>10485760: raise ApiError(413,'PAYLOAD_TOO_LARGE','导入文件最大10MiB')
        if name.lower().endswith('.csv'):
            try:
                text=stream.read().decode('utf-8-sig')
                if '\x00' in text: raise ValueError()
            except (UnicodeError,ValueError): raise ApiError(422,'FILE_VALIDATION_FAILED','CSV须为UTF-8文本') from None
            mime='text/csv'
        elif name.lower().endswith('.xlsx') and head.startswith(b'PK'):
            try:
                with zipfile.ZipFile(stream) as z:
                    if len(z.infolist())>1000 or sum(i.file_size for i in z.infolist())>100*1024*1024 or any('vbaproject' in i.filename.lower() or i.flag_bits & 1 for i in z.infolist()): raise ValueError()
                    if '[Content_Types].xml' not in z.namelist() or 'xl/workbook.xml' not in z.namelist(): raise ValueError()
                    content_types=z.read('[Content_Types].xml').lower()
                    if b'macroenabled' in content_types or b'vbaproject' in content_types: raise ValueError()
            except (ValueError,zipfile.BadZipFile): raise ApiError(422,'FILE_VALIDATION_FAILED','无效或过大的XLSX文件') from None
            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        else: raise ApiError(415,'UNSUPPORTED_MEDIA_TYPE','导入只接受CSV和XLSX')
    elif len(head)>12 and head[4:8]==b'ftyp':
        if purpose!='media': raise ApiError(415,'UNSUPPORTED_MEDIA_TYPE','原图和参考文件只允许图片')
        if size>min(limits['max_upload_video_bytes'],524288000): raise ApiError(413,'PAYLOAD_TOO_LARGE','视频超过上传大小限制')
        brand=head[8:12]
        if not (brand.startswith(b'iso') or brand in {b'mp41',b'mp42',b'avc1',b'M4V ',b'dash',b'MSNV'}):
            raise ApiError(415,'UNSUPPORTED_MEDIA_TYPE','媒体视频必须使用MP4容器')
        try:
            import av
            with av.open(stream,mode='r') as container:
                track=container.streams.video[0]
                width,height=track.width,track.height
                duration=float(track.duration*track.time_base) if track.duration else float(container.duration/av.time_base)
                next(container.decode(video=0))
                if width<=0 or height<=0 or width*height>40_000_000 or duration<=0: raise ValueError()
        except Exception: raise ApiError(422,'FILE_VALIDATION_FAILED','无法验证MP4视频尺寸、时长或视频内容') from None
        mime='video/mp4'
    else:
        if size>min(limits['max_upload_image_bytes'],20971520): raise ApiError(413,'PAYLOAD_TOO_LARGE','图片超过上传大小限制')
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('error',Image.DecompressionBombWarning)
                with Image.open(stream) as image:
                    mime=MIMES.get(image.format)
                    width,height=image.size
                    image.verify()
                if not mime: raise ValueError()
                stream.seek(0)
                with Image.open(stream) as decoded:
                    decoded.load()
        except Exception: raise ApiError(415,'UNSUPPORTED_MEDIA_TYPE','只支持内容有效的JPEG、PNG、WebP图片') from None
    stream.seek(0)
    return mime,width,height,duration


def upload(ctx):
    b=ctx.body;purpose=b['purpose'];product_id=b.get('product_id')
    if purpose!='import' and not product_id: raise ApiError(422,'VALIDATION_ERROR','此用途必须关联商品')
    if product_id: ctx.require_product(product_id)
    name=Path((ctx.upload.filename or '').replace('\\','/')).name
    if not 1<=len(name)<=255 or name in {'.','..'} or any(ord(char)<32 for char in name):
        raise ApiError(422,'FILE_VALIDATION_FAILED','文件名长度或内容不符合要求')
    stream=ctx.upload.file;stream.seek(0,2);length=stream.tell();stream.seek(0)
    mime,width,height,duration=inspect_file(stream,name,purpose,length,ctx.get('SystemSettings','singleton'))
    if not ctx.file_hash:
        digest=hashlib.sha256()
        for chunk in iter(lambda: stream.read(1024*1024), b''): digest.update(chunk)
        ctx.file_hash=digest.hexdigest();stream.seek(0)
    # Original names remain metadata; UUID-only object keys keep signed URLs bounded.
    file_id=str(uuid4());object_name='files/'+file_id
    ctx.db.info.setdefault('pending_storage_objects',[]).append({
        'file_id':file_id,'bucket':get_settings().minio_bucket,'object_name':object_name})
    minio.put(stream,object_name,length,mime)
    row=ctx.repo.create('FileObject',{'id':file_id,'product_id':product_id,'file_name':name,'content_type':mime,
        'byte_size':length,'sha256':ctx.file_hash,'purpose':purpose,'storage_status':'available','execution_mode':'real'})
    ctx.repo.create('FileStorage',{'file_id':file_id,'bucket':get_settings().minio_bucket,'object_name':object_name,
        'width':width,'height':height,'duration_seconds':duration,'checksum':ctx.file_hash})
    return row


def read_bytes(ctx,file_id):
    file=ctx.get('FileObject',file_id)
    if file['storage_status']!='available': raise ApiError(409,'FILE_NOT_AVAILABLE','文件尚不可用')
    obj=ctx.get('FileStorage',file_id)
    return minio.get(obj['bucket'],obj['object_name'])


def file_info(ctx):
    row=ctx.get('FileObject',ctx.params['file_id'])
    if row['product_id']: ctx.require_product(row['product_id'])
    return row


def access(ctx):
    file=file_info(ctx)
    if file['storage_status']!='available': raise ApiError(409,'FILE_NOT_AVAILABLE','文件尚不可用')
    obj=ctx.get('FileStorage',file['id'])
    try: url=minio.access_url(obj['bucket'],obj['object_name'])
    except ApiError: raise
    except Exception: raise ApiError(503,'DEPENDENCY_UNAVAILABLE','暂时无法生成文件访问地址',retryable=True) from None
    return {'file_id':file['id'],'url':url,
            'expires_at':(utcnow()+timedelta(seconds=300)).isoformat().replace('+00:00','Z'),'method':'GET'}

HANDLERS={'POST /files':upload,'GET /files/{file_id}':file_info,'GET /files/{file_id}/access-url':access}
