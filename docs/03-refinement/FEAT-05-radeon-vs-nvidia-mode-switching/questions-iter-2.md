# Radeon vs Nvidia Mode Switching - Technical Review (Iteration 2)

**Status**: ✅ READY FOR IMPLEMENTATION
**Iteration**: 2
**Date**: 2025-01-10

---

## Summary

This feature specification is sufficiently detailed to proceed with implementation. The iteration 1 Q&A has comprehensively addressed all critical ambiguities around data modeling, API design, caching strategy, error handling, and user interaction patterns. The specification now provides clear, actionable guidance for engineering implementation.

## What's Clear

### Data Model
- `manufacturer` field stored as `VARCHAR(50)` with database CHECK constraint limiting values to `'radeon'` and `'nvidia'` (lowercase)
- Index on `manufacturer` column for query performance: `CREATE INDEX idx_gpus_manufacturer ON gpus(manufacturer)`
- C# enum `ManufacturerType` with EF Core auto-conversion to lowercase strings
- Database constraint is extensible (adding Intel Arc is just `ALTER TABLE` to update CHECK constraint)
- Case-insensitive comparisons in application layer via `ToLowerInvariant()`

### Business Logic
- **Default mode**: Radeon on first visit
- **Persistence**: localStorage with key `preferredManufacturer`, values `"radeon"` or `"nvidia"`
- **Mode switching**: Immediate localStorage update → React state update → API call
- **Request cancellation**: New toggle during in-flight request cancels previous request via AbortController
- **Validation**: Invalid manufacturer query param returns 400 Bad Request with clear error message
- **Normalization**: All manufacturer values normalized to lowercase at API boundary

### API Design
- **Endpoint**: `GET /api/v1/gpus?manufacturer={manufacturer}` (single comprehensive endpoint)
- **Response structure**: Full GPU data including retail prices, used prices, value scores, and spec URLs in one call
- **Response size**: ~60KB typical (15-30 GPUs at ~2KB each) - acceptable for MVP
- **Error responses**: 
  - 400 for invalid manufacturer
  - 404 for no data available
  - 500 triggers auto-retry (transient failure)
- **Metadata included**: `count`, `lastUpdated`, `cacheExpiresAt` timestamps

### Caching Strategy
- **Backend (Redis)**: 
  - Keys: `gpus:manufacturer:radeon` and `gpus:manufacturer:nvidia` (separate per manufacturer)
  - TTL: 5 minutes (300 seconds)
  - Cache hit performance: ~50ms
  - Cache miss performance: ~300ms (database query + aggregation)
- **Frontend (TanStack Query)**:
  - Query keys: `['gpus', 'radeon']` and `['gpus', 'nvidia']`
  - Stale time: 5 minutes
  - Cache time: 10 minutes
  - Cache hit performance: 0ms (instant render)
- **Cache invalidation**: Manual (admin trigger) or TTL expiry

### Loading & Error Handling
- **Loading indicator delay**: 200ms (avoids flicker on fast responses)
- **Toggle state during loading**: Always enabled (allows cancellation)
- **Auto-retry logic**: 3 retries with exponential backoff (1s, 2s, 4s delays)
- **Error display**: Previous mode's data remains visible, error message shown with "Retry" and "Switch to {other mode}" options
- **Rapid toggling**: Only last-initiated request's data is rendered; previous requests cancelled
- **Loading skeleton**: Placeholder cards matching GPU card layout to prevent layout shift

### UI/UX
- **Toggle component**: Segmented control or tab interface (prominent, above-the-fold)
- **Active state**: Visual distinction (bold text, highlighted background)
- **Toggle position**: Always visible without scrolling
- **Feedback timing**: <200ms feels instant, >200ms shows loading indicator
- **Empty state**: "No {manufacturer} data available" message if API returns empty array
- **Data freshness indicator**: "Data as of [timestamp]" shown subtly below visualization

### Edge Cases
- **localStorage unavailable**: Graceful degradation to session-only state (defaults to Radeon each visit)
- **Invalid localStorage value**: Ignored, overwritten with valid default (Radeon)
- **API failure after retries**: Error shown, previous mode's data remains visible, toggle remains enabled
- **No data for manufacturer**: Empty state message shown, toggle remains enabled
- **Initial page load**: localStorage read synchronously before first render to avoid flash of wrong mode
- **Stale cache during price changes**: Acceptable (5-minute staleness), admin can manually invalidate if needed
- **Network timeout (>30s)**: Request aborted, retry initiated, error shown after 3 retries
- **Concurrent tabs**: Each tab manages own cache independently (no cross-tab sync in v1)

### Authorization
- No authorization required - this is a client-side filtering feature accessible to all users

### Out of Scope (Explicitly)
- No "All Manufacturers" view (cross-manufacturer comparison not valuable)
- No Intel Arc support in v1 (database schema supports future addition)
- No server-side preference storage (localStorage only)
- No URL state (mode not in query params or route)
- No analytics tracking (could add in v2)
- No keyboard shortcuts beyond standard tab navigation
- No real-time price updates (cache-based freshness)
- No per-user cache control

## Implementation Notes

### Database

**Migration to add manufacturer field** (if not already present):
```sql
ALTER TABLE gpus 
ADD COLUMN manufacturer VARCHAR(50) NOT NULL DEFAULT 'radeon'
CHECK (manufacturer IN ('radeon', 'nvidia'));

CREATE INDEX idx_gpus_manufacturer ON gpus(manufacturer);

-- Update existing rows based on model naming patterns
UPDATE gpus SET manufacturer = 'nvidia' WHERE model LIKE 'RTX %' OR model LIKE 'GTX %';
UPDATE gpus SET manufacturer = 'radeon' WHERE model LIKE 'RX %' OR model LIKE 'Radeon %';
```

