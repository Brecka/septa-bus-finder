from flask import Flask, request
import requests

app = Flask(__name__)

RADIUS_MILES = 0.4
NUM_STOPS_TO_CHECK = 8
NUM_PER_ROUTE = 10
NUM_RESULTS_TO_SHOW = 10


def get_nearby_bus_stops(lat: float, lon: float):
    url = "https://www3.septa.org/hackathon/locations/get_locations.php"
    params = {"lat": lat, "lon": lon, "type": "bus_stops", "radius": RADIUS_MILES}
    return requests.get(url, params=params, timeout=20).json()


def get_bus_schedules(stop_id: str):
    url = "https://www3.septa.org/api/BusSchedules/index.php"
    return requests.get(url, params={"stop_id": stop_id}, timeout=20).json()


def collect_matches_for_stop(stop_id: str, dest_keyword: str):
    sched = get_bus_schedules(stop_id)

    # sched is usually a dict of {route: [items...]}
    if not isinstance(sched, dict) or not sched:
        return []

    results = []
    routes = [r for r in sched.keys() if r != "0"]

    for route in routes:
        items = sched.get(route) or []
        for item in items[:NUM_PER_ROUTE]:
            dt = item.get("DateCalender") or item.get("date")
            direction = item.get("DirectionDesc") or ""
            stop_name = item.get("StopName") or ""

            if not dt:
                continue

            if dest_keyword:
                if dest_keyword.lower() not in direction.lower() and dest_keyword.lower() not in stop_name.lower():
                    continue

            results.append(
                {
                    "time": dt,
                    "route": route,
                    "direction": direction,
                    "stop_name": stop_name,
                    "stop_id": stop_id,
                }
            )

    return results


@app.get("/")
def home():
    return """
<!doctype html>
<html>
  <head>
    <meta name="viewport" content="width=device-width,initial-scale=1" />
    <title>SEPTA Bus Finder</title>
  </head>
  <body style="font-family: system-ui; padding: 16px; max-width: 720px;">
    <h2>SEPTA Bus Finder</h2>

    <p><b>Option A:</b> Use your location (if allowed)</p>
    <input id="destA" placeholder="Destination keyword (optional)" style="padding:10px; width:100%; max-width:520px;" />
    <br/><br/>
    <button id="goLoc" style="padding:10px 14px;">Use my location</button>

    <hr style="margin: 18px 0;" />

    <p><b>Option B:</b> Enter a Stop ID (works even if location is blocked)</p>
    <input id="stopId" placeholder="Stop ID (numbers)" inputmode="numeric"
           style="padding:10px; width:100%; max-width:520px;" />
    <br/><br/>
    <input id="destB" placeholder="Destination keyword (optional)" style="padding:10px; width:100%; max-width:520px;" />
    <br/><br/>
    <button id="goStop" style="padding:10px 14px;">Find buses for Stop ID</button>

    <p id="msg" style="margin-top:14px;"></p>

    <h3>Favorites</h3>
    <div id="favs"></div>

    <script>
      const msg = document.getElementById('msg');

      function loadFavs() {
        const favs = JSON.parse(localStorage.getItem("septa_favs") || "[]");
        const box = document.getElementById("favs");
        if (!favs.length) {
          box.innerHTML = "<p style='color:#555'>No favorites yet.</p>";
          return;
        }
        box.innerHTML = favs.map((f, i) => {
          const qs = new URLSearchParams({ stop_id: f.stop_id, dest: f.dest || "" }).toString();
          return `
            <div style="display:flex; gap:10px; align-items:center; margin:8px 0;">
              <a href="/results?${qs}">${f.label} (stop ${f.stop_id})</a>
              <button onclick="removeFav(${i})">Remove</button>
            </div>
          `;
        }).join("");
      }

      function saveFav(label, stop_id, dest) {
        const favs = JSON.parse(localStorage.getItem("septa_favs") || "[]");
        favs.unshift({ label, stop_id, dest });
        localStorage.setItem("septa_favs", JSON.stringify(favs.slice(0, 12)));
        loadFavs();
      }

      function removeFav(i) {
        const favs = JSON.parse(localStorage.getItem("septa_favs") || "[]");
        favs.splice(i, 1);
        localStorage.setItem("septa_favs", JSON.stringify(favs));
        loadFavs();
      }

      window.removeFav = removeFav;

      document.getElementById('goLoc').onclick = () => {
        const dest = document.getElementById('destA').value || '';
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
            msg.textContent = "Location blocked. Use Stop ID instead.";
          },
          { enableHighAccuracy: true, timeout: 10000 }
        );
      };

      document.getElementById('goStop').onclick = () => {
        const stop_id = (document.getElementById('stopId').value || '').trim();
        const dest = document.getElementById('destB').value || '';
        if (!stop_id) {
          msg.textContent = "Enter a Stop ID.";
          return;
        }
        const url = `/results?stop_id=${encodeURIComponent(stop_id)}&dest=${encodeURIComponent(dest)}`;
        window.location.href = url;
      };

      // quick add favorite from inputs (optional convenience)
      document.getElementById('stopId').addEventListener('change', () => {
        const stop_id = (document.getElementById('stopId').value || '').trim();
        if (stop_id) saveFav("Favorite", stop_id, "");
      });

      loadFavs();
    </script>
  </body>
</html>
"""


