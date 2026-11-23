import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import ReportSummaryView from '../ReportSummaryView.vue'

const api = vi.hoisted(() => ({ accounts: { list: vi.fn() }, trading: { getReportSummary: vi.fn() } }))
vi.mock('../../api/index.js', () => ({ accountsApi: api.accounts, tradingApi: api.trading }))

const report = inquiries => ({ total_messages_received: inquiries * 10, total_inquiries_created: inquiries, status_breakdown: [] })

function deferred() {
  let resolve, reject
  const promise = new Promise((res, rej) => { resolve = res; reject = rej })
  return { promise, resolve, reject }
}

const inquiriesTile = wrapper => wrapper.findAll('.tile').find(tile => tile.text().includes('Inquiries Created'))

describe('ReportSummaryView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers()
    api.accounts.list.mockResolvedValue({ data: [] })
  })
  afterEach(() => vi.useRealTimers())

  it('dims the old numbers while a new selection loads', async () => {
    const yearly = deferred()
    api.trading.getReportSummary.mockResolvedValueOnce({ data: report(440) }).mockReturnValueOnce(yearly.promise)
    const wrapper = mount(ReportSummaryView)
    await flushPromises()
    expect(wrapper.find('.page-body').classes()).not.toContain('stale')

    await wrapper.find('select').setValue('This Year')
    await flushPromises()
    expect(wrapper.find('.page-body').classes()).toContain('stale')
    expect(wrapper.find('.last-update').text()).toBe('Loading…')

    yearly.resolve({ data: report(83178) })
    await flushPromises()
    expect(wrapper.find('.page-body').classes()).not.toContain('stale')
    expect(inquiriesTile(wrapper).text()).toContain('83178')
    expect(wrapper.find('.last-update').text()).toBe('Updated just now')
  })

  it('ignores an older request that answers after a newer one', async () => {
    const slow = deferred()
    api.trading.getReportSummary
      .mockResolvedValueOnce({ data: report(1) })
      .mockReturnValueOnce(slow.promise)
      .mockResolvedValueOnce({ data: report(30) })
    const wrapper = mount(ReportSummaryView)
    await flushPromises()

    await wrapper.find('select').setValue('This Year')
    await wrapper.find('select').setValue('This Month')
    await flushPromises()
    slow.resolve({ data: report(83178) })
    await flushPromises()

    expect(inquiriesTile(wrapper).text()).toContain('30')
    expect(inquiriesTile(wrapper).text()).not.toContain('83178')
    expect(wrapper.find('.page-body').classes()).not.toContain('stale')
  })

  it('says when the report could not load instead of keeping old numbers silently', async () => {
    api.trading.getReportSummary
      .mockResolvedValueOnce({ data: report(440) })
      .mockRejectedValueOnce({ response: { status: 502 } })
    const wrapper = mount(ReportSummaryView)
    await flushPromises()
    await wrapper.find('select').setValue('This Year')
    await flushPromises()
    expect(wrapper.find('[role="alert"]').text()).toContain('server error 502')
    expect(wrapper.find('[role="alert"]').text()).toContain('previous selection')
    expect(wrapper.find('.page-body').classes()).toContain('stale')
  })

  it('does not start an auto-refresh while one is still running, and the age keeps counting', async () => {
    const slow = deferred()
    api.trading.getReportSummary.mockResolvedValueOnce({ data: report(1) }).mockReturnValueOnce(slow.promise)
    const wrapper = mount(ReportSummaryView)
    await flushPromises()
    vi.advanceTimersByTime(30000)
    await flushPromises()
    expect(wrapper.find('.last-update').text()).toBe('Updated 30s ago · refreshing…')
    vi.advanceTimersByTime(30000)
    await flushPromises()
    expect(api.trading.getReportSummary).toHaveBeenCalledTimes(2)
    slow.resolve({ data: report(2) })
    await flushPromises()
    expect(wrapper.find('.last-update').text()).toBe('Updated just now')
  })
})
