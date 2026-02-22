# QA Test Plan

**Date**: 2025-01-12  
**Scope**: Foundation + 5 features  
**Risk Level**: Medium

---

## Test Strategy

This application aggregates GPU pricing data from multiple sources (retail scrapers, used marketplaces) and presents it through a visual dashboard. Testing focuses on data integrity (scraper accuracy, outlier filtering, price calculations), API reliability (caching, error handling, performance), and frontend interactions (manufacturer toggling, value zone highlighting, responsive design). Foundation authentication and background jobs are critical paths requiring thorough integration testing.

**Test pyramid**:
- **Unit tests**: Business logic for price aggregation, outlier filtering, value zone calculations, model identification/normalization, scraper parsing logic, and validation rules
- **Integration tests**: End-to-end scraper workflows (fetch → parse → store → calculate averages), API endpoints with database/Redis interactions, background job execution, and authentication flows
- **E2E tests**: Critical user journeys only—dashboard visualization rendering, manufacturer toggle with data refresh, spec link navigation, and tooltip interactions

---

## Foundation Test Plan

### Authentication & Authorization

#### Unit Tests

| Test Case | Input | Expected Output |
|-----------|-------|----------------|
| Admin JWT generation | Valid admin credentials | JWT token with Admin role claim, 24-hour expiry |
| Admin JWT validation | Valid unexpired token | Token decoded, Admin role extracted |
| Admin JWT validation — expired token | Token with `exp` in past | 401 Unauthorized, error: "Token expired" |
| Admin JWT validation — invalid signature | Token with tampered signature | 401 Unauthorized, error: "Invalid token" |
| Admin JWT validation — missing role claim | Token without Admin role | 403 Forbidden, error: "Insufficient permissions" |

#### Integration Tests

| Scenario | Steps | Expected Result |
|----------|-------|----------------|
| Admin login flow | POST `/api/v1/auth/admin/login` with credentials → Check response headers | JWT token in HttpOnly cookie, 200 OK response |
| Protected endpoint access | Login → GET `/api/v1/admin/scraper/trigger` with token | 200 OK, scraper job queued |
| Protected endpoint access — no token | GET `/api/v1/admin/scraper/trigger` without cookie | 401 Unauthorized |
| Protected endpoint access — non-admin role | Login as non-admin → GET `/api/v1/admin/*` | 403 Forbidden |
| Token refresh | Use token 23 hours after issue | Token accepted (within 24h window) |

---

### Database & Entity Framework Core

#### Unit Tests

| Test Case | Input | Expected Output |
|-----------|-------|----------------|
| GPU entity — valid data | ModelId="rx-7900-xtx", Manufacturer="radeon", PerformanceScore=95 | Entity saved successfully |
| GPU entity — invalid manufacturer | Manufacturer="intel" (not in CHECK constraint) | Database exception: CHECK constraint violation |
| GPU entity — duplicate ModelId | Two GPUs with ModelId="rx-7900-xtx" | Database exception: UNIQUE constraint violation |
| RetailListing entity — null price | Price=null | Validation error: "Price is required" |
| RetailListing entity — negative price | Price=-50 | Validation error: "Price must be positive" |

#### Integration Tests

| Scenario | Steps | Expected Result |
|----------|-------|----------------|
| Seed GPU catalog | Run EF Core migration with seed data → Query gpus table | 33 GPU models present (RX 7000/6000, RTX 40/30 series) |
| GPU query by manufacturer | Query `gpus WHERE manufacturer='radeon'` | Returns only AMD cards (no Nvidia) |
| GPU query with eager loading | Query GPU with `.Include(RetailPrices)` | GPU entity includes related retail price records |
| Retail price average calculation | Insert 5 RetailListings → Calculate average via LINQ | Average matches manual calculation |
| Index performance | Query 1000 GPUs by manufacturer with/without index | WITH index: <50ms, WITHOUT index: >500ms (performance regression test) |

---

### API Infrastructure

#### Unit Tests

