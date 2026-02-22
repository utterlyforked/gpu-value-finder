# Value Visualization Dashboard - Technical Questions (Iteration 1)

**Status**: NEEDS CLARIFICATION  
**Iteration**: 1  
**Date**: 2025-01-10

---

## Summary

After reviewing the specification, I've identified **12** areas that need clarification before implementation can begin. These questions address:
- Data model and performance scoring methodology
- Visualization behavior and interaction patterns
- Value zone calculation specifics
- Real-time data updates and caching strategy
- Responsive design boundaries
- Integration with dependent features

---

## CRITICAL Questions

These block core implementation and must be answered first.

### Q1: How is the GPU Performance Score calculated and maintained?

**Context**: The PRD states performance is "derived from known GPU model hierarchies, VRAM capacity, and generation" but doesn't specify the formula or weighting. This directly affects Y-axis positioning and value zone calculations. The data model section asks whether this should be "hardcoded in the application or stored in the database" but doesn't define the actual scoring methodology.

**Options**:

- **Option A: Simple Ordinal Ranking (1-100 scale)**
  - Impact: Each GPU gets a manually-assigned score (e.g., 7900 XTX = 95, 7900 XT = 88, 7800 XT = 75)
  - Trade-offs: Simple to understand and maintain, but requires manual updates for each new GPU
  - Database: `GpuPerformanceTier` table with `PerformanceScore` integer field, seeded via migrations
  - Maintenance: Product team provides scores when new GPUs release
  
- **Option B: Weighted Formula (Generation + Tier + VRAM)**
  - Impact: Score = (Generation weight × 20) + (Tier weight × 50) + (VRAM GB × 2)
  - Trade-offs: Automatically calculates scores, but formula might not match real-world performance
  - Database: Same table, but scores calculated via database function or application logic
  - Maintenance: Update formula if it proves inaccurate
  
- **Option C: Hybrid - Base Scores with Formula Adjustments**
  - Impact: Manually assign base scores per generation (RX 7000 series baseline = 70), then adjust by tier and VRAM
  - Trade-offs: Balance between manual control and automation
  - Database: Store base scores and multipliers, calculate on query
  - Maintenance: Update base scores per generation, formula handles rest

**Recommendation for MVP**: **Option A** (Simple Ordinal Ranking). Gives product full control over positioning, avoids formula debates, easy to debug. Store in database (seeded via EF Core migrations) so updates don't require code deployment. Can revisit formula approach in v2 if scoring becomes too manual.

**Follow-up needed**: If Option A is chosen, who provides the initial performance scores for existing GPUs? Should there be a UI for non-technical staff to update scores when new GPUs release?

---

### Q2: What defines a "value zone" algorithmically?

**Context**: The PRD says "highlight used GPUs that meet or exceed the value frontier" and mentions calculating "performance-per-pound" but doesn't specify the exact logic. Multiple interpretations are possible, and this is the core feature differentiator.

**Options**:

- **Option A: Used GPU Beats Best Retail at Same Performance**
  - Logic: For each performance tier, if `usedPrice < cheapestRetailPriceAtSameTier`, it's a value zone
  - Example: If RX 7800 XT (retail) = £500 and used 7900 XT = £480, the 7900 XT is in value zone (better performance, lower price)
  - Impact: Very strict—only highlights clear wins
  - Trade-offs: Fewer highlights, but each is genuinely valuable
  
- **Option B: Used GPU Offers Better Performance-Per-Pound Than Retail Average**
  - Logic: Calculate `performanceScore / price` for all GPUs. Used GPUs in top 25% of PPP ratio get highlighted
  - Example: If average retail PPP = 0.15, any used GPU with PPP > 0.15 is highlighted
  - Impact: More highlights, shows "relative value"
  - Trade-offs: Might highlight marginal deals; requires defining "top X%"
  
- **Option C: Used GPU Matches Higher-Tier Retail at Same/Lower Price**
  - Logic: If `usedGpuPerformance >= (retailGpuPerformance + 10%)` AND `usedPrice <= retailPrice`, highlight it
  - Example: Used RX 7900 XTX (perf=95) at £650 vs. new RX 7900 XT (perf=88) at £700 → highlight the XTX
  - Impact: Shows "tier jumping" opportunities
  - Trade-offs: Clear value story ("get next-tier GPU for less"), but requires defining tier thresholds

