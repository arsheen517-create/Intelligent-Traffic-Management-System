(function () {
  const LEVELS = [
    {
      max: 0,
      label: 'No traffic',
      color: '#22c55e',
      radius: 80
    },
    {
      max: 5,
      label: 'Low traffic',
      color: '#22c55e',
      radius: 120
    },
    {
      max: 12,
      label: 'Moderate traffic',
      color: '#3b82f6',
      radius: 180
    },
    {
      max: 20,
      label: 'High traffic',
      color: '#f59e0b',
      radius: 240
    },
    {
      max: Infinity,
      label: 'Very high traffic',
      color: '#ef4444',
      radius: 300
    }
  ];

  function densityLevel(density) {
    const count = Number(density) || 0;
    return LEVELS.find(level => count <= level.max) || LEVELS[LEVELS.length - 1];
  }

  function create(map, signalLocations) {
    const overlays = {};

    addLegend(map);

    Object.entries(signalLocations).forEach(([lane, point]) => {
      const level = densityLevel(0);

      overlays[lane] = L.circle([point.lat, point.lng], {
        radius: level.radius,
        color: level.color,
        weight: 2,
        opacity: 0.9,
        fillColor: level.color,
        fillOpacity: 0.24,
        interactive: true
      }).addTo(map);

      overlays[lane].bindPopup(
        `${point.label}<br>Density: 0 vehicles<br>${level.label}`
      );
    });

    return overlays;
  }

  function addLegend(map) {
    if (map._itmsDensityLegend) return;

    const legend = L.control({ position: 'bottomright' });

    legend.onAdd = function () {
      const div = L.DomUtil.create('div', 'itms-density-legend');

      div.innerHTML = `
        <div style="
          background:rgba(15,23,42,.92);
          color:#fff;
          padding:.65rem .75rem;
          border-radius:10px;
          border:1px solid rgba(255,255,255,.14);
          box-shadow:0 10px 30px rgba(15,23,42,.25);
          font:12px Inter,Arial,sans-serif;
          line-height:1.35;">
          <div style="font-weight:700;margin-bottom:.35rem;">Traffic Density</div>
          <div><span style="display:inline-block;width:18px;height:6px;background:#22c55e;border-radius:4px;margin-right:6px;"></span>Low</div>
          <div><span style="display:inline-block;width:18px;height:6px;background:#3b82f6;border-radius:4px;margin-right:6px;"></span>Medium</div>
          <div><span style="display:inline-block;width:18px;height:6px;background:#f59e0b;border-radius:4px;margin-right:6px;"></span>High</div>
          <div><span style="display:inline-block;width:18px;height:6px;background:#ef4444;border-radius:4px;margin-right:6px;"></span>Very high</div>
        </div>
      `;

      return div;
    };

    legend.addTo(map);
    map._itmsDensityLegend = legend;
  }

  function update(overlays, signalLocations, state) {
    for (let lane = 1; lane <= 4; lane++) {
      const laneState = state[lane] || state[String(lane)];
      const overlay = overlays[lane] || overlays[String(lane)];
      const location = signalLocations[lane] || signalLocations[String(lane)];

      if (!laneState || !overlay || !location) continue;

      const density = Number(laneState.density) || 0;
      const level = densityLevel(density);

      overlay.setStyle({
        color: level.color,
        fillColor: level.color
      });

      overlay.setRadius(level.radius);
      overlay.setPopupContent(
        `${location.label}<br>Density: ${density} vehicles<br>${level.label}`
      );
    }
  }

  window.ITMSDensityOverlay = {
    create,
    update,
    densityLevel
  };
})();
