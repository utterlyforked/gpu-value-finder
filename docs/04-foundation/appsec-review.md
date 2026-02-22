# AppSec Review

**Date**: 2025-01-12  
**Scope**: Foundation + 5 features  
**Risk Level**: **Medium**

---

## Executive Summary

GPU Value Tracker is a public-facing web application that aggregates GPU pricing data from retail and used marketplaces, presenting comparative value analysis through an interactive dashboard. The primary attack surface consists of web scraping infrastructure, public REST APIs, and admin-only background job management. 

Overall risk posture is **Medium** due to minimal authentication requirements (admin-only backoffice), no user-generated content, and no payment processing. Critical risks center on scraping compliance, input validation from untrusted marketplace data, and API abuse prevention. Most sensitive data is pricing snapshots and admin session tokens—no PII or payment data is processed.

---

## Critical Requirements

Must be implemented before launch. Failure here is a showstopper.

### AUTH-01: Admin Authentication Token Security

**Risk**: Admin backoffice compromise allows unauthorized scraper triggering, spec link manipulation, and monitoring dashboard access. If JWT secret is weak or tokens don't expire, attackers can maintain persistent access.

**Requirement**: 
- JWT tokens must use HS256 algorithm with minimum 256-bit secret (generated via cryptographically secure RNG, stored in Azure Key Vault or equivalent secrets manager)
- Tokens must be stored in HttpOnly, Secure, SameSite=Strict cookies (never localStorage or sessionStorage)
- Token expiry: 24 hours maximum for access tokens
- Refresh tokens: 30-day expiry, single-use with rotation on refresh
- On logout, server-side token revocation via Redis blacklist (key: `revoked:jwt:{jti}`, TTL matching original token expiry)

**Applies to**: Foundation (authentication infrastructure)

---

### AUTH-02: Admin Endpoint Authorization

**Risk**: Missing or incorrect authorization on admin endpoints allows unauthenticated users to trigger expensive scraping jobs, manipulate GPU data, or access monitoring dashboards.

**Requirement**:
- All admin endpoints must require `[Authorize(Roles = "Admin")]` attribute
- Admin role assignment must be manual (no self-service registration)
- Initial admin account seeded via secure migration (credentials in environment variables, not hardcoded)
- Affected endpoints:
  - `POST /api/v1/admin/scraper/trigger` (FEAT-01, FEAT-02)
  - `GET /api/v1/admin/scraper/status/{jobId}` (FEAT-01, FEAT-02)
  - `GET /hangfire` (background job dashboard)
  - `POST /api/v1/admin/gpus/{id}/spec-url` (FEAT-04 spec link management)
  - Any future admin CRUD operations on GPU catalog

**Applies to**: Foundation, FEAT-01, FEAT-02, FEAT-04

---

### INPUT-01: Scraper Data Sanitization

**Risk**: Malicious marketplace listings containing XSS payloads, SQL injection attempts, or oversized data can corrupt database, exploit frontend rendering, or cause DoS.

**Requirement**:
- All scraped data (GPU model names, prices, URLs) must be sanitized before database insertion
- Model name validation: Max 200 characters, alphanumeric + spaces/hyphens only, regex: `^[a-zA-Z0-9\s\-]{1,200}$`
- Price validation: Decimal type, range £0.01 - £99,999.99, reject non-numeric values
- URL validation: Must match pattern `^https?://[a-zA-Z0-9\-\.]+\.[a-z]{2,}(/.*)?$`, max 2000 characters, HTTP HEAD request validation before storage
- Listing descriptions (if stored): HTML-encode on output, max 5000 characters
- Reject listings with null/empty required fields (price, model, source)
- Log rejected listings to `InvalidScrapedListing` table for review (not main data flow)

**Applies to**: FEAT-01 (retail scraping), FEAT-02 (used scraping), FEAT-04 (spec URL imports)

---

### INPUT-02: API Input Validation

**Risk**: Public API endpoints accepting malformed manufacturer parameters, malicious query strings, or oversized requests can cause crashes, expose error details, or enable injection attacks.

**Requirement**:
- `GET /api/v1/gpus?manufacturer={value}` must validate manufacturer parameter:
  - Whitelist: Only `"radeon"` or `"nvidia"` accepted (case-insensitive)
  - Reject and return 400 Bad Request for any other value
  - Error response must use RFC 7807 ProblemDetails (no stack traces in production)
