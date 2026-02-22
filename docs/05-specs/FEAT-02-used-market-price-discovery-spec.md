# Used Market Price Discovery — Engineering Spec

**Type**: feature
**Component**: used-market-price-discovery
**Dependencies**: foundation-spec, FEAT-01-retail-price-tracking
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

The Used Market Price Discovery feature tracks average asking prices for used GPUs (16GB+ VRAM) from eBay UK and CEX UK. The system scrapes marketplace listings daily, filters outliers, and calculates reliable average prices to help users identify fair market value for pre-owned graphics cards. This feature integrates with the retail price tracking feature (FEAT-01) to enable value comparison between used and new cards.

**Entities Owned**: `UsedListing`, `UsedPriceAverage`, `ScrapeJob`, `UnmatchedListing`, `OutlierLog`, `InvalidPriceListing`, `NonGbpListing`

**Entities Referenced**: `GpuModel` (from foundation), `RetailPrice` (from FEAT-01)

---

## Data Model

### UsedListing

Individual marketplace listing scraped from a data source. Retained for 7 days, then purged.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| id | UUID | PK, not null | Generated on insert |
| card_model | string(100) | not null | Canonical model name (e.g., "RTX 4060 Ti 16GB") |
| vram_gb | int | not null | VRAM size in GB |
| price | decimal(10,2) | not null, >= 0 | Asking price in GBP |
| source | string(50) | not null | Enum: "eBay", "CEX" |
| listing_url | string(2048) | nullable | Full URL to listing (admin debugging only) |
| scraped_at | datetime | not null | UTC timestamp when listing was scraped |
| is_outlier | boolean | not null, default false | True if filtered as outlier during calculation |
| created_at | datetime | not null, default CURRENT_TIMESTAMP | Record creation timestamp |

**Indexes**:
- `(scraped_at)` for efficient 7-day cleanup queries
- `(card_model, source, scraped_at)` for average calculation grouping

**Relationships**:
- References `GpuModel` via `card_model` (logical reference, no FK)

---

### UsedPriceAverage

Aggregated average price per card model, calculated daily. Historical records retained indefinitely.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| id | UUID | PK, not null | Generated on insert |
| card_model | string(100) | not null | Canonical model name |
| vram_gb | int | not null | VRAM size in GB |
| average_price | decimal(10,2) | not null, >= 0 | Average asking price in GBP after outlier filtering |
| listing_count | int | not null, >= 0 | Number of listings used to calculate average |
| source_breakdown | json | not null | JSON object: `{"eBay": 5, "CEX": 3}` |
| confidence | string(20) | not null | Enum: "low", "medium", "high" |
| calculated_at | datetime | not null | UTC timestamp of calculation |
| created_at | datetime | not null, default CURRENT_TIMESTAMP | Record creation timestamp |

**Indexes**:
- `(card_model, calculated_at)` for historical queries and latest price lookups
- `(calculated_at)` for staleness checks

**Relationships**:
- References `GpuModel` via `card_model` (logical reference, no FK)

---

### ScrapeJob

Metadata for each scraping run (one job per source per day).

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| id | UUID | PK, not null | Generated on insert |
| source | string(50) | not null | Enum: "eBay", "CEX" |
| run_at | datetime | not null | UTC timestamp when job started |
| listings_found | int | not null, >= 0 | Number of listings successfully scraped |
| status | string(50) | not null | Enum: "success", "partial", "failure" |
| error_message | string(2048) | nullable | Error details if status is "partial" or "failure" |
| created_at | datetime | not null, default CURRENT_TIMESTAMP | Record creation timestamp |

**Indexes**:
- `(run_at, source)` for admin dashboard queries
- `(status, run_at)` for monitoring failed jobs

**Relationships**:
- None (standalone metadata)

---

### UnmatchedListing

Listings that failed model identification. Used for manual review to improve model aliases.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| id | UUID | PK, not null | Generated on insert |
| listing_title | string(500) | not null | Raw listing title from marketplace |
| price | decimal(10,2) | not null | Extracted price in GBP |
| source | string(50) | not null | Enum: "eBay", "CEX" |
| scraped_at | datetime | not null | UTC timestamp when listing was scraped |
| created_at | datetime | not null, default CURRENT_TIMESTAMP | Record creation timestamp |

**Indexes**:
- `(scraped_at)` for admin review queries
- `(source, scraped_at)` for source-specific analysis

**Relationships**:
- None (logging table)

---

### OutlierLog

