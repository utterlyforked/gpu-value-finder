# Live Retail Price Aggregation — Engineering Spec

**Type**: feature
**Component**: live-retail-price-aggregation
**Dependencies**: foundation-spec (Auth, User, Group entities)
**Status**: Ready for Implementation

---

## Instructions for Implementation

This document is a technical contract. Your job is to implement everything described here:
- Create all database tables and migrations defined in the Data Model section
- Implement all API endpoints defined in the API Endpoints section
- Enforce all business rules, validation rules, and authorization policies exactly as specified
- Write tests that verify each acceptance criterion

Do not add features, fields, or behaviours not listed in this document.
Do not omit anything listed in this document.

---

## Overview

The Live Retail Price Aggregation feature establishes baseline "new GPU" pricing by scraping and aggregating current retail prices from three major UK retailers: Scan, Ebuyer, and Amazon UK. This feature tracks only latest-generation GPUs with 16GB+ VRAM that are currently in stock, providing accurate market pricing data.

This component owns three entities: `RetailListing` (individual retailer price records), `RetailPrice` (aggregated price calculations per GPU model), and `ScraperLog` (execution history). It reads from the foundation `User` entity for admin authorization but does not write to or modify foundation entities.

The feature exposes two public API endpoints for retrieving price data and two admin-only endpoints for manual scraper triggering and job status monitoring.

---

## Data Model

### RetailListing

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| id | UUID | PK, not null | Generated on insert |
| gpu_model | string(50) | not null | e.g., "RTX 4090", "RX 7900 XTX" |
| manufacturer | string(20) | not null | "Nvidia" or "Radeon" |
| vram_size_gb | integer | not null | e.g., 24, 16, 20 |
| retailer | string(50) | not null | "Scan", "Ebuyer", or "Amazon" |
| price | decimal(10,2) | not null, check > 0 | Price in GBP |
| is_in_stock | boolean | not null | True if available for purchase |
| product_url | text | nullable | Link to retailer product page |
| scraped_at | timestamp | not null | UTC timestamp of scrape |
| created_at | timestamp | not null | UTC timestamp of record creation |
| updated_at | timestamp | not null | UTC timestamp of last update |

**Indexes**:
- `(gpu_model, scraped_at DESC)` - Query recent listings per model
- `(manufacturer)` - Filter by manufacturer
- `(retailer, scraped_at DESC)` - Monitor retailer scrape history

**Constraints**:
- `CHECK (price > 0)`
- `CHECK (manufacturer IN ('Nvidia', 'Radeon'))`
- `CHECK (retailer IN ('Scan', 'Ebuyer', 'Amazon'))`

**Relationships**:
- None (standalone entity)

---

### RetailPrice

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| id | UUID | PK, not null | Generated on insert |
| gpu_model | string(50) | unique, not null | One row per GPU model |
| manufacturer | string(20) | not null | "Nvidia" or "Radeon" |
| vram_size_gb | integer | not null | e.g., 24, 16, 20 |
| min_price | decimal(10,2) | not null | Cheapest in-stock listing |
| avg_price | decimal(10,2) | not null | Average of in-stock listings |
| max_price | decimal(10,2) | not null | Most expensive in-stock listing |
| listing_count | integer | not null | Total listings contributing to calculation |
| in_stock_count | integer | not null | Number of in-stock listings |
| is_in_stock | boolean | not null | True if any retailer has stock |
| last_scraped_at | timestamp | not null | Last successful scrape for this model |
| last_seen_at | timestamp | not null | Last time model was found in any scrape |
| status | string(20) | not null | "Active", "Inactive", or "Archived" |
| created_at | timestamp | not null | UTC timestamp of record creation |
| updated_at | timestamp | not null | UTC timestamp of last update |

**Indexes**:
- `(gpu_model)` unique
- `(manufacturer)` - Filter by manufacturer
- `(status)` - Filter active/inactive/archived

