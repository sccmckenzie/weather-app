import urllib.request
import json
import duckdb

DB_PATH = "weather.duckdb"
HEADERS = {
    "User-Agent": "(weather-blog, demo@example.com)",
    "Accept": "application/geo+json",
}


def fetch_json(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def fetch_icao_stations(state):
    stations = []
    url = f"https://api.weather.gov/stations?state={state}&limit=500"
    while url:
        data = fetch_json(url)
        for feature in data["features"]:
            sid = feature["properties"]["stationIdentifier"]
            if len(sid) == 4 and sid.startswith("K"):
                lon, lat = feature["geometry"]["coordinates"]
                stations.append({
                    "station_id": sid,
                    "name": feature["properties"]["name"],
                    "lat": lat,
                    "lon": lon,
                })
        url = data.get("pagination", {}).get("next")
    return stations


stations = fetch_icao_stations("TX")
print(f"Found {len(stations)} ICAO stations in Texas")

rows = [[s["station_id"], s["name"], s["lat"], s["lon"]] for s in stations]

con = duckdb.connect(DB_PATH)
con.execute("""
    CREATE TABLE IF NOT EXISTS stations (
        station_id VARCHAR PRIMARY KEY,
        name       VARCHAR,
        lat        DOUBLE,
        lon        DOUBLE
    )
""")
con.execute("BEGIN")
con.execute("DELETE FROM stations")
con.executemany("INSERT INTO stations VALUES (?, ?, ?, ?)", rows)
con.execute("COMMIT")
print(con.execute("SELECT * FROM stations LIMIT 5").df().to_string(index=False))
con.close()
