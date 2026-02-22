# Live Retail Price Aggregation - Product Requirements (v1.1)

**Version History**:
- v1.0 - Initial specification
- v1.1 - Iteration 1 clarifications (added: GPU classification strategy, data storage model, lifecycle handling, price variance tracking, API contract details, scraper resilience, monitoring approach)

---

## Feature Overview

Live Retail Price Aggregation is the foundation feature that establishes baseline "new GPU" pricing by scraping and averaging current retail prices from major UK retailers (Scan, Ebuyer, Amazon UK). This feature focuses exclusively on latest-generation GPUs with 16GB+ VRAM, tracking only in-stock items to provide accurate market pricing.

This feature is critical because it creates the reference point against which used market prices are compared. Without accurate retail baseline data, the value visualization cannot identify where used cards offer genuine savings or where new cards are competitively priced.

The feature runs automated daily scraping jobs, calculates per-model average prices, and exposes this data through an API that the dashboard consumes. It handles the complexities of web scraping (rate limiting, HTML parsing, anti-scraping measures) and ensures data freshness by timestamping all price information.

---

## User Stories

- As a PC builder, I want to see the current average retail price for the latest Radeon cards so that I know what buying new would cost
- As a PC builder, I want to see the current average retail price for the latest Nvidia cards so that I can establish a price baseline for value comparison
- As a PC builder, I want prices updated regularly so that I'm working with current market data, not stale pricing
- As a PC builder, I want to see the price range (cheapest to most expensive) for each GPU model so I understand my purchasing options
- As a PC builder, I want to know when price data was last updated so I can trust its accuracy

---

## Acceptance Criteria (UPDATED v1.1)

- System scrapes prices from Scan, Ebuyer, and Amazon UK for latest-generation cards (16GB+ VRAM only)
- **GPU models are identified via hardcoded whitelist of eligible models (RTX 4090, RTX 4080, RX 7900 XTX, etc.)**
- **Individual retailer listings are stored in database alongside calculated averages**
- **Minimum, average, and maximum prices are tracked per GPU model**
- Prices are refreshed at least once every 24 hours
- Only cards currently in stock are included in average calculation
- **Retailer data older than 24 hours is excluded from average calculation**
- Price data includes timestamp of last successful scrape
- Retail prices are separated by manufacturer (Radeon/Nvidia) and never mixed
- Scraping jobs handle failures gracefully and retry failed sources
- **Models not found in scrapes for 14+ days are marked inactive; archived after 30 days**
- **Out-of-stock cards retain last known price with "Out of Stock" indicator and last-seen timestamp**
- Price data is persisted and queryable via API endpoint
- **API returns status metadata indicating data freshness and scraper health**
- **Currency (GBP) is explicitly included in API responses**
- **Admin users can manually trigger scrape jobs on-demand for testing/recovery**

---

## Detailed Specifications (UPDATED v1.1)

### GPU Model Classification

**Decision**: Use hardcoded whitelist of eligible GPU models

**Rationale**: Retailer product titles inconsistently include VRAM specifications (e.g., "RTX 4070 Ti" doesn't mention it's 12GB and ineligible). Attempting automatic VRAM detection from product text is unreliable and risks including cards that don't meet our 16GB+ requirement. A hardcoded whitelist provides 100% accuracy and is practical given the small number of latest-gen 16GB+ models (approximately 6-8 models across both manufacturers). New GPU launches are infrequent (every 6-12 months), making manual updates manageable for v1.

**Implementation**:
- Configuration file or database table: `EligibleGpuModels`
- **Nvidia whitelist (RTX 4000 series, 16GB+ only)**:
  - RTX 4090 (24GB)
  - RTX 4080 (16GB)
  - RTX 4080 Super (16GB)
  - RTX 4070 Ti Super (16GB)
- **Radeon whitelist (RX 7000 series, 16GB+ only)**:
  - RX 7900 XTX (24GB)
  - RX 7900 XT (20GB)
  - RX 7800 XT (16GB)

**Behavior**:
- Scrapers parse product titles and normalize to reference model names (remove "ASUS", "MSI", etc.)
- Normalized name is checked against whitelist
- If match found: continue processing and store listing
- If no match: discard listing (log for monitoring—may indicate new model launch)
- When new eligible models launch (e.g., RTX 4090 Ti), developer updates whitelist configuration

**Future Enhancement (v2)**: Auto-detection via specification page scraping or GPU database API can be added once whitelist proves stable

