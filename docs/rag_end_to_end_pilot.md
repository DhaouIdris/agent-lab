# Pilote RAG documentaire de bout en bout

La baseline est BM25 local, puis le contrôle lexical expérimental des passages, puis génération Azure JSON et vérification des identifiants de citations. Prompt Shields Azure Content Safety peut être activé en option. Le RAG documentaire est distinct du prototype agentique et de son catalogue SQLite ; il ne déclenche pas d'outils de réservation. Le corpus contient dix courtes annotations, pas une base documentaire complète.

`data/rag_end_to_end_dev.json` contient 18 questions déjà présentes dans le jeu de recherche élargi : neuf attendent une réponse sourcée et neuf une abstention. Elles ont été produites avec connaissance du corpus par le même auteur ; elles ne sont pas indépendantes. L'examen humain doit vérifier la fidélité, l'utilité, la pertinence des citations, l'absence d'inventions et les refus excessifs. Le contrôle automatique vérifie l'indicateur `abstain`, pas le sens de la réponse ; les IDs de citation sont contrôlés mais pas leur pertinence sémantique.

Un essai sans Prompt Shields additionnel utilise la configuration chat `azure.json`, une clé demandée masquée et au maximum 54 tentatives chat pour les 18 cas (jusqu'à trois par cas, retries compris). Des appels peuvent être facturés même en cas d'échec ; aucun plafond financier n'est établi. La campagne s'arrête sur erreur chat. Les rapports peuvent contenir questions, réponses et passages : ne pas transmettre de documents confidentiels et vérifier avant partage. Le fichier ne contient pas l'endpoint configuré ni la clé.

```powershell
.\.venv\Scripts\python.exe -m experiments.document_rag_batch --corpus data/rag_seed_extended.json --cases data/rag_end_to_end_dev.json
```

Le résumé affiche le chemin du rapport généré. Pour choisir un chemin, ajouter `--out runs/rag_e2e_01` (ce dossier ne doit pas déjà exister). Aucune clé ne doit être passée en argument de commande.

Pour utiliser en plus Prompt Shields, déployer/configurer séparément Azure Content Safety et fournir son endpoint sans clé ; la clé est demandée de façon masquée ou lue depuis `AGENTLAB_SHIELD_KEY` :

```powershell
.\.venv\Scripts\python.exe -m experiments.document_rag_batch --corpus data/rag_seed_extended.json --cases data/rag_end_to_end_dev.json --prompt-shield-endpoint https://MA-RESSOURCE.cognitiveservices.azure.com
```

Le contrôle local lexical intervient avant Prompt Shields. Au maximum un appel Content Safety par cas dans ce pilote (k=3, limite fournisseur de cinq passages par requête), donc jusqu'à 18 appels, en plus des appels chat. La question et les passages sont envoyés à Content Safety. Une attaque détectée bloque ce cas ; si le service est indisponible ou renvoie un format invalide, la génération est interrompue et la campagne s'arrête. Les blocages et indisponibilités ne sont pas comptés comme des réponses du modèle. Les résultats du fournisseur peuvent avoir des faux positifs et négatifs ; ni filtre n'établit la sécurité.

Le rapport est sauvegardé après chaque cas et contient les résultats de génération et l'usage chat quand fourni, mais aucun coût calculé ni compte d'appels ou tarif Content Safety. Les tests locaux simulent ces services ; aucun essai live n'a été réalisé par l'auteur de ce changement. Sur erreur, ne pas relancer en boucle ; examiner le rapport partiel et la configuration.
