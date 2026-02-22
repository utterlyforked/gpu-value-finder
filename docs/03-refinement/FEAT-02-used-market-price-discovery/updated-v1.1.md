# Used Market Price Discovery - Product Requirements (v1.1)

**Version History**:
- v1.0 - Initial specification (2025-01-10)
- v1.1 - Iteration 1 clarifications (2025-01-10) - Added: Scraping compliance approach, data quality thresholds, model identification methodology, failure handling, VRAM variant handling, outlier filtering details, data retention strategy, currency handling, scheduling approach, UI transparency, card scope definition, duplicate handling, URL storage policy, price validation

---

## Feature Overview

Used Market Price Discovery tracks average asking prices for used GPUs across secondary marketplaces (eBay UK and CEX UK) to establish fair market value baselines for pre-owned graphics cards. This feature enables PC builders to identify genuine bargains by comparing used prices against new retail prices and spotting value inversions where previous-generation cards offer better performance-per-pound than latest releases.

The feature focuses exclusively on 16GB+ VRAM cards from the previous 2-3 generations (not just the latest), giving users visibility into the used market depth. By calculating average prices from active listings and filtering outliers, the system provides reliable price targets that builders can use when negotiating used purchases or evaluating marketplace listings.

This is not a marketplace or buying platform—it's market intelligence. Users see "the going rate" for a used RTX 4070 Ti or RX 7800 XT, then use that information to evaluate deals they find themselves on eBay or CEX.

**v1.1 Update**: Implementation will use eBay's official API and CEX web scraping (with acknowledged ToS risk). Facebook Marketplace is excluded from v1 due to compliance concerns and aggressive anti-scraping measures.

---

## User Stories

- As a PC builder, I want to see the current average asking price for used GPUs on the secondary market so that I can identify fair market value
- As a value-conscious builder, I want to compare used prices for previous-generation cards against new latest-gen cards so that I can spot value inversions
- As a bargain hunter, I want to see price trends for specific used card models so that I know when I'm looking at a good deal
- As a used-hardware buyer, I want to see how many listings were found for each card model so that I can gauge market availability and confidence in the average price
- As a researcher, I want to know when used price data was last updated so that I can trust the information is current
- **[v1.1]** As a user viewing low-availability cards, I want to see a confidence indicator showing data reliability so that I can judge whether to trust prices based on 1-2 listings versus 10+ listings

---

## Acceptance Criteria (UPDATED v1.1)

- System retrieves asking prices from eBay UK (via official API) and CEX UK (via web scraping) for GPUs with 16GB VRAM or larger
- **[v1.1]** Facebook Marketplace is explicitly excluded from v1 due to ToS compliance concerns
- Average used price is calculated per card model based on active listings across both sources
- Used prices are tracked for cards that also have retail price data (ensuring comparison capability)
- **[v1.1]** VRAM variants are treated as separate models (e.g., RTX 4060 Ti 8GB vs 16GB are distinct entries)
- Prices are refreshed daily at 3:00 AM UTC via Hangfire scheduled job, with manual trigger available in admin backoffice
- Outliers (listings priced >2x or <0.5x the median for that model) are filtered from average calculation
- **[v1.1]** Prices outside £50-£5000 range are discarded as extraction errors
- Used prices are stored and displayed separately for Radeon and Nvidia architectures (never mixed)
- Each card's used price data includes:
  - Average asking price (£)
  - Number of active listings found
  - **[v1.1]** Confidence indicator (Low: 1-2 listings, Medium: 3-5, High: 6+)
  - Timestamp of last data refresh
  - Individual source contributions (e.g., "5 listings from eBay, 2 from CEX")
