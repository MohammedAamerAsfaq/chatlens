import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { nextTick } from 'vue'
import ClientEditorModal from '../ClientEditorModal.vue'

describe('ClientEditorModal', () => {
  it('renders manual client inputs inside a full, tall dialog', async () => {
    const host = document.createElement('div')
    host.id = 'ui-teleport-host'
    document.body.append(host)
    const form = {
      creation_mode: 'manual', whatsapp_contact_id: '', contact_search: '',
      display_name: '', phone: '', lifecycle_stage: 'lead', priority: 'normal', owner_id: '',
    }
    const wrapper = mount(ClientEditorModal, {
      attachTo: document.body,
      props: { open: true, form },
    })
    await nextTick()
    await nextTick()

    expect(host.querySelector('.ui-modal--full.ui-modal--tall')).not.toBeNull()
    expect(host.querySelector('input[placeholder="Person or company name"]')).not.toBeNull()
    expect(host.querySelector('input[placeholder="e.g. 971501234567"]')).not.toBeNull()

    wrapper.unmount()
    host.remove()
  })
})
