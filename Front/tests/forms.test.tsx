import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { editable, initial, schemas, SchemaForm, validateBody } from '../src/components/schema-form'
import { operations } from '../src/api/client'

describe('表单与权限契约',()=>{
  it('空PATCH不可提交',()=>{expect(validateBody('ProductPatch',{}).length).toBeGreaterThan(0)})
  it('金额必须是两位小数字符串',()=>{expect(validateBody('ProductPatch',{price:99.1}).length).toBeGreaterThan(0);expect(validateBody('ProductPatch',{price:'99.10'})).toEqual([])})
  it('不允许客户端覆盖计算指标或明文平台Token',()=>{expect(validateBody('PerformancePatch',{ctr:'0.10'}).length).toBeGreaterThan(0);expect(validateBody('PlatformAccountCreate',{platform:'douyin',account_name:'测试专用',token:'test-only'}).length).toBeGreaterThan(0)})
  it('实际开始操作必须填写外部计划和开始时间',()=>{expect(validateBody('ExperimentPatch',{experiment_status:'running',remark:'测试专用'}).length).toBeGreaterThan(0)})
  it('实验粒度必须引用实验，商品粒度不能混入实验',()=>{const row={round_id:'00000000-0000-4000-8000-000000000001',record_date:'2026-10-23',impressions:0,clicks:0,conversions:0,spend:'0.00',revenue:'0.00'};expect(validateBody('PerformanceCreate',{...row,granularity:'experiment_day'}).length).toBeGreaterThan(0);expect(validateBody('PerformanceCreate',{...row,granularity:'product_day',experiment_id:row.round_id}).length).toBeGreaterThan(0)})
  it('初始值只来自契约默认值，不填入虚构商品',()=>{expect(initial(schemas.ProductCreate)).toMatchObject({status:'draft',selling_points:[]});expect((initial(schemas.ProductCreate) as Record<string,unknown>).name).toBeUndefined()})
  it('编辑请求只保留可修改字段，不能带只读字段',()=>{expect(editable('UserPatch',{id:'test-id',username:'test-name',display_name:'测试专用',version:3,role:'viewer',status:'active'})).toEqual({display_name:'测试专用',role:'viewer',status:'active'})})
  it('必填可空字段初始化为null，而非无法提交的undefined',()=>{expect(initial(schemas.AuthMetadata)).toMatchObject({external_account_id:null,scopes:[],expires_at:null})})
  it('查看人员不能执行业务写操作，允许自行退出',()=>{for(const op of Object.values(operations)){if(['POST','PATCH'].includes(op.method) && !op.path.startsWith('/auth/'))expect(op.roles).not.toContain('viewer')}expect(operations['POST /auth/logout'].roles).toContain('viewer')})
  it('投放确认、用户管理和实验状态保留专项权限',()=>{expect(operations['PATCH /products/{product_id}/ad-recommendations/{recommendation_id}/confirmation'].permission).toBe('ads:confirm');expect(operations['PATCH /products/{product_id}/ad-experiments/{experiment_id}'].permission).toBe('experiments:update');expect(operations['POST /users'].roles).toEqual(['admin'])})
  it('表单可用可读标签访问，不把英文schema当作产品页面',()=>{render(<SchemaForm schemaName="UserCreate" value={{}} onChange={()=>{}}/>);expect(screen.getByLabelText(/用户名/)).toBeTruthy();expect(screen.getByLabelText(/显示名称/)).toBeTruthy();expect(screen.getByLabelText(/角色/)).toBeTruthy()})
})
