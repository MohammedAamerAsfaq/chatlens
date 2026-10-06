import { beforeEach, describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent } from 'vue'
import { uiDataTable } from '../uiDataTable'

const TestGrid = defineComponent({
  template: `<div><table v-ui-data-table="'test-legacy-grid'"><thead><tr><th>Name</th><th>Status</th></tr></thead><tbody><tr><td>Alpha</td><td>Ready</td></tr><tr class="detail"><td colspan="2">Detail</td></tr></tbody></table></div>`,
})

describe('uiDataTable directive', () => {
  beforeEach(() => localStorage.clear())

  it('adds controls and persists column visibility without hiding detail rows', async () => {
    const wrapper = mount(TestGrid, { global: { directives: { uiDataTable } } })
    expect(wrapper.get('.ui-data-table__bridge-tools').text()).toContain('Export CSV')
    expect(wrapper.get('table').classes()).toContain('ui-data-table__native--compact')

    const toggles = wrapper.findAll('.ui-data-table__bridge-menu input')
    await toggles[1]!.setValue(false)

    expect(wrapper.findAll('thead th')[1]!.attributes('style')).toContain('display: none')
    expect(wrapper.get('tr.detail td').attributes('style') || '').not.toContain('display: none')
    expect(localStorage.getItem('chatlens:datatable:test-legacy-grid:hidden')).toContain('1')
  })
})
