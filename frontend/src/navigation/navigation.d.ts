export interface NavigationItem {
  label: string
  to: string
  route: string
  permission?: string
  requiresCompanyAdmin?: boolean
  tenantAdmin?: boolean
  industries?: string[]
  badge?: string
  personal?: boolean
  [key: string]: unknown
}

export const primaryNavigation: NavigationItem[]
export const moreNavigation: NavigationItem[]
export const settingsNavigation: NavigationItem[]
export const logsNavigation: NavigationItem[]
export function navigationItemVisible(item: NavigationItem, context: Record<string, unknown>): boolean
export function visibleSettingsNavigation(context: Record<string, unknown>): NavigationItem[]
export function industryHomePath(industry: string | undefined): string
