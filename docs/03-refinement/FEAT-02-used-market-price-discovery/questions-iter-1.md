# Used Market Price Discovery - Technical Questions (Iteration 1)

**Status**: NEEDS CLARIFICATION
**Iteration**: 1
**Date**: 2025-01-10

---

## Summary

After reviewing the specification, I've identified **14** areas that need clarification before implementation can begin. These questions address:
- Web scraping compliance and technical approach
- Data reliability and quality thresholds
- Card model identification and maintenance
- Price calculation methodology
- User-facing data presentation
- System behavior during failures

---

## CRITICAL Questions

These block core implementation and must be answered first.

### Q1: What is our legal/compliance approach to marketplace scraping?

**Context**: The PRD acknowledges that "Facebook Marketplace scraping may violate ToS" and mentions potential IP blocks. This is a fundamental blocker—if we can't legally or technically scrape these sources, the entire feature cannot be implemented as specified. We need clarity on acceptable approaches before writing any scraper code.

**Options**:

- **Option A: Official APIs only (where available)**
  - Impact: CEX has no public API. eBay has official API (requires partner account). Facebook Marketplace has no official API for listing scrapes. Would need to drop Facebook and CEX entirely or find alternative approach.
  - Trade-offs: Legally safe, reliable data, but severely limits data sources (possibly only eBay)
  - Technical: Simple HTTP client with OAuth, rate limits handled by API provider
  
- **Option B: Scrape public pages with rate limiting and user agent rotation**
  - Impact: Can access all three sources, but risk of IP blocks, CAPTCHA challenges, and potential ToS violations
  - Trade-offs: Full data coverage, but requires ongoing maintenance as sites change HTML structure, risk of service disruption
  - Technical: Requires proxy rotation infrastructure, CAPTCHA solving service, robust error handling
  
- **Option C: Hybrid approach (API where available, scraping for others with acceptance of risk)**
  - Impact: Use eBay API officially, scrape CEX/Facebook with awareness of ToS risk
  - Trade-offs: Balanced approach, but partial compliance risk remains
  - Technical: Two implementation paths (API client + scraper)
  
- **Option D: Manual price entry or crowdsourced data**
  - Impact: No automated scraping; admin or users manually submit prices they see
  - Trade-offs: Eliminates legal risk but removes automation value, data freshness suffers
  - Technical: Simple CRUD, but requires admin UI or user submission workflow

**Recommendation for MVP**: **Option C** (Hybrid approach). Use eBay's official API (most reliable marketplace), accept calculated risk for CEX scraping (small UK retailer, public pricing pages), and **drop Facebook Marketplace** for v1 (highest ToS violation risk, most aggressive anti-scraping). Two sources (eBay + CEX) still provide meaningful market data. Can revisit Facebook if feature proves valuable and we can negotiate API access or find compliant alternative.

---

### Q2: What is the minimum number of listings required to display a price?

**Context**: PRD says "If fewer than 3 listings remain after filtering, mark price as 'Insufficient data'". However, this creates an inconsistent user experience. If we scrape 10 listings but 8 are outliers (leaving 2), do we hide the price? What about cards that genuinely have low market availability (e.g., only 4-5 total listings exist)?

**Options**:

- **Option A: Strict minimum of 3 listings (as stated in PRD)**
  - Impact: Display "Insufficient data" for any card with <3 listings after outlier filtering
  - Trade-offs: Conservative (avoids misleading users with 1-2 data points), but many rare/older cards will show no price even if legitimate listings exist
  - UI: User sees "Insufficient data - only 2 listings found"
  
- **Option B: Display price with confidence indicator (1-2 listings = "Low confidence", 3-5 = "Medium", 6+ = "High")**
  - Impact: Show all prices but flag data quality with badge/icon
  - Trade-offs: More transparent, gives users choice to trust data or not, but requires UI design for confidence display
  - UI: "£480 (Low confidence - 2 listings)" or similar badge system
  
