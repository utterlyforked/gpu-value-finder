# Foundation Infrastructure — Engineering Spec

**Type**: foundation
**Component**: foundation-infrastructure
**Dependencies**: None (this is the base layer)
**Status**: Ready for Implementation

---

## Instructions for Implementation

This document is a technical contract. Your job is to implement everything described here:
- Create all database tables and migrations defined in the Data Model section
- Implement all API endpoints defined in the API Endpoints section
- Enforce all business rules, validation rules, and authorization policies exactly as specified
- Write tests that verify each acceptance criterion

Do not add features, fields, or behaviours not listed in this document.
Do not omit anything listed in this document.

---

## Overview

This foundation provides the shared infrastructure required by all features in the GPU Value Tracker application. It includes the core GPU catalog entity, authentication infrastructure for admin users, API patterns, frontend application shell, caching layer, background job infrastructure, and HTTP client services. All five features (retail price aggregation, used market discovery, value visualization, manufacturer reference links, and manufacturer toggle) depend on components defined in this specification.

This foundation owns the `GPU`, `RetailListing`, `RetailPriceAverage`, `UsedListing`, `UsedPriceAverage`, and `ScraperLog` entities. It does not implement feature-specific business logic (scraping algorithms, visualization calculations) — those belong to individual feature specifications.

---

## Data Model

### GPU

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| id | UUID | PK, not null | Generated on insert |
| model_id | string(100) | unique, not null | Normalized identifier, e.g., "rx-7900-xtx" |
| reference_name | string(200) | not null | Display name, e.g., "AMD Radeon RX 7900 XTX" |
| manufacturer | string(20) | not null, CHECK constraint | Lowercase: "radeon" or "nvidia" |
| generation | string(50) | not null | e.g., "RX 7000", "RTX 40" |
| vram_gb | int | not null | VRAM capacity in GB, e.g., 16, 24 |
| performance_score | int | not null, CHECK (1-100) | Ordinal ranking for visualization (1=lowest, 100=highest) |
| is_current_gen | bool | not null, default false | True for latest generation GPUs |
| official_spec_url | string(500) | nullable | Manufacturer product page URL |
| spec_url_status | string(20) | not null, default 'Active' | Enum: "Active", "Unavailable", "NeedsReview" |
| spec_url_last_checked | timestamp | nullable | UTC timestamp of last validation check |
| created_at | timestamp | not null, default now() | UTC timestamp |
| updated_at | timestamp | not null, default now() | UTC timestamp, updated on modification |

**Indexes**:
- `model_id` (unique)
- `manufacturer`
- `is_current_gen`
- `(manufacturer, is_current_gen)` composite

**Relationships**:
- Has many `RetailListing` (no cascade, orphaned listings remain for audit)
- Has many `RetailPriceAverage` (no cascade)
- Has many `UsedListing` (no cascade)
- Has many `UsedPriceAverage` (no cascade)

**Constraints**:
- CHECK: `manufacturer IN ('radeon', 'nvidia')`
- CHECK: `performance_score >= 1 AND performance_score <= 100`
- CHECK: `spec_url_status IN ('Active', 'Unavailable', 'NeedsReview')`

---

### RetailListing

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| id | UUID | PK, not null | Generated on insert |
| gpu_model_id | UUID | FK → GPU(id), not null | |
| retailer | string(50) | not null, CHECK constraint | Enum: "Scan", "Ebuyer", "Amazon" |
| price | decimal(10,2) | not null, CHECK > 0 | GBP amount |
| is_in_stock | bool | not null | Stock availability at scrape time |
| product_url | string(1000) | nullable | Direct link to retailer product page |
| scraped_at | timestamp | not null | UTC timestamp when scraped |
| is_outlier | bool | not null, default false | Flagged during aggregation calculation |

**Indexes**:
- `gpu_model_id`
- `(gpu_model_id, scraped_at DESC)` composite
- `retailer`

**Relationships**:
- Belongs to `GPU` via `gpu_model_id`

**Constraints**:
- CHECK: `retailer IN ('Scan', 'Ebuyer', 'Amazon')`
- CHECK: `price > 0`

---

