import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({ conversations: vi.fn() }))
vi.mock('@/api', () => ({ clientPulseApi: api }))

import ClientConversationHistory from '../ClientConversationHistory.vue'

describe('ClientConversationHistory', () => {
  beforeEach(() => api.conversations.mockReset())

  it('renders linked-account messages and filters by account', async () => {
    api.conversations.mockResolvedValue({
      data: {
        count: 1,
        next: null,
        accounts: [{ id: 7, whatsapp_contact_id: 19, name: 'Primary WhatsApp', phone_number: '971500001234', session_status: 'connected' }],
        results: [{
          id: 11, account_id: 7, account_name: 'Primary WhatsApp', contact_name: 'Customer Name',
          sender_name: 'Customer Name', account_status: 'connected',
          conversation_type: 'dm', chat_name: '',
          direction: 'inbound', message_type: 'text', message_text: 'Customer history message',
          message_time: '2026-10-06T12:00:00Z', has_media: false, media_url: '',
        }],
      },
    })
    const wrapper = mount(ClientConversationHistory, { props: { profileId: 3, canOpenInbox: true } })
    await flushPromises()

    expect(wrapper.text()).toContain('Customer history message')
    expect(wrapper.text()).toContain('Customer Name')
    expect(wrapper.text()).not.toContain('Primary WhatsAppPrimary WhatsApp')
    await wrapper.findAll('button').find(button => button.text().includes('Open WhatsApp Inbox')).trigger('click')
    expect(wrapper.emitted('open-inbox')).toEqual([[{ id: 19, account_id: 7 }]])

    await wrapper.get('select').setValue('7')
    await flushPromises()
    expect(api.conversations).toHaveBeenLastCalledWith(3, {
      page: 1, page_size: 25, conversation_type: 'dm', account_id: 7,
    })
    wrapper.unmount()
  })

  it('loads older server pages on scroll and can collapse the panel', async () => {
    const account = { id: 7, name: 'Primary WhatsApp', phone_number: '', session_status: 'connected' }
    api.conversations
      .mockResolvedValueOnce({ data: {
        count: 2, next: '/api/clientpulse/clients/3/conversations/?page=2', accounts: [account],
        results: [{ id: 12, account_name: account.name, account_status: 'connected', conversation_type: 'dm', chat_name: '', direction: 'outbound', message_type: 'text', message_text: 'Newest', message_time: '2026-10-06T12:10:00Z', has_media: false }],
      } })
      .mockResolvedValueOnce({ data: {
        count: 2, next: null, accounts: [account],
        results: [{ id: 10, account_name: account.name, account_status: 'connected', conversation_type: 'dm', chat_name: '', direction: 'inbound', message_type: 'text', message_text: 'Earlier', message_time: '2026-10-06T11:00:00Z', has_media: false }],
      } })
    const wrapper = mount(ClientConversationHistory, { props: { profileId: 3 } })
    await flushPromises()
    const history = wrapper.get('[data-testid="conversation-history"]')
    Object.defineProperty(history.element, 'scrollHeight', { configurable: true, value: 900 })
    Object.defineProperty(history.element, 'scrollTop', { configurable: true, writable: true, value: 0 })
    await history.trigger('scroll')
    await flushPromises()

    expect(api.conversations).toHaveBeenLastCalledWith(3, {
      page: 2, page_size: 25, conversation_type: 'dm',
    })
    expect(wrapper.text()).toContain('Earlier')
    await wrapper.findAll('button').find(button => button.text().includes('Collapse')).trigger('click')
    expect(wrapper.find('[data-testid="conversation-history"]').exists()).toBe(false)
    await wrapper.findAll('button').find(button => button.text().includes('Expand')).trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-testid="conversation-history"]').exists()).toBe(true)
    wrapper.unmount()
  })

  it('loads group and announcement sections independently', async () => {
    const account = { id: 7, name: 'Primary WhatsApp', phone_number: '', session_status: 'connected' }
    api.conversations.mockResolvedValue({ data: { count: 0, next: null, accounts: [account], results: [] } })
    const wrapper = mount(ClientConversationHistory, { props: { profileId: 3 } })
    await flushPromises()

    await wrapper.findAll('[role="tab"]').find(tab => tab.text().includes('Group Messages')).trigger('click')
    await flushPromises()
    expect(api.conversations).toHaveBeenLastCalledWith(3, {
      page: 1, page_size: 25, conversation_type: 'group',
    })

    await wrapper.findAll('[role="tab"]').find(tab => tab.text().includes('Announcements')).trigger('click')
    await flushPromises()
    expect(api.conversations).toHaveBeenLastCalledWith(3, {
      page: 1, page_size: 25, conversation_type: 'announcement',
    })
    wrapper.unmount()
  })
})
