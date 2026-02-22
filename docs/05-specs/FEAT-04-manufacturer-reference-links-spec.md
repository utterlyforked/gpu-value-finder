# Manufacturer Reference Links — Engineering Spec

**Type**: feature
**Component**: manufacturer-reference-links
**Dependencies**: foundation-spec (GPU entity, dashboard UI)
**Status**: Ready for Implementation

---

## Instructions for Implementation

This document is a technical contract. Your job is to implement everything described here:
- Create all database migrations defined in the Data Model section
- Implement all API endpoints defined in the API Endpoints section
- Enforce all business rules, validation rules, and authorization policies exactly as specified
- Write tests that verify each acceptance criterion

Do not add features, fields, or behaviours not listed in this document.
Do not omit anything listed in this document.

---

## Overview

The Manufacturer Reference Links feature extends the existing GPU entity with official specification links, enabling users to access authoritative technical documentation from AMD and Nvidia product pages. This component owns three new fields on the GPU entity (`OfficialSpecUrl`, `SpecUrlStatus`, `SpecUrlLastChecked`) and a weekly validation job that monitors link health. It provides read-only spec links in the dashboard UI and admin tooling for CSV-based URL management and link status monitoring.

This feature reads from the foundation GPU entity (defined in foundation-spec) but does not own or redefine it. All spec link data is scoped to individual GPU models with 1:1 cardinality.

---

## Data Model

### GPU (Extended Entity - Foundation Owned)

> **Note**: The GPU entity is defined in the Foundation Spec. This feature extends it with three new fields only. All other GPU fields (Id, ModelName, Manufacturer, etc.) remain unchanged and are not redefined here.

**New Fields Added by This Feature**:

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| official_spec_url | string(2048) | nullable | Full HTTPS URL to manufacturer product page |
| spec_url_status | integer | not null, default 2 | Enum: 0=Active, 1=Unavailable, 2=NeedsReview |
| spec_url_last_checked | timestamptz | nullable | UTC timestamp of last validation job run |

**Indexes**:
- `(spec_url_status)` non-unique (for monitoring dashboard queries)

**Relationships**:
- No new relationships introduced
- Spec URL is 1:1 with GPU model

**Constraints**:
- `official_spec_url` must be null OR match pattern `https://(www\.amd\.com|www\.nvidia\.com)/.*`
- `spec_url_status` must be 0, 1, or 2

**Status Enum Values**:
```
Active = 0        // URL working, last validation returned 200 OK
Unavailable = 1   // GPU discontinued or URL permanently broken
NeedsReview = 2   // Validation failed, awaiting admin review
```

---

## API Endpoints

### GET /api/v1/gpus

**Auth**: None (public endpoint)  
**Authorization**: Public read access

**Query Parameters**:
| Parameter | Type | Required | Validation |
|-----------|------|----------|-----------|
| manufacturer | string | no | Must be "AMD" or "Nvidia" if provided |
| minPrice | decimal | no | Must be >= 0 |
| maxPrice | decimal | no | Must be >= minPrice |

**Success Response** `200 OK`:
| Field | Type | Notes |
|-------|------|-------|
| id | integer | GPU primary key |
| modelName | string | e.g., "Radeon RX 7900 XTX" |
| manufacturer | string | "AMD" or "Nvidia" |
| officialSpecUrl | string or null | Full URL or null if unavailable |
| specUrlStatus | integer | 0=Active, 1=Unavailable, 2=NeedsReview |
| ... | ... | Other GPU fields from foundation spec |

**Error Responses**:
| Status | Condition |
|--------|-----------|
| 400 | Invalid query parameter format |
| 500 | Database connection failure |

**Notes**:
- `specUrlStatus` is included in response for frontend conditional rendering
- `specUrlLastChecked` is NOT included in public API response (internal field)
- Frontend uses `specUrlStatus` to determine link visibility (Active = show link, Unavailable/NeedsReview = show "Specs Unavailable")

---

### POST /api/v1/admin/gpus/import-spec-urls

**Auth**: Required (Bearer JWT)  
**Authorization**: AdminUser policy

**Request Body** (multipart/form-data):
| Field | Type | Required | Validation |
|-------|------|----------|-----------|
| csvFile | file | yes | Must be .csv file, max 5 MB |

**CSV Format**:
```
GpuId,ModelName,OfficialSpecUrl,Notes
1,Radeon RX 7900 XTX,https://www.amd.com/en-gb/products/graphics/amd-radeon-rx-7900xtx.html,
2,GeForce RTX 4090,https://www.nvidia.com/en-gb/geforce/graphics-cards/40-series/rtx-4090/,
3,GeForce GTX 1660,,Discontinued - no official page
```

