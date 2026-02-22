# Radeon vs Nvidia Mode Switching — Engineering Spec

**Type**: feature
**Component**: manufacturer-mode-switching
**Dependencies**: foundation-spec (User, Authentication), FEAT-01 (retail pricing), FEAT-02 (used pricing), FEAT-03 (value visualization)
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

The Radeon vs Nvidia Mode Switching feature is a client-side filtering mechanism that controls which manufacturer's GPU data is visible across the entire dashboard. Users toggle between viewing AMD Radeon GPUs or Nvidia GPUs—never both simultaneously, as cross-manufacturer comparisons are not valuable given different architectures and ecosystems.

This component owns no new entities. It extends the existing `Gpu` entity (defined in foundation) with a `manufacturer` field and filtering logic. The selected mode persists in browser localStorage and determines which GPU records are returned by the API. All pricing data (retail and used), visualizations, and OEM spec links respect this filter.

**Foundation dependencies**: Reads from `Gpu` entity. Does not create new database tables beyond adding a column to the existing `gpus` table.

---

## Data Model

### Gpu (Extended)

This spec adds the `manufacturer` field to the existing `Gpu` entity defined in the foundation spec.

**New field**:

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| manufacturer | VARCHAR(50) | NOT NULL, CHECK constraint | Values: `'radeon'` or `'nvidia'` (lowercase only). Default: `'radeon'`. |

**Index**:
- `idx_gpus_manufacturer` on `(manufacturer)` — for fast filtering by manufacturer

**CHECK Constraint**:
```sql
CONSTRAINT chk_manufacturer CHECK (manufacturer IN ('radeon', 'nvidia'))
```

**Migration Notes**:
- Add column with default value `'radeon'` to support existing rows
- Update existing rows based on model naming patterns:
  - Models starting with `'RTX '` or `'GTX '` → set `manufacturer = 'nvidia'`
  - Models starting with `'RX '` or `'Radeon '` → set `manufacturer = 'radeon'`
- Add CHECK constraint after data migration
- Create index after column population

**C# Enum** (for application layer type safety):
```
public enum ManufacturerType 
{
    Radeon,
    Nvidia
}
```

Entity Framework Core auto-converts enum to lowercase string on save and parse string to enum on read using `.ToLowerInvariant()`.

> **Note**: This spec does not redefine the `Gpu` entity. See foundation spec for full `Gpu` schema (id, model, retail_price, used_price, value_score, spec_url, etc.). This spec only adds the `manufacturer` field.

---

## API Endpoints

### GET /api/v1/gpus

**Auth**: None (public endpoint)
**Authorization**: None

**Query parameters**:

| Parameter | Type | Required | Validation |
|-----------|------|----------|-----------|
| manufacturer | string | yes | Must be `'radeon'` or `'nvidia'` (case-insensitive) |

**Success response** `200 OK`:

| Field | Type | Notes |
|-------|------|-------|
| manufacturer | string | Normalized to lowercase (e.g., `"radeon"`) |
| gpus | array | Array of GPU objects with full nested data |
| gpus[].id | UUID | GPU unique identifier |
| gpus[].model | string | GPU model name (e.g., "RX 7900 XTX") |
| gpus[].manufacturer | string | Always matches query param (lowercase) |
| gpus[].retailPrice | object | Retail pricing data |
| gpus[].retailPrice.amount | decimal | Price in USD |
| gpus[].retailPrice.currency | string | Always `"USD"` |
| gpus[].retailPrice.lastUpdated | ISO 8601 datetime | UTC timestamp |
| gpus[].retailPrice.sources | string[] | Array of retailer names (e.g., `["newegg", "amazon"]`) |
| gpus[].usedPrice | object | Used market pricing data |
| gpus[].usedPrice.amount | decimal | Price in USD |
| gpus[].usedPrice.currency | string | Always `"USD"` |
| gpus[].usedPrice.lastUpdated | ISO 8601 datetime | UTC timestamp |
| gpus[].usedPrice.source | string | Marketplace name (e.g., `"ebay"`) |
| gpus[].valueScore | decimal | Value score (0.0 to 10.0) |
| gpus[].specUrl | string | OEM specification page URL |
| metadata | object | Response metadata |
| metadata.count | integer | Number of GPUs in response |
| metadata.lastUpdated | ISO 8601 datetime | UTC timestamp of most recent data update |
| metadata.cacheExpiresAt | ISO 8601 datetime | UTC timestamp when cache expires |

