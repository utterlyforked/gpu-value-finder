# Manufacturer Reference Links - Feature Requirements

**Version**: 1.0  
**Date**: 2025-01-10  
**Status**: Initial - Awaiting Tech Lead Review

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

## Acceptance Criteria

- Each GPU card displayed in the dashboard has a clearly labeled link (e.g., "Official Specs", "View Specs") to the manufacturer's product page
- Links open in a new browser tab to preserve the user's position in the dashboard
- Links point to official AMD product pages for Radeon cards
- Links point to official Nvidia product pages for GeForce cards
- No benchmark data, performance reviews, or editorial content about GPU specs is hosted on GPU Value Tracker
- If a GPU's official product page no longer exists (discontinued models), the link either points to the manufacturer's archive page or displays a "Discontinued" label with no clickable link
- Links are validated as part of the data pipeline to detect broken links
- Users can identify which GPUs have active spec links vs discontinued models at a glance

---

## Functional Requirements

### Link Display

**What**: Every GPU card shown in the dashboard visualization includes a visible link to official manufacturer specifications.

**Why**: Users who identify value opportunities need to verify technical details (TDP, physical dimensions, port configuration) before committing to a purchase. Providing one-click access to authoritative specs reduces friction in the research process.

**Behavior**:
- Link appears on each GPU card in the dashboard
- Link text is clear and action-oriented (e.g., "Official Specs", "View AMD Specs", "Nvidia Product Page")
- Link is visually distinct but not dominant (secondary button or text link styling)
- Link positioning is consistent across all GPU cards

### Link Targets

**What**: Links point to the official product page on AMD.com or Nvidia.com, depending on the manufacturer.

**Why**: Official manufacturer pages are the authoritative source for specifications. They're kept up-to-date, include detailed technical specs, and provide driver download links.

**Behavior**:
- Radeon cards link to `https://www.amd.com/en/products/graphics/...`
- Nvidia cards link to `https://www.nvidia.com/en-gb/geforce/graphics-cards/...`
- Links use UK-localized URLs where available (`/en-gb/`)
- Links open in a new tab (`target="_blank"` with `rel="noopener noreferrer"`)
- Links include GPU model in the URL path (e.g., `/radeon-rx-7900-xtx/`)

### Discontinued GPU Handling

**What**: GPUs that no longer have active product pages on manufacturer sites are handled gracefully.

**Why**: Used market pricing includes cards from previous generations that manufacturers have removed from their active product catalogs. Users should know when official specs aren't available so they can seek alternative sources (review archives, third-party documentation).

**Behavior**:
- If official product page no longer exists, link either:
  - Points to manufacturer's archive/legacy products section, OR
  - Is replaced with a "Discontinued" badge/label with no clickable link
- Determination of "discontinued" status is part of the data model (see below)
- Users can visually distinguish active vs discontinued cards

### Link Validation

**What**: Links are periodically tested to ensure they're not broken.

**Why**: Manufacturer sites reorganize; product pages move or disappear. Broken links damage user trust and create friction.

**Behavior**:
- During data scraping/update cycles, links are validated (HTTP HEAD request or similar)
- If a link returns 404 or similar error, it's flagged as broken in the database
- Broken links trigger a "discontinued" status change
- Admin/monitoring dashboard shows count of broken links for manual review

---

## Data Model (Initial Thoughts)

**Entities This Feature Needs**:

- **GPU**: Core GPU model entity (already exists from other features)
  - Add field: `officialSpecUrl` (string, nullable)
  - Add field: `specUrlStatus` (enum: Active, Discontinued, Broken)
  - Add field: `specUrlLastChecked` (timestamp)

**Key Relationships**:
- GPU entity is shared across retail pricing, used pricing, and spec link features
- Spec URL is stored per GPU model, not per listing (one canonical link per model)

**Data Source**:
- Initial spec URLs will be manually seeded or scripted during GPU catalog setup
- URLs are validated periodically by background job
- Status field updates based on validation results