- **Option C: Minimum of 2 listings (looser threshold)**
  - Impact: Display price if at least 2 listings remain after filtering
  - Trade-offs: Provides data for more cards, but 2-listing average is less reliable
  - UI: Standard price display, no special indication
  
- **Option D: Always display if at least 1 listing exists, but show listing count prominently**
  - Impact: Never hide price; always show count (e.g., "£480 based on 1 listing")
  - Trade-offs: Maximum transparency, user makes judgment, but single listing isn't really an "average"
  - UI: "£480 (1 listing found)" - user clearly sees it's not a true market average

**Recommendation for MVP**: **Option B** (Display price with confidence indicator). This provides maximum value to users—they see the data but understand its reliability. Someone researching a rare card (e.g., RTX 3090 Ti 24GB) would rather see "£680 - Low confidence, 2 listings" than "Insufficient data". Implement as:
- 1-2 listings: Show price with "⚠️ Low confidence" badge
- 3-5 listings: Show price with "Medium confidence" (or no badge)
- 6+ listings: Show price with "✓ High confidence"

---

### Q3: How do we identify and normalize GPU models from listing titles?

**Context**: PRD mentions maintaining a "lookup table of known GPU models with aliases" but doesn't specify the source of truth or maintenance workflow. This is critical—misidentifying a card means incorrect price aggregation (e.g., mixing RTX 4070 and 4070 Ti prices).

**Options**:

- **Option A: Hardcoded mapping in scraper code**
  - Impact: Model aliases stored as const dictionaries in C# scraper service
  - Trade-offs: Simple for v1, but requires code deployment to add new cards
  - Maintenance: Engineer updates code when new GPU releases, redeploys service
  
- **Option B: Database table (GpuModelAlias) with admin UI for editing**
  - Impact: Aliases stored in database, admin can add/edit via backoffice UI
  - Trade-offs: More flexible, non-engineers can maintain, but requires admin UI build
  - Maintenance: Admin user adds aliases when new cards release or scraping misses models
  
- **Option C: External reference file (JSON/YAML in repo, loaded at startup)**
  - Impact: Model aliases in `gpu-models.json`, read on service startup
  - Trade-offs: Easy to edit (just commit to repo), no UI needed, but requires restart to pick up changes
  - Maintenance: Engineer or PM edits JSON file, commits, redeploys service
  
- **Option D: Hybrid - seed database from JSON, allow runtime edits via admin UI**
  - Impact: Initial models from `gpu-models.json` on first run, then editable via admin panel
  - Trade-offs: Best of both worlds (version control + flexibility), but more complex initial setup
  - Maintenance: JSON for major updates, admin UI for quick fixes

**Sub-question: Where do we get the canonical list of GPU models?**
- Scrape from manufacturer websites (Nvidia/AMD)?
- Maintain manually based on TechPowerUp GPU database?
- Use an existing public API (e.g., TechPowerUp API if available)?

**Recommendation for MVP**: **Option C** (JSON reference file). Start with a manually curated `gpu-models.json` containing aliases for target cards (RTX 30/40-series, RX 6000/7000-series). Source the initial list from TechPowerUp GPU Database (manually extracted). This avoids building an admin UI for v1 while keeping aliases easy to update. If maintenance becomes burdensome, upgrade to Option D in v2.

Example JSON structure:
```json
{
  "models": [
    {
      "canonical_name": "RTX 4070 Ti",
      "vram": 12,
      "aliases": ["4070 Ti", "4070TI", "4070-Ti", "RTX4070Ti"],
      "manufacturer": "Nvidia"
    }
  ]
}
```

---

### Q4: What happens when all three (or two, per Q1 recommendation) marketplaces fail to scrape?

**Context**: PRD says "If scraping job fails entirely, retain previous day's data but mark with warning: 'Data is [X] days old'". However, this doesn't define "fails entirely" or specify staleness thresholds.

**Options**:

- **Option A: Retain data indefinitely until successful scrape**
  - Impact: If scraping breaks for a week, 7-day-old data still displays with warning
  - Trade-offs: Users always see something, but stale data could be misleading
  - UI: "⚠️ Used prices are 7 days old. Update in progress."
  