**Example response**:
```json
{
  "manufacturer": "radeon",
  "gpus": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "model": "RX 7900 XTX",
      "manufacturer": "radeon",
      "retailPrice": {
        "amount": 999.99,
        "currency": "USD",
        "lastUpdated": "2025-01-10T10:30:00Z",
        "sources": ["newegg", "amazon", "bestbuy"]
      },
      "usedPrice": {
        "amount": 849.99,
        "currency": "USD",
        "lastUpdated": "2025-01-10T09:15:00Z",
        "source": "ebay"
      },
      "valueScore": 8.5,
      "specUrl": "https://www.amd.com/en/products/graphics/amd-radeon-rx-7900xtx"
    }
  ],
  "metadata": {
    "count": 15,
    "lastUpdated": "2025-01-10T10:30:00Z",
    "cacheExpiresAt": "2025-01-10T10:35:00Z"
  }
}
```

**Error responses**:

| Status | Condition | Response Body |
|--------|-----------|---------------|
| 400 | Missing `manufacturer` query param | `{ "title": "Missing manufacturer parameter", "detail": "Query parameter 'manufacturer' is required.", "status": 400 }` |
| 400 | Invalid `manufacturer` value | `{ "title": "Invalid manufacturer", "detail": "Must be 'radeon' or 'nvidia'.", "status": 400 }` |
| 404 | No GPUs found for manufacturer | `{ "title": "No data available", "detail": "No GPU data available for manufacturer 'radeon'.", "status": 404 }` |
| 500 | Database error or Redis unavailable | `{ "title": "Internal server error", "detail": "An error occurred processing your request.", "status": 500 }` |

**Caching**:
- Redis cache key: `gpus:manufacturer:{manufacturer}` (e.g., `gpus:manufacturer:radeon`)
- TTL: 300 seconds (5 minutes)
- Cache miss: Query database, serialize response, store in Redis, return response (~300ms)
- Cache hit: Return cached response directly (~50ms)

**Request cancellation**:
- Endpoint must support cancellation via `CancellationToken` passed from controller
- If client aborts request (e.g., rapid mode toggle), database query and serialization should cancel gracefully

---

### POST /api/admin/cache/invalidate

**Auth**: Required (Bearer JWT)
**Authorization**: Admin role required

**Request body**:

| Field | Type | Required | Validation |
|-------|------|----------|-----------|
| manufacturer | string | yes | Must be `'radeon'` or `'nvidia'` (case-insensitive) |

**Success response** `204 No Content`:
- Empty body
- Cache entry for specified manufacturer is deleted

**Error responses**:

| Status | Condition |
|--------|-----------|
| 400 | Invalid `manufacturer` value |
| 401 | Not authenticated |
| 403 | User lacks Admin role |

---

## Business Rules

1. The `manufacturer` field is normalized to lowercase before storage and lookup (e.g., `"Radeon"` → `"radeon"`).
2. Only two manufacturer values are valid: `"radeon"` and `"nvidia"`. Any other value is rejected with 400 Bad Request.
3. The API returns only GPUs matching the exact manufacturer specified in the query parameter—no mixing of manufacturers in a single response.
4. On first visit (no localStorage value), the frontend defaults to `"radeon"` mode and persists this choice immediately on first toggle.
5. Cache entries are independent per manufacturer—invalidating `radeon` cache does not affect `nvidia` cache.
6. If zero GPUs exist for a manufacturer (database query returns empty result), the API returns 404 with descriptive error message.
7. The `manufacturer` field is required (NOT NULL) on all `Gpu` records—no GPU can exist without a manufacturer value.
8. Database CHECK constraint enforces valid values at insertion/update—invalid values are rejected before reaching application layer.

---

## Validation Rules

| Field | Rule | Error message |
|-------|------|---------------|
| manufacturer (query param) | Required | "Query parameter 'manufacturer' is required." |
| manufacturer (query param) | Must be `'radeon'` or `'nvidia'` (case-insensitive) | "Invalid manufacturer. Must be 'radeon' or 'nvidia'." |
| manufacturer (database) | Must pass CHECK constraint (`IN ('radeon', 'nvidia')`) | Database constraint violation error (should never occur if API validation is correct) |

