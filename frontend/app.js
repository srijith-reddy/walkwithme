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

// ----------------------------------------------------------
// MAP INIT (runs AFTER DOM loads)
// ----------------------------------------------------------
document.addEventListener("DOMContentLoaded", () => {

  // Register Service Worker (PWA)
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("service-worker.js")
      .then(() => console.log("SW registered"))
      .catch(err => console.log("SW registration failed", err));
  }

  // 1) Init map
  map = L.map("map").setView([40.7128, -74.0060], 14);

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenStreetMap",
  }).addTo(map);

  // 2) Allow clicking map to choose start/end
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

  // 3) Attach autocomplete to inputs
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
// DIFFICULTY ICONS
// ----------------------------------------------------------
function difficultyIcon(level) {
  if (level === "Easy") return "🟢 Easy";
  if (level === "Moderate") return "🟡 Moderate";
  if (level === "Hard") return "🟠 Hard";
  return "🔴 Very Hard";
}

// ----------------------------------------------------------
// ELEVATION CHART
// ----------------------------------------------------------
function drawElevationChart(elevations) {
  if (elevationChart) elevationChart.destroy();
  const ctx = document.getElementById("elevationChart");

  elevationChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: elevations.map((_, i) => i),
      datasets: [{
        label: "Elevation (m)",
        data: elevations,
        borderColor: "#4f46e5",
        fill: false
      }]
    },
    options: { responsive: true }
  });
}

// ----------------------------------------------------------
// ROUTE ANIMATION
// ----------------------------------------------------------
function animateRoute(coords) {
  let index = 0;

  const marker = L.circleMarker(coords[0], {
    radius: 6,
    color: "#0ea5e9",
    fillColor: "#38bdf8",
    fillOpacity: 1
  }).addTo(map);

  function step() {
    if (index >= coords.length) return;
    marker.setLatLng(coords[index]);
    index++;
    requestAnimationFrame(step);
  }

  step();
}

// ----------------------------------------------------------
// TRANSIT FALLBACK
// ----------------------------------------------------------
function showTransitFallbacks() {
  if (pathLayer) pathLayer.remove();
  if (ferryLayer) ferryLayer.remove();

  pathLayer = L.layerGroup().addTo(map);
  ferryLayer = L.layerGroup().addTo(map);

  const PATH_LINES = [
    [
      [40.734785, -74.164580],
      [40.737102, -74.143406],
      [40.733013, -74.059587],
      [40.749641, -74.033963],
      [40.753897, -74.029045],
      [40.712580, -74.009260]
    ]
  ];

  PATH_LINES.forEach(line => {
    L.polyline(line, { color: "purple", weight: 4, opacity: 0.8 })
      .addTo(pathLayer)
      .bindPopup("PATH Train Line");
  });

  alert("Walking unavailable. Showing PATH & Ferry options.");
}

// ----------------------------------------------------------
// GET ROUTE
// ----------------------------------------------------------
async function getRoute() {
  const start = document.getElementById("startInput_coords").value;
  const end = document.getElementById("endInput_coords").value;
  const mode = document.getElementById("modeSelect").value;

  if (!start) {
    alert("Please pick a valid START location from autocomplete.");
    return;
  }

  const url =
    `${API}/route?start=${encodeURIComponent(start)}&mode=${mode}` +
    (end ? `&end=${encodeURIComponent(end)}` : "");

  const res = await fetch(url);
  const data = await res.json();

  if (data.error) {
    if (data.suggest) showTransitFallbacks();
    alert(data.error);
    return;
  }

  if (routeLayer) routeLayer.remove();
  const coords = data.coordinates.map(c => [Number(c[0]), Number(c[1])]);

  routeLayer = L.polyline(coords, { color: "blue", weight: 4 }).addTo(map);
  map.fitBounds(routeLayer.getBounds());
  animateRoute(coords);

  const elevations = data.elevation?.elevations ?? [];
  if (elevations.length) drawElevationChart(elevations);
}

// ----------------------------------------------------------
// EXPORT GPX
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
// FIND TRAILS
// ----------------------------------------------------------
async function getTrails() {
  const start = document.getElementById("startInput_coords").value;

  if (!start) {
    alert("Pick a valid START location first!");
    return;
  }

  const res = await fetch(`${API}/trails?start=${encodeURIComponent(start)}&radius=2000&limit=5`);
  const trails = await res.json();

  if (trailLayer) trailLayer.remove();
  trailLayer = L.layerGroup().addTo(map);

  trails.forEach(t => {
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

    // Dropdown list
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
// PWA INSTALL PROMPT
// ----------------------------------------------------------
let deferredPrompt;

window.addEventListener("beforeinstallprompt", (e) => {
  e.preventDefault();
  deferredPrompt = e;

  const btn = document.getElementById("installBtn");
  if (btn) btn.style.display = "block";

  btn.onclick = () => {
    btn.style.display = "none";
    deferredPrompt.prompt();
  };
});