**Constraints**:
- `CHECK (status IN ('Active', 'Inactive', 'Archived'))`
- `CHECK (manufacturer IN ('Nvidia', 'Radeon'))`
- `CHECK (min_price > 0 AND avg_price > 0 AND max_price > 0)`
- `CHECK (min_price <= avg_price AND avg_price <= max_price)`
- `CHECK (listing_count >= 0 AND in_stock_count >= 0)`
- `CHECK (in_stock_count <= listing_count)`

**Relationships**:
- None (standalone entity)

---

### ScraperLog

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| id | UUID | PK, not null | Generated on insert |
| job_id | UUID | not null | Unique identifier for this scrape run |
| started_at | timestamp | not null | UTC timestamp of job start |
| completed_at | timestamp | nullable | UTC timestamp of job completion |
| status | string(20) | not null | "Success", "PartialFailure", or "Failure" |
| scan_status | string(20) | nullable | "Success", "Failed", or "Skipped" |
| ebuyer_status | string(20) | nullable | "Success", "Failed", or "Skipped" |
| amazon_status | string(20) | nullable | "Success", "Failed", or "Skipped" |
| scan_error | text | nullable | Error message if Scan failed |
| ebuyer_error | text | nullable | Error message if Ebuyer failed |
| amazon_error | text | nullable | Error message if Amazon failed |
| records_updated | integer | nullable | Number of RetailPrice records updated |
| triggered_by | string(256) | nullable | "scheduled" or admin user email |
| created_at | timestamp | not null | UTC timestamp of record creation |

**Indexes**:
- `(started_at DESC)` - Query recent scrape history
- `(job_id)` unique - Lookup specific job
- `(status)` - Filter by success/failure

**Constraints**:
- `CHECK (status IN ('Success', 'PartialFailure', 'Failure'))`
- `CHECK (scan_status IN ('Success', 'Failed', 'Skipped') OR scan_status IS NULL)`
- `CHECK (ebuyer_status IN ('Success', 'Failed', 'Skipped') OR ebuyer_status IS NULL)`
- `CHECK (amazon_status IN ('Success', 'Failed', 'Skipped') OR amazon_status IS NULL)`

**Relationships**:
- None (standalone entity)

---

> **Note**: This spec owns only the entities listed above. The `User` entity defined in the Foundation Spec is referenced for admin authorization but not redefined here.

---

## API Endpoints

### GET /api/v1/retail-prices

**Auth**: None (public endpoint)
**Authorization**: None

**Query Parameters**:
| Parameter | Type | Required | Validation |
|-----------|------|----------|-----------|
| manufacturer | string | yes | Must be "nvidia" or "radeon" (case-insensitive) |

**Success response** `200 OK`:
| Field | Type | Notes |
|-------|------|-------|
| manufacturer | string | "nvidia" or "radeon" |
| currency | string | Always "GBP" |
| status | string | "success", "cold_start", "scraper_failure", or "partial_failure" |
| lastUpdated | ISO 8601 datetime | UTC timestamp of most recent scrape, null if cold start |
| lastAttemptedAt | ISO 8601 datetime | UTC timestamp of most recent scrape attempt, null if none |
| dataFreshness | string | "current" (<24h), "stale" (24-48h), "very_stale" (>48h), or "unavailable" |
| message | string | User-facing message explaining status (present for non-success statuses) |
| prices | array | Array of GPU price objects (empty array if no data) |
| prices[].model | string | GPU model name (e.g., "RTX 4090") |
| prices[].vramGB | integer | VRAM size in gigabytes |
| prices[].minPrice | decimal | Lowest in-stock price across retailers |
| prices[].avgPrice | decimal | Average of in-stock prices |
| prices[].maxPrice | decimal | Highest in-stock price across retailers |
| prices[].listingCount | integer | Number of listings used in calculation |
| prices[].inStockCount | integer | Number of in-stock listings |
| prices[].inStock | boolean | True if any retailer has stock |
| prices[].lastSeenDaysAgo | integer | Days since last seen in scrape (null if Active) |
| prices[].priceRange.min | decimal | Same as minPrice |
| prices[].priceRange.max | decimal | Same as maxPrice |
| prices[].priceRange.variance | decimal | Percentage variance: ((max-min)/avg * 100) |
| retailers | object | Per-retailer status information |
| retailers.scan.status | string | "success" or "failed" |
| retailers.scan.lastScraped | ISO 8601 datetime | UTC timestamp of last Scan scrape |
| retailers.scan.error | string | Error message if failed (omitted if success) |
| retailers.ebuyer.status | string | "success" or "failed" |
| retailers.ebuyer.lastScraped | ISO 8601 datetime | UTC timestamp of last Ebuyer scrape |
| retailers.ebuyer.error | string | Error message if failed (omitted if success) |
| retailers.amazon.status | string | "success" or "failed" |
| retailers.amazon.lastScraped | ISO 8601 datetime | UTC timestamp of last Amazon scrape |
| retailers.amazon.error | string | Error message if failed (omitted if success) |

