import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ChatList from '../ChatList.vue'
import { useAuthStore } from '@/stores/auth'
import { useConversationsStore } from '@/stores/conversations'

vi.mock('@/api', () => ({ accountsApi: {}, chatsApi: {} }))

const chats = [
  { id: 1, wa_chat_id: '237600000001@s.whatsapp.net', display_name: 'Converted Buyer', clientpulse_profile_id: 9, unread_count: 0 },
  { id: 2, wa_chat_id: '237600000002@s.whatsapp.net', display_name: 'New Lead', clientpulse_profile_id: null, unread_count: 0 },
  { id: 3, wa_chat_id: '120363000000000001@g.us', display_name: 'Traders Group', clientpulse_profile_id: null, unread_count: 0 },
]
const tab = (wrapper, label) => wrapper.findAll('.chat-list__tab').find(item => item.text() === label)
const names = wrapper => wrapper.findAll('[data-chat-id]').map(row => row.attributes('data-chat-id'))

describe('ChatList ClientPulse filter', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    useAuthStore().user = { current_company: { id: 2 }, permissions: { 'clientpulse.clients.view': 'all' } }
    useConversationsStore().chats = chats
  })

  it('splits chats into ClientPulse clients and direct chats not yet converted', async () => {
    const wrapper = mount(ChatList)
    await tab(wrapper, 'ClientPulse').trigger('click')
    expect(names(wrapper)).toEqual(['1'])
    await tab(wrapper, 'Not in ClientPulse').trigger('click')
    expect(names(wrapper)).toEqual(['2'])
  })

  it('shows a converted chat under ClientPulse straight away', async () => {
    const wrapper = mount(ChatList)
    await tab(wrapper, 'ClientPulse').trigger('click')
    useConversationsStore().markClientPulse(2, 15)
    await wrapper.vm.$nextTick()
    expect(names(wrapper)).toEqual(['1', '2'])
  })

  it('hides the ClientPulse tabs from members who cannot see ClientPulse', () => {
    useAuthStore().user.permissions = {}
    const wrapper = mount(ChatList)
    expect(tab(wrapper, 'ClientPulse')).toBeUndefined()
    expect(tab(wrapper, 'Not in ClientPulse')).toBeUndefined()
  })
})
