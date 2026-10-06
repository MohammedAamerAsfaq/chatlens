const option = (value, label) => ({
  value,
  label: label || value.replaceAll('_', ' '),
})

export const contactTypeOptions = [option('person', 'Person'), option('organization', 'Organization')]
export const lifecycleOptions = ['lead', 'prospect', 'active_customer', 'dormant', 'lost', 'blocked'].map(value => option(value))
export const priorityOptions = ['low', 'normal', 'high', 'critical'].map(value => option(value))
export const channelOptions = [option('', 'Not set'), ...['whatsapp', 'email', 'phone', 'other'].map(value => option(value))]
export const identityTypeOptions = [option('phone', 'Phone'), option('email', 'Email'), option('whatsapp_jid', 'WhatsApp JID')]
export const consentChannelOptions = ['whatsapp', 'email', 'phone'].map(value => option(value))
export const consentPurposeOptions = ['transactional', 'follow_up', 'marketing'].map(value => option(value))
export const consentStatusOptions = ['unknown', 'granted', 'denied', 'revoked'].map(value => option(value))
export const ownerOption = (value, label) => option(value, label)
