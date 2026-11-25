# Revue humaine de fidélité au corpus RAG

`data/rag_faithfulness_human_18.json` contient 18 questions naturelles, trois par famille : Comoé, Taï, Nimba, Grand-Bassam, mosquées soudanaises et PIB. Chaque famille combine un fait directement présent dans le passage, une question causale dont le mécanisme manque ou est documenté, et une question de portée ou de transfert entre sources. Les questions n'embarquent aucun attendu. Le jeu et ses repères ont été rédigés en connaissant le petit corpus local : il s'agit d'un **panel de développement**, sans annotation indépendante ni estimation représentative.

Les `review_guide` sont des annotations privées : un fait établi par un passage et des détails absents de ce passage, **pas nécessairement faux**. Ils ne sont pas transmis à Azure. Le Markdown de revue les affiche après les réponses et les preuves, avec deux cases de contrôle ciblées. Évaluer chaque affirmation factuelle : une citation d'ID exact ne rend pas automatiquement fidèle un mécanisme écologique, une causalité économique ou un comportement transposé à un autre site. Les cas positifs vérifient aussi le risque de refuser abusivement une information réellement présente, notamment l'adaptation des mosquées au climat plus humide.

Depuis la racine du dépôt sous PowerShell, après fusion de la PR qui ajoute le panel :

```powershell
git switch master
git pull
$run = "runs/rag_faithfulness_$(Get-Date -Format yyyyMMddTHHmmssfff)"
.\.venv\Scripts\python.exe -m experiments.audit_campaign --live --cases data/rag_faithfulness_human_18.json --db local_data/lieux.sqlite --private-review --out $run
if (Test-Path "$run/review.private.json") {
    .\.venv\Scripts\python.exe -m experiments.readable_review $run
}
```

La campagne demande au plus 90 tentatives Azure selon le plafond du runner, retries compris ; le nombre réel est en général inférieur et le coût n'est pas estimé sans tarif configuré. Aucune question n'autorise ORS. Pour commencer par trois cas sans modifier le panel, ajouter `--category comoe` à la commande `audit_campaign` ; cela produit un rapport de sous-ensemble, distinct du résultat global. Les six cas marqués pour répétition sont destinés à un test ultérieur, après relecture de la première passe.

Ouvrir `review.readable.private.md`. Pour chaque cas, comparer la réponse aux passages cités, cocher les points ciblés puis les cinq dimensions habituelles et noter précisément la phrase non étayée, le passage invoqué et si le modèle l'attribue à la source ou le présente comme une généralité. Pour une question sans réponse dans la source, une limite clairement expliquée est préférable à une explication plausible mais invérifiable par le corpus. `report.json` ne contient pas ces textes ni annotations ; garder la revue Markdown et `review.private.json` en privé. Les cases du Markdown ne remplissent pas automatiquement `grades.private.json`.