---

### Data Storage Model

**Decision**: Store both individual retailer listings AND calculated aggregates

**Rationale**: While storing only aggregated prices is simpler, preserving individual listings provides critical capabilities:
1. **Transparency**: Users can see actual price range, not just average (min/avg/max)
2. **Debugging**: When average seems wrong, we can audit which retailer contributed what price
3. **Future features**: Price comparison, "best deal" indicators, and historical trend analysis all require individual listings
4. **Data quality**: Can identify which retailer has stale data or outlier pricing

Storage cost is negligible (3 retailers × 8 models = 24 rows per scrape run), and querying performance is not a concern at this scale.

**Database Schema**:

```sql
-- Individual listings from each retailer
CREATE TABLE RetailListings (
    Id SERIAL PRIMARY KEY,
    GpuModel VARCHAR(50) NOT NULL,           -- e.g., "RTX 4090"
    Manufacturer VARCHAR(20) NOT NULL,       -- "Nvidia" or "Radeon"
    VramSizeGB INT NOT NULL,                 -- e.g., 24
    Retailer VARCHAR(50) NOT NULL,           -- "Scan", "Ebuyer", "Amazon"
    Price DECIMAL(10,2) NOT NULL,            -- e.g., 1599.99
    IsInStock BOOLEAN NOT NULL,
    ProductUrl TEXT,                         -- Link to retailer product page
    ScrapedAt TIMESTAMP NOT NULL,
    
    INDEX idx_model_scrape (GpuModel, ScrapedAt DESC),
    INDEX idx_manufacturer (Manufacturer)
);

-- Aggregated pricing calculated from listings
CREATE TABLE RetailPrices (
    Id SERIAL PRIMARY KEY,
    GpuModel VARCHAR(50) NOT NULL UNIQUE,    -- One row per model
    Manufacturer VARCHAR(20) NOT NULL,
    VramSizeGB INT NOT NULL,
    MinPrice DECIMAL(10,2) NOT NULL,         -- Cheapest listing found
    AvgPrice DECIMAL(10,2) NOT NULL,         -- Average of in-stock listings
    MaxPrice DECIMAL(10,2) NOT NULL,         -- Most expensive listing found
    ListingCount INT NOT NULL,               -- How many listings contributed
    InStockCount INT NOT NULL,               -- How many are in stock
    IsInStock BOOLEAN NOT NULL,              -- True if any retailer has stock
    LastScrapedAt TIMESTAMP NOT NULL,        -- Last successful scrape for this model
    Status VARCHAR(20) NOT NULL,             -- "Active", "Inactive", "Archived"
    
    INDEX idx_manufacturer (Manufacturer),
    INDEX idx_status (Status)
);

-- Scraper execution logs
CREATE TABLE ScraperLogs (
    Id SERIAL PRIMARY KEY,
    StartedAt TIMESTAMP NOT NULL,
    CompletedAt TIMESTAMP,
    Status VARCHAR(20) NOT NULL,             -- "Success", "PartialFailure", "Failure"
    ScanStatus VARCHAR(20),                  -- "Success", "Failed", "Skipped"
    EbuyerStatus VARCHAR(20),
    AmazonStatus VARCHAR(20),
    RecordsUpdated INT,
    ErrorMessages TEXT,
    
    INDEX idx_started (StartedAt DESC)
);
```

**Update Flow**:
1. Scraper fetches listings from retailers
2. Insert/update rows in `RetailListings` table (UPSERT by GpuModel + Retailer)
3. Calculate min/avg/max from **current in-stock listings only**
4. Update `RetailPrices` table with aggregated values
5. Record scraper execution in `ScraperLogs`

---

### Price Variance Tracking

**Decision**: Track minimum, average, and maximum prices per GPU model

**Rationale**: Real-world GPU pricing has significant variance based on AIB partner (ASUS, MSI, Gigabyte) and cooling solutions. For example:
- RTX 4080 budget model (MSI Ventus): £1,149
- RTX 4080 mid-tier (Founders Edition): £1,199
- RTX 4080 premium (ASUS ROG Strix): £1,399

A single average (£1,249) doesn't tell users "you can get this card new for as low as £1,149" vs "typical price is £1,249" vs "premium versions go up to £1,399". Price range is critical for the value comparison use case—users need to know if a used RTX 4080 at £950 is a good deal compared to the **cheapest new option** (£1,149), not just the average.

