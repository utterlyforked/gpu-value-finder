# Live Retail Price Aggregation - Technical Review (Iteration 2)

**Status**: ✅ READY FOR IMPLEMENTATION
**Iteration**: 2
**Date**: 2025-01-12

---

## Summary

This feature specification is sufficiently detailed to proceed with implementation. All critical questions from iteration 1 have been answered clearly and comprehensively. The PRD now includes:

- Complete data model with schema definitions
- Clear business logic for price calculations and lifecycle management
- Well-defined API contracts with all response scenarios
- Explicit handling of edge cases (cold start, scraper failures, stale data)
- Monitoring and operational requirements
- Security considerations (admin-only manual triggers)

The specification provides enough detail for an engineer to write a technical implementation spec and begin development.

---

## What's Clear

### Data Model

- **Three-table architecture**: `RetailListings` (individual prices), `RetailPrices` (aggregates), `ScraperLogs` (execution history)
- **GPU model whitelist**: Hardcoded list of 7 eligible models (RTX 4090, 4080, 4080 Super, 4070 Ti Super, RX 7900 XTX, 7900 XT, 7800 XT)
- **Price variance tracking**: Min/Avg/Max prices per model with listing count metadata
- **Lifecycle states**: Active → Inactive (14 days) → Archived (30 days) with `LastSeenAt` timestamp
- **Currency handling**: Explicit GBP storage and API exposure
- **Indexes defined**: Composite indexes on `(GpuModel, ScrapedAt)`, `Manufacturer`, `Status`

### Business Logic

- **Freshness policy**: Exclude retailer data >24 hours old from average calculations
- **Outlier filtering**: Only when 4+ listings exist; statistical filtering with 2σ threshold
- **Stock handling**: Only in-stock items contribute to averages; out-of-stock items retain last price with indicator
- **Normalization rules**: Strip AIB partner names (ASUS, MSI, Gigabyte) to match whitelist reference models
- **Retry strategy**: 3 attempts per retailer with exponential backoff (5s, 10s delays)
- **Timeout configuration**: 30s per request, 5min total per retailer with override capability

### API Design

- **Endpoint**: `GET /api/v1/retail-prices?manufacturer={nvidia|radeon}`
- **Consistent 200 OK**: Status metadata differentiates cold_start, success, scraper_failure, partial_failure
- **Response includes**:
  - Per-model pricing (min/avg/max with variance percentage)
  - Listing counts (total and in-stock)
  - Per-retailer status (success/failed with last scraped timestamp and errors)
  - Data freshness indicators (current/stale/very_stale/unavailable)
  - Explicit currency field (`"currency": "GBP"`)
- **Admin endpoint**: `POST /api/v1/admin/scraper/trigger` with JWT admin role protection
- **Status endpoint**: `GET /api/v1/admin/scraper/status/{jobId}` for manual trigger monitoring

### Authorization

- **Public API**: `/api/v1/retail-prices` - no authentication required (read-only public data)
- **Admin API**: `/api/v1/admin/scraper/trigger` - requires JWT with `Admin` role claim
- **Rate limiting**: Admin trigger endpoint limited to 1 request per 5 minutes per user
- **Audit logging**: All manual scraper triggers logged with user identity and timestamp

### Validation

- **Price values**: DECIMAL(10,2) with positive value constraint
- **GPU model**: Must exist in whitelist configuration
- **Manufacturer**: Enum constraint ("Nvidia" or "Radeon")
- **VRAM size**: Integer, positive value (16GB minimum enforced by whitelist)
- **Product URLs**: TEXT field, validated as URL format
- **Timestamps**: NOT NULL for critical fields (ScrapedAt, LastUpdated)

### Edge Cases Addressed

1. **Cold start**: API returns `status: "cold_start"` with helpful message, no errors
2. **All scrapers fail**: Return last known data with `status: "scraper_failure"` and staleness warning
3. **Single retailer fails**: Partial failure status, calculate averages from successful retailers only
4. **Model disappears temporarily**: 14-day grace period before marking inactive
5. **Model permanently discontinued**: 30-day archive period, excluded from API by default
6. **Out of stock**: Preserve last price, set `inStock: false`, show `lastSeenDaysAgo`
7. **High price variance**: Log warning when spread >25% (2-3 listings) or >50% (4+ listings with outlier filtering)
8. **Stale retailer data**: Automatically exclude from averages after 24h, alert monitoring
9. **Rate limiting/CAPTCHA**: Graceful failure, log error, continue with other retailers
10. **Concurrent scrapes**: Hangfire prevents duplicate jobs via job deduplication
11. **Scraper timeout**: Per-request (30s) and per-retailer (5min) limits with configurable overrides
12. **New GPU launch**: Admin updates whitelist config, triggers manual scrape, data populates immediately

### Operational Requirements

