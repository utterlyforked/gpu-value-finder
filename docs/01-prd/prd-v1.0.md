# GPU Value Tracker - Product Requirements Document

**Version**: 1.0  
**Date**: 2025-01-10  
**Status**: Initial Draft

---

## Vision

GPU Value Tracker is a web application that cuts through the marketing hype in the PC gaming GPU market to help builders identify real value. By aggregating live pricing data from both retail outlets (Scan, Ebuyer, Amazon) and used marketplaces (Facebook Marketplace, CEX, eBay), the application provides a visual representation of where genuine bargains exist across GPU generations.

The core insight is that "value" is dynamic. A previous-generation card at the right price can deliver better value than the latest release, even if it's slightly slower. GPU Value Tracker makes these opportunities immediately visible through intelligent data visualization, showing the performance-to-price sweet spots that shift daily as the market moves.

This isn't a review site or a benchmark database—it's a real-time market intelligence tool that answers one question: "Where's the actual value right now?"

---

## Problem Statement

PC builders face overwhelming noise in the GPU market. YouTube influencers push the latest cards, manufacturers create artificial urgency with limited releases, and genuine value opportunities are buried under hype. A 10fps performance difference often doesn't justify a £200 price premium, but identifying these value inversions requires manually checking dozens of retailers and marketplaces, understanding relative performance across generations, and doing mental math on price-to-performance ratios.

This problem affects experienced PC builders who understand that smart purchasing means looking across generations and considering used options, but who lack a tool that aggregates this data and makes value opportunities immediately visible.

---

## Target Users

- **Primary**: Experienced PC builders and enthusiasts who self-build their machines, understand GPU performance tiers, and actively look for value in both new and used markets. These users check GPU prices regularly, know the difference between Radeon and Nvidia architectures, and are comfortable buying used hardware. Age typically 25-45, active in PC building communities.

- **Secondary**: Upgrading gamers who have built at least one PC and are looking to upgrade their GPU without overspending. They understand basic GPU specs but may not track pricing across multiple sites.

---

## Core Features

### Feature 1: Live Retail Price Aggregation

**Purpose**: Track current average pricing for latest-generation GPUs from major UK retailers to establish the "new" baseline price

**User Stories**:
- As a PC builder, I want to see the current average retail price for the latest Radeon cards so that I know what buying new would cost
- As a PC builder, I want to see the current average retail price for the latest Nvidia cards so that I can establish a price baseline for value comparison
- As a PC builder, I want prices updated regularly so that I'm working with current market data, not stale pricing

**Acceptance Criteria**:
- System scrapes prices from Scan, Ebuyer, and Amazon for latest-generation cards (16GB+ only)
- Average retail price is calculated for each card model across all available listings
- Prices are refreshed at least daily
- Only cards currently in stock are included in average calculation
- Price data includes timestamp of last update
- Retail prices are displayed separately for Radeon and Nvidia (never mixed)

---

### Feature 2: Used Market Price Discovery

**Purpose**: Track average asking prices for used GPUs across marketplaces to identify target prices for used purchases

**User Stories**:
- As a PC builder, I want to see the current average asking price for used GPUs on the secondary market so that I can identify fair market value
- As a value-conscious builder, I want to compare used prices for previous-generation cards against new latest-gen cards so that I can spot value inversions
- As a bargain hunter, I want to see price trends for specific used card models so that I know when I'm looking at a good deal

**Acceptance Criteria**:
- System scrapes asking prices from Facebook Marketplace, CEX, and eBay for GPUs 16GB and larger
- Average used price is calculated per card model based on active listings
- Used prices are tracked for previous 2-3 generations (not just latest)
- Prices are refreshed at least daily
- Outliers (extremely high/low prices) are filtered from average calculation
- Used prices are displayed separately for Radeon and Nvidia architectures
- Price data includes number of listings found and timestamp

---

### Feature 3: Value Visualization Dashboard

**Purpose**: Present retail and used pricing data in a single-page visual format that makes value opportunities immediately obvious

**User Stories**:
- As a PC builder, I want to see a visual representation of all GPU prices and their relative performance so that value sweet spots are immediately apparent
- As a visual learner, I want pricing and performance data displayed graphically so that I can quickly identify where the best deals are
- As a comparison shopper, I want to see where retail and used prices overlap with performance tiers so that I can make informed purchasing decisions

**Acceptance Criteria**:
- Single-page dashboard displays all pricing data visually (not tables)
- Performance-to-price relationship is represented graphically (e.g., heat map, scatter plot, or similar visualization)
- "Value zones" where used prices meet or beat new price-to-performance are highlighted
- User can toggle between Radeon view and Nvidia view (never both simultaneously)
- Visualization updates automatically when underlying price data refreshes
- Visual design has "wow factor"—immediately impressive and clear
- Page loads in under 2 seconds with all visualizations rendered
- Visualization is responsive and works on desktop and tablet (mobile secondary)

