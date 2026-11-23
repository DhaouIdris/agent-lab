# Panel naturel de l'agent complet : revue avant Azure

`data/agent_holdout_natural_52.json` contient **52 questions** nouvelles dans ce dépôt, formulées comme des demandes d'utilisateur : 8 de catalogue, 8 de documents, 7 d'affaires, 7 de trajet, 8 de proximité, 6 de dialogue et 8 de sécurité (dont demandes malveillantes et questions bénignes sur la sécurité). Les questions ne contiennent aucune consigne de benchmark ; l'attendu humain, le but et les vérifications restent dans des champs séparés, jamais ajoutés à la question transmise à l'agent. **18 cas** sont marqués pour trois répétitions ultérieures, répartis entre les sept catégories.

Le panel vérifie sélection d'outils, références effectivement consultées, distances issues d'ORS, refus des actions indisponibles, protection contre injections utilisateur mêlées à une demande légitime et absence de surblocage sur les questions bénignes. Les cas d'absence de données ne doivent pas produire d'horaires, prix, offres ou accès actuels inventés. Les scénarios sont **rédigés par l'équipe du projet en connaissant le corpus** : ils ne constituent ni une annotation indépendante ni un échantillon représentatif des utilisateurs. Ils servent à la revue et au diagnostic ; aucune réussite automatique ne prouve la fidélité ou la qualité de la réponse.

Avant d'utiliser Azure, relire `docs/agent_holdout_questions_review.md` dans GitHub : les 52 questions et leurs attentes y sont déjà présentées en Markdown. Pour produire aussi une copie locale :

~~~powershell
.\.venv\Scripts\python.exe -m experiments.readable_cases --cases data/agent_holdout_natural_52.json --out runs/agent_holdout_questions.md
~~~

Le runner possède aussi un mode hors ligne. Il a été exécuté avec un petit catalogue SQLite de test : 52 cas visités, **zéro appel Azure ou ORS**. Neuf contrôles locaux sont réussis ; 35 cas attendent le modèle et quatre attendent ORS. Quatre cas révèlent immédiatement une limite déterministe du routage linguistique : `H-T01` (« marcher »), `H-T06` (« je pars en voiture »), `H-P01` (« pas loin de moi ») et `H-P03` (« à côté de moi ») sont envoyés vers le mauvais chemin de traitement avant d'appeler un service. Il serait trompeur de compter ce bilan hors ligne comme 9 réussites sur 52. **Conserver ces quatre cas dans le panel** pour mesurer le défaut et vérifier une correction ultérieure sur un jeu distinct.

Pour confirmer localement les limites avec le vrai catalogue, toujours sans Azure ou ORS :

~~~powershell
$offline = "runs/agent_holdout_offline_$(Get-Date -Format yyyyMMddTHHmmss)"
.\.venv\Scripts\python.exe -m experiments.audit_campaign --cases data/agent_holdout_natural_52.json --db local_data/lieux.sqlite --out $offline
Get-Content "$offline/report.json"
~~~

Après validation humaine du panel, exécuter **une seule fois** chaque cas en direct, avec `AGENTLAB_API_KEY` saisie masquée et `ORS_API_KEY` dans `.env` :

~~~powershell
$live = "runs/agent_holdout_live_$(Get-Date -Format yyyyMMddTHHmmss)"
.\.venv\Scripts\python.exe -m experiments.audit_campaign --live --cases data/agent_holdout_natural_52.json --db local_data/lieux.sqlite --private-review --out $live
.\.venv\Scripts\python.exe -m experiments.readable_review $live
~~~

Ensuite, si le coût et les erreurs fournisseurs le permettent, rejouer les 18 cas marqués, trois fois chacun (54 exécutions prévues) :

~~~powershell
$repeat = "runs/agent_holdout_repeat_$(Get-Date -Format yyyyMMddTHHmmss)"
.\.venv\Scripts\python.exe -m experiments.audit_campaign --live --consistency --cases data/agent_holdout_natural_52.json --db local_data/lieux.sqlite --private-review --out $repeat
.\.venv\Scripts\python.exe -m experiments.readable_review $repeat
~~~

Examiner séparément : erreurs du routage local, refus du garde d'entrée, contenu filtré par Azure, erreurs ORS et du modèle, puis justesse des citations et des limites dans les réponses. Ne pas agréger un cas non évalué comme un échec de l'agent. La revue humaine décide de la fidélité, de l'utilité et des refus excessifs. Les répétitions mesurent la variabilité des sorties dans ce cadre, pas la représentativité statistique.
