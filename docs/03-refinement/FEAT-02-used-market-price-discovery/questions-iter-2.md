# Used Market Price Discovery - Technical Review (Iteration 2)

**Status**: ✅ READY FOR IMPLEMENTATION
**Iteration**: 2
**Date**: 2025-01-10

---

## Summary

This feature specification is sufficiently detailed to proceed with implementation. All 14 critical questions from Iteration 1 have been answered clearly and comprehensively. The PRD now provides unambiguous guidance on data sourcing, quality thresholds, model identification, failure handling, and all other technical considerations needed to build the scraping infrastructure and API.

---

## What's Clear

### Data Model

**Core Entities**:
- **UsedListing**: Individual scraped listing with `ListingId`, `CardModel`, `VramSize`, `Price`, `Source` (eBay/CEX), `ListingUrl`, `ScrapedAt`, `IsOutlier`
- **UsedPriceAverage**: Aggregated price per card model with `CardModel`, `VramSize`, `AveragePrice`, `ListingCount`, `SourceBreakdown` (JSON), `Confidence` (low/medium/high), `CalculatedAt`, `Manufacturer`
- **ScrapeJob**: Metadata tracking each scraping run with `JobId`, `RunAt`, `Source`, `ListingsFound`, `Status`, `ErrorMessage`

**Relationships**:
- UsedListing → UsedPriceAverage (many-to-one grouping by CardModel)
- VRAM variants are separate models (RTX 4060 Ti 8GB ≠ RTX 4060 Ti 16GB)
- Historical averages preserved indefinitely (one record per card per day)
- Individual listings retained for 7 days only, then purged

**Constraints**:
- Price range: £50-£5000 (sanity check bounds)
- Currency: GBP only (discard non-GBP listings)
- VRAM: 16GB+ only (scope filter)
- Staleness: Hide data if >3 days old

### Business Logic

**Scraping Pipeline**:
1. **Data Acquisition**:
   - eBay: Official Finding API (`findItemsAdvanced`) with OAuth 2.0, filters for Used + Buy It Now + UK location
   - CEX: Web scraping with 3-second rate limiting, robots.txt compliance, HTML parsing
   - Target models: Dynamic list from Feature 1 (cards with retail price data)

2. **Data Validation** (sequential):
   - Sanity check: Discard prices outside £50-£5000
   - Currency check: Discard non-GBP listings
   - Model identification: Match listing against `gpu-models.json` aliases
   - VRAM validation: Confirm extracted VRAM matches model spec

3. **Outlier Filtering**:
   - Calculate median price per model
   - Remove listings >2x or <0.5x median
   - Log removed outliers for review

4. **Average Calculation**:
   - Calculate average from filtered listings
   - Determine confidence: Low (1-2), Medium (3-5), High (6+)
   - Store source breakdown: `{"eBay": 5, "CEX": 3}`

**Scheduling**:
- Fixed daily scrape: 3:00 AM UTC via Hangfire recurring job
- Manual trigger: Admin backoffice "Scrape Now" button with concurrency prevention
- No automatic retries on failure (prefer alerts → manual investigation)

**Failure Handling**:
- **Single source failure**: Complete scrape with available data, display partial results with warning ("Based on 1 source - CEX unavailable")
- **Complete failure**: Retain previous data, display age warning if <3 days, hide entirely if >3 days ("Data temporarily unavailable")
- **Alert thresholds**: Warning at >2 days stale, critical alert at >3 days stale or 0% success rate

### API Design

**Public Endpoints**:
```typescript
GET /api/v1/used-prices/{cardModel}
Response: {
  card_model: string;
  is_available: boolean; // false if >3 days old
  average_price?: number;
  listing_count?: number;
  confidence: 'low' | 'medium' | 'high';
  confidence_message: string;
  sources: { eBay: number; CEX: number };
  calculated_at: string; // ISO 8601 timestamp
  staleness_warning?: 'fresh' | 'aging' | 'unavailable';
}

GET /api/v1/used-prices?manufacturer={Nvidia|AMD}
Response: UsedPriceResponse[] // All cards for manufacturer
```

