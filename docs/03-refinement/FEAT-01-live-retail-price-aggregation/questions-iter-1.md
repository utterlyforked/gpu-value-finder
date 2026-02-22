# Live Retail Price Aggregation - Technical Questions (Iteration 1)

**Status**: NEEDS CLARIFICATION
**Iteration**: 1
**Date**: 2025-01-10

---

## Summary

After reviewing the specification, I've identified **12** areas that need clarification before implementation can begin. These questions address:
- Data persistence and update strategies
- GPU model identification and classification
- Price calculation edge cases
- API contract details
- Scraper failure handling
- Monitoring and alerting requirements

The spec is well-structured and comprehensive, but several critical decisions about data handling and business logic need product input before engineering can proceed.

---

## CRITICAL Questions

These block core implementation and must be answered first.

### Q1: How do we handle GPU model classification when VRAM size isn't detectable from product title?

**Context**: The spec states we track "16GB+ VRAM only" and filter out cards under 16GB. However, retailer product titles often don't include VRAM size (e.g., "RTX 4070 Ti" without mentioning it's 12GB and should be excluded). This affects:
- Whether we can reliably filter GPUs automatically
- Whether scrapers need additional logic to fetch specifications pages
- Risk of including ineligible cards in our dataset

**Options**:

- **Option A: Maintain hardcoded whitelist of eligible models**
  - Impact: Create static list of models we know meet 16GB+ requirement (RTX 4090, RTX 4080, RX 7900 XTX, etc.)
  - Trade-offs: 
    - ✅ Reliable filtering, no ambiguity
    - ✅ Simple implementation
    - ❌ Requires manual updates when new models launch
    - ❌ Miss new models until whitelist updated
  - Database: Add `EligibleGpuModels` configuration table or app settings

- **Option B: Parse VRAM from product title/specs with fallback to manual review**
  - Impact: Scraper attempts to extract VRAM size from text, flags uncertain entries for manual review
  - Trade-offs:
    - ✅ Automatically detects new models
    - ❌ Complex regex/parsing logic
    - ❌ Requires admin interface for manual classification
    - ❌ Risk of misclassification

- **Option C: Scrape only specific product category pages that are known 16GB+ models**
  - Impact: Target retailer URLs like "/rtx-4090" or "/rx-7900-xtx" instead of broad GPU searches
  - Trade-offs:
    - ✅ High accuracy
    - ✅ Faster scraping (fewer pages)
    - ❌ Miss new models entirely
    - ❌ Requires maintaining URL lists per retailer

**Recommendation for MVP**: **Option A (hardcoded whitelist)**. Most reliable approach for v1. We know the exact set of latest-gen 16GB+ cards right now (about 6-8 models). New model launches are infrequent enough to update manually. Can add auto-detection in v2 if needed.

---

### Q2: Should we store individual retailer prices, or only the calculated average?

**Context**: Current spec shows `RetailPrices` table with `AveragePrice` and `Source` (comma-separated retailers). This affects:
- Ability to show per-retailer prices in future features
- Debugging when one retailer has bad data
- Transparency for users who want to know price range

**Options**:

- **Option A: Store only calculated average (as spec shows)**
  - Impact: One row per GPU model with average price
  - Trade-offs:
    - ✅ Simple schema
    - ✅ Fast queries
    - ❌ Cannot show "Scan: £1,199 | Ebuyer: £1,149 | Amazon: £1,249"
    - ❌ Cannot debug which retailer contributed outlier
    - ❌ Cannot add "best price" feature later without re-scraping
  - Database: Single `RetailPrices` table as spec shows

- **Option B: Store individual listings + calculated average**
  - Impact: Two tables: `RetailListings` (individual prices) and `RetailPrices` (calculated average)
  - Trade-offs:
    - ✅ Full transparency and debugging capability
    - ✅ Can show price range and individual retailer prices
    - ✅ Can add "best price" or "price alert" features later
    - ❌ More complex schema
    - ❌ More storage (3x rows for 3 retailers)
  - Database:
    ```
    RetailListings: Id, GpuModel, Retailer, Price, InStock, ScrapedAt
    RetailPrices: Id, GpuModel, AveragePrice, ... (aggregated from listings)
    ```