- **[v1.1]** If data is >3 days old due to scraping failures, hide used prices and display "Data temporarily unavailable"
- **[v1.1]** All prices must be in GBP; non-GBP listings are discarded
- System handles scraping failures gracefully (e.g., CEX down doesn't block eBay data)

---

## Detailed Specifications (UPDATED v1.1)

### **Data Source Strategy (Scraping Compliance)**

**Decision**: Hybrid approach using eBay official API + CEX web scraping. Facebook Marketplace excluded from v1.

**Rationale**: 
- **eBay API**: Provides legally compliant, reliable access to UK marketplace data. Requires eBay Partner Network account but eliminates ToS violation risk and anti-scraping challenges.
- **CEX Scraping**: CEX is a UK-based retailer with public pricing pages. Accept calculated ToS risk given small scale and public data nature. Implement respectful scraping (rate limiting, robots.txt compliance).
- **Facebook Marketplace Exclusion**: Aggressive anti-scraping measures, no official API for listing data, highest ToS violation risk. Two sources (eBay + CEX) provide sufficient market coverage for v1. Can revisit if feature proves valuable and API access becomes available.

**Implementation**:
- **eBay Integration**:
  - Use eBay Finding API (specifically `findItemsAdvanced` operation)
  - Register for eBay Developer account and obtain API credentials
  - OAuth 2.0 authentication with application token
  - Filter: `itemFilter=ListingType:FixedPrice` (Buy It Now only, no auctions)
  - Filter: `itemFilter=Condition:Used`
  - Filter: `itemFilter=Location:GB` (UK listings only)
  - Rate limit: Respect eBay's 5,000 calls/day limit (sufficient for daily scraping of ~50 models)
  
- **CEX Integration**:
  - HTTP client scraping of CEX search results pages
  - User-Agent: Identify as bot, respect robots.txt
  - Rate limiting: Minimum 3-second delay between requests
  - Parse HTML using AngleSharp or HtmlAgilityPack
  - Target URL pattern: `https://uk.webuy.com/search?stext=[MODEL]&section=computing-graphics-cards`
  - Handle pagination if search results exceed one page

**Edge Cases**:
- **eBay API rate limit hit**: Log warning, complete scrape with available data, alert ops team
- **CEX blocking/CAPTCHA**: Fail CEX scrape gracefully, continue with eBay data only, alert ops team
- **eBay API credentials invalid**: Critical failure - alert immediately, cannot proceed without eBay data

**Future Considerations (v2)**:
- Investigate Facebook Marketplace Graph API access (requires business verification)
- Consider Gumtree UK if market coverage insufficient
- Monitor eBay API costs if usage scales beyond free tier

---

### **Data Quality Thresholds (Minimum Listing Requirements)**

**Decision**: Display all prices with confidence indicators. Never hide data if at least 1 listing exists.

**Rationale**: 
Users researching rare or older cards (e.g., RTX 3090 Ti 24GB, RX 6950 XT) benefit more from seeing "£680 - Low confidence (2 listings)" than "Insufficient data". Transparency allows user judgment. Someone willing to buy a niche used card understands market is thin—they want any signal, not silence.

Conservative "minimum 3 listings" threshold would hide too much valuable data. Confidence indicators preserve transparency while setting expectations.

**Confidence Levels**:
- **Low Confidence** (1-2 listings): "⚠️ Low confidence - only [N] listing(s) found"
  - UI: Yellow/orange badge or icon
  - Tooltip: "Limited data available. Price may not reflect broader market."
  
- **Medium Confidence** (3-5 listings): No special badge (neutral state)
  - UI: Standard display
  - Tooltip: "Based on [N] listings"
  
- **High Confidence** (6+ listings): "✓ High confidence - [N] listings"
  - UI: Green badge or checkmark icon
  - Tooltip: "Price based on multiple listings across sources."

**Implementation**:
```typescript
interface UsedPriceData {
  average_price: number;
  listing_count: number;
  confidence: 'low' | 'medium' | 'high';
  confidence_message: string;
  sources: { eBay: number; CEX: number };
}
```

**Behavior**:
- 1 listing: Show price with "Low confidence - 1 listing found"
- 2 listings: Show price with "Low confidence - 2 listings found"
- 3-5 listings: Show price with standard display (listing count visible)
- 6+ listings: Show price with "High confidence" indicator

**Edge Cases**:
- **Zero listings after outlier filtering**: Display "No recent listings found" (not "£0" or blank)
- **All listings filtered as outliers**: Display "Data quality insufficient - listings appear unreliable"

---

### **GPU Model Identification & Normalization**

**Decision**: JSON reference file (`gpu-models.json`) stored in repository, loaded at service startup. Source canonical model list from TechPowerUp GPU Database (manually curated).

**Rationale**:
- **JSON file over database**: Avoids building admin UI for v1 while keeping aliases easy to update via code commits. Engineers/PMs can edit JSON directly.
- **Startup loading**: Fast in-memory lookups during scraping, no database round-trips per listing.
- **TechPowerUp as source**: Comprehensive, community-maintained GPU specs database. Manual extraction for v1 (50-70 models); can automate in v2 if needed.
- **Version control benefits**: Changes to model aliases are tracked in Git, reviewable in PRs.

**JSON Structure**:
```json
{
  "version": "1.0",
  "last_updated": "2025-01-10",
  "models": [
    {
      "canonical_name": "RTX 4070 Ti",
      "vram_gb": 12,
      "manufacturer": "Nvidia",
      "excluded_reason": "Below 16GB threshold",
      "aliases": []
    },
    {
      "canonical_name": "RTX 4060 Ti 16GB",
      "vram_gb": 16,
      "manufacturer": "Nvidia",
      "aliases": [
        "4060 Ti 16GB",
        "4060Ti 16GB",
        "4060-Ti 16GB",
        "RTX4060Ti 16GB",
        "RTX 4060Ti 16 GB"
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
        "Radeon 7900 XT"
      ]
    }
  ]
}
```

**Matching Algorithm**:
1. Extract GPU model string from listing title/description (case-insensitive)
2. For each model in JSON, check if any alias matches (substring match)
3. If match found, extract VRAM from listing text
4. Validate VRAM matches model's `vram_gb` specification
5. If valid, store as `canonical_name + VRAM` (e.g., "RTX 4060 Ti 16GB")
6. If no match or VRAM mismatch, log as "unmatched listing" for review

**Handling VRAM Variants**:
- **Separate entries for each VRAM SKU**: "RTX 4060 Ti 8GB" and "RTX 4060 Ti 16GB" are distinct models
- **Explicit VRAM in listing required**: If listing says "4060 Ti" without VRAM, attempt to extract from description
- **Mismatch handling**: If listing claims "RTX 4070 16GB" but model spec says 12GB, **discard listing** (seller error or wrong model identification)
- **Example**: Listing "RTX 4060 Ti 16GB - £380" matches model "RTX 4060 Ti 16GB". Listing "RTX 4060 Ti - £320" without VRAM is discarded (cannot confirm variant).

**Unmatched Listings**:
- Log to separate table (`UnmatchedListing`) with: listing title, price, source, timestamp
- Admin can review weekly to improve aliases or add missing models
- Common unmatched patterns inform JSON updates

**Maintenance Workflow**:
1. New GPU releases: Engineer adds to `gpu-models.json`, commits to repo
2. Alias improvements: Review `UnmatchedListing` logs, update JSON with better aliases
3. Service restart: Redeploy service to load updated JSON (Kubernetes rolling update, zero downtime)

**Future Enhancement (v2)**:
If maintenance burden becomes high, migrate to database table with admin UI (Option D from questions). JSON can seed initial database on first run.

---

### **Scraping Schedule & Failure Handling**

**Decision**: Fixed daily schedule (3:00 AM UTC) with manual "Scrape Now" button in admin backoffice. No automatic retries.

**Rationale**:
- **3 AM UTC timing**: Low user traffic, avoids marketplace peak hours, completes before UK users wake up
- **Manual retry over automatic**: Automatic retries mask systemic issues (e.g., API credentials expired, site structure changed). Prefer monitoring alerts + human intervention to fix root cause.
- **Admin control**: Ops team can trigger immediate scrape if data is stale or after fixing scraper issues

**Implementation**:
- **Hangfire Recurring Job**: `RecurringJob.AddOrUpdate("scrape-used-prices", () => usedMarketScraperService.ScrapeAllMarketplaces(), "0 3 * * *");`
- **Admin Backoffice Page**: 
  - Display: Last scrape time, status (success/failure), listings found, errors
  - Button: "Scrape Used Market Prices Now"
  - Validation: Prevent concurrent runs (check if job already in progress)
  - Logging: Record manual trigger user + timestamp for audit trail
- **Monitoring**: 
  - Alert if daily scrape fails (Slack/email notification)
  - Dashboard widget showing scrape health (last success time, failure count)

**Behavior on Failure**:
- **Single source failure (e.g., CEX down, eBay succeeds)**: 
  - Complete scrape with available data
  - Store partial results (eBay listings only)
  - Calculate averages from available source
  - UI shows: "Based on 1 source (CEX unavailable)" in tooltip
  - Alert ops team: "CEX scrape failed - eBay data only"

- **Both sources fail (complete failure)**:
  - Retain previous day's data
  - Mark data as stale in database (`last_scrape_successful = false`)
  - UI displays warning if data >3 days old (see Data Freshness section)
  - Alert ops team: "CRITICAL: All used market scrapes failed"

**Manual Trigger Use Cases**:
- After fixing scraper bug: "We fixed the eBay auth issue, trigger scrape now"
- After adding new GPU models: "We added RTX 5000-series to JSON, scrape immediately"
- User reports stale data: Admin checks backoffice, sees last scrape failed, triggers retry

---

### **Data Freshness & Staleness Handling**

**Decision**: Hide used price data if >3 days old. Display "Data temporarily unavailable" instead of stale prices.

**Rationale**:
Used GPU market moves quickly, especially around:
- New GPU launches (prices for previous-gen cards drop)
- Cryptocurrency mining trends (demand spikes for high-VRAM cards)
- Holiday sales (retail prices drop, affecting used market psychology)

3-day-old data is acceptable with a warning (user understands "prices from Tuesday" on Thursday). Beyond 3 days, data is unreliable—showing stale prices risks users making poor purchasing decisions.

Hiding the feature during extended outages creates appropriate urgency for ops team to fix scraping issues (vs. letting stale data linger unnoticed).

**Implementation**:
```csharp
public class UsedPriceAverage
{
    public string CardModel { get; set; }
    public decimal AveragePrice { get; set; }
    public int ListingCount { get; set; }
    public DateTime CalculatedAt { get; set; }
    public bool IsStale => DateTime.UtcNow - CalculatedAt > TimeSpan.FromDays(3);
}
```

**UI Behavior**:
- **Data <24 hours old**: Standard display, no warning
  - "£480 avg. (8 listings) • Updated 6 hours ago"
  
- **Data 1-3 days old**: Display with warning badge
  - "⚠️ £480 avg. (8 listings) • Updated 2 days ago"
  - Tooltip: "Price data is 2 days old. May not reflect current market."
  
- **Data >3 days old**: Hide price, show unavailability message
  - "Used market data temporarily unavailable. Check back later."
  - Dashboard shows: "Last updated: 4 days ago (currently unavailable)"

**API Response**:
```typescript
interface UsedPriceResponse {
  card_model: string;
  is_available: boolean; // false if >3 days old
  average_price?: number; // null if unavailable
  listing_count?: number;
  calculated_at: string;
  staleness_warning?: 'fresh' | 'aging' | 'unavailable';
}
```

**Monitoring**:
- Daily check: If any card data is >2 days old, send warning to ops team
- Critical alert: If >50% of cards show "unavailable" (systemic scraping failure)

---

### **Outlier Filtering Methodology**

**Decision**: Fixed threshold (2x/0.5x median) regardless of sample size. Rely on confidence indicators to communicate small-sample limitations to users.

**Rationale**:
- **Simplicity**: Easy to explain and understand. "Listings priced more than 2x or less than 0.5x the median are excluded."
- **Consistency**: Same rule applies whether 3 listings or 30 listings exist
- **Confidence indicators already address small samples**: User sees "Low confidence - 2 listings" and understands data is limited
- **Avoids over-engineering**: Statistical methods like IQR are more complex to explain and implement for minimal gain in v1

**Algorithm**:
```csharp
public List<UsedListing> FilterOutliers(List<UsedListing> listings)
{
    if (listings.Count < 1) return new List<UsedListing>();
    
    // Calculate median
    var sortedPrices = listings.OrderBy(l => l.Price).ToList();
    decimal median;
    if (sortedPrices.Count % 2 == 0)
        median = (sortedPrices[sortedPrices.Count / 2 - 1].Price + 
                  sortedPrices[sortedPrices.Count / 2].Price) / 2;
    else
        median = sortedPrices[sortedPrices.Count / 2].Price;
    
    // Define bounds
    decimal lowerBound = median * 0.5m;
    decimal upperBound = median * 2.0m;
    
    // Filter
    var filtered = listings.Where(l => 
        l.Price >= lowerBound && l.Price <= upperBound
    ).ToList();
    
    // Log removed outliers
    var outliers = listings.Except(filtered);
    foreach (var outlier in outliers)
    {
        _logger.LogInformation(
            "Outlier removed: {Model} £{Price} (median: £{Median})",
            outlier.CardModel, outlier.Price, median
        );
    }
    
    return filtered;
}
```

**Examples**:
- **4 listings at £400, £420, £440, £1200**:
  - Median: £430
  - Bounds: £215 - £860
  - Filtered: £400, £420, £440 (£1200 excluded)
  - Average: £420
  - Confidence: Low (3 listings after filtering)

- **10 listings at £380, £400, £410, £420, £430, £440, £450, £460, £470, £2000**:
  - Median: £435
  - Bounds: £217.50 - £870
  - Filtered: All except £2000
  - Average: £428
  - Confidence: High (9 listings after filtering)

**Logging**:
- Log all removed outliers to `OutlierLog` table for review
- Include: listing URL, price, median, bounds, reason for removal
- Admin can review weekly to identify:
  - Scraping extraction errors (parsed wrong field)
  - Legitimate high-value listings (e.g., watercooled custom cards)
  - Scam listings (£10 RTX 4090)

**Future Enhancement (v2)**:
If production data shows outlier filter is too aggressive/lenient, can adjust thresholds or implement IQR method based on real-world data analysis.

---

### **Data Retention Strategy**

**Decision**: Store historical `UsedPriceAverage` records indefinitely (one per card per day). Keep individual `UsedListing` records for 7 days, then purge.

**Rationale**:
- **Individual listings (7-day retention)**: 
  - Purpose: Debugging scraper issues, investigating average calculation accuracy
  - Example: "Why did RTX 4070 Ti average jump £50 on Tuesday?" → Review individual listings from that scrape
  - Storage: ~50 cards × 10 listings/card × 7 days = 3,500 records (minimal storage cost)
  - Purge after 7 days: Old listings are irrelevant for debugging recent scrapes

- **Average price history (indefinite retention)**:
  - Purpose: Enables future trend analysis features (v2)
  - Example: "Show 90-day price trend for RTX 4070 Ti" → Query historical averages
  - Storage: ~50 cards × 365 days/year = 18,250 records/year (negligible storage cost)
  - Schema: `UsedPriceAverage` table has `CalculatedAt` date column, multiple rows per card

**Implementation**:
```csharp
// Daily cleanup job (runs after scrape completes)
public async Task PurgeOldListings()
{
    var cutoffDate = DateTime.UtcNow.AddDays(-7);
    var oldListings = await _context.UsedListings
        .Where(l => l.ScrapedAt < cutoffDate)
        .ToListAsync();
    
    _context.UsedListings.RemoveRange(oldListings);
    await _context.SaveChangesAsync();
    
    _logger.LogInformation(
        "Purged {Count} listings older than {Date}",
        oldListings.Count, cutoffDate
    );
}
```

**Database Schema**:
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
```

**Benefits**:
- **Debugging capability**: 7 days of raw data covers most incident investigation windows
- **Trend analysis readiness**: Historical averages enable v2 features without data backfill
- **Storage efficiency**: Purging individual listings prevents unbounded growth

---

### **Currency Handling**

**Decision**: Discard all non-GBP listings. No currency conversion in v1.

**Rationale**:
- **UK marketplace focus**: eBay UK and CEX UK should only show GBP prices. Non-GBP listings are edge cases (international seller mistakes, site bugs).
- **Avoid conversion complexity**: Exchange rate APIs add external dependency, conversion errors, and maintenance burden for <1% of listings.
- **Log for investigation**: If non-GBP listings appear frequently, logs will reveal the issue for future handling.

**Implementation**:
```csharp
public bool IsValidCurrency(string priceText)
{
    // Accept: "£480", "GBP 480", "480 GBP", "£480.00"
    var gbpPatterns = new[] { "£", "GBP" };
    var hasGbpIndicator = gbpPatterns.Any(p => 
        priceText.Contains(p, StringComparison.OrdinalIgnoreCase)
    );
    
    // Reject: "€480", "$480", "USD 480"
    var nonGbpPatterns = new[] { "€", "$", "USD", "EUR" };
    var hasNonGbpIndicator = nonGbpPatterns.Any(p => 
        priceText.Contains(p, StringComparison.OrdinalIgnoreCase)
    );
    
    if (hasNonGbpIndicator)
    {
        _logger.LogWarning(
            "Non-GBP listing discarded: {Price}",
            priceText
        );
        return false;
    }
    
    return hasGbpIndicator;
}
```

**Logging**:
- Log all non-GBP listings to `NonGbpListing` table for review
- Include: listing URL, price text, source, timestamp
- If >5% of listings are non-GBP, alert ops team (indicates scraping issue or site changes)

**Future Enhancement (v2)**:
If production logs show significant legitimate non-GBP listings (e.g., CEX showing EUR prices for EU customers on UK site), implement Option B from questions (daily exchange rate conversion using exchangerate-api.io).

---

### **Source Breakdown Transparency**

**Decision**: Store aggregated listing counts per source in `UsedPriceAverage` table. Display in UI tooltip on hover.

**Rationale**:
- **User transparency**: Users understand data diversity ("5 from eBay, 3 from CEX" is more trustworthy than "8 listings" from unknown sources)
- **Lightweight implementation**: JSON field in database, simple tooltip in UI
- **No drill-down needed for v1**: Detailed individual listing view is unnecessary complexity

**Database Schema**:
```sql
-- source_breakdown column (JSONB)
{
  "eBay": 5,
  "CEX": 3
}
```

**UI Implementation**:
```typescript
// Card display
<div className="used-price-card">
  <span className="price">£480 avg.</span>
  <span className="listing-count" title="5 from eBay, 3 from CEX">
    (8 listings)
    <InfoIcon />
  </span>
</div>

// Tooltip on hover/click
<Tooltip>
  <p>Based on 8 listings:</p>
  <ul>
    <li>5 from eBay UK</li>
    <li>3 from CEX UK</li>
  </ul>
  <p className="text-muted">Updated 6 hours ago</p>
</Tooltip>
```

**API Response**:
```typescript
interface UsedPriceData {
  average_price: number;
  listing_count: number;
  confidence: 'low' | 'medium' | 'high';
  sources: {
    eBay: number;
    CEX: number;
  };
  calculated_at: string;
}
```

**Edge Case - Single Source**:
If one source fails (e.g., CEX scrape error), source breakdown shows:
- `{ "eBay": 8, "CEX": 0 }`
- UI tooltip: "Based on 8 listings: 8 from eBay UK (CEX unavailable)"

---

### **Card Scope Definition (Target Models)**

**Decision**: Scrape used prices only for cards that have retail price data (from Feature 1). Dynamic scope based on retail price tracker.

**Rationale**:
- **Feature synergy**: The core value proposition is "compare used vs. new prices to find value inversions". If a card has no retail price data, showing used price alone is less useful.
- **Consistent dashboard**: User sees same cards in both "new retail" and "used market" views
- **Efficient scraping**: No wasted effort scraping cards we can't fully analyze
- **Automatic updates**: When new cards are added to retail tracker, they automatically appear in used tracker

**Implementation**:
```csharp
public async Task<List<GpuModel>> GetTargetModelsForUsedScraping()
{
    // Query cards from Feature 1 that:
    // 1. Have valid retail price data (not null, updated within 7 days)
    // 2. Have VRAM >= 16GB
    // 3. Are from previous 2-3 generations (not latest, per PRD)
    
    var targetModels = await _context.GpuModels
        .Where(m => m.RetailPrice != null)
        .Where(m => m.RetailPriceUpdatedAt > DateTime.UtcNow.AddDays(-7))
        .Where(m => m.VramGb >= 16)
        .Where(m => m.Generation < GetLatestGeneration(m.Manufacturer))
        .ToListAsync();
    
    return targetModels;
}
```

**Example Scope** (assuming Feature 1 tracks these):
- **Nvidia**: RTX 4090 24GB, 4080 Super 16GB, 4070 Ti Super 16GB, 3090 Ti 24GB, 3090 24GB (excludes RTX 5000-series as "latest gen")
- **AMD**: RX 7900 XTX 24GB, 7900 XT 20GB, 7900 GRE 16GB, 6950 XT 16GB, 6900 XT 16GB (excludes RX 8000-series if released)

**Edge Case - Retail Data Missing**:
If Feature 1 temporarily loses retail price data for a card (e.g., retailer scrape fails), used scraping continues but dashboard may hide that card until retail data is restored. User doesn't see "orphaned" used prices without context.

**Future Consideration (v2)**:
If users request used prices for cards not in retail tracker (e.g., older cards like RTX 2080 Ti), can decouple features. For v1, tight coupling ensures feature cohesion.

---

### **Duplicate Listing Handling**

**Decision**: No duplicate detection in v1. Accept that cross-posted listings may be counted twice.

**Rationale**:
- **Low incidence**: Most sellers choose one platform (eBay or CEX) rather than cross-posting
- **Outlier filter mitigates**: If same card is listed at £480 on both eBay and CEX, having two listings at that price doesn't skew the average significantly
- **Complexity avoidance**: Detecting duplicates requires heuristics (same price + same timeframe = duplicate?) which introduce false positives/negatives
- **Monitoring in place**: If duplicate detection becomes necessary, we have the data (listing URLs, prices, timestamps) to analyze incidence in v2

**Logging**:
No special logging for potential duplicates in v1. Standard listing logs include source, price, timestamp—future analysis can identify patterns if needed.

**Future Enhancement (v2)**:
If monitoring shows >20% of listings are cross-posts (unlikely), implement Option B from questions: log potential duplicates (exact price match across sources within same scrape window) without filtering, then analyze data to build smarter de-duplication.

---

### **Listing URL Storage**

**Decision**: Store listing URLs in database for admin debugging only. Never expose via public API.

**Rationale**:
- **Admin debugging utility**: 
  - Investigate price anomalies ("Why was this £2000 listing an outlier?")
  - Verify scraper accuracy ("Did we extract the right price from this eBay listing?")
  - Audit outlier filtering decisions
- **No user-facing linking**: Avoids affiliate/legal concerns mentioned in PRD
- **Access control**: Admin backoffice requires authentication; URLs visible only to ops team

**Implementation**:
```csharp
// Database schema includes URL
public class UsedListing
{
    public Guid Id { get; set; }
    public string CardModel { get; set; }
    public decimal Price { get; set; }
    public string Source { get; set; }
    public string ListingUrl { get; set; } // Admin-only access
    public DateTime ScrapedAt { get; set; }
    public bool IsOutlier { get; set; }
}

// Admin backoffice endpoint (requires [Authorize(Roles = "Admin")])
[HttpGet("admin/used-listings/{id}")]
public async Task<UsedListingDetailDto> GetListingDetail(Guid id)
{
    var listing = await _context.UsedListings.FindAsync(id);
    return new UsedListingDetailDto
    {
        Id = listing.Id,
        CardModel = listing.CardModel,
        Price = listing.Price,
        Source = listing.Source,
        ListingUrl = listing.ListingUrl, // Only in admin DTO
        ScrapedAt = listing.ScrapedAt,
        IsOutlier = listing.IsOutlier
    };
}

// Public API (no URL field)
[HttpGet("api/v1/used-prices/{cardModel}")]
public async Task<UsedPriceResponseDto> GetUsedPrice(string cardModel)
{
    // Public DTO does NOT include listing URLs
    var priceData = await _usedPriceService.GetAveragePrice(cardModel);
    return new UsedPriceResponseDto
    {
        CardModel = priceData.CardModel,
        AveragePrice = priceData.AveragePrice,
        ListingCount = priceData.ListingCount,
        // No listing URLs in response
    };
}
```

**Admin UI**:
- Listing detail page shows URL as plain text (not clickable hyperlink to avoid accidental click-through)
- Copy-to-clipboard button for investigating listing externally
- Use case: Admin pastes URL into browser to verify scraper extracted correct data

---

### **Price Validation (Sanity Checks)**

**Decision**: Discard listings with prices outside £50-£5000 range before outlier filtering.

**Rationale**:
- **Prevents garbage data**: Scraping errors (extracted wrong DOM element, currency conversion bug) often result in extreme values (£0.01, £999,999)
- **Realistic GPU market bounds**: 
  - Minimum £50: Used GPUs below this are likely non-GPU items (cables, fans) scraped incorrectly, or extraction errors
  - Maximum £5000: Consumer GPUs (even RTX 4090) don't exceed this used. Higher values are commercial bulk listings, server GPUs, or typos.
- **Pre-filter before outlier detection**: Sanity check happens first to avoid extreme values skewing median calculation

**Implementation**:
```csharp
public const decimal MIN_VALID_PRICE = 50m;
public const decimal MAX_VALID_PRICE = 5000m;

public List<UsedListing> ValidateListings(List<UsedListing> rawListings)
{
    var validated = new List<UsedListing>();
    
    foreach (var listing in rawListings)
    {
        if (listing.Price < MIN_VALID_PRICE)
        {
            _logger.LogWarning(
                "Price too low - discarded: {Model} £{Price} from {Source}",
                listing.CardModel, listing.Price, listing.Source
            );
            continue;
        }
        
        if (listing.Price > MAX_VALID_PRICE)
        {
            _logger.LogWarning(
                "Price too high - discarded: {Model} £{Price} from {Source}",
                listing.CardModel, listing.Price, listing.Source
            );
            continue;
        }
        
        validated.Add(listing);
    }
    
    return validated;
}
```

**Logging**:
- Log all discarded listings to `InvalidPriceListing` table
- Include: listing URL, extracted price, card model, source
- Review weekly to identify systemic scraping issues (e.g., "We're consistently extracting shipping cost instead of item price")

**Boundary Adjustment**:
If high-end cards like RTX 6000 Ada (professional GPU) are added to scope in future, upper bound can be increased to £10,000. For consumer GPUs tracked in v1, £5,000 is appropriate ceiling.

**Processing Order**:
1. Extract listing data from source
2. **Sanity check price (£50-£5000)** ← This step
3. Identify GPU model and VRAM
4. Filter outliers (2x/0.5x median)
5. Calculate average

---

## Q&A History

### Iteration 1 - 2025-01-10

**Q1: What is our legal/compliance approach to marketplace scraping?**  
**A**: Hybrid approach - eBay official API + CEX web scraping. Facebook Marketplace excluded from v1. eBay provides compliant, reliable access via Partner Network API. CEX scraping accepted with calculated ToS risk (respectful rate limiting, robots.txt compliance). Two sources provide sufficient market coverage for MVP. Can revisit Facebook if API access becomes available.

**Q2: What is the minimum number of listings required to display a price?**  
**A**: Display all prices with confidence indicators. Never hide data if at least 1 listing exists. Confidence levels: Low (1-2 listings with warning badge), Medium (3-5 listings), High (6+ listings with checkmark). Transparency over conservative hiding - users judge data reliability themselves.

**Q3: How do we identify and normalize GPU models from listing titles?**  
**A**: JSON reference file (`gpu-models.json`) in repository, loaded at service startup. Source models from TechPowerUp GPU Database (manually curated). File includes canonical names, VRAM specs, manufacturer, and aliases. Matching algorithm: substring match against aliases, validate VRAM from listing matches spec. Log unmatched listings for review. Update JSON via code commits (version controlled, reviewable).

**Q4: What happens when all three (or two, per Q1 recommendation) marketplaces fail to scrape?**  
**A**: Hide data after 3 days of failed scrapes. If data age >72 hours, display "Data temporarily unavailable" instead of stale prices. Protects users from misleading outdated information in fast-moving market. Single-source failures display partial data with warning ("Based on 1 source"). Complete failures trigger critical alerts for immediate ops response.

**Q5: How do we handle VRAM size mismatches between listing and known model specs?**  
**A**: Treat VRAM variants as separate models. Lookup table includes distinct entries for each variant (e.g., "RTX 4060 Ti 8GB" and "RTX 4060 Ti 16GB" are separate models). Match listings against both model name AND VRAM. If listing claims VRAM that doesn't match any variant in lookup table, discard as seller error. Prevents mixing prices for different products.

**Q6: What is the outlier filtering methodology when listing count is low?**  
**A**: Fixed threshold (2x/0.5x median) regardless of sample size. Simple, consistent, easy to explain. Confidence indicators already communicate small-sample limitations to users. Outlier filtering happens after sanity checks, uses standard median calculation. Log removed outliers for review. If production data shows threshold needs adjustment, can revisit with statistical methods in v2.

**Q7: Should we store historical scraping data or only keep the latest snapshot?**  
**A**: Store historical averages indefinitely (one record per card per day). Keep individual listings for 7 days for debugging, then purge. Historical averages enable future trend features (v2) at negligible storage cost. 7-day listing retention allows investigation of calculation issues without unbounded database growth.

**Q8: How do we handle currency conversion if non-GBP listings appear?**  
**A**: Discard all non-GBP listings. No currency conversion in v1. UK marketplaces should only show GBP; non-GBP is edge case (<1% expected). Log discarded listings for investigation. Avoids exchange rate API dependency and conversion errors for rare occurrences. Can implement conversion in v2 if production logs show significant legitimate non-GBP listings.

**Q9: Should scraping run at a fixed time (3 AM) or on a rolling 24-hour interval?**  
**A**: Fixed daily schedule (3:00 AM UTC) with manual "Scrape Now" button in admin backoffice. No automatic retries - prefer monitoring alerts + human intervention to fix root cause. Admin panel shows last scrape status, allows immediate manual trigger if needed. Prevents concurrent runs via job status check.

**Q10: How granular should source breakdown be in the UI?**  
**A**: Store aggregated counts per source in JSON field (`{"eBay": 5, "CEX": 3}`). Display in tooltip on hover ("Based on 8 listings: 5 from eBay, 3 from CEX"). Provides transparency without overcomplicating UI. No drill-down to individual listings in v1 - counts are sufficient for user confidence assessment.

**Q11: What defines a "target card model" for scraping?**  
**A**: Scrape used prices only for cards with retail price data (from Feature 1). Dynamic scope - when new cards added to retail tracker, automatically included in used scraping. Ensures comparison capability (used vs. new) which is core value proposition. Scope automatically filtered to 16GB+ VRAM, previous 2-3 generations (not latest).

**Q12: How do we handle duplicate listings from the same seller across platforms?**  
**A**: No duplicate detection in v1. Accept that cross-posted listings may be counted twice. Incidence expected to be low (<5%) and outlier filter mitigates impact on averages. Avoids complexity of heuristic-based deduplication. Monitor in production; can add detection in v2 if data shows significant duplication.

**Q13: Should we expose individual listing URLs (even though PRD says no linking)?**  
**A**: Store URLs in database for admin debugging only. Never expose via public API or user-facing UI. Admin backoffice shows URLs as plain text (copy-to-clipboard for investigation) behind authentication. Enables ops team to verify scraper accuracy and investigate anomalies without creating affiliate/legal concerns.

**Q14: What validation rules apply to scraped price data?**  
**A**: Sanity check bounds: £50 minimum (filters extraction errors/non-GPU items), £5000 maximum (filters commercial bulk/server GPUs/typos). Discard out-of-bounds listings before outlier filtering. Log discarded listings for scraper quality review. Bounds appropriate for consumer GPU market; can adjust if professional cards added to scope.

---

## Product Rationale

### **Why Hybrid Scraping Approach (eBay API + CEX Scraping)?**

**User Need**: PC builders need visibility into used market prices across multiple marketplaces to identify fair value.

**Business Goal**: Provide reliable, legally defensible data without building unsustainable scraping infrastructure.

**Constraints**: 
- eBay has official API (reliable, compliant)
- CEX has no API (scraping required but accepted risk for UK retailer)
- Facebook Marketplace has aggressive anti-scraping + no API (high risk, high maintenance)

**Decision**: Two sources provide sufficient market coverage for v1. eBay represents largest UK used GPU marketplace; CEX adds retail/trade-in pricing perspective. Facebook exclusion is pragmatic risk management - can revisit if feature success justifies business partnership negotiations.

---

### **Why Confidence Indicators Instead of Hiding Low-Count Data?**

**User Need**: Researchers of rare/older GPUs (RTX 3090 Ti, RX 6950 XT) want any market signal, even from 1-2 listings.

**Product Philosophy**: Transparency over paternalism. User evaluating a £600 used card can judge "Low confidence - 2 listings" better than "Insufficient data" blackout.

**Constraint**: Small-sample averages are less reliable statistically.

**Decision**: Surface all data with clear reliability indicators. User buying rare hardware understands thin market - wants visibility, not protection. Serves advanced users without confusing beginners (who typically shop common models with high confidence).

---

### **Why JSON Reference File Over Database Table for Model Lookup?**

**Maintenance Need**: GPU models require alias updates as scraping finds new naming variants.

**MVP Constraint**: Building admin UI adds dev time; v1 focuses on core scraping functionality.

**Trade-off**: JSON is engineer-editable (requires code deploy) vs. database is admin-editable (requires UI build).

**Decision**: JSON provides 80% of maintainability at 20% of implementation cost. Model aliases change infrequently (new GPU releases ~quarterly). Engineers can update JSON in <5 minutes via PR. Version control provides audit trail and rollback capability. If maintenance becomes weekly burden (unlikely), upgrade to database+UI in v2. For MVP, prefer shipping scraping functionality over building admin tooling.

---

### **Why 3-Day Staleness Threshold?**

**Market Reality**: Used GPU prices fluctuate based on:
- New GPU launches (previous-gen prices drop 10-20%)
- Cryptocurrency mining trends (high-VRAM cards spike in demand)
- Retail sales events (Black Friday affects used market psychology)

**User Risk**: Week-old price data misleads users ("RTX 4070 Ti used market is £480" when reality shifted to £420 after new model announcement).

**Operational Pressure**: Hiding feature after 3 days creates urgency for ops team to fix scraping (vs. tolerating stale data indefinitely).

**Decision**: 3 days balances user protection (don't show misleading data) with operational grace period (reasonable time to fix scraper issues without weekend panic). Faster-moving markets (cryptocurrency, sneakers) use 24-hour thresholds; slower markets (cars, real estate) tolerate weeks. Used GPUs are medium-velocity - 3 days is conservative but not paranoid.

---

### **Why Dynamic Card Scope (Coupled to Feature 1)?**

**Feature Synergy**: Core value proposition is "compare used vs. new to find value inversions" (from PRD).

**Isolated Data Problem**: Showing "RTX 4070 used = £380" without retail price context is less actionable. User needs "RTX 4070 used = £380 vs. new = £520" to understand value.

**Maintenance Efficiency**: Single source of truth for "which cards we track" prevents drift between features.

**Decision**: Tight coupling is intentional architecture choice. Used price feature is an extension of retail price feature, not a standalone product. Ensures every used price is comparable to a retail price. Simplifies onboarding (adding new card to retail tracker automatically enables used tracking). If user research reveals demand for used-only pricing (e.g., older cards no longer sold new), can decouple in v2.

---

## Data Model (Initial Thoughts)

[UNCHANGED FROM V1.0 - Database schema additions reflected in Detailed Specifications sections above]

**Entities This Feature Needs**:

- **UsedListing**: Individual marketplace listing scraped from a source
  - Properties: ListingId (GUID), CardModel (string), VramSize (int), Price (decimal), Source (enum: eBay/CEX), ListingUrl (string), ScrapedAt (datetime), IsOutlier (bool)
  
- **UsedPriceAverage**: Aggregated average price per card model
  - Properties: CardModel (string), VramSize (int), AveragePrice (decimal), ListingCount (int), SourceBreakdown (JSON), Confidence (enum), CalculatedAt (datetime), Manufacturer (enum: Radeon/Nvidia)

- **ScrapeJob**: Metadata about each scraping run
  - Properties: JobId (GUID), RunAt (datetime), Source (enum), ListingsFound (int), Status (enum: Success/PartialFailure/Failure), ErrorMessage (string nullable)

**Key Relationships**:
- UsedListing → UsedPriceAverage (many-to-one grouping by CardModel)
- ScrapeJob tracks each marketplace scrape independently (one job per source per day)
- UsedPriceAverage is recalculated after each scrape; history preserved indefinitely for trend analysis

---

## User Experience Flow

[UPDATED FOR V1.1 - Reflects eBay API + CEX scraping, confidence indicators]

**Daily Background Process (invisible to user)**:

1. At 3:00 AM UTC, Hangfire triggers `ScrapeUsedMarketPrices` job
2. **eBay API Scraping**:
   - Service calls eBay Finding API with search terms for each target GPU model
   - Filters: Used condition, Buy It Now only, UK location, 16GB+ VRAM
   - Extracts: price (GBP), model, VRAM, listing URL
   - Stores raw listings in `UsedListing` table with `Source = 'eBay'`
3. **CEX Web Scraping**:
   - Service scrapes CEX UK search results for each target GPU model
   - Rate limiting: 3-second delay between requests, respect robots.txt
   - Parses HTML to extract: price (GBP), model, VRAM
   - Stores raw listings in `UsedListing` table with `Source = 'CEX'`
4. **Price Calculation** (per card model):
   - Sanity check: Discard prices outside £50-£5000
   - Calculate median price from remaining listings
   - Filter outliers: Remove listings >2x or <0.5x median
   - Calculate average price from filtered listings
   - Determine confidence level: Low (1-2 listings), Medium (3-5), High (6+)
   - Store `UsedPriceAverage` record with source breakdown
5. **Data Cleanup**:
   - Purge `UsedListing` records older than 7 days
   - Retain all `UsedPriceAverage` historical records
6. Log job completion metrics (listings found, averages calculated, errors)

**User Viewing Dashboard**:

1. User visits GPU Value Tracker and selects "Radeon" or "Nvidia" mode
2. Dashboard loads used price data for selected manufacturer (from Redis cache, 1-hour TTL)
3. For each card displayed, user sees:
   - Card model name (e.g., "RX 7900 XT 20GB")
   - Average used price (e.g., "£480")
   - Confidence badge (e.g., "✓ High confidence" or "⚠️ Low confidence")
   - Number of listings (e.g., "Based on 8 listings")
   - Last updated timestamp (e.g., "Updated 6 hours ago")
4. User hovers over listing count to see tooltip:
   - "Based on 8 listings: 5 from eBay UK, 3 from CEX UK"
5. User compares used price against retail price to identify value opportunities
6. **If data is stale** (>3 days old):
   - Used price section shows "Used market data temporarily unavailable"
   - Timestamp shows "Last updated: 4 days ago"

**Admin Manual Trigger**:

1. Admin visits backoffice "Used Market Scraping" page
2. Page displays:
   - Last scrape: "Success - 2025-01-10 03:15 UTC"
   - Listings found: "eBay: 142, CEX: 38"
   - Next scheduled: "2025-01-11 03:00 UTC"
3. Admin clicks "Scrape Now" button
4. System validates no scrape currently in progress
5. Hangfire enqueues immediate scrape job
6. Page shows "Scrape in progress..." with live status updates
7. On completion, page refreshes with updated metrics

**Edge Case - Partial Source Failure**:

1. Daily scrape runs at 3 AM
2. eBay API succeeds (finds 142 listings)
3. CEX scrape fails (HTTP 503 error)
4. System:
   - Stores eBay listings
   - Calculates averages from eBay data only
   - Logs CEX failure with error details
   - Sends alert to ops team Slack
5. User sees:
   - Standard price display: "£480 avg."
   - Tooltip shows: "Based on 5 listings: 5 from eBay UK (CEX unavailable)"
   - No visible error to user (graceful degradation)

---

## Edge Cases & Constraints

[UPDATED FOR V1.1 - Reflects answers to technical questions]

- **Zero listings found for a card**: Display "No listings found" instead of showing stale data or "£0". User needs to know data is unavailable, not that the card is free.

- **Both marketplaces fail to scrape**: Retain previous day's data and display with age warning if <3 days old ("⚠️ Prices updated 2 days ago"). If >3 days old, hide prices entirely and show "Data temporarily unavailable". Alert ops team for immediate investigation.

- **Card model ambiguity**: If a listing title could match multiple cards (e.g., "RTX 4070" could be 4070 or 4070 Ti), discard the listing rather than guess. Log to `UnmatchedListing` for manual review to improve model matching.

- **Multi-VRAM variants**: Cards like RTX 4060 Ti exist in 8GB and 16GB versions. Treat as separate models in `gpu-models.json`. Only track 16GB+ variant for this feature. Match listings against specific variant (don't aggregate 8GB and 16GB prices together).

- **VRAM listed incorrectly**: If listing says "RTX 4070 16GB" but model spec says 12GB, discard listing as seller error. Trust canonical model database over listing text to prevent incorrect price aggregation.

- **Currency conversion**: All prices must be in GBP. If a listing is in EUR or USD (rare on UK sites), discard listing and log for investigation. No currency conversion in v1 to avoid exchange rate complexity.

- **Condition variance**: CEX may list "Good", "Fair", "Poor" condition. All conditions included in average; outlier filter handles extreme price differences. User understands "average used price" includes a range of conditions.

- **Listing age**: eBay API provides listing date; filter to past 30 days only. CEX doesn't provide date on search results page; include all visible listings (assume recent). If CEX shows consistently stale listings in production, add date extraction from detail pages.

- **Duplicate listings**: Same seller may cross-post on eBay and CEX. No de-duplication in v1 (accept slight inflation of listing count). Outlier filter mitigates impact if duplicate prices skew average. Monitor in production to assess incidence.

- **Outlier removal edge case**: If all listings are filtered as outliers (unlikely), display "Data quality insufficient - listings appear unreliable" instead of showing average from zero listings.

- **Admin URL access**: Listing URLs stored in database are admin-only (not exposed via public API). Admin backoffice shows URLs as plain text for debugging, not clickable links (prevents accidental click-through, avoids affiliate concerns).

- **eBay API rate limit**: 5,000 calls/day limit. With ~50 target models × 1 call per model = 50 calls/day, well within limit. If limit hit due to errors/retries, complete scrape with available data and alert ops team.

- **CEX IP blocking**: If CEX detects scraping and blocks IP (returns CAPTCHA or 403 errors), scrape fails gracefully. Continue with eBay data only. Alert ops team to investigate (may need proxy rotation or user-agent changes in v2).

- **Price extraction errors**: If scraper extracts wrong HTML element (e.g., shipping cost instead of item price), sanity check (£50-£5000 bounds) catches most errors. Remaining bad data is logged in outlier filter. Weekly review of `InvalidPriceListing` and `OutlierLog` tables identifies systemic extraction issues.

---

## Out of Scope for This Feature

[UPDATED FOR V1.1 - Clarifies v1 exclusions]

This feature explicitly does NOT include:

- **Facebook Marketplace scraping**: Excluded due to ToS compliance concerns and aggressive anti-scraping. Revisit in v2 if API access becomes available or business justifies partnership negotiations.

- **Historical price trends**: No graphs showing "RTX 4070 Ti used prices over the past 3 months". V1 only shows current average price. Historical data is stored (enables v2 trends) but not exposed in UI.

- **Condition filtering**: No separate averages for "Good" vs "Fair" condition. User sees one average price across all conditions.

- **Seller reputation**: No tracking of whether listing is from a trusted seller or a new account. User sees price only.

- **Warranty status**: No indication of whether used card includes warranty or is sold "as-is".

- **Shipping costs**: Average price is asking price only; doesn't include shipping. User must factor in shipping separately when evaluating deals.

- **Regional price differences**: No breakdown by UK region (e.g., London vs Manchester). All UK listings are aggregated.

- **"Fair deal" recommendations**: No UI indicating "This is a good deal" or "Overpriced". User interprets the data themselves by comparing used vs. retail prices.

- **Link to individual listings**: No clickable links to eBay/CEX listings in user-facing UI. User uses the average price as a reference, then searches marketplaces themselves. (Admin backoffice has URLs for debugging only.)

- **Notifications**: No alerts when a card's used price drops. User must check dashboard manually.

- **International marketplaces**: No US eBay, EU Facebook Marketplace, etc. UK only for v1.

- **Automatic retry on scrape failure**: No automatic retries at 6 AM, 9 AM if 3 AM job fails. Manual trigger via admin backoffice only. Failures alert ops team to fix root cause rather than masking issues with retries.

- **Currency conversion**: No handling of EUR/USD listings. Discard non-GBP prices entirely in v1.

- **Duplicate detection**: No de-duplication of cross-posted listings (same seller on eBay + CEX). Accept potential double-counting in v1.

- **Auction listings**: eBay auctions are excluded; only "Buy It Now" fixed-price listings scraped. Auction prices don't represent asking price (they represent winning bid, which may be below/above market).

---

## Open Questions for Tech Lead

[REMOVED - All questions answered in Iteration 1]

All technical questions have been answered. Feature specification is complete and ready for technical validation.

---

## Dependencies

**Depends On**: 
- Background job infrastructure (Hangfire) must be configured and running
- Database schema for storing UsedListing and UsedPriceAverage entities
- **[v1.1]** `gpu-models.json` reference file with target card models, VRAM specs, and aliases
- **[v1.1]** eBay Developer account with API credentials (Partner Network application token)
- **[v1.1]** Feature 1 (Retail Price Tracking) must define scope of tracked cards (dynamic target list for used scraping)
- **[v1.1]** Redis caching layer for API responses (1-hour TTL for used price data)
- **[v1.1]** Admin backoffice authentication/authorization for manual scrape trigger

**Enables**: 
- Feature 3 (Value Visualization Dashboard) depends on this feature's data to compare used vs retail prices and highlight value opportunities
- Feature 5 (Radeon vs Nvidia Mode Switching) filters used price data by manufacturer

---

## Technical Implementation Notes

**For Tech Lead Review**:

This v1.1 specification resolves all 14 technical questions from Iteration 1. Key implementation considerations:

1. **eBay API Integration**:
   - Use eBay Finding API (`findItemsAdvanced`)
   - Register at https://developer.ebay.com/
   - Requires OAuth 2.0 application token (not user token)
   - Rate limit: 5,000 calls/day (sufficient for daily scraping)
   - C# SDK: `eBay.Service` NuGet package or direct REST calls

2. **CEX Scraping**:
   - Target URL: `https://uk.webuy.com/search?stext={model}&section=computing-graphics-cards`
   - HTML parsing: AngleSharp or HtmlAgilityPack
   - Rate limiting: 3-second delay between requests (System.Threading.Thread.Sleep)
   - Respect robots.txt: Check `/robots.txt` for disallowed paths
   - User-Agent: `GPUValueTracker/1.0 (contact@yoursite.com)` (transparent bot identification)

3. **Data Pipeline**:
   - Scrape → Sanity check (£50-£5000) → Model identification → Outlier filter → Average calculation
   - Hangfire recurring job: `RecurringJob.AddOrUpdate("scrape-used-prices", ...);`
   - Job execution time: Estimate 5-10 minutes (50 models × 2 sources × 5 sec/scrape)

4. **Database**:
   - PostgreSQL schema provided in Detailed Specifications
   - Indexes on `scraped_at` (for 7-day cleanup) and `card_model, calculated_at` (for price queries)
   - JSONB column for source_breakdown (native JSON support)

5. **API Response Caching**:
   - Redis cache key: `used-prices:{manufacturer}:{card-model}`
   - TTL: 1 hour (data refreshes daily, 1-hour cache is 4% stale at most)
   - Cache invalidation: On scrape completion, clear all `used-prices:*` keys

6. **Admin Backoffice**:
   - ASP.NET Core MVC or Razor Pages
   - Route: `/admin/used-market-scraping`
   - Authorization: `[Authorize(Roles = "Admin")]`
   - Manual trigger button calls `usedMarketScraperService.ScrapeAllMarketplaces()` (enqueues Hangfire job)
   - Prevent concurrent runs: Check `Hangfire.Storage.IMonitoringApi.JobState` before enqueuing

7. **Monitoring & Alerts**:
   - Slack webhook for scrape failures
   - Application Insights custom metrics: `scrape_listings_found`, `scrape_duration_seconds`
   - Alert if >3 days without successful scrape (critical)

**Ready for Engineering Specification**: All product decisions are finalized. Tech Lead can now validate technical feasibility, estimate effort, and create engineering spec.