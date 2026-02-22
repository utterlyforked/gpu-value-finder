# Radeon vs Nvidia Mode Switching - Feature Requirements (v1.1)

**Version History**:
- v1.0 - Initial specification (2025-01-10)
- v1.1 - Iteration 1 clarifications (2025-01-10) - Added: data model decisions, API structure, loading behavior, error handling patterns, caching strategy

---

## Feature Overview

The Radeon vs Nvidia Mode Switching feature allows users to toggle between viewing AMD Radeon GPU data and Nvidia GPU data. Since cross-manufacturer comparisons are not useful (different architectures, different performance characteristics, different ecosystems), users focus on one manufacturer at a time.

This feature is fundamental to the user experience—it determines what data is visible across the entire dashboard. When a user switches modes, all pricing data (retail and used), all visualizations, and all displayed GPU models update to show only the selected manufacturer's products.

The toggle is prominent, always accessible, and the user's preference persists across sessions so they don't have to re-select their preferred manufacturer every time they visit.

**Why it matters**: PC builders are typically loyal to one GPU ecosystem (Radeon or Nvidia) due to driver preferences, software compatibility, or brand loyalty. Mixing both manufacturers in one view creates noise and makes value comparisons meaningless since a Radeon 7900 XTX and an Nvidia RTX 4080 serve different users with different needs.

---

## User Stories

- As a Radeon user, I want to view only AMD cards so that I'm not distracted by Nvidia pricing
- As an Nvidia user, I want to view only Nvidia cards so that I can focus on my preferred ecosystem
- As a user exploring both options, I want to easily toggle between Radeon and Nvidia views so that I can compare the value landscape in each ecosystem
- As a returning user, I want my manufacturer preference remembered so that I don't have to re-select it on every visit

---

## Acceptance Criteria (UPDATED v1.1)

- Clear UI toggle between "Radeon" and "Nvidia" modes is present (segmented control or tab interface)
- Only one manufacturer's data is displayed at a time—Radeon and Nvidia data are never mixed in the visualization
- User's selection persists across page reloads using browser localStorage (key: `preferredManufacturer`, value: `"radeon"` or `"nvidia"`)
- Mode selection control is prominent and positioned above-the-fold (visible without scrolling)
- Default mode on first visit is Radeon
- All dashboard data updates immediately when user toggles mode: retail prices, used prices, value visualization, and OEM spec links all refresh to show only the selected manufacturer
- Mode switch is instant with 200ms delay before showing loading indicator (avoids flicker on fast responses)
- Visual feedback indicates which mode is currently active (e.g., active tab styling, toggle position)
- Toggle remains enabled during data fetching; toggling again cancels in-flight request and fetches new mode
- API returns full GPU data structure in single call: `GET /api/v1/gpus?manufacturer=radeon`
- Manufacturer values stored and transmitted in lowercase (`"radeon"`, `"nvidia"`)
- API responses cached with 5-minute TTL per manufacturer
- Failed API calls auto-retry 3 times with exponential backoff; if user toggles during retry, cancel and fetch new mode

---

## Detailed Specifications (UPDATED v1.1)

### Data Model: Manufacturer Field

**Decision**: Store manufacturer as `VARCHAR(50)` with database CHECK constraint, values in lowercase

**Rationale**: 
- Balances type safety with extensibility—when Intel Arc is added later, it's a simple `ALTER TABLE` statement to add `'intel'` to the constraint
- Lowercase convention is modern API standard and produces clean URLs (`?manufacturer=radeon`)
- Database CHECK constraint prevents invalid data while remaining flexible
- Application layer uses C# enum for type safety, but database isn't locked into PostgreSQL ENUM type

**Schema**:
```sql
CREATE TABLE gpus (
  id UUID PRIMARY KEY,
  model VARCHAR(100) NOT NULL,
  manufacturer VARCHAR(50) NOT NULL CHECK (manufacturer IN ('radeon', 'nvidia')),
  -- other fields
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_gpus_manufacturer ON gpus(manufacturer);
```

