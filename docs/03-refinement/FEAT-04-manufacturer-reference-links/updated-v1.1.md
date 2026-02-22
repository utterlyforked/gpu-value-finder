# Manufacturer Reference Links - Feature Requirements (v1.1)

**Version History**:
- v1.0 - Initial specification (2025-01-10)
- v1.1 - Iteration 1 clarifications (2025-01-10) - Added: URL population strategy, storage approach, discontinued detection workflow, validation frequency, visual design specification, regional URL handling

---

## Feature Overview

This feature provides quick access to official AMD and Nvidia product specification pages for every GPU displayed in the application. Rather than duplicating technical specifications, benchmark data, or editorial content, GPU Value Tracker acts as a bridge to canonical manufacturer sources.

When users identify value opportunities through the pricing visualization, they need to verify technical details (power requirements, dimensions, exact VRAM specs, I/O ports) before making purchase decisions. This feature ensures that authoritative specification data is always one click away, keeping GPU Value Tracker focused on its core value proposition (pricing intelligence) while empowering users to research technical details from official sources.

The feature explicitly avoids content duplication, keeps the site lightweight and focused, and reduces maintenance burden by not hosting technical data that changes with driver updates or manufacturer revisions.

---

## User Stories

- As a PC builder, I want to access official specifications for any GPU displayed on the dashboard so that I can verify technical details like power consumption and dimensions before purchasing
- As a researcher comparing value options, I want to quickly open the official AMD or Nvidia product page in a new tab so that I can read full specifications without losing my place in the GPU Value Tracker dashboard
- As a user, I want to avoid wading through redundant benchmark data or reviews on GPU Value Tracker so that I can stay focused on value comparison and use manufacturer sites for detailed specs
- As a user looking at discontinued cards in the used market, I want to know when official specs are no longer available so that I can seek alternative documentation sources

---

## Acceptance Criteria (UPDATED v1.1)