**Recommendation for MVP**: **Option C** (Tier Jumping). Easy to explain to users ("you're getting a higher-tier GPU for less"), visually clear, and aligns with the "wow factor" goal. Threshold of +10% performance at ≤ same price catches meaningful upgrades without noise.

**Follow-up needed**: Should value zones be exclusive to used GPUs, or could a retail GPU be highlighted if it's exceptionally good value compared to other retail options?

---

### Q3: What is the granularity of GPU models in the visualization?

**Context**: The PRD says "each GPU model is a visual element" but doesn't clarify what constitutes a unique model. For example, is "RX 7900 XTX" one model, or are "Sapphire RX 7900 XTX Nitro+" and "PowerColor RX 7900 XTX Red Devil" separate models?

**Options**:

- **Option A: Aggregate by Reference Model (e.g., "RX 7900 XTX")**
  - Impact: All manufacturer variants (Sapphire, PowerColor, XFX) are averaged into one data point
  - Trade-offs: Cleaner visualization (10-15 points instead of 50+), easier to compare
  - Database: `GpuModel.ReferenceName` = "RX 7900 XTX", all SKUs roll up to this
  - Example: "RX 7900 XTX - Avg retail £899 (12 listings from Sapphire, PowerColor, etc.)"
  
- **Option B: Show Each Manufacturer SKU Separately**
  - Impact: Sapphire Nitro+ is a different point than PowerColor Red Devil
  - Trade-offs: More detailed, but visualization gets crowded (60+ data points)
  - Database: Each SKU is a unique `GpuModel` entry
  - Example: "Sapphire RX 7900 XTX Nitro+ - £920" and "PowerColor RX 7900 XTX - £880"
  
- **Option C: Aggregate by Reference, Expandable to SKU Detail**
  - Impact: Default view shows "RX 7900 XTX (aggregated)", clicking it expands to show individual SKUs
  - Trade-offs: Best of both worlds, but more complex UI and interaction design
  - Database: Both `ReferenceName` and `SKU` stored, API supports both views

**Recommendation for MVP**: **Option A** (Aggregate by Reference Model). Users shopping for GPUs think in terms of "7900 XTX" not "Sapphire Nitro+ vs. PowerColor Red Devil." Keeps visualization uncluttered. Can add SKU drill-down in v2 if users request it.

**Follow-up needed**: How do we handle "special edition" SKUs with significantly different specs (e.g., factory overclocked models or water-cooled variants)? Same aggregation or separate?

---

### Q4: Can a GPU model appear at multiple price points simultaneously (retail + used)?

**Context**: The PRD says "RX 7900 XTX might appear twice—once at £899 (retail average) and once at £650 (used average)" but doesn't clarify if this is mandatory behavior or an example of what *could* happen.

**Options**:

- **Option A: Always Show Both (If Data Exists)**
  - Impact: Every GPU with both retail and used data appears as two distinct visual elements
  - Trade-offs: Emphasizes the price difference (good for comparison), but chart could get crowded
  - UI: Visual differentiation required (color, icon, or label: "New" vs "Used")
  - Example: 7900 XTX appears as two bubbles vertically aligned (same performance, different X position)
  
- **Option B: Show Whichever Is Better Value**
  - Impact: For each GPU, show only the data point with better performance-per-pound
  - Trade-offs: Cleaner chart, but hides retail prices if used is always better (less context)
  - UI: Tooltip can mention "Retail avg: £899, Used avg: £650 (shown)"
  
- **Option C: Default to Single Point, Toggle to Comparison View**
  - Impact: Default shows best value for each model; user can toggle "Show retail + used" to see both
  - Trade-offs: Flexible, but adds UI complexity
  - UI: Checkbox or toggle above chart

**Recommendation for MVP**: **Option A** (Always Show Both). This is the core value proposition—seeing the gap between retail and used. Crowding can be managed with zoom/pan or filtering (future iteration). Makes the "wow factor" obvious.

**Follow-up needed**: If Option A is chosen, how should the two points be visually connected (e.g., line connecting them, same color with different opacity, label linking them)?

---

### Q5: What happens when there are fewer than 3 listings for a GPU model?