**Calculation Logic**:
- **MinPrice**: Lowest in-stock listing price across all retailers
- **AvgPrice**: Mean of all in-stock listings (after outlier filtering)
- **MaxPrice**: Highest in-stock listing price across all retailers
- Out-of-stock listings are excluded from all calculations
- If only 1 in-stock listing exists: Min = Avg = Max = that price

**Example Calculation**:
```
RTX 4090 listings:
- Scan: £1,599 (in stock)
- Scan: £1,799 (in stock, premium model)
- Ebuyer: £1,549 (in stock)
- Ebuyer: £1,899 (in stock, premium model)
- Amazon: £1,649 (in stock)

Result:
- MinPrice: £1,549
- AvgPrice: £1,699 (mean of 5 listings)
- MaxPrice: £1,899
- ListingCount: 5
```

**Outlier Filtering**: Apply statistical outlier detection (>2 standard deviations from median) **only when 4+ listings exist**. With 2-3 listings, use all data points but log high variance (>25% spread) for manual review.

---

### GPU Model Lifecycle & Archival

**Decision**: Mark models inactive after 14 days of absence; archive after 30 days

**Rationale**: GPUs can temporarily disappear from retailers due to:
- Stock shortages (temporary, may return in weeks)
- Retailer website changes breaking scrapers (false negative)
- Model discontinuation (permanent removal)

Immediately deleting models risks data loss from temporary issues. Keeping discontinued models indefinitely clutters the dataset with irrelevant data. A staged approach balances these concerns:
- **14-day grace period**: Model marked "Inactive" but remains in dataset with stale data indicator
- **30-day archive**: Model moved to archived status, excluded from API by default

**Status Lifecycle**:

```
Active → Inactive (after 14 days not found) → Archived (after 30 days not found)
```

**Behavior**:
- **Active**: Model found in most recent scrape (appears in API responses)
- **Inactive**: Model not found in scrapes for 14+ days (API includes with "Last seen: 15 days ago" indicator)
- **Archived**: Model not found for 30+ days (excluded from API unless `?includeArchived=true`)

**Database Updates**:
- Add `Status` column to `RetailPrices` table: "Active", "Inactive", "Archived"
- Add `LastSeenAt` column: Timestamp of most recent scrape where model was found
- Nightly cleanup job (runs after scraper):
  - If `LastSeenAt` is 14-30 days old: Set Status = "Inactive"
  - If `LastSeenAt` is >30 days old: Set Status = "Archived"
  - If model reappears in scrape: Reset Status = "Active", update `LastSeenAt`

**API Impact**:
- Default `GET /api/v1/retail-prices` returns only "Active" and "Inactive" models
- "Inactive" models include `lastSeenDaysAgo` field
- `?includeArchived=true` returns all statuses (for admin debugging)

---

### Scraper Data Freshness Policy

**Decision**: Exclude retailer data from average calculation if >24 hours stale

**Rationale**: The feature's core value is "current market pricing". If Scan's scraper breaks and we continue using its 3-day-old prices in the average, we're presenting stale data as current. This violates user trust and defeats the purpose of daily scraping.

24-hour threshold balances two concerns:
1. **Data freshness**: Users expect prices updated daily; anything older is unreliable
2. **Scraper resilience**: Single scrape failure shouldn't immediately invalidate data (allows one retry cycle)

**Implementation**:
- Each `RetailListing` row has `ScrapedAt` timestamp
- When calculating average price, filter: `WHERE ScrapedAt > NOW() - INTERVAL '24 hours'`
- If a retailer has no listings <24h old, it contributes zero data points to average
- `ListingCount` in `RetailPrices` reflects only fresh listings used in calculation

**Example Scenario**:
```
Current time: 2025-01-12 10:00 AM

RTX 4090 listings:
- Scan: £1,599 (scraped 2025-01-12 02:00 - FRESH, 8 hours old)
- Ebuyer: £1,649 (scraped 2025-01-12 02:00 - FRESH, 8 hours old)
- Amazon: £1,699 (scraped 2025-01-10 02:00 - STALE, 56 hours old)

Average calculation uses only Scan + Ebuyer = £1,624
ListingCount = 2 (not 3)
Source = "Scan,Ebuyer" (Amazon excluded)
```

**Monitoring Alert**: If a retailer's data becomes stale (excluded from averages), log warning and send Slack/email alert: "Amazon scraper failing for 24+ hours - prices may be inaccurate"

---

### API Response Structure

**Decision**: Return 200 OK with status metadata for all cases; explicitly include currency