**C# Model**:
```csharp
public enum ManufacturerType 
{
    Radeon,
    Nvidia
}

public class Gpu 
{
    public Guid Id { get; set; }
    public string Model { get; set; } = string.Empty;
    public ManufacturerType Manufacturer { get; set; }
    // Entity Framework converts enum to lowercase string
}
```

**API Convention**:
- Request: `GET /api/v1/gpus?manufacturer=radeon`
- Response: `{ "manufacturer": "radeon", "gpus": [...] }`
- localStorage: `{ "preferredManufacturer": "radeon" }`
- All comparisons case-insensitive in API layer: `manufacturer.ToLowerInvariant()`

**Edge Cases**:
- Invalid manufacturer in query param → Return 400 Bad Request: `{ "error": "Invalid manufacturer. Must be 'radeon' or 'nvidia'." }`
- Case variations (`Radeon`, `RADEON`) → Normalized to lowercase in API controller before query
- localStorage contains invalid value → Frontend defaults to `"radeon"` and overwrites localStorage

---

### API Response Structure

**Decision**: Single endpoint returns full GPU data including retail prices, used prices, and value scores

**Rationale**:
- Simplifies frontend logic—one API call populates entire dashboard
- Reduces network overhead compared to multiple sequential requests
- TanStack Query caches full response, so subsequent mode switches can use cached data
- Performance is acceptable for MVP (typical response: 15-30 GPUs with ~2KB per GPU = ~60KB total)

**Endpoint**: `GET /api/v1/gpus?manufacturer={manufacturer}`

**Response Schema**:
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

**Performance Optimization**:
- Backend caches response in Redis with 5-minute TTL (key: `gpus:manufacturer:{manufacturer}`)
- Frontend caches with TanStack Query (stale time: 5 minutes, cache time: 10 minutes)
- If Redis cache hit, response time ~50ms; if cache miss, ~300ms (database query + aggregation)

---

### Mode Toggle Interaction Behavior

**Decision**: Toggle remains enabled during data fetching, new toggle cancels previous request

**Rationale**:
- Users expect responsive UI—disabling toggle feels sluggish, especially on slow networks
- Rapid toggling (Radeon → Nvidia → Radeon) should use last selection, not queue requests
- TanStack Query handles request cancellation automatically via AbortController
- Prevents race conditions where stale data overwrites fresh data

**Behavior**:
1. User clicks "Nvidia" toggle
2. Frontend updates localStorage immediately: `preferredManufacturer = "nvidia"`
3. Frontend updates React state: `setSelectedManufacturer("nvidia")`
4. TanStack Query starts fetching: `GET /api/v1/gpus?manufacturer=nvidia`
5. If user clicks "Radeon" toggle before response arrives:
   - Previous request is cancelled (AbortController aborts fetch)
   - New request starts: `GET /api/v1/gpus?manufacturer=radeon`
   - localStorage updates to `"radeon"`
6. Only the last-initiated request's data is rendered

**Implementation (React + TanStack Query)**:
```typescript
const { data, isLoading, error } = useQuery({
  queryKey: ['gpus', selectedManufacturer],
  queryFn: ({ signal }) => fetchGpus(selectedManufacturer, signal),
  staleTime: 5 * 60 * 1000, // 5 minutes
  retry: 3,
  retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000)
});
```

**Visual Feedback**:
- Toggle is always clickable (no disabled state)
- Active mode is visually distinct (bold text, highlighted background)
- Loading indicator appears on visualization area, not on toggle itself

---

### Loading State Timing

**Decision**: Show loading indicator only if API response takes longer than 200ms

**Rationale**:
- Most responses (cache hits) complete in <200ms—showing/hiding loading state creates distracting flicker
- 200ms is below human perception threshold for "instantaneous" (Jakob Nielsen: users perceive <100ms as instant, <1s as continuous)
- If response takes >200ms, loading indicator provides feedback that system is working
- Prevents "dead click" feeling where user clicks and nothing appears to happen