**Context**: The PRD mentions "If <3 listings exist for a GPU, show price with asterisk: '£650*' and tooltip: 'Based on only 2 listings—price may be unreliable'" but doesn't specify whether this GPU should still appear in value zone calculations or be treated differently.

**Options**:

- **Option A: Show With Warning, Include in Value Zones**
  - Impact: GPU appears normally with asterisk, can be highlighted as value zone
  - Trade-offs: Provides data (better than nothing), but might mislead users
  - UI: Asterisk + tooltip warning
  
- **Option B: Show With Warning, Exclude From Value Zones**
  - Impact: GPU appears with asterisk, but is never highlighted as value opportunity
  - Trade-offs: Conservative (avoids false positives), but might miss real deals
  - UI: Grayed out or different opacity, tooltip explains exclusion
  
- **Option C: Don't Show At All If <3 Listings**
  - Impact: GPU doesn't appear on visualization
  - Trade-offs: Cleanest approach, but hides potentially useful data
  - UI: N/A

**Recommendation for MVP**: **Option B** (Show With Warning, Exclude From Value Zones). Balances transparency (users see the data) with caution (we don't highlight unreliable deals). Users can still click through to listings if they want to investigate.

**Follow-up needed**: Should the "minimum 3 listings" threshold be the same for retail and used, or should retail require more listings (since used prices are inherently more variable)?

---

## HIGH Priority Questions

These affect major workflows but have reasonable defaults.

### Q6: How should the visualization handle extreme outliers in pricing?

**Context**: The PRD mentions "Prices >2x average for that model are filtered before calculating used average" but doesn't specify how to handle retail outliers or whether outliers are excluded from the visualization entirely or just from average calculations.

**Options**:

- **Option A: Filter Outliers From Average Calculation Only**
  - Impact: Outliers are removed before calculating average, but individual outlier listings are still visible in linked data (Feature 1/2)
  - Trade-offs: Average is accurate, but users might wonder why linked listings show prices that don't match the average
  - Logic: For used prices, exclude any listing >2x median; for retail, exclude >1.5x median (retail should be more stable)
  
- **Option B: Filter Outliers From Both Average and Count**
  - Impact: Outliers are completely excluded—average calculation and listing count both ignore them
  - Trade-offs: Cleaner, but "12 listings" might actually mean "15 listings, but 3 were outliers"
  - Logic: Same as Option A, but tooltip says "12 valid listings (3 excluded as outliers)"
  
- **Option C: Show Outliers As Range**
  - Impact: Instead of single average, show price range: "£650-£900 (avg £750)"
  - Trade-offs: More informative, but complicates visualization (how to display range on scatter plot?)
  - UI: Error bars or shaded region around data point

**Recommendation for MVP**: **Option A** (Filter From Average Only). Keeps visualization clean while preserving data integrity. Users who click through to listings (Feature 1/2) will see all listings including outliers, which is transparent.

**Follow-up needed**: Should there be an admin/debug view where outliers are visible (for data quality monitoring)?

---

### Q7: When data refreshes, how are users notified if they have the page open?

**Context**: The PRD mentions "If user has page open while scraping job completes, show notification: 'New price data available—refresh to update'" but doesn't specify the mechanism (polling, WebSocket, server-sent events) or the UX pattern.

**Options**:

- **Option A: Simple Polling Every 5 Minutes**
  - Impact: Frontend calls `/api/v1/visualization/last-updated` every 5 min, compares timestamp
  - Trade-offs: Simple, works everywhere, but 5-min delay and unnecessary requests
  - UI: Banner at top: "New prices available — Refresh" (button reloads page)
  - Infrastructure: Just HTTP, no WebSocket needed
  
- **Option B: Server-Sent Events (SSE)**
  - Impact: Server pushes notification when scraping job completes
  - Trade-offs: Real-time, but requires SSE endpoint and connection management
  - UI: Same banner, but appears immediately
  - Infrastructure: `/api/v1/visualization/updates` SSE endpoint
  
- **Option C: No Automatic Notification**
  - Impact: User sees stale data until they manually refresh
  - Trade-offs: Simplest, no polling/SSE complexity, but less "live" feeling
  - UI: Timestamp "Prices updated 2 hours ago" is always visible; user can refresh if desired

**Recommendation for MVP**: **Option C** (No Auto-Notification). Scraping jobs run every 4-6 hours (typical for price aggregation), so real-time updates aren't critical. Prominent timestamp lets users decide if they want to refresh. Can add polling/SSE in v2 if users complain about staleness.

**Follow-up needed**: If Option C is chosen, should there be a manual "Refresh Prices" button, or is browser refresh sufficient?

---

### Q8: What is the maximum number of GPU models displayed simultaneously?

**Context**: The PRD mentions "If >20 GPUs are displayed, may need to cluster or paginate (monitor after launch)" but doesn't provide guidance on current-gen GPU counts or whether this is a likely scenario.

**Options**:

- **Option A: No Limit, Optimize Visualization for Scalability**
  - Impact: Show all GPUs with available data (could be 30-50 for a manufacturer)
  - Trade-offs: Most informative, but chart might be crowded
  - UI: Implement zoom/pan controls, or interactive filtering (e.g., "show only RX 7000 series")
  
- **Option B: Cap at Top 20 by Performance**
  - Impact: Show only the highest-performing 20 GPUs for selected manufacturer
  - Trade-offs: Keeps chart clean, but hides budget options
  - UI: Message: "Showing top 20 models by performance — filter to see more"
  
- **Option C: Cap at Top 20 by Listing Count**
  - Impact: Show the 20 most-listed GPUs (most market activity)
  - Trade-offs: Focuses on popular models, but might miss rare high-value deals
  - UI: Same message as Option B

**Recommendation for MVP**: **Option A** (No Limit). Current-gen Radeon lineup is ~12 models (RX 7000 series), Nvidia is ~15 (RTX 40 series). Even with previous-gen included, unlikely to exceed 25-30. Modern visualization libraries (D3, Plotly, Recharts) handle 50 points easily. If crowding becomes an issue post-launch, add filtering in v2.

**Follow-up needed**: Should previous-generation GPUs (RX 6000 series, RTX 30 series) be included by default, or hidden behind a toggle?

---

### Q9: How should "tooltip on hover" work on touch devices (tablet)?

**Context**: The PRD specifies "touch interactions replace hover (tap for tooltip)" but doesn't define the exact behavior—tap-to-show or tap-to-toggle?

**Options**:

- **Option A: Tap to Show, Tap Anywhere Else to Dismiss**
  - Impact: Tapping a GPU point shows tooltip; tapping elsewhere or another point dismisses it
  - Trade-offs: Standard mobile pattern, intuitive
  - UI: Tooltip appears with small "X" button for explicit dismissal
  
- **Option B: Tap to Toggle (Tap Again to Dismiss)**
  - Impact: Tapping once shows tooltip, tapping same point again hides it
  - Trade-offs: Requires two taps to dismiss (slightly clunky), but avoids accidental dismissal
  - UI: No "X" button needed
  
- **Option C: Tap to Show, Auto-Dismiss After 5 Seconds**
  - Impact: Tooltip appears on tap, fades out automatically
  - Trade-offs: Good for quick browsing, but might disappear while user is reading
  - UI: Tooltip includes countdown indicator or "Tap to keep open" hint

**Recommendation for MVP**: **Option A** (Tap to Show, Tap Elsewhere to Dismiss). Standard pattern users expect; allows comparing multiple GPUs by tapping between them. Auto-dismiss (Option C) is frustrating for users trying to read detailed tooltips.

---

## MEDIUM Priority Questions

Edge cases and polish items - can have sensible defaults if needed.

### Q10: Should the "Official Specs" link in the tooltip open OEM page or reference page?

**Context**: The PRD says "User clicks 'Official Specs' link in tooltip → Opens AMD product page in new tab" but Feature 4 (Manufacturer Reference Links) distinguishes between "official specs (OEM reference)" and "retailer links." Tooltip should clarify which.

**Options**:

- **Option A: Link to OEM Product Page (AMD/Nvidia Official)**
  - Example: https://www.amd.com/en/products/graphics/amd-radeon-rx-7900-xtx
  - Impact: Canonical source, detailed specs
  - Trade-offs: User can't buy directly (OEM pages don't sell), extra click to find retailers
  
