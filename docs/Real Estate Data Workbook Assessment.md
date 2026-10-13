# Real Estate Data Workbook Assessment

**Status:** Analysis baseline; import deferred  
**Prepared:** 13 October 2026  
**Source directory:** `static/Real Estate Data/`  
**Files assessed:** 26 XLSX workbooks

## 1. Purpose

This document records the initial assessment of the real-estate Excel workbooks supplied for future ChatLens import work. It identifies the number of populated data rows in each workbook, the apparent business meaning of the data, and the normalization, privacy, and data-quality issues that must be addressed before production ingestion.

No workbook data was imported or modified during this assessment.

## 2. Counting Method

The counts in this document represent populated worksheet rows, with one header row removed from each non-empty headered sheet. Headerless worksheets count every populated row as a record.

These are physical row counts, not counts of unique people, properties, units, leads, owners, or transactions. Several exports repeat rows for:

- buyer and seller sides of one transaction;
- co-owners of one property;
- repeated transactions involving one unit;
- duplicate campaign submissions;
- the same owner across multiple properties or phases.

The primary datasets contain **205,293 data rows**. `AUG 2025.xlsx` also contains **38 project-summary rows**, reported separately and excluded from that total.

## 3. Dataset Summary

| Primary classification | Files | Data rows | General content |
|---|---:|---:|---|
| Campaign and CRM leads | 11 | 14,843 | Prospects, contact details, campaign source, property preference, budget, and purchase intent |
| Property owner and unit directories | 9 | 55,130 | Unit or villa references, phases, owners, contact details, areas, and communities |
| Property inventory and transaction registries | 6 | 135,320 | Projects, units, buyer/seller parties, transaction values, areas, property attributes, and ownership information |
| **Total** | **26** | **205,293** | Physical data rows before deduplication or validation |

The classifications describe the dominant content of each workbook. They are not strict boundaries because many registry exports also contain personal contact information.

## 4. Workbook Inventory

