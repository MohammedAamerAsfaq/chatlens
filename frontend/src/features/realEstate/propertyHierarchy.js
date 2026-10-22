const PAGE_SIZE = 100

function asHierarchyOption(property) {
  return {
    id: property.id,
    title: property.title,
    reference_code: property.reference_code || '',
    parent_id: property.parent || null,
  }
}

async function loadFromPropertyPages(api) {
  const records = []
  let page = 1
  let total = 0

  do {
    const { data } = await api.properties({ page, page_size: PAGE_SIZE, ordering: 'title' })
    records.push(...data.results.map(asHierarchyOption))
    total = data.count
    page += 1
  } while (records.length < total)

  return records
}

export async function loadPropertyHierarchy(api) {
  try {
    return (await api.propertyHierarchyOptions()).data
  } catch (error) {
    if (error?.response?.status !== 404) throw error
    return loadFromPropertyPages(api)
  }
}
