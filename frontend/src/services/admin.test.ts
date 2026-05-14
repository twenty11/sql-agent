import { beforeEach, describe, expect, it, vi, type Mock } from 'vitest'
import { api } from './api'
import { TablesAPI, UsersAPI } from './admin'

vi.mock('./api', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}))

describe('admin API wrappers', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('updates table metadata through the atomic endpoint', async () => {
    ;(api.put as unknown as Mock).mockResolvedValue({ data: { message: 'ok' } })

    await TablesAPI.updateMetadata('table-1', '中文名', '表注释')

    expect(api.put).toHaveBeenCalledWith('/admin/tables/table-1/metadata', {
      display_name: '中文名',
      comment: '表注释',
    })
  })

  it('sends batch deletes in the request body', async () => {
    ;(api.delete as unknown as Mock).mockResolvedValue({ data: { deleted: ['t1'], errors: [] } })

    await TablesAPI.deleteMany(['t1'])

    expect(api.delete).toHaveBeenCalledWith('/admin/tables/batch', {
      data: { table_ids: ['t1'] },
    })
  })

  it('uploads multiple files under the repeated files field', async () => {
    ;(api.post as unknown as Mock).mockResolvedValue({
      data: { batch_id: 'batch-1', count: 2, status: 'queued', message: 'ok' },
    })
    const first = new File(['a'], 'a.csv', { type: 'text/csv' })
    const second = new File(['b'], 'b.csv', { type: 'text/csv' })

    await TablesAPI.upload([first, second], 'group-1')

    const [url, body, config] = (api.post as unknown as Mock).mock.calls[0]
    expect(url).toBe('/admin/tables/upload')
    expect((body as FormData).getAll('files')).toEqual([first, second])
    expect((body as FormData).get('group_id')).toBe('group-1')
    expect((body as FormData).get('mode')).toBe('new')
    expect(config).toBeUndefined()
  })

  it('uploads batch update mappings under repeated target_table_ids', async () => {
    ;(api.post as unknown as Mock).mockResolvedValue({
      data: { batch_id: 'batch-1', count: 2, status: 'queued', message: 'ok' },
    })
    const first = new File(['a'], 'a.csv', { type: 'text/csv' })
    const second = new File(['b'], 'b.csv', { type: 'text/csv' })

    await TablesAPI.upload([first, second], 'group-1', ['table-1', 'table-2'])

    const [url, body] = (api.post as unknown as Mock).mock.calls[0]
    expect(url).toBe('/admin/tables/upload')
    expect((body as FormData).getAll('files')).toEqual([first, second])
    expect((body as FormData).get('mode')).toBe('update')
    expect((body as FormData).getAll('target_table_ids')).toEqual(['table-1', 'table-2'])
    expect((body as FormData).get('target_table_ids_json')).toBe('["table-1","table-2"]')
    expect((body as FormData).get('target_table_id')).toBeNull()
  })

  it('keeps legacy single table update field', async () => {
    ;(api.post as unknown as Mock).mockResolvedValue({
      data: { batch_id: 'batch-1', count: 1, status: 'queued', message: 'ok' },
    })
    const file = new File(['a'], 'a.csv', { type: 'text/csv' })

    await TablesAPI.upload(file, 'group-1', 'table-1')

    const [, body] = (api.post as unknown as Mock).mock.calls[0]
    expect((body as FormData).get('mode')).toBe('update')
    expect((body as FormData).get('target_table_id')).toBe('table-1')
    expect((body as FormData).getAll('target_table_ids')).toEqual([])
  })

  it('overwrites user roles through the expected endpoint', async () => {
    ;(api.put as unknown as Mock).mockResolvedValue({ data: { id: 'u1', roles: ['viewer'] } })

    await UsersAPI.setRoles('u1', ['viewer'])

    expect(api.put).toHaveBeenCalledWith('/admin/users/u1/roles', {
      roles: ['viewer'],
    })
  })
})
