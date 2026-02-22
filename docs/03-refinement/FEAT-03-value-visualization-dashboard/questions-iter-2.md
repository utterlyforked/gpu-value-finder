# Value Visualization Dashboard - Technical Review (Iteration 2)

**Status**: ✅ READY FOR IMPLEMENTATION
**Iteration**: 2
**Date**: 2025-01-10

---

## Summary

This feature specification is **sufficiently detailed to proceed with implementation**. All critical questions from Iteration 1 have been answered comprehensively, and the v1.1 update provides clear guidance on:

- Performance scoring methodology
- Value zone calculation algorithm
- Data aggregation strategy
- Visual design and accessibility
- API contracts and caching strategy
- Edge case handling

The PRD is thorough, well-structured, and includes concrete implementation details, database schemas, API specifications, and testing checklists.

---

## What's Clear

### Data Model

**Well-Defined Entities**:

1. **`GpuPerformanceTier` Table**:
   - `ModelId` (PK): Unique identifier (e.g., "rx-7900-xtx")
   - `Manufacturer` (enum): Radeon | Nvidia
   - `Generation`: "RX 7000" | "RTX 40" | "RX 6000" | "RTX 30"
   - `ReferenceName`: Display name (e.g., "AMD Radeon RX 7900 XTX")
   - `PerformanceScore` (int): 1-100 scale, manually assigned
   - `VramGB` (int): VRAM capacity
   - `OemProductUrl` (nullable): Link to OEM product page
   - `IsCurrentGen` (bool): Current vs. previous generation flag
   - Timestamps: `CreatedAt`, `UpdatedAt`

2. **`GpuPriceSnapshot` Table**:
   - Links to `GpuPerformanceTier` via `ModelId` FK
   - Separate fields for retail vs. used pricing: `AverageRetailPrice`, `AverageUsedPrice`
   - Listing counts with outlier tracking: `RetailListingCount`, `RetailOutlierCount`, `UsedListingCount`, `UsedOutlierCount`
   - `IsValueZone` (bool): Pre-calculated value zone status
   - `LastUpdated` (DateTime): Timestamp from scraping job
   - `SnapshotVersion` (int): Incremental version for history tracking

3. **Redis Cache Structure**:
   - Cache keys: `viz:radeon:current`, `viz:radeon:all`, `viz:nvidia:current`, `viz:nvidia:all`
   - 15-minute TTL
   - JSON payload includes full visualization data with pre-calculated flags (`isValueZone`, `hasLowListings`)
   - Cache invalidation triggered by scraping job completion (Hangfire)

**Relationships**:
- `GpuPriceSnapshot.ModelId` → `GpuPerformanceTier.ModelId` (many-to-one)
- `GpuListing` (Features 1/2) → `GpuPerformanceTier.ModelId` for aggregation
- Clear separation: performance scores are static (manually maintained), price snapshots are dynamic (updated every 4-6 hours)

---

### Business Logic

**Performance Scoring**:
- Simple Ordinal Ranking (1-100 scale)
- Manually assigned by product team based on GPU generation, tier, and VRAM
- Stored in database, updated via EF Core migrations
- Example hierarchy clear: RX 7900 XTX (95) > RX 7900 XT (88) > RX 7800 XT (75) > RX 7700 XT (68)
- Maintenance process defined: Product provides scores → Engineering creates migration → Deployment updates database

**Price Aggregation**:
- All manufacturer SKUs (Sapphire, PowerColor, XFX) aggregate to single reference model
- Outlier filtering before averaging:
  - Used: exclude listings >2x median
  - Retail: exclude listings >1.5x median
- Outliers excluded from average calculation AND listing count
- Special editions (>10% spec difference) treated as separate models (case-by-case)

**Value Zone Algorithm** ("Tier Jumping"):
- Applied to **used GPUs only** (retail never highlighted)
- Logic: `usedGpuPerformance >= (retailGpuPerformance + 10%)` AND `usedPrice <= retailPrice`
- Compares against retail GPUs in similar price range (±£100)
- Exclusions:
  - Used GPUs with <3 listings
  - Outlier-filtered listings
  - No retail comparisons available
