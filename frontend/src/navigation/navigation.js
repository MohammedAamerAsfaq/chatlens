export const primaryNavigation = [
  {
    id: 'conversations', label: 'Inbox', to: '/conversations', routes: ['conversations'],
    children: [
      { label: 'WhatsApp', to: '/conversations', route: 'conversations' },
    ],
  },
  {
    id: 'trading', label: 'Trading', to: '/trading',
    routes: ['trading', 'products', 'inquiry-products', 'non-inventory-products', 'v2-candidate-search', 'product-price-update'],
    children: [
      { label: 'Dashboard', to: '/trading', route: 'trading' },
      { label: 'Products', to: '/products', route: 'products' },
      { label: 'Inquiry Products', to: '/inquiry-products', route: 'inquiry-products' },
      { label: 'Non-Inventory', to: '/non-inventory-products', route: 'non-inventory-products' },
      { label: 'Candidate Search', to: '/v2-candidate-search', route: 'v2-candidate-search' },
      { label: 'Price Updates', to: '/product-price-update', route: 'product-price-update' },
    ],
  },
  {
    id: 'automation', label: 'Automation', to: '/automation',
    routes: ['price-automation'],
    children: [
      { label: 'Price Automation', to: '/automation', route: 'price-automation' },
    ],
  },
  {
    id: 'clientpulse', label: 'ClientPulse', to: '/clientpulse', permission: 'clientpulse.clients.view',
    routes: ['clientpulse', 'clientpulse-profile', 'clientpulse-reminders'],
    children: [
      { label: 'Customers', to: '/clientpulse', route: 'clientpulse', permission: 'clientpulse.clients.view' },
      { label: 'Reminders', to: '/clientpulse-reminders', route: 'clientpulse-reminders', permission: 'clientpulse.reminders.view' },
    ],
  },
  {
    id: 'campaigns', label: 'Campaigns', to: '/buying-inquiries',
    routes: ['buying-inquiries', 'selling-offers', 'group-buying-inquiries', 'group-selling-offers'],
    children: [
      { label: 'Direct Buying', to: '/buying-inquiries', route: 'buying-inquiries' },
      { label: 'Direct Selling', to: '/selling-offers', route: 'selling-offers' },
      { label: 'Group Buying', to: '/group-buying-inquiries', route: 'group-buying-inquiries' },
      { label: 'Group Selling', to: '/group-selling-offers', route: 'group-selling-offers' },
    ],
  },
  {
    id: 'reports', label: 'Reports', to: '/trading-analytics',
    routes: ['trading-analytics', 'report-summary', 'inventory-product-mentions', 'selling-offers-report'],
    children: [
      { label: 'Analytics', to: '/trading-analytics', route: 'trading-analytics' },
      { label: 'Summary', to: '/report-summary', route: 'report-summary' },
      { label: 'Product Mentions', to: '/inventory-product-mentions', route: 'inventory-product-mentions' },
      { label: 'Selling Offers', to: '/selling-offers-report', route: 'selling-offers-report' },
    ],
  },
]

export const moreNavigation = [
  { label: 'Contacts', to: '/contacts', route: 'contacts' },
  { label: 'Groups', to: '/groups', route: 'groups' },
]

export const settingsNavigation = [
  { label: 'Sessions', to: '/', route: 'sessions' },
  { label: 'Storage', to: '/storage', route: 'storage' },
  { label: 'AI Providers', to: '/ai-providers', route: 'ai-providers' },
  { label: 'KiwiRouter', to: '/kiwi-router', route: 'kiwi-router' },
  { label: 'AI Instructions', to: '/ai-instructions', route: 'ai-instructions' },
  { label: 'V2 Settings', to: '/v2-settings', route: 'v2-settings' },
  { label: 'V2 Match Training', to: '/v2-match-training', route: 'v2-match-training' },
  { label: 'Inquiry Forwarding', to: '/inquiry-forwarding', route: 'inquiry-forwarding' },
  { label: 'Task & Queues', to: '/task-queues', route: 'task-queues' },
  { label: 'ClientPulse', to: '/clientpulse-settings', route: 'clientpulse-settings', permission: 'settings.company.view' },
  { label: 'Users', to: '/company-users', route: 'company-users', permission: 'users.memberships.view' },
  { label: 'Roles & Permissions', to: '/company-roles', route: 'company-roles', permission: 'users.roles.view' },
  { label: 'Tenant Admin', to: '/tenant-admin', route: 'tenant-admin', tenantAdmin: true },
]

export const logsNavigation = [
  { label: 'Activity', to: '/activity', route: 'activity' },
  { label: 'Message Logs', to: '/message-logs', route: 'message-logs' },
  { label: 'Dropped', to: '/dropped-messages', route: 'dropped-messages' },
  { label: 'Baileys Events', to: '/baileys-events', route: 'baileys-events' },
  { label: 'Message Trace', to: '/message-trace', route: 'message-trace' },
  { label: 'Worker Alerts', to: '/worker-alerts', route: 'worker-alerts', badge: 'worker' },
  { label: 'Stuck Receipts', to: '/stuck-receipts', route: 'stuck-receipts', badge: 'receipts' },
  { label: 'Unresolved Messages', to: '/unresolved-messages', route: 'unresolved-messages', badge: 'messages' },
  { label: 'AI Parsing', to: '/ai-parsing-log', route: 'ai-parsing-log' },
  { label: 'AI Parse V2', to: '/ai-parse-v2-log', route: 'ai-parse-v2-log' },
  { label: 'Task Operations', to: '/task-operations', route: 'task-operations' },
]
