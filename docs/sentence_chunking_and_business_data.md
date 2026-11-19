# Découpage par phrases et données économiques : pilotes

L'importeur conserve le mode historique `characters` par défaut pour éviter de modifier les corpus existants. L'option `--split-mode sentences` privilégie les fins de phrases et paragraphes, avec une heuristique simple ; elle ne comprend pas toutes les abréviations et langues. Si une phrase dépasse la taille maximale, la coupure par mots ou caractères reste possible. Le chevauchement demandé est un maximum : lorsqu'aucune phrase entière ne rentre dans cette limite, il peut être nul. Les offsets Python et les empreintes font toujours référence aux textes fournis, pas aux pages HTML d'origine.

```powershell
.\.venv\Scripts\python.exe -m experiments.ingest_text_documents --manifest local_data/documents/manifest.json --out local_data/documents/corpus_sentences.json --split-mode sentences
```

`data/rag_unesco_sentences.json` est un corpus séparé de l'ancien `rag_unesco_descriptions.json`, créé à partir des mêmes descriptions avec 400 caractères maximum et chevauchement maximal de 50. Il contient 11 passages au lieu de 9. Attention : certains IDs existent dans les deux fichiers mais correspondent désormais à des offsets et contenus différents. Les anciens IDs, annotations et rapports ne sont pas interchangeables ; le jeu de cas `rag_unesco_sentences_dev_cases.json` corrige UD02 et doit accompagner ce corpus. Les deux corpus gardent les mêmes cinq sources UNESCO sous CC BY-SA 3.0 IGO ; consulter `docs/unesco_descriptions_pilot.md` pour les limites et attributions.

```powershell
.\.venv\Scripts\python.exe -m experiments.document_rag_batch --corpus data/rag_unesco_sentences.json --cases data/rag_unesco_sentences_dev_cases.json
```

Le jeu de 12 cas est réutilisé pour une première comparaison, non indépendante ; jusqu'à 36 tentatives de chat Azure, retries inclus. Les réponses et citations restent à examiner humainement ; la réduction des coupures de phrases n'assure ni pertinence ni fidélité.

## Premier indicateur économique séparé

`data/rag_worldbank_pilot.json` contient un résumé rédigé pour le projet de la valeur du PIB ivoirien 2025 en dollars courants, arrondie, issue des données Banque mondiale consultées le 18 novembre 2026. L'indicateur est publié sous CC BY 4.0, avec attribution et lien de licence dans l'entrée. Il s'agit d'une capture statique potentiellement révisable, non d'un flux à jour ou de conseils économiques. Le corpus contient une seule donnée ; il ne couvre ni investissements, ni formalités, ni marché local.

```powershell
.\.venv\Scripts\python.exe -m experiments.document_rag_batch --corpus data/rag_worldbank_pilot.json --cases data/rag_worldbank_pilot_cases.json
```

Les deux questions demandent le PIB total puis le PIB par habitant, absent du passage. Jusqu'à six tentatives chat ; les réponses sont à relire. Les jeux sont des exemples provisoires écrits en connaissant les données. Les textes et questions sont envoyés à Azure ; les coûts ne sont pas calculés et aucun appel réel n'a été lancé par l'auteur du code.
