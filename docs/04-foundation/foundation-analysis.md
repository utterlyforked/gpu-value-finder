# Foundation Analysis & Build Plan

**Date**: 2025-01-12
**Status**: Ready for Engineering Specification
**Features Analyzed**: 5 features (FEAT-01 through FEAT-05)

---

## Executive Summary

After analyzing 5 features, I've identified **17 foundation elements** that must be built before feature development can begin. The foundation includes core entities (User, GPU models), authentication infrastructure, API patterns, frontend shell, and shared services needed by multiple features.

The foundation blocks all features for approximately **2 weeks**. Features can then be built in **2 phases**:
- **Phase 1** (3 features): Can build in parallel after foundation completion
- **Phase 2** (2 features): Depend on Phase 1 completion

Total estimated timeline: **2 weeks foundation + 3-4 weeks Phase 1 + 1-2 weeks Phase 2 = 6-8 weeks to MVP**

---

## Foundation Elements

These are shared components used by multiple features.

### 1. Core Entities

**GPU (Graphics Processing Unit)**
- Purpose: Represents GPU models tracked across retail/used markets
- Used by: All 5 features
- Properties:
  - `Id` (Guid, PK)
  - `ModelId` (string, unique) - e.g., "rx-7900-xtx"
  - `ReferenceName` (string) - "AMD Radeon RX 7900 XTX" (display name)
  - `Manufacturer` (enum: Radeon/Nvidia) - with CHECK constraint on lowercase values
  - `Generation` (string) - "RX 7000", "RTX 40", etc.
  - `VramGB` (int) - 16, 24, etc.
  - `PerformanceScore` (int, 1-100) - Ordinal ranking for visualization
  - `IsCurrentGen` (bool) - True for latest generation
  - `OfficialSpecUrl` (string, nullable) - Manufacturer product page
  - `SpecUrlStatus` (enum: Active/Unavailable/NeedsReview)
  - `SpecUrlLastChecked` (DateTime, nullable)
  - `CreatedAt`, `UpdatedAt` (DateTime)
- Relationships:
  - Has many `RetailListings`
  - Has many `UsedListings`
  - Has many `RetailPriceAverages` (historical snapshots)
  - Has many `UsedPriceAverages` (historical snapshots)
- Indexes: `Manufacturer`, `IsCurrentGen`, `ModelId` (unique)

**RetailListing**
- Purpose: Individual retailer listing scraped from source
- Used by: FEAT-01 (Retail Price Aggregation), FEAT-03 (Visualization)
- Properties:
  - `Id` (Guid, PK)
  - `GpuModelId` (Guid, FK → GPU)
  - `Retailer` (enum: Scan/Ebuyer/Amazon)
  - `Price` (decimal) - GBP amount
  - `IsInStock` (bool)
  - `ProductUrl` (string, nullable) - Link to retailer page
  - `ScrapedAt` (DateTime)
  - `IsOutlier` (bool) - Flagged during calculation
- Relationships: Belongs to `GPU`
- Indexes: `GpuModelId`, `ScrapedAt DESC`, `Retailer`

**RetailPriceAverage**
- Purpose: Aggregated retail price snapshot per GPU model
- Used by: FEAT-01, FEAT-03, FEAT-05
- Properties:
  - `Id` (Guid, PK)
  - `GpuModelId` (Guid, FK → GPU)
  - `MinPrice`, `AvgPrice`, `MaxPrice` (decimal)
  - `ListingCount`, `InStockCount` (int)
  - `IsInStock` (bool) - Any retailer has stock
  - `LastScrapedAt` (DateTime)
  - `Status` (enum: Active/Inactive/Archived)
- Relationships: Belongs to `GPU`
- Indexes: `GpuModelId`, `Status`

**UsedListing**
- Purpose: Individual marketplace listing scraped from eBay/CEX
- Used by: FEAT-02 (Used Market Discovery), FEAT-03 (Visualization)
- Properties:
  - `Id` (Guid, PK)
  - `GpuModelId` (Guid, FK → GPU)
  - `Source` (enum: eBay/CEX)
  - `Price` (decimal) - GBP amount
  - `ListingUrl` (string, nullable)
  - `ScrapedAt` (DateTime)
  - `IsOutlier` (bool)
