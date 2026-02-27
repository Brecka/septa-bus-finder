from flask import Flask, request
import requests

app = Flask(__name__)

RADIUS_MILES = 0.4
NUM_STOPS_TO_CHECK = 8
NUM_PER_ROUTE = 20
NUM_RESULTS_TO_SHOW = 10

def get_nearby_bus_stops(lat: float, lon: float):
    url = "https://www3.septa.org/hackathon/locations/get_locations.php"
    params = {"lat": lat, "lon": lon, "type": "bus_stops", "radius": RADIUS_MILES}
    return requests.get(url, params=params, timeout=20).json()

def get_bus_schedules(stop_id: str):
    url = "https://www3.septa.org/api/BusSchedules/index.php"
    return requests.get(url, params={"stop_id": stop_id}, timeout=20).json()

@app.get("/")
def home():
    # You supply your phone's location each time:
    # /?lat=39.95&lon=-75.16&dest=Whitman
    lat = request.args.get("lat", type=float)
    lon = request.args.get("lon", type=float)
    dest = (request.args.get("dest") or "").strip()

    if lat is None or lon is None:
        return (
            "Provide lat/lon in the URL, e.g. "
            "/?lat=39.95151&lon=-75.15396&dest=Whitman"
        ), 400

    stops = get_nearby_bus_stops(lat, lon)
    if not stops:
        return "No nearby bus stops found (try increasing radius).", 404

    # Check multiple nearby stops
    matches = []
    for stop in stops[:NUM_STOPS_TO_CHECK]:
        stop_id = stop.get("location_id")
        stop_name = stop.get("location_name")
        dist = stop.get("distance")

        if not stop_id:
            continue

        sched = get_bus_schedules(stop_id)
        if not isinstance(sched, dict) or not sched:
            continue

        for route, items in sched.items():
            if route == "0" or not isinstance(items, list):
                continue

            for item in items[:NUM_PER_ROUTE]:
                date = item.get("DateCalender")
                direction = item.get("DirectionDesc")

                if not date or not direction:
                    continue

                if dest and dest.lower() not in direction.lower():
                    continue

                matches.append((date, route, direction, stop_name, stop_id, dist))

    # Simple sort by the date string is "good enough" for display; we can improve later
    matches.sort(key=lambda x: x[0])

    # HTML response
    html = []
    html.append("<h2>SEPTA Bus Finder</h2>")
    html.append(f"<p><b>Location:</b> {lat}, {lon}</p>")
    html.append(f"<p><b>Filter:</b> {dest or '(none)'}</p>")
    html.append("<p>Example: <code>/?lat=39.95151&lon=-75.15396&dest=Whitman</code></p>")

    if not matches:
        html.append("<p><b>No matches found.</b> Try a different dest keyword or remove dest.</p>")
        return "\n".join(html)

    html.append("<h3>Soonest results</h3>")
    html.append("<ul>")
    for date, route, direction, stop_name, stop_id, dist in matches[:NUM_RESULTS_TO_SHOW]:
        html.append(
            f"<li><b>{date}</b> | Route <b>{route}</b> | {direction} "
            f"| Stop: {stop_name} (id={stop_id}, dist={dist})</li>"
        )
    html.append("</ul>")

    return "\n".join(html)

@app.get("/health")
def health():
    return {"ok": True}

if __name__ == "__main__":
    # Render sets PORT
    import os
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)