**Success Response** `200 OK`:
| Field | Type | Notes |
|-------|------|-------|
| imported | integer | Count of URLs successfully imported |
| updated | integer | Count of existing URLs updated |
| skipped | integer | Count of rows skipped (invalid format) |
| errors | array of objects | List of row-level validation errors |

**Error Response Object**:
| Field | Type | Notes |
|-------|------|-------|
| row | integer | CSV row number (1-indexed, excluding header) |
| gpuId | integer or null | GPU ID from CSV if parseable |
| error | string | Human-readable error message |

**Error Responses**:
| Status | Condition |
|--------|-----------|
| 400 | Invalid CSV format or validation errors |
| 401 | Not authenticated |
| 403 | Not authorized (not AdminUser) |
| 413 | File exceeds 5 MB limit |
| 415 | Not a CSV file (wrong Content-Type) |

**Business Logic**:
1. Parse CSV, skip rows with empty GpuId
2. For each row:
   - Validate GpuId exists in database
   - Validate URL format (must be null OR match AMD/Nvidia domain pattern)
   - Update `official_spec_url` field
   - Set `spec_url_status` to `NeedsReview` (will be validated by next job run)
   - Set `spec_url_last_checked` to null
3. Return summary with errors for invalid rows (do not rollback entire import)

---

### GET /api/v1/admin/gpus/spec-url-status

**Auth**: Required (Bearer JWT)  
**Authorization**: AdminUser policy

**Query Parameters**:
| Parameter | Type | Required | Validation |
|-----------|------|----------|-----------|
| status | integer | no | Must be 0, 1, or 2 if provided |
| manufacturer | string | no | Must be "AMD" or "Nvidia" if provided |

**Success Response** `200 OK`:
| Field | Type | Notes |
|-------|------|-------|
| gpus | array of objects | List of GPUs matching filters |

**GPU Object**:
| Field | Type | Notes |
|-------|------|-------|
| id | integer | GPU primary key |
| modelName | string | |
| manufacturer | string | |
| officialSpecUrl | string or null | |
| specUrlStatus | integer | |
| specUrlLastChecked | ISO 8601 datetime or null | UTC timestamp |

**Error Responses**:
| Status | Condition |
|--------|-----------|
| 400 | Invalid query parameter |
| 401 | Not authenticated |
| 403 | Not authorized (not AdminUser) |

**Notes**:
- Used by admin monitoring dashboard to review broken links
- Defaults to `status=2` (NeedsReview) if no status filter provided
- Results ordered by `modelName` ascending

---

### PATCH /api/v1/admin/gpus/{id}/spec-url-status

**Auth**: Required (Bearer JWT)  
**Authorization**: AdminUser policy

**Request Body**:
| Field | Type | Required | Validation |
|-------|------|----------|-----------|
| status | integer | yes | Must be 0, 1, or 2 |
| url | string | no | Must match AMD/Nvidia domain pattern if provided |

**Success Response** `200 OK`:
| Field | Type | Notes |
|-------|------|-------|
| id | integer | GPU primary key |
| modelName | string | |
| specUrlStatus | integer | Updated status |
| officialSpecUrl | string or null | Updated URL if provided |

**Error Responses**:
| Status | Condition |
|--------|-----------|
| 400 | Invalid status value or URL format |
| 401 | Not authenticated |
| 403 | Not authorized (not AdminUser) |
| 404 | GPU ID not found |