- `GET /api/v1/visualization/data?manufacturer={value}&includeOlderGen={bool}`:
  - Validate `includeOlderGen` as boolean (`true`/`false` only)
  - Reject unexpected query parameters (return 400)
- All API endpoints: Max request size 1MB (prevent DoS via large payloads)
- Request timeout: 30 seconds server-side

**Applies to**: Foundation (API infrastructure), FEAT-03 (visualization API), FEAT-05 (manufacturer filtering)

---

### DATA-01: Prevent Mass Data Exposure

**Risk**: API responses returning entire database (no pagination, no field filtering) enable competitors to scrape all pricing data, overload servers, and create derivative products.

**Requirement**:
- `GET /api/v1/gpus` must return only active GPUs (exclude archived models by default unless `?includeArchived=true`)
- Response must explicitly list returned fields (no wildcard `SELECT *` projections)
- Exclude internal fields from API responses:
  - `GPU.Id` (use `ModelId` public identifier instead)
  - `SpecUrlLastChecked` (internal monitoring data)
  - `CreatedAt`, `UpdatedAt` (internal audit data)
- Implement pagination if response exceeds 50 GPUs (parameter: `?page=1&pageSize=50`, max pageSize=100)
- API responses must include `ETag` header for conditional requests (reduce bandwidth)
- Cache-Control headers: `public, max-age=300` (5 minutes, prevent excessive refetching)

**Applies to**: Foundation (API patterns), FEAT-03 (visualization data endpoint), FEAT-05 (manufacturer filtering)

---

### INFRA-01: CORS Configuration

**Risk**: Misconfigured CORS allows malicious sites to call APIs from victim browsers, steal admin tokens, or trigger unauthorized actions.

**Requirement**:
- CORS policy must explicitly whitelist allowed origins (no wildcard `*` in production)
- Allowed origin: `https://gpuvaluetracker.com` (production domain)
- Allowed origins (development): `http://localhost:5173` (Vite), `http://localhost:7000` (API)
- Allowed methods: `GET`, `POST`, `PUT`, `DELETE`, `OPTIONS`
- Allowed headers: `Content-Type`, `Authorization`, `X-Requested-With`
- Exposed headers: `ETag`, `X-Total-Count`, `X-Page-Size`
- `AllowCredentials: true` (required for HttpOnly cookie authentication)
- Preflight cache: 1 hour (`Access-Control-Max-Age: 3600`)

**Applies to**: Foundation (API infrastructure)

---

### INFRA-02: HTTPS Enforcement

**Risk**: Unencrypted HTTP connections expose admin tokens, allow man-in-the-middle attacks, and leak pricing data.

**Requirement**:
- Production API must reject all HTTP requests (301 redirect to HTTPS or 400 Bad Request)
- HSTS header required: `Strict-Transport-Security: max-age=31536000; includeSubDomains; preload`
- TLS 1.3 minimum (disable TLS 1.0, 1.1, 1.2)
- Certificate: Valid wildcard cert from Let's Encrypt or commercial CA (no self-signed in production)
- Local development: HTTPS via `dotnet dev-certs https --trust`

**Applies to**: Foundation (API infrastructure)

---

### INFRA-03: Secrets Management

**Risk**: Hardcoded API keys, database passwords, or JWT secrets in code/config files enable credential theft via repository access or leaked environment variables.

**Requirement**:
- All secrets must be stored in Azure Key Vault (production) or Docker secrets (local dev)
- Prohibited in appsettings.json or environment variables:
  - Database connection strings (retrieve from Key Vault)
  - JWT signing secret
  - Redis connection string
  - eBay API credentials
  - Admin account passwords
- Application startup must fail fast if secrets are missing (no defaults)
- Secrets rotation: JWT secret rotated every 90 days, database password every 180 days
- Secrets must never appear in logs (use `[Sensitive]` attribute in Serilog)

**Applies to**: Foundation (configuration management), FEAT-01 (retailer credentials), FEAT-02 (eBay API keys)

---

## High Priority Requirements

Should be implemented in the first release. Deferring increases risk significantly.

### SEC-01: Rate Limiting on Admin Endpoints

**Risk**: Brute-force attacks on admin login, DoS via repeated manual scraper triggers, or credential stuffing attacks.