**Implementation**:
```typescript
const [showLoading, setShowLoading] = useState(false);

useEffect(() => {
  let timer: NodeJS.Timeout;
  
  if (isLoading) {
    timer = setTimeout(() => setShowLoading(true), 200);
  } else {
    setShowLoading(false);
  }
  
  return () => clearTimeout(timer);
}, [isLoading]);
```

**User Experience**:
- Fast response (<200ms): Mode switches instantly, no loading indicator
- Slow response (>200ms): Loading skeleton appears over visualization area after 200ms delay
- Very slow response (>3s): Loading indicator remains visible, user can toggle to different mode

**Loading Skeleton**: Shows placeholder cards in visualization area matching the layout of GPU cards (prevents layout shift when data loads)

---

### Error Handling and Retry Logic

**Decision**: Auto-retry failed requests 3 times with exponential backoff; new toggle dismisses error and fetches new mode

**Rationale**:
- Transient network errors (WiFi hiccup, temporary API unavailability) shouldn't require user intervention
- Exponential backoff prevents hammering failing API (1s, 2s, 4s delays)
- If user toggles during error state, it signals they want to try something else—dismiss error and fetch new mode
- After 3 failed retries, show error message but keep UI responsive

**Retry Schedule**:
- Attempt 1: Immediate
- Attempt 2: 1 second delay
- Attempt 3: 2 seconds delay
- Attempt 4: 4 seconds delay
- After 4th failure: Show error, stop retrying

**Error Display**:
```
⚠️ Unable to load Nvidia data. Please check your connection.
[Retry] [Switch to Radeon]
```

**Behavior During Error**:
- Toggle remains enabled
- If user clicks toggle to switch to other manufacturer:
  - Error message dismisses immediately
  - New request starts (with fresh retry counter)
- If user clicks "Retry" button:
  - Same manufacturer request retries (resets retry counter)
- Previous mode's data remains visible during error state (don't show empty state)

**Error Response Handling**:
- 400 Bad Request (invalid manufacturer) → Show error: "Invalid selection. Please try again."
- 404 Not Found → Show error: "No data available for this manufacturer."
- 500 Internal Server Error → Auto-retry (transient failure)
- Network timeout → Auto-retry (transient failure)

---

### Caching Strategy

**Decision**: Redis cache on backend (5-minute TTL per manufacturer), TanStack Query cache on frontend (5-minute stale time)

**Rationale**:
- GPU prices don't change minute-by-minute—5-minute freshness is acceptable trade-off for performance
- Dual-layer caching: Redis reduces database load, TanStack Query reduces network requests
- When user toggles back to previously viewed manufacturer within 5 minutes, data loads instantly from cache
- Cache keys are separate per manufacturer so toggling doesn't invalidate opposite mode's cache

**Backend Caching (Redis)**:
- Key: `gpus:manufacturer:radeon` and `gpus:manufacturer:nvidia`
- TTL: 5 minutes (300 seconds)
- Value: Serialized JSON response
- Cache invalidation: Manual (admin trigger) or TTL expiry
- On cache miss: Query database, serialize, store in Redis, return to client

**Frontend Caching (TanStack Query)**:
- Query key: `['gpus', 'radeon']` and `['gpus', 'nvidia']`
- Stale time: 5 minutes (data considered fresh for 5 min)
- Cache time: 10 minutes (cache persists 10 min even if unused)
- On cache hit within stale time: Instant render, no network request
- On cache hit after stale time: Render cached data, refetch in background

**Cache Performance**:
- Cold start (no cache): ~300ms response time
- Redis cache hit: ~50ms response time
- TanStack Query cache hit: 0ms (instant render)
- User toggles Radeon → Nvidia → Radeon within 5 min: All data loads instantly

**Cache Freshness Indicator**:
- Response includes `metadata.lastUpdated` timestamp
- UI shows "Data as of 10:30 AM" in subtle text below visualization
- User can force refresh by clicking "Refresh" button (invalidates cache, fetches fresh data)

---

### URL State Handling