Listings filtered as outliers during average calculation. Used for debugging price anomalies.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| id | UUID | PK, not null | Generated on insert |
| card_model | string(100) | not null | Canonical model name |
| price | decimal(10,2) | not null | Listing price that was filtered |
| median | decimal(10,2) | not null | Median price used for outlier calculation |
| source | string(50) | not null | Enum: "eBay", "CEX" |
| listing_url | string(2048) | nullable | Full URL to listing (admin debugging) |
| logged_at | datetime | not null, default CURRENT_TIMESTAMP | UTC timestamp when outlier was detected |

**Indexes**:
- `(card_model, logged_at)` for admin debugging queries
- `(logged_at)` for periodic cleanup (optional retention policy)

**Relationships**:
- None (logging table)

---

### InvalidPriceListing

Listings discarded due to sanity check failure (price outside £50-£5000 range).

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| id | UUID | PK, not null | Generated on insert |
| listing_title | string(500) | not null | Raw listing title |
| extracted_price | decimal(10,2) | not null | Price that failed validation |
| card_model | string(100) | nullable | Model name if identified before price validation |
| source | string(50) | not null | Enum: "eBay", "CEX" |
| listing_url | string(2048) | nullable | Full URL to listing |
| scraped_at | datetime | not null | UTC timestamp when listing was scraped |
| created_at | datetime | not null, default CURRENT_TIMESTAMP | Record creation timestamp |

**Indexes**:
- `(scraped_at)` for admin review queries
- `(source, scraped_at)` for source-specific scraper debugging

**Relationships**:
- None (logging table)

---

### NonGbpListing

Listings discarded due to non-GBP currency. Used to detect scraper issues or site changes.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| id | UUID | PK, not null | Generated on insert |
| listing_title | string(500) | not null | Raw listing title |
| price_text | string(100) | not null | Raw price text with currency indicator (e.g., "€480") |
| source | string(50) | not null | Enum: "eBay", "CEX" |
| listing_url | string(2048) | nullable | Full URL to listing |
| scraped_at | datetime | not null | UTC timestamp when listing was scraped |
| created_at | datetime | not null, default CURRENT_TIMESTAMP | Record creation timestamp |

**Indexes**:
- `(scraped_at)` for admin review queries
- `(source, scraped_at)` for monitoring non-GBP listing frequency

**Relationships**:
- None (logging table)

---

## API Endpoints

### GET /api/v1/used-prices/{cardModel}

Retrieve average used price for a specific GPU model.

**Auth**: None (public endpoint)
**Authorization**: None

**Path parameters**:
| Parameter | Type | Required | Validation |
|-----------|------|----------|-----------|
| cardModel | string | yes | Must match canonical model name format (URL-encoded) |

**Success response** `200 OK`:
| Field | Type | Notes |
|-------|------|-------|
| card_model | string | Canonical model name |
| is_available | boolean | False if data is >3 days old |
| average_price | decimal | GBP price (null if unavailable) |
| listing_count | int | Number of listings (null if unavailable) |
| confidence | string | Enum: "low", "medium", "high" (null if unavailable) |
| confidence_message | string | Human-readable confidence description (null if unavailable) |
| sources | object | `{"eBay": 5, "CEX": 3}` (null if unavailable) |
| calculated_at | ISO 8601 datetime | UTC timestamp (null if unavailable) |
| staleness_warning | string | Enum: "fresh", "aging", "unavailable" |

**Error responses**:
| Status | Condition |
|--------|-----------|
| 404 | Card model not found in system |
| 400 | Invalid card model format |

**Example responses**:

```json
// Available data (high confidence)
{
  "card_model": "RTX 4060 Ti 16GB",
  "is_available": true,
  "average_price": 480.00,
  "listing_count": 8,
  "confidence": "high",
  "confidence_message": "High confidence - 8 listings",
  "sources": {"eBay": 5, "CEX": 3},
  "calculated_at": "2025-01-10T03:15:00Z",
  "staleness_warning": "fresh"
}

// Low confidence (1-2 listings)
{
  "card_model": "RX 6950 XT 16GB",
  "is_available": true,
  "average_price": 680.00,
  "listing_count": 2,
  "confidence": "low",
  "confidence_message": "Low confidence - only 2 listings found",
  "sources": {"eBay": 1, "CEX": 1},
  "calculated_at": "2025-01-10T03:15:00Z",
  "staleness_warning": "fresh"
}

// Stale data (1-3 days old)
{
  "card_model": "RTX 4070 Ti Super 16GB",
  "is_available": true,
  "average_price": 720.00,
  "listing_count": 6,
  "confidence": "high",
  "confidence_message": "High confidence - 6 listings",
  "sources": {"eBay": 4, "CEX": 2},
  "calculated_at": "2025-01-08T03:15:00Z",
  "staleness_warning": "aging"
}

// Unavailable (>3 days old)
{
  "card_model": "RTX 4080 Super 16GB",
  "is_available": false,
  "average_price": null,
  "listing_count": null,
  "confidence": null,
  "confidence_message": null,
  "sources": null,
  "calculated_at": null,
  "staleness_warning": "unavailable"
}
```

