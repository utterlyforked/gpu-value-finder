# Cross-Spec Consistency Review

**Date**: 2025-01-12
**Specs reviewed**: foundation-spec, FEAT-01-live-retail-price-aggregation-spec, FEAT-02-used-market-price-discovery-spec, FEAT-03-value-visualization-dashboard-spec, FEAT-04-manufacturer-reference-links-spec, FEAT-05-radeon-vs-nvidia-mode-switching-spec
**Status**: BLOCKERS FOUND

---

## Summary

Found 12 blocker issues and 3 warning issues that must be resolved before implementation. Most critical conflicts involve entity naming mismatches between foundation and features, status enum value inconsistencies, and field name misalignments that would cause runtime failures.

---

## BLOCKER Issues

### [B1] GPU Entity Name Mismatch Between Foundation and Features

**Specs affected**: foundation-spec, FEAT-01, FEAT-02, FEAT-03, FEAT-04, FEAT-05

**The conflict**: 
- Foundation spec defines table name as `gpus` (lowercase plural) in "Seed Data Notes" section
- Foundation spec uses `GPU` as entity name in "Data Model" section (singular, uppercase)
- FEAT-03 references entity as `GpuPerformanceTier` and `GpuPriceSnapshot`
- FEAT-04 refers to "GPU entity" but extends it with fields not defined in foundation
- FEAT-05 refers to "`Gpu` entity" (Pascal case)

**Example**:
- Foundation: "Seed Data Notes: Seed data script populates 33 GPU models"
- FEAT-01: Does not reference the GPU entity at all, works with GPU model strings only
- FEAT-03: "This feature owns the `GpuPerformanceTier` and `GpuPriceSnapshot` entities"
- FEAT-04: "The GPU entity is defined in the Foundation Spec. This feature extends it..."
- FEAT-05: "This spec adds the `manufacturer` field to the existing `Gpu` entity"

**Fix**: 
1. Foundation spec must clarify: Entity class name is `GPU` (or `Gpu`), table name is `gpus`
2. All feature specs must reference it consistently as `GPU` entity, `gpus` table
3. Establish convention: C# class names use Pascal case (`Gpu`), table names use snake_case plural (`gpus`)

---

### [B2] RetailPrice vs RetailPriceAverage Entity Name Conflict

**Specs affected**: foundation-spec, FEAT-01

**The conflict**:
- Foundation spec defines entity `RetailPriceAverage` with fields `min_price`, `avg_price`, `max_price`
- FEAT-01 defines entity `RetailPrice` with fields `min_price`, `avg_price`, `max_price`
- These appear to be the same entity with different names

**Example**:
- Foundation: "### RetailPriceAverage | Field | Type | ... | min_price | decimal(10,2) |"
- FEAT-01: "### RetailPrice | Field | Type | ... | min_price | decimal(10,2) |"

**Fix**: Choose one canonical name and use it everywhere. Recommendation: Use `RetailPriceAverage` from foundation spec since it's more descriptive. Update FEAT-01 to match foundation naming.

---

### [B3] UsedPrice vs UsedPriceAverage Entity Name Conflict

**Specs affected**: foundation-spec, FEAT-02

**The conflict**:
- Foundation spec defines entity `UsedPriceAverage`
- FEAT-02 defines entity `UsedPriceAverage` (matches foundation)
- But FEAT-02 *also* defines `UsedListing` which foundation also defines
- Foundation and FEAT-02 both claim ownership of `UsedPriceAverage` and `UsedListing`

**Example**:
- Foundation: "This foundation owns the `GPU`, `RetailListing`, `RetailPriceAverage`, `UsedListing`, `UsedPriceAverage`, and `ScraperLog` entities"
- FEAT-02: "**Entities Owned**: `UsedListing`, `UsedPriceAverage`, `ScrapeJob`, `UnmatchedListing`, `OutlierLog`..."

**Fix**: Clarify ownership boundaries. Recommendation:
- Foundation owns: `GPU`, `RetailListing`, `RetailPriceAverage`, `UsedListing`, `UsedPriceAverage`, `ScraperLog`
- FEAT-02 owns: `ScrapeJob`, `UnmatchedListing`, `OutlierLog`, `InvalidPriceListing`, `NonGbpListing`
- Update FEAT-02 to reference (not redefine) `UsedListing` and `UsedPriceAverage`

---

### [B4] GPU Model ID Field Name Mismatch

**Specs affected**: foundation-spec, FEAT-01, FEAT-02, FEAT-03

**The conflict**:
- Foundation spec defines `GPU` entity with field `model_id` (snake_case)
- FEAT-03 defines `GpuPerformanceTier` with field `ModelId` (Pascal case)
- Foreign keys in foundation use `gpu_model_id` but foundation's PK is just `id`

