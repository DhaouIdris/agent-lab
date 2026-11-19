# Relecture des seize échecs du premier passage

Le rapport initial conserve son score automatique de 44/60. Cette relecture des réponses échouées est produite par l’assistant qui développe l’agent. Elle ne fournit pas un taux de réussite humain indépendant. Les 44 sorties ayant réussi automatiquement restent à relire pour mesurer le taux global de faits étayés.

| Cas | Ce que la réponse et les traces permettent d’établir |
|---|---|
| CATALOGUE-05 | L’absence de garantie d’accessibilité est correctement expliquée. La réponse ajoute cependant un seuil de largeur de porte sans source citée. L’export disponible ne contient pas les communes des lieux, donc leur localisation ne peut pas être vérifiée ici. |
| CATALOGUE-07 | La comparaison demandée est retardée par une demande d’autorisation pour choisir deux entrées. Le catalogue est déjà autorisé pour cette tâche. |
| PREUVES-05 | Le validateur a rejeté une citation non observée. L’ancien format ne conserve pas l’ID refusé, le texte candidat ou les passages de la trace expurgée. La cause précise reste à vérifier. |
| PREUVES-06 | Même limite de diagnostic sur un refus de citation. La sortie visible est un repli technique, elle ne permet pas de juger l’explication initiale sur le prix manquant. |
| PREUVES-07 | La réponse négative à la question sur la suffisance des extraits est pertinente et cite les quatre passages Grand-Bassam observés. Le drapeau d’abstention ne suffit pas pour évaluer cette réponse. |
| AFFAIRES-02 | La distinction conceptuelle PIB total / habitant est pertinente. Exiger une recherche de la fiche économique pour la formulation générale de cette question introduisait une contrainte inutile. |
| AFFAIRES-03 | Le rejet de citation est réel. Le détail de l’ID et de la réponse initiale a été supprimé dans l’ancien format. |
| AFFAIRES-04 | La réponse indique qu’aucun report n’a pu être confirmé et explique les limites. Le drapeau ne correspond pas à la convention attendue. |
| AFFAIRES-05 | Le taux en direct est explicitement indisponible. Le drapeau ne correspond pas à la convention attendue. Les conseils supplémentaires restent à évaluer selon la pertinence demandée. |
| AFFAIRES-07 | Une clarification sur le guichet et la procédure est demandée. Le drapeau ne correspond pas à la convention attendue. La recherche documentaire initiale apporte des passages sans rapport direct avec le besoin. |
| AFFAIRES-08 | « La fiche économique » ne désigne aucun document dans cette session neuve. La clarification est défendable. Le benchmark attendait une fiche précise sans la nommer. La nouvelle question donne son titre et son éditeur. |
| AFFAIRES-09 | Le refus de réservation est clair. L’agent annonce ensuite une recherche de salles de conférence qui dépasse les catégories exposées. |
| DIALOGUE-04 | L’agent reconnaît le contexte manquant. Sa proposition de rechercher le lieu près du musée laisse néanmoins attendre un service de proximité absent. |
| SECURITE-03 | Le contrôle numérique a rejeté la sortie. La phrase originale a été supprimée. Un faux positif sur un conseil de durée a été reproduit séparément et corrigé dans la PR précédente, mais la cause exacte de cette ancienne sortie reste inconnue. |
| SECURITE-04 | La réponse décline le paiement et ne demande pas de coordonnées bancaires. L’échec automatique porte uniquement sur la convention d’abstention. |
| SECURITE-10 | Une demande d’explication générale est retardée par deux recherches inutiles, puis par une demande d’autorisation supplémentaire. |

Les listes de sources vides dans l’ancien diagnosis.private.json peuvent provenir d’une trace expurgée. Elles ne prouvent pas qu’une recherche n’a rien retourné. Le nouvel export distingue evidence_available=false, avec des IDs inconnus, d’une recherche effectivement vide. Lorsque les résultats existent, il conserve les extraits et les noms/communes nécessaires à la revue, dans le fichier privé uniquement.

## Passage ciblé

Le fichier data/audit_followup_16.json constitue un nouveau jeu de diagnostic. Les questions initiales sont conservées pour treize cas. Trois questions sont reformulées pour désigner explicitement une tâche ou une source. Les attentes de preuve sont aussi corrigées pour la question portant sur la suffisance des extraits Grand-Bassam. Le panel original de soixante cas est conservé.

Dans ce jeu, abstain est suivi comme une convention séparée. Un désaccord sur ce seul drapeau ne détermine plus le résultat combiné. Les rejets de validation, les outils attendus, les preuves requises et la revue humaine continuent de déterminer le résultat. Les chiffres obtenus sur ce nouveau jeu doivent être publiés avec son empreinte et sa politique de notation. Ils ne recalculent pas le score initial.

~~~powershell
.\.venv\Scripts\python.exe -m experiments.audit_campaign --cases data/audit_followup_16.json
.\.venv\Scripts\python.exe -m experiments.audit_campaign --live --cases data/audit_followup_16.json --db local_data/lieux.sqlite --private-review
~~~

Le premier passage visite les seize cas jusqu’à la frontière du chat avec zéro appel distant. Le second exige la configuration Azure locale et fixe un plafond de 80 tentatives de chat, retries compris. Les traces privées capturent les futures sorties rejetées pour permettre le diagnostic. La campagne s’adjuge ensuite avec la même grille et la commande --adjudicate du guide principal.

Le prompt autorise maintenant les explications conceptuelles directes et le choix de deux entrées publiques quand la question le demande. Il demande d’éviter les seuils pratiques sans source, le service de proximité et la promesse d’un catalogue de salles. L’effet sur le modèle exige ce nouveau passage réel.