---

### GET /api/v1/used-prices

Retrieve average used prices for all tracked GPU models, optionally filtered by manufacturer.

**Auth**: None (public endpoint)
**Authorization**: None

**Query parameters**:
| Parameter | Type | Required | Validation |
|-----------|------|----------|-----------|
| manufacturer | string | no | Enum: "Nvidia", "AMD" (case-insensitive) |

**Success response** `200 OK`:
Array of `UsedPriceResponse` objects (same schema as single-model endpoint).

**Error responses**:
| Status | Condition |
|--------|-----------|
| 400 | Invalid manufacturer value |

**Example request**:
```
GET /api/v1/used-prices?manufacturer=Nvidia
```

**Example response**:
```json
[
  {
    "card_model": "RTX 4090 24GB",
    "is_available": true,
    "average_price": 1420.00,
    "listing_count": 12,
    "confidence": "high",
    "confidence_message": "High confidence - 12 listings",
    "sources": {"eBay": 8, "CEX": 4},
    "calculated_at": "2025-01-10T03:15:00Z",
    "staleness_warning": "fresh"
  },
  {
    "card_model": "RTX 4060 Ti 16GB",
    "is_available": true,
    "average_price": 480.00,
    "listing_count": 8,
    "confidence": "high",
    "confidence_message": "High confidence - 8 listings",
    "sources": {"eBay": 5, "CEX": 3},
    "calculated_at": "2025-01-10T03:15:00Z",
    "staleness_warning": "fresh"
  }
]
```

---

### POST /admin/used-market/scrape

Manually trigger an immediate used market scrape across all sources.

**Auth**: Required (Bearer JWT)
**Authorization**: Admin role required

**Request body**: None

**Success response** `202 Accepted`:
| Field | Type | Notes |
|-------|------|-------|
| job_id | UUID | Hangfire job ID for tracking |
| message | string | "Scrape job enqueued successfully" |
| estimated_completion | ISO 8601 datetime | Estimated completion time (current time + 10 minutes) |

**Error responses**:
| Status | Condition |
|--------|-----------|
| 401 | Not authenticated |
| 403 | Not authorized (not Admin role) |
| 409 | Scrape job already in progress |

**Example response**:
```json
{
  "job_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "message": "Scrape job enqueued successfully",
  "estimated_completion": "2025-01-10T14:25:00Z"
}
```

---

### GET /admin/used-market/status

Retrieve current scraping status and recent job history.

**Auth**: Required (Bearer JWT)
**Authorization**: Admin role required

**Success response** `200 OK`:
| Field | Type | Notes |
|-------|------|-------|
| last_scrape_time | ISO 8601 datetime | UTC timestamp of most recent completed scrape |
| status | string | Enum: "success", "partial", "failure" |
| listings_found | object | `{"eBay": 142, "CEX": 38}` |
| next_scheduled | ISO 8601 datetime | UTC timestamp of next scheduled daily scrape |
| is_job_running | boolean | True if scrape currently in progress |
| recent_jobs | array | Last 10 scrape jobs (see schema below) |

**Recent job schema**:
| Field | Type | Notes |
|-------|------|-------|
| job_id | UUID | Hangfire job ID |
| source | string | Enum: "eBay", "CEX" |
| run_at | ISO 8601 datetime | UTC timestamp when job started |
| listings_found | int | Number of listings scraped |
| status | string | Enum: "success", "partial", "failure" |
| error_message | string | Error details (null if success) |

**Error responses**:
| Status | Condition |
|--------|-----------|
| 401 | Not authenticated |
| 403 | Not authorized (not Admin role) |