- **Option B: Link to Best-Price Retailer From Feature 1**
  - Example: Link to Overclockers UK listing (cheapest current price)
  - Impact: Direct path to purchase
  - Trade-offs: Might feel like we're pushing a specific retailer, price might change
  
- **Option C: Both Links in Tooltip**
  - Impact: "View Specs (AMD) | Buy Now (Overclockers UK - £899)"
  - Trade-offs: Most flexible, but tooltip gets crowded

**Recommendation for MVP**: **Option A** (OEM Product Page). Aligns with Feature 4's "manufacturer reference" concept and avoids appearance of favoritism toward specific retailers. Feature 1's retail listings are accessible via a separate flow (future feature or secondary link).

---

### Q11: What visual treatment distinguishes retail from used price points?

**Context**: The PRD says "Retail-priced GPUs are visually distinct from used-priced GPUs (different color, icon, or shape)" but doesn't specify the approach.

**Options**:

- **Option A: Color Differentiation**
  - Impact: Retail = blue, Used = green (or similar high-contrast pair)
  - Trade-offs: Simple, works well, but must ensure colorblind accessibility
  - Accessibility: Use different shades + patterns/textures
  
- **Option B: Shape Differentiation**
  - Impact: Retail = circles, Used = squares (or triangles)
  - Trade-offs: Shape is colorblind-safe, but might be less intuitive
  - Accessibility: Strong
  