**Error responses**:
| Status | Condition |
|--------|-----------|
| 400 | Invalid manufacturer parameter (not "nvidia" or "radeon") |

**Example Success Response**:
```json
{
  "manufacturer": "nvidia",
  "currency": "GBP",
  "status": "success",
  "lastUpdated": "2025-01-12T02:15:33Z",
  "dataFreshness": "current",
  "prices": [
    {
      "model": "RTX 4090",
      "vramGB": 24,
      "minPrice": 1549.99,
      "avgPrice": 1699.00,
      "maxPrice": 1899.00,
      "listingCount": 5,
      "inStockCount": 5,
      "inStock": true,
      "lastSeenDaysAgo": null,
      "priceRange": {
        "min": 1549.99,
        "max": 1899.00,
        "variance": 20.5
      }
    }
  ],
  "retailers": {
    "scan": { "status": "success", "lastScraped": "2025-01-12T02:15:10Z" },
    "ebuyer": { "status": "success", "lastScraped": "2025-01-12T02:15:20Z" },
    "amazon": { "status": "success", "lastScraped": "2025-01-12T02:15:30Z" }
  }
}
```

---

### POST /api/v1/admin/scraper/trigger

**Auth**: Required (Bearer JWT)
**Authorization**: User must have `Admin` role in JWT claims

**Request body**:
| Field | Type | Required | Validation |
|-------|------|----------|-----------|
| retailers | array of strings | no | Must be subset of ["Scan", "Ebuyer", "Amazon"]; defaults to all if omitted |
| forceRefresh | boolean | no | If true, scrapes regardless of recent scrape timestamp; defaults to false |

**Success response** `200 OK`:
| Field | Type | Notes |
|-------|------|-------|
| jobId | UUID | Unique identifier for this scrape job |
| status | string | Always "queued" |
| message | string | "Scrape job queued. Check /api/v1/admin/scraper/status/{jobId} for progress." |

**Error responses**:
| Status | Condition |
|--------|-----------|
| 400 | Invalid retailers array (contains unknown retailer names) |
| 401 | Not authenticated (missing or invalid JWT token) |
| 403 | Not authorized (user does not have Admin role) |
| 429 | Rate limit exceeded (more than 1 trigger request in past 5 minutes) |

**Example Request**:
```json
{
  "retailers": ["Scan", "Ebuyer"],
  "forceRefresh": true
}
```

**Example Response**:
```json
{
  "jobId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "queued",
  "message": "Scrape job queued. Check /api/v1/admin/scraper/status/a1b2c3d4-e5f6-7890-abcd-ef1234567890 for progress."
}
```

---

### GET /api/v1/admin/scraper/status/{jobId}

**Auth**: Required (Bearer JWT)
**Authorization**: User must have `Admin` role in JWT claims