**Rationale**: Distinguishing between "no data yet" (cold start), "scraper succeeded but found nothing" (data issue), and "scraper failed" (system error) improves user experience and debugging. A blanket empty array provides no context.

Returning 503 Service Unavailable during cold start would be semantically correct but forces frontend to handle error states differently for temporary vs permanent conditions. Consistent 200 OK with status metadata is simpler for frontend consumption.

Including currency explicitly makes the API self-documenting and future-proof for international expansion (EU retailers, USD pricing).

**API Contract** (UPDATED):

```http
GET /api/v1/retail-prices?manufacturer={nvidia|radeon}
```

**Response** (Success - Data Available):
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
      "priceRange": {
        "min": 1549.99,
        "max": 1899.00,
        "variance": 22.5
      }
    },
    {
      "model": "RTX 4080",
      "vramGB": 16,
      "minPrice": 1149.00,
      "avgPrice": 1199.00,
      "maxPrice": 1399.00,
      "listingCount": 3,
      "inStockCount": 2,
      "inStock": true,
      "lastSeenDaysAgo": null,
      "priceRange": {
        "min": 1149.00,
        "max": 1399.00,
        "variance": 21.8
      }
    }
  ],
  "retailers": {
    "scan": { "status": "success", "lastScraped": "2025-01-12T02:15:10Z" },
    "ebuyer": { "status": "success", "lastScraped": "2025-01-12T02:15:20Z" },
    "amazon": { "status": "failed", "lastScraped": "2025-01-11T02:15:30Z", "error": "Timeout" }
  }
}
```

**Response** (Cold Start - No Data Yet):
```json
{
  "manufacturer": "nvidia",
  "currency": "GBP",
  "status": "cold_start",
  "lastUpdated": null,
  "lastAttemptedAt": null,
  "dataFreshness": "unavailable",
  "prices": [],
  "retailers": {},
  "message": "Initial data collection in progress. Check back in 5-10 minutes."
}
```

**Response** (Scraper Failure - System Error):
```json
{
  "manufacturer": "nvidia",
  "currency": "GBP",
  "status": "scraper_failure",
  "lastUpdated": "2025-01-11T02:15:33Z",
  "lastAttemptedAt": "2025-01-12T02:00:00Z",
  "dataFreshness": "stale",
  "prices": [
    // Last known prices from previous successful scrape
  ],
  "retailers": {
    "scan": { "status": "failed", "lastScraped": "2025-01-11T02:15:10Z", "error": "Connection timeout" },
    "ebuyer": { "status": "failed", "lastScraped": "2025-01-11T02:15:20Z", "error": "Rate limited" },
    "amazon": { "status": "failed", "lastScraped": "2025-01-10T02:15:30Z", "error": "CAPTCHA" }
  },
  "message": "Price data may be outdated due to scraper issues. Last updated 24+ hours ago."
}
```

**Status Field Values**:
- `success`: Scraper ran successfully, data is current (<24h old)
- `cold_start`: No scraper has run yet (initial deployment)
- `scraper_failure`: All retailers failed on most recent run
- `partial_failure`: Some retailers succeeded, some failed (still returns data)

**Data Freshness Values**:
- `current`: Data <24h old
- `stale`: Data 24-48h old
- `very_stale`: Data >48h old
- `unavailable`: No data exists

**Frontend Usage**:
- `status === "success"`: Display prices normally
- `status === "cold_start"`: Show "Loading initial data..." message
- `status === "scraper_failure"`: Show "Using cached data from [date]" warning
- `dataFreshness === "stale"`: Show yellow indicator "Prices may be outdated"

---

### Scraper Timeout & Retry Configuration

**Decision**: 30-second request timeout, 5-minute total timeout per retailer, with manual override capability

**Rationale**: Most modern retail sites load product pages in 5-10 seconds. A 30-second timeout per HTTP request is generous and catches hanging connections quickly. 5-minute total per retailer (across all requests and retries) prevents a single slow/broken retailer from blocking the entire scrape job.

Starting with conservative timeouts reveals performance issues early in development. If testing proves Amazon UK requires longer (heavy JavaScript rendering), we can increase its timeout specifically via configuration rather than defaulting to slow timeouts globally.

**Timeout Configuration**:
```csharp
public class ScraperSettings
{
    public int RequestTimeoutSeconds { get; set; } = 30;
    public int RetailerTotalTimeoutMinutes { get; set; } = 5;
    public int MaxRetryAttempts { get; set; } = 3;
    public int RetryDelaySeconds { get; set; } = 5; // Initial delay, exponential backoff
    
