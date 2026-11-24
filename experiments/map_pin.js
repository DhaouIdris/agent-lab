/* The selected location stays in this page until the user requests nearby places. */
'use strict';
const map = L.map('map').setView([5.33, -4.02], 12);
L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 19,
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>'
}).addTo(map);
const button = document.getElementById('search');
const compareButton = document.getElementById('compare');
const selection = document.getElementById('selection');
const message = document.getElementById('message');
const results = document.getElementById('results');
const comparison = document.getElementById('comparison');
let pin = null;
let selectionVersion = 0;

function selected() {
  if (!pin) return;
  selectionVersion += 1;
  selection.textContent = 'Point de départ choisi. Tu peux déplacer le repère avant de chercher.';
  button.disabled = false;
  compareButton.disabled = false;
  message.textContent = '';
  results.replaceChildren();
  comparison.hidden = true;
}
map.on('click', event => {
  if (pin) pin.setLatLng(event.latlng);
  else {
    pin = L.marker(event.latlng, {draggable: true}).addTo(map);
    pin.on('dragend', selected);
  }
  selected();
});
document.getElementById('category').addEventListener('change', selected);
document.getElementById('mode').addEventListener('change', selected);

function requestBody() {
  const point = pin.getLatLng();
  return {category: document.getElementById('category').value,
          mode: document.getElementById('mode').value,
          lat: point.lat, lon: point.lng};
}

async function query(endpoint) {
  const response = await fetch(endpoint, {
    method: 'POST',
    headers: {'Content-Type': 'application/json',
              'X-Map-Token': document.querySelector('meta[name="map-token"]').content},
    body: JSON.stringify(requestBody())
  });
  return {response, data: await response.json()};
}

function renderPlaces(list,element) {
  element.replaceChildren();
  for (const place of list) {
    const item = document.createElement('li');
    if (place.url) {
      const link = document.createElement('a');
      link.textContent = place.name;
      link.href = place.url;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      item.append(link);
    } else item.append(document.createTextNode(place.name));
    item.append(document.createTextNode(` : ${place.distance}${place.duration ? ', ' + place.duration : ''}`));
    element.append(item);
  }
}

button.addEventListener('click', async () => {
  if (!pin) return;
  const version = selectionVersion;
  button.disabled = true;
  compareButton.disabled = true;
  message.textContent = 'Recherche des trajets…';
  results.replaceChildren();
  try {
    const {response,data} = await query('/api/nearby');
    if (version !== selectionVersion) return;
    if (!response.ok || data.status !== 'ok') {
      message.textContent = data.message || 'La recherche est indisponible pour le moment.';
      return;
    }
    message.textContent = data.mode === 'car' ? 'Voici les lieux accessibles en voiture :' : 'Voici les lieux accessibles à pied :';
    renderPlaces(data.places,results);
  } catch (_) {
    if (version === selectionVersion) message.textContent = 'Impossible de joindre le service local pour le moment.';
  } finally {
    button.disabled = false;
    setTimeout(() => { if (pin && version === selectionVersion) compareButton.disabled = false; }, 1600);
  }
});

compareButton.addEventListener('click', async () => {
  if (!pin) return;
  const version=selectionVersion;
  compareButton.disabled=true;
  comparison.hidden=false;
  const note=document.getElementById('comparison-note');
  note.textContent='Comparaison des trajets en cours…';
  try {
    const {response,data}=await query('/api/compare');
    if (version !== selectionVersion) return;
    if (!response.ok || data.status !== 'ok') {
      note.textContent=data.message || 'Comparaison indisponible pour le moment.';
      return;
    }
    renderPlaces(data.short,document.getElementById('short-results'));
    renderPlaces(data.wide,document.getElementById('wide-results'));
    const coverage = data.top3_bounded_in_catalogue
      ? 'Les trois premiers couvrent aussi les lieux non testés selon la borne de distance.'
      : data.nearest_bounded_in_catalogue
        ? 'Le premier couvre aussi les lieux non testés selon la borne de distance ; le trio peut encore changer.'
        : 'D’autres lieux recensés pourraient encore donner un trajet plus court.';
    note.textContent=(data.top3_changed
      ? 'La sélection de 12 lieux a écarté au moins un des trois premiers parmi 50.'
      : 'Les trois premiers sont les mêmes avec 12 et 50 lieux.')
      + ` ${data.reachable_candidates} trajets calculés parmi ${data.candidate_count} lieux testés et ${data.matching_in_radius} recensés dans la zone. ${coverage} Le repère, le catalogue et le réseau routier peuvent rester incomplets.`;
  } catch (_) {
    if (version === selectionVersion) note.textContent='Impossible de joindre le service local pour le moment.';
  } finally {
    compareButton.disabled=false;
  }
});