**Example response**:
```json
{
  "last_scrape_time": "2025-01-10T03:15:00Z",
  "status": "success",
  "listings_found": {"eBay": 142, "CEX": 38},
  "next_scheduled": "2025-01-11T03:00:00Z",
  "is_job_running": false,
  "recent_jobs": [
    {
      "job_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "source": "eBay",
      "run_at": "2025-01-10T03:00:00Z",
      "listings_found": 142,
      "status": "success",
      "error_message": null
    },
    {
      "job_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
      "source": "CEX",
      "run_at": "2025-01-10T03:05:00Z",
      "listings_found": 38,
      "status": "success",
      "error_message": null
    }
  ]
}
```

---

### GET /admin/used-listings/{id}

Retrieve detailed information for a specific used listing (debugging only).

**Auth**: Required (Bearer JWT)
**Authorization**: Admin role required

**Path parameters**:
| Parameter | Type | Required | Validation |
|-----------|------|----------|-----------|
| id | UUID | yes | Valid UUID format |

**Success response** `200 OK`:
| Field | Type | Notes |
|-------|------|-------|
| id | UUID | Listing ID |
| card_model | string | Canonical model name |
| vram_gb | int | VRAM size in GB |
| price | decimal | Asking price in GBP |
| source | string | Enum: "eBay", "CEX" |
| listing_url | string | Full URL to listing |
| scraped_at | ISO 8601 datetime | UTC timestamp when scraped |
| is_outlier | boolean | True if filtered as outlier |
| created_at | ISO 8601 datetime | Record creation timestamp |

**Error responses**:
| Status | Condition |
|--------|-----------|
| 401 | Not authenticated |
| 403 | Not authorized (not Admin role) |
| 404 | Listing ID not found |

**Example response**:
```json
{
  "id": "c3d4e5f6-a7b8-9012-cdef-123456789012",
  "card_model": "RTX 4060 Ti 16GB",
  "vram_gb": 16,
  "price": 480.00,
  "source": "eBay",
  "listing_url": "https://www.ebay.co.uk/itm/123456789012",
  "scraped_at": "2025-01-10T03:05:00Z",
  "is_outlier": false,
  "created_at": "2025-01-10T03:05:12Z"
}
```

---

## Business Rules

1. **Target card scope**: Only scrape used prices for GPU models that have valid retail price data (from FEAT-01) updated within the past 7 days, have VRAM >= 16GB, and are from previous 2-3 generations (not latest generation).

2. **Currency validation**: All prices must be in GBP. Discard any listings with non-GBP currency indicators (€, $, USD, EUR). Log discarded listings to `NonGbpListing` table.

3. **Price sanity bounds**: Discard any listings with prices outside the range £50-£5000. Log discarded listings to `InvalidPriceListing` table.

4. **Model identification**: Match listing titles against canonical model names and aliases defined in `gpu-models.json`. Listings that cannot be matched to a known model are logged to `UnmatchedListing` table and excluded from averages.

5. **VRAM validation**: If a listing specifies VRAM size, it must match the canonical model's VRAM specification. Discard listings with VRAM mismatches (trust model spec over listing text).

6. **VRAM variants as separate models**: Cards with multiple VRAM SKUs (e.g., RTX 4060 Ti 8GB vs 16GB) are treated as distinct models. Never aggregate prices across different VRAM variants.

7. **Outlier filtering**: After grouping listings by model, calculate median price. Remove listings priced >2x or <0.5x the median. Log removed outliers to `OutlierLog` table.

8. **Average calculation**: Calculate average price from remaining listings after outlier filtering. If all listings are filtered as outliers, do not store a `UsedPriceAverage` record for that model.

9. **Confidence levels**: Assign confidence level based on listing count: Low (1-2 listings), Medium (3-5 listings), High (6+ listings).

10. **Source breakdown**: Store per-source listing counts in `source_breakdown` JSON field (e.g., `{"eBay": 5, "CEX": 3}`).

11. **Data freshness**: Used price data is considered stale if >3 days old. Public API returns `is_available: false` and null price fields for stale data.

12. **Staleness warnings**: API includes `staleness_warning` field: "fresh" (<24 hours), "aging" (1-3 days), "unavailable" (>3 days).

13. **Data retention**: Individual `UsedListing` records are purged after 7 days. `UsedPriceAverage` historical records are retained indefinitely.

14. **Scraping schedule**: Daily scrape runs at 3:00 AM UTC via Hangfire recurring job. No automatic retries on failure.

15. **Manual trigger concurrency**: Prevent concurrent scrape jobs. If admin triggers manual scrape while another job is in progress, return 409 Conflict error.

16. **Partial source failure**: If one source fails (e.g., CEX down) but another succeeds (eBay), store partial results. Calculate averages from available source only. Log failure and alert ops team.

