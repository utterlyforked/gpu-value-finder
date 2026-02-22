# Live Retail Price Aggregation - Feature Requirements

**Version**: 1.0  
**Date**: 2025-01-10  
**Status**: Initial - Awaiting Tech Lead Review

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

---

## Acceptance Criteria

- System scrapes prices from Scan, Ebuyer, and Amazon UK for latest-generation cards (16GB+ VRAM only)
- Average retail price is calculated for each card model across all available listings
- Prices are refreshed at least once every 24 hours
- Only cards currently in stock are included in average calculation
- Price data includes timestamp of last successful scrape
- Retail prices are separated by manufacturer (Radeon/Nvidia) and never mixed
- Scraping jobs handle failures gracefully and retry failed sources
- Out-of-stock cards retain last known price with "Out of Stock" indicator
- Price data is persisted and queryable via API endpoint

---

## Functional Requirements

### Scraper Infrastructure

**What**: Scheduled background jobs that fetch GPU pricing data from three UK retailers

**Why**: Manual price checking across multiple retailers is time-consuming; automation ensures data freshness and consistency

**Behavior**:
- Hangfire scheduled job runs daily at 2:00 AM UTC (low-traffic period)
- Three separate scraper implementations: ScanScraper, EbuyerScraper, AmazonUKScraper
- Each scraper implements `IRetailScraper` interface with `ScrapeAsync()` method
- Scrapers run in parallel (not sequentially) to minimize total execution time
- Each scraper has independent retry logic (3 attempts with exponential backoff)
- If a scraper fails after retries, job continues with other scrapers (does not abort entire job)
- Scraping respects robots.txt and implements rate limiting (minimum 2-second delay between requests to same domain)
- User agent identifies as legitimate bot: "GPUValueTracker/1.0 (contact@gpuvaluetracker.com)"

### Target GPU Identification

**What**: Define which GPU models are "latest generation" and eligible for tracking

**Why**: Focusing on latest-gen cards keeps the dataset manageable and relevant to users considering new purchases

**Behavior**:
- **Radeon**: AMD Radeon RX 7000 series (RDNA 3 architecture) with 16GB VRAM minimum
  - Examples: RX 7900 XTX (24GB), RX 7900 XT (20GB), RX 7800 XT (16GB)
- **Nvidia**: GeForce RTX 4000 series (Ada Lovelace architecture) with 16GB VRAM minimum
  - Examples: RTX 4090 (24GB), RTX 4080 (16GB), RTX 4070 Ti Super (16GB)
- Manufacturer-specific partner cards (ASUS, MSI, Gigabyte) are normalized to reference model
  - "ASUS ROG Strix RTX 4080" → "RTX 4080"
  - "Sapphire Nitro+ RX 7900 XTX" → "RX 7900 XTX"
- Cards under 16GB VRAM are explicitly filtered out and never stored

### HTML Parsing & Price Extraction

**What**: Extract product name, price, and stock status from retailer HTML pages

**Why**: Retailer sites do not provide APIs; HTML parsing is the only data source

**Behavior**:
- Each scraper uses CSS selectors specific to that retailer's HTML structure
- Price parsing handles multiple formats:
  - "£649.99" → 649.99
  - "£1,299.00" → 1299.00
  - "Was £799, Now £699" → 699.00 (takes current price)
- Stock status detection:
  - "In Stock", "Available Now", "Dispatches in 1-2 days" → **In Stock**
  - "Out of Stock", "Currently Unavailable", "Pre-order" → **Out of Stock**
- Product name normalization:
  - Extract GPU model using regex patterns
  - Remove manufacturer prefixes (ASUS, MSI, Gigabyte, etc.)
  - Identify VRAM size from title or specs (e.g., "24GB", "16GB")
  - Store normalized name: "RTX 4090" not "ASUS TUF Gaming GeForce RTX 4090 OC Edition 24GB"

### Price Calculation & Averaging

**What**: Calculate average retail price per GPU model across all in-stock listings

**Why**: A single listing price may be an outlier (pricing error, clearance sale); average smooths market noise