- Relationships: Belongs to `GPU`
- Indexes: `GpuModelId`, `ScrapedAt DESC`, `Source`

**UsedPriceAverage**
- Purpose: Aggregated used market price snapshot per GPU model
- Used by: FEAT-02, FEAT-03, FEAT-05
- Properties:
  - `Id` (Guid, PK)
  - `GpuModelId` (Guid, FK → GPU)
  - `AveragePrice` (decimal)
  - `ListingCount` (int)
  - `SourceBreakdown` (JSONB) - `{"eBay": 5, "CEX": 3}`
  - `Confidence` (enum: Low/Medium/High)
  - `CalculatedAt` (DateTime)
- Relationships: Belongs to `GPU`
- Indexes: `GpuModelId`, `CalculatedAt DESC`

**ScraperLog**
- Purpose: Tracks scraper job execution history
- Used by: FEAT-01, FEAT-02 (monitoring/debugging)
- Properties:
  - `Id` (Guid, PK)
  - `JobType` (enum: Retail/Used)
  - `StartedAt`, `CompletedAt` (DateTime)
  - `Status` (enum: Success/PartialFailure/Failure)
  - `RetailerStatuses` (JSONB) - Per-source success/failure
  - `RecordsUpdated` (int)
  - `ErrorMessages` (text, nullable)
- Indexes: `StartedAt DESC`, `JobType`

---

### 2. Authentication & Authorization

**Required Capabilities**:
- Admin authentication (JWT tokens via HttpOnly cookies)
- Session management (Redis-backed sessions)
- Role-based authorization (`Admin` role for backoffice)

**Authorization Policies Needed**:
- `AdminOnly` - User has Admin role (for manual scraper triggers, monitoring dashboards)

**Used by**: FEAT-01 (manual scraper trigger), FEAT-02 (manual scraper trigger), FEAT-04 (spec link validation admin view)

**Implementation Notes**:
- ASP.NET Core Identity tables NOT needed (no user accounts for public site in MVP)
- Simple JWT authentication for admin backoffice access only
- Tokens stored in HttpOnly cookies (secure, not accessible via JavaScript)
- Redis stores active admin sessions for fast validation

---

### 3. API Infrastructure

**Required**:
- Base API structure (`/api/v1/...` prefix)
- Global error handling (RFC 7807 ProblemDetails format)
- CORS configuration (allow frontend origin)
- Request/response logging (Application Insights)
- Rate limiting (on admin endpoints only for MVP)
- Swagger/OpenAPI documentation

**Used by**: All features

**Patterns**:
- RESTful conventions
- Consistent error responses
- Cache headers (`ETag`, `Cache-Control`) for visualization API
- API versioning via URL path

---

### 4. Frontend Infrastructure

**Required**:
- React 18 app shell with TypeScript
- Routing setup (React Router v6)
- TanStack Query configuration (API client with caching)
- Tailwind CSS configuration
- Common layout components (Header, Footer if needed)
- Error boundaries
- Loading state patterns (skeleton UI)
- Browser localStorage utilities (for manufacturer preference)

**Used by**: All features

**Patterns**:
- Functional components only
- Props interfaces for all components
- Strict TypeScript (no `any` types)
- Context API for global state (manufacturer selection)

---

### 5. Shared Services

**Redis Caching Service**
- Purpose: Cache API responses, session data
- Used by: FEAT-01 (retail prices), FEAT-02 (used prices), FEAT-03 (visualization data), FEAT-05 (manufacturer-specific cache keys)
- Integration: StackExchange.Redis NuGet package
- Cache keys: `viz:radeon:current`, `viz:nvidia:current`, `retail-prices:{manufacturer}`, `used-prices:{manufacturer}`
- TTL: 5-15 minutes depending on data type

**Background Job Service (Hangfire)**
- Purpose: Schedule and execute recurring scraper jobs
- Used by: FEAT-01 (daily 2 AM retail scrape), FEAT-02 (daily 3 AM used scrape), FEAT-04 (weekly Sunday 2 AM spec link validation)
- Integration: Hangfire with PostgreSQL storage
- Dashboard: Admin-only access at `/hangfire`