| Test Case | Input | Expected Output |
|-----------|-------|----------------|
| Error handling — 404 | Request to `/api/v1/nonexistent` | 404 Not Found, RFC 7807 ProblemDetails JSON |
| Error handling — 400 | Invalid query param: `?manufacturer=invalid` | 400 Bad Request, ProblemDetails with validation errors |
| Error handling — 500 | Unhandled exception in controller | 500 Internal Server Error, ProblemDetails (no stack trace in production) |
| CORS configuration | Request from `http://localhost:5173` with Origin header | Response includes `Access-Control-Allow-Origin: http://localhost:5173` |
| Rate limiting — admin endpoint | 6 requests to `/api/v1/admin/scraper/trigger` in 5 minutes | First request succeeds, 6th returns 429 Too Many Requests |

#### Integration Tests

| Scenario | Steps | Expected Result |
|----------|-------|----------------|
| Swagger/OpenAPI availability | GET `/swagger/v1/swagger.json` | 200 OK, valid OpenAPI 3.0 spec returned |
| Global exception logging | Trigger unhandled exception → Check Application Insights | Exception logged with stack trace, request context |
| Request logging | Make API call → Check logs | Request logged with method, path, status code, duration |
| Response compression | GET `/api/v1/gpus?manufacturer=radeon` with `Accept-Encoding: gzip` | Response has `Content-Encoding: gzip`, size <50% of uncompressed |

---

### Redis Caching

#### Unit Tests

| Test Case | Input | Expected Output |
|-----------|-------|----------------|
| Cache set | Key="test", Value="data", TTL=60s | Cache entry created, expires after 60s |
| Cache get — hit | Set key="test" → Get key="test" | Returns "data" |
| Cache get — miss | Get key="nonexistent" | Returns null |
| Cache expiry | Set key with 1s TTL → Wait 2s → Get key | Returns null (expired) |
| Cache invalidation | Set key="test" → Delete key="test" → Get key | Returns null |

#### Integration Tests

| Scenario | Steps | Expected Result |
|----------|-------|----------------|
| API response caching | GET `/api/v1/gpus?manufacturer=radeon` → Check Redis → Repeat request | First: cache miss (300ms), Second: cache hit (50ms), response identical |
| Cache key separation | Cache Radeon data → Cache Nvidia data | Keys `viz:radeon:current` and `viz:nvidia:current` both exist with different data |
| Cache TTL behavior | Cache data with 5-min TTL → Wait 6 min → Request data | Cache miss, fresh data fetched and cached again |
| Redis unavailable fallback | Stop Redis container → Make API request | Request succeeds (queries database directly), logs warning about cache unavailability |

---

### Background Jobs (Hangfire)

#### Unit Tests

| Test Case | Input | Expected Output |
|-----------|-------|----------------|
| Job scheduling | Schedule retail scraper for daily 2 AM UTC | Job appears in Hangfire dashboard with correct cron expression |
| Job execution | Trigger test job → Check job completion | Job status changes to "Succeeded", logs execution time |
| Job failure handling | Job throws exception → Check Hangfire logs | Job status "Failed", exception logged, no retry (manual only) |
| Job cancellation | Start long-running job → Cancel via dashboard | Job status "Cancelled", resources cleaned up |

#### Integration Tests

| Scenario | Steps | Expected Result |
|----------|-------|----------------|
| Retail scraper job execution | Trigger retail scraper manually → Wait for completion | ScraperLog record created, RetailListings inserted, RetailPriceAverages updated |
| Spec link validator job | Trigger validator → Check GPU.SpecUrlStatus | Broken links marked as "NeedsReview", active links remain "Active" |
| Hangfire dashboard access — admin | Login as admin → Visit `/hangfire` | Dashboard loads, shows job history |
| Hangfire dashboard access — unauthenticated | Visit `/hangfire` without login | 401 Unauthorized, redirected to login |
| Job retry behavior | Job fails → Check retry count | Retry count = 0 (manual retry only, no auto-retry per spec) |

---

### HTTP Client Service (Scraping)

#### Unit Tests