**Requirement**:
- `POST /api/v1/admin/login`: 5 attempts per IP per 15-minute window, return 429 Too Many Requests on limit
- `POST /api/v1/admin/scraper/trigger`: 1 trigger per admin user per 5 minutes (prevent abuse)
- Rate limiting via ASP.NET Core Rate Limiting middleware (built-in .NET 7+)
- Configuration:
  ```csharp
  builder.Services.AddRateLimiter(options => {
      options.AddFixedWindowLimiter("admin-login", opt => {
          opt.Window = TimeSpan.FromMinutes(15);
          opt.PermitLimit = 5;
          opt.QueueLimit = 0;
      });
  });
  ```
- Logged failed attempts must include IP address, timestamp, username attempt (for forensic analysis)

**Applies to**: Foundation (admin authentication), FEAT-01, FEAT-02 (manual scraper trigger)

---

### SEC-02: Scraper Request Identification

**Risk**: Retailer/marketplace sites block GPU Value Tracker scrapers due to missing User-Agent, excessive request rates, or ToS violations.

**Requirement**:
- All HTTP requests from scrapers must include identifiable User-Agent:
  - Format: `GPUValueTracker/1.0 (+https://gpuvaluetracker.com/bot; contact@gpuvaluetracker.com)`
- Respect `robots.txt` for all scraped sites (fetch and parse before scraping)
- Rate limiting per site:
  - Retail sites (Scan, Ebuyer, Amazon): Min 2-second delay between requests
  - CEX: Min 3-second delay
  - eBay API: Respect API rate limits (5,000 calls/day)
- Timeout handling: 30-second request timeout, 3 retry attempts with exponential backoff
- Log all scraper 429 (rate limit) and 403 (forbidden) responses for monitoring

**Applies to**: FEAT-01 (retail scraping), FEAT-02 (used scraping), FEAT-04 (spec URL validation)

---

### SEC-03: CSV Import Validation (Spec Links)

**Risk**: Malicious CSV files uploaded by admins can inject XSS payloads, SQL commands, or malformed data into GPU spec URLs.

**Requirement**:
- CSV parser must validate file size: Max 1MB
- Row limit: Max 500 rows (prevents resource exhaustion)
- Column validation:
  - `GPUId`: Must be valid GUID format
  - `ModelName`: Max 200 characters, alphanumeric + spaces/hyphens
  - `SuggestedURL`: Must match URL pattern, HTTPS only, max 2000 characters
  - `Manufacturer`: Whitelist `"radeon"` or `"nvidia"` only
- Reject CSV if any row fails validation (atomic import—all or nothing)
- Preview imported data to admin before committing (show first 10 rows, require explicit confirmation)
- Log all CSV imports with admin username, timestamp, row count

**Applies to**: FEAT-04 (spec link CSV import)

---

### SEC-04: Background Job Authorization

**Risk**: Hangfire dashboard exposes job history, allows manual job triggering, and reveals system internals if publicly accessible.

**Requirement**:
- Hangfire dashboard at `/hangfire` must require authentication
- Apply `[Authorize(Roles = "Admin")]` filter to dashboard:
  ```csharp
  app.UseHangfireDashboard("/hangfire", new DashboardOptions {
      Authorization = new[] { new HangfireAuthorizationFilter() }
  });
  ```
- Dashboard must be excluded from public API documentation (not in Swagger)
- Job execution logs must not contain secrets (eBay API keys, database passwords)
- Failed jobs must not expose stack traces in dashboard (log full trace to Application Insights only)

**Applies to**: Foundation (Hangfire setup), FEAT-01, FEAT-02 (scraping jobs), FEAT-04 (validation job)

---

### SEC-05: Redis Connection Security

**Risk**: Unprotected Redis instance allows unauthorized cache manipulation, session hijacking, or DoS via cache poisoning.

**Requirement**:
- Redis must require password authentication (no anonymous access)
- Connection string format: `redis://:password@hostname:6379,ssl=true,abortConnect=false`
- Production: Enable TLS for Redis connections (`ssl=true`)
- Local dev: Password-protected Redis in Docker Compose
- Redis password: Min 32 characters, stored in Azure Key Vault
- Network segmentation: Redis accessible only from backend API (not public internet)

**Applies to**: Foundation (Redis caching), FEAT-01, FEAT-02, FEAT-03, FEAT-05 (all use Redis cache)

---

### SEC-06: Database Connection Pooling Limits

**Risk**: Unbounded database connections enable connection pool exhaustion DoS, causing 503 errors for all users.

**Requirement**:
- PostgreSQL connection string must include pooling limits:
  - `Pooling=true;MinPoolSize=5;MaxPoolSize=50`