- **Option C: Store individual listings, calculate average on-the-fly**
  - Impact: Only `RetailListings` table, API calculates average when requested
  - Trade-offs:
    - ✅ Single source of truth
    - ❌ Slower API responses (calculation overhead)
    - ❌ More complex query logic

**Recommendation for MVP**: **Option B (store both)**. Storage is cheap, and having individual listings unlocks future features (price comparison, "best deal" indicators) without re-architecting. The spec mentions "historical snapshots are NOT stored in v1" - but storing current individual listings isn't historical data, it's operational data that makes the current average auditable.

---

### Q3: What happens when a GPU model disappears from all retailers (discontinued)?

**Context**: Spec says "If all retailers are out of stock for a model, retain last known average price and mark as Out of Stock." But what if a model is completely discontinued and removed from retailer sites (not just out of stock)?

**Options**:

- **Option A: Keep forever with stale data indicator**
  - Impact: Row stays in database indefinitely, marked as "Last seen: 30 days ago"
  - Trade-offs:
    - ✅ Historical reference preserved
    - ❌ Clutters API responses with irrelevant models
    - ❌ Need to decide when to stop showing in UI

- **Option B: Archive after N days of not being scraped**
  - Impact: If model not found in scrapes for 14 days (configurable), move to `ArchivedRetailPrices` table or soft-delete
  - Trade-offs:
    - ✅ Keeps active dataset clean
    - ✅ Can restore if model reappears
    - ❌ Need archive mechanism and retention policy

- **Option C: Delete immediately when not found in scrape**
  - Impact: If scraper doesn't find a model, remove from database
  - Trade-offs:
    - ✅ Simplest implementation
    - ❌ Risk of false positives (retailer page loading error = model deleted)
    - ❌ Lose price history if model temporarily unavailable

**Recommendation for MVP**: **Option B (archive after 14 days)**. Protects against temporary scraping glitches while keeping the dataset relevant. Mark models as "Not found in recent scrapes" after 14 days of absence, then archive after 30 days. API endpoint should exclude archived models by default (but allow `includeArchived=true` query param for debugging).

---

### Q4: How should we handle manufacturer variants that differ significantly in price (e.g., reference vs. high-end AIB models)?

**Context**: Spec says "Manufacturer-specific partner cards are normalized to reference model" (e.g., "ASUS ROG Strix RTX 4080" → "RTX 4080"). However, high-end AIB cards can be £100-200+ more than reference models. Averaging them together might not represent what users can actually buy.