| Test Case | Input | Expected Output |
|-----------|-------|----------------|
| HTTP request — success | Mock 200 OK response | Response body returned, no exception |
| HTTP request — timeout | Mock request that takes 35 seconds (timeout=30s) | TaskCanceledException thrown after 30s |
| HTTP request — 404 | Mock 404 Not Found response | Exception thrown with "Resource not found" message |
| Retry logic | Mock 503 → 503 → 200 responses | First 2 attempts fail, 3rd succeeds after retry delays (1s, 2s) |
| Rate limiting | Send 10 requests with 1 req/sec limit | Each request delayed by ~1 second, total time ~10 seconds |

#### Integration Tests

| Scenario | Steps | Expected Result |
|----------|-------|----------------|
| eBay API integration | Call eBay Finding API with test credentials → Parse response | Valid JSON returned, listings extracted |
| CEX web scraping | HTTP GET to CEX search URL → Parse HTML | GPU prices extracted from product cards |
| Scraper timeout handling | Mock slow retailer (45s response) → Scraper runs | Request times out after 30s, other retailers continue |
| User-Agent verification | Make scraper request → Check request headers | User-Agent includes "GPUValueTracker/1.0" and contact email |

---

## Feature Test Plans

### FEAT-01: Live Retail Price Aggregation

**Risk areas**: Scraper failures cascading to stale data, outlier filtering removing valid prices, whitelist mismatches discarding legitimate listings

#### Unit Tests

| Test Case | Input | Expected Output |
|-----------|-------|----------------|
| Whitelist matching — exact match | Listing title: "RTX 4090", Whitelist: ["RTX 4090"] | Match found, listing processed |
| Whitelist matching — variant SKU | Listing title: "ASUS ROG Strix RTX 4090", Whitelist: ["RTX 4090"] | Match found (substring match), listing processed |
| Whitelist matching — no match | Listing title: "RTX 4070 Ti", Whitelist: ["RTX 4090", "RTX 4080"] | No match, listing discarded, logged |
| Price parsing — valid | HTML: `<span class="price">£899.99</span>` | Price extracted: 899.99 |
| Price parsing — currency mismatch | HTML: `<span class="price">€899.99</span>` | Price discarded (non-GBP), logged |
| Outlier filtering — retail | Prices: [£500, £520, £540, £1500], Median: £520 | Prices: [£500, £520, £540] (£1500 removed as >1.5x median) |
| Price average calculation | Valid prices: [£500, £520, £540] | MinPrice=£500, AvgPrice=£520, MaxPrice=£540 |
| Data freshness check | Listing scraped 25 hours ago | Listing excluded from average (>24h stale) |

#### Integration Tests

| Scenario | Steps | Expected Result |
|----------|-------|----------------|
| Full retail scrape job | Trigger job → Scrape Scan/Ebuyer/Amazon → Store listings | RetailListings table has 30+ rows (3 retailers × 10+ models), ScraperLog shows "Success" |
| Partial scraper failure | Mock Amazon 503 error → Run job | Scan/Ebuyer succeed, Amazon fails, job status "PartialFailure", averages calculated from 2 sources |
| Complete scraper failure | Mock all retailers down → Run job | Job status "Failure", no new listings, previous data retained, alert triggered |
| Average calculation after scrape | Insert 10 listings for RTX 4090 → Calculate averages | RetailPriceAverage record created with correct min/avg/max |
| Stale data exclusion | Insert listing with ScrapedAt = 26 hours ago → Calculate average | Stale listing excluded, ListingCount reflects only fresh listings |
| Manual scraper trigger | Admin clicks "Scrape Now" → Job runs | Job queued immediately (not at 2 AM schedule), returns jobId, admin can check status |

#### Edge Cases

| Case | Why it matters | Expected behaviour |
|------|---------------|-------------------|
| Zero listings after filtering | All scraped listings are outliers or stale | Display "No retail data available" (not £0 average) |
| Single in-stock listing | Only one retailer has stock | MinPrice = AvgPrice = MaxPrice = that listing's price, display with warning |
| Whitelist missing new GPU launch | RTX 5090 releases but not in whitelist | Listings discarded, logged as "unmatched", ops alerted to update whitelist |
| Retailer site structure change | Scan changes HTML, scraper can't find prices | Scraper fails for Scan only, other retailers continue, alert triggered |
| Price listed as "Call for Price" | Retailer doesn't show numeric price | Price extraction fails, listing discarded, logged |