- EF Core `DbContext` must use scoped lifetime (not singleton)
- Long-running queries (>5 seconds) must be logged as warnings
- Database timeout: 30 seconds per query
- Retry policy: Max 3 retries on transient failures (network blips), exponential backoff

**Applies to**: Foundation (database configuration)

---

### SEC-07: Error Response Sanitization

**Risk**: Verbose error messages expose database schema, internal paths, or stack traces to attackers, aiding reconnaissance.

**Requirement**:
- Production API must return RFC 7807 ProblemDetails for all errors (no raw exceptions)
- Error responses must NOT include:
  - Database table names or SQL queries
  - File paths (`C:\app\src\...`)
  - Stack traces
  - Internal IP addresses or hostnames
- Generic error messages:
  - 400 Bad Request: "Invalid input. Please check your request."
  - 401 Unauthorized: "Authentication required."
  - 403 Forbidden: "You do not have permission to access this resource."
  - 500 Internal Server Error: "An unexpected error occurred. Please try again later."
- Full error details logged to Application Insights with correlation IDs (not sent to client)

**Applies to**: Foundation (global error handling middleware)

---

### SEC-08: Frontend XSS Prevention

**Risk**: Scraped GPU model names, prices, or spec URLs containing malicious scripts execute in user browsers, stealing session tokens or redirecting to phishing sites.

**Requirement**:
- React must render all dynamic content via JSX (automatic HTML escaping)
- Prohibited: `dangerouslySetInnerHTML` usage anywhere in codebase
- URL rendering (spec links, retailer links):
  - Must use `<a href={sanitizedUrl}>` (React escapes by default)
  - Validate URL protocol: Only `http://` and `https://` allowed (reject `javascript:`, `data:`, `file:`)
  - Add `rel="noopener noreferrer"` to all external links
- Content Security Policy (CSP) header:
  ```
  Content-Security-Policy: 
    default-src 'self'; 
    script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; 
    style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; 
    img-src 'self' https: data:; 
    font-src 'self' https://fonts.gstatic.com;
    connect-src 'self' https://api.gpuvaluetracker.com;
  ```

**Applies to**: Foundation (frontend infrastructure), FEAT-03 (visualization dashboard), FEAT-04 (spec links), FEAT-05 (manufacturer toggle)

---

### SEC-09: Dependency Vulnerability Scanning

**Risk**: Outdated NuGet packages or npm dependencies with known CVEs enable exploitation (e.g., prototype pollution in lodash, RCE in System.Text.Json).

**Requirement**:
- Backend: Enable NuGet package vulnerability scanning in CI/CD
  - Run `dotnet list package --vulnerable` in build pipeline
  - Fail build on any high/critical severity vulnerabilities
  - Update packages monthly (automated PR via Dependabot or Renovate)
- Frontend: Enable npm audit in CI/CD
  - Run `npm audit --production --audit-level=high` in build pipeline
  - Fail build on high/critical vulnerabilities
  - Update dependencies monthly
- Exclude development dependencies from production builds (`npm prune --production`)

**Applies to**: Foundation (entire stack)

---

## Medium Priority Requirements

Best practice; address before going to production with real users.

### SEC-10: Audit Logging for Admin Actions

**Risk**: Unauthorized admin actions (scraper triggers, data manipulation) go undetected without audit trail.

**Requirement**:
- Log all admin actions to Application Insights:
  - Manual scraper triggers (user, timestamp, manufacturer)
  - Spec URL updates (user, GPU model, old URL, new URL)
  - CSV imports (user, row count, success/failure)
  - Login attempts (username, IP, success/failure)
- Log retention: 90 days minimum
- Logs must be immutable (append-only, no deletion by admins)

**Applies to**: Foundation (logging infrastructure), FEAT-01, FEAT-02, FEAT-04

---

### SEC-11: API Response Size Limits

**Risk**: Unbounded API responses cause memory exhaustion, slow page loads, or client crashes.

**Requirement**:
- `GET /api/v1/gpus`: Max 50 GPUs per response (implement pagination if exceeded)
- `GET /api/v1/visualization/data`: Max 100 data points per response
- JSON response max size: 5MB (server-side limit)
- Gzip compression enabled for all API responses (reduces bandwidth)

**Applies to**: Foundation (API infrastructure), FEAT-03 (visualization endpoint)

---

### SEC-12: Session Fixation Prevention

**Risk**: Attacker forces victim to use attacker-controlled session ID, hijacks session after login.

