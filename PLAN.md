# Chinese Deep Water Fishing Fleet Global Activity Map
## Implementation Plan

### Project Summary
Build a publication-quality global map of China's Distant Water Fishing (DWF) fleet activity (2022-2025) for U.S. policymaker briefings. Dual output: a high-resolution static map for print/presentations and a self-contained interactive HTML map for exploration. Pacific-centered Robinson projection with dark background styling. Government briefing quality with full source attribution.

---

## Design Decisions (Confirmed)

| Decision | Choice |
|----------|--------|
| Output format | Both: static image (PNG/PDF) + interactive HTML |
| Time range | 2022-2025 (4 years) |
| Base map style | Dark background (navy ocean, charcoal land) |
| Projection | Pacific-centered Robinson |
| Year encoding | Sequential color ramp (pale yellow 2022 -> deep crimson 2025) |
| Region insets | Americas & US Pacific (Galapagos, Argentina, American Samoa, Pacific islands) |
| Quality standard | Government briefing quality with sourcing |
| Interactive hosting | Self-contained static HTML files |
| Tech stack | Python (cartopy/matplotlib for static, Folium/Deck.gl for interactive) |
| Data sources | GFW fishing effort + API (AIS gaps, vessel identity), Marine Regions EEZ, Natural Earth basemap, curated incidents |
| Incidents | Collaborative curation (Claude researches, user verifies) |
| GFW API | User will register for free API key |

---

## Data Sources

### Primary Data
1. **GFW Fishing Effort v3.0** (Zenodo) - Gridded fishing hours by flag state, gear type, year. 0.01-degree resolution monthly. CC BY-SA 4.0.
2. **GFW Events API** - AIS-disabling gap events, transshipment encounters. Requires API key.
3. **GFW Vessel Identity** - Cross-referenced against 40+ registries. Identifies Chinese DWF vessels by flag, gear, size.
4. **Marine Regions EEZ v12** - World EEZ boundary polygons. Free download.
5. **Natural Earth** - Coastlines, land polygons, country boundaries, ocean bathymetry. Public domain.
6. **VIIRS Boat Detection (EOG)** - Nighttime light detections of squid jiggers. Catches vessels with AIS off. Free.

### Incident Sources (Manual Curation)
- The Outlaw Ocean Project (700+ documented Chinese DWF vessels)
- C4ADS IUU fishing reports
- Oceana reports on AIS avoidance
- NOAA IUU fishing biennial reports
- News reporting (Argentina, Philippines, Galapagos, South Korea incidents)
- RFMO IUU vessel lists (iuu-vessels.org)

### Key Data Limitations (to acknowledge on map)
- Only ~50% of Chinese DWF fleet broadcasts AIS (vs >90% for other nations)
- Chinese vessels account for 44% of global GPS manipulation
- ~927 Chinese-owned vessels fly other nations' flags (not captured by flag filter alone)
- 2025 data may be partial depending on GFW API lag

---

## Project Structure

```
DWF_fleet_tracking/
├── PLAN.md                          # This file
├── README.md                        # Methodology & usage documentation
├── requirements.txt                 # Python dependencies
├── config.py                        # API keys, file paths, constants
│
├── data/
│   ├── raw/                         # Downloaded source data (gitignored)
│   │   ├── gfw_fishing_effort/      # GFW gridded CSVs from Zenodo
│   │   ├── gfw_api/                 # Data from GFW API calls
│   │   ├── eez/                     # Marine Regions EEZ shapefiles
│   │   └── natural_earth/           # Basemap shapefiles
│   ├── processed/                   # Analysis-ready data (gitignored)
│   │   ├── china_dwf_effort.parquet # Filtered fishing effort
│   │   ├── ais_gaps.geojson         # AIS disabling events
│   │   └── eez_simplified.geojson   # Simplified EEZ for web
│   └── incidents/                   # Curated incident database (tracked in git)
│       └── incidents.csv            # Structured incident records
│
├── src/
│   ├── __init__.py
│   ├── data/
│   │   ├── __init__.py
│   │   ├── download_gfw_effort.py   # Download bulk fishing effort data
│   │   ├── download_boundaries.py   # Download EEZ + Natural Earth data
│   │   ├── fetch_gfw_api.py         # GFW API calls (gaps, vessels)
│   │   ├── process_effort.py        # Filter CHN flag, exclude China EEZ, aggregate
│   │   └── process_incidents.py     # Load & validate incident database
│   ├── maps/
│   │   ├── __init__.py
│   │   ├── static_map.py           # Publication-quality matplotlib/cartopy map
│   │   ├── interactive_map.py      # Self-contained HTML/Leaflet map
│   │   ├── inset_maps.py           # Regional inset/callout maps
│   │   └── styles.py               # Color palettes, fonts, styling constants
│   └── utils/
│       ├── __init__.py
│       └── geo.py                   # Spatial analysis helpers (EEZ intersection, etc.)
│
├── notebooks/                       # Jupyter notebooks for exploration
│   ├── 01_data_exploration.ipynb
│   ├── 02_dwf_filtering.ipynb
│   └── 03_map_prototyping.ipynb
│
├── output/
│   ├── static/                      # Publication maps
│   │   ├── dwf_global_map.png       # High-res PNG (300 DPI)
│   │   ├── dwf_global_map.pdf       # Vector PDF for print
│   │   └── dwf_global_map.svg       # Editable vector
│   └── interactive/                 # Self-contained HTML
│       ├── index.html               # Interactive map
│       └── data/                    # Embedded data files
│
└── .gitignore
```

