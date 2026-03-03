from flask import Flask, request
import requests
from datetime import datetime

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
    return """
<!doctype html>
<html>
  <head>
    <meta name="viewport" content="width=device-width,initial-scale=1" />
    <title>SEPTA Bus Finder</title>
  </head>
  <body style="font-family: system-ui; padding: 16px;">
    <h2>SEPTA Bus Finder</h2>
    <p>Enter a destination keyword (example: Whitman, Plaza, Andorra)</p>

    <input id="dest" placeholder="Destination keyword" style="padding:10px; width:100%; max-width:420px;" />
    <br/><br/>
    <button id="go" style="padding:10px 14px;">Use my location</button>

    <p id="msg" style="margin-top:14px;"></p>

    <script>
      const msg = document.getElementById('msg');
      document.getElementById('go').onclick = () => {
        const dest = document.getElementById('dest').value || '';
        if (!navigator.geolocation) {
          msg.textContent = "Geolocation not supported.";
          return;
        }
        msg.textContent = "Getting your location…";
        navigator.geolocation.getCurrentPosition(
          (pos) => {
            const lat = pos.coords.latitude;
            const lon = pos.coords.longitude;
            const url = `/results?lat=${encodeURIComponent(lat)}&lon=${encodeURIComponent(lon)}&dest=${encodeURIComponent(dest)}`;
            window.location.href = url;
          },
          () => {
            msg.textContent = "Location blocked. Allow location and try again.";
          },
          { enableHighAccuracy: true, timeout: 10000 }
        );
      };
    </script>
  </body>
</html>
"""


@app.get("/results")
def results():
    lat = request.args.get("lat", type=float)
    lon = request.args.get("lon", type=float)
    dest = (request.args.get("dest") or "").strip()

    if lat is None or lon is None:
        return "Missing lat/lon", 400

    stops = get_nearby_bus_stops(lat, lon)
    if not stops:
        return "No nearby bus stops found (try increasing radius).", 404

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
                date_str = item.get("DateCalender")
                direction = item.get("DirectionDesc")
                if not date_str or not direction:
                    continue

                if dest and dest.lower() not in direction.lower():
                    continue

                # Parse for sorting (example: "02/27/26 01:55 pm")
                try:
                    t = datetime.strptime(date_str, "%m/%d/%y %I:%M %p")
                except ValueError:
                    t = None

                matches.append({
                    "time": t,
                    "time_str": date_str,
                    "route": route,
                    "direction": direction,
                    "stop_name": stop_name,
                    "stop_id": stop_id,
                    "distance": dist
                })

    # Sort: parsed datetime first; fallback to string
    matches.sort(key=lambda x: (x["time"] is None, x["time"] or datetime.max, x["time_str"]))

    html = []
    html.append("<!doctype html><html><head><meta name='viewport' content='width=device-width,initial-scale=1' />")
    html.append("<title>Results</title></head><body style='font-family: system-ui; padding: 16px;'>")
    html.append("<a href='/'>← Back</a>")
    html.append(f"<h2>Matches{(' for ' + dest) if dest else ''}</h2>")

    if not matches:
        html.append("<p><b>No matches found.</b> Try a shorter keyword or leave destination blank.</p>")
        html.append("</body></html>")
        return "\n".join(html)

    html.append("<ul>")
    for m in matches[:NUM_RESULTS_TO_SHOW]:
        html.append(
            f"<li><b>{m['time_str']}</b> | Route <b>{m['route']}</b> | {m['direction']} "
            f"| Stop: {m['stop_name']} (dist={m['distance']})</li>"
        )
    html.append("</ul></body></html>")
    return "\n".join(html)


@app.get("/health")
def health():
    return {"ok": True}


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