**Requirement**:
- On admin login, regenerate session ID (issue new JWT with different `jti`)
- Old session tokens must be invalidated (added to Redis blacklist)
- Session cookies must have `SameSite=Strict` attribute

**Applies to**: Foundation (authentication)

---

### SEC-13: Clickjacking Prevention

**Risk**: Malicious site embeds GPU Value Tracker in iframe, tricks admin into triggering actions while logged in.

**Requirement**:
- Add `X-Frame-Options: DENY` header to all responses
- Add `Content-Security-Policy: frame-ancestors 'none'` header
- Test: Attempt to embed dashboard in `<iframe>` on external site (should fail)

**Applies to**: Foundation (HTTP headers middleware)

---

### SEC-14: Database Query Parameterization

**Risk**: String concatenation in dynamic queries enables SQL injection.

**Requirement**:
- All database queries must use Entity Framework LINQ (no raw SQL)
- If raw SQL is required (performance optimization), use parameterized queries:
  ```csharp
  var manufacturer = "radeon";
  var gpus = await _context.Gpus
      .FromSqlRaw("SELECT * FROM gpus WHERE manufacturer = {0}", manufacturer)
      .ToListAsync();
  ```
- Never concatenate user input into SQL strings:
  ```csharp
  // PROHIBITED:
  var sql = $"SELECT * FROM gpus WHERE manufacturer = '{manufacturer}'";
  ```

**Applies to**: Foundation (database access)

---

## Feature-Specific Notes

### FEAT-01: Live Retail Price Aggregation

- **Scraper credential storage**: Retailer login credentials (if required for accessing price data) must be in Azure Key Vault, rotated every 90 days
- **Outlier filtering bypass**: If attacker manipulates scraper to insert extreme prices (£0.01, £999,999), outlier filter (>1.5x median) mitigates impact
- **Manual trigger abuse**: Rate limit `POST /api/v1/admin/scraper/trigger` to 1 request per 5 minutes per user

---

### FEAT-02: Used Market Price Discovery

- **eBay API credentials**: Store in Azure Key Vault, rotate every 90 days per eBay Partner Network policy
- **CEX scraping**: Monitor for CAPTCHA responses (indicates detection), log and alert on 403 Forbidden
- **Unmatched listings**: Log rejected GPU models to `UnmatchedListing` table (not main flow) to prevent injection attacks via malformed model names

---

### FEAT-03: Value Visualization Dashboard

- **XSS via GPU model names**: All model names must be HTML-escaped in React (automatic via JSX)
- **CSV export of visualization data**: If added in v2, validate export format (no Excel formula injection: `=SUM(...)`)
- **Real-time WebSocket updates**: If added in v2, authenticate WebSocket connections (JWT in Sec-WebSocket-Protocol header)

---

### FEAT-04: Manufacturer Reference Links

- **CSV import validation**: See SEC-03 (high priority)
- **Spec URL SSRF protection**: If adding automatic URL validation, prevent SSRF by blacklisting private IP ranges:
  - Reject URLs to `127.0.0.1`, `169.254.*`, `10.*`, `172.16-31.*`, `192.168.*`
- **Link hijacking**: Validate spec URLs match expected OEM domains (amd.com, nvidia.com) to prevent phishing redirects

---

### FEAT-05: Radeon vs Nvidia Mode Switching

- **localStorage tampering**: If user edits localStorage to invalid manufacturer value (`"intel"`, `"<script>"`), API validation rejects it (400 Bad Request)
- **Cache poisoning**: Redis cache keys must include manufacturer (`viz:radeon:current`) to prevent cross-manufacturer cache pollution

---

## What the Engineering Spec Must Include

A checklist of security requirements the engineering spec agent must address in each component:

**Foundation**:
- [x] JWT signing algorithm (HS256), secret minimum 256 bits, stored in Key Vault
- [x] JWT expiry: 24 hours access tokens, 30-day refresh tokens with rotation
- [x] HttpOnly, Secure, SameSite=Strict cookie configuration
- [x] Token revocation via Redis blacklist on logout
- [x] Admin role assignment: Manual only, initial admin seeded via migration
- [x] `[Authorize(Roles = "Admin")]` on all admin endpoints
- [x] Rate limiting: 5 attempts per 15 min on login, 1 trigger per 5 min on scraper endpoints
- [x] CORS policy: Explicit origin whitelist, no wildcard `*`
- [x] HTTPS enforcement: HSTS header, TLS 1.3 minimum
- [x] Secrets management: Azure Key Vault for production, Docker secrets for dev
- [x] Database connection pooling: MaxPoolSize=50, 30-second query timeout
- [x] Global error handling: RFC 7807 ProblemDetails, no stack traces in production
- [x] CSP header: `default-src 'self'`, explicit script/style/img sources
- [x] X-Frame-Options: DENY
- [x] Dependency scanning: `dotnet list package --vulnerable` in CI/CD

