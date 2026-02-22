# Radeon vs Nvidia Mode Switching - Feature Requirements

**Version**: 1.0  
**Date**: 2025-01-10  
**Status**: Initial - Awaiting Tech Lead Review

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

## Acceptance Criteria

- Clear UI toggle between "Radeon" and "Nvidia" modes is present (e.g., tabs, toggle switch, or segmented control)
- Only one manufacturer's data is displayed at a time—Radeon and Nvidia data are never mixed in the visualization
- User's selection persists across page reloads using browser localStorage
- Mode selection control is prominent and positioned above-the-fold (visible without scrolling)
- Default mode on first visit is Radeon (arbitrary starting point; no user preference data exists yet)
- All dashboard data updates immediately when user toggles mode: retail prices, used prices, value visualization, and OEM spec links all refresh to show only the selected manufacturer
- Mode switch is instant (no page reload required)
- Visual feedback indicates which mode is currently active (e.g., active tab styling, toggle position)

---

## Functional Requirements

### Mode Selection Control

**What**: A prominent UI element that allows users to switch between "Radeon" and "Nvidia" modes

**Why**: Users need immediate, obvious control over which manufacturer's data they're viewing. The control must be discoverable by first-time users and quickly accessible for returning users.

**Behavior**:
- Control is positioned at the top of the dashboard, above the value visualization
- Two options only: "Radeon" and "Nvidia" (no "All" or "Both" option)
- Clicking/tapping toggles to the other mode
- Active mode is visually distinct (e.g., bold text, highlighted background, underline)
- Control is keyboard-accessible (tab navigation, enter to toggle)

**Example UI Options**:
- Segmented control (pill-shaped toggle)
- Tab interface (Radeon tab | Nvidia tab)
- Toggle switch with labels on each side

---

### Data Filtering by Manufacturer

**What**: When mode is switched, all data displayed on the dashboard updates to show only GPUs from the selected manufacturer

**Why**: Mixing Radeon and Nvidia data creates meaningless comparisons and confuses the value analysis. Each ecosystem needs to be evaluated independently.

**Behavior**:
- Backend API accepts a `manufacturer` query parameter (`?manufacturer=radeon` or `?manufacturer=nvidia`)
- Frontend sends API request with selected manufacturer when mode changes
- Dashboard re-renders with filtered data:
  - Retail prices show only Radeon or Nvidia cards
  - Used market prices show only Radeon or Nvidia cards
  - Value visualization displays only the selected manufacturer's cards
  - OEM spec links point only to AMD or Nvidia product pages
- No mixing: if Radeon mode is active, zero Nvidia data appears anywhere on the page

---

### Persistence Across Sessions

**What**: User's manufacturer preference is saved in browser localStorage and restored on subsequent visits

**Why**: Users typically have a strong preference for one manufacturer. Forcing them to re-select every visit is annoying and creates unnecessary friction.

**Behavior**:
- On mode toggle, selected manufacturer is written to `localStorage` (key: `preferredManufacturer`, value: `radeon` or `nvidia`)
- On page load, application reads `localStorage` and sets mode to saved value
- If no saved preference exists (first visit), default to Radeon mode
- localStorage value is read before initial API call so correct data loads immediately
- If localStorage is unavailable (privacy mode, blocked), default to Radeon mode without error

---

### Default Mode

**What**: First-time users see Radeon mode by default

**Why**: Application must have a default starting state. Radeon is chosen arbitrarily (could equally be Nvidia). In future, could use geo-location or market share data to inform default, but v1 uses simple static default.

**Behavior**:
- If `localStorage.preferredManufacturer` is `null` or `undefined`, set mode to `radeon`
- Default mode applies only on first visit or if localStorage is cleared
- Once user toggles mode, their preference overrides default

---

### Instant Mode Switching

**What**: Switching between Radeon and Nvidia modes happens instantly without full page reload

**Why**: Page reloads feel slow and break the user's mental flow. This is a simple data filter change, not a navigation event.

**Behavior**:
- Clicking mode toggle triggers:
  1. Update localStorage with new preference
  2. API call to fetch data for new manufacturer
  3. Dashboard re-renders with new data
- No browser navigation (no URL change, no page reload)
- Loading state is shown briefly while new data fetches (e.g., skeleton loader or spinner on visualization area)
- If API call fails, show error message and keep previous mode active

---

## Data Model (Initial Thoughts)

**No new entities required**—this feature filters existing GPU data by manufacturer.

**GPU Entity** (already exists):
- Must have a `manufacturer` field (enum or string: `"Radeon"` or `"Nvidia"`)
- All queries for retail prices, used prices, and visualization data filter by this field