### RetailPriceAverage

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| id | UUID | PK, not null | Generated on insert |
| gpu_model_id | UUID | FK → GPU(id), not null | |
| min_price | decimal(10,2) | not null, CHECK > 0 | Minimum price across retailers |
| avg_price | decimal(10,2) | not null, CHECK > 0 | Average price (outliers excluded) |
| max_price | decimal(10,2) | not null, CHECK > 0 | Maximum price across retailers |
| listing_count | int | not null, CHECK >= 0 | Total listings found (before outlier filtering) |
| in_stock_count | int | not null, CHECK >= 0 | Count of in-stock listings |
| is_in_stock | bool | not null | True if any retailer has stock |
| last_scraped_at | timestamp | not null | UTC timestamp of most recent scrape |
| status | string(20) | not null, default 'Active' | Enum: "Active", "Inactive", "Archived" |

**Indexes**:
- `gpu_model_id`
- `(gpu_model_id, status)` composite
- `status`

**Relationships**:
- Belongs to `GPU` via `gpu_model_id`

**Constraints**:
- CHECK: `min_price <= avg_price AND avg_price <= max_price`
- CHECK: `listing_count >= 0 AND in_stock_count >= 0`
- CHECK: `in_stock_count <= listing_count`
- CHECK: `status IN ('Active', 'Inactive', 'Archived')`

---

### UsedListing

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| id | UUID | PK, not null | Generated on insert |
| gpu_model_id | UUID | FK → GPU(id), not null | |
| source | string(50) | not null, CHECK constraint | Enum: "eBay", "CEX" |
| price | decimal(10,2) | not null, CHECK > 0 | GBP amount |
| listing_url | string(1000) | nullable | Direct link to marketplace listing |
| scraped_at | timestamp | not null | UTC timestamp when scraped |
| is_outlier | bool | not null, default false | Flagged during aggregation calculation |

**Indexes**:
- `gpu_model_id`
- `(gpu_model_id, scraped_at DESC)` composite
- `source`

**Relationships**:
- Belongs to `GPU` via `gpu_model_id`

**Constraints**:
- CHECK: `source IN ('eBay', 'CEX')`
- CHECK: `price > 0`

---

### UsedPriceAverage

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| id | UUID | PK, not null | Generated on insert |
| gpu_model_id | UUID | FK → GPU(id), not null | |
| average_price | decimal(10,2) | not null, CHECK > 0 | Average price across sources (outliers excluded) |
| listing_count | int | not null, CHECK >= 0 | Total listings found (before outlier filtering) |
| source_breakdown | JSONB | not null | Format: `{"eBay": 5, "CEX": 3}` |
| confidence | string(20) | not null | Enum: "Low", "Medium", "High" |
| calculated_at | timestamp | not null | UTC timestamp of aggregation |

**Indexes**:
- `gpu_model_id`
- `(gpu_model_id, calculated_at DESC)` composite

**Relationships**:
- Belongs to `GPU` via `gpu_model_id`

**Constraints**:
- CHECK: `average_price > 0`
- CHECK: `listing_count >= 0`
- CHECK: `confidence IN ('Low', 'Medium', 'High')`

---

### ScraperLog

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| id | UUID | PK, not null | Generated on insert |
| job_type | string(50) | not null, CHECK constraint | Enum: "Retail", "Used" |
| started_at | timestamp | not null | UTC timestamp when job started |
| completed_at | timestamp | nullable | UTC timestamp when job finished (null if still running) |
| status | string(50) | not null | Enum: "Success", "PartialFailure", "Failure" |
| retailer_statuses | JSONB | not null | Format: `{"Scan": "success", "Ebuyer": "failure", "Amazon": "success"}` |
| records_updated | int | not null, default 0 | Count of listings inserted/updated |
| error_messages | text | nullable | Newline-separated error messages |

**Indexes**:
- `(started_at DESC)`
- `job_type`

**Constraints**:
- CHECK: `job_type IN ('Retail', 'Used')`
- CHECK: `status IN ('Success', 'PartialFailure', 'Failure')`

---

## API Endpoints

### GET /api/v1/gpus

**Auth**: None (public endpoint)
**Authorization**: None

**Query Parameters**:
| Parameter | Type | Required | Validation |
|-----------|------|----------|-----------|
| manufacturer | string | no | Must be "radeon" or "nvidia" if provided |
| currentGenOnly | bool | no | Defaults to true |

**Success response** `200 OK`:
```json
[
  {
    "id": "uuid",
    "modelId": "rx-7900-xtx",
    "referenceName": "AMD Radeon RX 7900 XTX",
    "manufacturer": "radeon",
    "generation": "RX 7000",
    "vramGb": 24,
    "performanceScore": 95,
    "isCurrentGen": true,
    "officialSpecUrl": "https://www.amd.com/...",
    "specUrlStatus": "Active"
  }
]
```