- Example clearly explained: Used RX 7900 XTX (£650, perf=95) vs. Retail RX 7900 XT (£700, perf=88) → Value zone

**Low-Listing Handling**:
- Threshold: Minimum 3 listings (same for retail and used)
- Visual treatment: Asterisk (*), 70% opacity, warning tooltip
- Excluded from value zone calculations
- Tooltip shows: "⚠️ Based on only 2 listings — price may be unreliable"

**Data Freshness**:
- Timestamp displayed: "Prices updated: 2 hours ago" (relative time, updates every 60 seconds via JS)
- Staleness warning if >24 hours old: Yellow banner
- No automatic real-time updates (manual browser refresh only)
- Rationale clear: Scraping frequency (4-6 hours) doesn't justify WebSocket complexity

---

### API Design

**Endpoint**: `GET /api/v1/visualization/data`

**Request**:
- Query params: `manufacturer` (required: "radeon" | "nvidia"), `includeOlderGen` (optional: bool, default false)

**Response** (200 OK):
```json
{
  "manufacturer": "radeon",
  "includeOlderGen": false,
  "lastUpdated": "2025-01-10T14:32:00Z",
  "dataPoints": [
    {
      "modelId": "rx-7900-xtx",
      "modelName": "AMD Radeon RX 7900 XTX",
      "performanceScore": 95,
      "retailPrice": 899.00,
      "retailListingCount": 12,
      "retailOutlierCount": 1,
      "retailHasLowListings": false,
      "usedPrice": 650.00,
      "usedListingCount": 8,
      "usedOutlierCount": 2,
      "usedHasLowListings": false,
      "isValueZone": true,
      "oemProductUrl": "https://www.amd.com/..."
    }
  ]
}
```

**Caching**:
- Redis cache with 15-minute TTL
- ETag based on `lastUpdated` timestamp
- Cache-Control: `public, max-age=300` (5-minute client cache)
- Fallback to database query if Redis unavailable

**Error Responses**:
- 400 Bad Request: Invalid manufacturer parameter
- 304 Not Modified: ETag match (no data change)
- 503 Service Unavailable: Redis down + database timeout

**Performance Target**: <500ms response time (cached), <2 seconds page load total

---

### UI/UX

**Visualization Type**:
- Scatter plot (Recharts library)
- X-axis: Price (GBP, £0-£1500 typical, dynamically scaled)
- Y-axis: Performance Score (0-100, fixed scale, labeled "Performance Score (relative)")
- Each GPU with both retail and used data appears as TWO data points (vertically aligned, horizontally offset)

