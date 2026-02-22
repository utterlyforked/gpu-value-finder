# GPU Value Tracker — Implementation Guide

## What you are building

GPU Value Tracker is a web application that aggregates live GPU pricing from UK retailers (Scan, Ebuyer, Amazon) and used marketplaces (eBay, CEX) to help PC builders identify real value across GPU generations. The system scrapes prices daily, calculates averages with outlier filtering, and presents performance-to-price relationships in a visual dashboard that highlights when used cards offer better value than new retail options.

## Tech stack

**Backend**: ASP.NET Core 8.0 (LTS), C# 12  
**Database**: PostgreSQL 16+  
**ORM**: Entity Framework Core 8  
**Frontend**: React 18+ with TypeScript, Vite  
**State Management**: TanStack Query + Context API  
**Styling**: Tailwind CSS  
**Testing**: xUnit + FluentAssertions + NSubstitute (backend), Vitest + React Testing Library (frontend), Playwright (E2E)  
**Caching**: Redis  
**Background Jobs**: Hangfire  
**Monitoring**: Application Insights  

## Non-negotiable conventions

- Nullable reference types enabled project-wide
- Use `record` for DTOs and value objects
- Async/await everywhere (no `.Result` or `.Wait()`)
- Code-first migrations only
- Strict TypeScript mode enabled
- No `any` types
- Functional React components only
- Props interfaces required for all components
- RESTful API with `/api/v1/` prefix
- RFC 7807 ProblemDetails for errors
- JWT authentication via HttpOnly cookies
- OpenAPI/Swagger documentation required
- No stored procedures (business logic in code)
- No microservices (monolith until proven otherwise)
- No Redux (TanStack Query is sufficient)
- No localStorage for tokens (security risk)

---

## Implementation order

Follow this sequence. Do not start a phase until all tests in the previous phase pass.

### Phase 0: Foundation
**Spec**: `specs/foundation-spec.md`

Build everything in this spec before writing any feature code. This phase produces:
- PostgreSQL database with 6 tables: `GPU`, `RetailListing`, `RetailPriceAverage`, `UsedListing`, `UsedPriceAverage`, `ScraperLog`
- Seed data: 33 GPU models (RX 7000, RTX 40, RX 6000, RTX 30 series) with performance scores
- Admin JWT authentication system with HttpOnly cookies
- Public API endpoints: `GET /api/v1/gpus`, `GET /api/v1/gpus/{id}`
- Admin API endpoints: `POST /api/v1/auth/admin/login`, `POST /api/v1/auth/admin/logout`, `GET /api/v1/admin/health`
- Redis caching service with connection pooling
- Hangfire background job infrastructure with PostgreSQL storage
- HTTP client factory with retry policies and circuit breaker
- React 18 application shell with routing, TanStack Query, Tailwind CSS
- Manufacturer context provider for global state (Radeon/Nvidia toggle)
- Error boundaries, loading skeletons, localStorage utilities

**Done when**: All acceptance criteria in `specs/foundation-spec.md` pass. `dotnet test` green.

---

### Phase 1: Retail Scraping, Used Scraping, Spec Links, Manufacturer Toggle — parallel

These features have no inter-dependencies and can be built in parallel.

**Live Retail Price Aggregation**  
**Spec**: `specs/FEAT-01-live-retail-price-aggregation-spec.md`  
Owns: `RetailListing`, `RetailPriceAverage`, `ScraperLog` (writes retail job records)  
Reads: `GPU` (foundation entity for model catalog)  
- Daily scraper job (2 AM UTC) for Scan, Ebuyer, Amazon UK
- Outlier filtering (>1.5x median price excluded from averages)
- Public API: `GET /api/v1/retail-prices?manufacturer=radeon|nvidia`
- Admin API: `POST /api/v1/admin/scraper/trigger`, `GET /api/v1/admin/scraper/status/{jobId}`

**Used Market Price Discovery**  
**Spec**: `specs/FEAT-02-used-market-price-discovery-spec.md`  
Owns: `UsedListing`, `UsedPriceAverage`, `ScraperLog` (writes used job records)  
Reads: `GPU` (foundation entity), `RetailPriceAverage` (to filter used cards with retail data)  
- Daily scraper job (3 AM UTC) for eBay API and CEX web scraping
- Outlier filtering (>2x median price excluded from averages)
- Confidence levels: Low (1-2 listings), Medium (3-5), High (6+)
- Public API: `GET /api/v1/used-prices/{cardModel}`, `GET /api/v1/used-prices?manufacturer=AMD|Nvidia`
- Admin API: `POST /api/admin/used-market/scrape`, `GET /api/admin/used-market/status`

**Manufacturer Reference Links**  
**Spec**: `specs/FEAT-04-manufacturer-reference-links-spec.md`  
Owns: `GPU.official_spec_url`, `GPU.spec_url_status`, `GPU.spec_url_last_checked` (extends foundation entity)  
Reads: `GPU` (foundation entity)  
- CSV import workflow for populating OEM product URLs
- Weekly validation job (Sunday 2 AM UTC) to check link health
- Admin API: `POST /api/v1/admin/gpus/import-spec-urls`, `GET /api/v1/admin/gpus/spec-url-status`, `PATCH /api/v1/admin/gpus/{id}/spec-url-status`

**Radeon vs Nvidia Mode Switching**  
**Spec**: `specs/FEAT-05-radeon-vs-nvidia-mode-switching-spec.md`  
Owns: `GPU.manufacturer` field (extends foundation entity), React toggle component  
Reads: `GPU` (foundation entity)  
- Manufacturer filter query parameter on all API endpoints
- localStorage persistence of user's manufacturer preference
- React Context provider for global manufacturer state
- Toggle component integrated with all data-fetching queries