**Error responses**:
| Status | Condition |
|--------|-----------|
| 400 | Invalid manufacturer value (not "radeon" or "nvidia") |

---

### GET /api/v1/gpus/{id}

**Auth**: None (public endpoint)
**Authorization**: None

**Success response** `200 OK`:
```json
{
  "id": "uuid",
  "modelId": "rx-7900-xtx",
  "referenceName": "AMD Radeon RX 7900 XTX",
  "manufacturer": "radeon",
  "generation": "RX 7000",
  "vramGb": 24,
  "performanceScore": 95,
  "isCurrentGen": true,
  "officialSpecUrl": "https://www.amd.com/...",
  "specUrlStatus": "Active",
  "createdAt": "2025-01-12T10:00:00Z",
  "updatedAt": "2025-01-12T10:00:00Z"
}
```

**Error responses**:
| Status | Condition |
|--------|-----------|
| 404 | GPU with specified ID not found |

---

### POST /api/v1/auth/admin/login

**Auth**: None
**Authorization**: None

**Request body**:
| Field | Type | Required | Validation |
|-------|------|----------|-----------|
| username | string | yes | Non-empty, max 100 chars |
| password | string | yes | Non-empty, max 200 chars |

**Success response** `200 OK`:
```json
{
  "token": "jwt-token-string",
  "expiresAt": "2025-01-13T10:00:00Z"
}
```

**Note**: JWT token is also set as HttpOnly cookie named `auth_token` with Secure and SameSite=Strict flags.

**Error responses**:
| Status | Condition |
|--------|-----------|
| 400 | Validation failure — username or password missing |
| 401 | Invalid credentials |
| 429 | Rate limit exceeded (10 attempts per IP per hour) |

---

### POST /api/v1/auth/admin/logout

**Auth**: Required (Bearer JWT or HttpOnly cookie)
**Authorization**: AdminOnly

**Success response** `204 No Content`

**Error responses**:
| Status | Condition |
|--------|-----------|
| 401 | Not authenticated |

---

### GET /api/v1/admin/health

**Auth**: Required
**Authorization**: AdminOnly

**Success response** `200 OK`:
```json
{
  "database": "healthy",
  "redis": "healthy",
  "hangfire": "healthy"
}
```

**Error responses**:
| Status | Condition |
|--------|-----------|
| 401 | Not authenticated |
| 403 | Not authorized (not admin) |

---

## Business Rules

1. All timestamps are stored and returned in UTC.
2. The `manufacturer` field must be lowercase ("radeon" or "nvidia") — normalization happens before storage.
3. The `model_id` field is used for scraper matching and must be unique across all GPUs.
4. A GPU's `performance_score` is an ordinal ranking (1-100) used for visualization positioning — higher score = better performance.
5. The `spec_url_status` field defaults to "Active" and is updated by the spec link validation job (FEAT-04).
6. Retail and used listings are never deleted — they are retained for historical audit purposes.
7. Price averages use outlier filtering (implemented in feature specs) — the `is_outlier` flag is set during aggregation.
8. Admin authentication uses JWT tokens stored in HttpOnly cookies for security — tokens expire after 24 hours.
9. The `is_current_gen` flag is manually maintained during GPU catalog updates — it is not automatically derived.
10. Redis cache keys use manufacturer-specific namespacing: `viz:radeon:current`, `viz:nvidia:current`.

---

## Validation Rules

| Field | Rule | Error message |
|-------|------|---------------|
| GPU.model_id | Required, max 100 chars, unique | "Model ID is required" / "Model ID too long" / "Model ID already exists" |
| GPU.reference_name | Required, max 200 chars | "Reference name is required" / "Reference name too long" |
| GPU.manufacturer | Required, must be "radeon" or "nvidia" (case-insensitive) | "Manufacturer is required" / "Manufacturer must be 'radeon' or 'nvidia'" |
| GPU.performance_score | Required, integer between 1-100 | "Performance score is required" / "Performance score must be between 1 and 100" |
| GPU.official_spec_url | Max 500 chars, valid URL format if provided | "Spec URL too long" / "Invalid URL format" |
| RetailListing.price | Required, decimal > 0, max 2 decimal places | "Price is required" / "Price must be greater than 0" / "Price cannot have more than 2 decimal places" |
| UsedListing.price | Required, decimal > 0, max 2 decimal places | "Price is required" / "Price must be greater than 0" / "Price cannot have more than 2 decimal places" |
| Auth.username | Required, max 100 chars | "Username is required" / "Username too long" |
| Auth.password | Required, max 200 chars | "Password is required" / "Password too long" |