**Behavior**:
- Only in-stock listings are included in average calculation
- Outlier filtering: Remove prices >2 standard deviations from median (prevents pricing errors from skewing average)
- If only 1 listing exists, that price is used (no average needed)
- If all retailers are out of stock for a model, retain last known average price and mark as "Out of Stock"
- Average is recalculated fresh on each scrape run (no rolling average)
- Calculation example:
  - Scan: RTX 4080 = £1,199 (in stock)
  - Ebuyer: RTX 4080 = £1,149 (in stock)
  - Amazon: RTX 4080 = £1,249 (in stock)
  - **Average**: £1,199

### Data Storage

**What**: Persist scraped price data in PostgreSQL for querying and historical reference

**Why**: API endpoints need fast access to current pricing; future features may require historical data

**Behavior**:
- `RetailPrices` table schema:
  ```
  Id (PK)
  GpuModel (string, indexed) - e.g., "RTX 4090"
  Manufacturer (enum: Radeon, Nvidia)
  VramSizeGB (int)
  AveragePrice (decimal)
  ListingCount (int) - how many listings contributed to average
  IsInStock (bool)
  LastScrapedAt (timestamp)
  Source (string) - "Scan,Ebuyer,Amazon" (comma-separated list of contributing retailers)
  ```
- Each scrape run updates existing rows for each GPU model (UPSERT operation)
- Historical snapshots are NOT stored in v1 (only current pricing)
- Indexes on `GpuModel` and `Manufacturer` for fast querying

### API Endpoint

**What**: RESTful endpoint that serves current retail pricing data to frontend

**Why**: Frontend dashboard needs to fetch latest pricing on page load

**Behavior**:
- **Endpoint**: `GET /api/v1/retail-prices`
- **Query Parameters**:
  - `manufacturer` (required): "radeon" or "nvidia"
- **Response** (JSON):
  ```json
  {
    "manufacturer": "nvidia",
    "lastUpdated": "2025-01-10T02:15:33Z",
    "prices": [
      {
        "model": "RTX 4090",
        "vramGB": 24,
        "averagePrice": 1599.99,
        "listingCount": 12,
        "inStock": true
      },
      {
        "model": "RTX 4080",
        "vramGB": 16,
        "averagePrice": 1199.00,
        "listingCount": 8,
        "inStock": true
      }
    ]
  }
  ```
