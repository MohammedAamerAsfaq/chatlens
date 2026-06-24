# Fullstack Flow

## Purpose

Describe the end-to-end implementation pattern used across modules.

## Request Lifecycle

1. Django URL routes request to a function-based view.
2. View loads initial template or handles AJAX payload.
3. Repository/form layer validates and extracts data.
4. Model persistence runs in transaction boundaries.
5. Response returns HTML or JSON to Vue UI.

## Frontend Flow

1. Django template provides mount point and initial context.
2. Vue Options API app handles user interactions.
3. Reusable components (dropzone, select2, paginator, etc.) emit events.
4. Vue app transforms state to API payloads.
5. UI renders server responses and validation states.

## Backend Flow

1. Function views enforce permission and workflow checks.
2. Repository methods centralize extraction, defaults, and save logic.
3. Django forms provide structured validation.
4. Logging/audit hooks capture add/update/delete activity.
5. Workflows tie transactions to `work_id` where required.

## Related Docs

- [Backend Patterns](backend-patterns.md)
- [Frontend Patterns](frontend-patterns.md)
- [Contact Module Guide](../modules/contact.md)
