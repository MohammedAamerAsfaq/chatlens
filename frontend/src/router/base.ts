export function resolveRouterBase(configuredBase?: string): string {
  const normalized = configuredBase?.trim()
  return normalized || '/'
}