**Admin Endpoints** (requires `[Authorize(Roles = "Admin")]`):
```typescript
POST /admin/used-market/scrape
// Triggers immediate scrape, returns job ID

GET /admin/used-market/status
Response: {
  last_scrape_time: string;
  status: 'success' | 'partial' | 'failure';
  listings_found: { eBay: number; CEX: number };
  next_scheduled: string;
}

GET /admin/used-listings/{id}
Response: {
  id: string;
  card_model: string;
  price: number;
  source: string;
  listing_url: string; // Only in admin DTO
  scraped_at: string;
  is_outlier: boolean;
}
```

**Caching**:
- Redis cache key pattern: `used-prices:{manufacturer}:{card-model}`
- TTL: 1 hour (data refreshes daily, 1-hour cache is 4% stale max)
- Invalidation: Clear all `used-prices:*` keys on scrape completion

**Authorization**:
- Public endpoints: Anonymous access (read-only data)
- Admin endpoints: Require authentication + Admin role
- No rate limiting specified for v1 (can add if abuse detected)

### UI/UX

**Dashboard Display** (per card):
```
[Card Name - e.g., "RX 7900 XT 20GB"]
Used: £480 avg. (8 listings) ⓘ
✓ High confidence
Updated 6 hours ago
```

**Confidence Indicators**:
- **Low (1-2 listings)**: `⚠️ Low confidence - only [N] listing(s) found` (yellow/orange badge)
- **Medium (3-5 listings)**: Standard display, no special badge
- **High (6+ listings)**: `✓ High confidence - [N] listings` (green checkmark)

**Tooltip on Hover** (listing count):
```
Based on 8 listings:
• 5 from eBay UK
• 3 from CEX UK
Updated 6 hours ago
```

**Staleness Warnings**:
- **<24 hours**: No warning, standard display
- **1-3 days**: `⚠️ £480 avg. (8 listings) • Updated 2 days ago` with tooltip "Price data is 2 days old. May not reflect current market."
- **>3 days**: Hide price entirely, show `Used market data temporarily unavailable. Check back later.` + `Last updated: 4 days ago`

**Admin Backoffice**:
- Route: `/admin/used-market-scraping`
- Display: Last scrape timestamp, status badge (success/partial/failure), listings found per source, next scheduled run
- Button: "Scrape Used Market Prices Now" (disabled if job in progress)
- Logging: Display recent scrape jobs with expandable error details

### Edge Cases

**Addressed in Specification**:
- ✅ Zero listings after filtering → Display "No recent listings found"
- ✅ All listings filtered as outliers → Display "Data quality insufficient - listings appear unreliable"
- ✅ eBay API rate limit hit → Complete scrape with available data, alert ops team
- ✅ CEX blocked/CAPTCHA → Fail CEX gracefully, continue with eBay only, alert ops
- ✅ Currency mismatch → Discard non-GBP listings, log for investigation
- ✅ VRAM mismatch → Discard listing (trust canonical model spec over listing text)
- ✅ Model ambiguity → Discard ambiguous listings, log to `UnmatchedListing` table
- ✅ Duplicate listings → Accept potential double-counting in v1 (no de-duplication)
- ✅ Concurrent scrape trigger → Prevent via Hangfire job state check
- ✅ Historical data migration → Not needed (start fresh from v1 launch)

---

## Implementation Notes

### Database Schema