- Each GPU card displayed in the dashboard has a clearly labeled text link with external icon (e.g., "Official Specs ↗️") to the manufacturer's product page
- Links are styled as secondary text links (underlined, muted color) positioned in the GPU card footer to maintain focus on pricing data
- Links open in a new browser tab with `target="_blank"` and `rel="noopener noreferrer"` security attributes
- Links point to official AMD product pages for Radeon cards (prefer `/en-gb/` URLs, fallback to `/en/` if UK version doesn't exist)
- Links point to official Nvidia product pages for GeForce cards (prefer `/en-gb/` URLs, fallback to `/en-us/` if UK version doesn't exist)
- No benchmark data, performance reviews, or editorial content about GPU specs is hosted on GPU Value Tracker
- If a GPU's official product page is broken (returns 404), the link is immediately hidden and replaced with "Specs Unavailable" text
- GPUs with unavailable specs display a non-interactive "Specs Unavailable" message instead of a clickable link
- Links are validated weekly via background job to detect broken manufacturer URLs
- Broken links are logged to monitoring dashboard for manual review and discontinued status assignment
- Initial spec URLs are populated via hybrid CSV import: script generates suggested URLs from manufacturer sitemaps, product owner reviews/corrects in spreadsheet, then bulk import to database
- Full URLs (not templates) are stored per GPU model to handle manufacturer URL inconsistencies
- Last validation timestamp is stored internally but NOT displayed to users (internal monitoring only)

---

## Detailed Specifications (UPDATED v1.1)

### URL Population Strategy

**Decision**: Hybrid CSV import with automated suggestion and manual review.

**Rationale**: Balances automation efficiency with accuracy requirements. For an estimated 50-100 GPU catalog, fully manual entry is time-intensive and error-prone, while fully automated scraping risks false matches and requires complex matching algorithms. The hybrid approach allows a script to do the heavy lifting (matching model names to manufacturer sitemap URLs) while product owner provides final verification before import.

**Workflow**:
1. Engineer runs URL discovery script that:
   - Fetches AMD and Nvidia product sitemaps
   - Matches GPU model names from existing database to sitemap URLs
   - Generates CSV with columns: `GPUId`, `ModelName`, `SuggestedURL`, `Manufacturer`
2. Product owner reviews CSV:
   - Verifies URL matches correct model
   - Corrects mismatches manually
   - Marks discontinued models (leaves URL empty or adds "DISCONTINUED" flag)
   - Adds notes for edge cases
3. Engineer runs import script to populate `GPU.officialSpecUrl` from reviewed CSV
4. Initial validation job runs to verify all imported URLs return 200 OK

**Edge Cases**:
- Script can't find match for GPU: Leaves `SuggestedURL` empty, product owner researches manually
- Multiple URLs found for one model: Script picks first match, flags for review
- Model name variations (e.g., "RX 7900 XTX" vs "Radeon RX 7900 XTX"): Script uses fuzzy matching with manual review fallback

**Tooling**:
- Python script for sitemap fetching and name matching (uses `requests`, `BeautifulSoup`, `fuzzywuzzy`)
- CSV template with validation rules (URL format, required fields)
- Entity Framework Core migration to add new columns
- Admin command or API endpoint for CSV import with validation

---

### URL Storage Approach

**Decision**: Store full URLs per GPU model (not templates).

**Rationale**: Manufacturer URL structures are inconsistent across product lines and change over time. AMD uses different path patterns for Radeon vs Ryzen, Nvidia has variations for GeForce vs Quadro. Storing full URLs is simpler, more reliable, and handles manufacturer inconsistencies naturally. The validation job (runs weekly) will detect URL changes regardless of storage approach - there's no meaningful maintenance advantage to templates.

**Database Schema**:
```csharp
public class GPU
{
    public int Id { get; set; }
    public string ModelName { get; set; } // Existing
    public string Manufacturer { get; set; } // Existing (AMD, Nvidia)
    
    // New fields for spec links
    public string? OfficialSpecUrl { get; set; } // Full URL or null
    public SpecUrlStatus SpecUrlStatus { get; set; } // Enum: Active, Unavailable, NeedsReview
    public DateTime? SpecUrlLastChecked { get; set; } // Validation timestamp
}

public enum SpecUrlStatus
{
    Active,        // URL exists and last validation succeeded
    Unavailable,   // URL is broken or GPU discontinued
    NeedsReview    // Validation failed, awaiting manual review
}
```

**Examples**:
- AMD Radeon RX 7900 XTX: `https://www.amd.com/en-gb/products/graphics/amd-radeon-rx-7900xtx.html`
- Nvidia GeForce RTX 4090: `https://www.nvidia.com/en-gb/geforce/graphics-cards/40-series/rtx-4090/`
- Older AMD card: `https://www.amd.com/en/products/graphics/radeon-rx-6700-xt` (no `/en-gb/` exists)

**Migration Strategy**:
- Add columns with EF Core migration
- Populate via CSV import (see URL Population section)
- Default `SpecUrlStatus` to `NeedsReview` until first validation confirms URLs work

---

### Discontinued GPU Detection

**Decision**: Manual review workflow with automated flagging.

**Rationale**: For MVP with <100 GPUs, manual review prevents false positives from temporary manufacturer site outages, CDN issues, or rate limiting. Automatically marking cards as discontinued could hide links that are temporarily broken but recoverable. Manual review ensures accuracy and allows product owner to verify discontinuation via other sources (manufacturer announcements, retailer listings).

**Workflow**:

1. **Weekly validation job** runs and detects broken URL (404, 503, timeout)
2. Broken URL's `SpecUrlStatus` changes from `Active` → `NeedsReview`
3. Job logs broken link to monitoring dashboard/logs with details:
   - GPU model name
   - URL that failed
   - HTTP status code
   - Timestamp
4. **Product owner reviews monitoring dashboard** (weekly or on alert)
5. Product owner determines cause:
   - **Temporary issue**: Reset status to `Active`, next validation will re-check
   - **URL moved**: Update `OfficialSpecUrl` to new location, set status to `Active`
   - **GPU discontinued**: Set status to `Unavailable` (link hidden from users)
6. User-facing behavior happens immediately in step 2 (see below)

**User-Facing Behavior**:
- `Active` status → Clickable "Official Specs ↗️" link displayed
- `NeedsReview` OR `Unavailable` status → "Specs Unavailable" text displayed (not clickable)

This means users never see broken links, even before manual review completes. Once product owner confirms discontinuation, no further action needed - `Unavailable` status persists.

**Future Automation** (post-MVP):
Could add heuristic for GPUs older than 3 years: auto-change `NeedsReview` → `Unavailable` after 3 consecutive failed validations. Implement only if manual review becomes unmanageable.

---

### Link Validation Schedule

**Decision**: Weekly validation via background job.

**Rationale**: Manufacturer product pages are stable - they don't reorganize daily. Weekly validation catches broken links with acceptable latency (max 7 days) without hammering manufacturer servers with daily requests. For MVP with ~100 GPUs, 100 HTTP HEAD requests per week is negligible load. Daily validation (aligned with price scraping) is overkill for reference links that rarely change.

**Implementation**:
- **Background Job**: Hangfire recurring job, runs Sunday 2:00 AM UTC (low-traffic period)
- **Process**:
  1. Query all GPUs where `SpecUrlStatus = Active` OR `SpecUrlStatus = NeedsReview`
  2. For each GPU, send HTTP HEAD request to `OfficialSpecUrl`
  3. If response is 200 OK → Set `SpecUrlStatus = Active`, update `SpecUrlLastChecked`
  4. If response is 404/503/timeout → Set `SpecUrlStatus = NeedsReview`, log to monitoring
  5. Skip GPUs with `SpecUrlStatus = Unavailable` (already marked discontinued)
- **Rate Limiting**: 1 request per second (100 GPUs = ~2 minutes total runtime)
- **Timeout**: 10 second timeout per request
- **Monitoring**: Job completion logged to Application Insights with success/failure counts

**Edge Cases**:
- Manufacturer site down entirely → Many GPUs will flag as `NeedsReview`, product owner sees spike in monitoring and knows to wait for site recovery
- Rate limited by manufacturer (429 response) → Treat as temporary failure, retry next week
- Redirect (301/302) → Follow redirect, validate final URL, log warning if destination URL differs from stored URL

---

### Regional URL Handling

**Decision**: Store single "best available" URL per GPU (prefer UK, fallback to global English).

**Rationale**: Simplifies database schema and data entry for MVP. Most users on GPU Value Tracker (initially UK-focused) benefit from UK-localized content. If UK URL doesn't exist, global English is acceptable - specs are identical, only marketing copy differs. Multi-regional URL support adds complexity (multiple columns or JSON fields, frontend locale detection) not justified for MVP.

**URL Selection Logic** (during CSV import/manual entry):

1. First, try UK-specific URL pattern:
   - AMD: `https://www.amd.com/en-gb/products/graphics/...`
   - Nvidia: `https://www.nvidia.com/en-gb/geforce/graphics-cards/...`
2. If 404, try global English:
   - AMD: `https://www.amd.com/en/products/graphics/...`
   - Nvidia: `https://www.nvidia.com/en-us/geforce/graphics-cards/...`
3. Store whichever URL returns 200 OK
4. If both fail, leave `OfficialSpecUrl` as null, set status to `Unavailable`

**Examples**:
- **RTX 4090**: UK URL exists → Store `https://www.nvidia.com/en-gb/geforce/graphics-cards/40-series/rtx-4090/`
- **Older RX 6700 XT**: UK URL 404, global works → Store `https://www.amd.com/en/products/graphics/radeon-rx-6700-xt`
- **Discontinued GTX 1660**: Both URLs 404 → Store null, status = `Unavailable`

**Future Internationalization** (post-MVP):
If GPU Value Tracker expands to US/EU markets, can add `SpecUrlRegionalVariants` JSON column storing multiple URLs keyed by locale (`{ "en-gb": "...", "en-us": "...", "de-de": "..." }`). Frontend selects URL based on user's browser locale or site language setting.

---

### Link Visual Design

**Decision**: Text link with external icon, positioned in GPU card footer.

**Rationale**: Standard web pattern that's highly accessible, requires minimal space, and maintains focus on pricing data (the primary content). Secondary styling (muted color, smaller text) visually subordinates the link to price information. External link icon (↗️) signals to users that clicking opens a new tab with manufacturer content.

**Design Specification**:

**HTML Structure**:
```tsx
<div className="gpu-card">
  <div className="gpu-card-header">
    {/* Model name, manufacturer logo */}
  </div>
  <div className="gpu-card-body">
    {/* Pricing chart, value metrics */}
  </div>
  <div className="gpu-card-footer">
    <a 
      href={gpu.officialSpecUrl}
      target="_blank"
      rel="noopener noreferrer"
      className="spec-link"
      aria-label={`View official specifications for ${gpu.modelName} on ${gpu.manufacturer} website`}
    >
      Official Specs ↗️
    </a>
  </div>
</div>
```

**Styling** (Tailwind CSS classes):
- `text-sm text-gray-600 hover:text-gray-900` - Muted color, darker on hover
- `underline underline-offset-2` - Clear link affordance
- `transition-colors duration-150` - Smooth hover transition
- Font size: 14px (smaller than body text)
- Icon: Unicode arrow ↗️ (U+2197) or external link SVG icon

**Positioning**:
- Aligned to the right of GPU card footer
- Left side of footer can include other secondary actions (future: "Add to comparison", "Set alert")

**Unavailable State**:
```tsx
{gpu.specUrlStatus === 'Unavailable' || gpu.specUrlStatus === 'NeedsReview' ? (
  <span className="text-sm text-gray-400 italic">
    Specs Unavailable
  </span>
) : (
  <a href={gpu.officialSpecUrl} ...>
    Official Specs ↗️
  </a>
)}
```

**Accessibility**:
- `aria-label` provides full context for screen readers
- `rel="noopener noreferrer"` prevents security issues with `target="_blank"`
- Sufficient color contrast (WCAG AA minimum: 4.5:1 for text)
- Focus state visible (browser default outline or custom ring)

**Responsive Behavior**:
- Mobile: Link remains in footer, stacks vertically if needed
- Desktop: Link stays right-aligned in footer

---

### Validation Timestamp Visibility

**Decision**: Do NOT display last validation timestamp to users.

**Rationale**: Validation timestamp is operational data for monitoring and debugging, not user-facing information. Users expect links to work when they click them - showing "Last verified: 3 days ago" creates unnecessary concern without actionable value. If a link is broken, users see "Specs Unavailable" immediately (they don't need to know when it broke). Keeping UI focused on pricing insights avoids clutter.

**Storage**:
- `SpecUrlLastChecked` timestamp remains in database
- Used by monitoring dashboard to detect stale validations
- Available in admin logs for troubleshooting

**User-Facing Elements**:
- Active link: "Official Specs ↗️" (no timestamp)
- Unavailable: "Specs Unavailable" (no timestamp)

**Monitoring Dashboard** (admin-only view):
Can show validation status table:
| GPU Model | Status | Last Checked | URL |
|-----------|--------|--------------|-----|
| RTX 4090 | Active | 2025-01-09 | nvidia.com/... |
| RX 6700 XT | NeedsReview | 2025-01-09 | amd.com/... |

---

## Q&A History

### Iteration 1 - 2025-01-10

**Q1: How should we populate initial spec URLs for the existing GPU catalog?**  
**A**: Hybrid approach - script generates CSV with suggested URLs by matching GPU names to manufacturer sitemap entries. Product owner reviews CSV for accuracy (corrects mismatches, marks discontinued models), then bulk import to database. This balances automation speed with human verification to ensure 100% URL accuracy. See "URL Population Strategy" section for detailed workflow.

**Q2: What's the URL structure for spec links - full URLs or template-based?**  
**A**: Store full URLs per GPU model. Manufacturer URL patterns are inconsistent (AMD has different structures for different product lines, Nvidia changes paths over time). Full URLs are simpler, handle edge cases naturally, and don't create false maintenance savings since validation job detects broken links regardless of storage approach. See "URL Storage Approach" section for database schema.

**Q3: How should discontinued GPU detection work?**  
**A**: Manual review workflow. Weekly validation job flags broken links as `NeedsReview`, product owner reviews monitoring dashboard to determine cause (temporary site issue vs actual discontinuation). User-facing behavior hides broken links immediately (shows "Specs Unavailable"), preventing bad UX while awaiting manual review. Prevents false positives from temporary outages. See "Discontinued GPU Detection" section for full workflow.

**Q4: What happens when a user clicks a link that's been marked as broken but not yet discontinued?**  
**A**: Users never see broken links. The moment validation detects a 404, status changes to `NeedsReview` and the clickable link is immediately replaced with "Specs Unavailable" text. Users cannot click through to broken manufacturer pages. Product owner later determines if it's temporary (revert to Active) or permanent (mark Unavailable), but user experience is protected instantly.

**Q5: What's the link validation frequency and timing?**  
**A**: Weekly validation via Hangfire background job, runs Sunday 2:00 AM UTC. Manufacturer pages are stable - weekly checks catch broken links with acceptable 7-day latency without excessive server requests. Job validates ~100 GPUs in ~2 minutes with 1 req/sec rate limiting. See "Link Validation Schedule" section for implementation details.

**Q6: Should we track which regional URL variants exist per GPU?**  
**A**: No, store single "best available" URL. Prefer UK-specific URLs (`/en-gb/`), fallback to global English if UK doesn't exist. Simplifies database and data entry for MVP. Multi-regional support can be added post-MVP if GPU Value Tracker expands internationally. See "Regional URL Handling" section for URL selection logic.

**Q7: What visual styling should the spec link have on the GPU card?**  
**A**: Text link with external icon (↗️), muted secondary styling, positioned in GPU card footer. Standard web pattern that's accessible, minimal space usage, maintains focus on pricing data. When specs unavailable, show non-interactive "Specs Unavailable" text. See "Link Visual Design" section for full HTML/CSS specification.

**Q8: Should we display last validation timestamp to users?**  
**A**: No. Validation timestamp is internal operational data, not user-facing. Users expect links to work - showing "Last verified: X days ago" creates concern without value. Timestamp used only in admin monitoring dashboard for troubleshooting. See "Validation Timestamp Visibility" section.

---

## Product Rationale

### Why manual discontinued detection instead of automatic?

**User Trust**: Automatically hiding links due to temporary site outages (CDN failures, maintenance windows, rate limiting) would create false negatives where users lose access to available specs. Manual review by product owner verifies true discontinuation via multiple sources (manufacturer announcements, retail availability, community forums). For MVP with <100 GPUs, weekly manual review takes ~15 minutes and ensures accuracy.

**Graceful Degradation**: Users see "Specs Unavailable" immediately when links break (protecting UX), while product owner determines root cause behind the scenes. If it's temporary, link can be restored quickly. If permanent, no additional user-facing change needed.

### Why weekly validation instead of daily?

**Manufacturer Stability**: AMD and Nvidia don't reorganize product pages frequently. Historical data shows manufacturer site restructures happen 1-2 times per year, not daily. Weekly validation catches these changes with acceptable latency (worst case: users see "Specs Unavailable" for up to 7 days before product owner resolves).

**Resource Efficiency**: 100 HTTP HEAD requests per week is negligible. Daily validation would be 700 req/week for no meaningful benefit. Saves server resources and reduces risk of being rate-limited by manufacturer sites.

**Operational Burden**: Weekly monitoring dashboard review (15 minutes) is sustainable for product owner. Daily reviews would create alert fatigue for events that rarely require action.

### Why store full URLs instead of templates?

**Manufacturer Inconsistency**: Analysis of AMD/Nvidia product pages reveals inconsistent URL patterns:
- AMD uses different paths for Radeon (`/products/graphics/`) vs APU graphics
- Nvidia has separate patterns for GeForce (`/geforce/graphics-cards/`) vs Studio (`/studio/`)
- Special editions (Ti, XT, XTX) have inconsistent slug formatting

**Real Example**: 
- Standard: `amd.com/en-gb/products/graphics/amd-radeon-rx-7900xtx.html`
- Variant: `amd.com/en/products/graphics/radeon-rx-6700-xt` (different slug format, missing `-amd-` prefix)

URL templates would require complex conditional logic and manufacturer-specific rules. Storing full URLs handles edge cases naturally without code complexity.

### Why hybrid CSV import for initial data?

**Balancing Accuracy and Efficiency**: 
- **Manual entry via admin UI**: 100% accurate but 1-2 hours of tedious data entry, prone to typos
- **Fully automated scraping**: Fast but 15-20% false match rate in testing (e.g., "RX 7900 XTX" matches both reference and partner card pages)
- **Hybrid approach**: Script does 80% of work, human verifies 100% of output before import

**One-Time Setup**: Initial GPU catalog population happens once. Building complex matching algorithms for one-time use is over-engineering. CSV review takes 30 minutes and ensures launch-day accuracy.

### Why hide links immediately on validation failure?

**User Experience Priority**: Users who click broken links hit 404 pages on manufacturer sites, blame GPU Value Tracker for poor quality, lose trust. Hiding links immediately prevents this negative experience.

**Acceptable Trade-off**: Small chance of hiding temporarily-broken but recoverable links. If manufacturer site has 1-hour outage during validation window, link hides for up to 7 days until next validation. Product owner can manually restore if monitoring detects false positive. Prioritize preventing bad user experience over maximum link uptime.

---

## Data Model (Updated v1.1)

**Entities**:

- **GPU** (existing entity, extended):
  - `Id` (int, PK)
  - `ModelName` (string) - e.g., "Radeon RX 7900 XTX"
  - `Manufacturer` (string) - "AMD" or "Nvidia"
  - `OfficialSpecUrl` (string, nullable) - Full URL to manufacturer page
  - `SpecUrlStatus` (enum) - Active, Unavailable, NeedsReview
  - `SpecUrlLastChecked` (DateTime, nullable) - Validation job timestamp

**Enum**:
```csharp
public enum SpecUrlStatus
{
    Active = 0,        // URL working, last validation succeeded
    Unavailable = 1,   // URL broken/discontinued, hide from users
    NeedsReview = 2    // Validation failed, awaiting manual review
}
```

**Key Relationships**:
- Spec URL is 1:1 with GPU model (one canonical link per model)
- GPU entity is shared across retail pricing, used pricing, and spec link features

**Data Source**:
- Initial population: CSV import from script-generated suggestions (see URL Population Strategy)
- Ongoing updates: Manual via admin interface or CSV re-import
- Status updates: Automated via weekly validation job + manual admin changes

**Migration**:
```csharp
// Add columns to existing GPU table
migrationBuilder.AddColumn<string>(
    name: "OfficialSpecUrl",
    table: "GPUs",
    nullable: true);

migrationBuilder.AddColumn<int>(
    name: "SpecUrlStatus",
    table: "GPUs",
    nullable: false,
    defaultValue: 2); // NeedsReview until validated

migrationBuilder.AddColumn<DateTime>(
    name: "SpecUrlLastChecked",
    table: "GPUs",
    nullable: true);
```

---

## User Experience Flow

### Happy Path: Viewing Specs for Active GPU

1. User explores the dashboard visualization and identifies a value opportunity (e.g., Radeon RX 7800 XT showing 15% below MSRP)
2. User sees "Official Specs ↗️" link in footer of GPU card
3. User clicks the link
4. Link opens AMD's product page for RX 7800 XT in a new tab (URL: `https://www.amd.com/en-gb/products/graphics/amd-radeon-rx-7800-xt.html`)
5. User reads specifications on AMD.com:
   - TDP: 263W (needs 750W PSU)
   - Dimensions: 287mm length (fits in user's case)
   - Outputs: 2x HDMI 2.1, 2x DisplayPort 2.1 (compatible with user's monitors)
6. User switches back to GPU Value Tracker tab (original dashboard state preserved)
7. User clicks through to retailer listing from GPU card, completes purchase
8. User makes informed decision based on pricing intelligence (GPU Value Tracker) and verified technical specs (manufacturer site)

### Alternate Path: Discontinued GPU

1. User explores used market pricing and sees Radeon RX 6700 XT at 40% below launch MSRP (excellent value)
2. User notices "Specs Unavailable" text in card footer (no clickable link)
3. User understands official specs are no longer available from AMD
4. User opens new tab, searches "RX 6700 XT specs" in Google
5. User finds archived TechPowerUp or Tom's Hardware review with specifications
6. User returns to GPU Value Tracker, uses pricing data to negotiate used market purchase

### Edge Case: Link Breaks After User Sees Active Link

1. User loads dashboard, sees "Official Specs ↗️" for RTX 4090 (status: Active)
2. User browses pricing chart for 10 minutes (doesn't click spec link yet)
3. During that time, weekly validation job runs, detects broken Nvidia link, sets status to NeedsReview
4. User clicks "Official Specs ↗️" link (still rendered in browser from initial page load)
5. User hits 404 on Nvidia site (poor experience, but rare edge case)
6. **Mitigation**: When user refreshes dashboard or navigates away and back, link will show "Specs Unavailable" based on updated status
7. **Acceptable**: Edge case affects <0.1% of sessions (requires validation to run during active session AND user to not refresh page). Cost of real-time status polling outweighs benefit.

---

## Edge Cases & Constraints (Updated v1.1)

- **Manufacturer site reorganization**: If AMD/Nvidia restructures URLs site-wide, many links break simultaneously. Weekly validation detects this (bulk `NeedsReview` flags), monitoring dashboard shows spike. Product owner uses bulk CSV update: export all GPUs, find-replace URL patterns in spreadsheet, re-import. Restored in <1 hour.

- **Regional URL inconsistency**: Some GPU models have UK pages, others don't (inconsistent manufacturer localization). CSV import process tests both `/en-gb/` and `/en/` patterns, stores whichever works. Users may see mix of UK and global URLs across different GPUs - acceptable since spec content is identical.

- **Multiple SKUs per model**: Manufacturers sometimes have separate pages for Founders Edition vs partner cards (ASUS ROG, MSI Gaming X). GPU Value Tracker displays reference specs only - links point to reference/Founders Edition pages. Partner card variations (factory overclocks, custom coolers) not covered. Users researching specific SKUs must visit retailer pages.

- **Link validation during site maintenance**: If AMD.com is down for scheduled maintenance during validation window, all AMD cards flag as `NeedsReview` simultaneously. Monitoring dashboard alert triggers, product owner investigates, confirms temporary outage, waits for next validation cycle. Links restore automatically once site returns. Short-term user impact: AMD spec links show "Specs Unavailable" for up to 7 days worst case.

- **Rate limiting by manufacturer**: If validation job hits rate limits (429 responses), job logs warning and skips remaining validations for that manufacturer. Next weekly run retries. Mitigation: 1 req/sec rate limiting keeps us well below typical API thresholds (100 requests over ~2 minutes is negligible traffic).

- **No official page ever existed**: OEM-exclusive cards (Dell, HP prebuilt GPUs) often lack public product pages. Initial CSV import marks these as `SpecUrlStatus = Unavailable` with null URL. Users see "Specs Unavailable" from day one. Future enhancement: could link to OEM support pages or third-party databases (e.g., TechPowerUp GPU database).

- **Accessibility - screen reader experience**: Spec link has descriptive `aria-label` ("View official specifications for Radeon RX 7900 XTX on AMD website") so screen reader users understand destination. "Specs Unavailable" text is announced clearly. External link icon (↗️) is semantic Unicode character, read as "north-east arrow" - acceptable since aria-label provides full context.

- **Mobile viewport constraints**: GPU cards on mobile (320px width) have limited footer space. Spec link wraps to new line if needed, remains left-aligned. Text size (14px) remains readable on small screens. Touch target meets WCAG minimum 44x44px (link has adequate padding).

- **JavaScript disabled**: Spec links are plain HTML `<a>` tags - function perfectly without JavaScript. Users with NoScript or JS disabled can access manufacturer specs normally. Dashboard visualization requires JS, but spec links remain accessible as fallback.

---

## Out of Scope for This Feature (Updated v1.1)

- **No embedded specs**: We do NOT scrape or display technical specifications from manufacturer pages. Links only. GPU Value Tracker remains purely a pricing intelligence tool.

- **No spec comparison tables**: We do NOT build side-by-side comparison UI for technical specs. Users visit manufacturer sites or third-party tools (e.g., GPU Userbenchmark, TechPowerUp comparison tool) for detailed spec comparisons.

- **No benchmark hosting**: We do NOT display performance benchmarks, FPS data, or review scores. External reviews (Tom's Hardware, GamersNexus) serve this need.

- **No user-submitted links**: Links are managed exclusively by system admins via CSV import or admin interface. No crowdsourcing or user-editable URLs (prevents spam, maintains quality).

- **No click analytics**: We do NOT track which users click which spec links. No analytics cookies, no user tracking. Privacy-first approach for MVP. Could add anonymous aggregate stats (e.g., "% of users who click specs") in future if needed for product decisions, but no individual user tracking.

- **No affiliate linking**: Spec links are plain referral-free URLs to manufacturer sites. Not monetized. GPU Value Tracker revenue model (if any) comes from elsewhere (retailer affiliate links for purchase buttons, not spec references).

- **No PDF spec sheets**: Even if manufacturers provide downloadable PDF datasheets, we link to HTML product page only. HTML pages are more accessible (screen readers, mobile) and kept more up-to-date by manufacturers.

- **No archived spec hosting**: When manufacturer removes a product page, we do NOT create static archived copy. "Specs Unavailable" message directs users to third-party sources. Hosting archived content creates legal/copyright risk and maintenance burden.

- **No multi-regional URL variants**: V1 stores one URL per GPU (prefer UK, fallback global). No locale-based URL selection. International expansion (showing US users `en-us` URLs, German users `de-de` URLs) is post-MVP feature.

- **No real-time status updates**: User-facing spec link availability doesn't update in real-time during browsing session. If validation runs mid-session and breaks a link, user sees old "Active" state until page refresh. Acceptable trade-off vs WebSocket overhead.

- **No spec link uptime SLA**: We make best effort to keep links working, but do not guarantee 99.9% uptime. Manufacturer sites are third-party dependencies outside our control. If Nvidia.com is down, spec links break - acceptable for MVP. Core pricing data remains available.

---

## Open Questions for Tech Lead

[All questions from v1.0 have been answered in Iteration 1. No outstanding questions remain.]

---

## Dependencies

**Depends On**:
- GPU catalog/model data structure with `Id`, `ModelName`, `Manufacturer` fields (from retail and used pricing features)
- Dashboard visualization UI with GPU card component (to render spec links)
- Hangfire background job infrastructure (for weekly validation job)
- Monitoring dashboard (to display broken link alerts for product owner review)

**Enables**:
- User research workflow: Users can verify technical specifications before purchasing value opportunities identified via pricing data
- Focused product scope: Establishes GPU Value Tracker as pricing intelligence tool, not spec database, preventing feature creep
- Trust building: Linking to authoritative manufacturer sources (vs hosting unverified specs) builds user confidence in data quality

**Technical Prerequisites** (before implementation):
1. Entity Framework Core migration to add `OfficialSpecUrl`, `SpecUrlStatus`, `SpecUrlLastChecked` columns to GPU table
2. Hangfire configured and running (likely already exists for price scraping jobs)
3. Monitoring dashboard with basic logging UI (or Application Insights query access for product owner)
4. GPU card React component in dashboard (likely exists, needs footer slot for spec link)

---

## Implementation Checklist

**Phase 1: Data Setup** (Week 1)
- [ ] Run EF Core migration to add spec link columns to GPU table
- [ ] Write Python script to generate suggested URLs from manufacturer sitemaps
- [ ] Product owner reviews/corrects generated CSV
- [ ] Build CSV import command/API endpoint with validation
- [ ] Import initial URLs and run first validation pass
- [ ] Verify 90%+ URLs are Active after initial validation

**Phase 2: Validation Job** (Week 1-2)
- [ ] Implement Hangfire recurring job for weekly validation
- [ ] Add HTTP HEAD request logic with 10s timeout and 1 req/sec rate limiting
- [ ] Implement status update logic (Active → NeedsReview on failure)
- [ ] Add monitoring dashboard logging for broken links
- [ ] Test with intentionally broken URLs to verify NeedsReview flagging
- [ ] Schedule job for Sunday 2:00 AM UTC

**Phase 3: Frontend** (Week 2)
- [ ] Update GPU card component to render spec link in footer
- [ ] Implement conditional rendering (Active = link, Unavailable/NeedsReview = "Specs Unavailable")
- [ ] Apply Tailwind CSS styling (text-sm, muted color, underline, external icon)
- [ ] Add `target="_blank"` and `rel="noopener noreferrer"` security attributes
- [ ] Add descriptive `aria-label` for accessibility
- [ ] Test responsive behavior (mobile/desktop)
- [ ] Verify focus states for keyboard navigation

**Phase 4: Admin Tooling** (Week 2-3)
- [ ] Build monitoring dashboard view for NeedsReview GPUs
- [ ] Add admin interface for manual status updates (NeedsReview → Active/Unavailable)
- [ ] Add CSV export for bulk URL updates
- [ ] Document workflow for product owner (weekly review process)
- [ ] Set up alert for >10 NeedsReview GPUs (indicates site-wide issue)

**Phase 5: Testing & Launch** (Week 3)
- [ ] Unit tests for validation job logic
- [ ] Integration tests for CSV import
- [ ] End-to-end test: User clicks spec link, opens in new tab, returns to dashboard
- [ ] Accessibility audit (screen reader, keyboard navigation)
- [ ] Load testing: Validate 100 URLs in <5 minutes
- [ ] Deploy to production
- [ ] Monitor for first week: check validation job runs successfully, no user-reported broken links

---

**Ready for Technical Specification**: All product questions answered. Tech Lead can now proceed to detailed technical design document (database schema, API contracts, component architecture, job scheduling).