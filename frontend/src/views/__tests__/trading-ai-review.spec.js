import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import TradingAiReviewView from '../TradingAiReviewView.vue'
const api = vi.hoisted(() => ({ batchNext: vi.fn(), reviewNext: vi.fn(), correct: vi.fn(), submit: vi.fn() }))
vi.mock('@/api', () => ({ tradingReviewApi: api }))
const ai = { is_inquiry: true, direction: 'buy', products: [{ canonical_name: 'Phone 256GB', quantity: 2, price: 100, currency: 'AED' }], version: 'v2' }
const sample = { available: true, done: false, batch_name: 'Batch', total: 2, completed: 0, position: 1, message_id: 10, text: 'WTB two phones at AED 100', sampling_pool: 'buy', duplicate_count: 0, ai }
const button = (wrapper, name) => wrapper.findAll('button').find(item => item.text() === name)
describe('Trading AI quick review', () => {
  beforeEach(() => { vi.clearAllMocks(); api.batchNext.mockResolvedValue({ data: sample }); api.submit.mockResolvedValue({ data: { id: 1 } }); api.correct.mockResolvedValue({ data: { id: 1 } }) })
  it('shows all label fields and confirms only when clicked', async () => {
    const wrapper = mount(TradingAiReviewView); await flushPromises()
    expect(wrapper.text()).toContain('Phone 256GB'); expect(wrapper.text()).toContain('Quantity: 2'); expect(wrapper.text()).toContain('Price: 100 AED')
    expect(wrapper.find('form').exists()).toBe(false); expect(api.submit).not.toHaveBeenCalled()
    await button(wrapper, 'Correct').trigger('click'); await flushPromises()
    expect(api.submit).toHaveBeenCalledWith({ message_id: 10, label: { is_inquiry: true, direction: 'buy', products: [{ name: 'Phone 256GB', quantity: '2', price: '100', currency: 'AED' }], notes: '' } })
  })
  it('opens an editor and saves the correction', async () => {
    const wrapper = mount(TradingAiReviewView); await flushPromises(); await button(wrapper, 'Needs correction').trigger('click')
    await wrapper.findAll('.product input')[1].setValue('3'); await wrapper.find('form').trigger('submit'); await flushPromises()
    expect(api.submit.mock.calls[0][0].label.products[0].quantity).toBe('3')
  })
  it('skips without saving and refuses to confirm an unnamed product', async () => {
    api.batchNext.mockResolvedValue({ data: { ...sample, ai: { ...ai, products: [{}] } } })
    const wrapper = mount(TradingAiReviewView); await flushPromises()
    expect(button(wrapper, 'Correct').attributes('disabled')).toBeDefined(); await button(wrapper, 'Skip').trigger('click'); await flushPromises()
    expect(api.submit).not.toHaveBeenCalled(); expect(api.batchNext).toHaveBeenLastCalledWith(1)
  })
  it('confirms AI reviews using the original label for concurrency checking', async () => {
    const original = { is_inquiry: true, direction: 'buy', products: [{ name: 'Phone', quantity: '2' }], notes: 'AI review by OpenAI Codex; not human-verified.' }
    api.reviewNext.mockResolvedValue({ data: { done: false, review_id: 9, message_id: 10, origin: 'ai', text: sample.text, ai, label: original } })
    const wrapper = mount(TradingAiReviewView); await flushPromises(); await wrapper.find('header select').setValue('ai'); await flushPromises()
    await button(wrapper, 'Correct').trigger('click'); await flushPromises()
    expect(api.correct).toHaveBeenCalledWith({ review_id: 9, expected_label: original, label: { ...original, notes: '' } })
  })
})
