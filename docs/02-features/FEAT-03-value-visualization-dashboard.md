# Value Visualization Dashboard - Feature Requirements

**Version**: 1.0  
**Date**: 2025-01-10  
**Status**: Initial - Awaiting Tech Lead Review

---

## Feature Overview

The Value Visualization Dashboard is the primary interface of GPU Value Tracker—a single-page visual representation that makes GPU value opportunities immediately obvious through graphical display of performance-to-price relationships. This is not a data table or list; it's a visual analytics dashboard that presents retail and used market pricing in a way that allows users to spot value inversions and sweet spots at a glance.

The dashboard aggregates data from Features 1 (Live Retail Price Aggregation) and 2 (Used Market Price Discovery) and presents it in a compelling, "wow factor" visualization that draws users in and helps them make purchasing decisions quickly. Users can toggle between Radeon and Nvidia views (Feature 5), and the visualization updates instantly to reflect the selected manufacturer.

This feature is the core differentiator of the product—what transforms raw pricing data into actionable market intelligence.

---

## User Stories

- As a PC builder, I want to see a visual representation of all GPU prices and their relative performance so that value sweet spots are immediately apparent
- As a visual learner, I want pricing and performance data displayed graphically so that I can quickly identify where the best deals are
- As a comparison shopper, I want to see where retail and used prices overlap with performance tiers so that I can make informed purchasing decisions
- As a user browsing the site, I want to be impressed by a visually striking dashboard so that I trust the data and want to return
- As a mobile user, I want the visualization to work on my tablet so that I can browse GPU deals while shopping at a physical store

---

## Acceptance Criteria

- Single-page dashboard displays all pricing data visually (not tables)
- Performance-to-price relationship is represented graphically (e.g., heat map, scatter plot, or similar visualization)
- "Value zones" where used prices meet or beat new price-to-performance are highlighted
- User can toggle between Radeon view and Nvidia view (never both simultaneously)
- Visualization updates automatically when underlying price data refreshes
- Visual design has "wow factor"—immediately impressive and clear
- Page loads in under 2 seconds with all visualizations rendered
- Visualization is responsive and works on desktop and tablet (mobile secondary)
- No data tables visible on initial load—graphics only
- All price data includes timestamp showing when it was last refreshed

---

## Functional Requirements

### Visualization Type

**What**: A graphical representation that plots GPUs based on performance (Y-axis or similar) and price (X-axis or similar), visually differentiating retail prices from used market prices.

**Why**: Tables hide patterns. Scatter plots, heat maps, or bubble charts immediately reveal clusters, outliers, and value zones. Users can see "Ah, that used 7900 XTX is in the same performance tier as the new 7800 XT but costs less"—without doing math.

**Behavior**:
- X-axis represents price (GBP)
- Y-axis represents relative performance tier (derived from VRAM, model generation, and known hierarchies)
- Each GPU model is a visual element (dot, bubble, card, etc.)
- Retail-priced GPUs are visually distinct from used-priced GPUs (different color, icon, or shape)
- "Value zones" are highlighted—areas where used GPUs offer equal/better performance-per-pound than retail options
- Hovering/tapping on a GPU element shows details: model name, average price, number of listings, link to OEM specs

---

### Performance Representation

**What**: Performance is not based on benchmarks scraped from third parties. Instead, it's derived from known GPU model hierarchies (e.g., 7900 XTX > 7900 XT > 7800 XT), VRAM capacity, and generation.

**Why**: Scraping benchmarks violates "Out of Scope" (no editorial content). We don't need exact FPS numbers—users understand that a 7900 XTX is faster than a 7800 XT. Relative positioning is sufficient.

**Behavior**:
- Performance tier is calculated based on:
  - GPU generation (newer = higher baseline)
  - Model tier within generation (XTX > XT > base)
  - VRAM capacity (higher VRAM = higher tier)
- Positioning is relative: if five GPUs are visualized, they're spaced according to known hierarchy
- No FPS numbers or benchmark scores are displayed
- If two GPUs have very similar performance (e.g., 7900 XT vs. 7900 GRE), they appear at similar Y-axis positions

---

### Price Data Display

**What**: Average retail price and average used market price are displayed for each GPU model that has available data.

**Why**: Users need to compare "what it costs new" vs "what I can find used" to identify value opportunities.

**Behavior**:
- If a GPU has retail listings, display average retail price as one visual element
- If a GPU has used listings, display average used price as a separate visual element (same GPU, different price point)
- Example: RX 7900 XTX might appear twice—once at £899 (retail average) and once at £650 (used average)
- If only retail or only used data exists for a model, show what's available
- Price includes currency symbol (£) and is rounded to nearest pound
- Tooltip/hover shows: "Average of 12 retail listings" or "Average of 8 used listings"

