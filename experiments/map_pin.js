/* The selected location stays in this page until the user requests nearby places. */
'use strict';
const map = L.map('map').setView([5.33, -4.02], 12);
L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 19,
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>'
}).addTo(map);
const button = document.getElementById('search');
const selection = document.getElementById('selection');
const message = document.getElementById('message');
const results = document.getElementById('results');
let pin = null;

function selected() {
  selection.textContent = 'Point de départ choisi. Tu peux déplacer le repère avant de chercher.';
  button.disabled = false;
  message.textContent = '';
  results.replaceChildren();
}
map.on('click', event => {
  if (pin) pin.setLatLng(event.latlng);
  else {
    pin = L.marker(event.latlng, {draggable: true}).addTo(map);
    pin.on('dragend', selected);
  }
  selected();
});

button.addEventListener('click', async () => {
  if (!pin) return;
  button.disabled = true;
  message.textContent = 'Recherche des trajets…';
  results.replaceChildren();
  const point = pin.getLatLng();
  try {
    const response = await fetch('/api/nearby', {
      method: 'POST',
      headers: {'Content-Type': 'application/json',
                'X-Map-Token': document.querySelector('meta[name="map-token"]').content},
      body: JSON.stringify({category: document.getElementById('category').value,
                            mode: document.getElementById('mode').value,
                            lat: point.lat, lon: point.lng})
    });
    const data = await response.json();
    if (!response.ok || data.status !== 'ok') {
      message.textContent = data.message || 'La recherche est indisponible pour le moment.';
      return;
    }
    message.textContent = data.mode === 'car' ? 'Voici les lieux accessibles en voiture :' : 'Voici les lieux accessibles à pied :';
    for (const place of data.places) {
      const item = document.createElement('li');
      const link = document.createElement('a');
      link.textContent = place.name;
      link.href = place.url;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      item.append(link, document.createTextNode(` : ${place.distance}, ${place.duration}`));
      results.append(item);
    }
  } catch (_) {
    message.textContent = 'Impossible de joindre le service local pour le moment.';
  } finally {
    button.disabled = false;
  }
});