---

### FEAT-02: Used Market Price Discovery

**Risk areas**: eBay API rate limiting breaking scraper, model identification failing on variant names, CEX scraping blocked by anti-bot measures

#### Unit Tests

| Test Case | Input | Expected Output |
|-----------|-------|----------------|
| Model identification — exact match | Listing: "RX 7900 XTX", JSON alias: "RX 7900 XTX" | Match found, canonical name: "RX 7900 XTX" |
| Model identification — fuzzy match | Listing: "AMD Radeon 7900XT 20GB", JSON alias: "7900 XT" | Match found, canonical name: "RX 7900 XT" |
| Model identification — VRAM mismatch | Listing: "RTX 4070 16GB", Model spec: 12GB | Listing discarded (VRAM mismatch), logged |
| VRAM variant handling | Listing: "RTX 4060 Ti 16GB", JSON has separate 8GB/16GB variants | Matched to "RTX 4060 Ti 16GB" entry (not 8GB) |
| Outlier filtering — used | Prices: [£400, £420, £440, £900], Median: £420 | Prices: [£400, £420, £440] (£900 removed as >2x median) |
| Price validation | Price: £35 | Discarded (<£50 minimum), logged as extraction error |
| Confidence calculation | Listing count: 2 | Confidence: "Low" |
| Confidence calculation | Listing count: 8 | Confidence: "High" |

#### Integration Tests

| Scenario | Steps | Expected Result |
|----------|-------|----------------|
| eBay API scraping | Trigger job → Call eBay Finding API → Store listings | UsedListings table has eBay source listings, prices in GBP |
| CEX web scraping | Trigger job → HTTP GET to CEX → Parse HTML → Store listings | UsedListings table has CEX source listings |
| Model normalization | Insert listing "ASUS ROG Strix RX 7900 XTX" → Normalize | Stored as canonical "RX 7900 XTX", grouped with other variants |
| Average calculation with confidence | Insert 2 used listings → Calculate average | UsedPriceAverage created with Confidence="Low", warning indicator |
| Outlier filtering integration | Insert 10 listings (1 outlier) → Calculate average | Average excludes outlier, OutlierCount=1 logged |
| Source breakdown tracking | eBay: 5 listings, CEX: 3 listings → Calculate | SourceBreakdown JSON: `{"eBay": 5, "CEX": 3}` |
| Data staleness handling | All listings >3 days old → API request | API returns `is_available: false`, frontend hides prices |

#### Edge Cases

| Case | Why it matters | Expected behaviour |
|------|---------------|-------------------|
| eBay API rate limit hit | 5000 daily calls exceeded | Job completes with partial data, logs warning, alert sent, resumes next day |
| CEX returns CAPTCHA | Anti-scraping triggered | CEX scrape fails, eBay data continues, status "PartialFailure", alert sent |
| Zero listings for card | No used market for rare card | Display "No used listings found" (not £0) |
| All listings filtered as outliers | All prices are extreme | Display "Data quality insufficient" (not average from 0 listings) |
| Non-GBP eBay listing | Listing in EUR (seller error) | Listing discarded, logged, does not pollute GBP averages |
| Duplicate cross-post | Same card on eBay + CEX by same seller | Both counted (no de-duplication in v1), acceptable per spec |

---

### FEAT-03: Value Visualization Dashboard

**Risk areas**: Performance with 50+ data points, value zone highlighting missing genuine deals, touch interactions failing on mobile

#### Unit Tests

| Test Case | Input | Expected Output |
|-----------|-------|----------------|
| Performance score lookup | ModelId: "rx-7900-xtx" | PerformanceScore: 95 retrieved from database |
| Value zone calculation — eligible | Used RX 7900 XTX: perf=95, price=£650; Retail RX 7900 XT: perf=88, price=£700 | Used 7900 XTX marked as value zone (95 > 88 * 1.10) |
| Value zone calculation — not eligible | Used RX 7800 XT: perf=75, price=£500; Retail RX 7800 XT: perf=75, price=£499 | Not value zone (performance equal, price higher) |
| Low-listing exclusion | Used listing count: 2 | Not eligible for value zone highlighting (confidence too low) |
| Dual price point rendering | GPU has retail=£899, used=£650 | Two data points rendered: one blue (retail), one green (used), same Y-position |
| Outlier exclusion from display | Retail prices: [£500, £520, £1500 outlier], Avg calculated from [£500, £520] | Chart shows avg=£510 (outlier excluded), tooltip says "2 valid listings (1 outlier excluded)" |