- **Option B: Hide data after 3 days of failed scrapes**
  - Impact: After 72 hours with no successful scrape, display "Data temporarily unavailable"
  - Trade-offs: Protects users from stale data, but feature becomes unavailable during extended outages
  - UI: "Used market data temporarily unavailable. Check back later."
  
- **Option C: Hide data after 7 days (matches "no listings found" threshold)**
  - Impact: Stale data expires after 1 week, consistent with listing age threshold
  - Trade-offs: Longer grace period, but week-old data is quite stale for fast-moving market
  - UI: Similar to Option B, but 7-day threshold
  
- **Option D: Show stale data but disable price comparisons**
  - Impact: Display old prices with prominent warning, but hide value comparison features (inverting price delta, etc.)
  - Trade-offs: Users can still reference historical data, but feature degradation is clear
  - UI: "⚠️ Prices shown are 5 days old. Value comparisons disabled until data refreshes."

**Recommendation for MVP**: **Option B** (Hide data after 3 days). Used GPU prices can shift quickly, especially around new releases or cryptocurrency mining trends. 3-day-old data is acceptable with a warning, but beyond that we risk showing prices that don't reflect current market. If scraping is broken for 3+ days, that's a critical incident requiring immediate fix—hiding the feature creates appropriate urgency.

---

### Q5: How do we handle VRAM size mismatches between listing and known model specs?

**Context**: PRD states "If model lookup says '4070 is 12GB' but listing says '16GB', trust model lookup and discard listing". However, some cards exist in multiple VRAM variants (e.g., RTX 4060 Ti has 8GB and 16GB SKUs). How do we distinguish between seller error and legitimate variant?

**Options**:

- **Option A: Strict validation - discard any listing where VRAM doesn't match model spec**
  - Impact: Discard listing if extracted VRAM doesn't match canonical model VRAM from lookup table
  - Trade-offs: Filters out seller errors/typos, but also discards valid listings for multi-VRAM variants if our lookup table doesn't include all variants
  - Data quality: High precision, but potential for false negatives
  
- **Option B: Allow VRAM variance for known multi-variant models**
  - Impact: Lookup table includes multiple entries for same base model (e.g., "4060 Ti 8GB" and "4060 Ti 16GB" as separate models)
  - Trade-offs: Captures legitimate variants, but requires comprehensive lookup table maintenance
  - Data quality: Better recall, treats variants as distinct models (which they are for pricing)
  
- **Option C: Accept any VRAM claim if it meets minimum threshold (16GB+), validate model only**
  - Impact: If listing says "4070 Ti 16GB" and model lookup confirms "4070 Ti" exists, accept it even if spec says 12GB
  - Trade-offs: Maximizes data capture, but risks mixing incorrect VRAM claims into averages
  - Data quality: Lower precision, relies on outlier filter to catch obviously wrong prices
  
- **Option D: Log mismatch but include listing with canonical VRAM (override listing claim)**
  - Impact: If listing says "4070 12GB" but model is actually 16GB, store as 16GB listing
  - Trade-offs: Corrects seller errors, but assumes our lookup table is always correct
  - Data quality: Risky if lookup table is wrong

**Recommendation for MVP**: **Option B** (Treat VRAM variants as separate models). This is the most accurate approach. The lookup table should explicitly list each VRAM variant as a distinct model:
- "RTX 4060 Ti 8GB" (excluded - below 16GB threshold)
- "RTX 4060 Ti 16GB" (included)
- "RTX 4070 Ti 12GB" (excluded)