---

## User Experience Flow

### Happy Path: Viewing Specs for Active GPU

1. User explores the dashboard visualization and identifies a value opportunity (e.g., Radeon RX 7800 XT)
2. User sees "Official Specs" link on the GPU card
3. User clicks the link
4. Link opens AMD's product page for RX 7800 XT in a new tab
5. User reads specifications (TDP, dimensions, outputs) on AMD.com
6. User switches back to GPU Value Tracker tab to continue comparing prices
7. User makes informed purchase decision based on pricing data and verified specs

### Alternate Path: Discontinued GPU

1. User explores used market pricing and sees a Radeon RX 6700 XT at a great price
2. User notices "Discontinued" badge instead of a clickable link
3. User understands official specs are no longer available from AMD
4. User searches for third-party reviews or archived specs if needed (outside GPU Value Tracker)

---

## Edge Cases & Constraints

- **Manufacturer site reorganization**: If AMD or Nvidia restructures their product page URLs, many links could break simultaneously. Link validation job should detect this and flag for manual review. Consider storing URL patterns/templates for easier bulk updates.

- **Regional URL variations**: UK-specific URLs (`/en-gb/`) may not exist for all models. Fallback to global English (`/en-us/` or `/en/`) if UK page doesn't exist.

- **Multiple SKUs per model**: Manufacturers sometimes have separate pages for reference design vs partner cards (ASUS, MSI variants). GPU Value Tracker focuses on reference models only; link should point to reference/official model page.

- **Link rot over time**: Older cards (3+ years) are more likely to have broken links. Validation frequency could be tiered: monthly for recent cards, quarterly for older cards.

- **No official page ever existed**: Some cards (especially from smaller manufacturers or OEM-only models) may never have had an official product page. These should be marked "Discontinued" or "N/A" from initial seeding.

- **Accessibility**: Links must have descriptive text for screen readers ("View official specifications on AMD.com" vs generic "Click here").

---

## Out of Scope for This Feature

- **No embedded specs**: We do NOT scrape or display specifications from manufacturer pages. Links only.

- **No spec comparison tools**: We do NOT build side-by-side spec comparison tables. Users visit manufacturer sites for that.

- **No benchmark hosting**: We do NOT display performance benchmarks, FPS data, or review scores. This is purely a link to official specs.

- **No user-submitted links**: Links are managed by the system, not crowdsourced. Users cannot suggest or edit spec URLs.

- **No link analytics**: We do NOT track which users click which spec links (privacy-focused; no user tracking in v1).

- **No affiliate linking**: These are plain links to manufacturer sites, not affiliate or referral links.

- **No PDF spec sheets**: If manufacturers provide downloadable PDF specs, we link to the HTML product page, not directly to PDFs.

---

## Open Questions for Tech Lead

1. **URL Storage Strategy**: Should we store full URLs per GPU model, or store a URL pattern/template with model slug substitution? (Trade-off: flexibility vs easier bulk updates)

2. **Link Validation Frequency**: How often should we validate spec URLs? Daily (same as price scraping) or less frequently (weekly/monthly)?

3. **Discontinued Detection**: Should we automatically mark a GPU as "Discontinued" after N consecutive failed link validations, or require manual review?

4. **Initial URL Seeding**: How do we populate initial spec URLs for all GPUs? Manual entry, scripted scraping of manufacturer sitemaps, or third-party API?

5. **Fallback Behavior**: If a UK-specific URL (`/en-gb/`) doesn't exist, should we automatically try global English (`/en/`) or store both URLs in the database?

---

## Dependencies

**Depends On**:
- GPU catalog/model data structure (from retail and used pricing features)
- Dashboard visualization (to display the links on GPU cards)

**Enables**:
- User research workflow (users can verify specs before purchasing identified value opportunities)
- Keeps GPU Value Tracker focused on pricing intelligence without feature creep into spec databases