---

## Implementation Phases

### Phase 1: Project Setup & Data Acquisition
**Goal**: Set up the repo, install dependencies, download all base data.

**Steps**:
1. Initialize project structure (directories, requirements.txt, .gitignore, config.py)
2. Install Python dependencies:
   - `cartopy` - map projections and basemap rendering
   - `matplotlib` - static map rendering
   - `geopandas` - spatial data processing
   - `pandas` - data manipulation
   - `folium` - interactive Leaflet map generation
   - `requests` - API calls
   - `pyarrow` - Parquet support
   - `shapely` - geometric operations
   - `numpy` - numerical operations
   - `Pillow` - image processing
3. Download GFW fishing effort v3.0 bulk data from Zenodo (2022-2024 monthly CSVs, flag=CHN)
4. Download Marine Regions EEZ v12 shapefile
5. Download Natural Earth data (1:50m coastlines, land, ocean, country boundaries)
6. Create config.py with placeholder for GFW API key

**Deliverable**: All raw data downloaded and verified.

### Phase 2: Data Processing & Filtering
**Goal**: Transform raw data into analysis-ready datasets focused on Chinese DWF.

**Steps**:
1. **Filter fishing effort**:
   - Select records where `flag = 'CHN'`
   - Spatial join with China's EEZ polygon to EXCLUDE domestic fishing
   - Everything outside China's EEZ = DWF activity
   - Aggregate to 0.1-degree grid by year for manageable file size
2. **Classify DWF sub-types** by gear type:
   - Squid jiggers (drifting_longlines, squid_jigger)
   - Trawlers (trawlers)
   - Longliners (set_longlines, drifting_longlines)
   - Purse seiners (purse_seines)
3. **Process EEZ boundaries**:
   - Simplify geometry for web (Douglas-Peucker)
   - Identify specific EEZs of interest: American Samoa, Argentina, Ecuador (Galapagos), Philippines, South Korea, West African nations, Pacific island states
4. **Compute EEZ proximity/violation indicators**:
   - For each grid cell with Chinese DWF activity, calculate distance to nearest non-Chinese EEZ
   - Flag grid cells that fall WITHIN foreign EEZs (potential violations)
5. **GFW API data** (once API key is available):
   - Fetch AIS-disabling gap events for Chinese-flagged vessels (2022-2025)
   - Fetch transshipment encounters involving Chinese vessels
   - Fetch 2025 fishing effort data (not in bulk download)

**Deliverable**: `china_dwf_effort.parquet`, `ais_gaps.geojson`, processed EEZ data.

### Phase 3: Incident Database Curation
**Goal**: Build a structured, sourced database of notable DWF incidents.

**Incident categories**:
- `eez_violation` - Documented illegal fishing inside foreign EEZ
- `ais_disable` - Systematic AIS shutoff patterns (from GFW gap data)
- `coast_guard_clash` - Physical confrontation with another nation's enforcement
- `ocean_mapping` - Suspicious survey/mapping behavior
- `transshipment` - At-sea transshipment (labor/catch laundering risk)
- `us_interest` - Activity impinging on American interests (even if legal)