| Workbook | Data records | Apparent data type and content |
|---|---:|---|
| `Arabian Ranches New (1) (1).xlsx` | 31,472 | Property and ownership directory containing area, sub-location, building or unit reference, size, owner name, and mobile number |
| `Athlon by aldar with contact 2026.xlsx` | 423 | Villa owner/contact directory across two sheets: 294 and 129 records |
| `AUG 2025.xlsx` | 17,489 primary; 38 summary | Property purchase or booking records containing project, tower, unit, bedroom typology, applicant, saleable area, phone, and purchase price; separate project/unit summary sheet |
| `Avenue Residence 1 ,A. RESIDENCE 2 , A.R Three.xlsx` | 23,982 | Headerless property registry and unit inventory: 23,781 ownership/contact-style rows and 201 unit/property rows |
| `Baygrove leads.xlsx` | 230 | Headerless campaign lead list containing prospect name, project, and bedroom preference; some contact-position cells are blank |
| `Bayview Emaar beach.xlsx` | 11,796 | Transaction-party registry containing buyer/seller role, transaction value, area, project, building, unit, size, party name, mobile, procedure, and nationality |
| `Binghatti Leads-1.xlsx` | 9 | Campaign leads containing name, email, phone, work phone, budget, bedroom preference, and project; second sheet is empty |
| `Bugatti Residences Dubai 2026-1.xlsx` | 28 | Flat-number-to-owner directory with limited contact information |
| `Business Bay F2026.xlsx` | 13,393 | Property ownership directory containing area, community, size, unit number, plot number, owner, and mobile |
| `DAMAC Islands (2).xlsx` | 228 | Headerless campaign leads containing name, email, project, phone, and bedroom preference |
| `Damac Lagoons.xlsx` | 6,686 | Villa owner/contact directory containing phase, prefix, unit number, owner, mobile, email, and secondary mobile |
| `Dubai silicon oasis 2026.xlsx` | 1,149 | Detailed property and owner registry containing project/building, completion status, property type, use, beds, area, transaction amount, owner, and multiple phone fields |
| `Ellington Dubai hill.xlsx` | 70,836 | Two large datasets: 65,069 transaction-party rows and 5,767 property/owner rows covering projects, units, areas, transaction values, owner/contact data, and identity fields |
| `Flare By Binghatti Leads.xlsx` | 90 | Headerless campaign leads containing name, email, project, phone, and apartment preference |
| `Ghafwoods Distrikt New Phase .xlsx` | 51 | Headerless campaign leads containing name, email, project, phone, and bedroom preference |
| `Grand Polo-2 with contact 2026.xlsx` | 1,969 | Phase/property owner directory containing phase, property number, owner name, and phone |
| `La Tilia - Villanova.xlsx` | 270 | Villa owner/contact directory containing villa number, owner, phone, email, mobile, and secondary mobile |
| `Leads 2026 Fresh.xlsx` | 406 | Meta campaign leads across five populated sheets: Arada Masaar 7, Peacehome DLRC 172, Danube Apartment UK 156, Ora Bayn 54, and Passo Beyond 17; one additional sheet is empty |
| `Leads 2026 Updated-1.xlsx` | 7,287 | CRM contact export containing names, email, phone, source, campaign, property interests, location interests, budgets, purchase window, and other marketing fields |
| `Leads JVC-1.xlsx` | 6,219 | JVC campaign leads containing name, email, contact number, location, apartment type, lead source, and timestamp |
| `Oia residence Motor City.xlsx` | 10,068 | Two datasets: 8,301 transaction-party rows and 1,767 property/owner rows containing projects, units, values, areas, buyers/sellers, owners, and contact details |
| `rosehill by emaar leads .xlsx` | 252 | Headerless campaign leads containing name, email, project, phone, and bedroom preference |
| `South Bay - Dubai South.xlsx` | 373 | Unit owner/contact records across six phase sheets containing unit, owner, mobile, email, and secondary mobile |
| `The Valley - Venera.xlsx` | 516 | Phase and unit owner directory containing phase, unit number, owner name, and mobile |
| `The Valley ELWA.xlsx` | 34 | Headerless campaign leads for villas or semi-detached properties with prospect contact information |
| `The Valley Riviera Semi Detached .xlsx` | 37 | Headerless campaign leads for semi-detached properties with prospect contact information |

## 5. Data-Quality Findings

### 5.1 Missing or unreliable schemas

Several lead workbooks and both Avenue Residence worksheets do not provide a dependable header row. Their column meanings must be confirmed and captured in a source-specific mapping before import. Positional inference alone is not sufficient for a repeatable production importer.

### 5.2 Non-unique rows

Registry row counts cannot be treated as unique property or customer counts. Buyer/seller transaction exports generally create at least two rows for one transaction, while ownership exports can repeat a unit for multiple owners. Lead files can contain repeat submissions by the same person.

Deduplication is required independently at these levels:

- person/contact;
- property or unit;
- ownership relationship;
- transaction;
- campaign submission.

### 5.3 Phone-number integrity

Phone fields use inconsistent formats, including local UAE numbers, international numbers, delimiters, spaces, pipes, leading zeroes, and scientific notation such as `5.55385317E8` or `9.71525182089E11`.

Phone numbers must be imported as strings and normalized carefully. They must never be converted through floating-point arithmetic because that can change digits or remove leading zeroes.

### 5.4 Dates and encoded values

Several workbooks store dates as Excel serial values. This affects lead timestamps, update timestamps, birth dates, passport expiry dates, and related fields. Date conversion must use the workbook date system and must preserve the original raw value for audit purposes.

Some worksheets also contain:

- literal strings such as `null` rather than empty values;
- inconsistent country names and codes;
- inconsistent property and bedroom labels;
- incomplete or blank contact fields;
- mixed numeric and textual identifiers;
- apparent spelling variations in projects and locations.

### 5.5 Test data

`Leads 2026 Fresh.xlsx` contains at least four clearly labelled Meta dummy/test leads. Its 406-row count includes those records. Approximately 402 rows appear non-test based on the explicit dummy labels, but the file must still pass a full test-record filter before import.

### 5.6 Empty sheets

