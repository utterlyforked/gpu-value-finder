# Radeon vs Nvidia Mode Switching - Technical Questions (Iteration 1)

**Status**: NEEDS CLARIFICATION
**Iteration**: 1
**Date**: 2025-01-10

---

## Summary

After reviewing the specification, I've identified **8** areas that need clarification before implementation can begin. These questions address:
- Data model manufacturer field structure
- Mode toggle UI/UX behavior
- Error handling and retry logic
- Loading state thresholds
- URL and navigation behavior
- Data caching and staleness

The spec is quite thorough overall, but these specific decisions will affect core implementation patterns.

---

## CRITICAL Questions

These block core implementation and must be answered first.

### Q1: How is the manufacturer field stored in the GPU entity?

**Context**: The spec mentions GPU entities "must have a `manufacturer` field (enum or string)" but doesn't specify which. This affects:
- Database schema design (ENUM column vs VARCHAR)
- API validation logic (case sensitivity, validation approach)
- Query performance (indexed enum vs string matching)
- Future extensibility (adding Intel Arc or other manufacturers)

**Options**:

- **Option A: Database ENUM type**
  - Impact: PostgreSQL ENUM column with values `'RADEON'`, `'NVIDIA'`
  - Trade-offs: 
    - ✅ Type-safe at DB level, smaller storage, faster queries
    - ❌ Requires migration to add new manufacturers (Intel Arc later)
    - ❌ More rigid, enum management in DB
  - Example: `CREATE TYPE gpu_manufacturer AS ENUM ('RADEON', 'NVIDIA');`
  
- **Option B: VARCHAR with CHECK constraint**
  - Impact: `VARCHAR(50)` with `CHECK (manufacturer IN ('RADEON', 'NVIDIA'))`
  - Trade-offs:
    - ✅ Easier to extend (just alter constraint)
    - ✅ More flexible for future manufacturers
    - ❌ Slightly larger storage, need app-level validation
  - Example: `manufacturer VARCHAR(50) NOT NULL CHECK (manufacturer IN ('RADEON', 'NVIDIA'))`

- **Option C: VARCHAR with application-level validation only**
  - Impact: Simple VARCHAR, validation only in C# with enum
  - Trade-offs:
    - ✅ Maximum flexibility
    - ❌ No database-level constraint (data integrity risk)
    - ❌ Potential for invalid data from manual edits/scripts

**Recommendation for MVP**: **Option B (VARCHAR with CHECK constraint)**. Balances type safety with extensibility. When Intel Arc is added, it's just an ALTER TABLE statement rather than managing PostgreSQL ENUMs. C# layer can still use `enum ManufacturerType` for type safety.

---

### Q2: What case format should manufacturer values use in storage and API?

**Context**: The spec uses both "Radeon" (title case) and "radeon" (lowercase) in different contexts. Need consistency for:
- Database storage
- API request/response format
- localStorage values
- Case-sensitive comparisons

**Options**:

- **Option A: UPPERCASE everywhere**
  - Database: `'RADEON'`, `'NVIDIA'`
  - API: `?manufacturer=RADEON`
  - localStorage: `"RADEON"`
  - Impact: Traditional enum style, no case sensitivity issues
  - Trade-offs: Less readable in URLs, feels "shouty"
  
- **Option B: lowercase everywhere**
  - Database: `'radeon'`, `'nvidia'`
  - API: `?manufacturer=radeon`
  - localStorage: `"radeon"`
  - Impact: Clean URLs, modern API style
  - Trade-offs: Need to ensure case-insensitive comparisons everywhere
  
- **Option C: Database uppercase, API/UI accepts both**
  - Database: `'RADEON'`, `'NVIDIA'`
  - API: Accepts `radeon`, `RADEON`, `Radeon` → normalizes to uppercase
  - localStorage: `"RADEON"`
  - Impact: User-friendly, flexible input
  - Trade-offs: More validation logic, potential confusion

**Recommendation for MVP**: **Option B (lowercase everywhere)**. Simpler, modern API convention. PostgreSQL supports case-insensitive LIKE, and C# enum parsing can handle it with `StringComparison.OrdinalIgnoreCase`. Store and transmit as lowercase for consistency.

---

### Q3: What exact HTTP response should the API return when switching modes?

**Context**: The spec says "API call to fetch data for new manufacturer" but doesn't specify what data structure is returned. This affects:
- Frontend data processing logic
- TypeScript interface definitions
- Whether data is pre-filtered or post-filtered
- Response caching strategy