**HTTP Client Service**
- Purpose: Reusable HTTP client for web scraping
- Used by: FEAT-01 (retailer scraping), FEAT-02 (eBay API + CEX scraping), FEAT-04 (spec link validation)
- Features: Retry policies, rate limiting, timeout handling, user-agent configuration
- Integration: HttpClientFactory with Polly for resilience

**Logging & Monitoring Service**
- Purpose: Structured logging and error tracking
- Used by: All features
- Integration: Application Insights (or Seq for local dev)
- Patterns: Structured log events with context (job IDs, GPU models, prices)

---

## Feature Dependency Analysis

### Feature: FEAT-01 - Live Retail Price Aggregation

**Foundation Dependencies**:
- ✅ GPU entity
- ✅ RetailListing entity
- ✅ RetailPriceAverage entity
- ✅ ScraperLog entity
- ✅ Background Job Service (Hangfire)
- ✅ HTTP Client Service (for retailer scraping)
- ✅ Redis Caching Service
- ✅ API infrastructure
- ✅ Admin authentication (for manual trigger)

**Feature Dependencies**:
- None (can build immediately after foundation)

**Build Phase**: Phase 1

**Rationale**: Independent of other features, only needs foundation entities and services. Retail scraping can operate standalone.

---

### Feature: FEAT-02 - Used Market Price Discovery

**Foundation Dependencies**:
- ✅ GPU entity (to link used listings to models)
- ✅ UsedListing entity
- ✅ UsedPriceAverage entity
- ✅ ScraperLog entity
- ✅ Background Job Service (Hangfire)
- ✅ HTTP Client Service (for eBay API + CEX scraping)
- ✅ Redis Caching Service
- ✅ API infrastructure
- ✅ Admin authentication (for manual trigger)
- ✅ `gpu-models.json` reference file (for model identification)

**Feature Dependencies**:
- **Soft dependency on FEAT-01**: Uses same GPU catalog, but FEAT-02 spec states "Scrape used prices only for cards that have retail price data." This means FEAT-02's scraper reads from the same `GPU` table that FEAT-01 populates.
- However, FEAT-02 can be **developed in parallel** with FEAT-01 if we:
  1. Seed GPU table with initial models during foundation phase
  2. Both features read from/write to `GPU` table independently
  3. FEAT-02's "only scrape cards with retail data" logic can check `RetailPriceAverage` table (will be empty until FEAT-01 runs, but query works)

**Build Phase**: Phase 1 (with caveat)

**Rationale**: Can develop in parallel with FEAT-01, but **first scraper run** should happen after FEAT-01's first run to ensure GPU catalog is populated. For development, seed test data.

---

### Feature: FEAT-03 - Value Visualization Dashboard

**Foundation Dependencies**:
- ✅ GPU entity (with PerformanceScore field)
- ✅ RetailPriceAverage entity
- ✅ UsedPriceAverage entity
- ✅ API infrastructure
- ✅ Frontend infrastructure (React app shell, TanStack Query)
- ✅ Redis Caching Service (for visualization API responses)

**Feature Dependencies**:
- **Requires FEAT-01**: Needs `RetailPriceAverage` data to display retail prices
- **Requires FEAT-02**: Needs `UsedPriceAverage` data to display used prices
- **Requires FEAT-05**: Needs manufacturer toggle to filter data

**Build Phase**: Phase 2

**Rationale**: Cannot function without price data from FEAT-01 and FEAT-02. Visualization is the consumer of data produced by scraping features. Also depends on FEAT-05's toggle component being available.

---

### Feature: FEAT-04 - Manufacturer Reference Links

**Foundation Dependencies**:
- ✅ GPU entity (OfficialSpecUrl field already included in core entity definition)
- ✅ Background Job Service (for weekly spec link validation)
- ✅ HTTP Client Service (for URL validation)
- ✅ Admin authentication (for monitoring dashboard)

