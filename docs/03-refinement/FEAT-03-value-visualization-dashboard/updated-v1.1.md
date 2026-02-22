# Value Visualization Dashboard - Product Requirements (v1.1)

**Version History**:
- v1.0 - Initial specification (2025-01-10)
- v1.1 - Iteration 1 clarifications (2025-01-10) - Added: Performance scoring methodology, value zone algorithm, model granularity, dual price point display, low-listing handling, outlier filtering, visualization library choice, real-time update strategy, display limits, touch interactions, link strategy, visual differentiation, Y-axis labeling

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

## Acceptance Criteria (UPDATED v1.1)

- Single-page dashboard displays all pricing data visually (not tables)
- Performance-to-price relationship is represented graphically via scatter plot (X-axis = price, Y-axis = performance score)
- Performance scores are calculated using Simple Ordinal Ranking (1-100 scale), stored in database, manually maintained by product team
- GPUs are aggregated by reference model (e.g., "RX 7900 XTX") regardless of manufacturer variant (Sapphire, PowerColor, etc.)
- Each GPU model with both retail and used data appears as TWO visual elements (one for retail average, one for used average) at the same Y-position (performance) but different X-positions (price)
- "Value zones" highlight used GPUs where `usedGpuPerformance >= (retailGpuPerformance + 10%)` AND `usedPrice <= retailPrice`
- Value zones are exclusive to used GPUs—retail GPUs are never highlighted
- GPUs with fewer than 3 listings display with asterisk (*) and warning tooltip, and are excluded from value zone calculations
- Outlier prices (>2x median for used, >1.5x median for retail) are excluded from average calculations but still visible in linked listing data (Features 1/2)
- User can toggle between Radeon view and Nvidia view (never both simultaneously)
- Visualization updates automatically when underlying price data refreshes
- Visual design has "wow factor"—immediately impressive and clear
- Page loads in under 2 seconds with all visualizations rendered
- Visualization is responsive and works on desktop and tablet (mobile secondary)
- No data tables visible on initial load—graphics only
- All price data includes timestamp showing when it was last refreshed
- Retail and used price points are visually differentiated using color + icon badges (retail = "NEW" badge, used = "USED" badge)
- Y-axis displays numeric performance scores (0-100 scale) with label "Performance Score (relative)"
- Tooltip on hover (desktop) or tap (tablet/mobile) shows: model name, price, listing count, last updated timestamp, and link to OEM product page
- Touch interactions: tap to show tooltip, tap anywhere else to dismiss
- No automatic real-time update notifications—user sees "Prices updated X hours ago" timestamp and can manually refresh browser if desired
- All current-generation GPUs with available data are displayed (no arbitrary cap)—includes RX 7000 series and RTX 40 series by default
- Previous-generation GPUs (RX 6000, RTX 30 series) are hidden by default but can be toggled via "Show older GPUs" checkbox

---

## Functional Requirements

### Visualization Type

**What**: A scatter plot that positions GPUs based on performance score (Y-axis, 0-100 scale) and price in GBP (X-axis), visually differentiating retail prices from used market prices.

**Why**: Scatter plots immediately reveal clusters, outliers, and value zones. Users can see "Ah, that used 7900 XTX is in the same performance tier as the new 7800 XT but costs less"—without doing math.

**Behavior**:
- X-axis represents price (GBP, £0-£1500 typical range, dynamically scaled)
- Y-axis represents performance score (0-100 scale, numeric labels)
- Each GPU reference model (e.g., "RX 7900 XTX") appears as one or two visual elements depending on available data:
  - If retail data exists: one data point at `(averageRetailPrice, performanceScore)`
  - If used data exists: one data point at `(averageUsedPrice, performanceScore)`
  - If both exist: two data points vertically aligned (same Y, different X)
- Retail-priced GPUs use solid circle with "NEW" badge overlay (blue color)
- Used-priced GPUs use solid circle with "USED" badge overlay (green color)
- Value zone GPUs (used only) have additional glow/highlight effect (yellow border or similar)
- Hovering/tapping on a GPU element shows tooltip with:
  - Model name (e.g., "AMD Radeon RX 7900 XTX")
  - Price with condition: "£899 (New - Retail Avg)" or "£650 (Used - Market Avg)"
  - Listing count: "Based on 12 listings" (or "Based on 2 listings*" if <3)
  - Last updated: "Updated 2 hours ago"
  - Link: "View Official Specs →" (opens OEM product page in new tab)
- Visualization library: **Recharts** (React-native, TypeScript support, good performance for <50 data points, simpler than D3.js, lighter than Plotly)

---

### Performance Representation (UPDATED v1.1)

**What**: Performance is represented by a manually-assigned ordinal score (1-100 scale) stored in the `GpuPerformanceTier` database table. Scores are determined by product team based on known GPU hierarchies, generation, and VRAM.

**Why**: Simple ordinal ranking gives product full control over positioning, avoids benchmark scraping (out of scope), and is easy to debug and maintain. Users understand relative performance without needing exact FPS numbers.

**Behavior**:
- Each GPU reference model has a `PerformanceScore` integer field (1-100 scale)
- Scores are seeded via Entity Framework Core migrations
- Example scoring for Radeon RX 7000 series:
  - RX 7900 XTX: 95
  - RX 7900 XT: 88
  - RX 7900 GRE: 82
  - RX 7800 XT: 75
  - RX 7700 XT: 68
  - RX 7600 XT: 55
  - RX 7600: 50
- Scores are assigned considering:
  - GPU generation (RX 7000 > RX 6000)
  - Model tier within generation (XTX > XT > base)
  - VRAM capacity (24GB > 16GB > 12GB)
- Y-axis displays scores numerically (0, 25, 50, 75, 100) with label: "Performance Score (relative)"
- Axis label disclaimer: "(relative)" clarifies this is not FPS or benchmark data
- Positioning is relative: if five GPUs are visualized, they're spaced according to their scores
- GPUs with very similar performance (e.g., 7900 XT = 88, 7900 GRE = 82) appear at close but distinct Y-positions
- No FPS numbers, PassMark scores, or benchmark data are displayed anywhere
- **Maintenance process**: When new GPUs release, product team provides performance scores via Slack/email → Engineering adds scores via EF Core migration → Deployment updates database

---

### Price Data Display (UPDATED v1.1)

**What**: Average retail price and average used market price are displayed for each GPU reference model that has available data. Each GPU with both data types appears as TWO distinct visual elements.

**Why**: Users need to compare "what it costs new" vs "what I can find used" to identify value opportunities. Dual representation makes the price gap visually obvious.

**Behavior**:
- GPUs are aggregated by **reference model** (e.g., "RX 7900 XTX")—all manufacturer variants (Sapphire, PowerColor, XFX, etc.) roll up into one reference model
- Database: `GpuModel.ReferenceName` = "RX 7900 XTX", all SKUs from different manufacturers are averaged
- If a GPU has retail listings, display average retail price as one visual element (blue circle with "NEW" badge)
- If a GPU has used listings, display average used price as a separate visual element (green circle with "USED" badge)
- Example: RX 7900 XTX appears twice on chart:
  - Data point 1: X=£899 (retail), Y=95 (performance), blue, "NEW" badge
  - Data point 2: X=£650 (used), Y=95 (performance), green, "USED" badge
- Both points are vertically aligned (same performance score) but horizontally offset (different prices)
- If only retail OR only used data exists for a model, show what's available (single data point)
- Price includes currency symbol (£) and is rounded to nearest pound
- Tooltip shows: "Retail Avg: £899 (12 listings)" or "Used Avg: £650 (8 listings)"
- **Outlier filtering** (applied before calculating averages):
  - Used prices: exclude any listing >2x the median price for that model
  - Retail prices: exclude any listing >1.5x the median price for that model
  - Example: If median used price for 7900 XTX is £650, any listing >£1300 is excluded
  - Outliers are excluded from average calculation AND listing count
  - Tooltip for filtered data: "Based on 12 valid listings (3 outliers excluded)"
  - Outlier listings are still visible if user navigates to full listing pages (Features 1/2)

---

### GPU Model Granularity (UPDATED v1.1)