**Example**:
- Foundation GPU entity: "| model_id | string(100) | unique, not null |"
- Foundation RetailListing: "| gpu_model_id | UUID | FK → GPU(id), not null |"
- FEAT-03 GpuPerformanceTier: "| ModelId | string(50) | PK, not null |"

**Fix**: 
1. Foundation `GPU.model_id` should be a unique alternate key (not PK)
2. Foundation `GPU.id` is the UUID primary key
3. Foreign keys should reference `GPU.id` (UUID), not `model_id` (string)
4. FEAT-03's `GpuPerformanceTier.ModelId` appears to be a duplicate of `GPU.model_id` — consolidate these entities or clarify relationship

---

### [B5] SpecUrlStatus Enum Value Casing Inconsistency

**Specs affected**: foundation-spec, FEAT-04

**The conflict**:
- Foundation spec CHECK constraint uses string values: `'Active', 'Unavailable', 'NeedsReview'` (Pascal case)
- FEAT-04 spec uses integer enum in table definition but string enum in API responses
- FEAT-04 API says `specUrlStatus: integer` with comment `0=Active, 1=Unavailable, 2=NeedsReview`
- But FEAT-04 database section says: `spec_url_status | string(20) | not null, default 'Active'`

**Example**:
- Foundation: `CHECK: spec_url_status IN ('Active', 'Unavailable', 'NeedsReview')`
- FEAT-04 API: `specUrlStatus: integer | 0=Active, 1=Unavailable, 2=NeedsReview`
- FEAT-04 Database: `spec_url_status | string(20) | not null, default 'Active'`

**Fix**: Standardize on string enum storage with Pascal case values. Update FEAT-04 to remove integer enum references in API responses and use strings consistently.

---

### [B6] ScraperLog Entity Duplication and Field Conflicts

**Specs affected**: foundation-spec, FEAT-01, FEAT-02

**The conflict**:
- Foundation defines `ScraperLog` with field `job_type` (enum: "Retail", "Used")
- FEAT-01 defines `ScraperLog` with field `job_id`, `started_at`, `completed_at`, `status`
- FEAT-02 defines `ScrapeJob` with similar fields but different name
- All three specs define overlapping scraper logging but with incompatible schemas

**Example**:
- Foundation ScraperLog: "| job_type | string(50) | not null, CHECK constraint | Enum: 'Retail', 'Used' |"
- FEAT-01 ScraperLog: "| job_id | UUID | not null | Unique identifier for this scrape run |"
- FEAT-02 ScrapeJob: "| source | string(50) | not null | Enum: 'eBay', 'CEX' |"

**Fix**: Choose one canonical scraper log entity:
- Option A: Use foundation's `ScraperLog`, extend it with fields from FEAT-01/02
- Option B: Rename foundation's to `ScraperLogUnified`, keep FEAT-01/02 separate
- Recommendation: Merge into single `ScraperLog` table with fields covering both retail and used scraping

---

### [B7] Manufacturer Field Type Inconsistency

**Specs affected**: foundation-spec, FEAT-05

**The conflict**:
- Foundation defines `GPU.manufacturer` as `string(20)` with CHECK constraint `IN ('radeon', 'nvidia')`
- FEAT-05 defines same field as `VARCHAR(50)` with CHECK constraint `IN ('radeon', 'nvidia')`
- Different max lengths (20 vs 50 characters)

**Example**:
- Foundation: "| manufacturer | string(20) | not null, CHECK constraint |"
- FEAT-05: "| manufacturer | VARCHAR(50) | NOT NULL, CHECK constraint |"

**Fix**: Use consistent max length. Recommendation: Use `VARCHAR(20)` everywhere since "radeon" and "nvidia" both fit comfortably.

---

### [B8] Performance Score Field Missing in FEAT-03's GpuPerformanceTier

**Specs affected**: foundation-spec, FEAT-03

**The conflict**:
- Foundation `GPU` entity has `performance_score` field (int, 1-100)
- FEAT-03 introduces new entity `GpuPerformanceTier` with `PerformanceScore` field
- These appear to be duplicate data — same GPU model has performance score in two tables

**Example**:
- Foundation GPU: "| performance_score | int | not null, CHECK (1-100) |"
- FEAT-03 GpuPerformanceTier: "| PerformanceScore | int | not null, check (1-100) |"

**Fix**: Eliminate duplication. Options:
1. Remove `performance_score` from foundation `GPU` entity, only store in `GpuPerformanceTier`
2. Remove `GpuPerformanceTier` entity entirely, store all data in foundation `GPU`
3. Clarify that `GpuPerformanceTier` is the canonical source and foundation GPU references it via FK

Recommendation: Option 3 — Foundation `GPU` entity should have FK to `GpuPerformanceTier`, not duplicate the performance score field.

---

### [B9] Price Field Currency Mismatch

**Specs affected**: FEAT-01, FEAT-02, FEAT-03