#### Integration Tests

| Scenario | Steps | Expected Result |
|----------|-------|----------------|
| API endpoint — Radeon data | GET `/api/v1/visualization/data?manufacturer=radeon` | Returns 12-15 GPU models, includes retail/used prices, performance scores, value zone flags |
| API endpoint — Nvidia data | GET `/api/v1/visualization/data?manufacturer=nvidia` | Returns 9-15 GPU models, separate from Radeon data |
| Redis cache hit | Request Radeon data twice within 5 minutes | First: cache miss (300ms), Second: cache hit (50ms), ETag header matches |
| Redis cache miss | Request after 6 minutes → Cache expired | Fresh data fetched (300ms), new cache entry created |
| Chart rendering — desktop | Load dashboard → Wait for chart render | Recharts ScatterChart visible, X-axis (price), Y-axis (performance 0-100) |
| Chart rendering — tablet | Load on 768px viewport → Check chart | Chart scaled down, touch interactions enabled |
| Tooltip on hover | Hover over data point | Tooltip shows: model name, price, listing count, last updated, OEM link |
| Tooltip on tap (mobile) | Tap data point on touch device | Tooltip appears, tap elsewhere dismisses |
| Value zone highlighting | Value zone GPU in data | Yellow glow/border around used data point, tooltip shows "VALUE OPPORTUNITY" badge |

#### Edge Cases

| Case | Why it matters | Expected behaviour |
|------|---------------|-------------------|
| Zero GPUs returned (cold start) | No data scraped yet | Empty state: "Data loading, check back soon" |
| Chart with 60+ data points (older GPUs enabled) | Crowding concern | All points render, may feel busy but functional, zoom/pan not needed in v1 |
| Missing OEM URL for GPU | GPU.OemProductUrl is null | Tooltip omits "View Official Specs" link (graceful degradation) |
| Data refresh mid-session | Scraper runs while user has page open | User sees stale data until manual browser refresh (no real-time notification per spec) |
| Stale data >24 hours | Price data not updated | Yellow warning banner: "Price data outdated — last update 26 hours ago" |
| Low-listing asterisk display | GPU has 2 listings | Price shows "£420*", tooltip warns "Only 2 listings — may be unreliable" |

---

### FEAT-04: Manufacturer Reference Links

**Risk areas**: Spec URL validation job missing broken links, discontinued GPUs showing stale links, CSV import populating wrong URLs

#### Unit Tests

| Test Case | Input | Expected Output |
|-----------|-------|----------------|
| URL validation — 200 OK | Mock HTTP HEAD to AMD URL → 200 OK | SpecUrlStatus: "Active", SpecUrlLastChecked updated |
| URL validation — 404 Not Found | Mock HTTP HEAD to Nvidia URL → 404 | SpecUrlStatus: "NeedsReview", logged for manual review |
| URL validation — timeout | Mock HTTP HEAD that times out after 15s | SpecUrlStatus: "NeedsReview", logged |
| CSV import — valid row | CSV: `rx-7900-xtx,https://amd.com/...` | GPU.OfficialSpecUrl populated, status: "Active" |
| CSV import — invalid URL format | CSV: `rx-7900-xtx,not-a-url` | Validation error, row rejected, error logged |
| CSV import — empty URL (discontinued) | CSV: `rx-6700-xt,` (empty) | GPU.SpecUrlStatus set to "Unavailable", no URL stored |

#### Integration Tests