**Query pattern**:
```csharp
var gpus = await _context.Gpus
    .Where(g => g.Manufacturer == manufacturerEnum)
    .Include(g => g.RetailPrices)
    .Include(g => g.UsedPrices)
    .OrderByDescending(g => g.ValueScore)
    .ToListAsync(cancellationToken);
```

### API Layer

**Endpoint**: `GET /api/v1/gpus?manufacturer={manufacturer}`

**Controller validation**:
```csharp
[HttpGet]
public async Task<IActionResult> GetGpus([FromQuery] string manufacturer)
{
    var normalizedManufacturer = manufacturer?.ToLowerInvariant();
    
    if (!Enum.TryParse<ManufacturerType>(normalizedManufacturer, true, out var manufacturerEnum))
    {
        return BadRequest(new ProblemDetails 
        { 
            Title = "Invalid manufacturer",
            Detail = "Must be 'radeon' or 'nvidia'.",
            Status = 400
        });
    }
    
    // Check Redis cache first
    var cacheKey = $"gpus:manufacturer:{normalizedManufacturer}";
    var cachedData = await _cache.GetStringAsync(cacheKey);
    
    if (cachedData != null)
    {
        return Content(cachedData, "application/json");
    }
    
    // Cache miss - query database
    var gpus = await _gpuService.GetByManufacturerAsync(manufacturerEnum);
    var response = new GpuListResponse(normalizedManufacturer, gpus);
    
    // Cache for 5 minutes
    await _cache.SetStringAsync(cacheKey, JsonSerializer.Serialize(response), 
        new DistributedCacheEntryOptions { AbsoluteExpirationRelativeToNow = TimeSpan.FromMinutes(5) });
    
    return Ok(response);
}
```

### Frontend (React + TypeScript)

**localStorage utilities**:
```typescript
const STORAGE_KEY = 'preferredManufacturer';
type Manufacturer = 'radeon' | 'nvidia';

function getStoredManufacturer(): Manufacturer {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === 'radeon' || stored === 'nvidia') {
      return stored;
    }
  } catch {
    // localStorage unavailable - graceful degradation
  }
  return 'radeon'; // default
}

function setStoredManufacturer(manufacturer: Manufacturer) {
  try {
    localStorage.setItem(STORAGE_KEY, manufacturer);
  } catch {
    // localStorage unavailable - continue without persistence
  }
}
```

**TanStack Query setup**:
```typescript
const { data, isLoading, error, refetch } = useQuery({
  queryKey: ['gpus', selectedManufacturer],
  queryFn: ({ signal }) => fetchGpus(selectedManufacturer, signal),
  staleTime: 5 * 60 * 1000, // 5 minutes
  cacheTime: 10 * 60 * 1000, // 10 minutes
  retry: 3,
  retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
});
```

**Loading indicator delay**:
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

**Toggle handler**:
```typescript
function handleManufacturerChange(newManufacturer: Manufacturer) {
  setStoredManufacturer(newManufacturer);
  setSelectedManufacturer(newManufacturer);
  // TanStack Query automatically cancels previous request and starts new one
}
```

### Caching

**Redis cache keys**:
- `gpus:manufacturer:radeon` → Full GPU list for Radeon
- `gpus:manufacturer:nvidia` → Full GPU list for Nvidia

**Manual cache invalidation** (admin endpoint):
```csharp
[HttpPost("api/admin/cache/invalidate")]
[Authorize(Roles = "Admin")]
public async Task<IActionResult> InvalidateCache([FromQuery] string manufacturer)
{
    var cacheKey = $"gpus:manufacturer:{manufacturer}";
    await _cache.RemoveAsync(cacheKey);
    return NoContent();
}
```

### Key Decisions

1. **Lowercase convention**: All manufacturer values lowercase in database, API, and localStorage - modern API standard
2. **Single endpoint**: One call returns full GPU data - simpler than multiple endpoints, acceptable response size
3. **Separate caches**: Redis keys per manufacturer - allows independent cache invalidation and fast mode switching
4. **Toggle always enabled**: Better UX on slow networks, allows request cancellation by user intent
5. **200ms loading delay**: Prevents flicker on fast responses while still providing feedback for slow ones
6. **Auto-retry 3x**: Handles transient network errors without user intervention
7. **No URL state in v1**: Simpler implementation, acceptable trade-off (links not shareable with specific mode)
8. **5-minute cache TTL**: Balances performance and data freshness for GPU pricing data

## Recommended Next Steps

1. **Create database migration** to add `manufacturer` field with CHECK constraint and index (if not already present)
2. **Implement API endpoint** `GET /api/v1/gpus?manufacturer={manufacturer}` with Redis caching
3. **Build React toggle component** with localStorage persistence and TanStack Query integration
4. **Implement loading/error states** with 200ms delay and retry logic
5. **Test edge cases**: localStorage unavailable, rapid toggling, API failures, cache expiry
6. **Verify cache performance**: Measure Redis cache hit rate and response times
7. **Test first-time user experience**: Ensure Radeon default works and localStorage is written correctly
8. **Test returning user experience**: Verify saved preference is respected on page reload

---

**This feature is ready for detailed engineering specification and implementation.**