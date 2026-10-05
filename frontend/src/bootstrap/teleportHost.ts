export const TELEPORT_HOST_ID = 'ui-teleport-host'

export function ensureTeleportHost(documentRef: Document = document): HTMLElement {
  const existingHost = documentRef.getElementById(TELEPORT_HOST_ID)
  if (existingHost) return existingHost

  const host = documentRef.createElement('div')
  host.id = TELEPORT_HOST_ID

  const appRoot = documentRef.getElementById('app')
  if (appRoot?.parentNode) {
    appRoot.parentNode.insertBefore(host, appRoot)
  } else {
    documentRef.body.append(host)
  }

  return host
}
