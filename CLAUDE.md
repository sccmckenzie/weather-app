# CLAUDE.md

## Purpose

This project supports a technical blog post about incremental data loading patterns. The example domain is a US temperature heatmap built from National Weather Service station observations. The core lesson: don't commit a partial spatial dataset to your target artifact — wait for completeness before publishing.

## Domain Context

The blog post uses weather station data as a stand-in for any spatial quality measurement system. The pattern applies broadly: stations report at different times, and a consumer viewing a half-populated map can't distinguish "no data yet" from "no station here."

## Data Source

- **API**: https://api.weather.gov (National Weather Service)
- **Auth**: No API key required. All requests must include a `User-Agent` header (e.g., `User-Agent: (weather-blog, your@email.com)`)
- **Rate limits**: No published limits, but respect `Cache-Control` headers. Don't cache-bust with random query strings.
- **Key endpoints**:
  - `GET /stations?state={XX}` — list observation stations by state (paginated, 500/page)
  - `GET /stations/{stationId}/observations/latest` — latest observation for a station
  - `GET /stations/{stationId}/observations?start={ISO}&end={ISO}` — historical observations

## Station Filtering

The `/stations` endpoint returns thousands of stations per state (COOP, mesonet, RAWS, etc.). Most don't report hourly temperatures. Filter to **ICAO-coded stations** — 4-character IDs starting with `K` (e.g., `KDFW`, `KIAH`, `KAUS`). These are ASOS/AWOS airport stations with reliable ~5-60 minute reporting intervals. Expect ~200 per large state, ~2,000-2,500 nationwide.

## Data Model

Target schema for the blog post:

- `snapshots` — id, target_hour, station_count_expected, station_count_received, status
- `readings` — id, snapshot_id, station_id, lat, lon, temp_f, observed_at

The completeness check: don't flip `snapshots.status` to `complete` until `station_count_received` meets threshold.

## Key Design Decisions

- Temperature values come from API in Celsius (`properties.temperature.value`) — convert to Fahrenheit for US audience
- Coordinates are in `geometry.coordinates` as [lon, lat] (GeoJSON order, not lat/lon)
- Historical data is available via start/end params, so demos don't require live polling
- Observations include a `timestamp` field showing when the station actually reported — the natural variance in these timestamps is what makes the incremental loading pattern real

## Blog Post Tone

- Practical, code-forward, minimal fluff
- The audience is data engineers / analytics engineers
- Show real API calls, real data, real schema
- The "aha moment" is: staging + completeness gating prevents consumers from seeing fragmented snapshots
