import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import UiDataTable from '../UiDataTable.vue'

const columns = [
  { key: 'name', label: 'Name', sortable: true },
  { key: 'status', label: 'Status' },
]
const rows = [{ id: 1, name: 'Alpha', status: 'ready' }]

describe('UiDataTable', () => {
  it('emits server sorting and pagination changes', async () => {
    const wrapper = mount(UiDataTable, { props: { columns, rows, total: 30, page: 1, pageSize: 10 } })

    await wrapper.get('thead button').trigger('click')
    expect(wrapper.emitted('update:sortKey')?.[0]).toEqual(['name'])
    expect(wrapper.emitted('update:sortDirection')?.[0]).toEqual(['asc'])

    const next = wrapper.findAll('footer button').find(button => button.text() === 'Next')
    await next?.trigger('click')
    const pageEvents = wrapper.emitted('update:page') || []
    expect(pageEvents[pageEvents.length - 1]).toEqual([2])
  })

  it('supports column visibility and expandable row content', async () => {
    localStorage.clear()
    const wrapper = mount(UiDataTable, {
      props: { columns, rows, total: 1, expandable: true, persistKey: 'test-grid' },
      slots: { expanded: '<div class="expanded-test">Details</div>' },
    })

    await wrapper.get('tbody tr').trigger('click')
    expect(wrapper.get('.expanded-test').text()).toBe('Details')

    const columnsButton = wrapper.findAll('header button').find(button => button.text() === 'Columns')
    await columnsButton?.trigger('click')
    const statusToggle = wrapper.findAll('.ui-data-table__column-menu input')[1]
    expect(statusToggle).toBeDefined()
    await statusToggle!.setValue(false)
    expect(wrapper.findAll('thead th')).toHaveLength(1)
    expect(localStorage.getItem('chatlens:datatable:test-grid:hidden')).toContain('status')
  })
})