- `Binghatti Leads-1.xlsx`: `Sheet2` is empty.
- `Leads 2026 Fresh.xlsx`: `Sheet7` is empty.

Empty worksheets must be ignored without creating failed import batches.

## 6. Privacy and Access-Control Risk

The source files contain personally identifiable and, in some cases, highly sensitive data, including:

- names, phone numbers, and email addresses;
- passport and UAE identity numbers;
- birth dates and document expiry dates;
- nationality and country information;
- property ownership and transaction values;
- campaign interests and purchase budgets.

Before import, the business must confirm its lawful basis, retention rules, permitted users, company ownership, and communication consent. Raw files and staging records must not be exposed to users outside the owning company. Identity-document fields should not be copied into operational models unless there is a documented business requirement and appropriate field-level protection.

## 7. Required Import Architecture

Future ingestion should follow the established ChatLens architecture and should not import these workbooks directly into production domain tables.

Recommended sequence:

1. Register each workbook in a company-owned import batch with source filename, checksum, worksheet, row number, and import status.
2. Store an immutable raw staging representation before normalization.
3. Apply a versioned, source-specific column mapping.
4. Normalize phone numbers, emails, countries, dates, project names, locations, property types, bedroom values, area units, and null values.
5. Quarantine malformed or ambiguous rows instead of silently discarding them.
6. Deduplicate contacts, properties, ownership relationships, transactions, and campaign leads using separate rules.
7. Route campaign prospects into company-owned ClientPulse records only after consent and duplicate checks.
8. Route verified physical units into Real Estate property inventory.
9. Store ownership and historical transaction information separately from active sale or lease listings.
10. Create embeddings only after canonical structured records are available; source values must remain unchanged and auditable.
11. Produce an import reconciliation report containing accepted, merged, quarantined, rejected, and skipped counts.

## 8. Decisions Required Before Import

The following decisions remain intentionally deferred:

- which company owns each workbook and resulting records;
- whether each file is legally approved for marketing use or reference-only analysis;
- which owner and transaction fields must be retained;
- whether registry owners should become ClientPulse customers automatically;
- whether campaign leads without consent can be contacted;
- source-specific header mappings for headerless files;
- authoritative project, community, building, property-type, and area-unit masters;
- duplicate matching thresholds and manual-review workflow;
- retention and deletion policy for raw files and sensitive identity data;
- whether transaction data is historical reference data, comparable-market data, or eligible to create inventory/listings.

## 9. Acceptance Gate for Future Work

No production import should begin until:

- a company owner is assigned to every batch;
- source schemas and mappings are approved;
- privacy and communication-use permissions are confirmed;
- staging and reconciliation models are implemented;
- normalization and deduplication rules have automated tests;
- sample imports are reviewed against the original workbook rows;
- transaction history, property inventory, active listings, and ClientPulse contacts remain separate domain concepts.

## 10. Planned Use of the Data

The workbooks have two valid but different uses:

1. anonymized and controlled application testing;
2. carefully qualified production prospecting and market intelligence.

The data must not be bulk-imported directly as live opportunities or active listings. A source row proves only what is explicitly present in that source. In particular, property ownership or participation as a seller in a historical transaction does not prove a current intention to sell or lease.

### 10.1 Mapping to current ChatLens concepts

The Real Estate application already separates the relevant concepts:

- `Property` represents a verified physical property record;
- `Listing` represents verified current sale or lease availability;
- `RealEstateOpportunity` represents one of Buying, Selling, Leasing Inquiry, or Leasing Offer;
- `PropertyRequirement` stores the needs extracted for Buying and Leasing Inquiry opportunities;
- `PropertyCandidate` stores unverified supply extracted for Selling and Leasing Offer opportunities;
- ClientPulse stores the person or organization, contact lifecycle, ownership, reminders, consent, and communication history.

Workbook rows should be projected into these models only when their source meaning satisfies the model's purpose. Historical market records require a separate transaction model and must not be forced into `Listing`.

## 11. Initial Application Testing