**Decision**: Mode is NOT reflected in URL (no query parameter, no route change)

**Rationale**:
- This is a deliberate product decision (stated in spec's "Out of Scope")
- Mode is pure client-side filter, not a navigation action
- Browser back button does NOT switch modes (may confuse users initially, but simpler implementation for v1)
- Links are not shareable with specific mode (acceptable trade-off for MVP)

**Behavior**:
- URL remains `/dashboard` regardless of mode
- Browser back button navigates to previous page, not previous mode
- If user shares link, recipient sees default mode (Radeon) unless they have localStorage preference

**Future Consideration (v2)**:
- Could add URL query param: `/dashboard?manufacturer=nvidia`
- Benefits: Shareable links, back button switches modes (standard web UX)
- Trade-offs: Slightly more complex state management (sync URL ↔ localStorage ↔ React state)
- Recommendation: Revisit after v1 user feedback—if users complain about back button not switching modes, add URL state

---

## Data Model (Initial Thoughts)

**No new entities required**—this feature filters existing GPU data by manufacturer.

**GPU Entity** (already exists):
- `manufacturer` field: `VARCHAR(50)` with CHECK constraint (`'radeon'` or `'nvidia'`)
- Indexed for fast filtering: `CREATE INDEX idx_gpus_manufacturer ON gpus(manufacturer);`
- All queries for retail prices, used prices, and visualization data filter by this field

**Frontend State**:
- `selectedManufacturer`: `"radeon" | "nvidia"` (React state)
- Initialized from localStorage on mount
- Passed to TanStack Query as part of query key

**localStorage Schema**:
```json
{
  "preferredManufacturer": "radeon"
}
```

**Backend Query**:
```csharp
var gpus = await _context.Gpus
    .Where(g => g.Manufacturer == manufacturerEnum)
    .Include(g => g.RetailPrices)
    .Include(g => g.UsedPrices)
    .OrderByDescending(g => g.ValueScore)
    .ToListAsync(cancellationToken);
```

---

## User Experience Flow

### First Visit

1. User lands on dashboard
2. Application checks `localStorage.preferredManufacturer` → returns `null` (first visit)
3. Application defaults to Radeon mode
4. TanStack Query fetches: `GET /api/v1/gpus?manufacturer=radeon`
5. Backend checks Redis cache → cache miss (cold start)
6. Backend queries database, caches result in Redis (5-min TTL), returns response
7. Dashboard displays Radeon retail prices, used prices, value visualization (~300ms total)
8. Mode toggle shows "Radeon" as active, "Nvidia" as inactive

### Switching Modes (Fast Path - Cache Hit)

1. User clicks "Nvidia" toggle
2. Frontend updates localStorage: `preferredManufacturer = "nvidia"`
3. Frontend sets `selectedManufacturer` state to `"nvidia"`
4. TanStack Query checks cache → cache miss (first time viewing Nvidia)
5. API request sent: `GET /api/v1/gpus?manufacturer=nvidia`
6. Backend checks Redis cache → cache hit (another user fetched Nvidia data 2 min ago)
7. Backend returns cached response (~50ms)
8. Dashboard re-renders with Nvidia prices and visualization
9. No loading indicator shown (response took <200ms)

### Switching Modes (Slow Path - Cache Miss)

1. User clicks "Radeon" toggle
2. Frontend updates localStorage: `preferredManufacturer = "radeon"`
3. Frontend sets `selectedManufacturer` state to `"radeon"`
4. TanStack Query starts fetch: `GET /api/v1/gpus?manufacturer=radeon`
5. 200ms passes → Loading skeleton appears over visualization area
6. Backend checks Redis → cache expired (>5 min since last fetch)
7. Backend queries database, caches result (~300ms)
8. Response returns, dashboard re-renders
9. Loading skeleton disappears, data visible

### Returning User

1. User lands on dashboard
2. Application checks `localStorage.preferredManufacturer` → returns `"nvidia"`
3. Application sets mode to Nvidia automatically (no Radeon data fetched)
4. TanStack Query checks cache → cache hit (user visited 2 min ago, stale time not expired)
5. Dashboard renders instantly with cached Nvidia data (0ms)
6. TanStack Query validates cache freshness → still within 5-min stale time, no background refetch
7. User sees their preferred manufacturer immediately

### Rapid Toggling

1. User clicks "Nvidia" toggle
2. Request starts: `GET /api/v1/gpus?manufacturer=nvidia`
3. User immediately clicks "Radeon" toggle (changes mind)
4. TanStack Query cancels Nvidia request via AbortController
5. New request starts: `GET /api/v1/gpus?manufacturer=radeon`
6. Only Radeon data renders (Nvidia request never completes)

---

## Edge Cases & Constraints

- **localStorage unavailable**: If localStorage is blocked (privacy mode, browser settings), application defaults to Radeon mode on every visit. No error shown to user; feature degrades gracefully. Mode toggles still work within session (React state).

- **Invalid localStorage value**: If `localStorage.preferredManufacturer` contains invalid value (e.g., `"intel"` due to manual editing), application ignores it, defaults to `"radeon"`, and overwrites localStorage with valid value on first toggle.

- **API failure during mode switch**: If API call fails after 3 retries, show error message: "Unable to load Nvidia data. Please check your connection." Previous mode's data remains visible (don't clear visualization). User can click "Retry" or toggle to other manufacturer.