**Path Parameters**:
| Parameter | Type | Required | Validation |
|-----------|------|----------|-----------|
| jobId | UUID | yes | Must be valid UUID format |

**Success response** `200 OK`:
| Field | Type | Notes |
|-------|------|-------|
| jobId | UUID | Job identifier from request |
| status | string | "queued", "running", "completed", or "failed" |
| startedAt | ISO 8601 datetime | UTC timestamp of job start (null if queued) |
| completedAt | ISO 8601 datetime | UTC timestamp of job completion (null if running/queued) |
| progress | object | Per-retailer progress information (null if queued) |
| progress.scan | string | "pending", "running", "completed", or "failed" |
| progress.ebuyer | string | "pending", "running", "completed", or "failed" |
| progress.amazon | string | "pending", "running", "completed", or "failed" |
| recordsUpdated | integer | Number of RetailPrice records updated (null if not completed) |
| errors | object | Per-retailer error messages (only present if failures occurred) |
| errors.scan | string | Error message if Scan failed |
| errors.ebuyer | string | Error message if Ebuyer failed |
| errors.amazon | string | Error message if Amazon failed |

**Error responses**:
| Status | Condition |
|--------|-----------|
| 401 | Not authenticated (missing or invalid JWT token) |
| 403 | Not authorized (user does not have Admin role) |
| 404 | Job ID not found |

**Example Response (Running)**:
```json
{
  "jobId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "running",
  "startedAt": "2025-01-12T14:30:00Z",
  "completedAt": null,
  "progress": {
    "scan": "completed",
    "ebuyer": "running",
    "amazon": "pending"
  },
  "recordsUpdated": null,
  "errors": null
}
```

**Example Response (Completed with Partial Failure)**:
```json
{
  "jobId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "completed",
  "startedAt": "2025-01-12T14:30:00Z",
  "completedAt": "2025-01-12T14:35:22Z",
  "progress": {
    "scan": "completed",
    "ebuyer": "completed",
    "amazon": "failed"
  },
  "recordsUpdated": 7,
  "errors": {
    "amazon": "Request timeout after 30 seconds"
  }
}
```

---

## Business Rules

1. Only GPU models in the hardcoded whitelist are eligible for price tracking: RTX 4090, RTX 4080, RTX 4080 Super, RTX 4070 Ti Super (Nvidia); RX 7900 XTX, RX 7900 XT, RX 7800 XT (Radeon).

2. Product titles scraped from retailers are normalized by removing AIB partner names (ASUS, MSI, Gigabyte, etc.) and compared case-insensitively against the whitelist.

3. Only in-stock listings contribute to price calculations (min/avg/max).

4. Retailer data older than 24 hours from the current time is excluded from price calculations.

5. When 4 or more listings exist for a GPU model, outlier filtering is applied: any price more than 2 standard deviations from the median is excluded from average calculation.

6. When 2-3 listings exist for a GPU model, all data points are used but high variance (>25% spread between min and max) is logged as a warning.

7. GPU models not found in scrapes for 14 consecutive days are marked with status "Inactive".

8. GPU models not found in scrapes for 30 consecutive days are marked with status "Archived".

9. Archived models are excluded from the public API response unless explicitly requested (future enhancement; not implemented in v1).

10. When a GPU model reappears in a scrape after being marked Inactive or Archived, its status is reset to "Active".

11. Scraper jobs are scheduled to run daily at 2:00 AM UTC.

12. Each retailer scrape has a maximum timeout of 5 minutes total, with individual HTTP requests timing out after 30 seconds.

13. Failed retailer scrapes are retried up to 3 times with exponential backoff delays (5 seconds, 10 seconds).

14. Admin users may manually trigger scraper jobs, but are rate-limited to 1 trigger per 5 minutes per user.

15. All manual scraper triggers are audit logged with the triggering admin user's email address.

