// ----------------------------------------------------------
// CONFIG
// ----------------------------------------------------------
const API = "https://backend-floral-tree-4711.fly.dev"; 

// GLOBAL MAP + LAYERS
let map;
let routeLayer = null;
let trailLayer = null;
let pathLayer = null;
let ferryLayer = null;
let elevationChart = null;

let setStartNext = true;
let deferredPrompt = null;

// ----------------------------------------------------------
// MAP INIT
// ----------------------------------------------------------
document.addEventListener("DOMContentLoaded", () => {

  // DARK MODE
  if (localStorage.getItem("theme") === "dark") {
    document.documentElement.classList.add("dark");
  }

  // SERVICE WORKER
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("service-worker.js")
      .then(() => console.log("SW registered"))
      .catch(err => console.log("SW registration failed", err));
  }

  // MAP
  map = L.map("map").setView([40.7128, -74.0060], 14);

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenStreetMap",
  }).addTo(map);

  // CLICK TO SET START/END
  map.on("click", function (e) {
    const lat = e.latlng.lat.toFixed(6);
    const lon = e.latlng.lng.toFixed(6);

    if (setStartNext) {
      document.getElementById("startInput").value = `${lat},${lon}`;
      document.getElementById("startInput_coords").value = `${lat},${lon}`;
      alert("Start point set. Tap again to set END point.");
      setStartNext = false;
    } else {
      document.getElementById("endInput").value = `${lat},${lon}`;
      document.getElementById("endInput_coords").value = `${lat},${lon}`;
      alert("End point set.");
      setStartNext = true;
    }
  });

  setupAutocomplete("startInput", "startSuggestions");
  setupAutocomplete("endInput", "endSuggestions");
});

// ----------------------------------------------------------
// USE MY LOCATION
// ----------------------------------------------------------
function useMyLocation() {
  navigator.geolocation.getCurrentPosition(pos => {
    const { latitude, longitude } = pos.coords;

    document.getElementById("startInput").value = `${latitude},${longitude}`;
    document.getElementById("startInput_coords").value = `${latitude},${longitude}`;

    map.setView([latitude, longitude], 15);
    L.marker([latitude, longitude]).addTo(map).bindPopup("You are here");
  });
}

// ----------------------------------------------------------
// ROUTE + VALHALLA FIXED PARSER
// ----------------------------------------------------------
async function getRoute() {
  const start = document.getElementById("startInput_coords").value;
  const end = document.getElementById("endInput_coords").value;
  const mode = document.getElementById("modeSelect").value;

  if (!start) {
    alert("Please pick a valid START location.");
    return;
  }

  const url =
    `${API}/route?start=${encodeURIComponent(start)}&mode=${mode}` +
    (end ? `&end=${encodeURIComponent(end)}` : "");

  const res = await fetch(url);

  if (!res.ok) {
    alert(`Backend error (HTTP ${res.status})`);
    return;
  }

  const data = await res.json();

  if (data.error) {
    alert(data.error);
    return;
  }

  // ⭐ VALHALLA FIX — correct coordinate ordering
  // Backend returns [lat, lon]
  const coords = data.coordinates.map(c => [Number(c[0]), Number(c[1])]);

  if (routeLayer) routeLayer.remove();

  routeLayer = L.polyline(coords, { color: "blue", weight: 4 }).addTo(map);

  map.fitBounds(routeLayer.getBounds());
  animateRoute(coords);

  const elevations = data.elevation?.elevations ?? [];
  if (elevations.length) drawElevationChart(elevations);

  window.currentRouteCoords = coords;

  const btn = document.getElementById("startNavBtn");
  btn.classList.remove("hidden");
  btn.textContent = "▶️ Start Navigation";
  btn.onclick = startNavigation;

  if (window.navWatchId) {
    navigator.geolocation.clearWatch(window.navWatchId);
    window.navWatchId = null;
  }
}

// ----------------------------------------------------------
// TRAILS (Valhalla-compatible)
// ----------------------------------------------------------
async function getTrails() {
  const start = document.getElementById("startInput_coords").value;

  if (!start) {
    alert("Pick a valid START location first!");
    return;
  }

  const res = await fetch(
    `${API}/trails?start=${encodeURIComponent(start)}&radius=2000&limit=5`
  );
  const trails = await res.json();

  if (trailLayer) trailLayer.remove();
  trailLayer = L.layerGroup().addTo(map);

  trails.forEach(t => {
    // ⭐ VALHALLA FIX — route geometry is [lat, lon]
    const coords = t.geometry.map(c => [Number(c[0]), Number(c[1])]);

    L.polyline(coords, { color: "green", weight: 3 })
      .addTo(trailLayer)
      .bindPopup(`
        <b>${t.name}</b><br>
        ${difficultyIcon(t.difficulty)}<br>
        Elev Gain: ${t.elevation_gain_m} m<br>
        Scenic: ${t.scenic}<br>
        Safety: ${t.safety}
      `);
  });
}