---

## Authorization

| Action | Required policy | Notes |
|--------|----------------|-------|
| List GPUs | None (public) | |
| Get GPU details | None (public) | |
| Admin login | None (public) | Rate-limited to 10 attempts per IP per hour |
| Admin logout | AdminOnly | Requires valid JWT token |
| Admin health check | AdminOnly | Requires valid JWT token |

**AdminOnly Policy**:
- User must have valid JWT token (Bearer header or HttpOnly cookie)
- Token must contain `role: "Admin"` claim
- Token must not be expired (24-hour TTL)

---

## Acceptance Criteria

- [ ] Database migrations create all 6 tables with correct schema (GPU, RetailListing, RetailPriceAverage, UsedListing, UsedPriceAverage, ScraperLog)
- [ ] All indexes are created as specified
- [ ] All CHECK constraints are enforced (manufacturer enum, price > 0, performance_score 1-100)
- [ ] Foreign key relationships are created with correct cascade rules
- [ ] Seed data script populates 33 GPU models (RX 7000, RTX 40, RX 6000, RTX 30 series) with correct performance scores
- [ ] `GET /api/v1/gpus?manufacturer=radeon` returns only Radeon GPUs
- [ ] `GET /api/v1/gpus?currentGenOnly=true` excludes GPUs where `is_current_gen=false`
- [ ] `GET /api/v1/gpus/{id}` returns 404 for non-existent GPU ID
- [ ] `POST /api/v1/auth/admin/login` returns JWT token and sets HttpOnly cookie on valid credentials
- [ ] `POST /api/v1/auth/admin/login` returns 401 on invalid credentials
- [ ] `POST /api/v1/auth/admin/login` returns 429 after 10 failed attempts from same IP within 1 hour
- [ ] `POST /api/v1/auth/admin/logout` clears HttpOnly cookie and returns 204
- [ ] `GET /api/v1/admin/health` returns 403 when called without admin token
- [ ] `GET /api/v1/admin/health` returns 200 with service health status when called with valid admin token
- [ ] Redis connection is established and can set/get cache values
- [ ] Hangfire dashboard is accessible at `/hangfire` with admin authentication
- [ ] Global error handler returns RFC 7807 ProblemDetails for all errors
- [ ] CORS is configured to allow frontend origin (localhost:5173 for dev)
- [ ] Swagger/OpenAPI documentation is available at `/swagger`
- [ ] All API responses use camelCase field names (not snake_case)
- [ ] All timestamps in API responses are ISO 8601 format with UTC timezone

---

## Security Requirements

### Password Hashing
- Admin passwords must be hashed using bcrypt with minimum cost factor 12
- Plain-text passwords must never be logged or stored

### JWT Token Security
- Tokens must be signed with HS256 algorithm using 256-bit secret key
- Secret key must be stored in environment variable, not hardcoded
- Tokens must include `exp` (expiration) claim set to 24 hours from issue time
- Tokens must include `role` claim for authorization checks
- Tokens must be validated on every protected endpoint request

### Cookie Security
- Auth token cookie must have `HttpOnly=true` flag (prevents JavaScript access)
- Auth token cookie must have `Secure=true` flag in production (HTTPS only)
- Auth token cookie must have `SameSite=Strict` flag (CSRF protection)
- Cookie expiration must match JWT token expiration (24 hours)

### Rate Limiting
- Admin login endpoint must enforce 10 attempts per IP per hour
- Rate limit counter stored in Redis with 1-hour TTL
- Rate limit returns 429 status with `Retry-After` header

### Input Validation
- All API inputs must be validated before processing
- SQL injection prevented by using parameterized queries (EF Core query methods only, no raw SQL)
- XSS prevented by not rendering user input as HTML (API returns JSON only)
- Path traversal prevented by validating file paths in spec link validator (FEAT-04)

### CORS Configuration
- Allow origin: `http://localhost:5173` (dev), production domain (prod)
- Allow credentials: true (for HttpOnly cookies)
- Allow methods: GET, POST, PUT, DELETE, OPTIONS
- Allow headers: Content-Type, Authorization
- No wildcard origins allowed

