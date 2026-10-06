# ChatLens Frontend

The ChatLens frontend is a Vue 3 application built with Vite. Django serves the generated manifest and hashed assets from `static/frontend/` in production.

## Setup

```powershell
cd frontend
npm install
```

## Commands

```powershell
# Development server
npm run dev

# Unit tests
npm run test:unit -- --run

# Type-check and production build
npm run build
```

The production build writes directly to `../static/frontend` as configured in `vite.config.js`. Deploy the generated manifest and assets together so Django does not reference a missing hash.

## UI Architecture

Application primitives live in `src/components/ui`. Views should compose these controls rather than create feature-specific buttons, inputs, selects, date pickers, modals, panels, or grids.

Feature components live below `src/features/<feature>/components`. ClientPulse uses this boundary for its client and reminder editor dialogs.

The shared control system uses:

- Choices.js for enhanced and searchable selects,
- Flatpickr for date and datetime selection,
- CSS variables in `src/assets/ui-system.css` and `src/assets/ui-controls.css` for theme-specific presentation,
- `UiDataTable` for new grids and `v-ui-data-table` as the migration bridge for existing tables.

See `../docs/Frontend UI Component System.md` for component rules, modal sizing, migration constraints, and the required verification matrix.

## ClientPulse Reference

The ClientPulse directory, reminders, profile, and manual WhatsApp follow-up composer are the reference implementation for shared controls. Client and reminder editors intentionally use the `full` and `tall` modal configuration so all fields remain visible while the body scrolls independently.

WhatsApp-contact search is remote and permission-scoped. Do not load all contacts into the browser or bypass the backend visibility policy.
