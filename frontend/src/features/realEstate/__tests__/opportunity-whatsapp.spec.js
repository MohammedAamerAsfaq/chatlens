import { describe, expect, it, vi } from 'vitest'

const dialog = { openSource: vi.fn(), openSourceInInbox: vi.fn(), openDirect: vi.fn() }
vi.mock('@/features/trading/composables/useTradingConversationDialog', () => ({
  useTradingConversationDialog: () => dialog,
}))
vi.mock('@/stores/conversations', () => ({ useConversationsStore: () => ({}) }))

import { useOpportunityWhatsApp } from '../composables/useOpportunityWhatsApp'

const opportunity = {
  account: 3, contact: 9, source_chat: 7, source_message: 11,
  source_message_time: '2026-11-11T10:00:00Z', contact_name: 'Saidou', contact_phone: '971582686979',
}
const source = {
  account: 3, source_chat_id: 7, source_message_id: 11, source_message_time: '2026-11-11T10:00:00Z',
  contact_name: 'Saidou', contact_phone: '971582686979',
}

describe('opportunity WhatsApp actions', () => {
  it('opens the source message in the dialog and in the Inbox', () => {
    const actions = useOpportunityWhatsApp()
    actions.viewSource(opportunity)
    actions.openInInbox(opportunity)

    expect(dialog.openSource).toHaveBeenCalledWith(source, { title: 'Original Message', draft: '' })
    expect(dialog.openSourceInInbox).toHaveBeenCalledWith(source)
  })

  it('opens the direct chat with the contact', () => {
    useOpportunityWhatsApp().messageContact(opportunity)

    expect(dialog.openDirect).toHaveBeenCalledWith(
      { account: 3, contact: 9, contact_name: 'Saidou', contact_phone: '971582686979' },
      { title: 'Direct Message', draft: '' },
    )
  })

  it('does nothing without a source chat or contact', () => {
    vi.clearAllMocks()
    const actions = useOpportunityWhatsApp()
    actions.viewSource({ ...opportunity, source_chat: null })
    actions.openInInbox({ ...opportunity, source_chat: null })
    actions.messageContact({ ...opportunity, contact: null })

    expect(dialog.openSource).not.toHaveBeenCalled()
    expect(dialog.openSourceInInbox).not.toHaveBeenCalled()
    expect(dialog.openDirect).not.toHaveBeenCalled()
  })
})