- **Slow API response**: If response takes >200ms, loading skeleton appears over visualization area. Mode toggle remains enabled—user can toggle back if they change their mind, cancelling the slow request.

- **No data for selected manufacturer**: If API returns `gpus: []` (zero GPUs for selected manufacturer—unlikely but possible if scraping fails), show empty state message: "No Radeon data available right now. Check back soon or try Nvidia." Toggle remains enabled.

- **Initial page load with saved preference**: On page load, don't show Radeon mode first and then switch to Nvidia—read localStorage synchronously before first render and initialize React state with correct mode. First API call fetches correct manufacturer.

- **Stale cache during rapid price changes**: If GPU prices change while Redis cache is still valid (<5 min), users see stale prices. Acceptable trade-off for MVP—prices don't fluctuate minute-by-minute. Admin can manually invalidate cache if major price update occurs.

- **Network timeout**: If request takes >30 seconds, TanStack Query aborts and retries. After 3 retries (total ~60 sec), show error. User can retry or switch modes.

- **Concurrent requests from multiple tabs**: If user has dashboard open in two tabs and toggles mode in both simultaneously, each tab manages its own TanStack Query cache. No synchronization across tabs in v1 (acceptable—rare scenario).

---

## Out of Scope for This Feature

This feature explicitly does NOT include:

- **"All Manufacturers" mode**: No option to view Radeon and Nvidia simultaneously. Cross-manufacturer comparison is not valuable and is intentionally excluded.

- **Intel Arc support**: Only Radeon and Nvidia in v1. If Intel Arc is added later, mode toggle becomes three-way, but that's a future feature (database schema supports it via CHECK constraint update).

- **User accounts with saved preferences**: localStorage only. No server-side preference storage or user accounts in v1.

- **URL-based mode selection**: Mode is not reflected in URL (e.g., no `/dashboard?manufacturer=nvidia`). This is a client-side filter, not a navigation state. Could add in v2 for shareable links.

- **Analytics on mode switching**: No tracking of which mode users prefer or how often they switch. Could add in v2 if product wants usage data (e.g., Mixpanel event on toggle).

- **Keyboard shortcuts**: No hotkeys (e.g., "R" for Radeon, "N" for Nvidia). Mode toggle is keyboard-accessible via tab navigation and Enter key, but no custom shortcuts in v1.

- **Real-time price updates**: No WebSocket or SSE for live price changes. Data freshness is cache-TTL based (5 minutes). Users can manually refresh if needed.

- **Custom cache invalidation per user**: All users share same 5-minute cache window. No per-user cache control (e.g., "Show me fresh data"). Could add in v2 with "Force Refresh" button.

