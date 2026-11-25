# Extension des capacités territoriales — bilan de développement

Date : 25 novembre 2026. Cible confirmée : **Côte d’Ivoire uniquement**. Aucun flux officiel, GTFS, agenda, règles ou annuaire supplémentaire n’a été fourni. Cette extension est un **socle de contrats et de contrôles**, pas un assistant institutionnel opérationnel.

## Ce qui fonctionne maintenant

| Élément | État | Limite vérifiable |
| --- | --- | --- |
| Six nouveaux contrats (`search_public_services`, `get_entity_details`, `search_events_agenda`, `get_transit_options`, `get_official_alerts`, `lookup_procedure_rules`) | Schémas JSON fermés, champs requis et enums ; validation des arguments, dates, identifiants et provenance | Aucun adaptateur réel configuré : les outils ne sont **pas exposés** au LLM par défaut. Une exécution directe sans adaptateur retourne `SERVICE_UNAVAILABLE`. La compatibilité `strict: true` avec le déploiement Azure n'a pas encore été testée. |
| Détails d'entité | L'ID doit avoir été observé dans le registre correspondant pendant le tour | Aucun registre officiel chargé. |
| Contrôles d'entrée | Urgence lexicale avant modèle ; masquage de formats fréquents d'email, téléphone, IBAN, NIR, passeport et carte valide ; contexte date ISO à l'heure d'Abidjan | Pas de classifieur d'urgence, NER, rappel mesuré indépendamment, résolution des jours fériés ni garantie de détection exhaustive des PII. Le masquage ne remplace pas une politique de stockage des logs dans tous les clients. |
| Couplage catalogue | `origin_label` et `target_datetime_iso` acceptés ; origine inventée par le modèle rejetée ; origine réelle résolue par le catalogue/géocodeur et trajet à pied calculé si ORS répond | Le catalogue actuel n'a aucun horaire officiel : `open_status=UNKNOWN`. Pas de durée voiture attachée à chaque item dans ce chemin, pas de contrôle de fermeture exceptionnelle. La recherche catalogue autonome ne calcule pas les trajets. |
| Mode documentaire étendu | Passages d'un adaptateur configuré contrôlés contre les injections ; IDs observés vérifiés ; marqueurs `[CIT:id]` et `[[HANDOFF:id]]` résolus uniquement si observés et autorisés ; URL libre du modèle rejetée | La pertinence de chaque citation et la vérité de chaque phrase ne sont pas vérifiables automatiquement. Pas de régénération corrective : réponse de secours si garde de sortie en échec. Un lien officiel doit être explicitement configuré dans la liste blanche de l'application. |
| Budget | Au plus quatre appels de fonction par tour modèle ; timeout de 3 s transmis aux adaptateurs | Un adaptateur bloquant doit lui-même respecter cette limite. Pas de parallélisme effectif ni plafond de temps garanti de bout en bout. |

Le prompt alternatif n'est activé que lorsqu'au moins un adaptateur territorial est configuré. Il se présente comme un **assistant expérimental**, sans revendiquer un statut officiel, et n'annonce que les outils disponibles. Le prompt historique demeure celui du mode de base. Les schémas excluent les modes métro/tram et la ZFE français ; le profil `eu_visitor` du document initial est remplacé par `foreign_visitor`. Aucune règle de visa n'est déduite de cette seule catégorie.

## Pourquoi les flux restent désactivés

