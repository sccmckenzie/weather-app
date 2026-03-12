# weather-app

A technical blog post project exploring incremental data loading patterns using public APIs.

## Blog Post Concept

The core lesson: **don't expose partial spatial datasets to consumers** — gate publishing behind a completeness check. A half-populated map can't distinguish "no data yet" from "no data here."

The pattern is domain-agnostic. This repo has explored two candidate domains:

---

## Domain Exploration

### 1. NWS Weather (current implementation)

**API**: `https://api.weather.gov` — no auth required, `User-Agent` header required.

**Original approach**: Fetch latest observations from ICAO-coded stations (4-char IDs starting with `K`, e.g. `KAUS`). Stations are reliable ASOS/AWOS airport sensors. Filtered from `/stations?state=TX`.

**Current approach** (`fetch_grid.py`): Abandoned station-based fetching in favor of a coordinate grid. Generate an N×N grid of lat/lon points across a bounding box, resolve each to an NWS grid cell via `/points/{lat},{lon}`, deduplicate on `(gridId, gridX, gridY)`, then fetch hourly forecast temperature from `/gridpoints/{wfo}/{x},{y}/forecast/hourly`.

**Problem with this domain**: The grid approach produces a fixed, uniform set of points every run — no natural variability in observation count. This undermines the blog post's "incomplete snapshot" narrative.

### 2. EPA AQS Air Quality (considered, not implemented)

**API**: `https://aqs.epa.gov/data/api` — free API key required (email signup).

**Pros**: Monitors report at genuinely variable intervals (hourly, 5-min, 12-hour). A county-level query at a specific hour naturally returns partial results. Rich metadata including actual report timestamps.

**Cons**: Data is 6+ months stale — purely historical. API key signup adds friction.

### 3. USGS Seismic (considered, quick prototype in DuckDB)

**API**: `https://earthquake.usgs.gov/fdsnws/event/1/` — no auth required.

**Pros**: Strong narrative — stations report phase picks asynchronously after an event, ShakeMap literally ships incomplete and updates as more stations report in. Real-time and historical. No auth.

**Cons**: Observation count variability is per-event (earthquake), not per time window. Reproducibility depends on event history.

**Status**: Fetched 100 recent M5+ earthquakes into `earthquakes` table in `weather.duckdb`. The `nst` field (station count) varies naturally per event.

---

## Repo Structure

```
fetch_grid.py     # NWS grid-based temperature fetch for Travis County
weather.duckdb    # DuckDB database (grid_readings + earthquakes tables)
pyproject.toml    # uv project file
uv.lock
```

## Environment

- Python 3.14.3 via uv (`uv run python fetch_grid.py`)
- DuckDB 1.5.0
- Platform: Raspberry Pi

## DuckDB Schema

```sql
-- NWS grid temperature readings
CREATE TABLE grid_readings (
    lat        DOUBLE,
    lon        DOUBLE,
    grid_id    VARCHAR,
    grid_x     INTEGER,
    grid_y     INTEGER,
    temp_f     DOUBLE,
    valid_time TIMESTAMPTZ,
    insert_at  TIMESTAMPTZ DEFAULT now()
);

-- USGS earthquake events (prototype)
CREATE TABLE earthquakes (
    id         VARCHAR PRIMARY KEY,
    place      VARCHAR,
    mag        DOUBLE,
    mag_type   VARCHAR,
    event_time TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    nst        INTEGER,   -- station count, naturally variable
    lat        DOUBLE,
    lon        DOUBLE,
    depth_km   DOUBLE,
    status     VARCHAR
);
```

## fetch_grid.py Usage

```bash
uv run python fetch_grid.py                        # 10x10 grid, Travis County defaults
uv run python fetch_grid.py --grid-n 32           # 32x32 = 1024 points
uv run python fetch_grid.py --lat-min 30.1 --lat-max 30.5 --lon-min -97.9 --lon-max -97.5 --grid-n 10
```

## Next Steps (open questions)

- Commit to a domain: NWS grid, EPA AQS, or USGS seismic
- If seismic: explore per-event phase-data detail to show stations trickling in over time
- Implement `snapshots` table with completeness gating (`status: pending → complete`)
- Build the staging + publish pattern that is the actual blog post subject