**The conflict**:
- FEAT-01 explicitly states prices are in GBP
- FEAT-02 explicitly states prices are in GBP
- FEAT-03 API response shows `"currency": "USD"` in example
- Foundation spec does not specify currency

**Example**:
- FEAT-01: "| price | decimal(10,2) | not null, check > 0 | Price in GBP |"
- FEAT-02: "| price | decimal(10,2) | not null | Asking price in GBP |"
- FEAT-03 API example: `"currency": "USD"`

**Fix**: Standardize on GBP everywhere (FEAT-01/02 already use GBP). Update FEAT-03 example to show `"currency": "GBP"`.

---

### [B10] OfficialSpecUrl Field Name Casing Mismatch

**Specs affected**: foundation-spec, FEAT-03, FEAT-04

**The conflict**:
- Foundation defines field as `official_spec_url` (snake_case)
- FEAT-03 API response uses `officialSpecUrl` (camelCase)
- FEAT-04 database migration uses `official_spec_url` (snake_case)
- FEAT-04 API uses `OfficialSpecUrl` (Pascal case in table) and `officialSpecUrl` (camelCase in API)

**Example**:
- Foundation: "| official_spec_url | string(500) | nullable |"
- FEAT-03 API: `"oemProductUrl": "https://www.amd.com/..."`
- FEAT-04 API: `"officialSpecUrl": string or null`

**Fix**: Database fields should use snake_case (`official_spec_url`), API responses should use camelCase (`officialSpecUrl`). Update FEAT-03 to use `officialSpecUrl` not `oemProductUrl`.

---

### [B11] Timestamp Field Name Inconsistencies

**Specs affected**: foundation-spec, FEAT-01, FEAT-02, FEAT-03

**The conflict**:
- Foundation uses `created_at`, `updated_at` (snake_case)
- FEAT-01 uses `scraped_at`, `created_at`, `updated_at` (snake_case)
- FEAT-02 uses `scraped_at`, `created_at` (snake_case)
- FEAT-03 uses `CreatedAt`, `UpdatedAt` (Pascal case in data model section)
- FEAT-03 API uses camelCase: `lastUpdated`, `calculatedAt`

**Example**:
- Foundation: "| created_at | timestamp | not null, default now() |"
- FEAT-03 GpuPerformanceTier: "| CreatedAt | datetime | not null |"

**Fix**: Database schema should use snake_case consistently (`created_at`, `updated_at`, `scraped_at`). Update FEAT-03 data model section to use snake_case field names.

---

### [B12] GpuPriceSnapshot Missing Relationship to GPU Entity

**Specs affected**: FEAT-03, foundation-spec

**The conflict**:
- FEAT-03 defines `GpuPriceSnapshot` with field `ModelId` (string FK)
- FEAT-03 says it references `GpuPerformanceTier` via `ModelId`
- But `GpuPerformanceTier` is not defined in foundation spec
- Foundation spec defines `GPU` entity with `id` (UUID) as PK and `model_id` (string) as unique alternate key
- Unclear if `GpuPriceSnapshot.ModelId` should FK to `GPU.model_id` or `GpuPerformanceTier.ModelId`

**Example**:
- FEAT-03 GpuPriceSnapshot: "| ModelId | string(50) | FK → GpuPerformanceTier, not null |"
- Foundation GPU: "| id | UUID | PK, not null | ... | model_id | string(100) | unique, not null |"

**Fix**: Clarify entity hierarchy. Options:
1. `GpuPerformanceTier` is the canonical GPU reference model, foundation `GPU` entity should FK to it
2. Foundation `GPU` is canonical, FEAT-03 `GpuPerformanceTier` should be merged into foundation `GPU`
3. Keep both separate, clarify that `GpuPriceSnapshot.ModelId` FKs to `GPU.model_id` (string), not `GPU.id` (UUID)

Recommendation: Option 2 — merge `GpuPerformanceTier` into foundation `GPU` entity to eliminate duplication.

---

## WARNING Issues

### [W1] Redis Cache Key Naming Convention Mismatch

**Specs affected**: foundation-spec, FEAT-03, FEAT-05

**The conflict**:
- Foundation defines cache keys as `viz:{manufacturer}:current`
- FEAT-05 defines cache keys as `gpus:manufacturer:{manufacturer}`
- Different namespacing patterns (colon-separated vs mixed)

**Example**:
- Foundation: "Redis cache keys use manufacturer-specific namespacing: `viz:radeon:current`, `viz:nvidia:current`"
- FEAT-05: "Redis cache key: `gpus:manufacturer:{manufacturer}` (e.g., `gpus:manufacturer:radeon`)"

**Fix**: Establish single cache key naming convention across all features. Recommendation: Use `{feature}:{entity}:{identifier}` pattern:
- Visualization: `viz:gpus:radeon:current`
- Retail prices: `retail:prices:nvidia`
- Used prices: `used:prices:radeon`

