# Corpus documentaire UNESCO : pilote

Cinq descriptions courtes de sites du patrimoine mondial, issues des pages UNESCO de Grand-Bassam, Taï, Comoé, Nimba et des mosquées soudanaises, sont conservées dans `data/unesco_source_texts`. Il s'agit des descriptions françaises affichées sous CC BY-SA 3.0 IGO (© UNESCO World Heritage Centre), pas des pages complètes ni des dossiers d'inscription. Les URL, titres, attribution, licence et date de consultation sont dans le manifeste et chaque passage. La typographie a été normalisée (exposants et espaces) ; conserver cette mention. Vérifier la licence et ses obligations avant toute redistribution, adaptation ou combinaison avec d'autres contenus.

Le corpus `data/rag_unesco_descriptions.json` contient 9 passages issus de ces 5 descriptions, créés avec des fenêtres d'au plus 400 caractères et 50 caractères de chevauchement. Les offsets et SHA-256 sont vérifiables sur les fichiers texte fournis ; ce ne sont pas des offsets sur les pages HTML d'origine. Les passages sont étiquetés `licensed_excerpt`, pas `user_supplied_text` : les droits ont été examinés pour le projet et ne sont pas une déclaration de l'utilisateur. Reproduction du découpage : `build_corpus` avec `chunk_chars=400, overlap=50`, puis remplacement de `content_type` et suppression de `rights_confirmed_by_user`.

Le jeu `data/rag_unesco_descriptions_dev_cases.json` comprend 8 questions répondables et 4 sans réponse. Il est séparé des jeux antérieurs mais a été conçu par le même auteur en connaissant les sources : il n'est pas indépendant. Certains passages se chevauchent et des identifiants annotés peuvent être des alternatives (UD02) ; le rappel automatique qui attend tous les IDs est alors trop strict. Revue humaine obligatoire des citations et affirmations. Le corpus ne contient que du patrimoine, aucune disponibilité en direct et peu d'informations pour le tourisme pratique ou les démarches business ; ce n'est pas un corpus représentatif.

```powershell
.\.venv\Scripts\python.exe -m experiments.document_rag_batch --corpus data/rag_unesco_descriptions.json --cases data/rag_unesco_descriptions_dev_cases.json
```

Jusqu'à 36 tentatives chat Azure, retries compris ; clé saisie masquée ou variable de session ; coûts et disponibilité dépendent de la ressource. Aucun Prompt Shields distant n'est activé par défaut. Les questions et extraits sont envoyés au fournisseur ; le rapport peut contenir les réponses et sources. Une source consultée ne garantit ni actualité ni exactitude de chaque réponse. Les tests locaux n'appellent pas Azure.