**Options**:

- **Option A: Return full GPU list with all related data**
  ```json
  {
    "manufacturer": "radeon",
    "gpus": [
      {
        "id": "123",
        "model": "RX 7900 XTX",
        "manufacturer": "radeon",
        "retailPrice": 999.99,
        "usedPrice": 849.99,
        "valueScore": 8.5
      }
    ],
    "metadata": {
      "count": 15,
      "lastUpdated": "2025-01-10T10:30:00Z"
    }
  }
  ```
  - Impact: Single endpoint returns everything needed for dashboard
  - Trade-offs: Larger payload, but simpler frontend logic
  
- **Option B: Return minimal GPU list, separate calls for prices**
  ```json
  {
    "manufacturer": "radeon",
    "gpus": [
      { "id": "123", "model": "RX 7900 XTX" }
    ]
  }
  ```
  - Then: `GET /api/v1/prices/retail?manufacturer=radeon`
  - Then: `GET /api/v1/prices/used?manufacturer=radeon`
  - Impact: Multiple API calls required
  - Trade-offs: Better caching granularity, more complex frontend orchestration

- **Option C: Server-sent events or WebSocket for real-time updates**
  - Impact: Push-based updates when prices change
  - Trade-offs: Overkill for MVP, adds infrastructure complexity

**Recommendation for MVP**: **Option A (full GPU list with related data)**. Single API call keeps frontend simple. Endpoint: `GET /api/v1/gpus?manufacturer=radeon` returns everything needed to render the dashboard. Can optimize with separate endpoints in v2 if needed.

---

### Q4: Should the mode toggle disable during data fetching?

**Context**: The spec mentions "Mode toggle remains interactive" during loading but doesn't specify whether rapid toggling is allowed. This affects:
- Race condition handling (user toggles Radeon → Nvidia → Radeon quickly)
- Request cancellation logic
- UX during slow network conditions

**Options**:

- **Option A: Toggle disabled during fetch**
  - Impact: User cannot switch modes until current request completes
  - Trade-offs:
    - ✅ No race conditions, simpler logic
    - ❌ Feels sluggish on slow connections (could be 2-3 seconds disabled)
    - ❌ User stuck if API is slow
  
- **Option B: Toggle enabled, cancel previous request**
  - Impact: User can toggle freely, each toggle cancels in-flight request
  - Trade-offs:
    - ✅ Responsive, user always in control
    - ✅ Uses AbortController to cancel stale requests
    - ❌ More complex, need to handle cancellation errors
    - Example: TanStack Query handles this automatically
  
- **Option C: Toggle enabled, queue requests**
  - Impact: Rapid toggles queue up, execute in order
  - Trade-offs:
    - ❌ Confusing UX (user sees delayed mode switches)
    - ❌ Wastes API calls

**Recommendation for MVP**: **Option B (enable toggle, cancel previous request)**. TanStack Query handles request cancellation automatically via AbortController. User can change mind mid-fetch without waiting. This is standard practice for modern React apps.

---

## HIGH Priority Questions

These affect major workflows but have reasonable defaults.

### Q5: How long should we wait before showing the loading indicator?

**Context**: The spec asks "If API responds in <200ms, should we skip loading state to avoid flicker?" This affects perceived performance and UX smoothness.

**Options**:

- **Option A: Show loading immediately (0ms delay)**
  - Impact: Loading state always visible, even for fast responses
  - Trade-offs:
    - ✅ User always knows something is happening
    - ❌ Flicker on fast connections (skeleton appears and disappears quickly)
  
- **Option B: 200ms delay before showing loading state**
  - Impact: If API responds within 200ms, no loading state shown
  - Trade-offs:
    - ✅ Smooth experience on fast connections (most cases)
    - ✅ Still shows loading for slow responses
    - ❌ 200-250ms feels like brief "hang" if response is just over threshold
  
- **Option C: 500ms delay before showing loading state**
  - Impact: Only show loading for truly slow responses
  - Trade-offs:
    - ✅ Very smooth for most users
    - ❌ User might click toggle multiple times thinking it didn't work

**Recommendation for MVP**: **Option B (200ms delay)**. This is a common UX pattern (React Suspense uses similar timing). Most API responses should be under 200ms with proper caching, so users see instant mode switches. Slower responses get a loading indicator so users know the app is working.

---

### Q6: What happens if user toggles mode while API call is failing/retrying?