---

## Authorization

| Action | Required policy | Notes |
|--------|----------------|-------|
| GET /api/v1/gpus | None (public) | No authentication required—data is publicly accessible |
| POST /api/admin/cache/invalidate | Admin role | Only admin users can manually invalidate cache |

---

## Acceptance Criteria

- [ ] User can toggle between "Radeon" and "Nvidia" modes using a segmented control or tab interface
- [ ] Toggle component is visible above-the-fold (no scrolling required)
- [ ] Only one manufacturer's data is displayed at a time—Radeon and Nvidia data are never mixed in a single view
- [ ] User's selection persists across page reloads via localStorage (key: `preferredManufacturer`, values: `"radeon"` or `"nvidia"`)
- [ ] On first visit (no localStorage value), the application defaults to Radeon mode
- [ ] GET /api/v1/gpus?manufacturer=radeon returns only Radeon GPUs with status 200
- [ ] GET /api/v1/gpus?manufacturer=nvidia returns only Nvidia GPUs with status 200
- [ ] GET /api/v1/gpus without `manufacturer` query param returns 400 Bad Request
- [ ] GET /api/v1/gpus?manufacturer=intel returns 400 Bad Request with descriptive error
- [ ] GET /api/v1/gpus?manufacturer=RADEON (uppercase) normalizes to lowercase and returns Radeon GPUs
- [ ] API response includes full GPU data: id, model, manufacturer, retailPrice, usedPrice, valueScore, specUrl
- [ ] API response includes metadata: count, lastUpdated, cacheExpiresAt
- [ ] Redis caches responses with 5-minute TTL per manufacturer (separate keys: `gpus:manufacturer:radeon`, `gpus:manufacturer:nvidia`)
- [ ] Second identical request within 5 minutes returns cached response (cache hit)
- [ ] Cache hit responses complete in <100ms
- [ ] Cache miss responses complete in <500ms
- [ ] Mode switch updates all dashboard data: retail prices, used prices, value visualization, OEM links
- [ ] Loading indicator appears only if API response takes longer than 200ms
- [ ] Toggle remains enabled during data fetching (user can toggle again to cancel in-flight request)
- [ ] Rapid toggling (Radeon → Nvidia → Radeon) cancels intermediate requests and renders only the final selection
- [ ] If API call fails, error message displays: "Unable to load [manufacturer] data. Please check your connection."
- [ ] Failed API calls auto-retry 3 times with exponential backoff (1s, 2s, 4s delays)
- [ ] After 3 failed retries, error message persists but toggle remains enabled
- [ ] If user toggles mode during error state, error dismisses and new request starts
- [ ] Visual feedback indicates which mode is currently active (e.g., bold text, highlighted background)
- [ ] If localStorage is unavailable (privacy mode), mode selection works within session but does not persist across reloads
- [ ] If localStorage contains invalid value (e.g., `"intel"`), application ignores it and defaults to Radeon
- [ ] If database contains zero GPUs for a manufacturer, API returns 404 with message: "No GPU data available for manufacturer 'radeon'."
- [ ] Admin can manually invalidate cache via POST /api/admin/cache/invalidate (requires authentication and Admin role)
- [ ] Manual cache invalidation only affects the specified manufacturer's cache, not the opposite manufacturer

---

## Security Requirements

- Passwords must be hashed using bcrypt (min cost factor 12) — **inherited from foundation spec, not specific to this feature**
- JWT tokens expire after 24 hours — **inherited from foundation spec**
- Rate limit: max 100 requests per IP per minute for GET /api/v1/gpus — prevents abuse of public endpoint
- Admin cache invalidation endpoint requires authentication and Admin role authorization
- Manufacturer query parameter is validated and normalized before use in database queries — prevents SQL injection via parameterized queries (Entity Framework Core handles this automatically)
- Redis cache keys are deterministic and non-user-controlled — prevents cache poisoning attacks

---

## Not In This Document