**What**: All manufacturer-specific SKUs (Sapphire Nitro+, PowerColor Red Devil, XFX Speedster, etc.) are aggregated into a single "reference model" data point.

**Why**: Users shopping for GPUs think in terms of "7900 XTX" or "RTX 4080," not specific manufacturer variants. Aggregation keeps the visualization clean and comparable. SKU-level detail can be explored via linked listing pages (Features 1/2).

**Behavior**:
- Database schema:
  - `GpuModel` table has `ReferenceName` field (e.g., "RX 7900 XTX")
  - `GpuListing` table links to `GpuModel` and includes `ManufacturerSKU` (e.g., "Sapphire Nitro+ RX 7900 XTX")
- Price aggregation logic:
  - Query all listings for a reference model
  - Filter outliers (see Price Data Display section)
  - Calculate average price across all remaining listings regardless of manufacturer
- Example: "RX 7900 XTX" average retail price = £899 based on:
  - Sapphire Nitro+ (£920, 4 listings)
  - PowerColor Red Devil (£880, 3 listings)
  - XFX Speedster (£905, 5 listings)
  - Average = (920×4 + 880×3 + 905×5) / 12 = £902 → rounded to £899
- Tooltip displays aggregated data only: "RX 7900 XTX - £899 (Retail Avg) - 12 listings"
- **Special edition handling**: Factory overclocked models or water-cooled variants with significantly different specs (e.g., >10% clock speed difference or hybrid cooling) are treated as separate reference models
  - Example: "RX 7900 XTX" (standard) vs "RX 7900 XTX Aqua" (water-cooled)
  - Decision made on case-by-case basis when new SKUs are discovered during scraping

---

### Value Zone Highlighting (UPDATED v1.1)

**What**: Visual emphasis on used GPUs where the performance-per-pound represents a significant upgrade over retail options at the same or lower price—specifically, used GPUs that offer ≥10% better performance than retail GPUs at equal or lower cost.

**Why**: This is the core insight—identifying "tier jumping" opportunities where buyers can get a higher-tier GPU used for less than a lower-tier GPU new. Makes value opportunities impossible to miss.

**Behavior**:

**Algorithm** ("Tier Jumping" logic):
1. For each used GPU data point, calculate its performance score and price
2. Find all retail GPU data points with price ≥ usedPrice
3. If any retail GPU at equal or higher price has performance ≤ (usedPerformance - 10), the used GPU is a value zone candidate
4. Example:
   - Used RX 7900 XTX: £650, performance = 95
   - Retail RX 7800 XT: £499, performance = 75
   - Retail RX 7900 XT: £700, performance = 88
   - **Result**: RX 7900 XTX (used) IS in value zone because:
     - At £650, it offers perf=95
     - Retail 7900 XT at £700 (higher price) only offers perf=88
     - 95 > (88 + 10% of 88) = 95 > 96.8? NO, but...
     - Retail 7800 XT at £499 offers perf=75
     - User pays £151 more (30% increase) for 27% better performance (75→95)
     - This is "tier jumping"—getting high-end GPU for mid-range premium

**Simplified Implementation Logic**:
```csharp
// For each used GPU
foreach (var usedGpu in usedGpus) {
    // Find retail GPUs in similar or higher price range (within £100)
    var competingRetailGpus = retailGpus
        .Where(r => r.Price >= usedGpu.Price - 100 && r.Price <= usedGpu.Price + 100);
    
    // Check if used GPU has ≥10% better performance than any competing retail GPU
    var isValueZone = competingRetailGpus
        .Any(r => usedGpu.PerformanceScore >= r.PerformanceScore * 1.10);
    
    if (isValueZone) {
        usedGpu.HighlightAsValueZone = true;
    }
}
```

**Visual Treatment**:
- Value zone GPUs (used only) have additional visual emphasis:
  - Yellow/gold glow or border around the circle
  - Slightly larger circle size (+20% radius)
  - Optional: subtle animation (pulse effect on page load, stops after 3 seconds)
- Tooltip includes value zone explanation:
  - Standard tooltip content PLUS
  - Badge: "💎 VALUE OPPORTUNITY"
  - Subtext: "Better performance than similar-priced retail options"
- Value zones update dynamically as price data changes
- **Exclusions**:
  - Retail GPUs are NEVER highlighted as value zones (even if one retail option is cheaper than another)
  - Used GPUs with <3 listings are excluded from value zone calculation (see Low-Listing Handling)
  - Outlier-filtered listings do not contribute to value zone determination