@app.get("/results")
def results():
    dest = (request.args.get("dest") or "").strip()
    stop_id = (request.args.get("stop_id") or "").strip()

    # If stop_id is provided, use it directly (no location needed)
    if stop_id:
        matches = collect_matches_for_stop(stop_id, dest)[:NUM_RESULTS_TO_SHOW]
        if not matches:
            return f"No matches for stop_id={stop_id}. Try empty dest or a shorter keyword."
        html_items = "".join(
            f"<li>{m['time']} | Route {m['route']} | {m['direction']} | {m['stop_name']} | stop_id={m['stop_id']}</li>"
            for m in matches
        )
        return f"""
        <h2>SEPTA Bus Finder</h2>
        <p><b>Stop ID:</b> {stop_id}</p>
        <p><b>Filter:</b> {dest or '(none)'}</p>
        <ul>{html_items}</ul>
        <p><a href="/">Back</a></p>
        """

    # Otherwise, use lat/lon
    lat = request.args.get("lat", type=float)
    lon = request.args.get("lon", type=float)
    if lat is None or lon is None:
        return 'Provide lat/lon OR stop_id. Example: /results?stop_id=728&dest=Whitman'

    stops = get_nearby_bus_stops(lat, lon)
    if not stops:
        return "No bus stops found near you. Increase radius or use Stop ID."

    stops = stops[:NUM_STOPS_TO_CHECK]
    all_matches = []

    for s in stops:
        sid = str(s.get("location_id"))
        sname = s.get("location_name") or ""
        dist = s.get("distance")
        matches = collect_matches_for_stop(sid, dest)
        for m in matches:
            m["nearest_stop_name"] = sname
            m["distance"] = dist
        all_matches.extend(matches)

    # crude sort by time string (works “ok” for this API format)
    all_matches = all_matches[:NUM_RESULTS_TO_SHOW]

    if not all_matches:
        return f"""
        <h2>SEPTA Bus Finder</h2>
        <p>Location: {lat}, {lon}</p>
        <p>Filter: {dest or '(none)'}</p>
        <p>No matches found. Try a shorter keyword or use Stop ID.</p>
        <p><a href="/">Back</a></p>
        """

    html_items = "".join(
        f"<li>{m['time']} | Route {m['route']} | {m['direction']} | stop_id={m['stop_id']}</li>"
        for m in all_matches
    )

    return f"""
    <h2>SEPTA Bus Finder</h2>
    <p><b>Location:</b> {lat}, {lon}</p>
    <p><b>Filter:</b> {dest or '(none)'}</p>
    <ul>{html_items}</ul>
    <p><a href="/">Back</a></p>
    """


@app.get("/health")
def health():
    return {"ok": True}