16. Price variance is calculated as: ((max_price - min_price) / avg_price) × 100.

17. Data freshness is categorized as: "current" (<24 hours old), "stale" (24-48 hours old), "very_stale" (>48 hours old), or "unavailable" (no data).

18. When all retailers fail in a scrape run, the most recent successful price data is preserved and returned with status "scraper_failure".

---

## Validation Rules

| Field | Rule | Error message |
|-------|------|---------------|
| manufacturer (query param) | Required, must be "nvidia" or "radeon" (case-insensitive) | "Manufacturer must be 'nvidia' or 'radeon'" |
| retailers (request body) | Optional, must be array, each element must be "Scan", "Ebuyer", or "Amazon" | "Retailers must be an array containing only 'Scan', 'Ebuyer', or 'Amazon'" |
| forceRefresh (request body) | Optional, must be boolean | "Force refresh must be a boolean value" |
| jobId (path param) | Required, must be valid UUID format | "Job ID must be a valid UUID" |
| gpu_model (database) | Required, max 50 chars, must match whitelist | "Invalid GPU model" |
| manufacturer (database) | Required, must be "Nvidia" or "Radeon" | "Manufacturer must be 'Nvidia' or 'Radeon'" |
| vram_size_gb (database) | Required, must be positive integer | "VRAM size must be a positive integer" |
| retailer (database) | Required, must be "Scan", "Ebuyer", or "Amazon" | "Retailer must be 'Scan', 'Ebuyer', or 'Amazon'" |
| price (database) | Required, must be positive decimal(10,2) | "Price must be greater than zero" |
| is_in_stock (database) | Required, must be boolean | "In stock status is required" |
| scraped_at (database) | Required, must be valid timestamp | "Scraped timestamp is required" |
| status (database) | Required, must be "Active", "Inactive", or "Archived" | "Status must be 'Active', 'Inactive', or 'Archived'" |

---

## Authorization

| Action | Required policy | Notes |
|--------|----------------|-------|
| GET /api/v1/retail-prices | None (public) | No authentication required |
| POST /api/v1/admin/scraper/trigger | Authenticated + Admin role | User must have "Admin" claim in JWT |
| GET /api/v1/admin/scraper/status/{jobId} | Authenticated + Admin role | User must have "Admin" claim in JWT |

---

## Acceptance Criteria

- [ ] System scrapes prices from Scan, Ebuyer, and Amazon UK daily at 2:00 AM UTC
- [ ] Only GPU models in the hardcoded whitelist are processed and stored
- [ ] Individual retailer listings are stored in `RetailListing` table with timestamp
- [ ] Aggregated prices (min/avg/max) are calculated and stored in `RetailPrice` table
- [ ] Only in-stock listings contribute to price calculations
- [ ] Retailer data older than 24 hours is excluded from average calculation
- [ ] Outlier filtering is applied when 4+ listings exist (>2 standard deviations excluded)
- [ ] High variance is logged when 2-3 listings have >25% price spread
- [ ] GPU models not found for 14 days are marked "Inactive" with last_seen_at timestamp
- [ ] GPU models not found for 30 days are marked "Archived"
- [ ] Models that reappear after being Inactive/Archived are reset to "Active"
- [ ] GET /api/v1/retail-prices returns 200 OK with status metadata for all scenarios
- [ ] Cold start response includes status "cold_start" and helpful message
- [ ] Scraper failure response includes status "scraper_failure" and preserves last known data
- [ ] Partial failure response includes status "partial_failure" and per-retailer error details
- [ ] Success response includes "current" data freshness when data is <24 hours old
- [ ] Response includes explicit "GBP" currency field
- [ ] Response includes price variance calculation for each model
- [ ] Response includes per-retailer status (success/failed with timestamps and errors)
- [ ] Admin users can trigger manual scrape via POST /api/v1/admin/scraper/trigger
- [ ] Non-admin users receive 403 Forbidden when attempting to trigger scrape
- [ ] Scraper trigger endpoint returns job ID for status polling
- [ ] GET /api/v1/admin/scraper/status/{jobId} returns real-time job progress
- [ ] Manual scraper triggers are rate-limited to 1 per 5 minutes per admin user
- [ ] Manual scraper triggers are audit logged with admin email address
- [ ] Each retailer scrape times out after 30 seconds per request and 5 minutes total
- [ ] Failed retailer scrapes retry up to 3 times with exponential backoff
- [ ] Scraper execution details are logged to `ScraperLog` table
- [ ] When all retailers fail, most recent successful data is preserved and returned
- [ ] Product titles are normalized (AIB names removed) before whitelist matching
- [ ] Price calculations respect min <= avg <= max constraint
- [ ] ListingCount reflects only fresh (<24h) in-stock listings used in calculation
- [ ] Out-of-stock GPUs retain last known price with is_in_stock=false

