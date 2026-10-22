import { describe, expect, it, vi } from 'vitest'

import { loadPropertyHierarchy } from './propertyHierarchy'

describe('loadPropertyHierarchy', () => {
  it('uses the dedicated hierarchy endpoint when available', async () => {
    const rows = [{ id: 1, title: 'Tower' }]
    const api = { propertyHierarchyOptions: vi.fn().mockResolvedValue({ data: rows }) }

    await expect(loadPropertyHierarchy(api)).resolves.toEqual(rows)
  })

  it('falls back to all property pages when an older backend returns 404', async () => {
    const api = {
      propertyHierarchyOptions: vi.fn().mockRejectedValue({ response: { status: 404 } }),
      properties: vi.fn()
        .mockResolvedValueOnce({ data: { count: 2, results: [{ id: 1, title: 'Plot', parent: null }] } })
        .mockResolvedValueOnce({ data: { count: 2, results: [{ id: 2, title: 'Villa', parent: 1 }] } }),
    }

    await expect(loadPropertyHierarchy(api)).resolves.toEqual([
      { id: 1, title: 'Plot', reference_code: '', parent_id: null },
      { id: 2, title: 'Villa', reference_code: '', parent_id: 1 },
    ])
    expect(api.properties).toHaveBeenCalledTimes(2)
  })

  it('does not hide non-404 failures', async () => {
    const failure = { response: { status: 500 } }
    const api = { propertyHierarchyOptions: vi.fn().mockRejectedValue(failure) }

    await expect(loadPropertyHierarchy(api)).rejects.toBe(failure)
  })
})