When parsing listings, match against both model name AND VRAM. If listing says "4060 Ti 16GB", only match to the 16GB variant entry. If listing says "4060 Ti" without VRAM, try to extract VRAM from elsewhere in description; if unable, discard. This prevents mixing 8GB and 16GB 4060 Ti prices (which would be incorrect—they're different products with different values).

---

### Q6: What is the outlier filtering methodology when listing count is low?

**Context**: PRD defines outliers as ">2x or <0.5x the median". However, with small sample sizes (e.g., 4 listings), a single outlier can skew the median itself. Should outlier detection adapt based on sample size?

**Options**:

- **Option A: Fixed threshold (2x/0.5x median) regardless of sample size**
  - Impact: Always use 2x/0.5x rule, even if only 4 listings exist
  - Trade-offs: Simple, consistent, but may not catch outliers effectively in small samples
  - Example: 4 listings at £400, £420, £440, £1200 → median is £430, outlier is £1200 (>2x)
  
- **Option B: Stricter threshold for small samples (1.5x/0.67x for <5 listings)**
  - Impact: Use tighter bounds when fewer listings exist to be more conservative
  - Trade-offs: More aggressive filtering for small samples, reduces risk of skew
  - Example: Same 4 listings → median £430, outlier threshold is £645 (1.5x), so £1200 still filtered
  
- **Option C: Use IQR (interquartile range) method instead of median multiplier**
  - Impact: Calculate Q1/Q3, flag values outside 1.5×IQR range as outliers
  - Trade-offs: Statistically more robust, but more complex calculation and harder to explain to users
  - Example: Standard box plot outlier detection used in data science
  
- **Option D: No outlier filtering if fewer than 5 listings**
  - Impact: Below 5 listings, calculate average from all listings (no filtering)
  - Trade-offs: Avoids over-filtering small samples, but risks including genuine outliers
  - Example: 3 listings at £400, £420, £1500 → average includes £1500

**Recommendation for MVP**: **Option A** (Fixed threshold with existing minimum listing count rule). The PRD already addresses small samples by requiring minimum 3 listings (per Q2). If we implement Q2's confidence indicator, users will know when data is based on few listings. Keep the 2x/0.5x rule simple and consistent—it's easy to explain and understand. If we see problematic outliers in production, we can revisit with more sophisticated statistical methods in v2.

---

## HIGH Priority Questions

These affect major workflows but have reasonable defaults.

### Q7: Should we store historical scraping data or only keep the latest snapshot?

**Context**: PRD says "Listings older than 30 days can be purged" and notes "history may be preserved for future trend analysis but is not required for v1". However, this affects database design decisions now (even if we don't expose trends in UI yet).

**Options**:

- **Option A: Store only latest scrape (delete old listings on each run)**
  - Impact: Database only contains most recent 24 hours of listings
  - Trade-offs: Minimal storage, simple queries, but historical data is permanently lost
  - Database: Simple schema, no time-series considerations
  
- **Option B: Retain 30 days of listings for debugging/auditing**
  - Impact: Keep listings for 30 days, then purge via cleanup job
  - Trade-offs: Enables debugging ("Why did price spike last Tuesday?"), moderate storage cost
  - Database: Add indexed `scraped_at` column, scheduled cleanup job
  
- **Option C: Archive to cold storage (blob storage) after 30 days**
  - Impact: Active database has 30 days, older data exported to JSON in blob storage
  - Trade-offs: Preserves data for potential future trend features, but requires export job
  - Database: Same as Option B + export mechanism
  
- **Option D: Store historical averages only (not individual listings)**
  - Impact: After calculating daily average, discard individual listings; keep only the `UsedPriceAverage` records over time
  - Trade-offs: Very low storage, enables basic trend graphs later, but can't re-calculate averages with different methodology
  - Database: `UsedPriceAverage` includes `CalculatedAt` date, multiple records per model

**Recommendation for MVP**: **Option D** (Store historical averages only). Keep individual `UsedListing` records for 7 days for debugging purposes (allows investigation of calculation issues), then discard. Preserve all `UsedPriceAverage` records indefinitely (cheap storage, enables v2 trend features). This gives us:
- Short-term debugging capability (7 days of raw listings)
- Long-term trend data (historical averages)
- Reasonable storage costs
- No need to build archive infrastructure yet

---

### Q8: How do we handle currency conversion if non-GBP listings appear?

**Context**: PRD says "If a listing is in EUR or USD, convert using daily exchange rate or discard". UK sites should only show GBP, but edge cases exist (international sellers, site bugs). This needs a concrete decision.

**Options**:

- **Option A: Discard all non-GBP listings**
  - Impact: Simple validation: if currency != GBP, skip listing
  - Trade-offs: No conversion logic needed, but might lose legitimate UK listings priced in EUR/USD
  - Implementation: Currency regex check during scraping
  
- **Option B: Convert using daily exchange rate from public API**
  - Impact: Call currency API (e.g., exchangerate-api.io) daily, store rates, convert prices
  - Trade-offs: Handles edge cases gracefully, but adds external dependency and conversion errors
  - Implementation: Scheduled job fetches rates, converter service applies during scraping
  
- **Option C: Convert using hardcoded exchange rates (updated monthly)**
  - Impact: Manually update EUR/USD rates in config once per month
  - Trade-offs: Simple, no external API, but rates become stale quickly
  - Implementation: AppSettings with exchange rates, manual update process

**Recommendation for MVP**: **Option A** (Discard non-GBP). UK marketplace sites (eBay UK, CEX UK) should only show GBP prices. If we encounter EUR/USD, it's likely an edge case (international seller mistake) or scraping error. Discard and log for investigation. This avoids adding exchange rate infrastructure for what should be <1% of listings. If we see significant non-GBP listings in production logs, revisit with Option B.

---

### Q9: Should scraping run at a fixed time (3 AM) or on a rolling 24-hour interval?

**Context**: PRD specifies "Background job runs daily at 3:00 AM UTC". However, if the 3 AM job fails (marketplace downtime, deployment, etc.), the next attempt is 24 hours away. Should we have retry logic?

**Options**:

- **Option A: Fixed daily schedule (3 AM UTC), no automatic retries**
  - Impact: Hangfire recurring job runs once per day at 3 AM
  - Trade-offs: Simple, predictable, but single failure means stale data for 24 hours
  - Failure handling: Manual intervention or wait until next day
  
- **Option B: Fixed schedule with automatic retry (6 AM, 9 AM if 3 AM fails)**
  - Impact: Primary job at 3 AM; if it fails, automatic retry jobs at 6 AM and 9 AM
  - Trade-offs: Better reliability, but could mask systemic issues if failures are frequent
  - Failure handling: Up to 3 attempts per day
  
- **Option C: Rolling 24-hour interval (24 hours after last successful scrape)**
  - Impact: Schedule next job 24 hours after completion of current job
  - Trade-offs: Ensures scrape happens every 24 hours even if timing drifts, but time becomes unpredictable
  - Failure handling: Retries sooner if failure detected
  
- **Option D: Fixed schedule + manual "Scrape Now" button in admin UI**
  - Impact: Primary job at 3 AM, but admin can trigger immediate scrape via backoffice UI
  - Trade-offs: Gives ops team control, no automatic retries (relies on monitoring alerts)
  - Failure handling: Admin sees alert → clicks button

**Recommendation for MVP**: **Option D** (Fixed schedule + manual trigger). Scheduled job runs at 3 AM UTC (low traffic time). If it fails, monitoring alerts ops team, who can manually trigger via admin panel. This avoids complexity of automatic retry logic while giving team control. Requirements for implementation:
- Hangfire recurring job: `0 3 * * *` (3 AM daily)
- Admin backoffice page with "Scrape Used Market Prices Now" button
- Button triggers same scraper job manually
- Prevent concurrent runs (check if scrape already in progress)

---

### Q10: How granular should source breakdown be in the UI?

**Context**: PRD says user can "hover/click to see source breakdown (e.g., '3 eBay, 4 Facebook, 1 CEX')". This affects data storage and UI design.

**Options**:

- **Option A: Store aggregated counts per source in UsedPriceAverage table**
  - Impact: `SourceBreakdown` JSON field stores `{"eBay": 3, "CEX": 1}`
  - Trade-offs: Simple, lightweight, but can't reconstruct which specific listings contributed
  - UI: Tooltip shows counts per source
  
- **Option B: Store listing IDs per source (allows drill-down to individual listings)**
  - Impact: `UsedPriceAverage` references list of `UsedListing` IDs grouped by source
  - Trade-offs: Enables detailed audit trail, but requires keeping listing records longer
  - UI: User could theoretically click through to see individual listing details
  
- **Option C: Don't show source breakdown at all (just total count)**
  - Impact: UI only shows "Based on 8 listings" without source split
  - Trade-offs: Simpler implementation, but less transparency for users
  - UI: Single count, no hover/tooltip

**Recommendation for MVP**: **Option A** (Store aggregated counts per source). This provides the transparency mentioned in PRD without overcomplicating. Structure:

```json
{
  "average_price": 480,
  "listing_count": 8,
  "source_breakdown": {
    "eBay": 5,
    "CEX": 3
  },
  "calculated_at": "2025-01-10T03:15:00Z"
}
```

UI shows: "£480 avg. (8 listings)" with tooltip on hover: "5 from eBay, 3 from CEX". User understands data diversity without overwhelming detail.

---

### Q11: What defines a "target card model" for scraping?

**Context**: PRD says scraping focuses on "16GB+ VRAM cards from the previous 2-3 generations". However, this doesn't provide a concrete list. Do we scrape ALL cards meeting these criteria, or a curated subset?

**Options**:

- **Option A: Scrape all cards in the GPU model lookup table (comprehensive)**
  - Impact: Every card in `gpu-models.json` (or database) is scraped
  - Trade-offs: Maximum coverage, but longer scrape times and more API calls
  - Scope: Could be 50-100 different card models
  
- **Option B: Scrape only cards tracked in the main GPU Value Tracker feature**
  - Impact: Only scrape cards that are already in the "new retail price" tracking system
  - Trade-offs: Ensures consistency (same cards in both views), but limits used market data
  - Scope: Depends on Feature 1 scope
  
- **Option C: Scrape a curated "popular cards" list (top 20-30 models)**
  - Impact: Manually curate list of most common used market cards (e.g., RTX 3080, 4070, 7900 XT)
  - Trade-offs: Faster scraping, focuses on high-volume market, but excludes rare/older cards
  - Scope: 20-30 models
  
- **Option D: Dynamic scraping based on retail price data availability**
  - Impact: If we have retail price for a card (from Feature 1), scrape used prices for it
  - Trade-offs: Ensures parity between features, but couples them tightly
  - Scope: Matches Feature 1 exactly

**Recommendation for MVP**: **Option D** (Dynamic based on retail price data). The value of this feature is in comparing used vs. new prices (as stated in PRD: "compare used prices for previous-generation cards against new latest-gen cards"). If a card doesn't have retail price data, showing used price in isolation is less useful. Scrape used prices for any card where we successfully track new retail prices. This ensures:
- Consistent card coverage across dashboard
- Every used price can be compared to a retail price
- No wasted scraping effort on cards we can't fully analyze

---

## MEDIUM Priority Questions

Edge cases and polish items - can have sensible defaults if needed.

### Q12: How do we handle duplicate listings from the same seller across platforms?

**Context**: PRD acknowledges "Same seller may post the same card on eBay and Facebook" and states "No de-duplication in v1". However, should we log these for future improvement, or truly ignore?

**Options**:

- **Option A: No duplicate detection at all (as per PRD)**
  - Impact: Accept that some cards may be counted twice if seller cross-posts
  - Trade-offs: Simplest implementation, but listing count may be inflated
  - Implementation: None required
  
- **Option B: Log potential duplicates without filtering**
  - Impact: If same price appears across sources within same scrape run, log as "potential duplicate" but include both
  - Trade-offs: Creates data for future analysis, minimal implementation cost
  - Implementation: Simple duplicate detection query after scrape, log results
  
- **Option C: De-duplicate based on exact price match across sources**
  - Impact: If eBay and CEX both have "£485 RTX 4070 Ti", assume duplicate and keep only one
  - Trade-offs: Reduces false inflation, but risks filtering legitimate same-price listings from different sellers
  - Implementation: Group by (CardModel, Price) after scraping, keep first occurrence

**Recommendation for MVP**: **Option A** (No duplicate detection). PRD explicitly accepts this trade-off. Cross-posting is likely uncommon (most sellers pick one platform), and outlier filtering will handle cases where duplicates skew the average. If monitoring shows this is a significant problem (e.g., >20% of listings appear to be duplicates), revisit in v2 with Option B (logging) to gather data for smarter de-duplication.

---

### Q13: Should we expose individual listing URLs (even though PRD says no linking)?

**Context**: PRD states "No clickable links to eBay/Facebook/CEX listings" to avoid "legal/affiliate questions". However, storing URLs for admin debugging is different from displaying them to users.

**Options**:

- **Option A: Don't store listing URLs at all**
  - Impact: `UsedListing` table has no URL field
  - Trade-offs: Cleanest approach, no compliance concerns, but debugging is harder
  - Database: No URL column
  
- **Option B: Store URLs in database for admin debugging only (never exposed via API)**
  - Impact: Admin can view individual listing URLs in backoffice to investigate price anomalies
  - Trade-offs: Helps ops team debug, minimal risk if access controlled
  - Database: `listing_url` column, backoffice UI for admins only
  
- **Option C: Store URLs and expose via API, but don't render clickable in UI**
  - Impact: URLs available in API response but shown as plain text in UI
  - Trade-offs: Maximum flexibility, but risk of users copying/sharing links (which might create affiliate concerns)
  - Database: `listing_url` column, included in API response

**Recommendation for MVP**: **Option B** (Store URLs for admin only). Capture `listing_url` during scraping and store in database. This enables:
- Admin investigating "Why was this listing marked as an outlier?"
- Debugging scraper accuracy ("Did we extract the right price from this eBay listing?")
- Future v2 features if compliance concerns are resolved

Never expose URLs via public API. Admin-only backoffice access doesn't create affiliate/linking issues. This gives us debugging capability without user-facing complexity.

---

### Q14: What validation rules apply to scraped price data?

**Context**: PRD doesn't specify bounds checking for prices. Should we validate that extracted prices are reasonable before storing?

**Options**:

- **Option A: No validation - store all extracted prices**
  - Impact: Trust scraper extraction completely; outlier filter handles bad data
  - Trade-offs: Simple, but risks storing obviously wrong values (e.g., £0.01, £999,999)
  - Data quality: Relies entirely on outlier filter
  
- **Option B: Sanity check - discard prices outside realistic range (£50 - £5000)**
  - Impact: If extracted price is <£50 or >£5000, discard listing as extraction error
  - Trade-offs: Filters obvious scraping bugs, but hardcoded bounds may need adjustment
  - Data quality: Prevents garbage data from entering database
  
- **Option C: Validate against known MSRP (e.g., used price shouldn't exceed new MSRP)**
  - Impact: Cross-reference extracted price against retail price data; discard if used > new
  - Trade-offs: Smart validation, but requires coupling to retail price feature
  - Data quality: Catches listings where seller is asking more than new price (scam or error)

**Recommendation for MVP**: **Option B** (Sanity check with realistic bounds). Validate extracted prices are within £50-£5000 range. GPUs below £50 are likely extraction errors (scraped wrong element, currency issue). GPUs above £5000 are likely typos or commercial bulk listings. This prevents obviously bad data from entering the system. Bounds can be adjusted if we add very high-end cards (e.g., RTX 6000 Ada) in future. Log discarded listings so we can review if bounds are too strict.

---

## Notes for Product

- **Q1 (scraping compliance) is the critical blocker** - recommend starting with eBay API + CEX scraping, dropping Facebook for v1
- Several questions (Q3, Q11) depend on knowing the scope of Feature 1 (retail price tracking) - if you have that PRD, sharing it would help refine these questions
- Q5 (VRAM variants) and Q3 (model lookup) are closely related - decision on one affects the other
- Willing to do iteration 2 once you've answered these questions, especially if answers to Q1/Q3/Q11 raise new technical considerations

---

**Once these 14 questions are answered, I can proceed to validate the technical feasibility and mark ready for engineering specification.**