Des points de départ plausibles ont été repérés : [l'annuaire gouvernemental](https://annuaire.gouv.ci/), [le portail des démarches](https://www.servicepublic.gouv.ci/) et [l'agenda du CICG](https://www.cicg.gouv.ci/accueil). Ce sont des pages consultables, **pas** des flux stables déjà licenciés, synchronisés ou validés pour l'application. Vérifier les conditions de réutilisation, les interfaces, la date et la couverture avant toute ingestion.

- **Services publics, musées, santé** : sélectionner et licencier des enregistrements datés, avec identifiants stables, statut d'accessibilité attesté, horaires et, pour les pharmacies de garde, source de garde actualisée. Une fiche sans champ ne prouve ni ouverture ni fermeture.
- **Agenda et fermetures** : définir une source maintenue et son identifiant d'événement, sa période, sa zone, ses conditions de gratuité et la fréquence de synchronisation.
- **Transport** : trouver des flux GTFS autorisés et documenter la couverture réelle des réseaux ivoiriens. GTFS planifié ne prouve ni circulation en temps réel ni accessibilité PMR effective.
- **Alertes** : sélectionner une autorité compétente pour chaque domaine, avec horodatage et stratégie d'expiration ; sans flux, « aucune alerte » serait une conclusion fausse.
- **Démarches** : versionner chaque règle, champ conditionnel, date d'effet, éditeur et référence textuelle. Le modèle doit s'abstenir si la règle ou le profil requis manque.
- **Jours fériés** : ne pas déduire un calendrier officiel d'une bibliothèque générique sans validation locale. Le contexte temporel actuel marque ce calendrier comme indisponible.

Le document fourni mentionne 112/15/17/18, la Gare du Nord, la ZFE et le métro. Ces exemples sont français et ne sont pas transposés à la Côte d’Ivoire. Pour l'urgence ivoirienne, le court-circuit utilise **185 (SAMU), 180 (pompiers), 100 (police)** d'après [le ministère ivoirien des Affaires étrangères](https://www.diplomatie.gouv.ci/index.php/numeros-utiles) et [le portail gouvernemental](https://gouv.ci/index.php/actualite/amelioration-du-service-public-losep-au-service-de-la-population-2453). Vérification de ces références : 25 novembre 2026. Les lieux d'urgence les plus proches ne sont pas annoncés sans géolocalisation et données adaptées.

## Vérifications effectuées

`python -m unittest discover -s tests -q` : **310 tests réussis** dans l'environnement de développement. Les nouveaux tests couvrent les schémas, la provenance obligatoire, les IDs vus dans le bon registre, le rejet d'URL libre, la citation et le handoff, le court-circuit d'urgence, le masquage avant modèle et journal privé, les dates relatives et une origine catalogue résolue sans exposer ses coordonnées au modèle en mode étendu.
La dépendance `tzdata` fournit la zone `Africa/Abidjan` sous Windows, où la base de fuseaux système peut manquer. Installer `requirements.txt` avant les tests ou l'exécution locale.

`python -m experiments.eval_territory_controls --out /tmp/territory-controls-dev.json` : **12/12** urgences reconnues et **0/12** demandes bénignes bloquées sur un jeu **rédigé par l'auteur avec connaissance du filtre**. Le résultat ne mesure pas le rappel réel, ne justifie pas l'objectif de 99 % et ne teste pas un classifieur. Il faut un panel indépendant, multilingue et naturel, avec coût des faux blocages, avant de présenter cette voie comme protection suffisante.

## Avant d'activer les outils dans Azure

1. Obtenir les flux autorisés et documenter leur éditeur, licence, fréquence, couverture, dates et modalités d'accès ; implémenter au moins un adaptateur avec une stratégie de cache et d'échec explicite.
2. Ajouter `check_open_status` pour horaires et fermetures exceptionnelles, un calendrier officiel et la vérification des temps de trajet voiture si l'usage le demande.
3. Réaliser un préflight Azure des six schémas `strict`, mesurer la latence réellement observée et vérifier les limites du fournisseur.
4. Conduire un panel indépendant d'urgences, PII et injections, puis une campagne RAG avec revue humaine des affirmations, des citations, des refus et des liens.
5. Auditer l'ensemble des chemins de logs et les politiques de conservation avant d'affirmer une protection PII complète.

Pour l'instant, garder `TerritoryTools()` sans adaptateur ou ne pas le passer à `ask`. Les deux outils LLM historiques et l'itinéraire applicatif continuent de fonctionner comme auparavant, avec le prétraitement d'urgence/PII ajouté. Ne pas activer les nouvelles capacités comme services « officiels » sans données validées.