### Secrets Management
- Database connection string stored in environment variable `DATABASE_URL`
- Redis connection string stored in environment variable `REDIS_URL`
- JWT signing key stored in environment variable `JWT_SECRET`
- Admin credentials stored in environment variable `ADMIN_USERNAME` and `ADMIN_PASSWORD_HASH`
- Never commit secrets to version control

### HTTPS Enforcement
- Production API must redirect HTTP to HTTPS
- HSTS header must be set: `Strict-Transport-Security: max-age=31536000; includeSubDomains`
- Development environment may use HTTP for localhost only

---

## Not In This Document

This document does not contain:
- **Implementation code** — write the code yourself based on the contracts above
- **Feature-specific scraping logic** — retail scraper (FEAT-01), used scraper (FEAT-02) defined in separate specs
- **Visualization business logic** — value zone calculation (FEAT-03) defined in separate spec
- **Spec link validation logic** — CSV import and URL validation (FEAT-04) defined in separate spec
- **Manufacturer toggle UI components** — React components (FEAT-05) defined in separate spec
- **Test case definitions** — see QA spec for test plans
- **Deployment configuration** — Docker Compose, Kubernetes manifests are separate artifacts
- **Performance tuning** — query optimization, connection pooling tuning happens during implementation
- **Monitoring dashboards** — Application Insights dashboard configuration is separate
- **User account system** — only admin authentication in MVP, no public user registration

---

## Frontend Infrastructure Specification

### React Application Shell

**Project Structure**:
```
src/
├── main.tsx                 # Entry point
├── App.tsx                  # Root component with routing
├── components/
│   ├── layout/
│   │   ├── Header.tsx       # Site header with logo/title
│   │   └── Layout.tsx       # Wrapper component
│   ├── common/
│   │   ├── ErrorBoundary.tsx
│   │   ├── LoadingSkeleton.tsx
│   │   └── ErrorMessage.tsx
├── pages/
│   ├── Dashboard.tsx        # Main visualization page (placeholder)
│   └── admin/
│       └── AdminLogin.tsx   # Admin login page
├── api/
│   ├── client.ts            # Axios instance with interceptors
│   ├── gpuApi.ts            # GPU endpoints
│   └── authApi.ts           # Auth endpoints
├── hooks/
│   └── useManufacturer.tsx  # Context hook for manufacturer state
├── context/
│   └── ManufacturerContext.tsx  # Global manufacturer selection state
├── utils/
│   └── storage.ts           # localStorage wrapper functions
└── types/
    └── api.ts               # TypeScript interfaces for API responses
```

**Routing Setup** (React Router v6):
```typescript
// App.tsx routes
<Routes>
  <Route path="/" element={<Dashboard />} />
  <Route path="/admin/login" element={<AdminLogin />} />
  {/* Feature routes added in Phase 1 */}
</Routes>
```

**API Client Configuration** (TanStack Query):
```typescript
// src/api/client.ts
import axios from 'axios';

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:5000',
  withCredentials: true, // Send HttpOnly cookies
  headers: {
    'Content-Type': 'application/json',
  },
});

// Interceptor for error handling
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Redirect to login
      window.location.href = '/admin/login';
    }
    return Promise.reject(error);
  }
);
```

**Global State** (Manufacturer Context):
```typescript
// src/context/ManufacturerContext.tsx
import React, { createContext, useState, useEffect, ReactNode } from 'react';

type Manufacturer = 'radeon' | 'nvidia';

interface ManufacturerContextType {
  manufacturer: Manufacturer;
  setManufacturer: (m: Manufacturer) => void;
}

export const ManufacturerContext = createContext<ManufacturerContextType | undefined>(undefined);

export const ManufacturerProvider = ({ children }: { children: ReactNode }) => {
  const [manufacturer, setManufacturerState] = useState<Manufacturer>(() => {
    return (localStorage.getItem('preferredManufacturer') as Manufacturer) || 'radeon';
  });

  const setManufacturer = (m: Manufacturer) => {
    setManufacturerState(m);
    localStorage.setItem('preferredManufacturer', m);
  };

  return (
    <ManufacturerContext.Provider value={{ manufacturer, setManufacturer }}>
      {children}
    </ManufacturerContext.Provider>
  );
};
```

