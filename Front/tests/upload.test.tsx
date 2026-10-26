import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { UploadField } from '../src/components/schema-form'
import type { FormContext } from '../src/components/schema-form'

const mocks = vi.hoisted(() => ({ api: vi.fn() }))
vi.mock('../src/api/client', () => ({ api: mocks.api, operations: {} }))
vi.mock('../src/app/providers', () => ({ useSession: () => ({ can: () => true }) }))

afterEach(() => { cleanup(); mocks.api.mockReset() })

function field(context: FormContext, name = 'image_file_ids') {
  const onChange = vi.fn()
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const result = render(<QueryClientProvider client={client}><UploadField field={name} value={undefined} onChange={onChange} context={context} id="upload-test" /></QueryClientProvider>)
  return { input: result.container.querySelector('input[type="file"]') as HTMLInputElement, onChange }
}

describe('上传用途与商品归属', () => {
  it('无商品编号时先提示保存草稿，不把原图误作为导入文件', () => {
    const { input } = field({})
    expect(input.disabled).toBe(true)
    expect(input.accept).toContain('image/jpeg')
    expect(screen.getByText('先保存商品草稿，再在商品档案中上传原图。')).toBeTruthy()
    expect(mocks.api).not.toHaveBeenCalled()
  })
  it('已保存商品原图上传携带正确用途和商品编号', async () => {
    mocks.api.mockResolvedValue({ data: { id: 'file-id' } })
    const { input, onChange } = field({ productId: 'product-id' })
    fireEvent.change(input, { target: { files: [new File(['image-test-bytes'], 'cup.jpg', { type: 'image/jpeg' })] } })
    await waitFor(() => expect(onChange).toHaveBeenCalledWith('file-id'))
    const [key, options] = mocks.api.mock.calls[0]
    expect(key).toBe('POST /files')
    expect(options.body.get('purpose')).toBe('product_image')
    expect(options.body.get('product_id')).toBe('product-id')
  })
  it('明确的导入上传不要求商品编号，并保持 CSV/XLSX 类型', async () => {
    mocks.api.mockResolvedValue({ data: { id: 'import-file-id' } })
    const { input, onChange } = field({ uploadPurpose: 'import' }, 'file_id')
    expect(input.disabled).toBe(false)
    expect(input.accept).toBe('.csv,.xlsx')
    fireEvent.change(input, { target: { files: [new File(['name,price\n'], 'products.csv', { type: 'text/csv' })] } })
    await waitFor(() => expect(onChange).toHaveBeenCalledWith('import-file-id'))
    expect(mocks.api.mock.calls[0][1].body.get('purpose')).toBe('import')
    expect(mocks.api.mock.calls[0][1].body.has('product_id')).toBe(false)
  })
})
