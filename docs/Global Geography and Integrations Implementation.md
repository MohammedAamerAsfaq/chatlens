# Global Geography and Integrations Implementation

> **Status:** Phase 3 Google Maps manual verification implemented on 2026-10-18
> **Scope:** Provider-neutral Integrations control plane and Country -> Emirate -> City -> Locality/Community -> Project/Building hierarchy, with UAE-first GeoNames synchronization

## 1. Decisions

- `apps.integrations` owns external provider connections, adapters, synchronization runs, and external reference-data imports.
- Canonical geography is platform data shared by every company. Only a Control Account administrator can configure or synchronize it, regardless of which permitted workspace is currently selected.
- Google Maps geography verification is platform-managed because it enriches shared canonical geography. Future company-specific Maps use cases and Google Contacts remain company-owned.
- Google Maps credentials are entered through the Integrations control plane, stored using the same write-only database pattern as AI Provider keys, and never returned raw by an API.
- The Google Maps key is not read from IIS or an environment variable. Leaving the key field blank during a later edit preserves the stored value.
- Geography supplements raw property addresses. It does not replace or discard the original address, normalized location text, or coordinates.
- GeoNames is the canonical country, first-level administrative area, city-anchor, and locality source. Google Maps will be an enrichment and validation provider, not the canonical geography database.
- GeoNames populated places are not all cities. Administrative seats (`PPLC`, `PPLA`, `PPLA2`, `PPLA3`, and `PPLA4`) become city anchors; other populated places become localities.
- A locality is linked to a city only when source data provides an explicit parent that matches a city anchor. Unresolved rows are marked `unmapped`; distance-based guessing is prohibited.
- Synchronization runs through the existing durable `integrations` queue and is visible in Task Operations.

## 2. Implemented Schema

### `IntegrationConnection`

Stores a provider-neutral connection with either platform or company scope. The database enforces that platform connections have no company and company connections have a company. It also enforces one connection per provider within each scope.

### `Country`

Stores ISO codes, canonical and normalized names, GeoNames identity, center coordinates, aliases, source payload, active state, and source timestamps.

### `AdministrativeArea`

Stores country-owned administrative divisions with hierarchy support. Phase 1 imports level-one divisions such as UAE emirates.

### `City`

Stores city anchors, administrative-area membership, population, timezone, aliases, source payload, and active state. Records without valid coordinates are skipped.

### `Locality`

Stores communities, districts, neighborhoods, and other non-city populated places. Each row retains its GeoNames source identity and can be `mapped`, `unmapped`, or `review`. A nullable city link prevents uncertain source data from becoming a false hierarchy.

### `PropertyDevelopment`

Stores company-owned projects and buildings. A building may have a parent project, and both may reference a shared locality. Company ownership is enforced from the first migration; one company's developments cannot be used by another company.

### `PropertyAddress` canonical links

Property addresses now have optional protected links to country, administrative area, city, locality, and project/building masters. Existing raw country, region, city, community, project/building, normalized-location, and coordinate values remain unchanged and continue to preserve source input.

### `IntegrationSyncRun`

Records the requesting user and control workspace, durable task identity, country, status, result counters, errors, and timings.

### `GeographyExternalReference`

Stores only an approved Google place ID, the locality, the selected canonical city, verification state, operator, and timestamps. Google result labels, formatted addresses, coordinates, and raw payloads are not persisted.

### `IntegrationUsagePeriod`

Atomically counts Google API requests by calendar month and operation. ChatLens refuses requests after the configured monthly cap is reached.

## 3. Implemented Flow

```text
Control admin saves GeoNames username
  -> connection test checks UAE through GeoNames
  -> admin starts UAE synchronization
  -> integrations.sync_geography is durably queued
  -> worker retrieves country, ADM1 areas, and populated places
  -> administrative seats are upserted as city anchors
  -> remaining populated places are upserted as localities
  -> explicit locality-to-city parents are linked; unresolved rows are flagged
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
- active country, administrative-area, city, locality, and unmapped-locality counts,
- a paginated and searchable geography browser,
- recent synchronization status and counters.
- Google Maps Places API-key configuration with masked feedback,
- connection testing with visible monthly usage,
- manual locality search and operator-approved locality-to-city resolution.

The Real Estate Properties screen provides company-scoped **Projects / buildings** maintenance and canonical hierarchy selectors in the property editor. The editor shows only localities explicitly mapped to the selected city and keeps source address fields visible separately.

API routes:

```text
GET  /api/integrations/overview/
PUT  /api/integrations/geography-source/
POST /api/integrations/geography-source/test/
POST /api/integrations/geography-source/sync/
GET  /api/integrations/locations/
POST /api/integrations/google-maps/       # PUT remains accepted for compatibility
POST /api/integrations/google-maps/test/
POST /api/integrations/google-maps/localities/<id>/suggestions/
POST /api/integrations/google-maps/localities/<id>/resolve/
```

## 5. Deployment

1. Apply Django migrations.
2. Restart IIS/application processes after deployment.
3. Restart the background worker that includes the `integrations` queue for GeoNames synchronization.
4. As a Control Account administrator, open **Settings > Integrations** from any permitted workspace.
5. Enter a restricted Google key under **Google Maps APIs configuration**, enable it, save, and test it.
6. Set a conservative Google monthly cap. Google calls occur only from Test or Resolve actions, never during property/inquiry reads.
7. Browse Localities, choose Resolve, review Google suggestions, and explicitly select the canonical ChatLens city.

No new Python or Node dependency is required for Google Maps; the existing HTTP client is used.

## 6. Next Phases

1. Add UAE-authoritative locality/community enrichment and an explicit conflict-review workflow for unmapped rows.
2. Add provider billing telemetry and alerts before expanding Google Maps beyond manual verification.
3. Add authoritative project/building enrichment and alias review before these records participate in automatic matching.
4. Backfill canonical property-address links through reviewable suggestions; never overwrite raw source values.
5. Expand property attributes and matching rules.
6. Implement Listing Board grid/card views on the trusted property and listing models.
7. Implement Google Contacts separately under the existing ClientPulse Integrations design.

## 7. Non-Goals

- No Google secret is returned by an API or rendered back into the UI after saving.
- No automatic property-address rewrite occurs.
- No location is inferred from free text.
- No locality is assigned to a city by nearest-coordinate guessing.
- No company can alter the shared global geography source.
- No live external call occurs inside a property or inquiry request. Google calls require an explicit operator action.