17. **Complete source failure**: If both sources fail, retain previous day's data. Do not overwrite existing `UsedPriceAverage` records. Log critical failure and alert ops team immediately.

18. **eBay API rate limiting**: Respect eBay's 5,000 calls/day limit. With ~50 target models, daily scrape uses ~50 calls. If rate limit is hit, complete scrape with available data and alert ops team.

19. **CEX rate limiting**: Enforce minimum 3-second delay between CEX scrape requests to respect their servers and reduce blocking risk.

20. **Robots.txt compliance**: Before scraping CEX, verify that the search URL path is not disallowed in `/robots.txt`. If disallowed, skip CEX scrape and alert ops team.

21. **URL storage**: Store listing URLs in `UsedListing.listing_url` field for admin debugging only. Never expose URLs via public API endpoints.

22. **Duplicate listings**: No de-duplication logic for cross-posted listings (same seller on eBay and CEX). Accept potential double-counting in v1.

23. **Model lookup loading**: Load `gpu-models.json` file at service startup as singleton. Parse JSON into in-memory dictionary for fast lookups during scraping.

24. **Model alias matching**: Use case-insensitive substring matching for model aliases. If multiple aliases match a listing title, prefer the most specific (longest) match.

---

## Validation Rules

### Listing Extraction Validation

| Field | Rule | Action |
|-------|------|--------|
| price | Must be numeric decimal | Discard listing, log to `InvalidPriceListing` |
| price | Must be between £50 and £5000 | Discard listing, log to `InvalidPriceListing` |
| currency | Must contain "£" or "GBP" indicator | Discard listing, log to `NonGbpListing` |
| currency | Must not contain "€", "$", "USD", "EUR" | Discard listing, log to `NonGbpListing` |
| listing_title | Must not be empty | Discard listing, log warning |
| card_model | Must match known model in `gpu-models.json` | Discard listing, log to `UnmatchedListing` |
| vram_gb | If extracted, must match model spec | Discard listing, log to `UnmatchedListing` |

### API Request Validation

| Field | Rule | Error message |
|-------|------|---------------|
| cardModel (path param) | Required, max 100 chars | "Invalid card model format" |
| manufacturer (query param) | Optional, enum: "Nvidia", "AMD" | "Invalid manufacturer value. Must be 'Nvidia' or 'AMD'" |

### Admin Endpoint Validation

| Action | Rule | Error message |
|--------|------|---------------|
| Manual scrape trigger | No concurrent job in progress | "Scrape job already in progress. Wait for completion before triggering another." |

---

## Authorization

| Action | Required policy | Notes |
|--------|----------------|-------|
| GET /api/v1/used-prices/{cardModel} | None (public) | Read-only data, no authentication required |
| GET /api/v1/used-prices | None (public) | Read-only data, no authentication required |
| POST /admin/used-market/scrape | Authenticated + Admin role | Manual scrape trigger |
| GET /admin/used-market/status | Authenticated + Admin role | Scrape job monitoring |
| GET /admin/used-listings/{id} | Authenticated + Admin role | Listing detail debugging |

**Note**: Admin role is defined in foundation spec. Verify role membership via JWT claims.

---

## Acceptance Criteria

