const cleanText = value => String(value ?? '').replace(/\s+/g, ' ').trim()
const elementText = element => element?.innerText ?? element?.textContent ?? ''

function storageKey(binding) {
  return `chatlens:datatable:${binding.value || 'grid'}:hidden`
}

function readHidden(key) {
  try { return new Set(JSON.parse(localStorage.getItem(key) || '[]')) } catch { return new Set() }
}

function cellsForColumn(table, index) {
  return [...table.querySelectorAll(`tr > :nth-child(${index + 1})`)]
    .filter(cell => cell.parentElement.children.length > 1)
}

function applyVisibility(table, hidden) {
  const count = table.querySelectorAll('thead th').length
  for (let index = 0; index < count; index += 1) {
    cellsForColumn(table, index).forEach(cell => { cell.style.display = hidden.has(index) ? 'none' : '' })
  }
}

function exportCsv(table, filename) {
  const hidden = table.__uiGridHidden || new Set()
  const rows = [...table.querySelectorAll('tr')]
    .filter(row => !row.closest('.ui-data-table__detail') && ![...row.children].some(cell => cell.colSpan > 1) && row.offsetParent !== null)
    .map(row => [...row.children]
      .filter((_, index) => !hidden.has(index))
      .map(cell => `"${cleanText(elementText(cell)).replaceAll('"', '""')}"`).join(','))
  const link = document.createElement('a')
  link.href = URL.createObjectURL(new Blob([`\ufeff${rows.join('\r\n')}`], { type: 'text/csv;charset=utf-8' }))
  link.download = `${filename || 'records'}.csv`
  link.click()
  URL.revokeObjectURL(link.href)
}

function createTools(table, binding) {
  if (table.dataset.uiGridReady) return table.__uiGridTools
  table.dataset.uiGridReady = 'true'
  const key = storageKey(binding)
  const hidden = readHidden(key)
  table.__uiGridHidden = hidden
  table.classList.add('ui-data-table__native')
  const compact = table.querySelectorAll('thead th').length <= 4
    || table.matches('.mini-table, .stats-table, .ui-table--compact')
  table.classList.toggle('ui-data-table__native--compact', compact)
  table.parentElement?.classList.add('ui-data-table__legacy-viewport')
  table.parentElement?.classList.toggle('ui-data-table__legacy-viewport--compact', compact)

  const tools = document.createElement('div')
  tools.className = 'ui-data-table__bridge-tools'
  const columns = document.createElement('details')
  const summary = document.createElement('summary')
  summary.textContent = 'Columns'
  columns.append(summary)
  const menu = document.createElement('div')
  menu.className = 'ui-data-table__bridge-menu'

  ;[...table.querySelectorAll('thead th')].forEach((header, index, headers) => {
    const label = document.createElement('label')
    const checkbox = document.createElement('input')
    checkbox.type = 'checkbox'
    checkbox.checked = !hidden.has(index)
    checkbox.disabled = checkbox.checked && headers.length - hidden.size === 1
    checkbox.addEventListener('change', () => {
      checkbox.checked ? hidden.delete(index) : hidden.add(index)
      localStorage.setItem(key, JSON.stringify([...hidden]))
      applyVisibility(table, hidden)
      menu.querySelectorAll('input').forEach(input => { input.disabled = input.checked && headers.length - hidden.size === 1 })
    })
    label.append(checkbox, document.createTextNode(cleanText(elementText(header)) || `Column ${index + 1}`))
    menu.append(label)
  })
  columns.append(menu)

  const exportButton = document.createElement('button')
  exportButton.type = 'button'
  exportButton.textContent = 'Export CSV'
  exportButton.addEventListener('click', () => exportCsv(table, binding.value))
  tools.append(columns, exportButton)
  table.parentElement?.insertBefore(tools, table)
  applyVisibility(table, hidden)
  return tools
}

export const uiDataTable = {
  mounted(table, binding) { table.__uiGridTools = createTools(table, binding) },
  updated(table) { applyVisibility(table, table.__uiGridHidden || new Set()) },
  unmounted(table) { table.__uiGridTools?.remove() },
}

export function installUiDataTableObserver() {
  const enhanceTaskLedgers = root => {
    root.querySelectorAll?.('table.task-table:not([data-ui-grid-ready])').forEach(table => {
      const firstHeading = cleanText(elementText(table.querySelector('thead th')))
      table.__uiGridTools = createTools(table, { value: firstHeading === 'Task' ? 'execution-ledger' : 'outbound-ledger' })
    })
  }
  enhanceTaskLedgers(document)
  const observer = new MutationObserver(records => records.forEach(record => record.addedNodes.forEach(node => {
    if (node.nodeType === Node.ELEMENT_NODE) enhanceTaskLedgers(node)
  })))
  observer.observe(document.body, { childList: true, subtree: true })
  document.addEventListener('click', event => {
    document.querySelectorAll('.ui-data-table__bridge-tools details[open]').forEach(details => {
      if (!details.contains(event.target)) details.removeAttribute('open')
    })
  })
  return observer
}