**Visual Differentiation**:
- Retail: Blue circle (#3B82F6) + "NEW" badge (32px × 16px, white bg, blue border)
- Used: Green circle (#10B981) + "USED" badge (40px × 16px, white bg, green border)
- Value zones: Yellow glow (#FBBF24, 40% opacity halo) + 25% larger circle (30px vs. 24px)
- Low listings: 70% opacity + asterisk on price
- Colorblind accessibility: Used circles have subtle dot pattern (2px dots, 4px spacing)

**Interactions**:
- **Desktop (hover)**: Tooltip appears after 200ms delay
- **Tablet/Mobile (touch)**: Tap data point to show tooltip, tap elsewhere to dismiss, "×" close button
- **Tooltip content**:
  - Model name: "AMD Radeon RX 7900 XTX"
  - Price: "£899 (New - Retail Avg)" or "£650 (Used - Market Avg)"
  - Listing count: "Based on 12 listings" (or "2 listings*" with warning)
  - Last updated: "Updated 2 hours ago"
  - Value zone badge (if applicable): "💎 VALUE OPPORTUNITY"
  - Link: "View Official Specs →" (opens OEM page in new tab)

**Responsive Design**:
- Desktop (≥1200px): 1000px × 600px chart, hover interactions
- Tablet (768-1199px): 700px × 500px chart, touch interactions
- Mobile (375-767px): Full-width × 400px chart, modal-style tooltips, horizontal scroll if needed
- Touch targets ≥44px per WCAG

**Controls**:
- Manufacturer toggle (from Feature 5): Radeon | Nvidia (exclusive, smooth 200ms fade transition)
- "Show older GPUs" checkbox: Adds RX 6000 / RTX 30 series (~20 additional models)
- Data freshness indicator: Top-right corner, "Prices updated: X hours ago"

**Display Limits**:
- No hard cap on data points
- Current-gen only (default): ~12-15 GPUs × 2 = 24-30 points
- With older GPUs: ~50-60 points
- Chart remains functional; monitor crowding post-launch

---

### Edge Cases

**Addressed**:

1. **No data for model**: GPU doesn't appear on chart (both retail and used null)
2. **Only one price type**: Single data point (blue OR green, not both)
3. **Extreme outliers**: Filtered from average (>2x median used, >1.5x median retail), but visible in linked listings (Features 1/2)
4. **Very few listings (<3)**: Display with asterisk, 70% opacity, warning tooltip, exclude from value zones
5. **Chart overcrowding**: Monitor post-launch; add zoom/pan in v2 if needed
6. **Data refresh mid-session**: User sees stale data until manual refresh (no auto-notification)
7. **Browser compatibility**: Latest 2 versions of Chrome, Firefox, Safari, Edge (no IE11)
8. **No value zones for retail**: Retail GPUs never highlighted, even if one is significantly better value than another retail option
9. **Value zone with low listings**: Used GPU with <3 listings excluded from value zone calculation
10. **Missing OEM URL**: Link hidden if `OemProductUrl` is null (graceful degradation)
11. **Special edition GPUs**: Factory OC or water-cooled variants with >10% spec difference treated as separate models (case-by-case decision)
12. **Timezone handling**: All timestamps stored in UTC, converted to user's local timezone via JS `toLocaleString()`

---

### Authorization

- Not applicable to this feature (public dashboard, no auth required)
- If user auth added in future, this feature remains publicly accessible (no restrictions)

---

### Validation

**Data Quality**:
- Outlier filtering: >2x median (used), >1.5x median (retail)
- Low-listing threshold: Minimum 3 listings for reliable data
- Performance scores: 1-100 integer range, validated at database level

**API Input Validation**:
- `manufacturer` param: Must be "radeon" or "nvidia" (case-insensitive, returns 400 if invalid)
- `includeOlderGen` param: Boolean (defaults to false if omitted or invalid)

**Frontend Validation**:
- Chart rescales dynamically if price ranges exceed typical bounds
- Tooltip text truncated if model names exceed 50 characters (unlikely but handled)

---

### Key Decisions

1. **Simple Ordinal Ranking for Performance**: Gives product team full control, avoids benchmark scraping legal issues, easy to maintain
2. **Tier Jumping Value Zone Logic**: 10% performance improvement threshold catches meaningful upgrades without over-highlighting
3. **Aggregate by Reference Model**: Simplifies visualization, aligns with user mental model ("I want a 7900 XTX")
4. **Always Show Retail + Used (Dual Display)**: Core value proposition—makes price gap visually obvious
5. **Exclude Low-Listing GPUs from Value Zones**: Conservative approach builds credibility, avoids promoting unreliable deals
6. **No Real-Time Update Notifications**: Scraping frequency (4-6 hours) doesn't justify WebSocket complexity
7. **Recharts Library**: Pragmatic choice—React-native, TypeScript support, 50KB bundle, handles 50-100 points easily
8. **Icon + Color + Pattern for Differentiation**: WCAG AA compliance via triple redundancy (color + badge text + dot pattern)
9. **Numeric Y-Axis Scores**: More precise than tier labels, clearly labeled as "(relative)" to avoid benchmark misinterpretation
10. **OEM Links Only (No Retailer Links)**: Aligns with manufacturer reference concept, avoids favoritism, canonical spec source

---

## Implementation Notes

### Database

**Critical Path**:
1. Create `GpuPerformanceTier` table via EF Core migration
2. Seed performance scores for RX 7000 series (7 models minimum: XTX, XT, GRE, 7800 XT, 7700 XT, 7600 XT, 7600)
3. Seed performance scores for RTX 40 series (9 models minimum: 4090, 4080 Super, 4080, 4070 Ti Super, 4070 Ti, 4070 Super, 4070, 4060 Ti, 4060)
4. Seed OEM product URLs for all models
5. Add indexes: `Manufacturer`, `IsCurrentGen` for fast filtering

**Example Migration Seed**:
```csharp
migrationBuilder.InsertData(
    table: "GpuPerformanceTier",
    columns: new[] { "ModelId", "Manufacturer", "Generation", "ReferenceName", "PerformanceScore", "VramGB", "OemProductUrl", "IsCurrentGen" },
    values: new object[] { 
        "rx-7900-xtx", "Radeon", "RX 7000", "AMD Radeon RX 7900 XTX", 95, 24, 
        "https://www.amd.com/en/products/graphics/amd-radeon-rx-7900-xtx", true 
    }
);
```

**Unique Constraints**:
- `GpuPerformanceTier.ModelId` (PK)
- `GpuPriceSnapshot` (unique on `ModelId` + `SnapshotVersion`)

---

### Backend

**API Implementation**:
- Controller: `VisualizationController.GetData(manufacturer, includeOlderGen)`
- Service layer: `VisualizationService` with methods:
  - `GetVisualizationDataAsync(manufacturer, includeOlderGen)` → Queries Redis first, falls back to DB
  - `CalculateValueZones(dataPoints)` → Applies tier jumping logic
  - `FilterOutliers(listings)` → Removes >2x or >1.5x median
- Repository: Standard EF Core queries with `.Include(x => x.PerformanceTier)`

**Caching Strategy**:
- Hangfire job regenerates Redis cache after scraping completes
- Cache key pattern: `viz:{manufacturer}:{generation}` (4 keys total)
- Cache miss fallback: Direct DB query (slower but functional)

**Performance Optimization**:
- Pre-calculate `IsValueZone` during snapshot creation (avoid recalculating on every request)
- Use Redis hash structure for faster lookups
- Add ETag support to minimize redundant transfers

---

### Frontend

**Component Structure**:
```
<VisualizationDashboard>
  ├─ <DashboardHeader>
  │   ├─ <ManufacturerToggle> (Feature 5)
  │   ├─ <OlderGpusCheckbox>
  │   └─ <DataFreshnessIndicator>
  ├─ <PricePerformanceChart> (Recharts ScatterChart)
  │   ├─ <Scatter data={retailDataPoints} />
  │   ├─ <Scatter data={usedDataPoints} />
  │   ├─ <CustomTooltip>
  │   └─ <CustomLegend>
  └─ <ChartFooter>
      ├─ <PerformanceScoreExplainer>
      └─ <FaqLink>
```

**State Management**:
- TanStack Query: `useQuery(['visualization', manufacturer, includeOlderGen], { staleTime: 5 * 60 * 1000 })` (5-minute stale time)
- Feature 5's `useManufacturerToggle()` hook for manufacturer selection
- Local state for `includeOlderGen` checkbox (persist to localStorage)

**Chart Configuration**:
- Recharts `<ScatterChart>` with `<XAxis type="number" />` (price) and `<YAxis domain={[0, 100]} />` (performance)
- Custom `<Tooltip>` component with conditional rendering (value zone badge, low-listing warning)
- Custom data point rendering: SVG circles with badge overlays (use Recharts `<Cell>` for per-point styling)

---

### Testing

**High-Priority Tests**:
1. Value zone calculation with various performance/price combinations
2. Outlier filtering (>2x median used, >1.5x median retail)
3. Low-listing detection (<3 listings)
4. Reference model aggregation (multiple SKUs → single average)
5. API endpoint returns correct JSON structure
6. Redis cache hit/miss scenarios
7. Frontend chart renders with mock data
8. Tooltip shows on hover (desktop) and tap (mobile)
9. Manufacturer toggle updates chart smoothly
10. "Show older GPUs" checkbox adds data points
11. Accessibility: keyboard navigation, screen reader, color contrast

**Performance Targets**:
- Page load: <2 seconds (desktop, broadband)
- API response: <500ms (cached), <2s (uncached)
- LCP (Largest Contentful Paint): <1.5 seconds
- Chart render: <200ms for 50 data points

---

## Recommended Next Steps

1. **Create Database Migration**:
   - Generate `GpuPerformanceTier` table schema
   - Seed performance scores for RX 7000 and RTX 40 series (minimum 16 models)
   - Seed OEM product URLs
   - Add indexes on `Manufacturer` and `IsCurrentGen`

2. **Implement Backend API**:
   - Create `VisualizationController` with `GetData` endpoint
   - Implement `VisualizationService` with Redis caching logic
   - Add value zone calculation algorithm
   - Add outlier filtering logic
   - Write unit tests for business logic

3. **Implement Frontend Components**:
   - Install Recharts library (`npm install recharts`)
   - Create `<VisualizationDashboard>` component skeleton
   - Integrate Feature 5's `<ManufacturerToggle>` component
   - Implement `<PricePerformanceChart>` with Recharts
   - Style with Tailwind CSS (blue/green/yellow color scheme)
   - Add custom tooltip component with conditional badges

4. **Integration Testing**:
   - Mock Redis cache in development environment
   - Test API endpoint with Postman/Insomnia
   - Verify frontend fetches and renders data correctly
   - Test manufacturer toggle transitions
   - Test "Show older GPUs" checkbox

5. **Accessibility Audit**:
   - Run Lighthouse accessibility scan (target: 100 score)
   - Test keyboard navigation (tab through data points)
   - Test with screen reader (NVDA/JAWS)
   - Verify color contrast ratios (WCAG AA minimum 4.5:1)

6. **Performance Testing**:
   - Measure API response time with realistic data (50+ GPU models)
   - Measure page load time with Lighthouse
   - Test chart render performance with 60 data points
   - Monitor Redis cache hit rate in staging

7. **Documentation**:
   - Add API endpoint to OpenAPI/Swagger docs
   - Create FAQ page explaining performance score methodology
   - Document cache invalidation strategy for ops team
   - Add "How It Works" section to user-facing site

---

**This feature is ready for detailed engineering specification and implementation.**

---

## Dependencies Confirmed

**Requires**:
- ✅ Feature 1 (Live Retail Price Aggregation): Provides `GET /api/v1/prices/retail` with `ModelId`, `AveragePrice`, `ListingCount`, `OutlierCount`, `LastUpdated`
- ✅ Feature 2 (Used Market Price Discovery): Provides `GET /api/v1/prices/used` with same structure
- ✅ Feature 5 (Manufacturer Toggle): Provides `useManufacturerToggle()` React hook and localStorage persistence

**Enables**:
- ✅ Feature 4 (Manufacturer Reference Links): OEM URLs stored in `GpuPerformanceTier.OemProductUrl`, displayed in tooltip "View Official Specs" link

**Critical Path**:
- Backend: Features 1 and 2 must complete price aggregation endpoints before visualization API can aggregate their data
- Frontend: Feature 5's toggle component must be built in parallel (can be mocked during visualization development)
- Database: `GpuPerformanceTier` migration is blocking—must be deployed before any visualization development begins

---

## Final Assessment

**Completeness**: 10/10  
All functional requirements, edge cases, business logic, data models, API contracts, UI/UX flows, and testing criteria are thoroughly documented. No ambiguity remains.

**Clarity**: 10/10  
Specifications are concrete with examples. Technical decisions are justified with clear rationale. Implementation notes provide actionable guidance.

**Implementability**: 10/10  
An engineer can read this PRD and begin implementation immediately. Database schema is defined, API response structure is specified, component hierarchy is outlined, and testing checklist is provided.

**No Blocking Questions Remain**: ✅

This feature is **ready for implementation**.