- Returns 200 OK with empty `prices` array if no data available (e.g., first scrape hasn't run)
- Returns 400 Bad Request if `manufacturer` parameter is missing or invalid

---

## Data Model (Initial Thoughts)

**Entities This Feature Needs**:

- **RetailPrice**: Represents the current average retail price for a specific GPU model
  - Properties: GpuModel, Manufacturer, VramSizeGB, AveragePrice, ListingCount, IsInStock, LastScrapedAt, Source
  - One row per GPU model (e.g., one row for "RTX 4090", one for "RX 7900 XTX")

- **ScraperLog** (for monitoring/debugging): Records each scrape job execution
  - Properties: Id, StartedAt, CompletedAt, Status (Success/PartialFailure/Failure), ErrorMessages, RecordsUpdated

**Key Relationships**:
- RetailPrice is a standalone entity (no foreign keys in v1)
- ScraperLog references RetailPrice records indirectly (via count of updated records)

---

## User Experience Flow

1. **Automated Job Trigger**: At 2:00 AM UTC, Hangfire triggers the `RetailPriceScraperJob`
2. **Parallel Scraping**: Three scraper implementations fetch GPU listings from Scan, Ebuyer, and Amazon UK simultaneously
3. **Data Extraction**: Each scraper parses HTML, extracts GPU model names, prices, VRAM sizes, and stock status
4. **Normalization**: Product names are normalized to reference models (e.g., "ASUS RTX 4080" → "RTX 4080")
5. **Filtering**: Cards under 16GB VRAM are discarded; only latest-gen cards are retained
6. **Price Aggregation**: System calculates average price per model across all in-stock listings, applying outlier filtering
7. **Database Update**: `RetailPrices` table is updated with new average prices and timestamps
8. **Job Completion**: ScraperLog records job success/failure status
9. **User Visits Dashboard**: Frontend loads, calls `GET /api/v1/retail-prices?manufacturer=nvidia`
10. **API Response**: Backend returns current pricing data with timestamp of last scrape
11. **Dashboard Rendering**: Frontend displays prices in visualization (handled by Feature 3)

---

## Edge Cases & Constraints

- **Scraper Blocked by Retailer**: If a scraper is blocked (CAPTCHA, IP ban), it fails gracefully and logs error. Pricing data from other retailers is still used. User sees "Partial data - Scan unavailable" indicator in dashboard.

- **All Retailers Out of Stock**: If a GPU model is out of stock everywhere, last known price is retained in database with `IsInStock = false`. Dashboard shows "(Out of Stock)" label next to price.

- **Pricing Error on Retailer Site**: If a retailer lists a GPU for £1 (obviously wrong), outlier filtering removes it from average calculation. Logged for manual review.

- **New GPU Model Released**: If a new latest-gen card appears on retailer sites (e.g., RTX 4090 Ti), scraper automatically detects it and adds to database. No manual configuration needed.

- **GPU Model Naming Ambiguity**: If retailers use inconsistent naming (e.g., "RTX 4080" vs "RTX 4080 16GB"), normalization regex must handle both. Worst case: manual mapping table for edge cases.

- **Scraper HTML Changes**: If retailer redesigns their site, scraper breaks. Monitoring alerts on scrape failures. Requires developer intervention to update CSS selectors.

- **Rate Limiting by Retailer**: If scraper hits rate limit (429 error), exponential backoff retries. If still blocked, that scraper fails for this run and retries next scheduled run.

---

## Out of Scope for This Feature

This feature explicitly does NOT include:

- **Historical price tracking**: Only current prices are stored; no trend graphs or "price 30 days ago" functionality
- **Price drop alerts**: No email or push notifications when prices decrease
- **User-configurable scraping**: Scrape schedule is fixed at daily; users cannot trigger manual scrapes
- **International retailers**: Only UK retailers (Scan, Ebuyer, Amazon UK); no Newegg, B&H, or US-based stores
- **Intel Arc GPUs**: Only Radeon and Nvidia latest-gen cards
- **8GB or smaller GPUs**: Only 16GB+ VRAM cards are tracked
- **Partner card differentiation**: ASUS, MSI, Gigabyte variants are normalized to reference models; no price comparison between manufacturers
- **Affiliate links**: No monetization or referral links to retailers

---

## Open Questions for Tech Lead

1. **Scraper Technology**: Should we use headless browser (Playwright/Puppeteer) or HTTP client (HttpClient with AngleSharp for HTML parsing)? Headless browser is more robust against JavaScript-rendered pages but slower and resource-intensive.

2. **Anti-Scraping Mitigation**: Do we need rotating proxies or residential IPs to avoid detection, or is respectful scraping (rate limiting, user agent) sufficient for these UK retailers?

3. **CAPTCHA Handling**: If a retailer serves CAPTCHA, do we fail gracefully and skip that source, or do we invest in CAPTCHA-solving services (2Captcha, etc.)?

4. **Retailer-Specific Challenges**: Amazon UK heavily uses JavaScript rendering and anti-bot measures. Should we deprioritize Amazon in v1 if it proves too difficult, or is it critical to include?

5. **Normalization Accuracy**: Should we maintain a manual mapping table for GPU model name variations (e.g., "RTX 4080 Super" vs "RTX 4080 SUPER"), or rely purely on regex normalization?

6. **Monitoring & Alerts**: What monitoring do we need for scraper health? Should we alert (email/Slack) if scrapers fail 2 consecutive days?

---

## Dependencies

**Depends On**: None (this is a foundational feature)

**Enables**: 
- Feature 3 (Value Visualization Dashboard) depends on this data
- Feature 2 (Used Market Price Discovery) uses this as baseline for comparison