# Mobile UI Rollout Strategy

## Purpose

This document defines the implementation strategy for adding a mobile-friendly ERP interface without putting the current desktop experience at risk.

The goal is:

- a mobile presentation that feels closer to a native app
- a user-selectable toggle between:
  - existing desktop-like view on mobile
  - new mobile-friendly view
- a detachable implementation with minimal coupling to the current theme and templates

Initial rollout scope:

- Dashboard
- Product List
- Product Add/Update

## Non-Negotiable Constraints

The mobile implementation must follow these rules:

1. Do not modify existing SmartAdmin theme source files.
- No edits inside `staticfile/themes/smartadmin/*`
- No edits inside upstream theme SCSS/CSS as part of the mobile rollout

2. Add new files instead of rewriting existing shared theme assets.
- Mobile CSS, JS, templates, and Vue render helpers should be added as new files
- Existing desktop assets should remain the source of truth for desktop behavior

3. Mobile mode must be toggleable.
- A user must be able to choose:
  - desktop-style view on mobile
  - new mobile-friendly view
- Mobile mode must not be forced purely by viewport width
- Viewport detection can be used as a default suggestion, not as the only control

4. Existing business logic must remain shared.
- Same routes
- Same permissions
- Same backend payloads
- Same save/list logic
- Only presentation and interaction density should change

5. The implementation must be detachable.
- Removing or disabling mobile mode should not require rollback of core desktop UI code
- Desktop appearance should remain unchanged when mobile mode is off

## Core Design Decision

The mobile UI should be implemented as an additive presentation layer, not as a rewrite of the existing application shell.

That means:

- desktop mode remains the current default implementation
- mobile mode is introduced through new wrappers, new CSS, and optional alternate renderers
- the mobile system should be able to sit beside the existing UI without creating risk for desktop users

## Toggle Model

The rollout should support two display modes on phones/tablets:

1. `desktop`
- preserves the current desktop-like interface
- useful for users who prefer the full ERP layout even on mobile

2. `mobile`
- uses the new app-style layout
- prioritizes large touch targets, stacked cards, sticky actions, and simplified navigation

Recommended behavior:

- if no user preference is saved yet:
  - detect a small viewport
  - suggest mobile mode by default
- once the user explicitly chooses a mode:
  - persist that choice
  - always honor the saved preference

Recommended storage options:

- first phase:
  - `localStorage`
- later, if needed across devices:
  - user profile or settings table

## Isolation Strategy

To keep the implementation low-risk, mobile assets should live in separate files and namespaces.

Recommended structure:

```text
staticfile/mobile/
  ui_view_mode.js
  mobile_tokens.css
  mobile_app_shell.css
  mobile_utilities.css

staticfile/component/dashboard/
  dashboard_mobile_shell.js
  dashboard_mobile_widget_feed.js

staticfile/component/inventory/
  product_list_mobile_component.js
  product_list_mobile_card.js
```

Recommended scoping approach:

- apply a root class when mobile mode is active, for example:
  - `app-mobile-mode`
- all mobile CSS should be scoped under that root class
- do not rely on broad global overrides

Example pattern:

```css
.app-mobile-mode .dashboard-shell {
  padding: 1rem;
}
```

This avoids accidental desktop regressions.

## What Must Not Change

The following should remain intact during the first phase:

- SmartAdmin core theme files
- current desktop template structure for non-mobile mode
- existing backend endpoints
- existing widget payload contracts
- existing product list data/query contracts

## Phase 1 Targets

### Dashboard

Treat the dashboard as a mobile home screen, not a compressed desktop grid.

Mobile dashboard goals:

- vertical feed instead of dense desktop widget grid
- stronger top-level summary cards
- fewer rows per list widget
- sticky app-style top bar
- simplified quick actions
- thumb-friendly spacing and touch targets

Desktop dashboard behavior remains untouched when mobile mode is off.

### Product List

Treat the product list as a mobile inventory browser, not a shrunken data table.

Mobile product list goals:

- card-based product rows
- sticky top toolbar
- search optimized for narrow screens
- filter bottom sheet or drawer
- simplified per-row actions
- no dependence on tiny table controls

Desktop product grid/list behavior remains untouched when mobile mode is off.

## Recommended Rollout Plan

### Step 1: Shared mobile mode infrastructure

Add:

- a mobile mode controller JS file
- a scoped mobile app-shell stylesheet
- a root body/class toggle mechanism

This layer should:

- detect viewport size
- read/write user preference
- activate either:
  - desktop mode
  - mobile mode

