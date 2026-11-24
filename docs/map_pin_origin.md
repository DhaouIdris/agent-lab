# Pilote local : choisir un départ sur une carte

Quand une adresse libre ne peut pas être localisée de façon fiable, l'utilisateur peut cliquer sur une carte pour choisir son départ. Le navigateur garde la position sélectionnée en mémoire jusqu'au clic sur **Voir les lieux proches**. La page n'affiche jamais de nombres latitude/longitude ; le serveur local transmet le point choisi à la fonction de classement déjà utilisée par l'agent, qui interroge openrouteservice pour les distances et les durées. La clé `ORS_API_KEY` reste côté Python. Aucun appel Azure, géocodeur ou modèle n'est fait dans ce parcours.

Depuis la racine du dépôt sous PowerShell, avec la base SQLite déjà importée et la clé ORS dans `.env` :

```powershell
.\.venv\Scripts\python.exe -m experiments.map_pin --db local_data/lieux.sqlite
```

Ouvrir `http://127.0.0.1:8765/`, cliquer sur le point de départ, déplacer le repère si nécessaire, choisir restaurants ou une autre catégorie et « à pied » ou « en voiture », puis lancer la recherche. Le navigateur affiche au plus trois lieux avec leur lien OpenStreetMap, la distance et la durée estimées. Fermer la page et arrêter le serveur avec `Ctrl+C` après l'essai. Il n'y a pas de recherche d'adresse dans cette page et aucune entrée de bâtiment n'est vérifiée. Une zone dépourvue de lieux recensés ou un échec d'ORS conduit à un message, sans distance inventée.

Le serveur n'écoute que `127.0.0.1`. Il exige un jeton de page et la même origine HTTP pour la requête, valide les catégories et la position, limite la taille des messages et n'enregistre pas les positions dans des rapports ou journaux. Le navigateur envoie le point à ce serveur local uniquement au lancement d'une recherche ; ORS reçoit ensuite ce point pour calculer les trajets. Les tuiles du fond de carte sont chargées par le navigateur depuis OpenStreetMap pour la zone visible. Elles suivent la [politique d'utilisation des tuiles OSM](https://operations.osmfoundation.org/policies/tiles/) : attribution affichée, cache du navigateur, aucun téléchargement préalable ni mode hors ligne. Leaflet 1.9.4 est chargé depuis un CDN avec contrôle d'intégrité. L'accès à Internet est donc nécessaire pour la carte et pour ORS.

Ce pilote teste la sélection explicite d'un point en remplacement d'une adresse que Pelias ne sait pas résoudre. Les frontières sont seulement contrôlées par un rectangle englobant la Côte d'Ivoire ; le clic doit être vérifié visuellement. Le point cartographique peut différer de l'entrée routable, et le catalogue reste limité. Avant une mise en production, il faudra une interface adaptée au produit, une politique de tuiles et de confidentialité propre au déploiement, et des essais humains sur plusieurs points et trajets.