**Business Logic**:
- If `url` provided, update `official_spec_url` field
- Update `spec_url_status` to provided value
- Do NOT update `spec_url_last_checked` (manual changes don't count as validation)
- Used by admin to resolve `NeedsReview` flags after manual investigation

---

## Business Rules

1. **URL Format Validation**: `official_spec_url` must be null OR a full HTTPS URL pointing to `www.amd.com` or `www.nvidia.com` domains (no other domains allowed).

2. **Status Transitions (Validation Job)**:
   - If HTTP HEAD request returns 200 OK → Set status to `Active` (0)
   - If HTTP HEAD request returns 404, 503, timeout, or any non-200 status → Set status to `NeedsReview` (2)
   - Skip GPUs where status is already `Unavailable` (1) — do not re-validate discontinued models

3. **Status Transitions (Manual Admin Action)**:
   - Admin may change status from `NeedsReview` (2) to `Active` (0) if link is temporarily broken
   - Admin may change status from `NeedsReview` (2) to `Unavailable` (1) if GPU is confirmed discontinued
   - Admin may update `official_spec_url` and reset status to `Active` (0) if URL has moved

4. **User-Facing Link Visibility**:
   - If `spec_url_status` is `Active` (0) → Display clickable "Official Specs ↗️" link
   - If `spec_url_status` is `Unavailable` (1) OR `NeedsReview` (2) → Display non-interactive "Specs Unavailable" text
   - Users never see broken links — link hides immediately when status changes from Active

5. **Regional URL Priority**: When populating URLs via CSV import, prefer UK-specific URLs (`/en-gb/`) over global English (`/en/` or `/en-us/`). If both exist, store UK version. This is a manual data entry guideline, not enforced by validation logic.

6. **Validation Job Rate Limiting**: HTTP HEAD requests must be sent sequentially with 1-second delay between requests to avoid triggering manufacturer rate limits.

7. **CSV Import Idempotency**: Importing the same CSV file multiple times updates existing URLs (does not create duplicates). Uses `GpuId` as unique identifier.

8. **Null URL Handling**: A GPU with `official_spec_url = null` and `spec_url_status = Unavailable` represents a discontinued or OEM-exclusive model with no official product page. This is valid state (not an error).

---

## Validation Rules

### CSV Import Validation

| Field | Rule | Error Message |
|-------|------|---------------|
| GpuId | Required, must exist in database | "GPU with ID {id} not found" |
| OfficialSpecUrl | Must be null OR valid HTTPS URL | "Invalid URL format for GPU {id}" |
| OfficialSpecUrl | Must match domain pattern `https://(www\.amd\.com\|www\.nvidia\.com)/.*` | "URL must point to amd.com or nvidia.com for GPU {id}" |
| OfficialSpecUrl | Max 2048 characters | "URL too long for GPU {id} (max 2048 chars)" |

### Admin Status Update Validation

| Field | Rule | Error Message |
|-------|------|---------------|
| status | Required, must be 0, 1, or 2 | "Status must be 0 (Active), 1 (Unavailable), or 2 (NeedsReview)" |
| url | If provided, must match domain pattern | "URL must point to amd.com or nvidia.com" |
| url | If provided, max 2048 characters | "URL too long (max 2048 chars)" |

### Validation Job Logic

No user input validation required — job operates on existing database records.

---

## Authorization

| Action | Required Policy | Notes |
|--------|----------------|-------|
| View GPU spec URLs | None (public) | Via GET /api/v1/gpus endpoint |
| Import spec URLs via CSV | AdminUser | POST /api/v1/admin/gpus/import-spec-urls |
| View spec URL monitoring dashboard | AdminUser | GET /api/v1/admin/gpus/spec-url-status |
| Update GPU spec URL status | AdminUser | PATCH /api/v1/admin/gpus/{id}/spec-url-status |
| Trigger validation job manually | AdminUser | Via Hangfire dashboard (existing auth) |

**AdminUser Policy Definition**:
- User must have `IsAdmin = true` claim in JWT token
- Defined in Foundation Spec (not redefined here)

---

## Background Jobs

### Spec URL Validation Job

**Schedule**: Weekly, Sunday 2:00 AM UTC  
**Hangfire Cron**: `"0 2 * * 0"`  
**Job ID**: `"validate-spec-urls"`

**Process**:
1. Query all GPUs where `spec_url_status IN (0, 2)` (Active or NeedsReview)
   - Skip GPUs with `spec_url_status = 1` (Unavailable) — do not re-validate discontinued models
2. For each GPU, sequentially:
   - Send HTTP HEAD request to `official_spec_url`
   - Set timeout to 10 seconds
   - Wait 1 second before next request (rate limiting)
   - Follow redirects (max 5 hops)
   - Set User-Agent header: `"GPU-Value-Tracker-Link-Validator/1.0"`
3. Process response:
   - If 200 OK → Set `spec_url_status = 0` (Active), update `spec_url_last_checked` to current UTC time
   - If 404, 503, timeout, or any non-200 status → Set `spec_url_status = 2` (NeedsReview), update `spec_url_last_checked`, log error details
4. Log job completion summary:
   - Total GPUs checked
   - Count of Active confirmations
   - Count of new NeedsReview flags
   - List of newly broken URLs with GPU IDs and status codes

**Error Handling**:
- If HTTP request throws exception (network error, DNS failure) → Treat as validation failure (set to NeedsReview)
- If redirect chain exceeds 5 hops → Treat as validation failure
- If final redirect destination URL differs from stored URL → Log warning but treat as success if 200 OK (don't auto-update stored URL)
- Do not retry failed validations within same job run — wait for next weekly execution

**Monitoring**:
- Log job start/completion to Application Insights
- Create custom metric: `SpecUrlValidation.NeedsReviewCount` (gauge, updated weekly)
- Alert if `NeedsReviewCount > 10` (indicates site-wide manufacturer issue)

**Hangfire Configuration**:
- Job queue: `"maintenance"` (or default queue if maintenance queue doesn't exist)
- No automatic retries (manual investigation required for failures)
- Retain job history for 30 days

---

## Acceptance Criteria

- [ ] GPU entity has three new fields: `official_spec_url`, `spec_url_status`, `spec_url_last_checked`
- [ ] Database migration runs successfully and adds new columns with correct types and defaults
- [ ] CSV import endpoint accepts valid CSV files and populates GPU spec URLs
- [ ] CSV import validates URL format and rejects non-AMD/Nvidia domains
- [ ] CSV import returns row-level errors for invalid data without rolling back entire import
- [ ] Admin can view list of GPUs with `NeedsReview` status via monitoring endpoint
- [ ] Admin can manually update spec URL status via PATCH endpoint
- [ ] Validation job runs weekly on Sunday 2:00 AM UTC
- [ ] Validation job sends HTTP HEAD requests with 1-second delays between requests
- [ ] Validation job sets status to `Active` for URLs returning 200 OK
- [ ] Validation job sets status to `NeedsReview` for URLs returning 404 or timing out
- [ ] Validation job skips GPUs with `Unavailable` status
- [ ] Validation job logs newly broken URLs to Application Insights
- [ ] Frontend displays "Official Specs ↗️" link for GPUs with `Active` status
- [ ] Frontend displays "Specs Unavailable" text for GPUs with `Unavailable` or `NeedsReview` status
- [ ] Spec links open in new tab with `target="_blank"` and `rel="noopener noreferrer"` attributes
- [ ] Spec links have descriptive `aria-label` for screen reader accessibility
- [ ] Non-admin users cannot access CSV import endpoint (returns 403)
- [ ] Non-admin users cannot access monitoring endpoint (returns 403)
- [ ] Non-admin users cannot update spec URL status (returns 403)
- [ ] Public GET /api/v1/gpus endpoint includes `officialSpecUrl` and `specUrlStatus` fields
- [ ] Public GET /api/v1/gpus endpoint does NOT include `specUrlLastChecked` field

---

## Security Requirements

### Input Validation

- **CSV File Upload**:
  - Max file size: 5 MB (enforced by ASP.NET Core request size limit)
  - Content-Type must be `text/csv` or `application/vnd.ms-excel`
  - Reject files with executable extensions (`.exe`, `.dll`, `.sh`) even if renamed to `.csv`
  - Scan for malicious content patterns (SQL injection in URL field, script tags)

- **URL Validation**:
  - Enforce HTTPS-only (reject `http://` or `ftp://` schemes)
  - Whitelist domains: `www.amd.com`, `www.nvidia.com` only
  - Reject URLs with query parameters or fragments (e.g., `?utm_source=...`, `#section`) to prevent tracking pixel injection
  - Max length 2048 characters (prevent buffer overflow)

### HTTP Request Security (Validation Job)

- **User-Agent Header**: Set descriptive UA string to identify bot traffic to manufacturer sites
- **Redirect Policy**: Follow max 5 redirects to prevent infinite loops
- **Timeout**: 10-second hard timeout per request to prevent resource exhaustion
- **TLS Verification**: Validate SSL certificates, reject self-signed or expired certs
- **Rate Limiting**: 1 req/sec to avoid triggering manufacturer WAF/rate limits
- **No Authentication Headers**: Do not send any cookies or auth tokens to manufacturer sites

### Authorization

- **Admin Endpoints**: All `/api/v1/admin/*` endpoints require `AdminUser` policy (verified via JWT claims)
- **CSV Import**: Admin-only, audit log all imports with username and timestamp
- **Status Updates**: Admin-only, audit log all manual status changes

### Data Protection

- **No PII in Logs**: Do not log full URLs in validation errors (log GPU ID only)
- **No Credentials Storage**: Spec URLs are public manufacturer pages (no API keys or credentials stored)
- **Rate Limit Public API**: GET /api/v1/gpus endpoint limited to 100 requests per minute per IP (Foundation Spec rate limiting)

### Audit Logging

Log the following events to Application Insights:
- CSV import with row count and admin username
- Manual spec URL status changes with old/new status and admin username
- Validation job completion with broken link count
- Failed admin authentication attempts on admin endpoints

---

## Not In This Document

This document does not contain:

- **Implementation code** — Write C#, TypeScript, and EF Core migrations yourself based on contracts above
- **Test case definitions** — See QA spec for detailed test plans
- **Python script for CSV generation** — Script is tooling, not part of application codebase
- **Frontend component styling details** — Use Tailwind CSS classes specified in feature doc, implementation details are your choice
- **Hangfire dashboard configuration** — Use existing Hangfire setup from Foundation Spec
- **Database connection strings** — Use existing configuration from appsettings.json
- **Deployment instructions** — Follow standard deployment process for application
- **Email notifications for broken links** — Future feature, not in MVP scope
- **Multi-regional URL storage** — Single URL per GPU for MVP, internationalization deferred
- **Real-time link status updates** — Weekly validation only, no WebSockets or SSE
- **Click analytics for spec links** — No user tracking, privacy-first approach
- **Archived spec hosting** — Do not cache or mirror manufacturer content

---

## Database Migration Checklist

**Migration Name**: `AddGpuSpecUrlFields`

**Up Migration**:
- [ ] Add `official_spec_url` column (VARCHAR(2048), nullable)
- [ ] Add `spec_url_status` column (INTEGER, not null, default 2)
- [ ] Add `spec_url_last_checked` column (TIMESTAMPTZ, nullable)
- [ ] Create non-unique index on `spec_url_status`
- [ ] Add check constraint: `spec_url_status IN (0, 1, 2)`
- [ ] Add check constraint: `official_spec_url IS NULL OR official_spec_url LIKE 'https://%'`

**Down Migration**:
- [ ] Drop index on `spec_url_status`
- [ ] Drop column `spec_url_last_checked`
- [ ] Drop column `spec_url_status`
- [ ] Drop column `official_spec_url`

**Data Migration** (run separately after schema migration):
- [ ] No data migration required — all GPUs default to `NeedsReview` status with null URL
- [ ] CSV import will populate URLs post-deployment

---

## Frontend Integration Checklist

**Component**: `GpuCard.tsx` (extends existing component from Foundation Spec)

**Changes Required**:
- [ ] Add `officialSpecUrl: string | null` to GPU interface
- [ ] Add `specUrlStatus: 0 | 1 | 2` to GPU interface
- [ ] Implement conditional rendering in card footer:
  - If `specUrlStatus === 0` → Render `<a>` tag with "Official Specs ↗️" text
  - If `specUrlStatus === 1 || specUrlStatus === 2` → Render `<span>` with "Specs Unavailable" text
- [ ] Add link attributes: `target="_blank"`, `rel="noopener noreferrer"`
- [ ] Add `aria-label` with format: `"View official specifications for {modelName} on {manufacturer} website"`
- [ ] Apply Tailwind CSS classes: `text-sm text-gray-600 hover:text-gray-900 underline underline-offset-2 transition-colors duration-150`
- [ ] Position link in right-aligned card footer
- [ ] Test keyboard navigation (focus state visible)
- [ ] Test screen reader announcement (aria-label read correctly)

**No New API Calls Required**:
- Spec URL data included in existing GET /api/v1/gpus response
- No loading states needed

---

## Testing Strategy

### Unit Tests

**Backend (C# xUnit)**:
- [ ] CSV import service parses valid CSV and returns success summary
- [ ] CSV import service rejects invalid GPU IDs with row-level errors
- [ ] CSV import service rejects non-AMD/Nvidia URLs
- [ ] CSV import service handles empty URL field (sets to null)
- [ ] Validation job sets status to Active for 200 OK response
- [ ] Validation job sets status to NeedsReview for 404 response
- [ ] Validation job skips GPUs with Unavailable status
- [ ] Validation job updates `spec_url_last_checked` timestamp
- [ ] Admin endpoints return 403 for non-admin users

**Frontend (Vitest)**:
- [ ] GpuCard renders clickable link when status is Active
- [ ] GpuCard renders "Specs Unavailable" text when status is Unavailable
- [ ] GpuCard renders "Specs Unavailable" text when status is NeedsReview
- [ ] Link has correct `target="_blank"` and `rel="noopener noreferrer"` attributes
- [ ] Link has descriptive `aria-label` with GPU model name

### Integration Tests

**Backend (C# xUnit + TestServer)**:
- [ ] CSV import endpoint accepts multipart/form-data and processes file
- [ ] CSV import endpoint returns 413 for files >5 MB
- [ ] Admin monitoring endpoint filters by status correctly
- [ ] Admin status update endpoint updates database record
- [ ] Public API includes spec URL fields in response

### E2E Tests (Playwright)

- [ ] User views dashboard and sees "Official Specs ↗️" link for active GPU
- [ ] User clicks spec link and new tab opens to manufacturer site
- [ ] User views dashboard and sees "Specs Unavailable" for discontinued GPU
- [ ] Admin logs in, uploads CSV file, sees import success message
- [ ] Admin logs in, views monitoring dashboard, sees NeedsReview GPUs
- [ ] Admin logs in, updates GPU status to Active, link appears on dashboard

### Performance Tests

- [ ] Validation job processes 100 GPUs in <5 minutes (with 1 req/sec rate limit)
- [ ] CSV import processes 100 rows in <10 seconds
- [ ] Public API response time <200ms for 100 GPU records (including spec URL fields)

---

## Deployment Plan

**Phase 1: Schema Migration (Week 1)**
1. Deploy database migration to staging environment
2. Verify columns added successfully with correct defaults
3. Run sample CSV import in staging with 5 test GPUs
4. Deploy database migration to production (low-risk, additive-only change)

**Phase 2: Backend Services (Week 1-2)**
1. Deploy API endpoints to staging
2. Test CSV import with full GPU catalog (~100 rows)
3. Configure Hangfire job in staging, run manually to verify
4. Deploy backend to production
5. Schedule Hangfire job for Sunday 2:00 AM UTC

**Phase 3: Frontend (Week 2)**
1. Deploy updated GpuCard component to staging
2. Verify link visibility logic with test data (Active/Unavailable/NeedsReview GPUs)
3. Deploy frontend to production

**Phase 4: Data Population (Week 2)**
1. Run Python script to generate CSV with suggested URLs
2. Product owner reviews CSV, corrects mismatches
3. Admin uploads finalized CSV via import endpoint
4. Manually trigger validation job to verify all URLs
5. Monitor Application Insights for broken link alerts

**Rollback Plan**:
- If CSV import fails: Revert individual GPU records via admin interface
- If validation job crashes: Disable Hangfire job, investigate logs, fix and redeploy
- If frontend breaks: Revert frontend deployment (backend/database changes are backwards-compatible)
- Database migration rollback: Run down migration (safe, no data loss since fields are new)

---

## Monitoring & Observability

**Metrics to Track (Application Insights)**:
- `SpecUrlValidation.NeedsReviewCount` — Gauge, updated weekly after validation job
- `SpecUrlValidation.ActiveCount` — Gauge, count of working URLs
- `SpecUrlImport.RowsProcessed` — Counter, incremented on CSV import
- `SpecUrlImport.ValidationErrors` — Counter, incremented for invalid CSV rows

**Log Events**:
- `SpecUrlValidationJobStarted` — Logged at job start with timestamp
- `SpecUrlValidationJobCompleted` — Logged at job end with summary stats
- `SpecUrlBroken` — Logged for each URL that changes from Active to NeedsReview (includes GPU ID, URL, status code)
- `SpecUrlImportStarted` — Logged when admin uploads CSV (includes filename, row count)
- `SpecUrlImportCompleted` — Logged after import with success/error counts
- `SpecUrlStatusUpdated` — Logged when admin manually changes status (includes GPU ID, old status, new status, admin username)

**Alerts**:
- Alert if `SpecUrlValidation.NeedsReviewCount > 10` → Notify product owner via email
- Alert if validation job fails to complete (no `SpecUrlValidationJobCompleted` log within 1 hour of scheduled time)
- Alert if CSV import endpoint returns 500 error

**Dashboard Queries** (Application Insights Analytics):
```kusto
// GPUs needing review
customMetrics
| where name == "SpecUrlValidation.NeedsReviewCount"
| summarize arg_max(timestamp, value)

// Recent broken links
traces
| where message contains "SpecUrlBroken"
| project timestamp, GPU_ID = tostring(customDimensions.GpuId), URL = tostring(customDimensions.Url), StatusCode = tostring(customDimensions.StatusCode)
| order by timestamp desc
| take 20
```

---

**This engineering specification is complete and ready for implementation. All acceptance criteria, validation rules, and security requirements are defined. Proceed with coding the solution based on these contracts.**