### Step 2: Dashboard mobile shell

Add a mobile-specific dashboard renderer that reuses existing widget data but changes layout only.

Prefer:

- stacked cards
- compact chart areas
- “view more” patterns for lists
- reduced visual noise compared with desktop panels

### Step 3: Product list mobile renderer

Add a mobile-specific product list renderer using the existing data source.

Prefer:

- product cards
- larger image/title hierarchy
- tap-friendly status badges
- primary action plus overflow menu

### Step 4: Toggle UX

Expose a user-facing switch such as:

- `Desktop View`
- `Mobile View`

Recommended placement:

- dashboard/settings/profile area first
- optionally page-level quick toggle later

### Step 5: Persist preference

Persist the chosen mode so users are not forced to reselect it every visit.

### Step 6: Expand only after pattern is stable

After Dashboard and Product List are stable, extend the same pattern to:

- voucher lists
- add/update forms
- reports

## Current Reference Standard

The current reference implementation for mobile UI work is now:

- Product List mobile view
- Product Add/Update mobile view

These two screens are the standard to copy when updating other forms and lists.

### Why this is the standard

This pair now demonstrates the approved detached rollout pattern end to end:

- shared global desktop/mobile mode controller
- automatic default mode by viewport size
- explicit user override preserved when the user chooses a mode
- no SmartAdmin theme source changes
- desktop behavior kept intact outside mobile-scoped styling
- mobile-only header cleanup
- mobile-only action styling
- focused mobile screen behavior instead of squeezing desktop panel chrome onto phones

### Standard mobile screen rules

When adapting other forms, use the Product Add/Update and Product List implementation as the baseline.

1. Keep desktop markup behavior intact.
- avoid changing desktop header/toolbars unless absolutely necessary
- prefer mobile-scoped classes and CSS over shared structural rewrites

2. Hide inherited desktop panel chrome in mobile mode when it adds clutter.
- panel toolbar buttons
- decorative panel icons when they do not help mobile scanning
- nonessential desktop settings controls

3. Use app-style mobile headers.
- soft elevated header background
- full-width title row
- clean spacing
- minimal competing controls

4. Use clearly prioritized mobile actions.
- modern rounded-rectangle buttons, not small desktop outline buttons
- primary actions should look primary
- secondary navigation actions should remain visibly secondary

5. Use sticky mobile action areas for forms.
- save actions must be easy to reach with the thumb
- buttons should stack or reflow cleanly on narrow widths

6. Keep mobile list and mobile form appearance in sync.
- similar header treatment
- similar button language
- similar spacing, radius, and shadow system

7. Prefer CSS-only mobile adaptation where possible.
- do not rewrite backend save/list logic just to change presentation
- add Vue mode-awareness only when the page needs to branch rendering or hide/show mobile-only elements

8. Use the shared app Vue import target for mobile rollout screens.
- import Vue from a single app-level module entry such as:
  - `staticfile/libraries/vue.app.js`
- do not point new rollout screens directly at CDN Vue URLs
- do not scatter direct runtime imports across files if a shared app alias exists

### Vue runtime note

The repo currently has a centralized app Vue entrypoint:

- `staticfile/libraries/vue.app.js`

This is intended to become the single swap point between development and production Vue ESM builds.

Current state:

- `vue.app.js` currently re-exports the local development Vue ESM file
- a real checked-in production Vue ESM artifact is still pending

Implementation rule:

- new mobile rollout screens should import Vue from `vue.app.js`
- when the production Vue file is added, the switch should happen in that one app entry file instead of updating many screens individually

### Standard rollout order for future forms

For the next forms, the preferred sequence is:

1. mobile header cleanup
2. mobile action-bar adaptation
3. mobile section/tab treatment
4. mobile list/line-card treatment where needed
5. final consistency pass against Product List and Product Add/Update

## Exact Implementation Blueprint

This section converts the strategy into a practical starting checklist.

### Phase 1 Goal

Deliver a safe foundation that:

- introduces mobile mode as an additive layer
- lets the user switch between desktop and mobile presentation on phones/tablets
- does not alter current desktop rendering when mobile mode is off

### New Files To Add First

Add these new files before changing page-specific rendering:

1. Shared mobile mode controller
- `staticfile/mobile/ui_view_mode.js`

Responsibilities:

- detect small viewport
- read saved preference from `localStorage`
- resolve effective mode:
  - `desktop`
  - `mobile`
- add root classes to `body`, for example:
  - `app-mobile-capable`
  - `app-mobile-mode`
  - `app-mobile-desktop-mode`