| Scenario | Steps | Expected Result |
|----------|-------|----------------|
| CSV import workflow | Generate CSV with script → Product owner reviews → Import to DB | All GPUs have OfficialSpecUrl populated, status: "Active" |
| Weekly validation job | Trigger job → Validate all Active URLs | Broken links marked "NeedsReview", logs show which URLs failed |
| Validation job rate limiting | Job validates 100 GPUs → Check request timing | 1 request per second, total runtime ~2 minutes |
| Manual status update (admin) | Admin marks URL as "Unavailable" via backoffice → Save | Status updated, link hidden from users immediately |
| Spec link rendering — active | GPU with status="Active" → Render card footer | "Official Specs ↗️" link visible, clickable |
| Spec link rendering — unavailable | GPU with status="Unavailable" → Render card footer | "Specs Unavailable" text displayed (not clickable) |
| Link click behavior | User clicks "Official Specs" link | Opens AMD/Nvidia page in new tab with `rel="noopener noreferrer"` |

#### Edge Cases

| Case | Why it matters | Expected behaviour |
|------|---------------|-------------------|
| Manufacturer site down during validation | AMD.com returns 503 for all requests | All AMD links marked "NeedsReview", monitoring alert triggered, ops investigates |
| Validation detects URL moved (301 redirect) | Link redirects to new location | Follow redirect, validate final URL, log warning if destination differs |
| CSV import with duplicate ModelIds | Two rows for "rx-7900-xtx" | Validation error, import rejected, error logged |
| User clicks link marked "NeedsReview" before manual review | Edge case: status changed during user session | User cannot click (link replaced with "Specs Unavailable" text) |
| Special edition GPU (e.g., RX 7900 XTX Aqua) | Different URL from reference model | Stored as separate GPU row with distinct URL |

---

### FEAT-05: Radeon vs Nvidia Mode Switching

**Risk areas**: localStorage corruption breaking mode selection, rapid toggling causing race conditions, cache invalidation failing

#### Unit Tests

| Test Case | Input | Expected Output |
|-----------|-------|----------------|
| localStorage read — valid | localStorage: `{"preferredManufacturer": "radeon"}` | Mode initialized to Radeon |
| localStorage read — invalid value | localStorage: `{"preferredManufacturer": "intel"}` | Default to Radeon, overwrite localStorage with valid value |
| localStorage read — empty | localStorage empty (first visit) | Default to Radeon |
| Mode toggle | User clicks "Nvidia" toggle → State updates | selectedManufacturer: "nvidia", localStorage updated |
| API request with mode | selectedManufacturer="nvidia" | API called with query param: `?manufacturer=nvidia` |
| TanStack Query cache key | Mode="radeon" | Query key: `['gpus', 'radeon']` (separate from Nvidia cache) |

#### Integration Tests

| Scenario | Steps | Expected Result |
|----------|-------|----------------|
| First visit flow | Load dashboard → Check localStorage → Render | Radeon mode active, API fetches Radeon data, localStorage set |
| Mode toggle flow | Click "Nvidia" → Check API call → Check chart | API called with `?manufacturer=nvidia`, chart re-renders with Nvidia GPUs |
| Rapid toggling | Click Nvidia → Click Radeon immediately (before response) | First request cancelled via AbortController, only Radeon data renders |
| Cache hit on toggle back | Toggle Radeon → Nvidia → Radeon within 5 min | Third toggle uses cached data (0ms load time) |
| Cache miss on toggle | Toggle to Nvidia after 6 min → Check cache | Cache expired, fresh data fetched, new cache entry created |
| Loading state timing | Slow API response (250ms) | No loading indicator for first 200ms, then skeleton appears |
| Error during toggle | API returns 500 → User toggles to other manufacturer | Error dismissed, new request starts, retry counter resets |
| Auto-retry on failure | API fails → Check retry | Auto-retries 3 times (1s, 2s, 4s delays), shows error after 4th failure |

#### Edge Cases

| Case | Why it matters | Expected behaviour |
|------|---------------|-------------------|
| localStorage unavailable (privacy mode) | Some users block storage | Mode defaults to Radeon on every visit, toggle works within session (React state) |
| API returns empty GPU list | Scraper failed for selected manufacturer | Empty state: "No Nvidia data available. Try Radeon." |
| Invalid manufacturer in URL (manual edit) | User types `?manufacturer=intel` | API returns 400 Bad Request, frontend shows error, reverts to stored localStorage value |
| Toggle during error state | API fails for Radeon, user toggles to Nvidia | Error dismissed, Nvidia request starts fresh (no error inheritance) |
| Concurrent tabs | User has two tabs open, toggles in both | Each tab manages own cache (no cross-tab sync in v1), acceptable per spec |