- [ ] Daily scrape job runs at 3:00 AM UTC via Hangfire recurring job
- [ ] eBay API integration scrapes listings using official Finding API with OAuth 2.0 authentication
- [ ] CEX web scraping extracts listings from search results with 3-second rate limiting
- [ ] Listings outside £50-£5000 price range are discarded and logged to `InvalidPriceListing`
- [ ] Non-GBP listings are discarded and logged to `NonGbpListing`
- [ ] Listings are matched against `gpu-models.json` canonical model names and aliases
- [ ] Unmatched listings are logged to `UnmatchedListing` table for manual review
- [ ] VRAM variants (e.g., RTX 4060 Ti 8GB vs 16GB) are treated as separate models
- [ ] Outlier filtering removes listings >2x or <0.5x median price per model
- [ ] Removed outliers are logged to `OutlierLog` table with median reference
- [ ] Average price is calculated from filtered listings and stored in `UsedPriceAverage`
- [ ] Source breakdown JSON field stores per-source listing counts (e.g., `{"eBay": 5, "CEX": 3}`)
- [ ] Confidence level is assigned based on listing count: Low (1-2), Medium (3-5), High (6+)
- [ ] Data is considered stale if >3 days old, and public API returns `is_available: false`
- [ ] Staleness warning indicates "fresh" (<24h), "aging" (1-3d), or "unavailable" (>3d)
- [ ] Individual `UsedListing` records are purged after 7 days via scheduled cleanup job
- [ ] Historical `UsedPriceAverage` records are retained indefinitely (no purge)
- [ ] Manual scrape trigger returns 409 Conflict if job already in progress
- [ ] Single source failure (e.g., CEX down) results in partial data storage with eBay-only averages
- [ ] Complete source failure retains previous day's data without overwriting
- [ ] eBay API rate limit (5,000 calls/day) is not exceeded during daily scrape
- [ ] CEX scraping enforces 3-second minimum delay between requests
- [ ] Robots.txt compliance check prevents CEX scraping if search path is disallowed
- [ ] Listing URLs are stored in database but never exposed via public API
- [ ] Admin endpoints require authentication and Admin role authorization
- [ ] Public API endpoints return 200 OK with used price data for available models
- [ ] Public API endpoints return 404 Not Found for unknown card models
- [ ] Public API caches responses in Redis with 1-hour TTL
- [ ] Cache is invalidated on scrape completion (all `used-prices:*` keys cleared)
- [ ] Target card scope is dynamically determined by querying FEAT-01 retail price data
- [ ] Only cards with retail price updated within 7 days, VRAM >= 16GB, and non-latest generation are scraped

---

## Security Requirements

- **Authentication**: Admin endpoints require valid JWT bearer token with Admin role claim. Validate token signature and expiration on every request.
- **Authorization**: Public API endpoints have no authorization (read-only public data). Admin endpoints enforce role-based access control.
- **Sensitive data exposure**: Listing URLs are stored in database but never exposed via public API responses. Only admin endpoints return URLs, behind authentication.
- **External API credentials**: eBay API credentials (OAuth 2.0 application token) must be stored in environment variables or secure key vault. Never hardcode in source code.
- **Rate limiting**: No rate limiting on public API endpoints for v1 (can add later if abuse detected). Admin manual scrape trigger inherently rate-limited by concurrency prevention.
- **Input validation**: Validate all API input parameters to prevent injection attacks. Use parameterized queries for all database operations (EF Core handles this by default).
- **Logging**: Log scraping errors and anomalies (outliers, invalid prices, unmatched models) for security monitoring. Do not log listing URLs in application logs (only in database tables).
- **HTTPS**: All API endpoints must be served over HTTPS in production. HTTP traffic should redirect to HTTPS.
- **CORS**: Configure CORS policy to allow frontend domain only. No wildcard (*) origin allowed.
- **Error handling**: Never expose stack traces or internal error details in API error responses. Use generic error messages for 500 Internal Server Error.
- **Dependencies**: Keep eBay SDK, AngleSharp/HtmlAgilityPack, and all NuGet packages up-to-date with security patches.
- **Scraping user-agent**: Identify scraper as bot with transparent user-agent string (e.g., "GPUValueTracker/1.0 (contact@yoursite.com)"). Do not impersonate human browsers.

---

## Not In This Document

This document does not contain:
- Implementation code (C#, TypeScript, SQL migrations) — write the code yourself based on contracts above
- Test case definitions — see QA spec for test plans
- eBay API OAuth 2.0 flow implementation details — consult eBay Developer documentation
- CEX HTML parsing selectors — determine correct DOM elements during implementation
- Hangfire dashboard configuration — use standard Hangfire setup from foundation spec
- Redis cache invalidation strategy beyond spec — implement cache-aside pattern with 1-hour TTL
- Monitoring alert configuration (Slack webhooks, Application Insights metrics) — configure in infrastructure
- GPU model JSON file seeding — manually create initial `gpu-models.json` from TechPowerUp database
- Email notification feature for price drops — future feature, not in v1
- Historical price trend graphs — future feature, not in v1 (data is stored to enable v2)
- Facebook Marketplace scraping — explicitly excluded from v1 due to ToS compliance concerns
- Currency conversion for non-GBP listings — explicitly excluded from v1 (discard non-GBP)
- Duplicate listing de-duplication — explicitly excluded from v1 (accept potential double-counting)
- Auction listing support — explicitly excluded from v1 (eBay Buy It Now only)
- Regional price breakdown (London vs Manchester) — explicitly excluded from v1 (aggregate all UK)
- Warranty tracking — explicitly excluded from v1
- Seller reputation tracking — explicitly excluded from v1
- Shipping cost inclusion — explicitly excluded from v1 (asking price only)