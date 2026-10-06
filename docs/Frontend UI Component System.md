# Frontend UI Component System

> **Status:** Active implementation standard
> **Updated:** 2026-10-06

## 1. Purpose

ChatLens supports its original visual theme and an Inspinia-derived theme. Application views must not copy controls from the reference theme or maintain separate markup for each theme. They use a shared Vue component layer whose colors, typography, spacing, borders, and shadows are supplied by CSS variables.

The ignored `static/inspinia_html` and `static/inspinia_vue` directories are design references only. Production code and assets must not import files from those directories.

## 2. Component Boundaries

Reusable primitives live under `frontend/src/components/ui/`:

- `UiButton`, `UiInput`, `UiSelect`, `UiDatePicker`, and `UiCheckbox` for controls,
- `UiModal` and `UiConfirmModal` for dialogs,
- `UiCard`, `UiPage`, `UiPageHeader`, `UiToolbar`, and `UiTabs` for layout,
- `UiBadge`, `UiMetric`, `UiNotice`, and `UiEmptyState` for feedback,
- `UiFileUpload` for file selection,
- `UiDataTable`, `UiTableFrame`, and `UiPagination` for grids.

Feature-specific orchestration belongs under the feature directory. ClientPulse editor components live under `frontend/src/features/clientpulse/components/`; they may compose shared controls but must not duplicate their base styling or behavior.

## 3. Control Decisions

### Selects

`UiSelect` wraps Choices.js. It supports object options, preservation of numeric values, disabled state, optional client-side search, a `search` event for remote search, and refresh when asynchronous option data changes.

Remote selectors must debounce requests and ignore stale responses. The ClientPulse WhatsApp-contact selector is the reference implementation.

### Date and time

`UiDatePicker` wraps Flatpickr and is the standard date/datetime control. Values exchanged with APIs must still be normalized explicitly by the view.

### Modals

`UiModal` owns presentation, Escape handling, backdrop close behavior, body scroll locking, and responsive width. Use `small` only for short confirmations, `large` for ordinary editors, and `full` with `tall` for multi-section forms such as ClientPulse client and reminder editors.

Modal form fields belong in the scrollable body; primary and cancel actions belong in the footer.

### Tables

New grids should use `UiDataTable`. Existing semantic tables may use `v-ui-data-table` while being migrated. The bridge adds column visibility and CSV export, stores hidden columns per grid key, assigns a minimum width from the column count, and preserves horizontal scrolling rather than compressing cells into unreadable columns.

## 4. Theme Rules

- Use `--ui-*` variables; do not hard-code an Inspinia skin color in a feature view.
- Use the shared font variables rather than feature-owned font declarations.
- Keep component CSS scoped when it describes feature layout.
- Put cross-application primitive styling in `ui-system.css` or `ui-controls.css`.
- Do not reintroduce legacy `cp-input`, `cp-select`, `cp-button`, or equivalent feature-owned control classes on migrated pages.
- Both themes must retain usable focus states, disabled states, overflow, and mobile layout.

## 5. ClientPulse Reference Screens

The following screens are the reference implementation for the shared controls:

- Customer directory: shared filters, grid, pagination, and full-height client editor.
- Reminders: shared filters, buttons, metrics, grid, date picker, and full-height reminder editor.
- Client profile: shared page header, cards, profile fields, identities, tags, notes, consent, timeline, and manual WhatsApp follow-up composer.

The profile follow-up composer preserves all outbound controls: account settings, direct/image sending switches, preflight, existing/new-chat policy, consent mode, do-not-contact state, character limits, attachment validation, idempotency, and durable outbound queueing.

## 6. Verification

Before committing component or migrated-view changes, run:

```powershell
cd frontend
npm.cmd run test:unit -- --run
npm.cmd run build
```

Also run `git diff --check` from the repository root. Visual verification must cover both themes, desktop and narrow layouts, modal scrolling, searchable dropdown overlays, table horizontal scrolling, disabled controls, and empty/loading/error states.