---

### [W2] API Endpoint Response Field Ordering Inconsistency

**Specs affected**: FEAT-01, FEAT-02, FEAT-03, FEAT-05

**The conflict**:
- Different features order response fields differently
- FEAT-01 puts `status` first, then `lastUpdated`, then data
- FEAT-05 puts `manufacturer` first, then data, then `metadata` object
- No consistent pattern for metadata placement

**Fix**: Establish canonical response structure:
```json
{
  "data": [...],
  "metadata": {
    "count": 0,
    "lastUpdated": "timestamp",
    ...
  }
}
```
Apply consistently across all feature API endpoints.

---

### [W3] Scraping Schedule Time Inconsistency

**Specs affected**: foundation-spec, FEAT-01, FEAT-02

**The conflict**:
- Foundation Hangfire config shows retail scraper at 2 AM UTC
- FEAT-01 says "Daily scrape runs at 2:00 AM UTC"
- FEAT-02 says "Daily scrape runs at 3:00 AM UTC"
- But foundation's RecurringJob for used scraper also shows 3 AM UTC (correct)
- Potential confusion if times change — only one source of truth needed

**Fix**: Not a blocker (times are actually consistent), but document in foundation spec that retail runs at 2 AM, used at 3 AM, to avoid sequential overload.

---

## CLEAN Sections

- **UUID Primary Keys**: All entities consistently use UUID for `id` field (foundation standard correctly applied)
- **Timestamp Types**: All specs use `timestamp` or `datetime` types for UTC timestamps (no date-only fields that would cause timezone issues)
- **Boolean Field Naming**: Consistent `is_*` prefix for boolean flags (`is_in_stock`, `is_outlier`, `is_current_gen`)
- **Decimal Precision**: All price fields consistently use `decimal(10,2)` for currency amounts
- **Check Constraints**: All specs define explicit CHECK constraints for enums (good practice, prevents bad data)
- **HTTP Status Codes**: Consistent use of 400 (validation), 401 (auth), 403 (authorization), 404 (not found), 429 (rate limit)
- **Authentication Mechanism**: All admin endpoints consistently require JWT Bearer token or HttpOnly cookie (foundation pattern correctly followed)
- **API Versioning**: All endpoints use `/api/v1/` prefix consistently
- **Error Response Format**: All specs reference RFC 7807 ProblemDetails format for errors
- **Rate Limiting**: Consistent 429 status code with retry-after headers across features

---

## Regeneration Order

If specs need to be regenerated, do it in this order to avoid cascading inconsistencies:

1. **foundation-spec** — Establish canonical entity names, field names, and types
   - Fix: Clarify `GPU` entity owns `manufacturer`, `performance_score`, `official_spec_url` fields
   - Fix: Define `ScraperLog` schema to accommodate both retail and used scraping
   - Fix: Remove duplicate ownership of `RetailPriceAverage`, `UsedPriceAverage` (foundation owns storage, features own business logic)

2. **FEAT-05-radeon-vs-nvidia-mode-switching-spec** — Depends on foundation GPU entity
   - Fix: Reference foundation `GPU.manufacturer` field (don't redefine it)
   - Fix: Update cache key naming to match foundation convention

3. **FEAT-04-manufacturer-reference-links-spec** — Extends foundation GPU entity
   - Fix: Reference foundation `GPU.official_spec_url` and `spec_url_status` fields (don't redefine)
   - Fix: Remove data model section (foundation owns these fields)

4. **FEAT-03-value-visualization-dashboard-spec** — Depends on foundation GPU and FEAT-01/02 pricing entities
   - Fix: Merge `GpuPerformanceTier` into foundation `GPU` entity OR clarify FK relationship
   - Fix: Update `GpuPriceSnapshot.ModelId` to FK to `GPU.model_id` (string) or `GPU.id` (UUID)
   - Fix: Change API currency from USD to GBP
   - Fix: Rename `oemProductUrl` to `officialSpecUrl` to match foundation field

5. **FEAT-01-live-retail-price-aggregation-spec** — Depends on foundation GPU entity
   - Fix: Rename `RetailPrice` entity to `RetailPriceAverage` to match foundation
   - Fix: Clarify this feature does not own `RetailListing` or `RetailPriceAverage` entities (foundation owns them)
   - Fix: Reference foundation `GPU` entity via `gpu_model_id` FK

6. **FEAT-02-used-market-price-discovery-spec** — Depends on foundation GPU entity and FEAT-01 pattern
   - Fix: Clarify this feature does not own `UsedListing` or `UsedPriceAverage` entities (foundation owns them)
   - Fix: Rename `ScrapeJob` to avoid confusion with foundation `ScraperLog`
   - Fix: Reference foundation `GPU` entity via `gpu_model_id` FK