---

## Q&A History

### Iteration 1 - 2025-01-10

**Q1: How is the manufacturer field stored in the GPU entity?**

**A**: Store as `VARCHAR(50)` with database CHECK constraint: `CHECK (manufacturer IN ('radeon', 'nvidia'))`. Values are lowercase. This balances type safety (constraint prevents invalid data) with extensibility (adding Intel Arc later is just an `ALTER TABLE` statement, not managing PostgreSQL ENUM migrations). Application layer uses C# enum `ManufacturerType` for type safety, with EF Core converting to/from lowercase strings.

---

**Q2: What case format should manufacturer values use in storage and API?**

**A**: Lowercase everywhere: database stores `'radeon'` and `'nvidia'`, API accepts and returns lowercase, localStorage stores lowercase. API layer normalizes input with `manufacturer.ToLowerInvariant()` so case-insensitive comparisons work. This is modern API convention and produces clean URLs (`?manufacturer=radeon`).

---

**Q3: What exact HTTP response should the API return when switching modes?**

**A**: Single endpoint returns full GPU list with all related data:

```json
{
  "manufacturer": "radeon",
  "gpus": [
    {
      "id": "uuid",
      "model": "RX 7900 XTX",
      "manufacturer": "radeon",
      "retailPrice": { "amount": 999.99, "currency": "USD", "lastUpdated": "timestamp", "sources": ["newegg"] },
      "usedPrice": { "amount": 849.99, "currency": "USD", "lastUpdated": "timestamp", "source": "ebay" },
      "valueScore": 8.5,
      "specUrl": "https://amd.com/..."
    }
  ],
  "metadata": { "count": 15, "lastUpdated": "timestamp", "cacheExpiresAt": "timestamp" }
}
```

Endpoint: `GET /api/v1/gpus?manufacturer=radeon`. Single call populates entire dashboard. Simpler than multiple endpoints, and response size is acceptable for MVP (~60KB for 15-30 GPUs).

---

**Q4: Should the mode toggle disable during data fetching?**

