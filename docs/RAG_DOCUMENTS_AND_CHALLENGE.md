# Ingestion documentaire et lot de diagnostic

La version de développement conserve le corpus original et ajoute `data/rag_seed_extended.json` : dix courtes annotations factuelles rédigées pour le projet à partir de pages officielles. Ce ne sont pas des documents complets. Les annotations supplémentaires concernent notamment la situation et la superficie du parc de la Comoé, la décision de 2017, le lieu du SIREXE et le périmètre du guichet CEPICI. Leurs sources et dates de consultation sont dans le JSON. Une date de consultation n'est pas une date de mise à jour ; les informations pratiques restent à vérifier.

Le lot `data/rag_challenge_dev.json` contient 12 questions : six réponses attendues, six abstentions, dont une instruction demandant d'inventer un tarif. Les cas sont **provisoires**, rédigés par le même assistant en connaissance du corpus. Ils ne constituent pas un jeu indépendant ni une validation par des experts. Les sorties automatiques évaluent le drapeau d'abstention et la présence d'un passage attendu ; elles ne valident pas la fidélité ni la pertinence de toutes les citations. Le programme enregistre les SHA-256 des fichiers corpus et cas dans le rapport final.

`data/rag_synthetic_conflicts.json` et `data/rag_synthetic_conflicts_cases.json` sont deux scénarios entièrement fictifs, séparés du corpus réel : tarifs contradictoires et instruction injectée dans une source. Ils ne représentent pas des établissements réels. Les réponses exigent une revue humaine : le contrôle automatique n'établit pas que les deux contradictions ont été relevées ni que l'injection a été ignorée.

```powershell
# Recherche locale seule
.\.venv\Scripts\python.exe -m experiments.document_rag retrieve --corpus data/rag_seed_extended.json --question "Quelle superficie couvre le parc de la Comoé ?"

# Lot payant : au plus 36 tentatives HTTP, retries compris
.\.venv\Scripts\python.exe -m experiments.document_rag_batch --corpus data/rag_seed_extended.json --cases data/rag_challenge_dev.json

# Lot séparé et fictif, au plus 6 tentatives HTTP
.\.venv\Scripts\python.exe -m experiments.document_rag_batch --corpus data/rag_synthetic_conflicts.json --cases data/rag_synthetic_conflicts_cases.json
```

Le lot est limité à 20 cas par lancement. Les appels sont séquentiels avec l'espacement défini dans `azure.json`. La clé est saisie en mode masqué ; questions et passages sont envoyés au fournisseur. Un rapport partiel est conservé après chaque cas. Un plafond d'appels n'est pas un plafond financier.

## Ajouter ses propres documents autorisés

L'importeur accepte des fichiers **texte brut UTF-8 locaux** seulement. Il ne télécharge pas et n'extrait pas les PDF/HTML, ne vérifie pas lui-même les licences et ne garantit pas qu'un texte soit à jour. Avant chaque import, confirmer les droits d'utilisation et, si applicable, de redistribution ; ne pas mettre de données personnelles dans un dépôt partagé. Les documents peuvent contenir des instructions adverses : ils restent des données non fiables.

Créer un dossier `local_data/documents/`, y placer par exemple `guide.txt` et `manifest.json` :

```json
[
  {
    "id": "GUIDE_01",
    "title": "Titre du document",
    "file": "guide.txt",
    "url": "https://example.org/guide",
    "publisher": "Éditeur",
    "consulted_at": "2026-11-17",
    "source_updated_at": null,
    "license_note": "Licence et conditions effectivement vérifiées",
    "rights_confirmed": true
  }
]
```

L'URL d'exemple n'est pas une source réelle. Remplacer les valeurs par celles du document utilisé. Tous les champs sauf `source_updated_at` sont obligatoires ; `rights_confirmed` est une déclaration de l'utilisateur, pas une vérification juridique automatique. Chaque document doit se trouver sous le dossier du manifeste. Les URLs contenant identifiants, paramètres de requête ou fragment sont refusées. Maximum 1 Mo par fichier texte.

```powershell
.\.venv\Scripts\python.exe -m experiments.ingest_text_documents --manifest local_data/documents/manifest.json --out local_data/documents/corpus.json
.\.venv\Scripts\python.exe -m experiments.document_rag retrieve --corpus local_data/documents/corpus.json --question "Votre question"
```

Un fichier de sortie existant est refusé. Les passages sont construits par fenêtres de caractères avec chevauchement (800 caractères et 120 de chevauchement par défaut), pas par découpage sémantique. Chaque passage garde l'ID et le titre du document, des offsets en caractères Python, une empreinte SHA-256 du texte source et la provenance déclarée. `--chunk-chars` et `--overlap` sont bornés. Il faut conserver le fichier texte original pour réutiliser les offsets. Les sources fournies au modèle comprennent le texte récupéré : ne pas envoyer de documents confidentiels sans autorisation adaptée.

## Étape suivante

Réunir des documents complets avec licence et dates vérifiées, puis faire relire les annotations de pertinence par au moins une personne indépendante. Construire un jeu de test à part regroupé par document et version pour éviter les quasi-doublons entre développement et test ; mesurer retrieval, réponses et citations, abstentions et prompt injections, puis comparer méthodes lexicales/denses/hybrides sur exactement le même jeu. Le score provisoire de ce lot ne justifie ni décision de production ni classement entre modèles.