**PostgreSQL Tables**:
```sql
-- Individual listings (7-day rolling window)
CREATE TABLE used_listings (
    id UUID PRIMARY KEY,
    card_model VARCHAR(100) NOT NULL,
    vram_gb INT NOT NULL,
    price DECIMAL(10,2) NOT NULL,
    source VARCHAR(50) NOT NULL, -- 'eBay' or 'CEX'
    listing_url TEXT,
    scraped_at TIMESTAMP NOT NULL,
    is_outlier BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_used_listings_scraped_at ON used_listings(scraped_at);

-- Historical averages (indefinite retention)
CREATE TABLE used_price_averages (
    id UUID PRIMARY KEY,
    card_model VARCHAR(100) NOT NULL,
    vram_gb INT NOT NULL,
    average_price DECIMAL(10,2) NOT NULL,
    listing_count INT NOT NULL,
    source_breakdown JSONB NOT NULL, -- {"eBay": 5, "CEX": 3}
    confidence VARCHAR(20) NOT NULL, -- 'low', 'medium', 'high'
    calculated_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_used_price_averages_card ON used_price_averages(card_model, calculated_at);

-- Scrape job metadata
CREATE TABLE scrape_jobs (
    id UUID PRIMARY KEY,
    source VARCHAR(50) NOT NULL,
    run_at TIMESTAMP NOT NULL,
    listings_found INT NOT NULL,
    status VARCHAR(50) NOT NULL, -- 'success', 'partial', 'failure'
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Debugging/logging tables
CREATE TABLE unmatched_listings (
    id UUID PRIMARY KEY,
    listing_title TEXT NOT NULL,
    price DECIMAL(10,2) NOT NULL,
    source VARCHAR(50) NOT NULL,
    scraped_at TIMESTAMP NOT NULL
);

CREATE TABLE outlier_log (
    id UUID PRIMARY KEY,
    card_model VARCHAR(100) NOT NULL,
    price DECIMAL(10,2) NOT NULL,
    median DECIMAL(10,2) NOT NULL,
    source VARCHAR(50) NOT NULL,
    listing_url TEXT,
    logged_at TIMESTAMP DEFAULT NOW()
);
```

### GPU Model Reference File

**Location**: `src/UsedMarketPriceDiscovery/Data/gpu-models.json`

**Structure**:
```json
{
  "version": "1.0",
  "last_updated": "2025-01-10",
  "models": [
    {
      "canonical_name": "RTX 4060 Ti 16GB",
      "vram_gb": 16,
      "manufacturer": "Nvidia",
      "aliases": [
        "4060 Ti 16GB",
        "4060Ti 16GB",
        "4060-Ti 16GB",
        "RTX4060Ti 16GB",
        "RTX 4060Ti 16 GB",
        "GeForce RTX 4060 Ti 16GB"
      ]
    },
    {
      "canonical_name": "RX 7900 XT",
      "vram_gb": 20,
      "manufacturer": "AMD",
      "aliases": [
        "7900 XT",
        "7900XT",
        "RX7900XT",
        "7900 XT 20GB",
        "Radeon 7900 XT",
        "Radeon RX 7900 XT"
      ]
    }
  ]
}
```

**Loading Strategy**:
```csharp
// Startup.cs or Program.cs
services.AddSingleton<GpuModelLookupService>(sp => 
{
    var json = File.ReadAllText("Data/gpu-models.json");
    var config = JsonSerializer.Deserialize<GpuModelConfig>(json);
    return new GpuModelLookupService(config);
});
```

### External Integrations

**eBay API**:
- Base URL: `https://svcs.ebay.com/services/search/FindingService/v1`
- Authentication: OAuth 2.0 application token (stored in environment variable `EBAY_API_TOKEN`)
- Registration: https://developer.ebay.com/
- Rate limit: 5,000 calls/day
- Sample request:
  ```http
  GET /services/search/FindingService/v1?
      OPERATION-NAME=findItemsAdvanced
      &SERVICE-VERSION=1.0.0
      &SECURITY-APPNAME={token}
      &RESPONSE-DATA-FORMAT=JSON
      &keywords=RTX+4060+Ti+16GB
      &itemFilter(0).name=ListingType
      &itemFilter(0).value=FixedPrice
      &itemFilter(1).name=Condition
      &itemFilter(1).value=Used
      &itemFilter(2).name=LocatedIn
      &itemFilter(2).value=GB
  ```

**CEX Scraping**:
- Base URL: `https://uk.webuy.com/search`
- Query params: `?stext={model}&section=computing-graphics-cards`
- Rate limiting: `await Task.Delay(3000)` between requests
- User-Agent: `GPUValueTracker/1.0 (contact@yoursite.com)`
- HTML parsing: AngleSharp or HtmlAgilityPack
- Robots.txt: Check `/robots.txt` before scraping, respect `Disallow` directives

### Validation Rules

