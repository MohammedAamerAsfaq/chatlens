import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({ conversations: vi.fn() }))
vi.mock('@/api', () => ({ clientPulseApi: api }))

import ClientConversationHistory from '../ClientConversationHistory.vue'

describe('ClientConversationHistory', () => {
  it('renders linked-account messages and filters by account', async () => {
    api.conversations.mockResolvedValue({
      data: {
        count: 1,
        accounts: [{ id: 7, name: 'Primary WhatsApp', phone_number: '971500001234', session_status: 'connected' }],
        results: [{
          id: 11, account_id: 7, account_name: 'Primary WhatsApp', account_status: 'connected',
          direction: 'inbound', message_type: 'text', message_text: 'Customer history message',
          message_time: '2026-10-06T12:00:00Z', has_media: false, media_url: '',
        }],
      },
    })
    const wrapper = mount(ClientConversationHistory, { props: { profileId: 3 } })
    await flushPromises()

    expect(wrapper.text()).toContain('Customer history message')
    expect(wrapper.text()).toContain('Primary WhatsApp')

    await wrapper.get('select').setValue('7')
    await flushPromises()
    expect(api.conversations).toHaveBeenLastCalledWith(3, {
      page: 1, page_size: 25, account_id: 7,
    })
    wrapper.unmount()
  })
})
