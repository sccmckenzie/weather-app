import urllib.request
import json
import duckdb
import itertools
from concurrent.futures import ThreadPoolExecutor, as_completed

DB_PATH = "weather.duckdb"
HEADERS = {
    "User-Agent": "(weather-blog, demo@example.com)",
    "Accept": "application/geo+json",
}

# Travis County bounding box
LAT_MIN, LAT_MAX = 30.02, 30.63
LON_MIN, LON_MAX = -98.17, -97.37
GRID_N = 32  # 32x32 = 1024 points


def fetch_json(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def resolve_point(lat, lon):
    """Return (lat, lon, gridId, gridX, gridY) or None on failure."""
    try:
        d = fetch_json(f"https://api.weather.gov/points/{lat:.4f},{lon:.4f}")
        p = d["properties"]
        return (lat, lon, p["gridId"], p["gridX"], p["gridY"])
    except Exception:
        return None


def fetch_temp(gridId, gridX, gridY):
    """Return temp_f and valid_time for the current hour."""
    d = fetch_json(f"https://api.weather.gov/gridpoints/{gridId}/{gridX},{gridY}/forecast/hourly")
    period = d["properties"]["periods"][0]
    return period["temperature"], period["startTime"]  # already °F


# --- 1. Generate grid coordinates ---
lats = [LAT_MIN + (LAT_MAX - LAT_MIN) * i / (GRID_N - 1) for i in range(GRID_N)]
lons = [LON_MIN + (LON_MAX - LON_MIN) * i / (GRID_N - 1) for i in range(GRID_N)]
coords = list(itertools.product(lats, lons))
print(f"Generated {len(coords)} grid coordinates")

# --- 2. Resolve each coordinate to a NWS grid cell (threaded) ---
resolved = []
with ThreadPoolExecutor(max_workers=20) as ex:
    futures = {ex.submit(resolve_point, lat, lon): (lat, lon) for lat, lon in coords}
    for i, f in enumerate(as_completed(futures), 1):
        result = f.result()
        if result:
            resolved.append(result)
        if i % 100 == 0:
            print(f"  resolved {i}/{len(coords)}")

print(f"Resolved {len(resolved)} points")

# --- 3. Deduplicate by grid cell ---
seen = {}
for lat, lon, gridId, gridX, gridY in resolved:
    key = (gridId, gridX, gridY)
    if key not in seen:
        seen[key] = (lat, lon)

print(f"Unique grid cells: {len(seen)}")

# --- 4. Fetch hourly forecast for each unique cell (threaded) ---
rows = []
def fetch_row(key, lat, lon):
    gridId, gridX, gridY = key
    try:
        temp_f, valid_time = fetch_temp(gridId, gridX, gridY)
        return (lat, lon, gridId, gridX, gridY, temp_f, valid_time)
    except Exception:
        return None

with ThreadPoolExecutor(max_workers=10) as ex:
    futures = {ex.submit(fetch_row, key, lat, lon): key for key, (lat, lon) in seen.items()}
    for i, f in enumerate(as_completed(futures), 1):
        result = f.result()
        if result:
            rows.append(result)
        if i % 50 == 0:
            print(f"  fetched {i}/{len(seen)}")

print(f"Fetched {len(rows)} temperature readings")

# --- 5. Write to DuckDB ---
con = duckdb.connect(DB_PATH)
con.execute("""
    CREATE TABLE IF NOT EXISTS grid_readings (
        lat        DOUBLE,
        lon        DOUBLE,
        grid_id    VARCHAR,
        grid_x     INTEGER,
        grid_y     INTEGER,
        temp_f     DOUBLE,
        valid_time TIMESTAMPTZ
    )
""")
con.execute("BEGIN")
con.execute("DELETE FROM grid_readings")
con.executemany("INSERT INTO grid_readings VALUES (?, ?, ?, ?, ?, ?, ?)", rows)
con.execute("COMMIT")

print(con.execute("SELECT * FROM grid_readings LIMIT 5").df().to_string(index=False))
con.close()