**Feature Dependencies**:
- None (operates independently—adds data to GPU entity but doesn't depend on other features)

**Build Phase**: Phase 1

**Rationale**: Can develop in parallel with FEAT-01/02. Adds `OfficialSpecUrl` and validation logic to GPU entity. Visualization (FEAT-03) will consume these URLs once available.

---

### Feature: FEAT-05 - Radeon vs Nvidia Mode Switching

**Foundation Dependencies**:
- ✅ GPU entity (with Manufacturer field)
- ✅ Frontend infrastructure (React Context API for state management)
- ✅ localStorage utilities
- ✅ API infrastructure (manufacturer query parameter support)

**Feature Dependencies**:
- None for **toggle component itself** (can build standalone)
- But **toggle is consumed by FEAT-03** (visualization needs the toggle to filter data)

**Build Phase**: Phase 1 (component), integrated in Phase 2 (with FEAT-03)

**Rationale**: Toggle component can be built early and tested with mock data. Integration with visualization happens in Phase 2 when FEAT-03 is built.

---

## Build Phases

### Phase 0: Foundation (Blocks Everything)

**Duration**: 2 weeks

**Scope**:

**Database & Entities** (Week 1, Days 1-3):
- PostgreSQL database provisioned
- EF Core migrations for core entities:
  - `GPU` table with all fields (ModelId, Manufacturer, PerformanceScore, OfficialSpecUrl, etc.)
  - `RetailListings`, `RetailPriceAverages`, `UsedListings`, `UsedPriceAverages` tables
  - `ScraperLogs` table
  - Indexes on all foreign keys and query-critical fields
- Seed GPU catalog with initial models:
  - RX 7000 series (7 models) with performance scores
  - RTX 40 series (9 models) with performance scores
  - RX 6000 series (9 models, marked `IsCurrentGen = false`)
  - RTX 30 series (8 models, marked `IsCurrentGen = false`)
- Total: ~33 GPU models seeded

**Backend Infrastructure** (Week 1, Days 4-5):
- ASP.NET Core 8 Web API project setup
- Swagger/OpenAPI configuration
- Global error handling middleware (RFC 7807 ProblemDetails)
- CORS configuration for frontend origin
- Application Insights integration (or Seq for local dev)
- Admin JWT authentication (minimal—no user registration, just hard-coded admin credentials for MVP)
- Rate limiting middleware (admin endpoints only)

**Caching & Background Jobs** (Week 2, Days 1-2):
- Redis setup (local Docker container + Azure Redis Cache config for production)
- StackExchange.Redis integration
- Cache service abstraction (`ICacheService`)
- Hangfire setup with PostgreSQL storage
- Hangfire dashboard secured with admin auth
- HTTP Client Factory with Polly retry policies

**Frontend Infrastructure** (Week 2, Days 3-5):
- React 18 + TypeScript + Vite project scaffold
- Tailwind CSS configuration
- React Router v6 setup with basic routes:
  - `/` → Dashboard (placeholder)
  - `/admin` → Admin backoffice (placeholder)
- TanStack Query setup with axios
- Error boundary component
- Loading skeleton components (reusable)
- localStorage utility functions
- Basic layout (header with logo/title, main content area, footer optional)

**Deliverable**: 
- Running ASP.NET Core API with Swagger at `https://localhost:7000/swagger`
- Running React app at `http://localhost:5173`
- Database with seeded GPU catalog
- Redis and Hangfire operational
- Admin can log in to `/admin` (placeholder page)
- API endpoint `GET /api/v1/gpus?manufacturer=radeon` returns seeded data (even though no prices yet)

**Definition of Done**:
- [ ] All EF Core migrations run successfully
- [ ] Seed data script populates 33 GPU models
- [ ] API returns 200 OK for `GET /api/v1/gpus?manufacturer=radeon` with empty price fields
- [ ] Frontend renders "GPU Value Tracker" dashboard shell
- [ ] Redis cache set/get works (smoke test)
- [ ] Hangfire dashboard accessible at `https://localhost:7000/hangfire`
- [ ] Admin login works (returns JWT token)

---

### Phase 1: Independent Features (3-4 weeks, parallel development)

**Features**:
- **FEAT-01**: Live Retail Price Aggregation
- **FEAT-02**: Used Market Price Discovery
- **FEAT-04**: Manufacturer Reference Links
- **FEAT-05**: Radeon vs Nvidia Mode Switching (component only)

**Parallel Work Streams**:

**Stream A: Retail Scraping (FEAT-01)** - 1 developer, 2 weeks
- Week 1: Scraper implementation (Scan, Ebuyer, Amazon) with whitelist matching
- Week 2: Price aggregation logic, outlier filtering, API endpoints, manual trigger admin UI
- Deliverable: Daily 2 AM scraper populates `RetailPriceAverages`, API returns retail prices

**Stream B: Used Scraping (FEAT-02)** - 1 developer, 2 weeks
- Week 1: eBay API integration, CEX scraper, model identification via `gpu-models.json`
- Week 2: Price aggregation, outlier filtering, confidence indicators, API endpoints, manual trigger admin UI
- Deliverable: Daily 3 AM scraper populates `UsedPriceAverages`, API returns used prices

**Stream C: Spec Links (FEAT-04)** - 1 developer, 1 week
- CSV import workflow (script + manual review)
- Spec link validation job (weekly)
- Admin monitoring dashboard for broken links
- Deliverable: GPU table has `OfficialSpecUrl` for all models, validation job runs weekly

**Stream D: Manufacturer Toggle (FEAT-05)** - 1 developer, 3 days
- React toggle component with localStorage persistence
- Context API provider for manufacturer state
- API query parameter support (already in foundation, just wire up toggle)
- Deliverable: Toggle component works with mock data, ready to integrate with visualization

**End of Phase 1**:
- Retail prices are being scraped daily ✅
- Used prices are being scraped daily ✅
- Spec links are populated and validated weekly ✅
- Manufacturer toggle component exists ✅
- **No user-facing dashboard yet** (data is being collected but not visualized)

---

### Phase 2: Dependent Features (1-2 weeks)

**Features**:
- **FEAT-03**: Value Visualization Dashboard (depends on FEAT-01, FEAT-02, FEAT-05)

**Work Stream**: Visualization (FEAT-03) - 2 developers, 2 weeks
- Week 1:
  - Backend: Visualization API endpoint (`GET /api/v1/visualization/data?manufacturer=radeon`) aggregates retail + used prices + performance scores
  - Backend: Value zone calculation logic (Tier Jumping algorithm)
  - Backend: Redis caching of visualization responses
  - Frontend: Recharts scatter plot component
- Week 2:
  - Frontend: GPU card components with price display, tooltips, badges (NEW/USED)
  - Frontend: Value zone highlighting (yellow glow on used GPUs meeting criteria)
  - Frontend: Integration with FEAT-05 toggle (filter data by manufacturer)
  - Frontend: Low-listing warnings, confidence indicators
  - Testing: E2E tests for visualization interactions

**Deliverable**: 
- User visits dashboard, sees Radeon GPUs by default
- Chart displays retail prices (blue circles, "NEW" badge) and used prices (green circles, "USED" badge)
- Value zones are highlighted (yellow glow)
- Hovering/tapping shows tooltip with price, listing count, OEM link
- Toggle to Nvidia updates chart instantly
- "Show older GPUs" checkbox adds RX 6000 / RTX 30 series
- **Full MVP is functional** ✅

---

## Dependency Graph

```
Foundation (Phase 0) - 2 weeks
    │
    ├─► FEAT-01: Retail Scraping (Phase 1) ────┐
    │                                           │
    ├─► FEAT-02: Used Scraping (Phase 1) ──────┤
    │                                           ├─► FEAT-03: Visualization (Phase 2) - 2 weeks
    ├─► FEAT-04: Spec Links (Phase 1) ─────────┤
    │                                           │
    └─► FEAT-05: Toggle Component (Phase 1) ───┘
```

**Build Order Rules**:
1. Foundation must complete before any features (2 weeks)
2. Phase 1 features can build in parallel (FEAT-01, 02, 04, 05 have no interdependencies)
3. Phase 2 (FEAT-03) waits for Phase 1 completion (needs price data + toggle component)
4. Total critical path: 2 weeks (foundation) + 2 weeks (Phase 1) + 2 weeks (Phase 2) = **6 weeks minimum**
5. With parallel development (4 devs), can achieve 6-week timeline; with 2 devs, likely 8 weeks

---

## Foundation Scope Definition

### What IS in Foundation

✅ **Entities used by 2+ features**
- `GPU` (used by all 5 features)
- `RetailListing`, `RetailPriceAverage` (used by FEAT-01, FEAT-03, FEAT-05)
- `UsedListing`, `UsedPriceAverage` (used by FEAT-02, FEAT-03, FEAT-05)
- `ScraperLog` (used by FEAT-01, FEAT-02)

✅ **Authentication/Authorization** (admin-only for MVP)
- JWT-based admin login
- HttpOnly cookie storage
- `AdminOnly` authorization policy

✅ **API patterns that all features follow**
- RESTful structure (`/api/v1/...`)
- RFC 7807 error handling
- OpenAPI documentation
- CORS configuration

✅ **Frontend shell that all pages use**
- React app with routing
- TanStack Query for API calls
- Tailwind CSS styling
- Error boundaries
- Loading skeletons

✅ **Services needed by multiple features**
- Redis caching (FEAT-01, 02, 03, 05)
- Hangfire background jobs (FEAT-01, 02, 04)
- HTTP Client with retry policies (FEAT-01, 02, 04)
- Structured logging (all features)

✅ **GPU catalog seeding**
- 33 initial GPU models with performance scores
- Reference model names, manufacturers, generations
- Foundation for all scraping and visualization

### What is NOT in Foundation

❌ **Feature-specific scraping logic**
- Retailer-specific HTML parsing (FEAT-01)
- eBay API integration (FEAT-02)
- CEX scraping (FEAT-02)
- Build these in Phase 1, not foundation

❌ **Feature-specific business logic**
- Outlier filtering algorithms (FEAT-01, FEAT-02)
- Value zone calculation (FEAT-03)
- Model identification normalization (FEAT-02)
- Build in feature phases

❌ **Visualization components**
- Recharts scatter plot (FEAT-03)
- GPU card components (FEAT-03)
- Tooltip components (FEAT-03)
- Build in Phase 2

❌ **Admin UI pages**
- Manual scraper trigger pages (FEAT-01, FEAT-02)
- Spec link monitoring dashboard (FEAT-04)
- Build with their respective features in Phase 1

---

## Technical Decisions

### Database Design

**Approach**: Code-first migrations with Entity Framework Core

**Shared Tables**:
- `gpus` (core GPU catalog)
- `retail_listings` (individual retailer prices)
- `retail_price_averages` (aggregated retail prices per GPU, historical)
- `used_listings` (individual marketplace listings)
- `used_price_averages` (aggregated used prices per GPU, historical)
- `scraper_logs` (job execution tracking)

**Indexes** (critical for query performance):
- `gpus.manufacturer` (for FEAT-05 filtering)
- `gpus.model_id` (unique, for scraper matching)
- `gpus.is_current_gen` (for "Show older GPUs" toggle)
- `retail_listings.gpu_model_id, scraped_at DESC` (for recent listings query)
- `used_listings.gpu_model_id, scraped_at DESC` (for recent listings query)
- `retail_price_averages.gpu_model_id, status` (for active prices query)
- `used_price_averages.gpu_model_id, calculated_at DESC` (for latest average)

**Constraints**:
- `gpus.manufacturer` CHECK constraint: `CHECK (manufacturer IN ('radeon', 'nvidia'))`
- `retail_listings.retailer` CHECK constraint (Scan/Ebuyer/Amazon)
- `used_listings.source` CHECK constraint (eBay/CEX)

### API Patterns

**Convention**: RESTful with `/api/v1/` prefix, manufacturer filter via query param

**Error Handling**: All errors return RFC 7807 ProblemDetails:
```json
{
  "type": "https://tools.ietf.org/html/rfc7231#section-6.5.1",
  "title": "Invalid manufacturer",
  "status": 400,
  "detail": "Manufacturer must be 'radeon' or 'nvidia'.",
  "traceId": "00-abc123..."
}
```

**Authorization**: 
- Public endpoints: No auth required (GET data)
- Admin endpoints: `[Authorize(Policy = "AdminOnly")]` (POST manual triggers, validation dashboards)

**Caching**:
- `ETag` headers for conditional requests
- `Cache-Control: public, max-age=300` (5 minutes)
- Redis cache behind API responses (5-15 minute TTL)

### Frontend Architecture

**Routing**: React Router v6
- `/` → Dashboard (FEAT-03)
- `/admin/retail-scraper` → Retail scraper management (FEAT-01)
- `/admin/used-scraper` → Used scraper management (FEAT-02)
- `/admin/spec-links` → Spec link validation dashboard (FEAT-04)

**State Management**:
- Server state: TanStack Query (GPU data, prices, visualization)
- UI state: React Context (manufacturer selection from FEAT-05)
- Persistent state: localStorage (`preferredManufacturer`)
- No Redux (per tech stack standards)

**Styling**: Tailwind CSS utility classes only
- Custom components use Tailwind classes
- No CSS modules or styled-components
- Design system tokens configured in `tailwind.config.js`

### Background Jobs (Hangfire)

**Retail Scraper** (FEAT-01):
- Recurring job: `0 2 * * *` (2 AM UTC daily)
- Job ID: `retail-price-scraper`
- Timeout: 30 minutes
- Retry: Manual only (no auto-retry, see feature spec)

**Used Scraper** (FEAT-02):
- Recurring job: `0 3 * * *` (3 AM UTC daily)
- Job ID: `used-price-scraper`
- Timeout: 30 minutes
- Retry: Manual only

**Spec Link Validator** (FEAT-04):
- Recurring job: `0 2 * * 0` (2 AM UTC Sunday weekly)
- Job ID: `spec-link-validator`
- Timeout: 10 minutes
- Retry: Auto-retry on next run

**Dashboard**: 
- Accessible at `/hangfire` (admin auth required)
- Shows job history, schedules, execution times

---

## Risks & Considerations

### Potential Issues

**1. Foundation Scope Creep**
- Risk: Adding "nice to have" features to foundation (e.g., user accounts, email service)
- Mitigation: Strict rule - only shared elements needed by 2+ features. Admin auth is minimal (hard-coded credentials for MVP). No user accounts unless explicitly in feature specs.

**2. GPU Catalog Completeness**
- Risk: Missing models in seed data causes scraper to discard valid listings
- Mitigation: Seed data includes all current-gen + previous-gen models (33 total). FEAT-01 and FEAT-02 scrapers log unmatched listings for review. Can add missing models via migration in Phase 1.

**3. Parallel Development Coordination**
- Risk: FEAT-01 and FEAT-02 both write to `GPU` table; potential for conflicts
- Mitigation: Seed GPU catalog in foundation phase before Phase 1 starts. Both features only INSERT into their respective listing tables, UPDATE `GPU` table's price average fields (non-conflicting). Database transactions ensure consistency.

**4. Foundation Timeline**
- Risk: 2 weeks for foundation feels long before seeing features
- Mitigation: Foundation is intentionally focused—only essential shared infrastructure. No gold-plating. Can demo foundation deliverable (API returning seeded GPU data, empty dashboard shell) after 2 weeks to show progress.

**5. eBay API Access Delay**
- Risk: FEAT-02 depends on eBay Developer account approval, which can take days
- Mitigation: Start eBay Developer application during foundation phase (Week 1). If delayed, FEAT-02 developer can build CEX scraper first (no API approval needed), then add eBay integration once approved.

### Open Questions

**Q: Should we build admin authentication in foundation or defer to Phase 1?**
- Recommendation: **Build in foundation**. FEAT-01, FEAT-02, and FEAT-04 all need admin endpoints for manual triggers and monitoring. Simple JWT auth (hard-coded admin credentials) is 1 day of work and unblocks 3 features. Don't defer and risk blocking Phase 1 features.

**Q: How much GPU catalog data should we seed?**
- Recommendation: **Seed current-gen + previous-gen (33 models)**. This covers FEAT-01 and FEAT-02 whitelist requirements and FEAT-03 visualization needs. Can add older GPUs (RTX 20 series, RX 5000 series) later if users request. Start with 33 to prove foundation, expand if needed.

**Q: Should visualization API be built in foundation or Phase 2?**
- Recommendation: **Phase 2 (with FEAT-03)**. Visualization API endpoint aggregates data from FEAT-01 and FEAT-02, which don't exist until Phase 1 completes. No value in building API before data sources are ready. Foundation includes generic `/api/v1/gpus` endpoint (simple list), visualization-specific endpoint (`/api/v1/visualization/data`) is built in Phase 2.

---

## Recommended Next Steps

1. **Review this analysis** (Estimated: 1 day)
   - Product Owner validates feature sequencing
   - Tech Lead validates technical feasibility of foundation scope
   - Team agrees on 2-week foundation timeline

2. **Create Foundation Engineering Spec** (Estimated: 2 days, can overlap with foundation build)
   - Detailed database schema with all fields
   - API endpoint contracts (request/response schemas)
   - Frontend component hierarchy
   - Hangfire job configurations
   - Seed data scripts

3. **Build Foundation** (Estimated: 2 weeks, 2-4 developers)
   - Week 1: Database, backend infrastructure, caching, background jobs
   - Week 2: Frontend infrastructure, admin auth, smoke tests
   - Deliverable: Running app with seeded GPU data, empty dashboard, admin backoffice shell

4. **Create Phase 1 Feature Engineering Specs** (Estimated: 1 week, can start during foundation Week 2)
   - FEAT-01: Retail scraper implementation plan
   - FEAT-02: Used scraper implementation plan
   - FEAT-04: Spec link CSV import and validation plan
   - FEAT-05: Toggle component implementation plan

5. **Build Phase 1 Features** (Estimated: 3-4 weeks, parallel development with 4 developers)
   - Stream A: FEAT-01 (2 weeks)
   - Stream B: FEAT-02 (2 weeks)
   - Stream C: FEAT-04 (1 week)
   - Stream D: FEAT-05 (3 days)
   - Deliverable: All scrapers running daily, spec links populated, toggle component exists

6. **Create Phase 2 Feature Engineering Spec** (Estimated: 3 days, during Phase 1 Week 2)
   - FEAT-03: Visualization API and frontend implementation plan

7. **Build Phase 2 Feature** (Estimated: 2 weeks, 2 developers)
   - FEAT-03: Value Visualization Dashboard
   - Deliverable: Full MVP functional

8. **Testing & Launch Prep** (Estimated: 1 week, overlaps with Phase 2 Week 2)
   - E2E tests (Playwright)
   - Performance testing (API response times, scraper execution times)
   - Security review (admin auth, XSS prevention, SQL injection checks)
   - Deployment scripts (Docker Compose for local, Kubernetes manifests for production)

**Total Timeline**: 2 weeks foundation + 4 weeks Phase 1 + 2 weeks Phase 2 + 1 week testing = **9 weeks to production-ready MVP**

With aggressive parallel development (4 developers), can compress to **7 weeks**.

---

## Appendix: Feature Requirements Matrix

| Feature | GPU Entity | Retail Entities | Used Entities | Scraper Logs | Admin Auth | Background Jobs | HTTP Client | Redis Cache | Frontend Shell | Manufacturer Filter | Phase |
|---------|------------|-----------------|---------------|--------------|------------|-----------------|-------------|-------------|----------------|---------------------|-------|
| FEAT-01 (Retail) | ✅ | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | 1 |
| FEAT-02 (Used) | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | 1 |
| FEAT-03 (Viz) | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ | 2 |
| FEAT-04 (Links) | ✅ | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | 1 |
| FEAT-05 (Toggle) | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ | 1* |

**Legend**:
- ✅ = Required by feature
- ❌ = Not used by feature
- * = FEAT-05 component built in Phase 1, integrated in Phase 2 with FEAT-03

**Key Insights**:
- `GPU` entity is foundational—used by all 5 features
- Admin auth needed by 3 features (FEAT-01, 02, 04) → must be in foundation
- Redis caching needed by 4 features (FEAT-01, 02, 03, 05) → must be in foundation
- Background jobs needed by 3 features (FEAT-01, 02, 04) → must be in foundation
- Frontend shell only needed by 2 features (FEAT-03, FEAT-05) but is shared infrastructure → build in foundation to avoid duplication

---

**Status**: ✅ **Ready for Engineering Specification**

This analysis provides complete foundation scope, clear feature dependencies, and a sequenced build plan. Engineering can now create detailed implementation specs for:
1. Foundation (database schema, API structure, frontend shell)
2. Phase 1 features (scraping logic, spec links, toggle component)
3. Phase 2 feature (visualization dashboard)