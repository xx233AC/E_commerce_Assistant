import { readFile, readdir } from 'node:fs/promises'
import { resolve } from 'node:path'
import assert from 'node:assert/strict'
const root=resolve(import.meta.dirname,'..')
const spec=JSON.parse(await readFile(resolve(root,'contracts/openapi.json'),'utf8'))
const operations=JSON.parse(await readFile(resolve(root,'src/api/operations.json'),'utf8'))
const schemas=JSON.parse(await readFile(resolve(root,'src/api/schemas.json'),'utf8'))
let count=0
for(const [path,methods] of Object.entries(spec.paths))for(const [method,op]of Object.entries(methods)){
  count++
  const binding=operations[method.toUpperCase()+' '+path]
  assert(binding,`缺少接口元信息 ${method} ${path}`)
  assert.equal(binding.id,op.operationId)
  assert.deepEqual(binding.roles,op['x-roles'])
  if(binding.body)assert(schemas[binding.body],`缺少请求Schema ${binding.body}`)
}
assert.deepEqual(schemas,spec.components.schemas)
assert.equal(count,Object.keys(operations).length)
async function sources(dir){let all='';for(const item of await readdir(dir,{withFileTypes:true})){const path=resolve(dir,item.name);if(item.isDirectory())all+=await sources(path);else if(/\.tsx?$/.test(item.name))all+='\n'+await readFile(path,'utf8')}return all}
const source=await sources(resolve(root,'src'))
const staticCalls=[...source.matchAll(/['"]((?:GET|POST|PATCH) \/[^'"\n]+)['"]/g)].map(m=>m[1]).filter(k=>!k.includes('${'))
for(const key of new Set(staticCalls))assert(operations[key],`页面引用契约外接口 ${key}`)
const dynamicCalls=[
  ...['main-images','video-scripts','titles'].map(x=>`POST /products/{product_id}/creative-plans/${x}/generate`),
  ...['images','videos'].map(x=>`POST /products/{product_id}/creative-plans/{creative_plan_id}/${x}/generate`),
  ...['products','sku-inventory','performance-records','platform-mappings'].map(x=>`GET /workspace/templates/${x}`),
  'GET /r/{tracking_code}',
]
const coverage=new Set([...staticCalls,...dynamicCalls])
for(const key of Object.keys(operations))assert(coverage.has(key),`缺少页面/动态操作绑定 ${key}`)
assert(!/\b(?:mockData|mockProducts|fakeData|demoProducts)\b/.test(source),'发现运行时代替真实数据的业务数组')
console.log(JSON.stringify({contractOperations:count,requestSchemas:Object.keys(schemas).length,staticBindings:new Set(staticCalls).size,dynamicBindings:dynamicCalls.length,coveredOperations:count,unknownBindings:0,embeddedBusinessMockPatterns:0},null,2))