---

### Feature 4: Manufacturer Reference Links

**Purpose**: Provide quick access to official specifications without duplicating content or bloating the site

**User Stories**:
- As a PC builder, I want to access official specifications for any GPU so that I can verify technical details
- As a researcher, I want canonical links to AMD and Nvidia's official product pages so that I can read full specs without leaving the ecosystem
- As a user, I want to avoid reading redundant benchmark data on this site so that I stay focused on value, not reviews

**Acceptance Criteria**:
- Each GPU card displayed has a link to the official AMD or Nvidia product page
- Links open in new tab
- Links are clearly labeled as "Official Specs" or similar
- No benchmark data, reviews, or editorial content is hosted on GPU Value Tracker
- Links are tested regularly to ensure they're not broken
- If official page doesn't exist (discontinued cards), link goes to OEM's archive or is marked "Discontinued"

---

### Feature 5: Radeon vs Nvidia Mode Switching

**Purpose**: Allow users to focus on one ecosystem at a time, since cross-manufacturer comparison is not useful

**User Stories**:
- As a Radeon user, I want to view only AMD cards so that I'm not distracted by Nvidia pricing
- As an Nvidia user, I want to view only Nvidia cards so that I can focus on my preferred ecosystem
- As a user, I want to easily toggle between Radeon and Nvidia views so that I can explore both markets if I'm undecided

**Acceptance Criteria**:
- Clear UI toggle between "Radeon" and "Nvidia" modes (e.g., tabs, toggle switch)
- Only one manufacturer's data is displayed at a time (never mixed)
- User's selection persists across page reloads (cookie or localStorage)
- Mode selection is prominent and above-the-fold
- Default mode is Radeon (arbitrary choice; could be user location-based in future)
- All data (retail prices, used prices, visualization) updates immediately on toggle

---

## Success Metrics

- **Daily Active Users**: 100+ users visiting daily within 3 months of launch
- **Engagement Rate**: Average session duration >3 minutes (indicates users are exploring the visualization)
- **Price Data Freshness**: 95%+ uptime on daily scraping jobs; data never more than 24 hours old
- **User Retention**: 30% of users return within 7 days of first visit
- **Value Discovery**: Track "clicks to OEM specs" as proxy for users researching cards identified as value opportunities

---

## Out of Scope (V1)

To maintain focus and ship quickly, the following are intentionally excluded:

- **No e-commerce**: Not selling cards, not affiliate links (may add in v2 if monetization desired)
- **No Intel Arc cards**: Focus on mature Radeon/Nvidia markets only
- **No manufacturer comparison**: No ASUS vs Gigabyte vs MSI; only reference AMD/Nvidia models
- **No 8GB cards**: Only 16GB VRAM and larger to focus on mid-to-high-end market
- **No editorial content**: No benchmarks, reviews, or articles—just pricing data
- **No user accounts**: No login, saved searches, or personalization in v1
- **No alerts**: No price drop notifications or email alerts (could add in v2)
- **No historical charts**: Only current pricing; no trend graphs over weeks/months
- **No mobile app**: Web-only; responsive design for mobile browsers is sufficient

---

## Technical Considerations

- **Platform**: Web application (desktop-first, responsive for tablet/mobile)
- **Scraping Infrastructure**: Reliable scheduled jobs to scrape retail and marketplace sites daily
- **Anti-scraping Mitigation**: Respectful scraping (rate-limiting, user agents, robots.txt compliance); expect to handle CAPTCHA or blocks gracefully
- **Data Storage**: Persistent storage for pricing data; ability to query by card model, date, source
- **Performance**: Visualization must load quickly; consider caching aggregated data
- **UK-Focused**: Pricing in GBP; UK retailer/marketplace focus (Scan, Ebuyer, Amazon UK, CEX, eBay UK, Facebook Marketplace UK)
- **Scalability**: Initial version can handle 1000s of daily users; scraping infrastructure should not overload target sites

---

## Timeline & Prioritization

**Phase 1 (MVP)**: Core features (live retail prices, used prices, basic visualization, mode toggle, OEM links) - Target 6-8 weeks  
**Phase 2**: Enhanced visualization (user-requested improvements), price history, alerts - Target 3 months post-launch

---

## Technical Architecture Notes

**Backend**: Scraping jobs (Hangfire or similar for scheduled tasks), API endpoints to serve aggregated price data, PostgreSQL for storage  
**Frontend**: React with TypeScript, data visualization library (D3.js, Recharts, or Plotly), Tailwind CSS for styling  
**Caching**: Redis for caching aggregated price data to speed up dashboard loads  
**Containerization**: Docker for local development and production deployment (K8s-ready)

---

**Next Steps**: Break down individual features for Tech Lead review.