    // Per-retailer overrides if needed
    public Dictionary<string, int> RetailerTimeoutOverrides { get; set; } = new()
    {
        // Example: { "Amazon", 60 } if Amazon needs longer timeout
    };
}
```

**Retry Logic**:
- Attempt 1: Fails after 30s → Wait 5s
- Attempt 2: Fails after 30s → Wait 10s (exponential backoff: 5s × 2)
- Attempt 3: Fails after 30s → Mark retailer as failed
- Total time per retailer (worst case): 30s + 5s + 30s + 10s + 30s = ~2 minutes

**Implementation**:
```csharp
var cts = new CancellationTokenSource(TimeSpan.FromMinutes(retailerTimeout));

for (int attempt = 1; attempt <= maxRetries; attempt++)
{
    try 
    {
        var httpTimeout = TimeSpan.FromSeconds(requestTimeout);
        var response = await httpClient.GetAsync(url, cts.Token);
        // Success - process response
        return;
    }
    catch (TaskCanceledException)
    {
        if (cts.Token.IsCancellationRequested)
        {
            // Total timeout exceeded
            throw new RetailerTimeoutException($"{retailer} exceeded {retailerTimeout}min limit");
        }
        // Request timeout - retry
        await Task.Delay(TimeSpan.FromSeconds(retryDelay * attempt), cts.Token);
    }
}
```

**Manual Override**: If Amazon consistently requires 90-second requests, add override:
```json
{
  "ScraperSettings": {
    "RetailerTimeoutOverrides": {
      "Amazon": 90
    }
  }
}
```

---

### Manual Scraper Triggering

**Decision**: Provide admin-only API endpoint to trigger scrape jobs on-demand

**Rationale**: Waiting up to 24 hours for the next scheduled run is impractical during development and incident response. Scenarios requiring manual trigger:
- **Scraper fix deployed**: Test immediately rather than waiting until 2 AM
- **Retailer website change**: Scraper breaks; after fixing code, validate fix works
- **Monitoring alert**: Scraper failed; after investigating, trigger manual retry
- **New GPU launch**: Add model to whitelist, trigger scrape to populate data immediately

Hangfire makes this trivial to implement (`BackgroundJob.Enqueue<RetailPriceScraperJob>()`). Security is addressed via admin-only authentication (existing auth system).

**API Endpoint**:
```http
POST /api/v1/admin/scraper/trigger
Authorization: Bearer {admin_jwt_token}
Content-Type: application/json

{
  "retailers": ["Scan", "Ebuyer", "Amazon"],  // Optional: specific retailers only
  "forceRefresh": true                         // Optional: ignore recent scrapes
}
```

**Response**:
```json
{
  "jobId": "abc123",
  "status": "queued",
  "message": "Scrape job queued. Check /api/v1/admin/scraper/status/abc123 for progress."
}
```

**Status Endpoint**:
```http
GET /api/v1/admin/scraper/status/{jobId}
```

**Response**:
```json
{
  "jobId": "abc123",
  "status": "running",
  "startedAt": "2025-01-12T14:30:00Z",
  "progress": {
    "scan": "completed",
    "ebuyer": "running",
    "amazon": "pending"
  }
}
```

**Access Control**:
- Endpoint requires `Admin` role in JWT claims
- Rate limited to 1 trigger per 5 minutes per admin user (prevents abuse)
- Audit logged: "Admin user@example.com triggered scrape job at 2025-01-12 14:30"

---

### Monitoring Strategy

**Decision**: Log-based monitoring with structured logging; no dedicated health API endpoint in v1

**Rationale**: The existing API endpoint already returns `lastUpdated` timestamp and per-retailer status in responses. Frontend can display "Prices updated 2 hours ago" using this data. A separate health check endpoint (`/api/v1/scraper/health`) would duplicate information already exposed.

For MVP, centralized logging (Application Insights, Seq) with alerts is sufficient for monitoring scraper health. A dedicated monitoring dashboard (showing success rates, scrape duration trends, retailer reliability) is a v2 feature—useful for ops teams but not user-facing.

**Logging Requirements**:

**Structured Log Events**:
```csharp
// Scraper start
logger.LogInformation("Scraper job started {JobId} at {StartTime}", jobId, startTime);