**TypeScript Interfaces**:
```typescript
// src/types/api.ts
export interface GPU {
  id: string;
  modelId: string;
  referenceName: string;
  manufacturer: 'radeon' | 'nvidia';
  generation: string;
  vramGb: number;
  performanceScore: number;
  isCurrentGen: boolean;
  officialSpecUrl: string | null;
  specUrlStatus: 'Active' | 'Unavailable' | 'NeedsReview';
}

export interface AuthResponse {
  token: string;
  expiresAt: string;
}

export interface ProblemDetails {
  type: string;
  title: string;
  status: number;
  detail: string;
  traceId: string;
}
```

**Tailwind Configuration**:
```javascript
// tailwind.config.js
/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        radeon: {
          primary: '#ED1C24',
          secondary: '#000000',
        },
        nvidia: {
          primary: '#76B900',
          secondary: '#000000',
        },
      },
    },
  },
  plugins: [],
}
```

**Component Standards**:
- All components must be functional (no class components)
- All props must have TypeScript interfaces
- Use TanStack Query for data fetching (no useEffect for API calls)
- Use Tailwind utility classes only (no CSS modules)
- Error states must use `<ErrorBoundary>` or `<ErrorMessage>` component
- Loading states must use `<LoadingSkeleton>` component

---

## Background Job Infrastructure

### Hangfire Configuration

**Database Storage**: Use PostgreSQL as Hangfire job storage (same database as main application)

**Dashboard Access**: 
- Mounted at `/hangfire` route
- Requires `AdminOnly` authorization policy
- Accessible only to authenticated admin users

**Recurring Job Registration** (configured in startup):
```csharp
// Program.cs or Startup.cs
RecurringJob.AddOrUpdate<RetailScraperService>(
    "retail-price-scraper",
    service => service.ScrapeRetailPrices(),
    "0 2 * * *",  // 2 AM UTC daily
    new RecurringJobOptions { TimeZone = TimeZoneInfo.Utc }
);

RecurringJob.AddOrUpdate<UsedScraperService>(
    "used-price-scraper",
    service => service.ScrapeUsedPrices(),
    "0 3 * * *",  // 3 AM UTC daily
    new RecurringJobOptions { TimeZone = TimeZoneInfo.Utc }
);

RecurringJob.AddOrUpdate<SpecLinkValidatorService>(
    "spec-link-validator",
    service => service.ValidateSpecLinks(),
    "0 2 * * 0",  // 2 AM UTC Sunday weekly
    new RecurringJobOptions { TimeZone = TimeZoneInfo.Utc }
);
```

**Job Retry Policy**:
- Automatic retries: Disabled (feature specs specify manual-only retry)
- Job timeout: 30 minutes for scraper jobs, 10 minutes for spec link validator
- Failed jobs: Logged in `ScraperLog` table with status "Failure"

**Monitoring**:
- Dashboard shows job execution history
- Succeeded/failed job counts visible
- Job execution time tracked

---

## Redis Cache Infrastructure

### Cache Service Interface

```csharp
// ICacheService.cs
public interface ICacheService
{
    Task<T?> GetAsync<T>(string key, CancellationToken cancellationToken = default);
    Task SetAsync<T>(string key, T value, TimeSpan? expiration = null, CancellationToken cancellationToken = default);
    Task RemoveAsync(string key, CancellationToken cancellationToken = default);
    Task<bool> ExistsAsync(string key, CancellationToken cancellationToken = default);
}
```

**Cache Key Conventions**:
- Visualization data: `viz:{manufacturer}:current` (e.g., `viz:radeon:current`)
- Retail prices: `retail-prices:{manufacturer}` (e.g., `retail-prices:nvidia`)
- Used prices: `used-prices:{manufacturer}` (e.g., `used-prices:radeon`)
- Admin sessions: `session:{userId}` (e.g., `session:admin-001`)

**TTL Defaults**:
- Visualization data: 5 minutes
- Retail/used price caches: 15 minutes
- Admin sessions: 24 hours (matches JWT token expiration)

**Connection**:
- Use `StackExchange.Redis` NuGet package
- Connection string from environment variable `REDIS_URL`
- Connection pooling enabled (default settings)

---

## HTTP Client Service

### HTTP Client Factory Configuration

