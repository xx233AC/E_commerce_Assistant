from datetime import timedelta
from functools import lru_cache
from minio import Minio
from minio.error import S3Error
import urllib3
from app.core.config import get_settings
from app.core.exceptions import ApiError


@lru_cache
def client(public=False):
    c=get_settings()
    return Minio(c.minio_public_endpoint if public else c.minio_endpoint,
                 access_key=c.minio_access_key.get_secret_value(),secret_key=c.minio_secret_key.get_secret_value(),
                 secure=c.minio_secure,region='us-east-1',http_client=urllib3.PoolManager(timeout=urllib3.Timeout(connect=4,read=60),retries=False))


def ensure_bucket():
    c=get_settings();s=client()
    if not s.bucket_exists(c.minio_bucket): s.make_bucket(c.minio_bucket)
    # Dedicated application bucket must be private. Do not touch existing shared buckets.
    try:
        policy=s.get_bucket_policy(c.minio_bucket)
    except S3Error as exc:
        if exc.code not in ('NoSuchBucketPolicy','NoSuchPolicy'): raise
        policy=None
    if policy:
        raise ApiError(503,'DEPENDENCY_UNAVAILABLE','应用文件桶必须为私有，请移除匿名访问策略')


def put(stream,object_name,length,content_type):
    try:
        ensure_bucket()
        client().put_object(get_settings().minio_bucket,object_name,stream,length,content_type=content_type)
    except ApiError: raise
    except Exception:
        raise ApiError(503,'DEPENDENCY_UNAVAILABLE','无法连接MinIO文件服务，请检查19000端口隧道',retryable=True) from None


def get(bucket,object_name):
    response=None
    try:
        response=client().get_object(bucket,object_name)
        return response.read()
    except Exception:
        raise ApiError(503,'DEPENDENCY_UNAVAILABLE','暂时无法读取文件',retryable=True) from None
    finally:
        if response is not None: response.close();response.release_conn()


def access_url(bucket,object_name):
    return client(public=True).presigned_get_object(bucket,object_name,expires=timedelta(seconds=300))