- **Scheduled execution**: Daily at 2 AM UK time via Hangfire recurring job
- **Manual trigger**: Admin-only endpoint for on-demand scraping
- **Structured logging**: All events logged with context (JobId, Retailer, Status, Duration, Error)
- **Alerting rules**:
  - 2 consecutive scraper failures → High severity Slack alert
  - Retailer data stale >48h → Medium severity email
  - Zero models updated → High severity page on-call
  - Price variance >50% → Low severity log for review
- **Monitoring metrics**:
  - Scrape success rate (per day, per retailer)
  - Average duration (per retailer, overall)
  - Listings found per retailer (trend detection)
  - API response times
  - Error rates (4xx/5xx)

---

## Implementation Notes

### Database

**Schema created per specification**:
- `RetailListings`: Individual scraper results with GpuModel, Manufacturer, VramSizeGB, Retailer, Price, IsInStock, ProductUrl, ScrapedAt
- `RetailPrices`: Aggregated data with Min/Avg/Max prices, ListingCount, InStockCount, Status (Active/Inactive/Archived), LastScrapedAt
- `ScraperLogs`: Execution history with per-retailer status tracking and error messages

**Indexes required**:
```sql
CREATE INDEX idx_model_scrape ON RetailListings (GpuModel, ScrapedAt DESC);
CREATE INDEX idx_manufacturer ON RetailListings (Manufacturer);
CREATE INDEX idx_manufacturer ON RetailPrices (Manufacturer);
CREATE INDEX idx_status ON RetailPrices (Status);
CREATE INDEX idx_started ON ScraperLogs (StartedAt DESC);
```

**Constraints**:
- UNIQUE constraint on `RetailPrices.GpuModel`
- Check constraint: `Price > 0`
- Foreign key not needed (whitelist is configuration-based, not relational)

### Configuration

**GPU whitelist** (appsettings.json or database table):
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
  },
  "ScraperSettings": {
    "RequestTimeoutSeconds": 30,
    "RetailerTotalTimeoutMinutes": 5,
    "MaxRetryAttempts": 3,
    "RetryDelaySeconds": 5,
    "ScheduledExecutionTime": "02:00",
    "RetailerTimeoutOverrides": {}
  },
  "Retailers": [
    { "name": "Scan", "baseUrl": "https://www.scan.co.uk" },
    { "name": "Ebuyer", "baseUrl": "https://www.ebuyer.com" },
    { "name": "Amazon", "baseUrl": "https://www.amazon.co.uk" }
  ]
}
```

### Scraper Architecture

**Workflow**:
1. Hangfire triggers `RetailPriceScraperJob.Execute()` at 2 AM daily
2. Job spawns parallel tasks for each retailer (Scan, Ebuyer, Amazon)
3. Each retailer scraper:
   - Fetches GPU product pages (search or category listing)
   - Parses HTML to extract: product title, price, stock status, URL
   - Normalizes title to reference model (strip "ASUS ROG Strix", keep "RTX 4090")
   - Checks whitelist for match
   - UPSERT to `RetailListings` table
4. After all retailers complete/fail:
   - Query fresh listings (ScrapedAt > NOW() - 24h, IsInStock = true)
   - Group by GpuModel, calculate Min/Avg/Max
   - Apply outlier filtering (if 4+ listings)
   - Update `RetailPrices` table
5. Run lifecycle cleanup job:
   - Mark models Inactive if LastSeenAt > 14 days
   - Mark models Archived if LastSeenAt > 30 days
6. Write to `ScraperLogs` table with status summary

**Error handling**:
- Individual retailer failure: Log error, continue with others (partial success)
- All retailers fail: Log critical error, alert, preserve last known data
- Timeout: Cancel task, log timeout error, retry with backoff
- HTTP errors: Log status code and response, don't retry 4xx (bad URL), retry 5xx

### API Implementation

**Controller structure**:
```csharp
[ApiController]
[Route("api/v1/retail-prices")]
public class RetailPricesController : ControllerBase
{
    [HttpGet]
    public async Task<ActionResult<RetailPriceResponse>> GetPrices(
        [FromQuery] string manufacturer) // "nvidia" or "radeon"
    {
        // Query RetailPrices where Manufacturer = manufacturer
        // Query RetailListings for per-retailer status
        // Build response with status metadata
        return Ok(response);
    }
}

[ApiController]
[Route("api/v1/admin/scraper")]
[Authorize(Roles = "Admin")]
public class ScraperAdminController : ControllerBase
{
    [HttpPost("trigger")]
    public async Task<ActionResult<TriggerResponse>> TriggerScrape(
        [FromBody] TriggerRequest request)
    {
        // Enqueue Hangfire job
        var jobId = BackgroundJob.Enqueue<RetailPriceScraperJob>(
            x => x.Execute(request.Retailers, request.ForceRefresh));
        return Ok(new { jobId, status = "queued" });
    }