---

## E2E Test Scenarios

Keep E2E tests narrow — cover the critical user journeys only.

| Journey | Steps | Pass Criteria |
|---------|-------|--------------|
| Admin triggers retail scrape | Navigate to `/admin/retail-scraper` → Click "Scrape Now" → Wait 2 min → Refresh page | Job status shows "Success", listing count >0, timestamp updated |
| User views Radeon dashboard (default) | Open homepage → Wait for dashboard load | Radeon GPUs visible, chart renders, toggle shows "Radeon" active |
| User switches to Nvidia mode | Click "Nvidia" toggle → Wait for data load | Chart updates with Nvidia GPUs, used/retail prices update, toggle shows "Nvidia" active |
| User hovers over value zone GPU | Hover over green data point with yellow glow → Read tooltip | Tooltip shows "VALUE OPPORTUNITY" badge, price, listing count, OEM link |
| User clicks spec link | Hover GPU card → Click "Official Specs ↗️" → Check new tab | AMD/Nvidia product page opens in new tab, original dashboard tab remains |
| User toggles "Show older GPUs" | Check "Show older GPUs" checkbox → Wait for chart update | RX 6000 / RTX 30 series appear on chart, total data points increase |
| Mobile user taps GPU (touch) | Load dashboard on tablet (768px) → Tap data point → Tap elsewhere | Tooltip appears on tap, dismisses when tapping empty space |
| User views stale data warning | Mock data >24 hours old → Load dashboard | Yellow banner: "Price data outdated — last update 26 hours ago" |

---

## Test Data Requirements

| Data Type | Specification | Notes |
|-----------|--------------|-------|
| Valid admin credentials | email: admin@gputracker.com, password: Admin123!@# | Standard admin for protected endpoints |
| GPU catalog (seeded) | 33 models: RX 7000 (7), RTX 40 (9), RX 6000 (9), RTX 30 (8) | Foundation seed data, includes performance scores |
| Retail listings | 10 listings per model (Scan/Ebuyer/Amazon mix), prices £400-£1500 | Used for average calculations, mix of in-stock and out-of-stock |
| Used listings | 5-10 listings per model (eBay/CEX mix), prices £300-£1200 | Some with low counts (<3) to test confidence indicators |
| Outlier listings | Retail: £3000 (>1.5x median), Used: £5000 (>2x median) | Test outlier filtering logic |
| Stale listings | ScrapedAt: 25 hours ago | Test data freshness exclusion |
| Invalid manufacturer values | "intel", "amd" (wrong case), "unknown" | Test validation and normalization |
| Broken spec URLs | https://amd.com/nonexistent-page | Test URL validation job flagging |
| Valid spec URLs | https://www.amd.com/en-gb/products/graphics/amd-radeon-rx-7900-xtx.html | Test active link rendering |

---

## Risk Areas Requiring Extra Coverage

| Area | Risk | Extra Coverage Needed |
|------|------|----------------------|
| Scraper data extraction | HTML structure changes break parsing, causing silent failures | Unit tests with fixture HTML snapshots for each retailer; integration tests with live sandbox URLs (if available); monitor logs for "unmatched listing" spikes |
| Outlier filtering | Over-aggressive filtering removes legitimate price spikes; under-aggressive allows scam listings | Property-based testing with generated price distributions; manual review of OutlierLog table weekly; test boundary conditions (exactly 2x median, 1.5x median) |
| Value zone calculation | Logic error causes false positives (highlighting overpriced cards) or false negatives (missing genuine deals) | Test all combinations: used<retail with perf+10%, used=retail with perf+10%, used>retail with perf+10%; visual regression testing on dashboard to catch unexpected highlights |
| Performance with large datasets | Chart rendering slows with >50 data points, Redis cache misses under load | Load test API with 100 concurrent requests; render test with 100 GPU data points; benchmark Redis cache hit/miss ratios; monitor API response times in production |
| eBay API rate limiting | Exceeding 5000 calls/day breaks scraper silently | Unit test job behavior at 4999/5000 calls; integration test with mock 429 responses; alert when daily call count >4500 (80% threshold) |
| Cache invalidation race conditions | User toggles modes rapidly, sees stale data from wrong manufacturer | Concurrency test: 10 rapid toggles (Radeon↔Nvidia) in 5 seconds; verify only last selection's data renders; test AbortController cancellation |
| Mobile touch interactions | Tooltips don't appear or don't dismiss on tap | E2E test on real mobile device (not just Chrome DevTools emulation); test tap, drag, pinch gestures; verify tooltip z-index above other elements |