This document does not contain:
- Implementation code — write the code yourself based on the contracts above
- Test case definitions — see the QA spec for test plans
- "All Manufacturers" mode — explicitly out of scope; cross-manufacturer comparison is not valuable
- Intel Arc support — future feature; database CHECK constraint can be updated via migration when needed
- URL-based mode selection (e.g., `/dashboard?manufacturer=nvidia`) — mode is client-side state only, not reflected in URL
- Server-side user preference storage — mode is persisted only in browser localStorage, not in database
- Real-time price updates via WebSocket or SSE — data freshness is cache-TTL based (5 minutes)
- Analytics tracking of mode switching behavior — could be added in future iteration
- Keyboard shortcuts for toggling modes — standard tab navigation is supported, but no custom hotkeys
- Email notifications — not applicable to this feature

---

## Implementation Notes

### Database Migration

**Migration**: Add `manufacturer` column to `gpus` table

**Steps**:
1. Add column with default value to support existing rows:
   ```sql
   ALTER TABLE gpus 
   ADD COLUMN manufacturer VARCHAR(50) NOT NULL DEFAULT 'radeon';
   ```

2. Backfill existing rows based on model naming patterns:
   ```sql
   UPDATE gpus 
   SET manufacturer = 'nvidia' 
   WHERE model LIKE 'RTX %' OR model LIKE 'GTX %';

   UPDATE gpus 
   SET manufacturer = 'radeon' 
   WHERE model LIKE 'RX %' OR model LIKE 'Radeon %';
   ```

3. Add CHECK constraint after backfill:
   ```sql
   ALTER TABLE gpus 
   ADD CONSTRAINT chk_manufacturer CHECK (manufacturer IN ('radeon', 'nvidia'));
   ```

4. Create index for query performance:
   ```sql
   CREATE INDEX idx_gpus_manufacturer ON gpus(manufacturer);
   ```

**Rollback Strategy**:
- Drop index: `DROP INDEX idx_gpus_manufacturer;`
- Drop constraint: `ALTER TABLE gpus DROP CONSTRAINT chk_manufacturer;`
- Drop column: `ALTER TABLE gpus DROP COLUMN manufacturer;`

---

### Frontend localStorage Contract

**localStorage key**: `preferredManufacturer`

**Valid values**: `"radeon"` or `"nvidia"` (lowercase string)

**Behavior**:
- On page load, read localStorage value
- If value is `"radeon"` or `"nvidia"`, use it to initialize React state
- If value is missing or invalid, default to `"radeon"` and overwrite localStorage on next toggle
- On mode toggle, immediately update localStorage before making API call

**localStorage unavailable**:
- If localStorage access throws exception (privacy mode, browser restriction), continue without persistence
- Mode selection still works within the session (React state), but does not persist across reloads
- No error message shown to user—graceful degradation

---

### TanStack Query Configuration

**Query key structure**: `['gpus', manufacturer]`

**Example keys**:
- `['gpus', 'radeon']`
- `['gpus', 'nvidia']`

**Configuration**:
- `staleTime`: 300,000 ms (5 minutes) — data is considered fresh for 5 minutes
- `cacheTime`: 600,000 ms (10 minutes) — cache persists 10 minutes even if unused
- `retry`: 3 — auto-retry failed requests 3 times
- `retryDelay`: Exponential backoff `(attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000)`
  - Retry 1: 1 second delay
  - Retry 2: 2 second delay
  - Retry 3: 4 second delay
  - Retry 4: 8 second delay (capped at 30 seconds, but only 3 retries configured)

**Request cancellation**:
- Pass `AbortSignal` from query function to fetch call
- TanStack Query automatically cancels in-flight requests when query key changes (user toggles mode)

---

### Loading Indicator Timing

**Delay**: 200ms before showing loading indicator

**Implementation**:
- Use `setTimeout` to delay showing loading skeleton
- If response completes before 200ms, clear timeout and skip loading state
- If response takes >200ms, loading skeleton appears and remains until response completes

**Loading skeleton**:
- Show placeholder cards in the same layout as GPU cards
- Prevents layout shift when data loads
- Loading skeleton replaces visualization area content, not the mode toggle itself

---

### Redis Cache Keys

**Key format**: `gpus:manufacturer:{manufacturer}`

**Examples**:
- `gpus:manufacturer:radeon`
- `gpus:manufacturer:nvidia`

**TTL**: 300 seconds (5 minutes)

**Value**: Serialized JSON response (full `GpuListResponse` object)

**Cache invalidation**:
- Automatic: TTL expiry after 5 minutes
- Manual: Admin endpoint `POST /api/admin/cache/invalidate` with `{ "manufacturer": "radeon" }`

