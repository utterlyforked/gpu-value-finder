# Manufacturer Reference Links - Technical Review (Iteration 2)

**Status**: ✅ READY FOR IMPLEMENTATION
**Iteration**: 2
**Date**: 2025-01-10

---

## Summary

This feature specification is sufficiently detailed to proceed with implementation. All critical questions from Iteration 1 have been answered clearly and comprehensively. The product requirements provide concrete guidance on data model, workflows, validation logic, and user experience.

## What's Clear

### Data Model
- **GPU entity extension** with three new fields clearly defined:
  - `OfficialSpecUrl` (string, nullable) - stores full URL
  - `SpecUrlStatus` (enum: Active, Unavailable, NeedsReview) - tracks link health
  - `SpecUrlLastChecked` (DateTime, nullable) - validation timestamp
- **Full URL storage approach** (not templates) with clear rationale for handling manufacturer inconsistencies
- **Status enum** with well-defined states and transitions
- **Migration strategy** specified with default values

### Business Logic

#### URL Population Workflow
- **Hybrid CSV import** process with three clear steps:
  1. Script generates suggested URLs from manufacturer sitemaps
  2. Product owner reviews/corrects in spreadsheet
  3. Bulk import with validation
- **Regional URL selection logic**: Prefer `/en-gb/`, fallback to `/en/` or `/en-us/`
- **Edge case handling** for missing matches, multiple URLs, name variations

#### Validation Job
- **Schedule**: Weekly, Sunday 2:00 AM UTC
- **Process**: HTTP HEAD requests with 10s timeout, 1 req/sec rate limiting
- **Status transitions**:
  - 200 OK → Active
  - 404/503/timeout → NeedsReview
  - Skip Unavailable GPUs
- **Monitoring**: Log broken links to dashboard with details

#### Discontinued Detection Workflow
- **User-facing**: Links hide immediately when validation fails (show "Specs Unavailable")
- **Admin workflow**: Product owner reviews monitoring dashboard weekly
- **Manual decisions**: Reset to Active (temporary issue), update URL (moved), or mark Unavailable (discontinued)
- **No false positives**: Manual review prevents hiding temporarily-broken links permanently

### API Design
- Spec links are rendered client-side from GPU data (no new API endpoints needed)
- CSV import via admin command or API endpoint (implementation choice)
- Monitoring dashboard queries `SpecUrlStatus = NeedsReview` GPUs

### UI/UX

#### Component Behavior
- **Active status**: Clickable "Official Specs ↗️" link in GPU card footer
- **Unavailable/NeedsReview status**: Non-interactive "Specs Unavailable" text
- **Link attributes**: `target="_blank"`, `rel="noopener noreferrer"`
- **Accessibility**: Descriptive `aria-label` with full context

#### Visual Design
- **Positioning**: Right-aligned in GPU card footer
- **Styling**: 14px text, muted color (gray-600), underlined, hover state (gray-900)
- **Icon**: Unicode ↗️ (U+2197) or external link SVG
- **Responsive**: Wraps to new line on mobile if needed

### Edge Cases

#### Addressed in Specification
- **Manufacturer site reorganization**: Bulk CSV update workflow defined
- **Regional URL inconsistency**: Mixed UK/global URLs acceptable
- **Multiple SKUs per model**: Link to reference/Founders Edition only
- **Validation during maintenance**: Temporary false positives, auto-recover next week
- **Rate limiting**: 1 req/sec keeps us below thresholds
- **OEM-exclusive cards**: Mark as Unavailable with null URL from day one
- **Accessibility**: Screen reader labels, keyboard navigation, touch targets
- **Mobile constraints**: Text wrapping, adequate spacing
- **JavaScript disabled**: Plain HTML links work without JS
- **Mid-session status changes**: User sees stale state until refresh (acceptable)

### Validation Rules
- **URL format**: Full HTTPS URLs to amd.com or nvidia.com domains
- **Timeout**: 10 seconds per HTTP HEAD request
- **Rate limiting**: 1 request per second (100 GPUs = ~2 minutes)
- **Success criteria**: 200 OK response
- **Failure criteria**: 404, 503, timeout, or non-200 status

### Key Decisions

#### Strategic Choices (Well-Justified)
- **Weekly validation frequency**: Manufacturer pages are stable, daily checks unnecessary
- **Manual discontinued detection**: Prevents false positives from temporary outages
- **Full URL storage**: Handles manufacturer URL inconsistencies naturally
- **Hybrid CSV import**: Balances automation with accuracy for one-time setup
- **Hide links immediately**: Protects user experience, acceptable trade-off vs maximum uptime
- **No timestamp display**: Operational data, not user-facing information
- **Single regional URL**: Simplifies MVP, internationalization deferred to v2

#### Security & Accessibility
- **`rel="noopener noreferrer"`**: Prevents security issues with `target="_blank"`
- **Descriptive aria-labels**: Screen reader users understand link destination
- **Focus states**: Keyboard navigation support
- **WCAG AA compliance**: Color contrast, touch target sizing

