import urllib.request
import json
import duckdb

STATION = "KAUS"  # Austin-Bergstrom International Airport
URL = f"https://api.weather.gov/stations/{STATION}/observations/latest"
DB_PATH = "weather.duckdb"

req = urllib.request.Request(URL, headers={
    "User-Agent": "(weather-blog, demo@example.com)",
    "Accept": "application/geo+json",
})

with urllib.request.urlopen(req) as resp:
    data = json.loads(resp.read())

props = data["properties"]
temp_c = props["temperature"]["value"]
temp_f = temp_c * 9 / 5 + 32 if temp_c is not None else None
timestamp = props["timestamp"]
lon, lat = data["geometry"]["coordinates"]

print(f"Station:     {STATION}")
print(f"Observed at: {timestamp}")
print(f"Temperature: {temp_f:.1f}°F ({temp_c:.1f}°C)" if temp_f else "Temperature: N/A")

con = duckdb.connect(DB_PATH)
con.execute("""
    CREATE TABLE IF NOT EXISTS readings (
        station_id  VARCHAR,
        lat         DOUBLE,
        lon         DOUBLE,
        temp_f      DOUBLE,
        observed_at TIMESTAMPTZ
    )
""")
con.execute(
    "INSERT INTO readings VALUES (?, ?, ?, ?, ?)",
    [STATION, lat, lon, temp_f, timestamp],
)
print(f"Written to {DB_PATH} ({con.execute('SELECT count(*) FROM readings').fetchone()[0]} rows total)")
con.close()