---

## What the Engineering Spec Must Include

To enable testing, every engineering spec must include:

- [x] **Acceptance criteria as testable statements** (e.g., "Average price is calculated excluding listings older than 24 hours" — not "price calculation works correctly")
- [x] **Explicit error response shapes for every error case** (e.g., "API returns 400 Bad Request with ProblemDetails JSON: `{ "type": "...", "title": "Invalid manufacturer", "status": 400, "detail": "..." }`")
- [x] **Business rule numbers** (e.g., "BR-3: Outlier filtering uses 2x median for used, 1.5x for retail" — so tests can reference rules directly)
- [x] **Explicit field constraints** (e.g., "Price must be DECIMAL(10,2), range £50-£5000" — for boundary testing)

**Gaps to address in engineering specs**:
- BR numbers not assigned in feature specs — add explicit "BR-01: Whitelist matching", "BR-02: Outlier filtering", etc.
- Some error responses are described but not given status codes (e.g., "validation error" — should be "400 Bad Request with field-level errors array")
- Performance targets mentioned ("API <500ms") but not tied to specific load scenarios (10 users? 100 users? Need concurrency specs)

---

## Out of Scope

- **Performance testing / load testing**: Not covered in v1 test plan. Will monitor production metrics and add load tests in v2 if performance issues arise. Foundation allows for this (Redis caching, API rate limiting) but formal load testing requires production-like traffic patterns.
- **Security penetration testing**: Owned by AppSec team. Test plan assumes standard ASP.NET Core security practices (HttpOnly cookies, CORS, rate limiting) are correctly implemented. Does not cover OWASP Top 10 testing, XSS/CSRF/injection attack simulation.
- **Test implementation**: QA defines WHAT to test; engineers implement HOW. This plan provides test cases with inputs/outputs; engineers write xUnit/Vitest/Playwright code.
- **Accessibility testing**: WCAG AA compliance assumed for features (color contrast, keyboard nav, screen reader support). Not explicitly tested in this plan. Recommend accessibility audit by specialist before production launch.
- **Cross-browser compatibility**: Test plan assumes latest Chrome/Firefox/Safari/Edge. No IE11 support. Engineers should run Playwright tests across browsers, but browser-specific bugs are out of scope for initial test plan.

---

## Quality Checklist

- [x] Every feature has a test plan
- [x] All happy paths covered (Radeon mode, Nvidia mode, value zones, spec links, scraper success)
- [x] Common error paths covered (invalid manufacturer, 404, scraper failure, cache miss, stale data)
- [x] Edge cases identified and documented (zero listings, outlier-only data, rapid toggling, localStorage unavailable)
- [x] E2E tests cover only critical user journeys (8 scenarios, not exhaustive)
- [x] Test data requirements are specific (33 GPUs seeded, outlier prices defined, admin credentials)
- [x] Risk areas called out (scraper parsing, outlier filtering, value zone logic, performance, rate limiting)
- [x] No implementation code (test plan is specification, not code)
- [x] No vague test cases (all have explicit inputs/outputs)

---

**Status**: ✅ Ready for Engineering Implementation

This test plan covers foundation infrastructure (auth, database, API, Redis, Hangfire, HTTP client) and all 5 features with unit, integration, and E2E tests. Engineers can use this as specification for writing test code. Risk areas requiring extra monitoring have been flagged. Test data requirements are defined for seeding and fixture generation.