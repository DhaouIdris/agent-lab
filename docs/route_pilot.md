# Pilote itinéraire

Outil expérimental openrouteservice hébergé, en lecture seule et uniquement pour deux paires `latitude, longitude` explicites dans la question et un mode explicite voiture ou à pied. Aucun géocodage, classement du lieu le plus proche, réservation, trafic en direct ou garantie d'ouverture des lieux. Un trajet explicite est validé localement puis transmis à HeiGIT. Le calcul simple consomme zéro appel de chat. Dans une question mixte reconnue, la partie documentaire est traitée séparément. Ne pas mettre de lieux privés dans les scénarios ou rapports. Réponse chiffrée produite par le code depuis le service ; données de cartographie © contributeurs OpenStreetMap, calcul openrouteservice. Un délai, une absence de clé ou une erreur fournisseur entraîne une abstention. Le détecteur lexical reste incomplet.

Les latitudes hors [-90, 90] et les longitudes hors [-180, 180] sont rejetées avant appel à Azure et au service ; les mêmes bornes sont contrôlées au niveau du client de routage. Cette validation ne confirme pas l'ordre des coordonnées, leur emplacement en Côte d'Ivoire, une route existante ou la précision des données OSM. Le prototype attend des paires décimales séparées par une virgule.

Créer une clé gratuite dans le compte HeiGIT et consulter les quotas. Dans le fichier `.env` à la racine du projet, renseigner `ORS_API_KEY=...` (ne pas partager ce fichier). Une variable d'environnement déjà définie a priorité sur `.env`. Lancer ensuite :

```powershell
.\.venv\Scripts\python.exe -m experiments.unified_agent_consistency --db local_data/lieux.sqlite --cases data/unified_route_pilot.json --repeat 1
```

La clé n'est pas dans le rapport. Les questions et réponses peuvent y figurer. Le pilote utilise au plus 25 tentatives Azure ; le service routier n'est appelé que si le modèle demande l'outil et que les coordonnées et le mode correspondent strictement à la question. Il n'y a pas de retry ORS. Les contrôles automatiques des noms d'outils ne vérifient pas la qualité de la réponse ; relire le rapport. Tester le service dans une région ne prouve pas sa couverture routière sur toute la Côte d'Ivoire. Il peut refuser, limiter ou retourner un itinéraire imparfait.