- **Option C: Icon + Color**
  - Impact: Retail = solid circle with "NEW" badge, Used = outlined circle with "USED" badge
  - Trade-offs: Clearest differentiation, but more visual weight
  - Accessibility: Best (color + text + shape)

**Recommendation for MVP**: **Option C** (Icon + Color). Meets WCAG AA (color is not the only differentiator), immediately clear to users, and works well in screenshots/marketing. Badges can be small to avoid clutter.

---

### Q12: Should the Y-axis (performance) show numeric scores or just relative positioning?

**Context**: The PRD says "No FPS numbers or benchmark scores are displayed" but doesn't clarify whether the Y-axis should show the performance score numbers (e.g., 95, 88, 75) or just relative labels (e.g., "High-End," "Mid-Range," "Budget").

**Options**:

- **Option A: Show Numeric Performance Scores (e.g., 75, 88, 95)**
  - Impact: Y-axis labeled 0-100 with GPU points positioned by score
  - Trade-offs: Precise, but might be misinterpreted as "FPS" or "benchmark score"
  - UI: Axis label: "Performance Score (relative)"
  
- **Option B: Show Tier Labels Only (High-End, Mid-Range, Budget)**
  - Impact: Y-axis has 3-4 zones with text labels, no numbers
  - Trade-offs: Less precise, but can't be misinterpreted
  - UI: Visual bands/zones instead of numeric scale
  
- **Option C: No Y-Axis Labels (Relative Position Only)**
  - Impact: Y-axis is unlabeled; users infer performance from vertical position
  - Trade-offs: Cleanest visually, but least informative
  - UI: Tooltip explains "Higher = better performance"

**Recommendation for MVP**: **Option A** (Numeric Scores). Users expect quantifiable data in a dashboard. As long as axis is labeled "Performance Score (relative, not FPS)" and FAQ/docs explain it's not a benchmark, it's the most useful option. Avoids ambiguity of "mid-range" (is that good or bad?).

---

## Notes for Product

- **Performance Score Methodology (Q1)** and **Value Zone Logic (Q2)** are the highest-priority questions—they determine the entire visualization's behavior and must be locked down before any API or frontend work begins.

- **GPU Model Granularity (Q3)** affects database schema and API response size, so it should be decided early.

- Questions about real-time updates (Q7), outliers (Q6), and touch interactions (Q9) have reasonable defaults if you'd like to defer them, but they'll affect user experience quality.

- If any answers conflict with Features 1, 2, or 5, please flag them—this feature depends heavily on their data contracts.

- Happy to do another iteration if these answers raise new questions (especially around value zone calculation—it might need a detailed example walkthrough).

---

## Implementation Readiness Blockers

**Cannot proceed until answered:**
1. Q1 (Performance score calculation method)
2. Q2 (Value zone definition)
3. Q3 (Model granularity)
4. Q4 (Retail + used simultaneous display)

**Can proceed with assumptions if needed:**
- Q5-Q12 have recommended defaults that are reasonable for MVP

Once Q1-Q4 are answered, I can validate whether the data model section is sufficient or if additional entities/fields are needed.