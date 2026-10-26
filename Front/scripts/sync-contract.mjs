import { readFile, writeFile } from 'node:fs/promises'
import { resolve } from 'node:path'
const root=resolve(import.meta.dirname,'..')
const spec=JSON.parse(await readFile(resolve(root,'contracts/openapi.json'),'utf8'))
const operations={}
for(const [path,methods]of Object.entries(spec.paths))for(const [method,op]of Object.entries(methods)){
  const parameters=(op.parameters || []).map(p=>p.$ref?spec.components.parameters[p.$ref.split('/').at(-1)]:p)
  const body=Object.values(op.requestBody?.content || {})[0]?.schema?.$ref?.split('/').at(-1) || null
  operations[method.toUpperCase()+' '+path]={id:op.operationId,method:method.toUpperCase(),path,title:op.summary,roles:op['x-roles'],permission:op['x-permission'],origin:op['x-origin'],parameters,body,concurrency:parameters.some(p=>p.name==='If-Match'),idempotent:parameters.some(p=>p.name==='Idempotency-Key'),responses:Object.keys(op.responses)}
}
await writeFile(resolve(root,'src/api/operations.json'),JSON.stringify(operations,null,2)+'\n')
await writeFile(resolve(root,'src/api/schemas.json'),JSON.stringify(spec.components.schemas,null,2)+'\n')
console.log(`已从项目内契约同步 ${Object.keys(operations).length} 个接口操作`)