**All authenticated endpoints**:
- [x] Authorization policy: `[Authorize(Roles = "Admin")]`
- [x] Unauthorized behavior: 401 if not authenticated, 403 if authenticated but not Admin
- [x] Rate limiting rules documented (see SEC-01)

**Any endpoint accepting user input** (API query params, scraper data, CSV imports):
- [x] Input validation: Manufacturer whitelist (`"radeon"`, `"nvidia"`), boolean validation for `includeOlderGen`
- [x] Size limits: 1MB max request size, 500 rows max CSV, 2000 characters max URL
- [x] Sanitization: Model names alphanumeric + spaces/hyphens, prices £0.01-£99,999.99
- [x] URL validation: HTTPS only, protocol whitelist, max 2000 characters

**Any endpoint returning user data**:
- [x] Explicit field list: No `SELECT *`, exclude internal fields (`Id`, `CreatedAt`, `SpecUrlLastChecked`)
- [x] Pagination: Max 50 GPUs per response, 100 data points in visualization
- [x] Response size limit: 5MB max JSON, gzip compression enabled
- [x] Cache headers: `ETag`, `Cache-Control: public, max-age=300`

**Scraping infrastructure** (FEAT-01, FEAT-02, FEAT-04):
- [x] User-Agent: `GPUValueTracker/1.0 (+URL; contact@email)` on all requests
- [x] Respect `robots.txt` for CEX and retail sites
- [x] Rate limiting: Min 2-second delay per retailer, 3 seconds for CEX
- [x] Timeout: 30 seconds per request, 3 retry attempts with exponential backoff
- [x] eBay API rate limit: 5,000 calls/day, monitor and alert on 429 responses

**Background jobs** (Hangfire):
- [x] Dashboard authorization: `[Authorize(Roles = "Admin")]` on `/hangfire`
- [x] Dashboard excluded from Swagger documentation
- [x] Job logs exclude secrets (eBay API keys, database passwords)
- [x] Failed job logs: Full stack trace to Application Insights only, generic error in dashboard

**Frontend** (React):
- [x] All dynamic content via JSX (automatic HTML escaping)
- [x] No `dangerouslySetInnerHTML` usage
- [x] External links: `rel="noopener noreferrer"` on all `<a target="_blank">`
- [x] URL protocol validation: Only `http://` and `https://`, reject `javascript:`, `data:`
- [x] CSP header applied (see SEC-08)

---

## Out of Scope

- **Penetration testing**: Recommended post-launch, but not blocking for MVP
- **Infrastructure security**: 
  - Cloud provider configuration (Azure network security groups, firewall rules)
  - Kubernetes pod security policies
  - CI/CD pipeline security (GitHub Actions secrets, Docker image signing)
  - These are assumed to follow industry best practices, but not covered in this review
- **Compliance frameworks**: 
  - GDPR: Risk is low (no PII collected beyond admin accounts), but document data retention policies
  - SOC 2: Recommended for enterprise customers, but not MVP requirement
  - PCI DSS: Not applicable (no payment processing)
- **DDoS mitigation**: Cloudflare or Azure DDoS Protection assumed to be in place at infrastructure layer
- **Advanced threat detection**: SIEM integration, anomaly detection, threat intelligence feeds are post-MVP enhancements

---

## Quality Checklist

- [x] All critical requirements are specific and testable
- [x] Each requirement names the component it applies to
- [x] Priority levels are justified (Critical = launch blocker, High = first release, Medium = best practice)
- [x] Feature-specific risks are called out (FEAT-01 through FEAT-05)
- [x] Engineering spec checklist is complete and actionable
- [x] No vague advice ("be secure", "validate input")—all requirements include acceptance criteria
- [x] No implementation code (requirements only, not C# snippets for production)

---

**Review Status**: ✅ **COMPLETE**  
**Next Step**: Engineering agent must incorporate all Critical and High Priority requirements into technical specification before implementation begins. Medium Priority requirements should be tracked as post-MVP hardening tasks.