---

### Value Zone Highlighting

**What**: Visual emphasis on areas of the chart where used GPUs provide equal or better performance-per-pound than retail GPUs.

**Why**: This is the core insight—where the deals are. Highlighting makes it impossible to miss.

**Behavior**:
- Calculate performance-per-pound for every GPU (performance tier score / price)
- Identify "value frontier"—the best performance-per-pound at each price range
- Highlight used GPUs that meet or exceed the value frontier
- Visual treatment: could be a colored zone, glow effect, badge, or border
- Example: If RX 7800 XT costs £500 new and used 7900 XTX costs £650, the 7900 XTX is higher performance for only 30% more cost—highlight it as a value opportunity
- Value zones update dynamically as price data changes

---

### Manufacturer Toggle Integration

**What**: When user toggles between Radeon and Nvidia (Feature 5), the entire visualization re-renders with the selected manufacturer's data.

**Why**: Cross-manufacturer comparison is explicitly out of scope. The dashboard must focus on one ecosystem at a time.

**Behavior**:
- Toggle control is above or beside the visualization (prominent placement)
- Selecting "Radeon" shows only AMD GPUs
- Selecting "Nvidia" shows only Nvidia GPUs
- Transition is smooth (fade/slide animation, not jarring)
- All tooltips, labels, and data update instantly
- Chart axes may rescale if price ranges differ significantly between manufacturers
- User's selection persists (handled by Feature 5)

---

### Data Freshness Indicator

**What**: Timestamp displayed on the dashboard showing when price data was last updated.

**Why**: Users need to trust that they're seeing current market data, not stale information.

**Behavior**:
- Display "Prices updated: 2 hours ago" or similar
- Timestamp updates automatically when price data refreshes
- If data is >24 hours old, show warning: "Price data is outdated—last update was [time]"
- Timestamp is visible without scrolling (top of page or in header)

---

### Performance Requirements

**What**: Page must load and render the visualization in under 2 seconds on desktop with broadband.

**Why**: Slow-loading visualizations kill engagement. Users will leave if they wait >3 seconds.

**Behavior**:
- API endpoint serving price data must respond in <500ms
- Aggregated price data is cached in Redis (refreshed when scraping jobs complete)
- Frontend uses lazy loading or skeleton UI while data fetches
- Visualization library is optimized (avoid libraries that render 1000+ DOM nodes)
- Initial page load includes inlined critical CSS; visualization library loads async
- Target: Largest Contentful Paint (LCP) <1.5 seconds

---

### Responsive Design

**What**: Dashboard works on desktop (1920x1080 primary), tablet (768px+), and gracefully degrades on mobile (≥375px wide).

**Why**: Users may browse on tablets while shopping or share links on mobile. Desktop-first, but tablet must be usable.

**Behavior**:
- Desktop: Full visualization with all details visible, hover interactions work
- Tablet (portrait/landscape): Visualization scales down, touch interactions replace hover (tap for tooltip)
- Mobile: Simplified visualization or scrollable horizontal view; performance and value zones still visible
- No horizontal scrolling on any screen size (responsive layout)
- Touch targets are ≥44px on mobile/tablet
- Text remains readable at all sizes (minimum 14px font)

---

### Accessibility

**What**: Visualization is accessible to keyboard users and screen reader users (WCAG AA compliance minimum).

**Why**: Legal requirement in UK; also good practice.

**Behavior**:
- All interactive elements (GPU data points) are keyboard accessible (tab navigation)
- Focus indicators are visible
- Alt text describes the chart for screen readers: "Scatter plot showing GPU performance vs price, with value zones highlighted"
- Color is not the only differentiator (use shapes, labels, or patterns in addition to color)
- Tooltips are accessible via keyboard (not hover-only)

---

## Data Model (Initial Thoughts)

**Entities This Feature Needs**:

- **GpuPriceSnapshot**: Aggregated price data for a GPU model at a point in time
  - Fields: ModelId, Manufacturer (Radeon/Nvidia), AverageRetailPrice, AverageUsedPrice, RetailListingCount, UsedListingCount, LastUpdated
  
- **GpuPerformanceTier**: Static mapping of GPU models to relative performance scores
  - Fields: ModelId, ModelName, PerformanceScore, Generation, VramGB
  