    [HttpGet("status/{jobId}")]
    public async Task<ActionResult<JobStatus>> GetJobStatus(string jobId)
    {
        // Query Hangfire job state
        return Ok(status);
    }
}
```

**Response mapping**:
- Query `RetailPrices` for models (filter by Status: Active/Inactive only)
- Query `ScraperLogs` for most recent execution
- Determine `status` field: 
  - If no logs exist: "cold_start"
  - If most recent log shows all retailers failed: "scraper_failure"
  - If some failed: "partial_failure"
  - If all succeeded: "success"
- Determine `dataFreshness`:
  - LastScrapedAt < 24h: "current"
  - 24-48h: "stale"
  - >48h: "very_stale"
  - null: "unavailable"

### Background Jobs

**Hangfire configuration**:
```csharp
// Startup.cs
services.AddHangfire(config =>
    config.UsePostgreSqlStorage(connectionString));

// Recurring job
RecurringJob.AddOrUpdate<RetailPriceScraperJob>(
    "retail-price-scraper",
    job => job.Execute(null, false),
    "0 2 * * *", // 2 AM daily
    TimeZoneInfo.FindSystemTimeZoneById("GMT Standard Time"));

// Cleanup job (runs after scraper)
RecurringJob.AddOrUpdate<ModelLifecycleJob>(
    "model-lifecycle-cleanup",
    job => job.Execute(),
    "0 3 * * *", // 3 AM daily
    TimeZoneInfo.FindSystemTimeZoneById("GMT Standard Time"));
```

**Job implementation skeleton**:
```csharp
public class RetailPriceScraperJob
{
    public async Task Execute(List<string> retailers = null, bool forceRefresh = false)
    {
        var jobId = Guid.NewGuid();
        _logger.LogInformation("Scraper job {JobId} started", jobId);

        var results = await Task.WhenAll(
            ScrapeScan(),
            ScrapeEbuyer(),
            ScrapeAmazon()
        );

        // Process results, update database
        await CalculateAggregates();
        await LogExecution(jobId, results);
    }
}
```

### Security

- **JWT validation**: Use ASP.NET Core `[Authorize(Roles = "Admin")]` attribute
- **Rate limiting**: Custom middleware or AspNetCoreRateLimit library (1 req/5min per admin)
- **Audit logging**: Structured log with `ClaimsPrincipal.Identity.Name` for admin actions
- **HTTPS only**: Enforce via HSTS header
- **CORS**: Allow dashboard origin only, no wildcard

### Testing Strategy

**Unit tests**:
- Price calculation logic (min/avg/max with various listing counts)
- Outlier filtering (ensure 4+ threshold, verify 2σ exclusion)
- Product name normalization (strip AIB brands correctly)
- Whitelist matching (case-insensitive, handles variants like "RTX 4080 SUPER")

**Integration tests**:
- Database CRUD operations (listings, prices, logs)
- Hangfire job execution (mock scrapers, verify DB updates)
- API responses (verify status metadata for all scenarios)

**E2E tests** (Playwright):
- Mock scraper HTML responses
- Trigger job, poll API until complete
- Verify dashboard displays correct prices

---

## Key Decisions Locked In

1. **Whitelist approach**: Hardcoded list of 7 models in configuration, updated manually on new launches
2. **Dual storage**: Individual listings + aggregates for transparency and debugging
3. **24-hour freshness**: Stale retailer data excluded from averages automatically
4. **Min/Avg/Max tracking**: Essential for user value comparison use case
5. **200 OK everywhere**: Consistent API responses with status metadata instead of HTTP error codes
6. **Lifecycle stages**: 14-day inactive grace period, 30-day archive
7. **Manual trigger**: Admin-only endpoint for operational flexibility
8. **Log-based monitoring**: No dedicated health dashboard in v1, rely on structured logs + alerts

---

## Recommended Next Steps

1. **Create engineering specification** with:
   - Detailed class/interface definitions
   - Scraper implementation details (HTML selectors, parsing logic)
   - Database migration scripts
   - Hangfire job registration code
   - API controller implementation
   - Unit test structure

2. **Set up development environment**:
   - PostgreSQL database with migrations
   - Hangfire dashboard for job monitoring
   - Application Insights or Seq for structured logging
   - Redis for caching (future use)

3. **Implement in phases**:
   - Phase 1: Database schema + whitelist configuration
   - Phase 2: Single retailer scraper (Scan) + price calculation
   - Phase 3: Remaining retailers (Ebuyer, Amazon) + parallel execution
   - Phase 4: API endpoints (public + admin)
   - Phase 5: Lifecycle cleanup job + monitoring alerts
   - Phase 6: Integration and E2E testing

4. **Create runbook** for:
   - Manual scraper trigger procedure
   - Investigating scraper failures
   - Updating whitelist when new GPUs launch
   - Interpreting monitoring alerts

---

**This feature is ready for detailed engineering specification and implementation.**