**Context**: The spec says "If API call fails when switching modes, show error message and keep previous mode active. User can retry toggle." But what if the user toggles *again* before resolving the error?

**Options**:

- **Option A: Error state blocks toggling**
  - Impact: User must dismiss error (or wait for timeout) before toggling again
  - Trade-offs:
    - ✅ Clear error handling, user acknowledges failure
    - ❌ Blocks user from trying different mode
  
- **Option B: New toggle dismisses error and tries new mode**
  - Impact: Error disappears when user clicks toggle, new request starts
  - Trade-offs:
    - ✅ User can immediately try different manufacturer
    - ✅ Non-blocking error handling
    - ❌ Error might disappear before user reads it
  
- **Option C: Automatic retry with exponential backoff**
  - Impact: Failed request auto-retries 2-3 times before showing error
  - Trade-offs:
    - ✅ Handles transient network issues automatically
    - ❌ Delays error visibility for persistent failures

**Recommendation for MVP**: **Option B (new toggle dismisses error)**. Keep UI responsive. TanStack Query can be configured for Option C's auto-retry as well (default is 3 retries), combining both approaches: auto-retry transient failures, but if user toggles during retry, cancel and fetch new mode.

---

## MEDIUM Priority Questions

Edge cases and polish items - can have sensible defaults if needed.

### Q7: Should mode selection be reflected in the URL?

**Context**: The spec explicitly says "Mode is not reflected in URL... Could add in v2 for shareable links." But this affects:
- Browser back button behavior (does back button switch modes?)
- Shareable links (can user share "Nvidia mode" view?)
- Analytics (tracking mode preference via URL params)

**Options**:

- **Option A: No URL state (as spec suggests)**
  - Impact: Mode is pure client state (localStorage only)
  - Trade-offs:
    - ✅ Simpler implementation
    - ❌ Back button doesn't switch modes (might confuse users)
    - ❌ Can't share specific mode via link
  
- **Option B: URL query param reflects mode**
  - Example: `/dashboard?mode=nvidia`
  - Impact: URL updates when mode toggles
  - Trade-offs:
    - ✅ Shareable links work
    - ✅ Back button switches modes (standard web behavior)
    - ❌ Slightly more complex (need URL state management)

**Recommendation for MVP**: **Option A (no URL state)** as spec suggests. This is a deliberate product decision. However, recommend revisiting in v2 because users may expect back button to switch modes (that's standard web app behavior).

---

### Q8: How fresh does the data need to be when switching modes?

**Context**: The spec asks "Should API responses for Radeon and Nvidia be cached separately in Redis? If user toggles back and forth, should we serve cached data or always fetch fresh?" This affects performance vs data freshness trade-off.

**Options**:

- **Option A: No caching, always fetch fresh**
  - Impact: Every mode toggle hits database
  - Trade-offs:
    - ✅ Always fresh data (prices are current)
    - ❌ Slower mode switching
    - ❌ Higher database load
  
- **Option B: Cache with 5-minute TTL**
  - Impact: Redis cache per manufacturer, 5-minute expiry
  - Trade-offs:
    - ✅ Fast mode switching (serves from cache)
    - ✅ Reasonable freshness (prices update every 5 min)
    - ❌ User might see stale prices briefly
  
- **Option C: Cache with stale-while-revalidate**
  - Impact: Serve cached data immediately, fetch fresh in background
  - Trade-offs:
    - ✅ Instant mode switching (no loading state)
    - ✅ Data updates in background
    - ❌ User sees stale data first (might be confusing)

**Recommendation for MVP**: **Option B (5-minute cache TTL)**. GPU prices don't change minute-by-minute. Caching with 5-minute TTL gives instant mode switching for most users while keeping data reasonably fresh. TanStack Query on frontend can implement client-side caching, Redis on backend can cache DB query results. This is a reasonable default that can be tuned based on real usage patterns.

---

## Notes for Product

- The spec is well-detailed overall—excellent work defining user flows and edge cases
- Most questions are about specific implementation boundaries (case sensitivity, caching TTLs) that affect technical implementation but need product input on user experience trade-offs
- The "no URL state" decision is clear in the spec, but flagging Q7 because it conflicts with standard web UX patterns—worth discussing
- Once these questions are answered (especially Q1-Q4), implementation can proceed with confidence
- Happy to do another iteration if these answers raise new questions

---

**Next Steps**: Please review prioritization (Critical/High/Medium) and confirm if that matches product's urgency. Critical questions (Q1-Q4) must be answered before work begins.