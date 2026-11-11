import { useTradingConversationDialog } from '@/features/trading/composables/useTradingConversationDialog'
import { useConversationsStore } from '@/stores/conversations'

// WhatsApp actions for a Real Estate opportunity, shared by the board, search and detail
// pages. Reuses the Trading conversation dialog (MessagePanel in a modal) - nothing in it
// is trading-specific, it just lives under that feature folder.
export function useOpportunityWhatsApp() {
  const dialog = useTradingConversationDialog(useConversationsStore())

  function sourceTarget(opportunity) {
    return {
      account: opportunity.account,
      source_chat_id: opportunity.source_chat,
      source_message_id: opportunity.source_message,
      source_message_time: opportunity.source_message_time,
      contact_name: opportunity.contact_name,
      contact_phone: opportunity.contact_phone,
    }
  }

  // The original message in the dialog, jumped to and marked.
  function viewSource(opportunity) {
    if (!opportunity?.source_chat) return
    dialog.openSource(sourceTarget(opportunity), { title: 'Original Message', draft: '' })
  }

  // The same message in the full WhatsApp Inbox page.
  function openInInbox(opportunity) {
    if (!opportunity?.source_chat) return
    dialog.openSourceInInbox(sourceTarget(opportunity))
  }

  // One-to-one chat with the opportunity's contact (even when the source was a group),
  // ready to type a message.
  function messageContact(opportunity) {
    if (!opportunity?.contact) return
    dialog.openDirect({
      account: opportunity.account,
      contact: opportunity.contact,
      contact_name: opportunity.contact_name,
      contact_phone: opportunity.contact_phone,
    }, { title: 'Direct Message', draft: '' })
  }

  return { dialog, viewSource, openInInbox, messageContact }
}