- expose a small global API for:
  - get current mode
  - set mode
  - subscribe to mode changes

2. Shared mobile tokens
- `staticfile/mobile/mobile_tokens.css`

Responsibilities:

- spacing scale
- touch target sizes
- app bar heights
- safe-area padding variables
- mobile card radius/shadow tokens

3. Shared mobile shell styles
- `staticfile/mobile/mobile_app_shell.css`

Responsibilities:

- app-style top bar helpers
- sticky bottom action bar helpers
- full-height mobile content wrappers
- card/feed/list primitives
- mobile-only utility classes

4. Shared mobile toggle styles
- `staticfile/mobile/mobile_toggle.css`

Responsibilities:

- style the desktop/mobile switch UI
- keep it visually isolated from theme styles

### Existing Files To Touch Minimally First

These should be the first existing files touched, and only lightly:

1. Shared authenticated header
- `dashboard/templates/header.html`

Why:

- this is the cleanest place to expose a user-facing mode switch
- it already contains app-level controls and user actions

Minimal change:

- add a small toggle entry for:
  - `Desktop View`
  - `Mobile View`

2. Shared authenticated base shell
- `basetemplate/base.html`

Why:

- this is the right place to load the new global mobile JS/CSS once

Minimal change:

- include:
  - `staticfile/mobile/mobile_tokens.css`
  - `staticfile/mobile/mobile_app_shell.css`
  - `staticfile/mobile/mobile_toggle.css`
  - `staticfile/mobile/ui_view_mode.js`

Important:

- this load is safe only if all CSS is scoped and dormant unless mobile mode is active

### Files For Dashboard Phase

Existing files:

- `dashboard/templates/dashboard/landing_page.html`
- `staticfile/dashboard/dashboard_main.js`
- `staticfile/component/dashboard/dashboard_kpi_widget.js`
- `staticfile/component/dashboard/dashboard_list_widget.js`
- `staticfile/component/dashboard/dashboard_chart_widget.js`
- `staticfile/component/dashboard/dashboard_empty_widget.js`

New files to add:

- `staticfile/dashboard/css/dashboard_mobile.css`
- `staticfile/component/dashboard/dashboard_mobile_shell.js`
- `staticfile/component/dashboard/dashboard_mobile_widget_feed.js`
- `staticfile/component/dashboard/dashboard_mobile_widget_card.js`

Dashboard implementation rule:

- keep widget payload loading exactly as it is
- branch only the renderer/layout layer

Recommended dashboard approach:

1. Leave `dashboard_main.js` as the widget data orchestrator.
2. Add a mode-aware render branch:
   - desktop mode:
     - current grid
   - mobile mode:
     - stacked feed
3. Move dashboard inline mobile-targeted CSS out of the template into:
   - `staticfile/dashboard/css/dashboard_mobile.css`
4. Keep desktop styling untouched except for optional extraction/cleanup later.

### Files For Product List Phase

Existing files:

- `inventory/templates/inventory/product_list_vue_template.html`
- `staticfile/inventory/product_list_template.js`
- `staticfile/component/inventory/product_list_component.js`

New files to add:

- `staticfile/inventory/css/product_list_mobile.css`
- `staticfile/component/inventory/product_list_mobile_component.js`
- `staticfile/component/inventory/product_list_mobile_card.js`
- `staticfile/component/inventory/product_list_mobile_filter_sheet.js`

Product-list implementation rule:

- do not replace the current DataTable component
- add a separate mobile renderer beside it

Recommended product-list approach:

1. Keep `product_list_component.js` as the desktop/table implementation.
2. Add `product_list_mobile_component.js` as a card-based mobile renderer.
3. In the page/template or parent bootstrap:
   - desktop mode:
     - mount/use existing `product-list`
   - mobile mode:
     - mount/use new mobile product-list component
4. Reuse the same backend list endpoint if feasible.
5. If the mobile component needs a simpler payload later, add a dedicated lightweight endpoint only after validating performance pain.

## First Concrete Work Sequence

This is the recommended order of execution.

### Sequence A: shared mode infrastructure

1. Add:
- `staticfile/mobile/ui_view_mode.js`
- `staticfile/mobile/mobile_tokens.css`
- `staticfile/mobile/mobile_app_shell.css`
- `staticfile/mobile/mobile_toggle.css`

2. Load them from:
- `basetemplate/base.html`

3. Add the mode switch UI to:
- `dashboard/templates/header.html`

4. Persist choice in:
- `localStorage`

