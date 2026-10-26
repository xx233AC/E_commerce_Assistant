import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api, ApiError, buildPath, tokenStore, transport } from '../src/api/client'

const meta={request_id:'00000000-0000-4000-8000-000000000001'}
const success=()=>new Response(JSON.stringify({data:[],meta}),{status:200,headers:{'Content-Type':'application/json'}})
describe('接口传输契约',()=>{
  beforeEach(()=>tokenStore.clear())
  afterEach(()=>vi.unstubAllGlobals())
  it('按路径编码参数，保留false和0，过滤未填筛选',()=>{expect(buildPath('/products/{product_id}',{product_id:'a/b'},{page:0,low_stock_only:false,empty:'',missing:undefined})).toBe('/products/a%2Fb?page=0&low_stock_only=false')})
  it('没有路径参数就停止，不发送不完整请求',()=>{expect(()=>buildPath('/products/{product_id}')).toThrow('缺少路径参数')})
  it('登录态通过Bearer发送',async()=>{tokenStore.set('test-only-session');const fetch=vi.fn().mockResolvedValue(success());vi.stubGlobal('fetch',fetch);await api('GET /stores');const headers=fetch.mock.calls[0][1].headers as Headers;expect(headers.get('Authorization')).toBe('Bearer test-only-session')})
  it('写入使用指定幂等键和带引号的当前版本',async()=>{const fetch=vi.fn().mockResolvedValue(success());vi.stubGlobal('fetch',fetch);await api('PATCH /products/{product_id}',{params:{product_id:'product'},body:{status:'inactive'},version:4,idempotencyKey:'stable-key'});const h=fetch.mock.calls[0][1].headers as Headers;expect(h.get('If-Match')).toBe('"4"');expect(h.get('Idempotency-Key')).toBe('stable-key')})
  it('缺失版本不得发送修改请求',async()=>{const fetch=vi.fn();vi.stubGlobal('fetch',fetch);await expect(api('PATCH /products/{product_id}',{params:{product_id:'product'},body:{status:'inactive'}})).rejects.toThrow('缺少当前版本');expect(fetch).not.toHaveBeenCalled()})
  it('表单上传不手动指定Content-Type，保留浏览器boundary',async()=>{const fetch=vi.fn().mockResolvedValue(success());vi.stubGlobal('fetch',fetch);const form=new FormData();form.set('purpose','import');await api('POST /files',{body:form});expect((fetch.mock.calls[0][1].headers as Headers).has('Content-Type')).toBe(false)})
  it('401触发清理登录事件',async()=>{const listener=vi.fn();window.addEventListener('commerce:unauthorized',listener);vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response('{}',{status:401,headers:{'content-type':'application/json'}})));await expect(api('GET /stores')).rejects.toBeInstanceOf(ApiError);expect(listener).toHaveBeenCalledOnce();window.removeEventListener('commerce:unauthorized',listener)})
  it('412保留字段明细和请求编号，不伪装成保存成功',async()=>{vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response(JSON.stringify({error:{code:'VERSION_CONFLICT',message:'版本冲突',details:[],retryable:false},request_id:meta.request_id}),{status:412,headers:{'content-type':'application/json'}})));try{await api('GET /stores');expect.unreachable()}catch(e){expect(e).toBeInstanceOf(ApiError);expect((e as ApiError).status).toBe(412);expect((e as ApiError).requestId).toBe(meta.request_id)}})
  it('拒绝没有契约包裹的成功响应',async()=>{vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response('{}',{status:200,headers:{'content-type':'application/json'}})));await expect(api('GET /stores')).rejects.toMatchObject({error:{code:'INVALID_RESPONSE'}})})
  it('网络失败显示连接错误，不返回假业务结果',async()=>{vi.stubGlobal('fetch',vi.fn().mockRejectedValue(new TypeError('Failed to fetch')));await expect(api('GET /stores')).rejects.toMatchObject({status:0,error:{code:'CONNECTION_FAILED'}})})
  it('模板下载保留二进制响应',async()=>{vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response('name,price',{status:200,headers:{'content-type':'text/csv'}})));const result=await transport('GET /workspace/templates/products',{raw:true});expect(result).toBeInstanceOf(Blob)})
  it('未知接口不发送请求',async()=>{const fetch=vi.fn();vi.stubGlobal('fetch',fetch);await expect(api('GET /not-in-contract')).rejects.toThrow('接口未在契约中定义');expect(fetch).not.toHaveBeenCalled()})
})
