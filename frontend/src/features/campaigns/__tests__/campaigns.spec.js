import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import CampaignAttachmentPanel from '../components/CampaignAttachmentPanel.vue'
import CampaignModeSelector from '../components/CampaignModeSelector.vue'
import CampaignSearchActions from '../components/CampaignSearchActions.vue'
import { campaignCharacterCount, campaignImageError, campaignMessageLimit } from '../constants'
import { addAllCampaignResults, fetchAllPaginatedResults } from '../bulkSelection'

describe('campaign feature', () => {
  it('uses shared WhatsApp message and image constraints', () => {
    expect(campaignCharacterCount('A😀')).toBe(2)
    expect(campaignMessageLimit(false)).toBe(10000)
    expect(campaignMessageLimit(true)).toBe(1024)
    expect(campaignImageError({ type: 'text/plain', size: 12 })).toContain('JPEG')
  })

  it('switches between formatted and direct campaign modes', async () => {
    const wrapper = mount(CampaignModeSelector, {
      props: { modelValue: 'formatted', formattedDescription: 'Use products.', directDescription: 'Write a message.' },
    })
    await wrapper.findAll('button')[1].trigger('click')
    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual(['direct'])
  })

  it('shows the image-caption limit for a persisted attachment', () => {
    const wrapper = mount(CampaignAttachmentPanel, {
      props: { message: 'Offer', asset: { image_asset: 7, image_url: '/image.jpg' } },
    })
    expect(wrapper.text()).toContain('1,024')
    expect(wrapper.text()).toContain('retained after refresh')
  })

  it('tracks successful and failed bulk recipient additions', async () => {
    const rows = [{ id: 1 }, { id: 2 }, { id: 3 }]
    const result = await addAllCampaignResults(rows, row => (
      row.id === 2 ? Promise.reject(new Error('blocked')) : Promise.resolve()
    ))
    expect(result.succeeded.map(row => row.id)).toEqual([1, 3])
    expect(result.failed.map(row => row.id)).toEqual([2])
  })

  it('fetches every page of campaign search results', async () => {
    const pages = [
      { results: [{ id: 1 }], next: '/contacts/?page=2' },
      { results: [{ id: 2 }], next: null },
    ]
    const rows = await fetchAllPaginatedResults(page => pages[page - 1])
    expect(rows.map(row => row.id)).toEqual([1, 2])
  })

  it('offers current-view and complete-result bulk actions', async () => {
    const wrapper = mount(CampaignSearchActions, {
      props: { visibleCount: 10, totalCount: 24, page: 2, totalPages: 3 },
    })
    expect(wrapper.text()).toContain('24 results')
    await wrapper.findAll('button')[0].trigger('click')
    await wrapper.findAll('button')[1].trigger('click')
    expect(wrapper.emitted('add-view')).toHaveLength(1)
    expect(wrapper.emitted('add-all')).toHaveLength(1)
  })
})