Suggested key:

- `cellusense.ui.view_mode`

Suggested values:

- `desktop`
- `mobile`
- optional later: `auto`

### Sequence B: dashboard mobile proof

5. Add dashboard mobile CSS and renderer files.
6. Make `landing_page.html` mode-aware without deleting the current grid markup.
7. Reuse the existing widget API responses unchanged.
8. Validate:
- desktop mode unchanged
- mobile mode shows vertical feed

### Sequence C: product-list mobile proof

9. Add product-list mobile CSS and card renderer files.
10. Keep the current DataTable component intact.
11. Switch between:
- desktop DataTable
- mobile card list
12. Validate:
- desktop page unchanged
- mobile page becomes card-first and touch-friendly

## What The Very First Commit Should Contain

To reduce risk, the first implementation commit should include only the shared mode foundation:

- new mobile JS/CSS files
- base-template inclusion
- header toggle UI
- no dashboard/product renderer changes yet

Why:

- this lets you verify the toggle system safely
- it confirms that dormant mobile assets do not alter desktop appearance
- it creates the contract that page-level mobile renderers will use later

## Suggested Phase Boundaries

### Phase 1

- shared mobile mode infrastructure
- user toggle
- no visual page rewrite yet

### Phase 2

- dashboard mobile renderer
- dashboard mobile CSS

### Phase 3

- product list mobile renderer
- product list mobile CSS

### Phase 4

- mobile navigation refinement
- bottom action patterns
- filter sheets/drawers

### Phase 5

- rollout to other modules after the pattern is proven
- use Product List and Product Add/Update as the mandatory visual/interaction reference

## Guardrails During Implementation

1. Every existing-file change should be narrow and reversible.
2. Every new CSS rule should be scoped under mobile-mode root classes.
3. Do not change backend behavior unless a mobile renderer truly cannot reuse the existing payload.
4. Do not refactor SmartAdmin theme code as part of the rollout.
5. Do not mix dashboard/product mobile logic into generic desktop components unless necessary.

## Technical Rules for Clean Implementation

1. Additive files only for mobile-specific UI.
- new JS
- new CSS
- optional new partial templates

2. Prefer composition over mutation.
- wrap existing content
- swap renderers at the page level
- avoid deep edits to mature shared components unless necessary

3. Keep backend contracts unchanged whenever possible.
- mobile work should be mostly frontend composition and presentation

4. Use page-level opt-in first.
- start with Dashboard and Product List only
- do not globally enable mobile mode for every screen in phase 1

5. Avoid global CSS overrides without mobile root scoping.
- no broad selectors that can leak into desktop mode

## Acceptance Criteria

### Shared

- desktop appearance is unchanged when mobile mode is off
- mobile mode can be switched off by the user
- mobile assets can be removed without destabilizing desktop mode

### Dashboard

- no horizontal scrolling on common phone widths
- widgets read clearly without zooming
- primary actions are touch-friendly
- dense desktop widget layout is not forced onto small screens

### Product List

- products are readable as cards on small screens
- filters/search are usable one-handed
- actions are reachable without tiny icon targets
- current desktop product list remains intact when mobile mode is off

### Product Add/Update

- desktop form remains intact when mobile mode is off
- inherited panel chrome is reduced in mobile mode
- header actions look modern and touch-friendly
- save actions are sticky, easy to reach, and clearly prioritized
- mobile form appearance matches the product-list mobile language

## Current Source References

Dashboard:

- `dashboard/templates/dashboard/landing_page.html`
- `staticfile/dashboard/dashboard_main.js`
- `staticfile/component/dashboard/*`
- `widgetcenter/views.py`

Product List:

- `inventory/templates/inventory/product_list_vue_template.html`
- `inventory/function_views/product_rev1.py`
- `staticfile/component/inventory/product_list_component.js`
- `staticfile/component/inventory/product_list_mobile_component.js`
- `staticfile/inventory/css/product_list_mobile.css`

Product Add/Update:

- `inventory/templates/inventory/product_add_update_vue.html`
- `staticfile/inventory/add_update_product_vue.js`
- `staticfile/inventory/css/product_add_update_mobile.css`

## Summary

This mobile initiative should be built as a detachable, toggleable presentation layer.

The main principles are:

- no SmartAdmin theme modification
- add new files instead of rewriting shared ones
- preserve existing desktop behavior
- let the user choose desktop or mobile view on mobile devices
- default automatically by viewport size unless the user explicitly overrides
- use Product List and Product Add/Update as the standard for future mobile form work
