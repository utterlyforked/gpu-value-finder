# Manufacturer Reference Links - Technical Questions (Iteration 1)

**Status**: NEEDS CLARIFICATION
**Iteration**: 1
**Date**: 2025-01-10

---

## Summary

After reviewing the specification, I've identified **8 areas** that need clarification before implementation can begin. These questions address:
- URL storage and management strategy
- Link validation approach and error handling
- Data seeding and maintenance workflows
- User-facing behavior for edge cases
- Visual design integration with dashboard

The feature concept is clear (provide links to manufacturer specs without hosting content), but several implementation details need product decisions to proceed.

---

## CRITICAL Questions

These block core implementation and must be answered first.

### Q1: How should we populate initial spec URLs for the existing GPU catalog?

**Context**: The PRD mentions "manually seeded or scripted during GPU catalog setup" but doesn't specify the preferred approach. This is blocking because we need to know the data model and whether to build import tooling.

For a catalog of (estimating) 50-100 GPU models across AMD and Nvidia, we need a practical approach that balances accuracy with effort.

**Options**:

- **Option A: Manual entry via admin interface**
  - Impact: Build admin CRUD interface for GPU management, manually enter each URL
  - Trade-offs: 100% accuracy, but time-intensive (1-2 hours of data entry), prone to typos
  - Effort: Medium (admin UI + manual data entry)
  
- **Option B: CSV import with validation**
  - Impact: Create spreadsheet template, bulk import with validation, manual URL research still required
  - Trade-offs: Faster than UI entry, but still requires researching each URL manually
  - Effort: Low (simple import script + spreadsheet work)
  
- **Option C: Scripted discovery from manufacturer sitemaps**
  - Impact: Build scraper to parse AMD/Nvidia product sitemaps, match to GPU names, validate matches
  - Trade-offs: Automated but complex, may have false matches requiring manual review
  - Effort: High (scraper logic + matching algorithm + review workflow)

- **Option D: Hybrid - Import template with suggested URLs**
  - Impact: Script generates CSV with suggested URLs based on name matching, product owner reviews and corrects before import
  - Trade-offs: Best of both worlds - automation assists but human verifies accuracy
  - Effort: Medium (simple matching script + CSV review + import)

**Recommendation for MVP**: **Option D (Hybrid approach)**. Script generates suggested URLs by matching GPU model names to manufacturer sitemap URLs, product owner reviews the CSV for accuracy (fixing mismatches, marking discontinued models), then bulk import. This balances speed with accuracy and doesn't require building complex admin UI for what's essentially a one-time setup task.

---

### Q2: What's the URL structure for spec links - full URLs or template-based?

**Context**: The open questions section asks "Should we store full URLs per GPU model, or store a URL pattern/template with model slug substitution?" This fundamentally affects the database schema and flexibility.

**Options**:

- **Option A: Store full URLs per GPU**
  - Impact: Database stores `https://www.amd.com/en-gb/products/graphics/radeon-rx-7900-xtx.html` for each model
  - Trade-offs: Simple, flexible (handles manufacturer URL variations), but harder to bulk-update if AMD/Nvidia changes URL patterns
  - Database: Single `officialSpecUrl` column per GPU (VARCHAR)
  
- **Option B: Store URL templates + model slugs**
  - Impact: Store template pattern like `https://www.amd.com/en-gb/products/graphics/{model-slug}` with separate `modelSlug` field
  - Trade-offs: Easier bulk updates (change template, all URLs update), but assumes consistent manufacturer URL patterns which may not be true
  - Database: Need `officialSpecUrlTemplate` + `modelSlug` columns, plus template management table

- **Option C: Store manufacturer-specific base URLs + model slugs**
  - Impact: Store `baseUrl` per manufacturer (AMD/Nvidia) plus `modelSlug` per GPU
  - Trade-offs: Middle ground - some reusability but handles per-manufacturer differences
  - Database: Manufacturer reference table with base URLs, GPU table with slugs

**Recommendation for MVP**: **Option A (Full URLs)**. Manufacturers don't have perfectly consistent URL patterns (some models have different paths, some include extra segments). Storing full URLs is simpler, more reliable, and handles edge cases naturally. If AMD changes their URL structure in the future, we'll need to validate and update URLs regardless of storage approach - the validation job (Q3) will detect this. Optimization can come later if needed.

---

### Q3: How should discontinued GPU detection work?