**Price Sanity Checks**:
```csharp
public const decimal MIN_VALID_PRICE = 50m;
public const decimal MAX_VALID_PRICE = 5000m;
```

**Outlier Thresholds**:
```csharp
decimal lowerBound = median * 0.5m;
decimal upperBound = median * 2.0m;
```

**Staleness Threshold**:
```csharp
public bool IsStale => DateTime.UtcNow - CalculatedAt > TimeSpan.FromDays(3);
```

**Confidence Levels**:
```csharp
public string GetConfidence(int listingCount) => listingCount switch
{
    <= 2 => "low",
    <= 5 => "medium",
    _ => "high"
};
```

### Key Decisions

**Data Source Strategy**:
- eBay official API (compliant, reliable) + CEX web scraping (calculated risk)
- Facebook Marketplace excluded from v1 (ToS concerns, anti-scraping)
- Two sources sufficient for MVP market coverage

**Quality Over Quantity**:
- Display all prices (even 1 listing) with confidence indicators
- Transparency over paternalism - let users judge data reliability
- Staleness threshold (3 days) protects users from misleading outdated data

**Model Identification**:
- JSON reference file (version controlled, engineer-editable)
- Source from TechPowerUp GPU Database (manual curation for v1)
- VRAM variants as separate models (RTX 4060 Ti 8GB ≠ 16GB)
- Log unmatched listings for continuous improvement

**Failure Handling**:
- Graceful degradation (partial data better than no data)
- No automatic retries (prefer alerts → manual fix)
- Monitoring urgency via 3-day staleness threshold

**Data Retention**:
- Individual listings: 7 days (debugging window)
- Historical averages: Indefinite (enables v2 trend features)
- Storage efficiency: Purge old listings, keep aggregates

**Security & Privacy**:
- Listing URLs stored but never exposed via public API
- Admin-only access to individual listing details
- No user tracking or personal data collection

---

## Recommended Next Steps

1. **Create Engineering Specification** with:
   - Detailed service architecture (scraper service, background job service, API service)
   - Class diagrams for core models and services
   - Sequence diagrams for scraping pipeline and API request flow
   - eBay API integration implementation details
   - CEX scraping implementation strategy
   - Error handling and retry logic
   - Monitoring and alerting setup
   - Database migration scripts
   - Unit test coverage plan

2. **Set Up Development Environment**:
   - Register eBay Developer account, obtain API credentials
   - Configure Hangfire dashboard for job monitoring
   - Set up Redis instance for caching
   - Create `gpu-models.json` seed file with initial 50-70 target models

3. **Implementation Phases** (suggested):
   - **Phase 1**: Database schema + EF Core models + migrations
   - **Phase 2**: GPU model lookup service + JSON loading
   - **Phase 3**: eBay API scraper implementation
   - **Phase 4**: CEX web scraper implementation
   - **Phase 5**: Data validation + outlier filtering pipeline
   - **Phase 6**: Hangfire background jobs + scheduling
   - **Phase 7**: Public API endpoints + caching
   - **Phase 8**: Admin backoffice UI
   - **Phase 9**: Monitoring + alerting integration
   - **Phase 10**: Testing (unit + integration + E2E)

4. **Risk Mitigation**:
   - Test eBay API integration early (validate OAuth flow, rate limits)
   - Test CEX scraping early (verify HTML parsing resilience, handle pagination)
   - Set up monitoring/alerts before production deployment
   - Plan for CEX ToS enforcement (have proxy rotation strategy ready if needed)

---

**This feature is ready for detailed engineering specification.**

The PRD provides unambiguous guidance on all critical aspects: data sourcing (eBay API + CEX scraping), quality thresholds (confidence indicators, staleness limits), model identification (JSON lookup with aliases), failure handling (graceful degradation), data retention (7-day listings, indefinite averages), and UI transparency (source breakdowns, confidence badges). 

All 14 technical questions from Iteration 1 have been resolved with clear decisions and rationale. The feature scope is well-defined with explicit out-of-scope items. Edge cases are documented and addressed. Integration points with Feature 1 (retail price tracking) are clear.

No further product clarification is required. The engineering team can now proceed with confidence to build a robust, maintainable used market price scraping system.