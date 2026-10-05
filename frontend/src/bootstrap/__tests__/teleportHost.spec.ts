import { beforeEach, describe, expect, it } from 'vitest'
import { ensureTeleportHost, TELEPORT_HOST_ID } from '../teleportHost'

describe('teleport host bootstrap', () => {
  beforeEach(() => {
    document.body.innerHTML = '<div id="app"></div>'
  })

  it('creates the host before the Vue application root', () => {
    const host = ensureTeleportHost()

    expect(host.id).toBe(TELEPORT_HOST_ID)
    expect(document.body.firstElementChild).toBe(host)
    expect(host.nextElementSibling?.id).toBe('app')
  })

  it('reuses an existing host instead of replacing it', () => {
    const existingHost = document.createElement('div')
    existingHost.id = TELEPORT_HOST_ID
    existingHost.dataset.marker = 'existing'
    document.body.prepend(existingHost)

    expect(ensureTeleportHost()).toBe(existingHost)
    expect(document.querySelectorAll(`#${TELEPORT_HOST_ID}`)).toHaveLength(1)
  })
})