---

## Security Requirements

- Admin endpoints (`/api/v1/admin/*`) must validate JWT token signature using application's signing key
- Admin endpoints must verify JWT contains claim `role: Admin` or `roles` array includes `Admin`
- JWT tokens must not be expired (validate `exp` claim against current UTC time)
- Rate limiting for admin scraper trigger endpoint: maximum 1 request per 5 minutes per user (identified by JWT `sub` claim)
- All manual scraper triggers must be audit logged with: timestamp, admin user email (from JWT claims), triggered retailers, force_refresh flag
- Retailer scraping must respect robots.txt and implement polite scraping delays (minimum 2 seconds between requests to same domain)
- HTTP requests to retailers must include User-Agent header identifying the application
- Database connections must use parameterized queries to prevent SQL injection
- Price data is public (no PII); no additional access controls required for GET /api/v1/retail-prices
- HTTPS must be enforced for all API endpoints in production environments
- Admin manual trigger endpoint must implement CSRF protection if cookies are used for authentication (not applicable for Bearer token auth)

---

## Configuration

The following configuration must be provided via application settings (appsettings.json, environment variables, or configuration service):

### GPU Whitelist

```json
{
  "EligibleGpuModels": {
    "Nvidia": [
      { "model": "RTX 4090", "vramGB": 24 },
      { "model": "RTX 4080", "vramGB": 16 },
      { "model": "RTX 4080 Super", "vramGB": 16 },
      { "model": "RTX 4070 Ti Super", "vramGB": 16 }
    ],
    "Radeon": [
      { "model": "RX 7900 XTX", "vramGB": 24 },
      { "model": "RX 7900 XT", "vramGB": 20 },
      { "model": "RX 7800 XT", "vramGB": 16 }
    ]
  }
}
```

### Scraper Settings

```json
{
  "ScraperSettings": {
    "RequestTimeoutSeconds": 30,
    "RetailerTotalTimeoutMinutes": 5,
    "MaxRetryAttempts": 3,
    "RetryDelaySeconds": 5,
    "ScheduledExecutionTime": "02:00",
    "RetailerTimeoutOverrides": {},
    "PoliteScrapingDelaySeconds": 2
  }
}
```

### Retailer Configuration

```json
{
  "Retailers": [
    {
      "name": "Scan",
      "baseUrl": "https://www.scan.co.uk",
      "searchPath": "/shop/gaming/gpu-nvidia-gaming",
      "userAgent": "GPU Price Tracker Bot/1.0"
    },
    {
      "name": "Ebuyer",
      "baseUrl": "https://www.ebuyer.com",
      "searchPath": "/store/Graphics-Cards/cat/CG",
      "userAgent": "GPU Price Tracker Bot/1.0"
    },
    {
      "name": "Amazon",
      "baseUrl": "https://www.amazon.co.uk",
      "searchPath": "/s?k=graphics+card",
      "userAgent": "GPU Price Tracker Bot/1.0"
    }
  ]
}
```

### Rate Limiting

