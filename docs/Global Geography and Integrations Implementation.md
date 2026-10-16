# Global Geography and Integrations Implementation

> **Status:** Phase 1 implemented on 2026-10-16
> **Scope:** Provider-neutral Integrations control plane and global country/state/city master, with UAE-first GeoNames synchronization

## 1. Decisions

- `apps.integrations` owns external provider connections, adapters, synchronization runs, and external reference-data imports.
- Canonical geography is platform data shared by every company. Only a Control Account administrator can configure or synchronize it, regardless of which permitted workspace is currently selected.
- Company-specific connectors, including future Google Maps and Google Contacts connections, remain company-owned.
- Provider credentials must not be stored as plain text. `IntegrationConnection.secret_reference` stores only a reference to an external secret facility.
- Geography supplements raw property addresses. It does not replace or discard the original address, normalized location text, or coordinates.
- GeoNames is the canonical country, first-level administrative area, and city source. Google Maps will be an enrichment and validation provider, not the canonical geography database.
- Synchronization runs through the existing durable `integrations` queue and is visible in Task Operations.

## 2. Implemented Schema

### `IntegrationConnection`

Stores a provider-neutral connection with either platform or company scope. The database enforces that platform connections have no company and company connections have a company. It also enforces one connection per provider within each scope.

### `Country`

Stores ISO codes, canonical and normalized names, GeoNames identity, center coordinates, aliases, source payload, active state, and source timestamps.

### `AdministrativeArea`

Stores country-owned administrative divisions with hierarchy support. Phase 1 imports level-one divisions such as UAE emirates.

### `City`

Stores geocoded populated places, administrative-area membership, population, timezone, aliases, source payload, and active state. Records without valid coordinates are skipped.

### `IntegrationSyncRun`

Records the requesting user and control workspace, durable task identity, country, status, result counters, errors, and timings.

## 3. Implemented Flow

```text
Control admin saves GeoNames username
  -> connection test checks UAE through GeoNames
  -> admin starts UAE synchronization
  -> integrations.sync_geography is durably queued
  -> worker retrieves country, ADM1 areas, and populated places
  -> records are normalized and upserted transactionally
  -> source records absent from the new response are deactivated
  -> sync run and connection health are updated
```

GeoNames requires a registered username on each API request. The implementation uses the documented secure REST endpoint and JSON country/search services: [GeoNames web-service documentation](https://www.geonames.org/export/web-services.html).

## 4. Implemented UI and API

The Settings menu now exposes **Integrations** to users with `integrations.connections.view`.

The screen provides:

- control-admin-only GeoNames configuration,
- connection testing,
- durable UAE geography synchronization,
- active country, administrative-area, and city counts,
- a paginated and searchable geography browser,
- recent synchronization status and counters.

API routes:

```text
GET  /api/integrations/overview/
PUT  /api/integrations/geography-source/
POST /api/integrations/geography-source/test/
POST /api/integrations/geography-source/sync/
GET  /api/integrations/locations/
```

## 5. Deployment

1. Apply Django migrations.
2. Restart IIS/application processes.
3. Restart the background worker that includes the `integrations` queue.
4. As a Control Account administrator, open **Settings > Integrations** from any permitted workspace.
5. Save a registered GeoNames username and test the connection.
6. Start **Sync UAE geography** and inspect its run in the page or Task Operations.

No new Python or Node dependency is required for Phase 1.

## 6. Next Phases

1. Add UAE-authoritative locality/community enrichment with source provenance and conflict review.
2. Implement a secure credential backend, then Google Maps configuration and Places/geocoding enrichment under Integrations.
3. Link Real Estate property addresses to canonical country, administrative area, and city records while retaining raw values.
4. Add controlled locality and project masters plus aliases for reliable property matching.
5. Expand property attributes and matching rules.
6. Implement Listing Board grid/card views on the trusted property and listing models.
7. Implement Google Contacts separately under the existing ClientPulse Integrations design.

## 7. Non-Goals in Phase 1

- No Google secret is accepted or stored.
- No automatic property-address rewrite occurs.
- No location is inferred from free text.
- No company can alter the shared global geography source.
- No live external call occurs inside a property or inquiry request.