```csharp
// Program.cs or Startup.cs
services.AddHttpClient("ScraperClient")
    .ConfigurePrimaryHttpMessageHandler(() => new HttpClientHandler
    {
        AutomaticDecompression = DecompressionMethods.GZip | DecompressionMethods.Deflate,
    })
    .AddPolicyHandler(GetRetryPolicy())
    .AddPolicyHandler(GetCircuitBreakerPolicy());

static IAsyncPolicy<HttpResponseMessage> GetRetryPolicy()
{
    return HttpPolicyExtensions
        .HandleTransientHttpError()
        .WaitAndRetryAsync(3, retryAttempt => TimeSpan.FromSeconds(Math.Pow(2, retryAttempt)));
}

static IAsyncPolicy<HttpResponseMessage> GetCircuitBreakerPolicy()
{
    return HttpPolicyExtensions
        .HandleTransientHttpError()
        .CircuitBreakerAsync(5, TimeSpan.FromSeconds(30));
}
```

**Headers**:
- User-Agent: `GPUValueTracker/1.0 (+https://gpuvaluetracker.com)`
- Accept: `text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8`
- Accept-Language: `en-GB,en;q=0.9`

**Timeout**: 30 seconds per request

**Usage**: Injected via `IHttpClientFactory` in scraper services (FEAT-01, FEAT-02) and spec link validator (FEAT-04)

---

## Seed Data

### GPU Catalog (33 Models)

**RX 7000 Series** (7 models, current gen):
| Model ID | Reference Name | VRAM GB | Performance Score |
|----------|----------------|---------|-------------------|
| rx-7900-xtx | AMD Radeon RX 7900 XTX | 24 | 95 |
| rx-7900-xt | AMD Radeon RX 7900 XT | 20 | 90 |
| rx-7900-gre | AMD Radeon RX 7900 GRE | 16 | 85 |
| rx-7800-xt | AMD Radeon RX 7800 XT | 16 | 80 |
| rx-7700-xt | AMD Radeon RX 7700 XT | 12 | 70 |
| rx-7600-xt | AMD Radeon RX 7600 XT | 16 | 60 |
| rx-7600 | AMD Radeon RX 7600 | 8 | 55 |

**RTX 40 Series** (9 models, current gen):
| Model ID | Reference Name | VRAM GB | Performance Score |
|----------|----------------|---------|-------------------|
| rtx-4090 | NVIDIA GeForce RTX 4090 | 24 | 100 |
| rtx-4080-super | NVIDIA GeForce RTX 4080 SUPER | 16 | 93 |
| rtx-4080 | NVIDIA GeForce RTX 4080 | 16 | 91 |
| rtx-4070-ti-super | NVIDIA GeForce RTX 4070 Ti SUPER | 16 | 87 |
| rtx-4070-ti | NVIDIA GeForce RTX 4070 Ti | 12 | 83 |
| rtx-4070-super | NVIDIA GeForce RTX 4070 SUPER | 12 | 78 |
| rtx-4070 | NVIDIA GeForce RTX 4070 | 12 | 73 |
| rtx-4060-ti | NVIDIA GeForce RTX 4060 Ti | 8 | 63 |
| rtx-4060 | NVIDIA GeForce RTX 4060 | 8 | 58 |

**RX 6000 Series** (9 models, previous gen):
| Model ID | Reference Name | VRAM GB | Performance Score |
|----------|----------------|---------|-------------------|
| rx-6950-xt | AMD Radeon RX 6950 XT | 16 | 88 |
| rx-6900-xt | AMD Radeon RX 6900 XT | 16 | 86 |
| rx-6800-xt | AMD Radeon RX 6800 XT | 16 | 82 |
| rx-6800 | AMD Radeon RX 6800 | 16 | 77 |
| rx-6750-xt | AMD Radeon RX 6750 XT | 12 | 72 |
| rx-6700-xt | AMD Radeon RX 6700 XT | 12 | 68 |
| rx-6650-xt | AMD Radeon RX 6650 XT | 8 | 62 |
| rx-6600-xt | AMD Radeon RX 6600 XT | 8 | 57 |
| rx-6600 | AMD Radeon RX 6600 | 8 | 52 |

**RTX 30 Series** (8 models, previous gen):
| Model ID | Reference Name | VRAM GB | Performance Score |
|----------|----------------|---------|-------------------|
| rtx-3090-ti | NVIDIA GeForce RTX 3090 Ti | 24 | 92 |
| rtx-3090 | NVIDIA GeForce RTX 3090 | 24 | 89 |
| rtx-3080-ti | NVIDIA GeForce RTX 3080 Ti | 12 | 84 |
| rtx-3080 | NVIDIA GeForce RTX 3080 | 10 | 81 |
| rtx-3070-ti | NVIDIA GeForce RTX 3070 Ti | 8 | 75 |
| rtx-3070 | NVIDIA GeForce RTX 3070 | 8 | 71 |
| rtx-3060-ti | NVIDIA GeForce RTX 3060 Ti | 8 | 66 |
| rtx-3060 | NVIDIA GeForce RTX 3060 | 12 | 61 |