**Example Real-World Data**:
- RTX 4080 Founders Edition: £1,199 (if available)
- MSI Ventus RTX 4080: £1,149 (budget AIB)
- ASUS ROG Strix RTX 4080 OC: £1,399 (premium AIB)
- Average: £1,249 (doesn't represent any actual purchasable option well)

**Options**:

- **Option A: Average all variants together (as spec describes)**
  - Impact: Single price per GPU model
  - Trade-offs:
    - ✅ Simple implementation
    - ✅ Gives general market price
    - ❌ Doesn't reflect actual cheapest available option
    - ❌ Can be misleading for value comparison

- **Option B: Track minimum, average, and maximum prices**
  - Impact: Database stores `MinPrice`, `AvgPrice`, `MaxPrice` for each model
  - Trade-offs:
    - ✅ Shows price range users can expect
    - ✅ Can highlight "budget" vs "premium" options
    - ❌ More complex schema and calculations
  - Database: Add `MinPrice` and `MaxPrice` columns to `RetailPrices`

- **Option C: Use minimum price only (cheapest available)**
  - Impact: Store lowest price found across all variants as the baseline
  - Trade-offs:
    - ✅ Represents best possible new-card deal
    - ✅ Most relevant for value comparison
    - ❌ Might not represent typical purchase (cheap models often out of stock)

**Recommendation for MVP**: **Option B (track min/avg/max)**. The "value proposition" of the app is showing used vs new pricing. Users need to know "I can get this card new for as low as £1,149" (min) and "typical price is £1,249" (avg). Minimal extra complexity (just track min/max during calculation), high user value.

---

### Q5: What should the API return if the scraper has never successfully run (cold start)?

**Context**: Spec says "Returns 200 OK with empty `prices` array if no data available". But should we distinguish between:
- "Scraper hasn't run yet" (cold start)
- "Scraper ran but found no eligible GPUs" (data issue)
- "Scraper failed on last run" (system error)

**Options**:

- **Option A: 200 OK with empty array for all cases**
  - Impact: Frontend cannot distinguish why no data exists
  - Trade-offs:
    - ✅ Simple API contract
    - ❌ Poor user experience (no explanation)
    - ❌ Frontend shows "No data" without context

- **Option B: 200 OK with status metadata**
  - Impact: Response includes status field: `"status": "cold_start"`, `"status": "success"`, or `"status": "scraper_failure"`
  - Trade-offs:
    - ✅ Frontend can show appropriate message
    - ✅ Better debugging
    - ❌ Slightly more complex response
  - API Response:
    ```json
    {
      "manufacturer": "nvidia",
      "status": "cold_start",
      "lastUpdated": null,
      "lastAttemptedAt": "2025-01-10T02:00:00Z",
      "prices": []
    }
    ```

- **Option C: 503 Service Unavailable when no data exists**
  - Impact: Error status code until first scrape completes
  - Trade-offs:
    - ✅ Clear signal that service isn't ready
    - ❌ Breaks "200 OK with empty array" pattern from spec
    - ❌ Requires error handling in frontend

**Recommendation for MVP**: **Option B (status metadata in 200 OK)**. Maintains the 200 OK pattern from spec while giving frontend enough information to display helpful messages like "Data updating, check back in a few minutes" vs "System error, contact support".

---

## HIGH Priority Questions

These affect major workflows but have reasonable defaults.

### Q6: Should outlier filtering (>2 standard deviations) apply when there are only 2-3 listings?

**Context**: Spec says "Outlier filtering: Remove prices >2 standard deviations from median". Standard deviation is less meaningful with small sample sizes. If we only have 2 listings and they differ significantly, which is the outlier?

**Example**:
- Scan: RTX 4090 = £1,599
- Ebuyer: RTX 4090 = £1,999 (pricing error or premium model?)
- Only 2 data points - standard deviation calculation might remove valid data

**Options**:

- **Option A: Only apply outlier filtering when 4+ listings exist**
  - Impact: Use all data when 2-3 listings, apply statistical filtering at 4+
  - Trade-offs:
    - ✅ Avoids false positives with small samples
    - ❌ Pricing errors can skew average when few listings

- **Option B: Use percentage-based outlier detection for small samples**
  - Impact: If 2-3 listings, remove any price >30% different from median
  - Trade-offs:
    - ✅ Simple threshold-based filtering
    - ❌ Arbitrary 30% threshold needs tuning

- **Option C: Always apply statistical outlier filtering regardless of sample size**
  - Impact: Use 2-stdev rule even with 2 listings
  - Trade-offs:
    - ✅ Consistent algorithm
    - ❌ Statistically questionable with small N

**Recommendation for MVP**: **Option A (require 4+ listings for statistical filtering)**. With 2-3 listings, average them all and log for manual review if spread is >25%. Flag in monitoring: "High price variance for RTX 4090: £1,599-£1,999". Let product team review flagged cases and decide if manual intervention needed.

---

### Q7: How long should we wait before marking a scrape job as "failed" for a specific retailer?

**Context**: Spec mentions "3 attempts with exponential backoff" per scraper but doesn't specify timeouts. A slow-loading page could hang indefinitely.

**Options**:

- **Option A: 30-second timeout per request, 5-minute total per retailer**
  - Impact: Request fails if page doesn't load in 30s, entire retailer scrape fails if not complete in 5 min
  - Trade-offs:
    - ✅ Prevents jobs running forever
    - ✅ Reasonable for most retailers
    - ❌ Might be too aggressive for Amazon UK (heavy JS rendering)

- **Option B: 60-second timeout per request, 10-minute total per retailer**
  - Impact: More generous timeouts
  - Trade-offs:
    - ✅ Handles slow sites
    - ❌ Slow failures (10 min to detect retailer is down)

- **Option C: Configurable timeouts per retailer**
  - Impact: Settings: `{ "Scan": 30s, "Ebuyer": 30s, "Amazon": 90s }`
  - Trade-offs:
    - ✅ Optimized per retailer
    - ❌ More configuration complexity

**Recommendation for MVP**: **Option A (30s request, 5min total) with manual override capability**. Most sites load in <10s. 30s is generous. If Amazon proves problematic in testing, we can increase its timeout specifically, but start conservative to catch issues quickly.

---

### Q8: Should the API endpoint support filtering by stock status (in-stock only vs. all)?

**Context**: Spec shows API returns all GPUs with `inStock` boolean. Should frontend be able to request only in-stock items?

**Options**:

- **Option A: Always return all GPUs, frontend filters if needed**
  - Impact: API response includes out-of-stock items with `inStock: false`
  - Trade-offs:
    - ✅ Simple API
    - ✅ Frontend has full dataset flexibility
    - ❌ Wastes bandwidth if frontend only needs in-stock

- **Option B: Add optional `?inStock=true` query parameter**
  - Impact: `GET /api/v1/retail-prices?manufacturer=nvidia&inStock=true`
  - Trade-offs:
    - ✅ Efficient for in-stock-only use cases
    - ✅ Backward compatible (parameter is optional)
    - ❌ Slightly more complex API

**Recommendation for MVP**: **Option A (return all, frontend filters)**. The dataset is small (6-8 GPU models per manufacturer), so bandwidth isn't a concern. Keeps API simple. Can add filtering in v2 if performance becomes an issue.

---

### Q9: When multiple scrape attempts fail for a retailer, should we preserve the last successful data or clear it?

**Context**: If Scan's scraper fails for 3 consecutive days, should:
- Keep showing Scan's prices from 3 days ago in the average?
- Exclude Scan from average until it succeeds again?

**Options**:

- **Option A: Exclude retailer data from average after 24 hours of staleness**
  - Impact: If Scan data is >24h old, average only uses Ebuyer + Amazon
  - Trade-offs:
    - ✅ Average reflects current market (2 retailers)
    - ✅ Indicates data quality issue
    - ❌ Average becomes less reliable with fewer sources
  - Database: Track `LastSuccessfulScrapeAt` per retailer per model

- **Option B: Keep stale data in average with staleness indicator**
  - Impact: Include 3-day-old Scan price in average, show "Scan data from 3 days ago"
  - Trade-offs:
    - ✅ More data points in average
    - ❌ Might not reflect current pricing
    - ❌ Can skew average if price changed

- **Option C: Exclude retailer from average after 48 hours of staleness**
  - Impact: Grace period of 2 days before excluding
  - Trade-offs:
    - ✅ Balance between data freshness and stability
    - ❌ Still arbitrary threshold

**Recommendation for MVP**: **Option A (24-hour staleness threshold)**. Spec emphasizes "data freshness" and "prices updated regularly". If a retailer's scraper is broken for >24h, that's a data quality issue that should be flagged in monitoring. Average should only include recent data. Log exclusion: "Scan excluded from RTX 4090 average due to stale data (last scraped 3 days ago)".

---

## MEDIUM Priority Questions

Edge cases and polish items - can have sensible defaults if needed.

### Q10: Should we track and expose currency in the API response, or assume GBP?

**Context**: Spec focuses on UK retailers (£), but API response doesn't explicitly state currency.

**Options**:

- **Option A: Hardcode GBP, no currency field in API**
  - Impact: Assume all prices are £
  - Trade-offs:
    - ✅ Simple
    - ❌ If we expand to EU/US retailers later, need API change

- **Option B: Include currency in API response**
  - Impact: `"currency": "GBP"` in response
  - Trade-offs:
    - ✅ Explicit and future-proof
    - ❌ Trivial overhead

**Recommendation for MVP**: **Option B (include currency)**. Costs nothing to add `"currency": "GBP"` to response, makes API self-documenting, prevents assumptions. If we expand internationally later, API already supports it.

---

### Q11: Should admin users be able to manually trigger a scrape job on-demand, or is scheduled-only sufficient?

**Context**: Spec says scraping runs daily at 2:00 AM. If a retailer's site changes and scraper breaks, or if we deploy a scraper fix, do we wait until next scheduled run?

**Options**:

- **Option A: Scheduled-only (as spec describes)**
  - Impact: No manual trigger, wait for next 2 AM run
  - Trade-offs:
    - ✅ Simple implementation
    - ❌ Can't test scraper fixes immediately
    - ❌ Up to 24h delay for critical updates

- **Option B: Add admin endpoint to trigger scrape job**
  - Impact: `POST /api/v1/admin/scraper/trigger` (auth required)
  - Trade-offs:
    - ✅ Test scraper changes immediately
    - ✅ Recover from failures faster
    - ❌ Need admin authentication and endpoint

**Recommendation for MVP**: **Option B (add manual trigger endpoint)**. Hangfire makes this trivial (`BackgroundJob.Enqueue<RetailPriceScraperJob>()`). Critical for development and debugging. Protect with admin-only auth.

---

### Q12: Should we expose scraper health metrics via the API, or only in logs?

**Context**: Spec mentions `ScraperLog` table for monitoring but doesn't specify if this data is queryable by frontend.

**Options**:

- **Option A: Logs only (no API endpoint)**
  - Impact: Scraper status only visible in Application Insights / logs
  - Trade-offs:
    - ✅ Simple, no API needed
    - ❌ Frontend can't show "Data last updated 2 hours ago" with confidence

- **Option B: Add health check endpoint**
  - Impact: `GET /api/v1/scraper/health` returns last run status, success/failure per retailer
  - Trade-offs:
    - ✅ Frontend can display data quality indicators
    - ✅ Useful for monitoring dashboard
    - ❌ Another endpoint to maintain

**Recommendation for MVP**: **Option A (logs only), but include `lastUpdated` in existing API response**. The retail prices endpoint already returns `lastUpdated` timestamp per spec. Frontend can show "Prices updated 2 hours ago". Full scraper health dashboard is v2 feature. Keep it simple for now.

---

## Notes for Product

- **Open Questions in Spec**: The "Open Questions for Tech Lead" section contains implementation questions (scraper technology choices, CAPTCHA handling) that are engineering decisions, not product decisions. I can make those calls during implementation—no need for product input on headless browser vs HTTP client.

- **Data Storage Decision is Critical**: Q2 (individual listings vs aggregated only) significantly impacts future features. If we want to add "best price" or "price comparison" later, we need individual listings. Recommend deciding this now to avoid re-architecture.

- **Monitoring Strategy**: Spec mentions monitoring but doesn't specify SLAs. Do we need alerts if scraper fails? If so, what's the threshold (1 failure, 2 consecutive, 3+)? Can establish sensible defaults unless you have specific requirements.

- **MVP Scope Confirmation**: All questions above assume we're building the feature as specified. If any functionality (outlier filtering, parallel scraping, etc.) is negotiable for MVP, let me know and I can simplify recommendations.

---

**Once these questions are answered, I can proceed to implementation planning.**