**Context**: The PRD mentions both automatic detection via link validation failures and potential manual review. Need to decide the workflow to avoid false positives (temporary site outages) and ensure accuracy.

**Options**:

- **Option A: Automatic after N consecutive failures**
  - Impact: After 3 consecutive 404 responses (or similar threshold), automatically set `specUrlStatus = Discontinued`
  - Trade-offs: Fully automated, but temporary site issues could false-flag as discontinued
  - Effort: Simple logic in validation job
  
- **Option B: Flag for manual review**
  - Impact: Failed validations set status to `NeedsReview`, admin dashboard shows list requiring manual check
  - Trade-offs: Prevents false positives, but requires human intervention
  - Effort: Need admin review interface
  
- **Option C: Hybrid - auto-mark older cards, flag recent cards**
  - Impact: GPUs older than 3 years auto-mark as discontinued after failures; newer cards flag for review
  - Trade-offs: Sensible heuristic (old cards likely discontinued, new cards likely temporary issues)
  - Effort: Medium (age-based logic + review interface)

- **Option D: Manual only**
  - Impact: Validation job detects broken links, sends alert/log, admin manually updates discontinued status
  - Trade-offs: Maximum control, minimal false positives, but requires monitoring
  - Effort: Low (just logging + manual database updates)

**Recommendation for MVP**: **Option D (Manual only)**. Given this is MVP and we likely have <100 GPUs, manual review of broken links is feasible and prevents false positives from temporary manufacturer site issues. Set up validation job to log broken links to monitoring dashboard, admin can manually mark as discontinued when confirmed. Can automate later if volume becomes unmanageable.

---

### Q4: What happens when a user clicks a link that's been marked as broken but not yet discontinued?

**Context**: There's a window between link validation detecting a 404 and the link being marked as discontinued (whether automatic or manual). Need to define user-facing behavior during this period.

**Options**:

- **Option A: Still show clickable link**
  - Impact: Link displays normally, user clicks and gets 404 on manufacturer site
  - Trade-offs: Simplest, but poor UX - user hits error
  
- **Option B: Show link with warning icon**
  - Impact: Display link with visual indicator (⚠️) and tooltip "This link may be outdated"
  - Trade-offs: Transparent, but doesn't prevent click-through to 404
  
- **Option C: Replace with "Specs Unavailable" message**
  - Impact: Remove clickable link, show non-interactive text
  - Trade-offs: Prevents bad experience, but might hide temporarily broken links that later recover

- **Option D: Show "Checking..." state**
  - Impact: Display "Verifying link..." message during validation period
  - Trade-offs: Honest but vague, could persist longer than expected

**Recommendation for MVP**: **Option C (Replace with "Specs Unavailable")**. If validation detects a broken link, immediately hide it from users even before marking as officially discontinued. This prevents poor UX of users clicking into 404s. If we later determine it was a temporary issue and the link recovers, validation will re-enable it. Users of GPU Value Tracker prioritize pricing data - they can Google specs if needed.

---

## HIGH Priority Questions

These affect major workflows but have reasonable defaults.

### Q5: What's the link validation frequency and timing?

**Context**: The PRD mentions "periodically tested" and asks "Daily (same as price scraping) or less frequently (weekly/monthly)?" Need to balance freshness with API rate limits and resource usage.

**Options**:

- **Option A: Daily with price scraping**
  - Impact: Validation runs as part of existing daily scraping job
  - Trade-offs: Catches broken links quickly, but 100 HEAD requests/day to manufacturer sites (might trigger rate limits)
  
- **Option B: Weekly validation**
  - Impact: Separate weekly background job validates all spec URLs
  - Trade-offs: Reasonable freshness, lower request volume, broken links could persist up to 7 days
  
- **Option C: Monthly validation**
  - Impact: Monthly job validates all URLs
  - Trade-offs: Very low overhead, but broken links could persist weeks
  
- **Option D: Adaptive frequency**
  - Impact: Validate new cards daily for first month, then weekly, then monthly as they age
  - Trade-offs: Optimal resource usage but more complex logic

**Recommendation for MVP**: **Option B (Weekly validation)**. Manufacturer sites don't reorganize frequently - weekly checks are sufficient to catch broken links without hammering their servers. A 7-day window where some links might be broken is acceptable given that users can still find specs via Google. Daily validation is overkill for reference links that rarely change.

---

### Q6: Should we track which regional URL variants exist per GPU?