**Seed Data Notes**:
- All current-gen GPUs have `is_current_gen = true`
- All previous-gen GPUs have `is_current_gen = false`
- Performance scores are normalized across both manufacturers (RTX 4090 = 100, highest overall)
- `official_spec_url` is null for all models initially (populated by FEAT-04)
- `spec_url_status` defaults to "NeedsReview" for all models
- `created_at` and `updated_at` set to migration execution time

---

## Environment Variables

| Variable | Required | Default | Notes |
|----------|----------|---------|-------|
| DATABASE_URL | Yes | - | PostgreSQL connection string |
| REDIS_URL | Yes | - | Redis connection string (format: `localhost:6379`) |
| JWT_SECRET | Yes | - | 256-bit base64-encoded secret for JWT signing |
| ADMIN_USERNAME | Yes | - | Admin username for login |
| ADMIN_PASSWORD_HASH | Yes | - | Bcrypt hash of admin password (cost factor 12) |
| CORS_ORIGIN | No | http://localhost:5173 | Allowed frontend origin |
| API_BASE_URL | No | http://localhost:5000 | Backend API base URL |
| HANGFIRE_DASHBOARD_ENABLED | No | true | Enable/disable Hangfire dashboard |
| RATE_LIMIT_WINDOW_MINUTES | No | 60 | Rate limit window for login attempts |
| RATE_LIMIT_MAX_ATTEMPTS | No | 10 | Max login attempts per window |

**Example `.env` file** (development):
```
DATABASE_URL=Host=localhost;Port=5432;Database=gpuvalue;Username=postgres;Password=dev_password
REDIS_URL=localhost:6379
JWT_SECRET=your-256-bit-secret-here-base64-encoded
ADMIN_USERNAME=admin
ADMIN_PASSWORD_HASH=$2a$12$hash_here
CORS_ORIGIN=http://localhost:5173
API_BASE_URL=http://localhost:5000
```

---

## Definition of Done

- [ ] All database migrations execute successfully without errors
- [ ] All 33 GPU models are seeded with correct data
- [ ] All indexes are created and verified with `EXPLAIN` queries
- [ ] All CHECK constraints are enforced (test by attempting to insert invalid data)
- [ ] `GET /api/v1/gpus` returns 200 with seeded GPU data
- [ ] `GET /api/v1/gpus?manufacturer=radeon` returns only Radeon GPUs
- [ ] `GET /api/v1/gpus?currentGenOnly=false` includes previous-gen GPUs
- [ ] `POST /api/v1/auth/admin/login` with valid credentials returns JWT token and sets HttpOnly cookie
- [ ] `POST /api/v1/auth/admin/login` with invalid credentials returns 401
- [ ] `POST /api/v1/auth/admin/login` returns 429 after 10 failed attempts from same IP
- [ ] `GET /api/v1/admin/health` returns 403 without auth token
- [ ] `GET /api/v1/admin/health` returns 200 with valid auth token
- [ ] Redis connection succeeds and cache operations (set/get/delete) work
- [ ] Hangfire dashboard is accessible at `/hangfire` with admin auth
- [ ] Hangfire dashboard shows 0 recurring jobs (jobs registered but not yet implemented)
- [ ] Global error handler catches unhandled exceptions and returns RFC 7807 ProblemDetails
- [ ] CORS preflight requests (OPTIONS) return 200 with correct headers
- [ ] Swagger UI is accessible at `/swagger` and shows all endpoints
- [ ] Frontend React app renders at `http://localhost:5173` with "GPU Value Tracker" header
- [ ] Frontend dashboard page shows placeholder text (no data yet)
- [ ] Frontend admin login page renders and can submit form
- [ ] Frontend API client successfully calls `GET /api/v1/gpus` and logs response
- [ ] Manufacturer context provider initializes with "radeon" default
- [ ] localStorage stores and retrieves `preferredManufacturer` correctly
- [ ] All TypeScript compiles without errors (`tsc --noEmit` passes)
- [ ] All backend unit tests pass (if any written during foundation)
- [ ] HTTP client factory can be injected and makes successful test request