Testing must use a dedicated real-estate test company, preferably a disposable copy of `Seville`. Raw workbook records must not be loaded into the Control Account or another production tenant.

### 11.1 Property and inventory testing

Representative samples can be drawn from:

- `Dubai silicon oasis 2026.xlsx`;
- `AUG 2025.xlsx`;
- `Oia residence Motor City.xlsx`;
- `Ellington Dubai hill.xlsx`;
- `Avenue Residence 1 ,A. RESIDENCE 2 , A.R Three.xlsx`.

These records can test:

- property creation and company isolation;
- property-type master resolution;
- project, building, community, and unit normalization;
- bedrooms, area, completion status, and developer mapping;
- square-metre, square-foot, and other area-unit conversions;
- normalized location and geographic fields;
- duplicate property and unit detection;
- property embeddings, semantic search, and requirement matching;
- data-table filtering, pagination, and export;
- queue throughput and large-volume processing.

Properties generated for test purposes should remain `draft` or `inactive`. Historical transaction values must not be presented as current asking prices.

### 11.2 Buying workflow testing

The strongest Buying test sources are the campaign and CRM exports:

- `Leads 2026 Updated-1.xlsx`;
- `Leads JVC-1.xlsx`;
- `Leads 2026 Fresh.xlsx`;
- the named Binghatti, Rosehill, Ghafwoods, DAMAC Islands, Baygrove, ELWA, and Riviera lead files.

A row with explicit property interest can test this projection:

```text
CompanyContact
  -> ClientPulse profile with lifecycle Lead
  -> RealEstateOpportunity with activity Buying
  -> PropertyRequirement
```

Location, project, property type, bedroom preference, budget, timeframe, and purpose can populate structured requirement fields when present.

### 11.3 Selling workflow testing

Owner directories provide realistic owner/property structures but do not prove selling intent. Selling workflow tests should use anonymized owner/property rows to create explicitly synthetic test messages, for example:

```text
TEST: I own villa NH05-53_03 in Athlon and want to sell it.
```

This can test:

```text
RealEstateOpportunity with activity Selling
  -> PropertyCandidate
  -> agent review
  -> verified Property
  -> verified sale Listing
```

The original ownership row must not automatically become a Selling opportunity or active listing.

### 11.4 Leasing workflow testing

No reliable explicit Leasing Inquiry or Leasing Offer dataset was identified in the supplied workbooks. Leasing tests must initially use synthetic, anonymized records covering:

- a tenant seeking a property;
- a landlord or authorized agent offering a property for rent;
- ambiguous lease direction requiring review;
- missing rent or payment frequency;
- yearly, monthly, weekly, and daily payment frequencies;
- availability dates, deposits, commissions, and expired offers.

### 11.5 Recommended test volumes

| Test stage | Recommended volume | Purpose |
|---|---:|---|
| Smoke | 100-250 anonymized rows | Validate mappings, CRUD, company scope, and basic queues |
| Functional | 2,000-5,000 mixed rows | Exercise normalization, duplicates, review, embeddings, and matching |
| Performance | All 205,293 rows in a disposable database | Measure import, queue, database, API, and grid behavior |
| AI accuracy | About 500 curated messages with expected outcomes | Measure all four activities, extraction accuracy, ambiguity, and `not_real_estate` handling |

The AI accuracy set should use structured workbook fields to establish expected values, but should not expose real personal data to an AI provider. Names, phones, emails, identity values, and exact unit-owner relationships must be anonymized.

## 12. Production Use for Possible Leads

### 12.1 Buying leads

The 14,843 campaign and CRM rows are the main possible source for Buying prospects. They are not automatically 14,843 valid live opportunities.

Before a row can become a production Buying opportunity, the importer must:

- remove dummy and test submissions;
- validate and normalize phone and email values;
- deduplicate by company, phone, email, source, and campaign submission;
- evaluate source date and recency;
- confirm lawful use and communication consent;
- require explicit current property-buying interest;
- quarantine incomplete or contradictory records.

An unambiguous campaign field such as an explicit selected property/project, bedroom preference, or buying purpose may create a classified Buying opportunity and a pending-review `PropertyRequirement`. Ambiguous records should remain ClientPulse leads without a Real Estate opportunity.