**Context**: The PRD mentions "UK-localized URLs where available (`/en-gb/`)" with fallback to global English. Need to decide if we store multiple URL variants or just one canonical URL.

**Options**:

- **Option A: Store only UK URLs**
  - Impact: Single `officialSpecUrl` column, always points to `/en-gb/` when available
  - Trade-offs: Simple, but assumes UK users only (contradicts "global English fallback" mention)
  
- **Option B: Store primary URL with fallback logic**
  - Impact: Single URL stored (prefer `/en-gb/`, fall back to `/en/` or `/en-us/` if UK doesn't exist)
  - Trade-offs: One URL per GPU, logic handles preference at import time
  
- **Option C: Store multiple regional URLs**
  - Impact: Store UK, US, and global URLs where they exist, frontend selects based on user locale
  - Trade-offs: Most flexible for internationalization, but complexity for MVP
  - Database: Multiple columns or JSON field with URL variants

**Recommendation for MVP**: **Option B (Primary URL with fallback)**. Store one "best available" URL per GPU - prefer UK if it exists, otherwise global English. At data import time, check both URL patterns and save the one that works. This keeps the database simple while handling regional variance. If GPU Value Tracker later expands to multiple regions, can add URL variants in v2.

---

### Q7: What visual styling should the spec link have on the GPU card?

**Context**: The PRD says "visually distinct but not dominant (secondary button or text link styling)" and "positioning is consistent" but doesn't specify exact design. This affects dashboard component implementation.

**Options**:

- **Option A: Text link with icon**
  - Impact: Subtle underlined text link with external link icon (🔗 or ↗️)
  - Trade-offs: Minimal visual weight, clear affordance, standard pattern
  - CSS: Simple text styling, icon via Unicode or SVG

- **Option B: Secondary outline button**
  - Impact: Small button with border, no fill (e.g., "View Specs →")
  - Trade-offs: More prominent, clear CTA, but takes more space on card
  - CSS: Button component with secondary variant

- **Option C: Icon-only button**
  - Impact: Small circular button with just external link icon
  - Trade-offs: Minimal space, but less discoverable (users might not know what it does)
  - Accessibility: Would need tooltip/aria-label

- **Option D: Compact badge/pill**
  - Impact: Small pill-shaped badge with "Specs" text
  - Trade-offs: Subtle, fits in card header/footer nicely
  - CSS: Badge component styling

**Recommendation for MVP**: **Option A (Text link with icon)**. Standard web pattern, highly accessible, minimal space usage. Position it in the GPU card footer or near the model name. Users immediately understand it's clickable and external. Example: "Official Specs ↗️" in a muted color to keep it secondary to pricing data.

---

## MEDIUM Priority Questions

Edge cases and polish items - can have sensible defaults if needed.

### Q8: Should we display last validation timestamp to users?

**Context**: The data model includes `specUrlLastChecked` timestamp. Should this be visible to users or just for internal monitoring?

**Options**:

- **Option A: Don't display to users**
  - Impact: Timestamp only visible in admin logs/monitoring
  - Trade-offs: Cleaner UI, users trust links work
  
- **Option B: Show on hover/tooltip**
  - Impact: Tooltip on link hover shows "Last verified: [date]"
  - Trade-offs: Transparency, but might create unnecessary concern if validation is delayed
  
- **Option C: Show for discontinued cards only**
  - Impact: Discontinued badge includes "As of [date]"
  - Trade-offs: Useful context for old cards, irrelevant for active links

**Recommendation for MVP**: **Option A (Don't display)**. Users don't need to know when we last checked a link - they expect it to work when they click it. Last checked timestamp is operational data for monitoring/debugging, not user-facing. Keep the UI focused on pricing insights.

---

## Notes for Product

- **Q1 (URL population)** is the most critical blocker - we need to know the data entry workflow before building any database schema or import tooling.

- **Q2 (URL storage)** and **Q3 (discontinued detection)** are tightly coupled - the answers affect database design and validation job architecture.

- **Q7 (visual design)** can be mocked up quickly - if you have a design preference or can provide a wireframe, that would accelerate frontend implementation.

- Several questions (Q4-Q6, Q8) have sensible defaults, so if you're comfortable with the recommendations, we can proceed with those and iterate later if needed.

- Once Q1-Q3 are answered, I can proceed to detailed technical specification and database schema design.

- Happy to do another iteration if these answers raise follow-up questions!