// Per-retailer status
logger.LogInformation("Scraping {Retailer} - {Status}: {ListingsFound} listings, {Duration}ms", 
    retailer, status, count, duration);

// Scraper completion
logger.LogInformation("Scraper job {JobId} completed - {Status}: {ModelsUpdated} models updated, {Duration}ms",
    jobId, status, modelsUpdated, totalDuration);

// Failures
logger.LogError("Scraper job {JobId} failed for {Retailer}: {Error}", 
    jobId, retailer, exception.Message);

// Stale data warning
logger.LogWarning("Retailer {Retailer} data is stale ({HoursSinceLastScrape}h) - excluding from averages",
    retailer, hoursSinceLastScrape);

// High price variance
logger.LogWarning("High price variance for {Model}: {MinPrice}-{MaxPrice} (variance: {Variance}%)",
    model, minPrice, maxPrice, variance);
```

**Alerting Rules** (configure in Application Insights or equivalent):
1. **Alert**: Scraper job fails 2 consecutive runs
   - Severity: High
   - Action: Slack notification to #gpu-tracker-alerts
   
2. **Alert**: Any retailer data stale >48 hours
   - Severity: Medium
   - Action: Email to on-call engineer
   
3. **Alert**: Zero models updated in scrape run (possible scraper breakage)
   - Severity: High
   - Action: Slack notification + page on-call
   
4. **Alert**: Price variance >50% for any model (possible data quality issue)
   - Severity: Low
   - Action: Log for manual review

**Metrics to Track**:
- Scrape job success rate (per day, per retailer)
- Average scrape duration (per retailer, overall)
- Listings found per retailer (trending down = possible scraper breakage)
- API response times for `/retail-prices` endpoint
- 4xx/5xx error rates on API

**Dashboard (v2 Feature)**:
- Real-time scraper status (currently running, last run time, next scheduled run)
- Retailer reliability chart (success rate over 30 days)
- Price trend graphs (avg price per model over time—requires historical data)
- Listing count trends (detect when retailer inventory drops)

---

## Q&A History

### Iteration 1 - 2025-01-12

**Q1: How do we handle GPU model classification when VRAM size isn't detectable from product title?**  
**A**: Use a hardcoded whitelist of eligible models (RTX 4090, RTX 4080, RX 7900 XTX, etc.) stored in configuration. Scrapers normalize product names to reference models, check against whitelist, and discard non-matching listings. This provides 100% accuracy and is practical given the small number of latest-gen 16GB+ cards. Manual updates are manageable given infrequent GPU launches (every 6-12 months).

**Q2: Should we store individual retailer prices, or only the calculated average?**  
**A**: Store both. Individual listings go in `RetailListings` table, calculated aggregates in `RetailPrices` table. This enables price transparency (showing min/avg/max), debugging (auditing which retailer contributed what), and future features (price comparison, best deal indicators) without re-architecture. Storage cost is negligible at MVP scale.

**Q3: What happens when a GPU model disappears from all retailers (discontinued)?**  
**A**: Staged lifecycle: Models not found in scrapes for 14+ days are marked "Inactive" (remain in API with "last seen" indicator), then "Archived" after 30 days (excluded from API by default unless `?includeArchived=true`). This prevents false positives from temporary scraper issues while keeping the active dataset clean.

**Q4: How should we handle manufacturer variants that differ significantly in price (e.g., reference vs. high-end AIB models)?**  
**A**: Track min/avg/max prices per model. Users need to know "cheapest available new" (min), "typical price" (avg), and "premium option cost" (max) for accurate value comparison. Real-world variance is significant (£250+ between budget and premium RTX 4080 variants), and averaging alone obscures this critical information.

**Q5: What should the API return if the scraper has never successfully run (cold start)?**  
**A**: Return 200 OK with status metadata. Response includes `"status": "cold_start"`, `"lastUpdated": null`, and helpful message "Initial data collection in progress." Also return status for "scraper_failure" and "partial_failure" cases. This allows frontend to display appropriate user messaging (loading state, stale data warning, etc.) while maintaining consistent 200 OK pattern.

**Q6: Should outlier filtering (>2 standard deviations) apply when there are only 2-3 listings?**  
**A**: Only apply statistical outlier filtering when 4+ listings exist. With 2-3 listings, use all data points but log high variance (>25% spread) for manual review. Statistical methods are unreliable with small sample sizes; flag anomalies for human review rather than risk removing valid data.

**Q7: How long should we wait before marking a scrape job as "failed" for a specific retailer?**  
**A**: 30-second request timeout, 5-minute total timeout per retailer, 3 retry attempts with exponential backoff (5s, 10s delays). Most retail sites load in 5-10 seconds; 30s is generous. If testing reveals Amazon UK needs longer, add per-retailer timeout override in configuration. Start conservative to catch issues quickly.

**Q8: Should the API endpoint support filtering by stock status (in-stock only vs. all)?**  
**A**: No filtering needed in v1. Always return all GPUs with `inStock` boolean; frontend filters if desired. Dataset is small (6-8 models per manufacturer), so bandwidth isn't a concern. Keeps API simple. Can add query parameters in v2 if performance becomes an issue.

**Q9: When multiple scrape attempts fail for a retailer, should we preserve the last successful data or clear it?**  
**A**: Exclude retailer data from average calculation after 24 hours of staleness. If Scan's scraper fails and data is >24h old, only use Ebuyer + Amazon for average. Log exclusion and alert monitoring: "Scan excluded from averages due to stale data." Maintains data freshness commitment while giving 24h grace period for retry. Track `LastSuccessfulScrapeAt` per retailer per model.

**Q10: Should we track and expose currency in the API response, or assume GBP?**  
**A**: Include explicit `"currency": "GBP"` field in API response. Makes API self-documenting, prevents assumptions, and future-proofs for international expansion (EU retailers, USD pricing). Zero cost to add, high clarity benefit.

**Q11: Should admin users be able to manually trigger a scrape job on-demand, or is scheduled-only sufficient?**  
**A**: Add admin-only endpoint `POST /api/v1/admin/scraper/trigger` protected by JWT admin role. Critical for testing scraper fixes, responding to incidents, and populating data after whitelist updates. Hangfire makes this trivial. Rate limit to 1 trigger per 5 minutes, audit log all triggers.

**Q12: Should we expose scraper health metrics via the API, or only in logs?**  
**A**: Logs only for v1. The existing `/api/v1/retail-prices` response already includes `lastUpdated` timestamp and per-retailer status, which is sufficient for frontend to show "Prices updated X hours ago." Use structured logging with Application Insights alerts for operational monitoring. Dedicated health dashboard is v2 feature.

---

## Product Rationale

### Why Hardcoded Whitelist Over Auto-Detection?

**User Need**: Users must trust that our "latest-gen 16GB+" filter is accurate. Including a 12GB RTX 4070 Ti by mistake undermines the entire value proposition.

**Technical Reality**: Retailer product titles are inconsistent. Attempting to parse VRAM from strings like "RTX 4080 Gaming OC" (no VRAM mentioned) vs "RX 7900 XTX 24GB" (explicit) requires complex heuristics prone to errors.

**Practical Trade-off**: Latest-gen GPU launches are rare (2-3 new models per year). Manual whitelist updates are trivial compared to building and maintaining auto-detection logic. Start simple, prove value, add automation in v2 if manual maintenance becomes burdensome.

---

### Why Store Individual Listings AND Aggregates?

**User Need**: "Is this used RTX 4090 at £1,200 a good deal?" requires knowing "new cards range from £1,549 to £1,899" not just "average is £1,699." The cheapest new option is what users mentally compare against.

**Data Quality**: When average price looks wrong, we need to audit: "Did Amazon report £99 by mistake? Did Scan's scraper break and report £0?" Individual listings make debugging possible.

**Future Features**: Price comparison ("Scan has it £50 cheaper than Ebuyer"), best deal indicators, historical trend analysis all require individual listings. Re-architecting later is expensive; storing upfront is cheap (24 rows per day).

**Cost**: PostgreSQL storage for 24 rows/day × 365 days × 3 years = ~26,000 rows = ~5MB. Negligible.

---

### Why 24-Hour Staleness Threshold?

**User Expectation**: Feature promises "prices updated daily." If we show 3-day-old Scan prices as current, we're lying.

**Data Integrity**: If Scan's scraper breaks Monday and we keep using Monday's prices through Thursday, our averages don't reflect reality. Better to show "Average based on Ebuyer + Amazon only (Scan unavailable)" than present stale data as fresh.

**Grace Period**: 24 hours allows one full retry cycle (scraper runs daily at 2 AM). Single failure doesn't immediately invalidate data, but persistent failure does.

**Transparency**: When retailer data is excluded, we log it, alert monitoring, and show status in API. Users and ops team know data quality state.

---

### Why Min/Avg/Max Instead of Just Average?

**Real-World Variance**: RTX 4080 pricing (actual example):
- Budget AIB: £1,149 (MSI Ventus)
- Reference: £1,199 (Founders Edition, often out of stock)
- Premium AIB: £1,399 (ASUS ROG Strix with custom cooling)

**User Decision**: "Should I buy this used RTX 4080 for £950?"
- Compare to **min** (£1,149): Saving £199 (17% discount) - good deal
- Compare to **avg** (£1,249): Saving £299 (24% discount) - great deal
- Compare to **max** (£1,399): Saving £449 (32% discount) - excellent deal if comparing to premium models

Average alone doesn't tell the full story. Users need context: "How much cheaper is used vs the absolute cheapest new option?" (min) and "What's the typical new price?" (avg).

**Variance Indicator**: If min/max spread is <10%, market is uniform. If >30%, market has budget vs premium tiers—users should know this.

---

### Why 200 OK with Status Metadata Instead of 503?

**Frontend Simplicity**: Consistent 200 OK response structure means frontend doesn't need separate error handling logic for "no data yet" vs "scraper failed" vs "success."

**User Experience**: During cold start (first deployment), showing "Loading initial data, check back in 5 minutes" is friendlier than a generic error page. Status metadata enables contextual messaging.

**Monitoring**: Scraper failures should alert ops team (via logs/metrics), not surface as 5xx errors to end users. Users see last known good data with "may be outdated" warning, not a broken page.

**Semantic Correctness Trade-off**: Yes, 503 Service Unavailable is semantically correct for cold start. But pragmatically, making frontend handle both 200 and 503 for the same endpoint adds complexity for minimal benefit. Status metadata achieves the same goal within consistent 200 responses.

---

### Why Manual Scraper Trigger is Critical for MVP?

**Development Velocity**: Waiting 24 hours to test scraper changes is impractical. Manual trigger enables rapid iteration: change code → trigger scrape → verify results in minutes.

**Incident Response**: If all scrapers fail overnight, ops team needs ability to trigger manual retry after fixing root cause (e.g., deploy code fix, trigger scrape, validate). Waiting until next 2 AM scheduled run delays recovery.

**New GPU Launch**: When RTX 5090 releases, we add it to whitelist. Manual trigger immediately populates pricing data rather than waiting for next scheduled run. Users see new data within minutes of configuration update.

**Cost**: Implementation is trivial with Hangfire (`BackgroundJob.Enqueue<T>()`). Security via existing admin JWT auth. High value, low effort.

---

## Out of Scope for This Feature (UPDATED v1.1)

This feature explicitly does NOT include:

- **Historical price tracking**: Only current prices are stored; no trend graphs or "price 30 days ago" functionality (v2 feature requiring time-series data model)
- **Price drop alerts**: No email or push notifications when prices decrease (v2 feature requiring user subscriptions and notification service)
- **User-configurable scraping**: Scrape schedule is fixed at daily 2 AM; users cannot customize timing or trigger scrapes (admin manual trigger only)
- **International retailers**: Only UK retailers (Scan, Ebuyer, Amazon UK); no Newegg, B&H, US/EU stores
- **Intel Arc GPUs**: Only Radeon and Nvidia latest-gen cards (Intel Arc lacks market share for MVP)
- **8GB or smaller GPUs**: Only 16GB+ VRAM cards are tracked (focus on AI/ML use cases)
- **Partner card differentiation**: ASUS, MSI, Gigabyte variants are normalized to reference models; no "which AIB brand is cheapest" comparison (min/max prices address this indirectly)
- **Affiliate links**: No monetization or referral links to retailers
- **Scraper performance optimization**: No distributed scraping, proxy rotation, or CAPTCHA solving services (v1 uses respectful scraping with rate limiting; add sophistication in v2 if blocked)
- **Admin monitoring dashboard**: No dedicated UI for scraper health visualization (rely on logs and alerts; dashboard is v2)
- **Price prediction/forecasting**: No ML models predicting future prices (focus on current pricing only)
- **Multi-currency support**: GBP only; no EUR, USD conversion (UK market focus for MVP)

---

## Dependencies

**Depends On**: None (this is a foundational feature)

**Enables**: 
- Feature 2 (Used Market Price Discovery) depends on this baseline pricing data for value comparison
- Feature 3 (Value Visualization Dashboard) consumes this API to display retail pricing context

---

**Status**: Ready for Implementation (all clarifications provided)