### 12.2 Selling prospects

The 55,130 owner/unit directory rows can identify potential property-owner prospects, but they must not be labelled as current sellers.

After lawful-use and identity checks, an owner may be represented as:

```text
ClientPulse profile
  tag: Property Owner
  source: Import
  linked ownership/reference record
```

A Selling opportunity should be created only after the owner or authorized agent explicitly confirms current selling intent. Historical transaction rows with party role `Seller` are evidence of a past transaction, not a current offer.

The current domain does not have a dedicated ownership relationship model. If owner data is retained, add an auditable company-owned property-party or ownership model instead of overloading `Listing.source_contact`.

### 12.3 Leasing inquiries

A Leasing Inquiry requires explicit evidence that a person is currently seeking a rental property. No inspected workbook provides a dependable leasing-inquiry source.

Investment purpose, property ownership, or prior purchase activity must not be interpreted as rental demand.

### 12.4 Leasing offers

A Leasing Offer requires explicit current evidence of:

- an available rental property;
- rent amount and currency;
- payment frequency;
- availability date;
- a landlord or authorized agent;
- authority or permission to market the unit.

An owner-directory row alone must not create a Leasing Offer or lease `Listing`.

### 12.5 Historical transactions and market intelligence

The 135,320 property and transaction rows are best suited to:

- comparable transaction analysis;
- project and area price trends;
- property valuation context;
- property and ownership reference checks;
- market reporting;
- enriching normalized projects, buildings, communities, and property types.

They should be stored separately from active listings. A future company-owned `PropertyTransaction` model and related transaction-party model should preserve transaction date, value, procedure, property reference, buyer/seller role, and source lineage.

## 13. Live-Data Eligibility Rules

| Source evidence | ClientPulse | Opportunity | Property | Active listing |
|---|---|---|---|---|
| Explicit recent buying campaign submission | Yes, after deduplication and consent checks | Buying | No, unless a separate property record is present | No |
| Property owner directory row | Possible owner prospect | No until intent is confirmed | Draft/reference property may be created after unit verification | No |
| Historical buyer/seller transaction row | Only when lawful use is confirmed | No | Reference/enrichment only | No |
| Explicit current sale offer | Yes | Selling | Candidate, then verified property | Sale listing only after review and verification |
| Explicit current rental requirement | Yes | Leasing Inquiry | No | No |
| Explicit current rental offer | Yes | Leasing Offer | Candidate, then verified property | Lease listing only after review and verification |
| Ambiguous, malformed, stale, or test row | No or quarantined | No | No | No |

## 14. Controlled Production Pilot

The first production pilot should be deliberately small:

1. Select 100-200 recent rows with explicit Buying interest from `Leads JVC-1.xlsx` or another approved campaign source.
2. Assign the import batch to the intended real-estate company.
3. Normalize and deduplicate the records in staging.
4. Import approved contacts as ClientPulse leads with source `import`.
5. Keep outbound campaigns and automatic WhatsApp contact disabled.
6. Create Buying opportunities only for rows with explicit, mappable intent.
7. Have an agent manually review contact validity, consent, requirement fields, and duplicate decisions.
8. Reconcile source, accepted, merged, quarantined, rejected, and skipped counts.
9. Measure contact validity and conversion before increasing batch size.

For broader system testing, use `Dubai silicon oasis 2026.xlsx` for property normalization and `South Bay - Dubai South.xlsx` for owner/property relationship and deduplication behavior.

## 15. Production Safety Rules

- Do not send automated messages immediately after import.
- Do not infer Selling or Leasing Offer intent from ownership.
- Do not infer Leasing Inquiry intent from investment interest.
- Do not treat historical prices as live asking prices.
- Do not activate a listing without current availability and human verification.
- Do not send raw identity fields to embedding or AI providers.
- Do not discard or overwrite source values during normalization.
- Do not expose one company's imported records to another company.
- Do not process the complete dataset until the controlled pilot reconciles successfully.
