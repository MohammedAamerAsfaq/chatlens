import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import AIProvidersView from '../AIProvidersView.vue'

const api = vi.hoisted(() => ({
  providers: {
    list: vi.fn(), meta: vi.fn(), agentTarget: vi.fn(), fetchModels: vi.fn(), lookupModel: vi.fn(), update: vi.fn(),
  },
  routers: { list: vi.fn() },
}))
vi.mock('@/api/index.js', () => ({ aiProvidersApi: api.providers, kiwiRoutersApi: api.routers }))

const saved = {
  id: 7, display_name: 'Main agent', provider: 'openai', provider_label: 'OpenAI', capability: 'agent',
  model: 'my-fine-tune', is_active: true, base_url: '', api_key_masked: 'sk-…abcd', extra_config: { rate_limit_rpm: 60 },
}
const info = {
  catalog_id: 'openai/gpt-4o-mini', name: 'OpenAI: GPT-4o-mini', description: '', context_length: 128000,
  max_output_tokens: 16384, input_cost_per_million: 0.15, output_cost_per_million: 0.6,
  supported_parameters: ['max_tokens', 'tools'], input_modalities: ['text', 'image'],
}

async function openEdit() {
  const wrapper = mount(AIProvidersView, { global: { stubs: { teleport: true } } })
  await flushPromises()
  await wrapper.findAll('button').find(b => b.text() === 'Edit').trigger('click')
  await flushPromises()
  return wrapper
}

const modelInput = wrapper => wrapper.find('input[placeholder="Enter model name or fetch from provider"]')
const button = (wrapper, text) => wrapper.findAll('button').find(b => b.text().includes(text))

describe('AI Providers model lookup', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    api.providers.list.mockResolvedValue({ data: [saved] })
    api.providers.meta.mockResolvedValue({ data: { providers: { openai: 'OpenAI' }, capabilities: {}, models: {} } })
    api.providers.agentTarget.mockResolvedValue({ data: { mode: 'direct' } })
    api.routers.list.mockResolvedValue({ data: [] })
    api.providers.fetchModels.mockResolvedValue({ data: { models: ['gpt-4o', 'gpt-4o-mini'], source: 'api' } })
    api.providers.update.mockResolvedValue({ data: {} })
  })

  it('keeps a typed model name that the list does not have', async () => {
    const wrapper = await openEdit()
    expect(modelInput(wrapper).element.value).toBe('my-fine-tune')
    await button(wrapper, 'Choose from the list instead').trigger('click')
    expect(wrapper.find('select[required] option[value="gpt-4o-mini"]').exists()).toBe(true)
  })

  it('verifies a typed name, offers close names, and saves the rates it found', async () => {
    api.providers.lookupModel
      .mockResolvedValueOnce({ data: {
        verified: false, model: 'gpt-4o-mni', detail: 'OpenAI has no model named "gpt-4o-mni".',
        suggestions: ['gpt-4o-mini'], info: null, info_source: '', info_detail: 'No listing.',
      } })
      .mockResolvedValueOnce({ data: {
        verified: true, model: 'gpt-4o-mini', detail: 'OpenAI lists "gpt-4o-mini".', suggestions: [],
        info, info_source: 'openrouter_catalog', info_detail: 'From OpenRouter.', checked_at: '2026-11-24T10:00:00Z',
      } })
    const wrapper = await openEdit()
    await modelInput(wrapper).setValue('gpt-4o-mni')
    await button(wrapper, 'Verify & get rates').trigger('click')
    await flushPromises()
    expect(api.providers.lookupModel).toHaveBeenLastCalledWith(expect.objectContaining({ config_id: 7, model: 'gpt-4o-mni' }))
    expect(wrapper.text()).toContain('Model name not confirmed')

    await wrapper.find('.model-lookup__suggestion').trigger('click')
    await flushPromises()
    expect(modelInput(wrapper).element.value).toBe('gpt-4o-mini')
    const facts = wrapper.find('.model-lookup__facts').text()
    expect(facts).toContain('$0.15 / 1M tokens')
    expect(facts).toContain('$0.6 / 1M tokens')
    expect(facts).toContain('128K tokens')
    expect(facts).toContain('16.4K tokens')
    expect(wrapper.find('.model-lookup').text()).toContain('tools')

    await wrapper.find('form').trigger('submit')
    await flushPromises()
    const [, payload] = api.providers.update.mock.calls[0]
    expect(payload.model).toBe('gpt-4o-mini')
    expect(payload.extra_config).toMatchObject({
      rate_limit_rpm: 60, input_price_per_1m: 0.15, output_price_per_1m: 0.6,
      model_info: { context_length: 128000, source: 'openrouter_catalog', checked_at: '2026-11-24T10:00:00Z' },
    })
  })

  it('forgets looked-up details when the name is changed afterwards', async () => {
    api.providers.lookupModel.mockResolvedValue({ data: {
      verified: true, model: 'gpt-4o-mini', detail: 'ok', suggestions: [], info, info_source: 'openrouter_catalog', info_detail: '',
    } })
    const wrapper = await openEdit()
    await modelInput(wrapper).setValue('gpt-4o-mini')
    await button(wrapper, 'Verify & get rates').trigger('click')
    await flushPromises()
    await modelInput(wrapper).setValue('gpt-4o')
    expect(wrapper.find('.model-lookup').exists()).toBe(false)
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    const [, payload] = api.providers.update.mock.calls[0]
    expect(payload.extra_config.model_info).toBeUndefined()
    expect(payload.extra_config.input_price_per_1m).toBeUndefined()
  })
})