- **VisualizationCache**: Pre-calculated visualization data to speed up API responses
  - Fields: Manufacturer, DataBlob (JSON), CacheTimestamp

**Key Relationships**:
- GpuPriceSnapshot references GpuPerformanceTier via ModelId
- Frontend API endpoint joins PriceSnapshot + PerformanceTier to generate visualization data

**Open Questions**:
- Should PerformanceTier data be hardcoded in the application or stored in the database? (Leaning toward database for easier updates when new GPUs release)
- How often should VisualizationCache be regenerated? (Every scraping job completion?)

---

## User Experience Flow

1. User lands on the homepage, sees a prominent toggle: **Radeon | Nvidia** (Radeon selected by default)
2. Page loads visualization showing Radeon GPU price/performance scatter plot with value zones highlighted
3. User sees: Latest-gen RX 7900 XTX at £899 (retail), used at £650; RX 7800 XT at £499 (retail), used at £420
4. User hovers over the used RX 7900 XTX bubble—tooltip appears: "RX 7900 XTX (Used) - Avg £650 - 8 listings - Updated 2 hours ago"
5. User clicks "Official Specs" link in tooltip → Opens AMD product page in new tab
6. User toggles to **Nvidia**
7. Visualization smoothly transitions to show Nvidia GPUs (RTX 4080, 4070 Ti, etc.) with their retail/used prices
8. User identifies a value opportunity: used RTX 4080 at £800 is in a highlighted value zone
9. User reviews multiple GPUs, makes a purchasing decision, leaves the site

---

## Edge Cases & Constraints

- **No data for a GPU model**: If a GPU has no retail or used listings, it doesn't appear on the chart
- **Only one price type available**: If only retail OR only used data exists, show what's available (no "missing data" error)
- **Extreme outliers in used market**: Prices >2x average for that model are filtered before calculating used average (prevents "GPU listed at £10,000" from skewing data)
- **Very few listings**: If <3 listings exist for a GPU, show price with asterisk: "£650*" and tooltip: "Based on only 2 listings—price may be unreliable"
- **Chart overcrowding**: If >20 GPUs are displayed, may need to cluster or paginate (monitor after launch)
- **Data refresh mid-session**: If user has page open while scraping job completes, show notification: "New price data available—refresh to update"
- **Browser compatibility**: Support latest 2 versions of Chrome, Firefox, Safari, Edge (no IE11)

---

## Out of Scope for This Feature

The following are explicitly NOT part of the Value Visualization Dashboard in v1:

- **Historical price trends**: No "price over time" graphs or trend lines
- **User-saved comparisons**: No ability to save or bookmark specific GPUs
- **Custom performance weighting**: Users cannot adjust what "performance" means (e.g., prioritize VRAM vs. speed)
- **Filtering by price range**: No sliders to filter "show only GPUs £400-£600" (entire dataset is visible)
- **Comparison with other hardware**: No CPU, RAM, or PSU recommendations based on selected GPU
- **Third-party benchmark integration**: No FPS data, PassMark scores, or review scores
- **Export to PDF/image**: No ability to download or share the visualization as an image
- **Animated transitions on data update**: Visualization re-renders on data refresh but doesn't animate points moving

---

## Open Questions for Tech Lead

- **Visualization Library**: Should we use D3.js (flexible but heavy), Recharts (React-native, simpler), or Plotly (feature-rich, larger bundle)? What's the trade-off between visual sophistication and performance?
  
- **Performance Score Source**: Should we hardcode the GPU performance hierarchy in the app (fast, but requires code changes for new GPUs) or maintain it as database-seeded data (flexible, but requires migration process)?

- **Value Zone Calculation**: Should the "value frontier" be recalculated on every page load, or pre-calculated and cached? What's the performance impact?

- **Real-time Updates**: If a user has the page open for 30+ minutes, should we poll for new data, use WebSockets, or show a "Refresh for latest prices" banner?

- **Mobile Strategy**: Given that mobile is secondary, is a simplified chart (e.g., vertical bar chart instead of scatter plot) acceptable, or should we attempt to render the same visualization responsively?

---

## Dependencies

**Depends On**:
- Feature 1: Live Retail Price Aggregation (provides retail price data)
- Feature 2: Used Market Price Discovery (provides used price data)
- Feature 5: Radeon vs Nvidia Mode Switching (manufacturer toggle functionality)

**Enables**:
- Feature 4: Manufacturer Reference Links (OEM links displayed within visualization tooltips)

**Critical Path**: This feature cannot be built until Features 1 and 2 provide data via API endpoints. Feature 5 must be implemented in parallel (toggle controls the visualization).