**Done when**: All acceptance criteria in all Phase 1 specs pass.

---

### Phase 2: Value Visualization Dashboard

**Spec**: `specs/FEAT-03-value-visualization-dashboard-spec.md`  
Depends on: FEAT-01 (retail prices), FEAT-02 (used prices), FEAT-05 (manufacturer toggle)  
Owns: `GpuPerformanceTier`, `GpuPriceSnapshot`  
Reads: `GPU`, `RetailPriceAverage`, `UsedPriceAverage`  
- Visualization API: `GET /api/v1/visualization/data?manufacturer=radeon|nvidia&includeOlderGen=true|false`
- Value zone calculation (Tier Jumping algorithm: used GPU offers ≥10% better performance than retail GPU at same/lower price)
- Redis caching with 5-minute TTL
- Recharts scatter plot with performance score (Y-axis) vs price (X-axis)
- Visual indicators: blue circles (retail, "NEW" badge), green circles (used, "USED" badge), yellow glow (value zone)
- Low-listing warnings (<3 listings = 70% opacity + asterisk)

**Done when**: All acceptance criteria in `specs/FEAT-03-value-visualization-dashboard-spec.md` pass.

---

## Implementation rules

These rules apply across all phases. Violations will cause integration failures.

### Entity names
Use the exact entity and table names from `specs/foundation-spec.md`. Never rename:
- GPU
- RetailListing
- RetailPriceAverage
- UsedListing
- UsedPriceAverage
- ScraperLog
- GpuPerformanceTier (FEAT-03)
- GpuPriceSnapshot (FEAT-03)

### Status enums
- `RetailPriceAverage.status`: `Active` | `Inactive` | `Archived`
- `GPU.spec_url_status`: `Active` | `Unavailable` | `NeedsReview`
- `ScraperLog.status`: `Success` | `PartialFailure` | `Failure`
- `UsedPriceAverage.confidence`: `Low` | `Medium` | `High`
- `RetailListing.retailer`: `Scan` | `Ebuyer` | `Amazon`
- `UsedListing.source`: `eBay` | `CEX`
- `ScraperLog.job_type`: `Retail` | `Used`
- `GPU.manufacturer`: `radeon` | `nvidia` (lowercase only)

### Field names
Database columns use snake_case. C# properties use PascalCase. TypeScript properties use camelCase.
The mapping is automatic via EF Core conventions — do not override it.

**Example**:
- Database: `gpu.official_spec_url`
- C# entity: `Gpu.OfficialSpecUrl`
- TypeScript interface: `gpu.officialSpecUrl`

### Primary keys
All entities use UUID primary keys. Never use integer auto-increment IDs.
Exception: `GpuPriceSnapshot.id` uses integer auto-increment for performance (high write volume).

### What not to build
Do not implement anything not described in the specs:
- No additional endpoints
- No additional fields
- No alternative status values
- No features from the "Not in this document" sections
- No user accounts (only admin authentication)
- No email notifications
- No historical price trend graphs (data is stored for future use, but no UI in v1)
- No cross-manufacturer comparison (Radeon and Nvidia data never mixed)
- No Intel Arc GPU support
- No 8GB-only cards (16GB+ VRAM only)

---

## How to verify a feature is complete

Each spec has an `## Acceptance Criteria` section with a checkbox list.
A feature is complete when every checkbox can be verified by a test.

Run tests:
```bash
dotnet test                    # backend unit + integration tests
npm run test                   # frontend unit tests
npx playwright test            # E2E tests (run last)
```

All tests must pass before moving to the next phase.

---

## Spec index

| Spec | Phase | Owns |
|------|-------|------|
| `specs/foundation-spec.md` | 0 | GPU, RetailListing, RetailPriceAverage, UsedListing, UsedPriceAverage, ScraperLog |
| `specs/FEAT-01-live-retail-price-aggregation-spec.md` | 1 | RetailListing, RetailPriceAverage (feature logic) |
| `specs/FEAT-02-used-market-price-discovery-spec.md` | 1 | UsedListing, UsedPriceAverage (feature logic) |
| `specs/FEAT-04-manufacturer-reference-links-spec.md` | 1 | GPU.official_spec_url, GPU.spec_url_status, GPU.spec_url_last_checked (extensions) |
| `specs/FEAT-05-radeon-vs-nvidia-mode-switching-spec.md` | 1 | GPU.manufacturer (extension), ManufacturerContext (React) |
| `specs/FEAT-03-value-visualization-dashboard-spec.md` | 2 | GpuPerformanceTier, GpuPriceSnapshot |

---

## Security requirements

- Admin passwords must be hashed using bcrypt with minimum cost factor 12
- JWT tokens must be signed with HS256 using 256-bit secret key from environment variable
- JWT tokens expire after 24 hours
- Auth token cookie must have `HttpOnly=true`, `Secure=true` (production), `SameSite=Strict`
- Admin login endpoint rate-limited to 10 attempts per IP per hour
- All API inputs validated before processing (parameterized queries via EF Core only, no raw SQL)
- CORS configured to allow frontend origin only (no wildcard `*`)
- HTTPS enforced in production with HSTS header (`Strict-Transport-Security: max-age=31536000; includeSubDomains`)
- Database connection string, Redis URL, JWT secret stored in environment variables (never hardcoded)
- Retailer scraping must respect robots.txt and use transparent User-Agent identifying bot traffic

---

**CLAUDE.md complete. Begin with Phase 0 foundation build. Do not proceed to Phase 1 until all foundation acceptance criteria pass.**