**CSV schema**:
```
id, date, lat, lon, category, subcategory, title, description,
country_affected, source_name, source_url, severity (1-3),
vessels_involved, notes
```

**Research targets** (I compile, you verify):
- Argentina/Patagonian shelf incidents (2022-2025)
- Galapagos EEZ edge massing (2022-2025)
- American Samoa area activity
- Philippines/South China Sea clashes
- South Korea EEZ seizures
- West African IUU incidents
- Indian Ocean surge documentation
- Pacific island EEZ violations

**Deliverable**: `data/incidents/incidents.csv` with 30-60 documented incidents.

### Phase 4: Static Map Design & Build
**Goal**: Create a publication-quality global map meeting government briefing standards.

**Base map design**:
- **Projection**: Robinson, centered on 160°W (Pacific-centered, puts Americas on right, Asia on left)
- **Ocean**: Dark navy (#0a1628) with subtle bathymetric shading
- **Land**: Dark charcoal (#1a1a2e) with thin (#333355) country borders
- **EEZ boundaries**: Very thin, low-opacity cyan lines (#4488aa at 20% opacity)
- **Graticule**: Subtle grid lines at 30° intervals (#1a2a3a)
- **Labels**: White/light gray, clean sans-serif font (Source Sans Pro or similar)

**Data layers** (bottom to top):
1. **Fishing effort heatmap** - 0.1° gridded fishing hours
   - Color ramp per year:
     - 2022: pale yellow (#ffffb2)
     - 2023: light orange (#fecc5c)
     - 2024: orange-red (#fd8d3c)
     - 2025: deep crimson (#bd0026)
   - Opacity scaled by fishing hours intensity
   - This is the primary visual layer
2. **AIS gap event clusters** - Where vessels systematically go dark
   - White/ice blue marker outlines with transparency
   - Concentrated near EEZ boundaries
3. **Incident markers** - Specific documented events
   - Icon by category (different shapes)
   - Red for clashes, orange for violations, blue for mapping, star for US interest
   - Small but visible with leader lines to labels
4. **EEZ violation highlights** - Where DWF effort falls inside foreign EEZs
   - Subtle red glow/halo on relevant EEZ portions

**Annotations & labels**:
- Title: "China's Distant Water Fishing Fleet: Global Activity 2022-2025"
- Subtitle: Context line about fleet scale
- Year legend with color ramp
- Category legend for incident types
- Data source attribution (GFW, Marine Regions, curated incidents)
- Caveat note about AIS undercount (~50%)
- Scale bar and graticule labels

**Regional inset maps** (Americas & US Pacific focus):
1. **Galapagos / Ecuador EEZ** - Show fleet massing at EEZ boundary
2. **Argentine Patagonian Shelf** - Show activity along continental shelf edge and EEZ proximity
3. **American Samoa / Central Pacific** - Show DWF presence near US territories
4. **Optional: Philippines/South China Sea** - If space permits, show coast guard clash zone

**Inset design**: Same dark background, slightly zoomed, with EEZ clearly labeled. Connected to main map with subtle callout lines.

**Output formats**:
- PNG at 300 DPI (for slides/screen): ~8000x4500 px
- PDF (vector, for print)
- SVG (editable)

**Deliverable**: Publication-ready map files in `output/static/`.

### Phase 5: Interactive Map Build
**Goal**: Create a self-contained HTML file that opens in any browser.

**Technology**: Folium (Python-generated Leaflet.js) or hand-crafted HTML with Leaflet + Mapbox GL JS. The choice depends on what achieves the best dark-background styling. Folium is faster to build; hand-crafted HTML gives more control.

**Features**:
- **Dark basemap tile layer** (CartoDB Dark Matter or Mapbox dark style)
- **Year toggle** - Checkbox or slider to show/hide each year (2022-2025)
- **Layer toggle** - Show/hide: Fishing effort, AIS gaps, Incidents, EEZ boundaries
- **Click-to-inspect** on incidents: popup with date, description, source link
- **Hover** on fishing effort grid cells: fishing hours, year, gear type
- **Zoom** into any region
- **Legend** with year colors and incident categories
- **Title overlay** with methodology note

**Data embedding**: All data embedded as GeoJSON/JSON within the HTML file (or as companion files in the same directory). No external API calls needed to view.

**Deliverable**: `output/interactive/index.html` (+ companion data files).

### Phase 6: Polish & Review
**Goal**: Ensure government briefing quality.

**Steps**:
1. Cartographic review:
   - Label placement and readability
   - Color contrast and accessibility (check with colorblind simulation)
   - Visual hierarchy (most important info most prominent)
   - No overlapping labels or markers
2. Source attribution:
   - Every data source cited
   - Methodology note
   - Date of data retrieval
   - Caveats clearly stated
3. Accuracy review:
   - Cross-check incident locations against sources
   - Verify EEZ boundary accuracy for highlighted regions
   - Confirm year-over-year trends match known reporting
4. Final exports at full resolution
5. README.md with methodology, data sources, reproduction instructions

**Deliverable**: Final polished outputs, README.

---

## Workflow & Dependencies

```
Phase 1 (Setup & Download)
    ↓
Phase 2 (Data Processing)  ←──  Blocked on GFW API key for gap events + 2025 data
    ↓                            (bulk 2022-2024 effort can proceed without API key)
Phase 3 (Incidents)         ←──  Can run in parallel with Phase 2
    ↓
Phase 4 (Static Map)        ←──  Requires Phase 2 + 3 complete
    ↓
Phase 5 (Interactive Map)   ←──  Can reuse Phase 4 data; partially parallel
    ↓
Phase 6 (Polish)
```

**Critical path blocker**: The GFW API key. We can build the full pipeline with bulk 2022-2024 data and add API-dependent features (AIS gaps, 2025 data) once the key is available. The static map can be prototyped without it.

---

## Color Palette

### Year Colors (Sequential Ramp)
| Year | Hex | Description |
|------|-----|-------------|
| 2022 | #ffffb2 | Pale yellow |
| 2023 | #fecc5c | Light orange |
| 2024 | #fd8d3c | Orange-red |
| 2025 | #bd0026 | Deep crimson |

### Incident Categories
| Category | Color | Shape |
|----------|-------|-------|
| EEZ violation | #ff4444 | Triangle |
| Coast guard clash | #ff0000 | Diamond |
| AIS disable pattern | #88ccff | Circle outline |
| Ocean mapping | #44aaff | Square |
| US interest zone | #ffd700 (gold) | Star |
| Transshipment | #aa66cc | Hexagon |

### Base Map
| Element | Hex |
|---------|-----|
| Ocean | #0a1628 |
| Land | #1a1a2e |
| Country borders | #333355 |
| EEZ lines | #4488aa (20% opacity) |
| Graticule | #1a2a3a |
| Text (primary) | #e0e0e0 |
| Text (secondary) | #888899 |

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| GFW bulk data is very large (multi-GB) | Slow download, memory issues | Filter by flag=CHN during download; use chunked processing |
| GFW API key takes time to approve | Blocks gap events + 2025 data | Build pipeline with bulk data first; add API data as enhancement |
| Incident data is subjective | Credibility risk for briefing | Require minimum 2 independent sources per incident; clearly attribute |
| 50% AIS undercount | Map understates fleet size | Prominent caveat on map; consider VIIRS squid jigger data as supplement |
| Too much data on one map | Visual clutter | Aggressive filtering; opacity control; insets for detail; interactive version for exploration |
| Robinson projection distorts high latitudes | Visual misleading | Acceptable for this use case (most DWF is equatorial/mid-latitude); note projection in legend |

---

## Next Steps (Immediate)

1. **User action**: Register for GFW API key at https://globalfishingwatch.org/our-apis/
2. **Claude action**: Begin Phase 1 (project setup, dependency installation, data download scripts)
3. **Parallel**: Begin Phase 3 incident research (I compile a draft, you review)

---

## Questions Resolved
- Output: Both static + interactive ✓
- Years: 2022-2025 ✓
- Style: Dark background ✓
- Projection: Pacific-centered Robinson ✓
- Year encoding: Sequential color ramp ✓
- Insets: Americas & US Pacific ✓
- Quality: Government briefing ✓
- Interactive delivery: Static HTML files ✓
- Tech: Python (cartopy/matplotlib + Folium) ✓
- Incidents: Collaborative curation ✓
- API: User will register ✓
