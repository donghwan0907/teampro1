const SL = window.SafeLease;
const colors = {
  '낮음': '#3ba272',
  '주의': '#f2bf48',
  '높음': '#ec7c3b',
  '매우 높음': '#d84a4a',
  '자료 부족': '#aab2bd',
};

const escapeHtml = (value) => String(value ?? '')
  .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
  .replaceAll('"', '&quot;').replaceAll("'", '&#039;');

const map = L.map('map', { zoomControl: true, minZoom: 10 }).setView([37.5665, 126.9780], 11);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  attribution: '© OpenStreetMap contributors',
  maxZoom: 18,
}).addTo(map);

let geoLayer;

function styleFeature(feature) {
  const level = feature.properties.risk_level || '자료 부족';
  return {
    color: '#ffffff',
    weight: 0.9,
    fillColor: colors[level] || colors['자료 부족'],
    fillOpacity: 0.72,
  };
}

function popupHtml(properties) {
  const code = String(properties.legal_dong_code || '').padStart(10, '0');
  const evidence = Number(properties.official_dong_evidence_count || 0) > 0
    ? '<span class="popup-badge">동 단위 공식자료 있음</span>'
    : '';
  return `
    <div class="popup-title">서울 ${escapeHtml(SL.value(properties.district, ''))} ${escapeHtml(SL.value(properties.legal_dong, ''))}</div>
    <div class="popup-score">${SL.fmt(properties.risk_score)}점 · ${escapeHtml(SL.riskLevelLabel(properties.risk_level))}</div>
    ${evidence}
    <div class="popup-meta">
      자료 신뢰도 ${escapeHtml(SL.value(properties.data_confidence))}<br>
      추정 전세가율 ${SL.fmt(properties.jeonse_ratio_pct)}%<br>
      매매 ${SL.fmt(properties.sale_count, 0)}건 · 전세 ${SL.fmt(properties.jeonse_count, 0)}건<br>
      자치구 공식 가결 ${SL.fmt(properties.official_total, 0)}건
    </div>
    <a class="popup-link" href="/region/${code}">전세 위험 근거 자세히 보기 →</a>
  `;
}

fetch('/api/map/legal-dong')
  .then((response) => {
    if (!response.ok) throw new Error('서울 법정동 지도 데이터를 불러오지 못했습니다.');
    return response.json();
  })
  .then((geojson) => {
    geoLayer = L.geoJSON(geojson, {
      style: styleFeature,
      onEachFeature: (feature, layer) => {
        layer.bindPopup(popupHtml(feature.properties), { maxWidth: 390 });
        layer.on({
          mouseover: (event) => event.target.setStyle({ weight: 2.3, fillOpacity: 0.88 }),
          mouseout: (event) => geoLayer.resetStyle(event.target),
        });
      },
    }).addTo(map);
    map.fitBounds(geoLayer.getBounds(), { padding: [8, 8] });
  })
  .catch((error) => {
    document.getElementById('map').innerHTML = `<p class="map-error">${escapeHtml(error.message)}</p>`;
  });

fetch('/api/summary')
  .then((response) => response.json())
  .then((summary) => {
    document.getElementById('metric-dongs').textContent = SL.fmt(summary.legal_dongs, 0);
    document.getElementById('metric-high').textContent = SL.fmt(summary.high_or_higher, 0);
    document.getElementById('metric-confidence').textContent = SL.fmt(summary.high_confidence, 0);
    document.getElementById('metric-official').textContent = SL.fmt(summary.official_district_total_2023_2025, 0);
  });

async function searchRegion() {
  const query = document.getElementById('region-search').value.trim();
  const resultBox = document.getElementById('search-result');
  if (!query) {
    resultBox.textContent = '자치구 또는 법정동명을 입력하세요.';
    return;
  }
  resultBox.innerHTML = '검색 중…';
  const response = await fetch(`/api/dong-risk?query=${encodeURIComponent(query)}&limit=12`);
  const { items } = await response.json();
  if (!items.length) {
    resultBox.textContent = '일치하는 서울 법정동이 없습니다.';
    return;
  }
  resultBox.innerHTML = items.map((item) => `
    <a class="search-hit" href="/region/${String(item.legal_dong_code).padStart(10, '0')}">
      ${escapeHtml(item.district)} ${escapeHtml(item.legal_dong)} · ${SL.fmt(item.risk_score)}점 · 신뢰도 ${escapeHtml(SL.value(item.data_confidence))}
    </a>
  `).join('');
}

document.getElementById('search-button').addEventListener('click', searchRegion);
document.getElementById('region-search').addEventListener('keydown', (event) => {
  if (event.key === 'Enter') searchRegion();
});