**Cache miss behavior**:
1. Query database with Entity Framework Core
2. Serialize result to JSON
3. Store in Redis with 5-minute TTL
4. Return response to client

**Cache hit behavior**:
1. Retrieve cached JSON from Redis
2. Return directly to client (no deserialization/reserialization needed)

---

### Error Messages

| Scenario | Error Message |
|----------|---------------|
| Missing manufacturer param | "Query parameter 'manufacturer' is required." |
| Invalid manufacturer value | "Invalid manufacturer. Must be 'radeon' or 'nvidia'." |
| No GPUs for manufacturer | "No GPU data available for manufacturer 'radeon'." |
| Network error (shown after retries) | "Unable to load Radeon data. Please check your connection." |
| API timeout | "Request timed out. Please try again." |
| Server error (500) | "An error occurred processing your request. Please try again later." |

---

### Edge Cases

**localStorage unavailable**:
- Catch exceptions when accessing localStorage
- Continue with session-only state (React state)
- Do not show error to user

**Invalid localStorage value**:
- If value is not `"radeon"` or `"nvidia"`, treat as missing
- Default to `"radeon"`
- Overwrite invalid value on next toggle

**Zero GPUs for manufacturer**:
- API returns 404 status
- Frontend shows empty state message: "No Radeon data available right now. Check back soon or try Nvidia."
- Toggle remains enabled

**API failure after retries**:
- Show error message with "Retry" button
- Keep previous mode's data visible if available (don't clear visualization)
- Toggle remains enabled (user can switch to other manufacturer)

**Rapid toggling**:
- User toggles Radeon → Nvidia → Radeon in quick succession
- TanStack Query cancels first two requests
- Only the final request (Radeon) completes and renders
- No race conditions—query key ensures correct data is rendered

**Concurrent tabs**:
- Each browser tab manages its own TanStack Query cache
- No synchronization across tabs (acceptable for v1)
- Each tab reads/writes localStorage independently (last write wins)

---

## Test Scenarios

### Unit Tests

**API Controller**:
- Valid manufacturer query param returns 200 with GPU list
- Missing manufacturer query param returns 400 with error message
- Invalid manufacturer query param returns 400 with error message
- Case-insensitive manufacturer param normalizes correctly (`RADEON` → `radeon`)
- Redis cache hit returns cached data without database query
- Redis cache miss queries database and caches result
- Zero GPUs for manufacturer returns 404 with error message

**Service Layer**:
- GetByManufacturerAsync filters GPUs correctly by manufacturer enum
- Result includes nested retailPrice and usedPrice data
- Result is ordered by valueScore descending

### Integration Tests

**Database**:
- Migration adds manufacturer column with default value
- CHECK constraint rejects invalid manufacturer values
- Index on manufacturer improves query performance (verify execution plan)

**API**:
- GET /api/v1/gpus?manufacturer=radeon returns only Radeon GPUs
- GET /api/v1/gpus?manufacturer=nvidia returns only Nvidia GPUs
- Response includes all required fields (id, model, manufacturer, retailPrice, usedPrice, valueScore, specUrl, metadata)
- Response metadata includes count, lastUpdated, cacheExpiresAt

**Redis Caching**:
- First request stores result in Redis with 5-minute TTL
- Second request within 5 minutes returns cached result
- Request after 5 minutes triggers cache miss and re-queries database

### Frontend Tests

**Component**:
- Toggle renders with Radeon selected by default
- Clicking Nvidia toggle updates React state and localStorage
- localStorage value persists across component remount

**TanStack Query**:
- Initial query fetches Radeon data
- Toggling to Nvidia cancels Radeon query and fetches Nvidia data
- Query retries 3 times on network error
- Loading indicator shows only after 200ms delay

### E2E Tests (Playwright)

**User Flow**:
- User lands on dashboard → Radeon mode active by default
- User clicks Nvidia toggle → Visualization updates to show Nvidia GPUs
- User reloads page → Nvidia mode persists (localStorage)
- User clicks Radeon toggle → Visualization updates to show Radeon GPUs
- User opens new tab → Radeon mode active (no localStorage value yet in new tab)

**Error Handling**:
- Disconnect network → Error message shows after retries
- Reconnect network → User clicks Retry → Data loads successfully

---

**This specification is complete and ready for implementation.**