```json
{
  "RateLimiting": {
    "AdminScraperTrigger": {
      "PermitLimit": 1,
      "WindowSeconds": 300
    }
  }
}
```

---

## Monitoring and Logging

### Structured Log Events

All log events must include structured data in the format specified below. Use the application's logging framework (e.g., Serilog, NLog) with structured logging enabled.

**Scraper Job Start**:
```
Level: Information
Message: "Scraper job started"
Properties: { JobId, StartTime, TriggeredBy, Retailers, ForceRefresh }
```

**Per-Retailer Scrape Result**:
```
Level: Information (success) or Error (failure)
Message: "Scraping {Retailer} completed" or "Scraping {Retailer} failed"
Properties: { JobId, Retailer, Status, ListingsFound, Duration, Error }
```

**Scraper Job Completion**:
```
Level: Information
Message: "Scraper job completed"
Properties: { JobId, Status, ModelsUpdated, TotalDuration, ScanStatus, EbuyerStatus, AmazonStatus }
```

**Stale Data Warning**:
```
Level: Warning
Message: "Retailer data is stale and excluded from averages"
Properties: { Retailer, HoursSinceLastScrape, GpuModel }
```

**High Price Variance Warning**:
```
Level: Warning
Message: "High price variance detected"
Properties: { GpuModel, MinPrice, MaxPrice, AvgPrice, Variance, ListingCount }
```

**Outlier Filtered**:
```
Level: Information
Message: "Price outlier filtered from average calculation"
Properties: { GpuModel, Price, Median, StandardDeviations }
```

**Model Lifecycle Change**:
```
Level: Information
Message: "GPU model status changed"
Properties: { GpuModel, OldStatus, NewStatus, LastSeenAt }
```

**Admin Scraper Trigger**:
```
Level: Information
Message: "Manual scraper job triggered by admin"
Properties: { JobId, AdminEmail, Retailers, ForceRefresh, Timestamp }
```

### Alert Conditions

Configure the following alerts in the monitoring system (Application Insights, Datadog, etc.):

1. **Critical Alert**: Scraper job fails 2 consecutive runs
   - Condition: `ScraperLog.status = 'Failure'` for 2 most recent records
   - Severity: High
   - Action: Slack notification to #gpu-tracker-alerts

2. **Warning Alert**: Any retailer data stale >48 hours
   - Condition: `RetailListing.scraped_at < NOW() - INTERVAL '48 hours'` for any retailer
   - Severity: Medium
   - Action: Email to on-call engineer

3. **Critical Alert**: Zero models updated in scrape run
   - Condition: `ScraperLog.records_updated = 0` and `ScraperLog.status = 'Success'`
   - Severity: High
   - Action: Slack notification + page on-call

4. **Info Alert**: Price variance >50% for any model
   - Condition: Log event "High price variance detected" with `Variance > 50`
   - Severity: Low
   - Action: Log aggregation for manual review

5. **Warning Alert**: Admin scraper trigger rate limit exceeded
   - Condition: More than 10 rate limit rejections (429 responses) in 1 hour
   - Severity: Medium
   - Action: Email to admin team (possible abuse or misconfiguration)

---

## Not In This Document

This document does not contain:
- Implementation code (scraper parsing logic, HTTP client configuration, background job setup)
- Database migration scripts (DDL statements are in Data Model section as specification)
- Retailer-specific HTML parsing logic (CSS selectors, JavaScript rendering requirements)
- Test case definitions (see QA spec for test plans)
- Hangfire configuration details (dashboard setup, storage connection strings)
- Monitoring dashboard UI design
- Historical price tracking (future feature, not in v1 scope)
- Email/push notification system for price drop alerts (future feature)
- International retailers or multi-currency support (UK/GBP only in v1)
- Intel Arc GPU tracking (Nvidia and Radeon only in v1)
- User-configurable scraping preferences (fixed daily schedule in v1)