## Implementation Notes

### Database
- **Migration**: Add three columns to existing `GPU` table
- **Default values**: `SpecUrlStatus = NeedsReview` until first validation
- **Indexes**: Consider index on `SpecUrlStatus` for monitoring queries (100 rows won't need it, but good practice)
- **Data type**: `string?` for nullable URL field

### Authorization
- **CSV import**: Admin-only access (add to existing admin role)
- **Monitoring dashboard**: Admin-only view
- **Manual status updates**: Admin-only actions
- **User-facing links**: Public read access (no auth required)

### Validation Job (Hangfire)
- **Job ID**: `"validate-spec-urls"` (recurring job identifier)
- **Cron schedule**: `"0 2 * * 0"` (Sunday 2:00 AM UTC)
- **Queue**: Use default queue (or dedicated "maintenance" queue if exists)
- **Retry policy**: No retries (wait for next weekly run)
- **Logging**: Use structured logging with GPU IDs, URLs, status codes

### Frontend Components
- **GPU Card Component**: Extend existing card footer with conditional spec link
- **Conditional Rendering**:
  ```tsx
  {gpu.specUrlStatus === SpecUrlStatus.Active ? (
    <a href={gpu.officialSpecUrl} ...>Official Specs ↗️</a>
  ) : (
    <span className="text-gray-400 italic">Specs Unavailable</span>
  )}
  ```
- **TypeScript Types**: Add new fields to GPU interface/type
- **No loading states**: Data fetched with existing GPU data (no separate API call)

### Tooling
- **Python script** for sitemap fetching: Use `requests`, `BeautifulSoup`, `fuzzywuzzy` for name matching
- **CSV format**: `GPUId,ModelName,SuggestedURL,Manufacturer,Notes` columns
- **Import validation**: Check URL format, manufacturer domain, required fields
- **Monitoring dashboard**: Query EF Core for `SpecUrlStatus.NeedsReview`, display in admin UI

### Key Technical Decisions
- **HTTP HEAD vs GET**: Use HEAD for validation (faster, only checks existence)
- **Follow redirects**: Yes, but log warning if final URL differs from stored URL
- **User-Agent header**: Send descriptive UA: `"GPU-Value-Tracker-Link-Validator/1.0"`
- **Timeout handling**: Treat timeouts as failures (set to NeedsReview)
- **Concurrent requests**: No, sequential with 1 req/sec delay (simple, avoids rate limits)

## Recommended Next Steps

1. **Create engineering specification** with:
   - Database migration SQL (EF Core migration code)
   - Hangfire job class implementation skeleton
   - React component interface changes
   - CSV import service architecture
   - Testing strategy (unit, integration, E2E scenarios)

2. **Set up Python environment** for URL discovery script:
   - Document dependencies (requests, beautifulsoup4, fuzzywuzzy)
   - Create script template with manufacturer sitemap URLs
   - Define CSV output format

3. **Plan initial data population**:
   - Schedule time for product owner CSV review (~30 minutes)
   - Coordinate import timing (staging first, then production)
   - Prepare rollback plan (revert migration if issues found)

4. **Configure monitoring**:
   - Set up Application Insights query for NeedsReview GPUs
   - Create admin dashboard widget or standalone page
   - Configure alerts for >10 NeedsReview GPUs (site-wide issue indicator)

---

## Why This is Ready

### Complete Requirements
Every "how should we..." question has been answered:
- ✅ URL population strategy defined (hybrid CSV)
- ✅ Storage approach specified (full URLs)
- ✅ Validation workflow detailed (weekly job, manual review)
- ✅ User experience designed (link styling, unavailable state)
- ✅ Edge cases addressed (outages, discontinued cards, mobile)

### Clear Implementation Path
An engineer can write a technical spec without guessing:
- Database schema is fully specified (field names, types, defaults)
- Validation logic has concrete rules (HTTP HEAD, 10s timeout, status transitions)
- UI design includes HTML structure and CSS classes
- Workflows have step-by-step processes (CSV import, discontinued detection)

### Bounded Scope
The PRD clearly states what's NOT included:
- No embedded specs, comparison tables, or benchmark hosting
- No user-submitted links or click analytics
- No real-time status updates or multi-regional URLs
- These are explicitly deferred or permanently out of scope

### Risk Mitigation
Product owner has thought through failure modes:
- Temporary outages won't auto-hide links (manual review prevents false positives)
- Manufacturer site reorganization has bulk update workflow
- Mid-session status changes are acceptable (no WebSocket overhead)
- Privacy-first approach (no user tracking)

### Pragmatic MVP Decisions
Every "why not X?" has clear rationale:
- Weekly validation: Manufacturer pages are stable
- Manual review: 15 minutes/week for <100 GPUs
- Full URL storage: Handles manufacturer inconsistencies
- No real-time updates: Overhead outweighs benefit

---

**This feature is ready for detailed engineering specification.** The requirements are comprehensive, unambiguous, and implementation-ready. No blocking questions remain.