**Frontend State**:
- `selectedManufacturer`: `"radeon" | "nvidia"` (React state)
- Initialized from localStorage on mount
- Passed to all API calls as query parameter

**localStorage Schema**:
```json
{
  "preferredManufacturer": "radeon" // or "nvidia"
}
```

---

## User Experience Flow

### First Visit

1. User lands on dashboard
2. Application checks `localStorage.preferredManufacturer` → returns `null` (first visit)
3. Application defaults to Radeon mode
4. API fetches Radeon GPU data
5. Dashboard displays Radeon retail prices, used prices, value visualization
6. Mode toggle shows "Radeon" as active, "Nvidia" as inactive

### Switching Modes

1. User clicks "Nvidia" toggle
2. Frontend updates localStorage: `preferredManufacturer = "nvidia"`
3. Frontend sets `selectedManufacturer` state to `"nvidia"`
4. API request sent: `GET /api/v1/gpus?manufacturer=nvidia`
5. Loading indicator appears on visualization area
6. API returns Nvidia GPU data
7. Dashboard re-renders with Nvidia prices and visualization
8. Mode toggle updates to show "Nvidia" as active

### Returning User

1. User lands on dashboard
2. Application checks `localStorage.preferredManufacturer` → returns `"nvidia"`
3. Application sets mode to Nvidia automatically
4. API fetches Nvidia GPU data
5. Dashboard displays Nvidia data immediately
6. User doesn't have to re-select preference

---

## Edge Cases & Constraints

- **localStorage unavailable**: If localStorage is blocked (privacy mode, browser settings), application defaults to Radeon mode on every visit. No error shown to user; feature degrades gracefully.

- **Invalid localStorage value**: If `localStorage.preferredManufacturer` contains invalid value (e.g., `"intel"` due to manual editing), application ignores it and defaults to Radeon.

- **API failure during mode switch**: If API call fails when switching modes, show error message ("Unable to load Nvidia data. Please try again.") and keep previous mode active. User can retry toggle.

- **Slow API response**: While waiting for new manufacturer data, show loading skeleton over visualization area. Mode toggle remains interactive (user can toggle back if they change mind, cancelling in-flight request).

- **No data for selected manufacturer**: If API returns zero GPUs for selected manufacturer (unlikely but possible if scraping fails), show empty state message: "No [Radeon/Nvidia] data available. Check back soon."

- **Initial page load with saved preference**: On page load, don't show Radeon mode first and then switch to Nvidia—read localStorage before first render and load correct data immediately.

---

## Out of Scope for This Feature

This feature explicitly does NOT include:

- **"All Manufacturers" mode**: No option to view Radeon and Nvidia simultaneously. Cross-manufacturer comparison is not valuable and is intentionally excluded.

- **Intel Arc support**: Only Radeon and Nvidia in v1. If Intel Arc is added later, mode toggle becomes three-way, but that's a future feature.

- **User accounts with saved preferences**: localStorage only. No server-side preference storage or user accounts in v1.

- **URL-based mode selection**: Mode is not reflected in URL (e.g., no `/dashboard?manufacturer=nvidia`). This is a client-side filter, not a navigation state. Could add in v2 for shareable links.

- **Analytics on mode switching**: No tracking of which mode users prefer or how often they switch. Could add in v2 if product wants usage data.

- **Keyboard shortcuts**: No hotkeys (e.g., "R" for Radeon, "N" for Nvidia). Mode toggle is keyboard-accessible via tab navigation, but no custom shortcuts in v1.

---

## Open Questions for Tech Lead

- **API Design**: Should manufacturer filter be a query parameter (`?manufacturer=radeon`) or a route segment (`/api/v1/gpus/radeon`)? Query param is more RESTful, but route segment might be clearer.

- **Caching Strategy**: Should API responses for Radeon and Nvidia be cached separately in Redis? If user toggles back and forth, should we serve cached data or always fetch fresh?

- **Loading State**: How long should we wait before showing loading indicator? If API responds in <200ms, should we skip loading state to avoid flicker?

- **Error Handling**: If API call fails during mode switch, should we retry automatically or require user to click toggle again?

---

## Dependencies

**Depends On**: 
- Feature 1 (Live Retail Price Aggregation) - needs retail price data with manufacturer field
- Feature 2 (Used Market Price Discovery) - needs used price data with manufacturer field
- Feature 3 (Value Visualization Dashboard) - needs visualization that can re-render with filtered data

**Enables**: 
- All other features depend on this mode being set correctly to filter data
- Feature 4 (Manufacturer Reference Links) - OEM links must point to correct manufacturer based on active mode

---

**Note**: This is a foundational feature that affects the entire dashboard. The mode selection determines what data is fetched, displayed, and visualized across all other features. Implementation should happen early in development since other features depend on the `manufacturer` filter being in place.