// ----------------------------------------------------------
// EXPORT GPX (unchanged)
// ----------------------------------------------------------
function exportGPX() {
  const start = document.getElementById("startInput_coords").value;
  const end = document.getElementById("endInput_coords").value;
  const mode = document.getElementById("modeSelect").value;

  if (!start || !end) {
    alert("Select both START and END first.");
    return;
  }

  const url =
    `${API}/export_gpx?start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}&mode=${mode}`;

  window.location.href = url;
}

// ----------------------------------------------------------
// AUTOCOMPLETE ENGINE
// ----------------------------------------------------------
function setupAutocomplete(inputId, boxId) {
  const input = document.getElementById(inputId);
  const box = document.getElementById(boxId);
  const hiddenField = document.getElementById(inputId + "_coords");

  let items = [];
  let cursorIndex = -1;

  async function fetchSuggestions(query) {
    if (!query || query.length < 2) {
      box.classList.add("hidden");
      return;
    }

    const res = await fetch(`${API}/autocomplete?q=${encodeURIComponent(query)}&limit=5`);
    items = await res.json();

    box.innerHTML = "";
    cursorIndex = -1;

    if (items.length === 0) {
      box.classList.add("hidden");
      return;
    }

    // Auto-select 1 result
    if (items.length === 1) {
      const s = items[0];
      input.value = s.label;
      hiddenField.value = `${s.lat},${s.lon}`;
      box.classList.add("hidden");
      return;
    }

    // Auto-select exact match
    const exact = items.find(x => x.label.toLowerCase() === query.toLowerCase());
    if (exact) {
      input.value = exact.label;
      hiddenField.value = `${exact.lat},${exact.lon}`;
      box.classList.add("hidden");
      return;
    }

    // List dropdown
    items.forEach((s, i) => {
      const div = document.createElement("div");
      div.className = "autocomplete-item";
      div.textContent = s.label;

      div.onclick = () => {
        input.value = s.label;
        hiddenField.value = `${s.lat},${s.lon}`;
        box.classList.add("hidden");
      };

      box.appendChild(div);
    });

    box.classList.remove("hidden");
  }

  input.addEventListener("input", (e) => {
    hiddenField.value = "";
    fetchSuggestions(e.target.value.trim());
  });

  input.addEventListener("keydown", (e) => {
    const children = box.children;

    if (e.key === "ArrowDown") {
      e.preventDefault();
      cursorIndex = (cursorIndex + 1) % children.length;
      highlight(children, cursorIndex);
    }

    if (e.key === "ArrowUp") {
      e.preventDefault();
      cursorIndex = (cursorIndex - 1 + children.length) % children.length;
      highlight(children, cursorIndex);
    }

    if (e.key === "Enter") {
      e.preventDefault();
      if (cursorIndex >= 0) {
        const item = items[cursorIndex];
        input.value = item.label;
        hiddenField.value = `${item.lat},${item.lon}`;
        box.classList.add("hidden");
      }
    }
  });

  function highlight(children, idx) {
    [...children].forEach(c => c.classList.remove("active"));
    if (idx >= 0) children[idx].classList.add("active");
  }

  document.addEventListener("click", (e) => {
    if (!box.contains(e.target) && e.target !== input) {
      box.classList.add("hidden");
    }
  });
}

// ----------------------------------------------------------
// LIVE NAVIGATION
// ----------------------------------------------------------
let navMarker = null;
let watchId = null;

function startNavigation() {
  alert("Navigation started!");

  const btn = document.getElementById("startNavBtn");
  btn.textContent = "🛑 Stop Navigation";
  btn.onclick = stopNavigation;

  watchId = navigator.geolocation.watchPosition(
    pos => {
      const { latitude, longitude } = pos.coords;

      if (navMarker) navMarker.remove();

      navMarker = L.circleMarker([latitude, longitude], {
        radius: 8,
        color: "#2563eb",
        fillColor: "#3b82f6",
        fillOpacity: 1
      }).addTo(map);

      map.setView([latitude, longitude], map.getZoom());
    },
    err => console.error("GPS error:", err),
    { enableHighAccuracy: true, maximumAge: 1000, timeout: 5000 }
  );
}

function stopNavigation() {
  alert("Navigation stopped.");

  const btn = document.getElementById("startNavBtn");
  btn.textContent = "▶️ Start Navigation";
  btn.onclick = startNavigation;

  if (watchId) {
    navigator.geolocation.clearWatch(watchId);
    watchId = null;
  }

  if (navMarker) navMarker.remove();
  navMarker = null;
}

// ----------------------------------------------------------
// OPEN AR LEVEL-3
// ----------------------------------------------------------
function openAR() {
  if (!window.currentRouteCoords) {
    alert("Get a route first!");
    return;
  }

  const encoded = encodeURIComponent(
    JSON.stringify(window.currentRouteCoords)
  );

  window.location.href = `ar3.html?coords=${encoded}`;
}
