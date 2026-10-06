import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ClientTagManager from '../ClientTagManager.vue'

const api = vi.hoisted(() => ({ createTag: vi.fn(), updateTag: vi.fn(), deleteTag: vi.fn() }))
vi.mock('@/api', () => ({ clientPulseApi: api }))

const tags = [{ id: 7, name: 'VIP', color: '#23865b', usage_count: 2 }]

describe('ClientTagManager', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.stubGlobal('confirm', vi.fn(() => true))
  })

  it('creates and selects a tag', async () => {
    api.createTag.mockResolvedValue({ data: { id: 9, name: 'Buyer', color: '#123456' } })
    const wrapper = mount(ClientTagManager, { props: { tags, modelValue: [], canEdit: true } })
    await wrapper.find('input[type="text"]').setValue('Buyer')
    await wrapper.find('input[type="color"]').setValue('#123456')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(api.createTag).toHaveBeenCalledWith({ name: 'Buyer', color: '#123456' })
    expect(wrapper.emitted('update:modelValue').at(-1)[0]).toEqual([9])
    expect(wrapper.emitted('tags-changed')).toHaveLength(1)
  })

  it('updates and deletes an existing tag', async () => {
    api.updateTag.mockResolvedValue({ data: {} })
    api.deleteTag.mockResolvedValue({ data: null })
    const wrapper = mount(ClientTagManager, { props: { tags, modelValue: [7], canEdit: true } })
    await wrapper.findAll('button').find(button => button.text() === 'Edit').trigger('click')
    const textInputs = wrapper.findAll('input[type="text"]')
    await textInputs.at(-1).setValue('Priority')
    await wrapper.findAll('button').find(button => button.text() === 'Save').trigger('click')
    await flushPromises()
    expect(api.updateTag).toHaveBeenCalledWith(7, { name: 'Priority', color: '#23865b' })

    await wrapper.findAll('button').find(button => button.text() === 'Delete').trigger('click')
    await flushPromises()
    expect(globalThis.confirm).toHaveBeenCalledWith(expect.stringContaining('2 customer profile(s)'))
    expect(api.deleteTag).toHaveBeenCalledWith(7)
    expect(wrapper.emitted('update:modelValue').at(-1)[0]).toEqual([])
  })
})