**Edge Cases**:
- If no retail GPUs exist in similar price range (±£100), used GPU is not a value zone (can't compare)
- If all retail GPUs at similar price have similar or worse performance, used GPU is NOT a value zone (no "jumping" occurred)
- Value zone status is recalculated every time visualization loads (not cached separately)

---

### Low-Listing Handling (UPDATED v1.1)

**What**: GPUs with fewer than 3 listings display with a visual warning indicator and are excluded from value zone highlighting to avoid promoting unreliable deals.

**Why**: Small sample sizes (1-2 listings) are unreliable—could be typos, scams, or non-representative prices. Showing the data with a warning provides transparency while avoiding false recommendations.

**Behavior**:
- **Threshold**: Minimum 3 listings required for "reliable" data
  - Retail listings: minimum 3 (same threshold as used)
  - Used listings: minimum 3
  - Rationale: Retail prices are more stable, but requiring 3 ensures we're not showing a single outlier retailer
- **Visual Treatment** (for GPUs with <3 listings):
  - Data point appears on chart normally (same color, same badge)
  - Price displayed with asterisk: "£650*" or "£899*"
  - Opacity reduced to 70% (slightly faded vs. reliable data points)
  - Tooltip warning:
    - "⚠️ Limited data: Based on only 2 listings"
    - "Price may not be representative of market average"
- **Value Zone Exclusion**:
  - Used GPUs with <3 listings are excluded from value zone calculation
  - They appear on chart but are never highlighted with glow/border
  - Rationale: Conservative approach—don't promote deals based on insufficient data
- **Tooltip Content** (low-listing GPUs):
  - Model name: "AMD Radeon RX 7900 XTX"
  - Price with asterisk: "£650* (Used - Market Avg)"
  - Warning: "⚠️ Based on only 2 listings — price may be unreliable"
  - Listing count: "2 listings found"
  - Last updated: "Updated 3 hours ago"
  - Link: "View Official Specs →"
  - No "VALUE OPPORTUNITY" badge even if performance-per-pound is good
- **Count Display**:
  - Tooltip shows actual listing count: "2 listings" (not "2 valid listings, 0 excluded")
  - If outliers were filtered AND count is <3, count reflects valid listings only
  - Example: 4 listings found, 2 outliers excluded → shows "Based on 2 listings*" (triggers warning)

---

### Manufacturer Toggle Integration

**What**: When user toggles between Radeon and Nvidia (Feature 5), the entire visualization re-renders with the selected manufacturer's data.

**Why**: Cross-manufacturer comparison is explicitly out of scope. The dashboard must focus on one ecosystem at a time.

**Behavior**:
- Toggle control is above or beside the visualization (prominent placement)
- Selecting "Radeon" shows only AMD GPUs (RX 7000 series + RX 6000 series if "Show older GPUs" is checked)
- Selecting "Nvidia" shows only Nvidia GPUs (RTX 40 series + RTX 30 series if "Show older GPUs" is checked)
- Transition is smooth (200ms fade-out, data swap, 200ms fade-in—no jarring flash)
- All tooltips, labels, and data update instantly
- Chart axes may rescale if price ranges differ significantly between manufacturers:
  - Example: Radeon max price £950, Nvidia max price £1500 → X-axis rescales
  - Y-axis always 0-100 (performance score scale is consistent)
- User's selection persists (handled by Feature 5—browser localStorage)
- Value zones recalculate for selected manufacturer only

---

### Data Freshness Indicator (UPDATED v1.1)

**What**: Timestamp displayed prominently on the dashboard showing when price data was last updated, with no automatic real-time notifications.

**Why**: Users need to trust that they're seeing current market data, not stale information. However, scraping jobs run every 4-6 hours, so real-time push notifications are unnecessary complexity. Prominent timestamp + manual refresh is sufficient.

**Behavior**:
- **Display Location**: Top-right corner of visualization, above the chart
- **Format**: "Prices updated: 2 hours ago" (relative time, updated via JavaScript every 60 seconds)
- **Tooltip Hover**: Shows exact timestamp: "Last updated: 2025-01-10 14:32 UTC"
- **Staleness Warning**: If data is >24 hours old, display warning banner:
  - "⚠️ Price data is outdated — last update was 26 hours ago"
  - Background color: light yellow
  - Positioned above chart (does not obscure data)
- **Manual Refresh**: User can refresh browser to get latest data (no "Refresh Prices" button needed—browser refresh is sufficient)
- **No Automatic Notifications**:
  - Frontend does NOT poll for new data
  - Frontend does NOT use WebSockets or Server-Sent Events
  - If user has page open for 3 hours while scraping job completes, they see stale data until they manually refresh
  - Rationale: Simplifies architecture, avoids unnecessary server load, and scraping frequency (4-6 hours) doesn't justify real-time updates
- **API Response**: Timestamp comes from database field `GpuPriceSnapshot.LastUpdated` (updated by scraping jobs when prices refresh)

---

### GPU Display Limits (UPDATED v1.1)

**What**: All current-generation GPUs with available data are displayed by default, with no arbitrary cap. Previous-generation GPUs are hidden by default but can be toggled on.

**Why**: Current-gen Radeon lineup is ~12 models (RX 7000 series), Nvidia is ~15 (RTX 40 series). Total of ~25-30 data points (including retail + used duplicates) is well within modern visualization library capabilities. No need to artificially limit.

**Behavior**:
- **Default View (Current-Gen Only)**:
  - Radeon: RX 7000 series (7900 XTX, 7900 XT, 7900 GRE, 7800 XT, 7700 XT, 7600 XT, 7600)
  - Nvidia: RTX 40 series (4090, 4080 Super, 4080, 4070 Ti Super, 4070 Ti, 4070 Super, 4070, 4060 Ti, 4060)
  - Total data points: ~12-15 GPUs × 2 (retail + used) = 24-30 points maximum
- **"Show Older GPUs" Toggle**:
  - Checkbox above chart (next to manufacturer toggle)
  - When checked, adds previous-generation GPUs:
    - Radeon: RX 6000 series (6950 XT, 6900 XT, 6800 XT, 6800, 6750 XT, 6700 XT, 6650 XT, 6600 XT, 6600)
    - Nvidia: RTX 30 series (3090 Ti, 3090, 3080 Ti, 3080, 3070 Ti, 3070, 3060 Ti, 3060)
  - Total data points with older GPUs: ~50-60 points
  - User's selection persists via localStorage (Feature 5 mechanism)
- **No Hard Cap**:
  - If >60 data points are displayed, visualization may become crowded but remains functional
  - Modern libraries (Recharts, Plotly) handle 100+ points without performance issues
  - Monitor crowding post-launch; if users complain, add zoom/pan controls or filtering in v2
- **Chart Rescaling**:
  - X-axis (price) rescales automatically to fit data range
  - Y-axis (performance 0-100) remains fixed
  - If older GPUs have significantly different price ranges (e.g., RX 6600 at £150), X-axis adjusts accordingly

---

### Performance Requirements

**What**: Page must load and render the visualization in under 2 seconds on desktop with broadband.

**Why**: Slow-loading visualizations kill engagement. Users will leave if they wait >3 seconds.

**Behavior**:
- API endpoint `/api/v1/visualization/data?manufacturer=radeon&includeOlderGen=false` must respond in <500ms
- Aggregated price data is cached in Redis with 15-minute TTL (refreshed when scraping jobs complete)
- Cache key: `viz:radeon:current` or `viz:nvidia:current` (separate cache per manufacturer/generation combo)
- Frontend uses skeleton UI while data fetches (animated placeholder chart)
- Recharts library loads async (not in critical path)
- Initial page load includes inlined critical CSS; Recharts script loads async
- Target: Largest Contentful Paint (LCP) <1.5 seconds
- Measured via Lighthouse and RUM (Real User Monitoring)

---

### Responsive Design

**What**: Dashboard works on desktop (1920x1080 primary), tablet (768px+), and gracefully degrades on mobile (≥375px wide).

**Why**: Users may browse on tablets while shopping or share links on mobile. Desktop-first, but tablet must be usable.

**Behavior**:
- **Desktop (≥1200px)**:
  - Full visualization with all details visible
  - Hover interactions work (mouse cursor shows pointer on data points)
  - Tooltip appears on hover with 200ms delay
  - Chart dimensions: 1000px wide × 600px tall (or fills container)
- **Tablet (768px - 1199px)**:
  - Visualization scales down proportionally
  - Touch interactions replace hover:
    - Tap data point to show tooltip
    - Tap anywhere else (or another data point) to dismiss tooltip
    - No auto-dismiss timer
  - Chart dimensions: 700px wide × 500px tall
  - Font sizes slightly reduced (14px minimum)
  - Toggle controls stack vertically if needed
- **Mobile (375px - 767px)**:
  - Simplified visualization: scatter plot becomes vertical layout if too crowded
  - Alternative: Horizontal scrollable chart (pan left/right to see all data)
  - Touch targets ≥44px (data points may need larger radius)
  - Chart dimensions: Full width × 400px tall
  - Tooltip is modal-style overlay (full-width, bottom of screen) instead of hover popup
  - "Show older GPUs" toggle hidden by default (collapsible "Filters" section)
- **No Horizontal Scrolling**: Page content never exceeds viewport width (responsive layout)
- **Text Readability**: Minimum font size 14px on mobile, 16px on desktop

---

### Touch Interactions (UPDATED v1.1)

**What**: On touch devices (tablet and mobile), tapping a GPU data point shows its tooltip, and tapping anywhere else dismisses it.

**Why**: Hover doesn't exist on touch screens. Tap-to-show is the standard mobile pattern.

**Behavior**:
- **Desktop (Mouse Input)**:
  - Hover over data point → tooltip appears after 200ms delay
  - Move cursor away → tooltip disappears immediately
  - Click data point → no action (hover is sufficient)
- **Tablet/Mobile (Touch Input)**:
  - Tap data point → tooltip appears immediately (no delay)
  - Tooltip includes small "×" close button in top-right corner
  - Tap "×" button → tooltip dismisses
  - Tap another data point → current tooltip dismisses, new tooltip appears
  - Tap anywhere else on chart (empty space) → tooltip dismisses
  - Tap outside chart area → tooltip dismisses
- **Tooltip Content** (same for hover and tap):
  - Model name: "AMD Radeon RX 7900 XTX"
  - Price: "£899 (New - Retail Avg)" or "£650 (Used - Market Avg)"
  - Listing count: "Based on 12 listings" (or "2 listings*" if low-listing warning)
  - Last updated: "Updated 2 hours ago"
  - Value zone badge (if applicable): "💎 VALUE OPPORTUNITY"
  - Link: "View Official Specs →" (opens OEM page in new tab)
- **Multi-Touch**: No pinch-to-zoom support in v1 (standard browser zoom works)
- **Accessibility**: Touch targets are ≥44px per WCAG guidelines (data point radius may increase on mobile)

---

### Manufacturer Reference Links (UPDATED v1.1)

**What**: Each GPU tooltip includes a "View Official Specs" link that opens the OEM (AMD or Nvidia) product page in a new tab.

**Why**: Provides canonical source for detailed specs without cluttering the dashboard. Aligns with Feature 4's "manufacturer reference" concept and avoids appearance of favoritism toward specific retailers.

**Behavior**:
- **Link Text**: "View Official Specs →" (consistent across all GPUs)
- **Link Target**: OEM product page (examples):
  - AMD Radeon RX 7900 XTX → `https://www.amd.com/en/products/graphics/amd-radeon-rx-7900-xtx`
  - Nvidia RTX 4080 → `https://www.nvidia.com/en-gb/geforce/graphics-cards/40-series/rtx-4080-family/`
- **Link Behavior**:
  - Opens in new browser tab (`target="_blank"`)
  - Includes `rel="noopener noreferrer"` for security
  - No tracking parameters or affiliate codes
- **Fallback**: If OEM URL is unavailable in database, link is hidden (no broken links)
- **Database Schema**:
  - `GpuPerformanceTier` table includes `OemProductUrl` field (nullable)
  - URLs are seeded via migrations when performance scores are added
  - Example row:
    ```
    ModelId: "rx-7900-xtx"
    ModelName: "AMD Radeon RX 7900 XTX"
    PerformanceScore: 95
    OemProductUrl: "https://www.amd.com/en/products/graphics/amd-radeon-rx-7900-xtx"
    ```
- **Retail Links** (out of scope for v1):
  - No "Buy Now" or retailer links in tooltip
  - Feature 1 (Live Retail Price Aggregation) will provide retailer links in a separate view (future iteration)

---

### Visual Differentiation (UPDATED v1.1)

**What**: Retail and used price points are visually distinguished using color, icon badges, and accessibility-friendly patterns.

**Why**: Users must immediately understand whether a data point represents a new GPU (retail) or used GPU (market). Color alone is insufficient for colorblind users (WCAG AA compliance).

**Behavior**:

**Color Scheme**:
- **Retail (New)**: Blue (#3B82F6)
- **Used (Market)**: Green (#10B981)
- **Value Zone Highlight**: Yellow/gold glow (#FBBF24 with 40% opacity halo)

**Icon Badges**:
- **Retail**: Small "NEW" text badge overlaid on top of circle
  - Badge size: 32px × 16px
  - Background: White with blue border
  - Text: "NEW" in 10px bold font
  - Positioned: Top-center of circle, slightly overlapping
- **Used**: Small "USED" text badge overlaid on top of circle
  - Badge size: 40px × 16px
  - Background: White with green border
  - Text: "USED" in 10px bold font
  - Positioned: Top-center of circle, slightly overlapping

**Shape/Pattern** (for colorblind accessibility):
- Retail circles: Solid fill
- Used circles: Solid fill with subtle dot pattern texture (2px dots, 4px spacing)
- Pattern is subtle enough to not interfere with readability but distinct enough to differentiate

**Circle Sizing**:
- Standard data points: 24px diameter
- Low-listing data points (<3): 24px diameter, 70% opacity
- Value zone data points: 30px diameter (+25% size increase), yellow glow

**Hover/Focus State**:
- Hover (desktop): Circle scales to 28px diameter (+20%), cursor changes to pointer
- Focus (keyboard): 2px solid black outline (WCAG focus indicator)

**Legend**:
- Positioned below chart
- Shows:
  - 🔵 NEW (Retail Average)
  - 🟢 USED (Market Average)
  - ✨ VALUE OPPORTUNITY (better performance for price)
  - ⚠️ * Limited data (<3 listings)

**Accessibility Compliance**:
- Color contrast ratio: Blue/green on white background meets WCAG AA (4.5:1 minimum)
- Color is not the only differentiator (badges + text + pattern)
- Focus indicators are visible for keyboard navigation
- Alt text for screen readers: "Scatter plot showing GPU performance versus price, with retail and used market data"

---

### Y-Axis Labeling (UPDATED v1.1)

**What**: Y-axis displays numeric performance scores (0-100 scale) with clear labeling that this is a relative measure, not FPS or benchmark data.

**Why**: Users expect quantifiable data in a dashboard. Numeric scores are more precise than vague labels like "High-End" or "Mid-Range." As long as axis is clearly labeled as relative, it avoids misinterpretation.

**Behavior**:
- **Y-Axis Scale**: 0 to 100 (fixed range, does not rescale)
- **Y-Axis Ticks**: 0, 25, 50, 75, 100 (evenly spaced)
- **Y-Axis Label**: "Performance Score (relative)" positioned vertically along axis
- **Axis Title Styling**:
  - Font size: 14px
  - Color: Gray (#6B7280)
  - Positioned: Left side of chart, rotated 90° counterclockwise
- **Tooltip Clarification**: When user hovers over axis label, tooltip appears:
  - "Performance scores are relative rankings based on GPU generation, tier, and VRAM. They do not represent FPS or benchmark results."
- **FAQ Link** (below chart):
  - "How are performance scores calculated?" → Links to FAQ page explaining ordinal ranking methodology
- **No Benchmark Data**:
  - No FPS numbers displayed anywhere
  - No PassMark, 3DMark, or other third-party scores
  - Tooltip shows only: model name, price, listing count, update time, OEM link
  - Performance score is visible only on Y-axis and in backend database (not in tooltip)

---

## Data Model (UPDATED v1.1)

**Entities This Feature Needs**:

### GpuPerformanceTier
Stores manually-assigned performance scores for GPU reference models. Seeded via Entity Framework Core migrations.

**Fields**:
- `ModelId` (string, PK): Unique identifier, e.g., "rx-7900-xtx"
- `Manufacturer` (enum): Radeon | Nvidia
- `Generation` (string): "RX 7000" | "RTX 40" | "RX 6000" | "RTX 30"
- `ReferenceName` (string): "AMD Radeon RX 7900 XTX" (display name)
- `PerformanceScore` (int): 1-100 scale, manually assigned
- `VramGB` (int): 24, 16, 12, etc.
- `OemProductUrl` (string, nullable): Link to AMD/Nvidia product page
- `IsCurrentGen` (bool): True for RX 7000 / RTX 40, False for older
- `CreatedAt` (DateTime): When record was seeded
- `UpdatedAt` (DateTime): When score/URL was last modified

**Example Rows**:
```
ModelId: "rx-7900-xtx"
Manufacturer: Radeon
Generation: "RX 7000"
ReferenceName: "AMD Radeon RX 7900 XTX"
PerformanceScore: 95
VramGB: 24
OemProductUrl: "https://www.amd.com/en/products/graphics/amd-radeon-rx-7900-xtx"
IsCurrentGen: true
```

```
ModelId: "rtx-4080"
Manufacturer: Nvidia
Generation: "RTX 40"
ReferenceName: "Nvidia GeForce RTX 4080"
PerformanceScore: 92
VramGB: 16
OemProductUrl: "https://www.nvidia.com/en-gb/geforce/graphics-cards/40-series/rtx-4080-family/"
IsCurrentGen: true
```

---

### GpuPriceSnapshot
Aggregated price data for a GPU reference model at a point in time. Regenerated by scraping jobs every 4-6 hours.

**Fields**:
- `Id` (int, PK): Auto-increment
- `ModelId` (string, FK → GpuPerformanceTier): Links to performance tier
- `Manufacturer` (enum): Radeon | Nvidia (denormalized for faster queries)
- `AverageRetailPrice` (decimal?, nullable): Average price from retail listings (GBP), null if no retail data
- `RetailListingCount` (int): Number of valid retail listings (after outlier filtering)
- `RetailOutlierCount` (int): Number of retail listings excluded as outliers
- `AverageUsedPrice` (decimal?, nullable): Average price from used listings (GBP), null if no used data
- `UsedListingCount` (int): Number of valid used listings (after outlier filtering)
- `UsedOutlierCount` (int): Number of used listings excluded as outliers
- `IsValueZone` (bool): True if used GPU meets value zone criteria (calculated at snapshot creation)
- `LastUpdated` (DateTime): When scraping job completed and snapshot was created
- `SnapshotVersion` (int): Increments with each scraping job (for tracking history)

**Example Row**:
```
Id: 123
ModelId: "rx-7900-xtx"
Manufacturer: Radeon
AverageRetailPrice: 899.00
RetailListingCount: 12
RetailOutlierCount: 1
AverageUsedPrice: 650.00
UsedListingCount: 8
UsedOutlierCount: 2
IsValueZone: true
LastUpdated: 2025-01-10 14:32:00 UTC
SnapshotVersion: 47
```

---

### VisualizationCache (Redis)
Pre-calculated JSON payload for frontend visualization. Regenerated when scraping jobs complete.

**Cache Keys**:
- `viz:radeon:current` → JSON for Radeon current-gen GPUs
- `viz:radeon:all` → JSON for Radeon current-gen + previous-gen GPUs
- `viz:nvidia:current` → JSON for Nvidia current-gen GPUs
- `viz:nvidia:all` → JSON for Nvidia current-gen + previous-gen GPUs

**Cache Value (JSON structure)**:
```json
{
  "manufacturer": "Radeon",
  "includeOlderGen": false,
  "lastUpdated": "2025-01-10T14:32:00Z",
  "dataPoints": [
    {
      "modelId": "rx-7900-xtx",
      "modelName": "AMD Radeon RX 7900 XTX",
      "performanceScore": 95,
      "retailPrice": 899.00,
      "retailListingCount": 12,
      "retailHasLowListings": false,
      "usedPrice": 650.00,
      "usedListingCount": 8,
      "usedHasLowListings": false,
      "isValueZone": true,
      "oemProductUrl": "https://www.amd.com/en/products/graphics/amd-radeon-rx-7900-xtx"
    },
    {
      "modelId": "rx-7800-xt",
      "modelName": "AMD Radeon RX 7800 XT",
      "performanceScore": 75,
      "retailPrice": 499.00,
      "retailListingCount": 15,
      "retailHasLowListings": false,
      "usedPrice": 420.00,
      "usedListingCount": 2,
      "usedHasLowListings": true,
      "isValueZone": false,
      "oemProductUrl": "https://www.amd.com/en/products/graphics/amd-radeon-rx-7800-xt"
    }
  ]
}
```

**Cache Invalidation**:
- TTL: 15 minutes (to handle race conditions during scraping)
- Regenerated immediately when scraping job completes (via Hangfire job)
- Cache miss fallback: Query database directly (slower but functional)

---

**Key Relationships**:
- `GpuPriceSnapshot.ModelId` → `GpuPerformanceTier.ModelId` (many-to-one)
- `GpuListing` (from Features 1/2) → `GpuPerformanceTier.ModelId` (many-to-one) for aggregation
- Frontend API calls Redis first, falls back to DB query if cache miss

---

## User Experience Flow

1. User lands on the homepage, sees prominent toggle: **Radeon | Nvidia** (Radeon selected by default) and checkbox: **☐ Show older GPUs** (unchecked by default)
2. Page loads visualization showing Radeon RX 7000 series GPU price/performance scatter plot
3. Chart displays:
   - X-axis: Price (£0 - £1000)
   - Y-axis: Performance Score (0-100, labeled "Performance Score (relative)")
   - ~12 GPU models, most with two data points each (retail + used)
   - Example data points visible:
     - RX 7900 XTX: Blue circle at (£899, 95) labeled "NEW", green circle at (£650, 95) labeled "USED" with yellow glow (value zone)
     - RX 7800 XT: Blue circle at (£499, 75) labeled "NEW", green circle at (£420*, 75) labeled "USED" with asterisk (low listings)
   - Timestamp in top-right: "Prices updated: 2 hours ago"
4. User hovers over used RX 7900 XTX (green circle with glow) → Tooltip appears:
   - "AMD Radeon RX 7900 XTX"
   - "£650 (Used - Market Avg)"
   - "💎 VALUE OPPORTUNITY"
   - "Based on 8 listings"
   - "Updated 2 hours ago"
   - "View Official Specs →"
5. User clicks "View Official Specs" → Opens AMD product page in new tab
6. User returns to dashboard, hovers over used RX 7800 XT (green circle with asterisk) → Tooltip shows:
   - "AMD Radeon RX 7800 XT"
   - "£420* (Used - Market Avg)"
   - "⚠️ Based on only 2 listings — price may be unreliable"
   - "2 listings found"
   - "Updated 2 hours ago"
   - "View Official Specs →"
7. User toggles to **Nvidia** → Visualization smoothly fades out (200ms), data changes, fades in (200ms)
8. Chart now shows Nvidia RTX 40 series GPUs (RTX 4090, 4080, 4070 Ti, etc.) with similar retail + used data points
9. User checks **☐ Show older GPUs** → Chart updates to include RTX 30 series (3090, 3080, 3070, etc.), X-axis rescales to accommodate wider price range
10. User identifies multiple value opportunities (used RTX 4080 at £800, used 3090 at £600), reviews specs via OEM links, leaves site to purchase

---

## Edge Cases & Constraints

- **No data for a GPU model**: If a GPU reference model has no retail or used listings (both null), it doesn't appear on the chart
- **Only one price type available**: If only retail OR only used data exists, GPU appears as single data point (blue or green circle, no dual representation)
- **Extreme outliers in used market**: Prices >2x median for used, >1.5x median for retail are filtered before calculating average—excluded from average calculation AND listing count
  - Example: 12 used listings found, 2 are outliers → Tooltip shows "Based on 10 valid listings (2 outliers excluded)"
- **Very few listings**: If <3 listings exist for a GPU, show price with asterisk (*), reduce opacity to 70%, display warning tooltip, and exclude from value zone highlighting
- **Chart overcrowding**: With "Show older GPUs" enabled, may display 50-60 data points—chart remains functional but could feel busy. Monitor user feedback post-launch; if complaints, add zoom/pan controls or generation filtering in v2
- **Data refresh mid-session**: If user has page open while scraping job completes, they continue seeing cached data until they manually refresh browser. No automatic notification or polling (by design—see Data Freshness Indicator section)
- **Browser compatibility**: Support latest 2 versions of Chrome, Firefox, Safari, Edge. No IE11 support (IE11 market share <1% in UK as of 2025)
- **No value zones for retail**: Retail GPUs are never highlighted as value zones, even if one retail option is significantly cheaper than another retail option (value zones are used-market-only feature)
- **Value zone with low listings**: If a used GPU has <3 listings, it's excluded from value zone calculation even if its performance-per-pound is excellent (conservative approach to avoid false positives)
- **Missing OEM URL**: If `GpuPerformanceTier.OemProductUrl` is null, tooltip does not display "View Official Specs" link (graceful degradation)
- **Special edition GPUs**: Factory overclocked or water-cooled variants with >10% spec difference are treated as separate reference models (e.g., "RX 7900 XTX Aqua" is distinct from "RX 7900 XTX")—decided case-by-case during scraping data normalization
- **Timezone handling**: All timestamps are stored and displayed in UTC, converted to user's local timezone via JavaScript `toLocaleString()` for display

---

## Out of Scope for This Feature

The following are explicitly NOT part of the Value Visualization Dashboard in v1:

- **Historical price trends**: No "price over time" graphs, trend lines, or historical data display
- **User-saved comparisons**: No ability to save, bookmark, or create custom comparison sets of specific GPUs
- **Custom performance weighting**: Users cannot adjust what "performance" means (e.g., prioritize VRAM vs. clock speed) or provide their own scores
- **Filtering by price range**: No sliders to filter "show only GPUs £400-£600"—entire dataset for selected manufacturer/generation is visible
- **Comparison with other hardware**: No CPU, RAM, PSU, or motherboard recommendations based on selected GPU
- **Third-party benchmark integration**: No FPS data, PassMark scores, 3DMark results, or review aggregation
- **Export to PDF/image**: No ability to download or share the visualization as an image or PDF
- **Animated transitions on data update**: Visualization re-renders when data refreshes but doesn't animate points moving from old to new positions (fade-out/fade-in only)
- **Zoom/pan controls**: No interactive zoom or pan functionality in v1 (browser zoom works, but no custom controls)
- **Drill-down to manufacturer SKUs**: No ability to expand a reference model to see individual SKUs (Sapphire vs PowerColor variants)—aggregated data only
- **Price alerts**: No ability to set "notify me when RX 7900 XTX drops below £600" alerts
- **Retailer links in tooltip**: No "Buy Now" or retailer-specific links in v1 (Feature 1 will provide this in separate view)
- **Cross-manufacturer comparison**: No ability to view Radeon + Nvidia on same chart simultaneously (manufacturer toggle is exclusive)
- **Generation filtering**: "Show older GPUs" is binary (all or none)—cannot show "only RX 6900 XT and RX 7900 XTX" (too complex for v1)
- **User customization**: No ability to change color scheme, chart type (scatter plot only), or visualization style

---

## Q&A History

### Iteration 1 - 2025-01-10

**Q1: How is the GPU Performance Score calculated and maintained?**  
**A**: **Simple Ordinal Ranking (Option A)** is chosen. Each GPU reference model receives a manually-assigned integer score (1-100 scale) determined by product team based on GPU generation, model tier, and VRAM. Scores are stored in `GpuPerformanceTier` database table, seeded via Entity Framework Core migrations. When new GPUs release, product team provides scores via Slack/email, and engineering adds them via migration. This approach gives product full control over positioning, avoids benchmark scraping (out of scope), and is easy to debug and maintain.

**Example scoring**: RX 7900 XTX = 95, RX 7900 XT = 88, RX 7800 XT = 75, RX 7700 XT = 68, RX 7600 XT = 55, RX 7600 = 50.

**Database storage**: Preferred over hardcoding because it allows score updates without code deployment and supports potential future UI for non-technical staff to manage scores.

---

**Q2: What defines a "value zone" algorithmically?**  
**A**: **Option C (Tier Jumping)** is chosen. A used GPU is highlighted as a value zone if it offers ≥10% better performance than retail GPUs at the same or lower price. Specifically: `usedGpuPerformance >= (retailGpuPerformance + 10%)` AND `usedPrice <= retailPrice`.

**Example**: Used RX 7900 XTX at £650 (perf=95) vs. Retail RX 7900 XT at £700 (perf=88) → RX 7900 XTX is highlighted because it offers 7.9% higher performance for 7.1% lower cost (user "jumps" to a higher tier GPU for less money).

**Rationale**: This approach is easy to explain to users ("get a higher-tier GPU for less"), visually clear, and aligns with the "wow factor" goal. Threshold of +10% performance catches meaningful upgrades without highlighting marginal deals.

**Exclusivity**: Value zones are exclusive to used GPUs. Retail GPUs are never highlighted, even if one retail option is significantly better value than another retail option.

---

**Q3: What is the granularity of GPU models in the visualization?**  
**A**: **Option A (Aggregate by Reference Model)** is chosen. All manufacturer-specific SKUs (Sapphire Nitro+, PowerColor Red Devil, XFX Speedster, etc.) are averaged into a single "reference model" data point (e.g., "RX 7900 XTX").

**Rationale**: Users shopping for GPUs think in terms of "7900 XTX" or "RTX 4080," not specific manufacturer variants. Aggregation keeps the visualization uncluttered (10-15 points instead of 50+) and easier to compare. SKU-level detail can be explored via linked listing pages (Features 1/2) in future iterations.

**Database schema**: `GpuModel.ReferenceName` = "RX 7900 XTX", all SKUs roll up to this field for aggregation.

**Special editions**: Factory overclocked models or water-cooled variants with significantly different specs (>10% clock speed difference or hybrid cooling) are treated as separate reference models on a case-by-case basis (e.g., "RX 7900 XTX Aqua" is distinct from standard "RX 7900 XTX").

---

**Q4: Can a GPU model appear at multiple price points simultaneously (retail + used)?**  
**A**: **Option A (Always Show Both If Data Exists)** is chosen. Every GPU with both retail and used data appears as two distinct visual elements on the chart.

**Rationale**: This is the core value proposition—seeing the gap between retail and used prices. Dual representation makes the price difference visually obvious and emphasizes potential savings. Chart crowding is manageable with current-gen GPU counts (~25-30 data points total).

**Visual connection**: The two points are vertically aligned (same Y-position for performance score) but horizontally offset (different X-positions for price). They share the same model name but have different color/badge (blue "NEW" vs. green "USED"). No line connects them (to avoid visual clutter), but shared Y-position implies they're the same GPU model.

---

**Q5: What happens when there are fewer than 3 listings for a GPU model?**  
**A**: **Option B (Show With Warning, Exclude From Value Zones)** is chosen. GPU appears on chart with visual warning (asterisk, reduced opacity, tooltip disclaimer) but is never highlighted as a value opportunity.

**Rationale**: Balances transparency (users see the data) with caution (we don't highlight unreliable deals). Users can still assess the data and click through to listings (Features 1/2) if they want to investigate further.

**Threshold**: Minimum 3 listings applies to both retail and used data (same threshold). Even though retail prices are more stable, requiring 3 ensures we're not showing a single outlier retailer.

**Visual treatment**: Price displayed with asterisk (£650*), opacity reduced to 70%, tooltip shows "⚠️ Based on only 2 listings — price may be unreliable."

---

**Q6: How should the visualization handle extreme outliers in pricing?**  
**A**: **Option A (Filter Outliers From Average Calculation Only)** is chosen. Outliers are removed before calculating average price, but individual outlier listings remain visible if users navigate to full listing pages (Features 1/2).

**Outlier definition**:
- Used prices: Exclude any listing >2x the median price for that model
- Retail prices: Exclude any listing >1.5x the median price for that model (retail should be more stable)

**Rationale**: Keeps visualization clean (average is accurate) while preserving data integrity (all listings remain accessible). Tooltip displays "Based on 12 valid listings (3 outliers excluded)" to explain the filtering.

**Admin/debug view**: Out of scope for v1. If data quality monitoring becomes necessary, add admin-only outlier dashboard in v2.

---

**Q7: When data refreshes, how are users notified if they have the page open?**  
**A**: **Option C (No Automatic Notification)** is chosen. User sees stale data until they manually refresh browser.

**Rationale**: Scraping jobs run every 4-6 hours (typical for price aggregation), so real-time updates aren't critical. Prominent timestamp ("Prices updated: 2 hours ago") lets users decide if they want to refresh. Avoids polling/WebSocket complexity and unnecessary server load.

**Manual refresh**: Browser refresh is sufficient—no custom "Refresh Prices" button needed.

**Staleness warning**: If data is >24 hours old, display yellow warning banner: "⚠️ Price data is outdated — last update was 26 hours ago."

---

**Q8: What is the maximum number of GPU models displayed simultaneously?**  
**A**: **Option A (No Limit, Optimize for Scalability)** is chosen. All GPUs with available data are shown, with no arbitrary cap.

**Rationale**: Current-gen Radeon lineup is ~12 models (RX 7000 series), Nvidia is ~15 (RTX 40 series). Even with retail + used duplicates, unlikely to exceed 25-30 data points. Modern visualization libraries (Recharts) handle 50-100 points easily. If crowding becomes an issue post-launch, add zoom/pan controls or filtering in v2.

**Previous-gen handling**: RX 6000 / RTX 30 series are hidden by default but can be toggled on via "Show older GPUs" checkbox. This adds ~20 more models, bringing total to ~50-60 data points when enabled.

---

**Q9: How should "tooltip on hover" work on touch devices (tablet)?**  
**A**: **Option A (Tap to Show, Tap Anywhere Else to Dismiss)** is chosen.

**Behavior**: Tapping a GPU data point shows tooltip. Tapping elsewhere (or another data point) dismisses the current tooltip and shows the new one. Tooltip includes small "×" button for explicit dismissal.

**Rationale**: Standard mobile pattern users expect. Allows comparing multiple GPUs by tapping between them. Auto-dismiss (Option C) is frustrating for users trying to read detailed tooltips.

---

**Q10: Should the "Official Specs" link in the tooltip open OEM page or reference page?**  
**A**: **Option A (OEM Product Page)** is chosen. Link opens AMD or Nvidia official product page (e.g., `https://www.amd.com/en/products/graphics/amd-radeon-rx-7900-xtx`).

**Rationale**: Aligns with Feature 4's "manufacturer reference" concept and provides canonical source for detailed specs. Avoids appearance of favoritism toward specific retailers. Users can't buy directly from OEM pages, but that's acceptable—retail listing links will be accessible via Feature 1 in a separate flow (future iteration).

---

**Q11: What visual treatment distinguishes retail from used price points?**  
**A**: **Option C (Icon + Color)** is chosen.

**Visual treatment**:
- Retail: Solid blue circle (#3B82F6) with "NEW" badge overlay (white background, blue border, 10px font)
- Used: Solid green circle (#10B981) with "USED" badge overlay (white background, green border, 10px font)
- Value zones: Yellow/gold glow (#FBBF24 with 40% opacity halo) around used circles
- Additional: Used circles have subtle dot pattern texture (2px dots, 4px spacing) for colorblind accessibility

**Rationale**: Meets WCAG AA compliance (color + text + pattern as differentiators), immediately clear to users, and works well in screenshots/marketing. Badges are small (32px × 16px) to avoid clutter.

---

**Q12: Should the Y-axis (performance) show numeric scores or just relative positioning?**  
**A**: **Option A (Show Numeric Performance Scores)** is chosen.

**Y-axis display**:
- Scale: 0 to 100 (fixed range)
- Ticks: 0, 25, 50, 75, 100
- Label: "Performance Score (relative)" positioned vertically along axis
- Tooltip on hover: "Performance scores are relative rankings based on GPU generation, tier, and VRAM. They do not represent FPS or benchmark results."

**Rationale**: Users expect quantifiable data in a dashboard. Numeric scores are more precise than vague labels like "High-End" or "Mid-Range." As long as axis is clearly labeled as "(relative)" and FAQ/docs explain it's not a benchmark, it's the most useful option. Avoids ambiguity.

**FAQ link**: Below chart, "How are performance scores calculated?" links to FAQ page explaining ordinal ranking methodology.

---

## Product Rationale

### Why Simple Ordinal Ranking for Performance Scores?

**User Need**: Users need to understand relative GPU capabilities without diving into technical benchmark comparisons. They think in terms of "high-end vs. mid-range," not "12,450 PassMark score."

**Business Goal**: Avoid legal/licensing issues from scraping third-party benchmark data. Maintain editorial independence by controlling our own performance hierarchy.

**Constraints**: No in-house benchmark testing capacity. Must rely on publicly known GPU hierarchies (which are well-established in PC building community).

**Decision**: Manually-assigned 1-100 scores give us control, flexibility, and avoid external dependencies. Product team can adjust scores based on community consensus or VRAM/generation tiers. Simple to maintain via database migrations.

---

### Why "Tier Jumping" Value Zone Logic?

**User Need**: Users want to know "Can I get a better GPU used for the same price as a worse GPU new?" This is the core value proposition of comparing retail vs. used markets.

**Business Goal**: Highlight genuinely valuable deals without overwhelming users with marginal highlights. Every highlighted GPU should feel like a "discovery."

**Constraints**: Performance scores are ordinal (not ratio scale), so calculating exact "value per pound" is imprecise. Need a simple heuristic that's defensible.

**Decision**: "10% better performance at same/lower price" is a meaningful threshold. It catches clear upgrades (e.g., used 7900 XTX vs. new 7800 XT) while filtering noise. Easy to explain in marketing: "Get a higher-tier GPU for less."

---

### Why Aggregate by Reference Model (Not Manufacturer SKU)?

**User Need**: Users shopping for GPUs think in terms of chipset/model ("I want a 7900 XTX"), not specific brands ("I want a Sapphire Nitro+ specifically"). Brand preference is secondary to price and availability.

**Business Goal**: Keep visualization clean and comparative. Showing 50+ SKUs would overwhelm users and obscure patterns.

**Constraints**: Different manufacturers have different pricing and availability, but those differences are usually <5% and don't affect purchase decisions significantly.

**Decision**: Aggregate all SKUs into reference models. Users see "7900 XTX averages £899" and can explore individual retailer listings (Features 1/2) if they want SKU detail. Simplifies visualization without losing critical information.

---

### Why Always Show Both Retail + Used (If Data Exists)?

**User Need**: Users need to immediately see the price gap between new and used to assess whether buying used is worth it. Hiding one or the other obscures this comparison.

**Business Goal**: The "wow factor" comes from seeing dramatic price differences (e.g., "£899 new vs. £650 used for the same GPU"). Dual representation makes this impossible to miss.

**Constraints**: Chart could get crowded with 50+ data points (25 GPUs × 2 prices each).

**Decision**: Dual display is the core feature—crowding is acceptable because current-gen GPU counts are manageable (~25-30 points). Monitor post-launch; if crowding is an issue, add zoom/pan in v2. Don't sacrifice core value prop for a hypothetical problem.

---

### Why Exclude Low-Listing GPUs From Value Zones?

**User Need**: Users trust our recommendations. Highlighting a "value opportunity" based on 1-2 listings could lead to disappointment if those listings are scams, typos, or non-representative.

**Business Goal**: Build credibility by being conservative with highlights. Better to miss a real deal than promote a false one.

**Constraints**: Small sample sizes (n<3) have high variance. A single outlier can skew the average dramatically.

**Decision**: Show low-listing data transparently (with asterisk and warning) but never highlight it as a value zone. Users can investigate if curious, but we don't endorse it. Threshold of 3 listings is industry-standard minimum for basic statistical reliability.

---

### Why No Real-Time Update Notifications?

**User Need**: Users want recent data but don't need second-by-second updates. GPU prices change slowly (hours to days), not rapidly (minutes).

**Business Goal**: Keep architecture simple. Avoid WebSocket infrastructure, polling overhead, and notification UX complexity.

**Constraints**: Scraping jobs run every 4-6 hours. Real-time updates would only matter if data refreshed every 5-10 minutes.

**Decision**: Prominent timestamp + manual refresh is sufficient. Users can see "Prices updated 2 hours ago" and decide if they need to refresh. If scraping frequency increases in v2 (e.g., hourly), revisit this decision.

---

### Why Recharts Over D3.js or Plotly?

**Technical Need**: Visualization library must support scatter plots, custom tooltips, touch interactions, and responsive design. Must integrate cleanly with React + TypeScript.

**Business Goal**: Ship quickly without over-engineering. Prefer "boring technology that works" over cutting-edge complexity.

**Constraints**:
- D3.js: Extremely flexible but heavy (200KB+), steep learning curve, requires custom touch handling
- Plotly: Feature-rich (3D, animations) but large bundle size (1MB+), overkill for simple scatter plot
- Recharts: React-native, TypeScript support, 50KB bundle, simple API, handles 50-100 data points easily

**Decision**: Recharts is the pragmatic choice for v1. Provides everything we need (scatter plot, tooltips, responsive) without D3's complexity or Plotly's bloat. If we need advanced features in v2 (zoom/pan, animations), we can migrate then—but start simple.

---

### Why Icon + Color + Pattern for Visual Differentiation?

**User Need**: Users must instantly distinguish retail from used data points, including users with color blindness (8% of male population).

**Business Goal**: WCAG AA compliance is a legal requirement in UK. Accessibility is also good UX—benefits everyone.

**Constraints**: Color alone fails for colorblind users. Shape alone is less intuitive. Text alone is hard to see on small data points.

**Decision**: Combine all three (color + badge text + dot pattern texture). This ensures:
- Color-sighted users see blue vs. green instantly
- Colorblind users see "NEW" vs. "USED" badge text
- Screen reader users hear alt text describing the chart
- Pattern texture provides additional tactile differentiation

Triple redundancy ensures no user is excluded.

---

### Why Show Numeric Y-Axis Scores Instead of Tier Labels?

**User Need**: Users want precision. "Mid-range" is vague—does that mean £400 or £600? Score of 75 is unambiguous.

**Business Goal**: Dashboard should feel data-driven and authoritative. Numeric scores convey precision and expertise.

**Constraints**: Scores could be misinterpreted as FPS or benchmark results.

**Decision**: Show numeric scores with clear labeling: "Performance Score (relative)". Axis label disclaimer + FAQ link clarify this is not benchmark data. Precision outweighs misinterpretation risk as long as we're transparent about methodology.

---

## Open Questions for Tech Lead (RESOLVED)

All critical questions from Iteration 1 have been answered. No blocking questions remain.

**Resolved**:
1. ✅ Performance score calculation: Simple Ordinal Ranking, database-stored, manually maintained
2. ✅ Value zone definition: Tier Jumping logic (≥10% better performance at ≤ same price)
3. ✅ Model granularity: Aggregate by reference model (not SKU)
4. ✅ Dual price display: Always show both retail + used if data exists
5. ✅ Low-listing handling: Show with warning, exclude from value zones
6. ✅ Outlier filtering: Filter from average calculation, keep in linked listings
7. ✅ Visualization library: Recharts
8. ✅ Real-time updates: No automatic notifications, manual refresh only
9. ✅ Display limits: No hard cap, show all current-gen by default
10. ✅ Touch interactions: Tap to show, tap elsewhere to dismiss
11. ✅ Link strategy: OEM product page (not retailer links)
12. ✅ Visual differentiation: Color + icon badges + pattern texture
13. ✅ Y-axis labeling: Numeric scores (0-100) with "(relative)" label

**New Questions** (if any arise during implementation):
- None at this time. Proceed with implementation.

---

## Dependencies

**Depends On**:
- Feature 1: Live Retail Price Aggregation (provides retail price data via API endpoint `/api/v1/prices/retail`)
- Feature 2: Used Market Price Discovery (provides used price data via API endpoint `/api/v1/prices/used`)
- Feature 5: Radeon vs Nvidia Mode Switching (manufacturer toggle functionality + localStorage persistence)

**Enables**:
- Feature 4: Manufacturer Reference Links (OEM links displayed within visualization tooltips—this feature provides the UI, Feature 4 provides the URL data)

**Critical Path**: 
- Backend: Features 1 and 2 must provide aggregated price data before visualization API can be built
- Frontend: Feature 5's toggle component must be built in parallel (can mock toggle while visualization is being developed)
- Database: `GpuPerformanceTier` table must be seeded with initial performance scores before visualization can render (blocking migration)

**API Contracts Required** (from Features 1/2):
- `GET /api/v1/prices/retail?manufacturer=radeon&includeOlderGen=false`
  - Returns: List of retail price snapshots by GPU model
- `GET /api/v1/prices/used?manufacturer=radeon&includeOlderGen=false`
  - Returns: List of used price snapshots by GPU model
- Both endpoints must return: `ModelId`, `AveragePrice`, `ListingCount`, `OutlierCount`, `LastUpdated`

**Integration Points**:
- Feature 5 provides: `useManufacturerToggle()` React hook that returns current manufacturer selection
- This feature consumes: Manufacturer selection to filter visualization data
- This feature provides: Visual display of toggled manufacturer's GPU data

---

## Implementation Notes

### Database Migration Priority

**High Priority** (blocks development):
1. Create `GpuPerformanceTier` table via EF Core migration
2. Seed initial performance scores for RX 7000 series (7 models minimum)
3. Seed initial performance scores for RTX 40 series (9 models minimum)
4. Seed OEM product URLs for all seeded models

**Medium Priority** (needed before launch):
1. Seed performance scores for RX 6000 series (for "Show older GPUs" toggle)
2. Seed performance scores for RTX 30 series
3. Add indexes on `GpuPerformanceTier.Manufacturer` and `IsCurrentGen` for fast filtering

**Example Migration Seed Data**:
```csharp
migrationBuilder.InsertData(
    table: "GpuPerformanceTier",
    columns: new[] { "ModelId", "Manufacturer", "Generation", "ReferenceName", "PerformanceScore", "VramGB", "OemProductUrl", "IsCurrentGen" },
    values: new object[,]
    {
        { "rx-7900-xtx", "Radeon", "RX 7000", "AMD Radeon RX 7900 XTX", 95, 24, "https://www.amd.com/en/products/graphics/amd-radeon-rx-7900-xtx", true },
        { "rx-7900-xt", "Radeon", "RX 7000", "AMD Radeon RX 7900 XT", 88, 20, "https://www.amd.com/en/products/graphics/amd-radeon-rx-7900-xt", true },
        { "rx-7800-xt", "Radeon", "RX 7000", "AMD Radeon RX 7800 XT", 75, 16, "https://www.amd.com/en/products/graphics/amd-radeon-rx-7800-xt", true },
        // ... additional rows
    });
```

---

### API Endpoint Specification

**Endpoint**: `GET /api/v1/visualization/data`

**Query Parameters**:
- `manufacturer` (required): "radeon" | "nvidia"
- `includeOlderGen` (optional): "true" | "false" (default: false)

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
      "oemProductUrl": "https://www.amd.com/en/products/graphics/amd-radeon-rx-7900-xtx"
    }
  ]
}
```

**Response** (304 Not Modified): If client sends `If-None-Match` header matching current ETag

**Response** (400 Bad Request): If `manufacturer` parameter is invalid

**Response** (503 Service Unavailable): If Redis cache is down and database query times out

**Caching Headers**:
- `ETag`: Hash of `lastUpdated` timestamp
- `Cache-Control`: `public, max-age=300` (5 minutes client-side cache)

---

### Frontend Component Structure

**Proposed React Component Hierarchy**:
```
<VisualizationDashboard>
  ├─ <DashboardHeader>
  │   ├─ <ManufacturerToggle> (from Feature 5)
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
- Use TanStack Query for data fetching (`useQuery` with 5-minute stale time)
- Use Feature 5's `useManufacturerToggle()` hook for manufacturer selection
- Use local state for `includeOlderGen` checkbox (persist to localStorage)

---

### Testing Checklist

**Unit Tests** (Backend):
- [ ] Value zone calculation logic with various performance/price combinations
- [ ] Outlier filtering logic (>2x median for used, >1.5x median for retail)
- [ ] Low-listing detection (<3 listings)
- [ ] Reference model aggregation (multiple SKUs → single average)

**Integration Tests** (Backend):
- [ ] `/api/v1/visualization/data` endpoint returns correct data structure
- [ ] Redis cache hit/miss scenarios
- [ ] Database fallback when Redis is unavailable

**Component Tests** (Frontend):
- [ ] Chart renders with mock data
- [ ] Tooltip shows on hover (desktop) and tap (mobile)
- [ ] Manufacturer toggle updates chart data
- [ ] "Show older GPUs" checkbox updates chart data
- [ ] Value zone highlights appear on correct data points
- [ ] Low-listing asterisks and warnings display correctly

**E2E Tests** (Playwright):
- [ ] User lands on dashboard, sees Radeon GPUs by default
- [ ] User hovers over data point, tooltip appears
- [ ] User clicks "View Official Specs", OEM page opens in new tab
- [ ] User toggles to Nvidia, chart updates smoothly
- [ ] User checks "Show older GPUs", additional data points appear
- [ ] User on tablet: tap data point, tooltip appears; tap elsewhere, tooltip dismisses

**Accessibility Tests**:
- [ ] Keyboard navigation works (tab through data points)
- [ ] Focus indicators are visible
- [ ] Screen reader announces chart description
- [ ] Color contrast meets WCAG AA (4.5:1 minimum)
- [ ] Touch targets are ≥44px on mobile

**Performance Tests**:
- [ ] Page loads in <2 seconds on desktop with 50 data points
- [ ] API response time <500ms (cached)
- [ ] LCP (Largest Contentful Paint) <1.5 seconds
- [ ] No layout shift (CLS = 0)

---

## Version History Summary

**v1.0 (2025-01-10)**: Initial specification with core feature requirements, acceptance criteria, functional requirements, data model, and user stories.

**v1.1 (2025-01-10)**: Iteration 1 clarifications based on Tech Lead questions. Added 13 detailed specifications:
1. Performance scoring methodology (Simple Ordinal Ranking, 1-100 scale, database-stored)
2. Value zone algorithm (Tier Jumping: ≥10% better performance at ≤ same price)
3. GPU model granularity (aggregate by reference model, not manufacturer SKU)
4. Dual price point display (always show retail + used if both exist)
5. Low-listing handling (<3 listings: show with warning, exclude from value zones)
6. Outlier filtering (>2x median for used, >1.5x for retail; exclude from average only)
7. Visualization library choice (Recharts for React/TypeScript, 50KB bundle)
8. Real-time update strategy (no automatic notifications, manual refresh only)
9. Display limits (no hard cap, show all current-gen by default, older GPUs toggleable)
10. Touch interactions (tap to show tooltip, tap elsewhere to dismiss)
11. Link strategy (OEM product page, not retailer links)
12. Visual differentiation (color + icon badges + dot pattern for accessibility)
13. Y-axis labeling (numeric scores 0-100 with "(relative)" label)

Added implementation notes, API specification, testing checklist, and product rationale for all major decisions.

---

**Status**: ✅ **READY FOR IMPLEMENTATION**  
All blocking questions resolved. Database schema defined. API contracts specified. UI/UX flows documented. Proceed with development.