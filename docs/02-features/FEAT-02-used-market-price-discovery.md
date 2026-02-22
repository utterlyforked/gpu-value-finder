# Used Market Price Discovery - Feature Requirements

**Version**: 1.0  
**Date**: 2025-01-10  
**Status**: Initial - Awaiting Tech Lead Review

---

## Feature Overview

Used Market Price Discovery tracks average asking prices for used GPUs across secondary marketplaces (Facebook Marketplace, CEX, and eBay UK) to establish fair market value baselines for pre-owned graphics cards. This feature enables PC builders to identify genuine bargains by comparing used prices against new retail prices and spotting value inversions where previous-generation cards offer better performance-per-pound than latest releases.

The feature focuses exclusively on 16GB+ VRAM cards from the previous 2-3 generations (not just the latest), giving users visibility into the used market depth. By calculating average prices from active listings and filtering outliers, the system provides reliable price targets that builders can use when negotiating used purchases or evaluating marketplace listings.

This is not a marketplace or buying platform—it's market intelligence. Users see "the going rate" for a used RTX 4070 Ti or RX 7800 XT, then use that information to evaluate deals they find themselves on Facebook, eBay, or CEX.

---

## User Stories

- As a PC builder, I want to see the current average asking price for used GPUs on the secondary market so that I can identify fair market value
- As a value-conscious builder, I want to compare used prices for previous-generation cards against new latest-gen cards so that I can spot value inversions
- As a bargain hunter, I want to see price trends for specific used card models so that I know when I'm looking at a good deal
- As a used-hardware buyer, I want to see how many listings were found for each card model so that I can gauge market availability and confidence in the average price
- As a researcher, I want to know when used price data was last updated so that I can trust the information is current

---

## Acceptance Criteria

- System scrapes asking prices from Facebook Marketplace UK, CEX, and eBay UK for GPUs with 16GB VRAM or larger
- Average used price is calculated per card model based on active listings across all three sources
- Used prices are tracked for previous 2-3 GPU generations (e.g., Nvidia 30-series, 40-series; Radeon 6000-series, 7000-series), not just the latest generation
- Prices are refreshed at least once daily via scheduled background job
- Outliers (listings priced >2x or <0.5x the median for that model) are filtered from average calculation
- Used prices are stored and displayed separately for Radeon and Nvidia architectures (never mixed)
- Each card's used price data includes:
  - Average asking price (£)
  - Number of active listings found
  - Timestamp of last data refresh
  - Individual source contributions (e.g., "5 listings from eBay, 2 from Facebook, 1 from CEX")