**A**: No—toggle remains enabled. User can toggle again during fetch, which cancels the in-flight request (via TanStack Query's AbortController) and starts fetching the new mode. This keeps UI responsive and prevents "locked" feeling on slow networks. Race conditions are handled automatically by TanStack Query—only the last-initiated request's data is rendered.

---

**Q5: How long should we wait before showing the loading indicator?**

**A**: 200ms delay. If API responds in <200ms (most cache hits), no loading indicator is shown—mode switches feel instant. If response takes >200ms, loading skeleton appears. This is standard UX pattern (React Suspense uses similar timing) and avoids flicker while still providing feedback for slow responses.

---

**Q6: What happens if user toggles mode while API call is failing/retrying?**

**A**: New toggle dismisses error message and starts fetching the new mode. This keeps UI responsive. TanStack Query also auto-retries failed requests 3 times with exponential backoff (1s, 2s, 4s delays), so transient network errors are handled automatically. If user toggles during auto-retry, the retry is cancelled and new mode is fetched. After 3 failed retries, error message is shown but toggle remains enabled.

---

**Q7: Should mode selection be reflected in the URL?**

**A**: No (as stated in spec's "Out of Scope"). Mode is pure client state—no URL query param, no route change. URL remains `/dashboard` regardless of mode. Browser back button navigates to previous page, not previous mode. Links are not shareable with specific mode. This is a deliberate product decision for v1 simplicity. Recommend revisiting in v2 if users expect back button to switch modes (that's standard web app behavior).

---

**Q8: How fresh does the data need to be when switching modes?**

**A**: 5-minute freshness is acceptable. Backend caches responses in Redis with 5-minute TTL (key: `gpus:manufacturer:radeon`). Frontend caches with TanStack Query (5-minute stale time). GPU prices don't change minute-by-minute, so this trade-off between performance and freshness is reasonable. Cache hit responses are ~50ms vs ~300ms for database queries. If major price update occurs, admin can manually invalidate Redis cache.

---

## Product Rationale

### Why lowercase manufacturer values?

GPU prices are consumer-facing data, and URLs will be visible to users (when shared, debugging, etc.). Lowercase is modern API convention (`?manufacturer=radeon` looks cleaner than `?manufacturer=RADEON`). It also aligns with JSON conventions (lowercase property values are standard). The trade-off is needing case-insensitive comparisons in code, but that's trivial with `ToLowerInvariant()`.

### Why single API endpoint instead of separate calls for prices?

Simplicity for MVP. Multiple endpoints (one for GPUs, one for retail prices, one for used prices) would require frontend orchestration, error handling for partial failures, and more complex loading states. Single endpoint means one loading state, one error state, one cache entry. Performance is acceptable (~60KB response). Can optimize in v2 if needed.

### Why 5-minute cache TTL?

GPU prices update slowly (retailers change prices hours/days apart, not minutes apart). 5-minute caching gives ~95% cache hit rate (users toggle modes, refresh page, etc. within 5 minutes) while keeping data reasonably fresh. Shorter TTL (1 min) would increase database load without meaningful freshness benefit. Longer TTL (15 min) risks stale prices annoying users. 5 minutes is sweet spot.

### Why keep toggle enabled during fetch instead of disabling?

Disabling the toggle punishes users on slow connections—they're stuck waiting for a request they might not even want anymore. Keeping toggle enabled respects user intent: if they toggle again, they're signaling "I changed my mind, cancel that request." TanStack Query handles cancellation automatically. This is standard practice in modern web apps (Twitter/X, Gmail, etc. let you click around during loading).

### Why 200ms delay before showing loading indicator?

Below 200ms, loading state appears and disappears so fast it's distracting (flicker effect). Most cache hits are <200ms, so 200ms delay means most mode switches feel instant. Above 200ms, loading indicator provides feedback that system is working. This is supported by UX research (Jakob Nielsen: <100ms feels instant, <1s feels continuous, >1s needs feedback).

### Why auto-retry 3 times instead of showing error immediately?

Transient network errors (WiFi hiccup, temporary API blip) are common on web. Retrying automatically handles these without user intervention. 3 retries with exponential backoff (1s, 2s, 4s) gives ~8 seconds total before showing error—enough time for transient issues to resolve. After 3 failures, it's likely a persistent problem (API down, user offline), so show error and let user decide next action.

### Why no URL state for mode in v1?

Simplicity. URL state requires syncing three sources of truth: URL query param, localStorage, and React state. It also affects browser history (back button behavior). For v1, keeping mode as pure client state reduces complexity. The trade-off is that links aren't shareable with specific mode and back button doesn't switch modes—acceptable for MVP. User feedback will inform whether v2 needs URL state.

### Why separate Redis cache per manufacturer instead of combined?

Cache invalidation is simpler. If Radeon prices update, invalidate only `gpus:manufacturer:radeon` cache, leaving `gpus:manufacturer:nvidia` intact. This also allows different TTLs per manufacturer in future (e.g., Nvidia prices update more frequently, use shorter TTL). Separate caches also mean toggling between modes doesn't invalidate opposite mode's cache—switching back and forth is fast.

---

## Dependencies

**Depends On**: 
- Feature 1 (Live Retail Price Aggregation) - needs retail price data with manufacturer field
- Feature 2 (Used Market Price Discovery) - needs used price data with manufacturer field
- Feature 3 (Value Visualization Dashboard) - needs visualization that can re-render with filtered data
- Database schema must include `manufacturer VARCHAR(50)` field with CHECK constraint

**Enables**: 
- All other features depend on this mode being set correctly to filter data
- Feature 4 (Manufacturer Reference Links) - OEM links must point to correct manufacturer based on active mode

---

**Note**: This is a foundational feature that affects the entire dashboard. The mode selection determines what data is fetched, displayed, and visualized across all other features. Implementation should happen early in development since other features depend on the `manufacturer` filter being in place.