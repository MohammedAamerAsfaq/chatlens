export async function addAllCampaignResults(items, addItem, concurrency = 5) {
  const rows = [...items]
  const outcomes = Array(rows.length)
  let cursor = 0
  async function worker() {
    while (cursor < rows.length) {
      const index = cursor++
      try {
        await addItem(rows[index])
        outcomes[index] = { status: 'fulfilled' }
      } catch (reason) {
        outcomes[index] = { status: 'rejected', reason }
      }
    }
  }
  const workerCount = Math.min(Math.max(1, concurrency), rows.length)
  await Promise.all(Array.from({ length: workerCount }, worker))
  return outcomes.reduce((result, outcome, index) => {
    result[outcome.status === 'fulfilled' ? 'succeeded' : 'failed'].push(rows[index])
    return result
  }, { succeeded: [], failed: [] })
}

export async function fetchAllPaginatedResults(loadPage, pageSize = 100) {
  const rows = []
  let page = 1
  let hasNext = true
  while (hasNext) {
    const data = await loadPage(page, pageSize)
    rows.push(...(data.results || data))
    hasNext = Boolean(data.next)
    page += 1
  }
  return rows
}