- If no listings are found for a card model in the past 7 days, it displays "No listings found" instead of a stale price
- System handles scraping failures gracefully (e.g., one marketplace down doesn't block the others)

---

## Functional Requirements

### Marketplace Scraping

**What**: Automated scraping of used GPU listings from three UK secondary marketplaces

**Why**: Manual price checking across multiple sites is time-consuming and error-prone; automation provides consistent, repeatable data collection

**Behavior**:
- Scrape Facebook Marketplace UK using search terms like "RTX 4070 Ti 16GB", "RX 7900 XT", etc. for target card models
- Scrape CEX website (UK) for in-stock used GPUs matching target models
- Scrape eBay UK "Buy It Now" listings (not auctions) for used GPUs matching target models
- Search filters include:
  - Memory size: 16GB minimum
  - Condition: Used, refurbished, "for parts" (all included; outlier filter handles condition variance)
  - Location: UK only
- Extract: listing price (£), card model, VRAM size, marketplace source, listing URL, timestamp
- Respect robots.txt and rate-limit requests (minimum 2-second delay between requests to same domain)
- Retry failed requests up to 3 times with exponential backoff
- Log scraping metrics: success/failure count per source, listings found, scrape duration

### Card Model Identification

**What**: Parse listing titles/descriptions to identify specific GPU models and VRAM capacity

**Why**: Listings use inconsistent naming (e.g., "nvidia 4070ti 16gb", "RTX 4070 Ti Super", "4070TI"); normalization is required for grouping

**Behavior**:
- Maintain a lookup table of known GPU models with aliases:
  - Example: "RTX 4070 Ti" matches ["4070 Ti", "4070TI", "4070-Ti", "RTX4070Ti"]
  - Example: "RX 7900 XT" matches ["7900 XT", "7900XT", "RX7900XT"]
- Extract VRAM from title/description: "16GB", "16 GB", "24GB" → normalize to integer (16, 24)
- Discard listings where model cannot be identified with confidence
- Discard listings with <16GB VRAM
- Log unmatched listings for manual review (to improve lookup table over time)

### Outlier Filtering

**What**: Remove extreme outliers from price averages to prevent skewed results

**Why**: Marketplace listings include scams, typos, and wildly optimistic sellers; these shouldn't distort average price

**Behavior**:
- For each card model, calculate median price across all listings
- Remove listings where price is >2x or <0.5x the median
- If fewer than 3 listings remain after filtering, mark price as "Insufficient data" (don't calculate average from 1-2 listings)
- Log removed outliers for review (may indicate scraping errors or data quality issues)

### Price Aggregation

**What**: Calculate average asking price per card model across all marketplaces

**Why**: Single average price gives users a quick reference point for "market rate"

**Behavior**:
- Group all listings by normalized card model (e.g., "RTX 4070 Ti 16GB")
- After outlier filtering, calculate mean price across remaining listings
- Store average price with:
  - Card model identifier
  - Average price (£, rounded to nearest £1)
  - Number of listings included in average
  - Breakdown by source (e.g., "5 from eBay, 2 from CEX, 0 from Facebook")
  - Timestamp of calculation
- If a card appears in multiple VRAM configurations (e.g., 16GB and 24GB), treat as separate models

### Data Freshness

**What**: Ensure used price data is refreshed daily and stale data is flagged

**Why**: Secondary market prices shift quickly; stale data misleads users

**Behavior**:
- Background job runs daily at 3:00 AM UTC to scrape all marketplaces
- If scraping job fails entirely, retain previous day's data but mark with warning: "Data is [X] days old"
- If no listings found for a card in the past 7 days, display "No listings found" instead of showing last known price
- Dashboard shows last update timestamp prominently: "Used prices updated [X] hours ago"

### Multi-Source Handling

**What**: Gracefully handle failures or missing data from individual marketplaces

**Why**: One marketplace being unavailable shouldn't block the entire feature

**Behavior**:
- Each marketplace scrape runs independently; one failure doesn't prevent others from completing
- If Facebook Marketplace scrape fails, still calculate averages from CEX + eBay data
- If a marketplace returns zero results for a card, log it but don't treat as error (card may not be available there)
- Dashboard indicates source coverage: "Based on 3 sources" or "Based on 2 sources (eBay unavailable)"

---

## Data Model (Initial Thoughts)

**Entities This Feature Needs**:

- **UsedListing**: Individual marketplace listing scraped from a source
  - Properties: ListingId (GUID), CardModel (string), VramSize (int), Price (decimal), Source (enum: Facebook/CEX/eBay), ListingUrl (string), ScrapedAt (datetime), IsOutlier (bool)
  
- **UsedPriceAverage**: Aggregated average price per card model
  - Properties: CardModel (string), VramSize (int), AveragePrice (decimal), ListingCount (int), SourceBreakdown (JSON or nested object), CalculatedAt (datetime), Manufacturer (enum: Radeon/Nvidia)

- **ScrapeJob**: Metadata about each scraping run
  - Properties: JobId (GUID), RunAt (datetime), Source (enum), ListingsFound (int), Status (enum: Success/PartialFailure/Failure), ErrorMessage (string nullable)

**Key Relationships**:
- UsedListing → UsedPriceAverage (many-to-one grouping by CardModel)
- ScrapeJob tracks each marketplace scrape independently (one job per source per day)
- UsedPriceAverage is recalculated after each scrape; history may be preserved for future trend analysis but is not required for v1

**Notes**: 
- Listings older than 30 days can be purged (not needed for v1 calculations)
- Card model normalization may require a separate lookup/mapping table (GpuModelAlias)

---

## User Experience Flow

**Daily Background Process (invisible to user)**:

1. At 3:00 AM UTC, Hangfire triggers used market scraping job
2. System scrapes Facebook Marketplace UK for target GPU models → stores raw listings
3. System scrapes CEX UK for target GPU models → stores raw listings
4. System scrapes eBay UK for target GPU models → stores raw listings
5. For each card model found:
   - Calculate median price
   - Filter outliers (>2x or <0.5x median)
   - Calculate average price from remaining listings
   - Store UsedPriceAverage record with timestamp
6. Log job completion metrics (listings found, averages calculated, errors)

**User Viewing Dashboard**:

1. User visits GPU Value Tracker and selects "Radeon" or "Nvidia" mode
2. Dashboard loads used price data for selected manufacturer (from cache)
3. For each card displayed, user sees:
   - Card model name (e.g., "RX 7900 XT 20GB")
   - Average used price (e.g., "£480")
   - Number of listings (e.g., "Based on 8 listings")
   - Last updated timestamp (e.g., "Updated 6 hours ago")
4. User can hover/click to see source breakdown (e.g., "3 eBay, 4 Facebook, 1 CEX")
5. User compares used price against retail price to identify value opportunities

**Edge Case - No Listings Found**:

1. User views a card that has no recent used listings (e.g., rare older model)
2. Dashboard displays "No listings found" instead of price
3. User understands this card is not available on secondary market or is too rare to price

---

## Edge Cases & Constraints

- **Zero listings found for a card**: Display "No listings found" instead of showing stale data or "£0". User needs to know data is unavailable, not that the card is free.

- **All three marketplaces fail to scrape**: Retain previous day's data and display warning: "Used prices are [X] days old. Update in progress." Don't show blank dashboard.

- **Card model ambiguity**: If a listing title could match multiple cards (e.g., "RTX 4070" could be 4070 or 4070 Ti), discard the listing rather than guess. Log for manual review to improve model matching.

- **Multi-VRAM variants**: Cards like RTX 4060 Ti exist in 8GB and 16GB versions. Treat as separate models. Only track 16GB+ variant for this feature.

- **Auction listings on eBay**: Ignore auctions; only scrape "Buy It Now" listings. Auction prices don't represent asking price (they represent winning bid, which may be artificially low/high).

- **Currency conversion**: All prices must be in GBP. If a listing is in EUR or USD (rare on UK sites but possible), convert using daily exchange rate or discard.

- **Condition variance**: CEX may list "Good", "Fair", "Poor" condition. All conditions included in average, but outlier filter handles extreme price differences. User understands "average used price" includes a range of conditions.

- **Listing age**: Only include listings posted within the past 30 days. Older listings are likely stale or already sold. Facebook Marketplace may not provide date; if unavailable, include listing but flag for monitoring.

- **Duplicate listings**: Same seller may post the same card on eBay and Facebook. No de-duplication in v1 (too complex). Accept that some cards may be double-counted; this slightly inflates listing count but doesn't significantly skew average price.

- **VRAM listed incorrectly**: Some sellers list "16GB" in title when card is actually 12GB (e.g., RTX 4070). If model lookup says "4070 is 12GB" but listing says "16GB", trust model lookup and discard listing (it's likely a seller mistake).

---

## Out of Scope for This Feature

This feature explicitly does NOT include:

- **Historical price trends**: No graphs showing "RTX 4070 Ti used prices over the past 3 months". V1 only shows current average price. Historical tracking is a v2 feature.

- **Condition filtering**: No separate averages for "Good" vs "Fair" condition. User sees one average price across all conditions.

- **Seller reputation**: No tracking of whether listing is from a trusted seller or a new account. User sees price only.

- **Warranty status**: No indication of whether used card includes warranty or is sold "as-is".

- **Shipping costs**: Average price is asking price only; doesn't include shipping. User must factor in shipping separately when evaluating deals.

- **Regional price differences**: No breakdown by UK region (e.g., London vs Manchester). All UK listings are aggregated.

- **"Fair deal" recommendations**: No UI indicating "This is a good deal" or "Overpriced". User interprets the data themselves.

- **Link to individual listings**: No clickable links to eBay/Facebook/CEX listings. User uses the average price as a reference, then searches marketplaces themselves. (Linking to specific listings raises legal/affiliate questions and adds complexity.)

- **Notifications**: No alerts when a card's used price drops. User must check dashboard manually.

- **International marketplaces**: No US eBay, EU Facebook Marketplace, etc. UK only for v1.

---

## Open Questions for Tech Lead

- **Scraping legality/ethics**: Facebook Marketplace scraping may violate ToS. Should we use official APIs (if available) or accept risk of IP blocks? CEX and eBay have public pages but may still object to automated scraping.

- **Rate limiting**: What's an acceptable scrape frequency per marketplace to avoid being blocked? Should we rotate user agents or use proxies?

- **Model lookup table**: Should GPU model aliases be stored in the database (editable via admin UI) or hardcoded in the scraper? How do we maintain this as new cards release?

- **Cache duration**: Used price data refreshes daily. Should the frontend cache this data, or hit the API on every page load? What's the acceptable staleness for users?

- **Partial data handling**: If only 1 of 3 marketplaces successfully scrapes, do we show that data or wait until all 3 succeed? What's the minimum threshold for "reliable" data?

---

## Dependencies

**Depends On**: 
- Background job infrastructure (Hangfire) must be configured and running
- Database schema for storing UsedListing and UsedPriceAverage entities
- GpuModelAlias lookup table (or equivalent normalization logic) for card model identification

**Enables**: 
- Feature 3 (Value Visualization Dashboard) depends on this feature's data to compare used vs retail prices and highlight value opportunities
- Feature 5 (Radeon vs Nvidia Mode Switching) filters used price data by manufacturer