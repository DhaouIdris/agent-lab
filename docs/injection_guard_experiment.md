# Détecteur expérimental d'instructions injectées

Le RAG documentaire inspecte les titres et textes des passages retrouvés avant l'appel au modèle. Si l'un correspond au détecteur lexical, il arrête la requête entière avec `guard_status=blocked_suspected_injection` ; aucune génération n'a lieu. Les résultats de la recherche sont des données non fiables. Un passage suspect même non pertinent parmi les k passages interrompt la requête. Ce contrôle est propre au prototype RAG documentaire ; il n'est pas branché sur le moteur agentique ni sur d'autres outils.

Le détecteur est une liste expérimentale d'expressions régulières, non un classificateur robuste ni une barrière de sécurité. Il ne détecte pas toutes les injections, variantes, langues, obfuscations ou combinaisons. Un texte bénin peut aussi être bloqué. En particulier, l'absence d'alerte ne rend pas un document fiable. Ne pas utiliser comme protection de production. Les véritables autorisations d'outils, la protection des secrets et le contrôle des effets doivent rester externes au modèle. Aucun secret ne doit être inclus dans les documents ou prompts.

Le rapport de lot distingue `blocked_suspected_injection` de `model_output`. Un blocage local n'est ni une réussite ni un échec du modèle : `behavior_match` vaut null. Il peut néanmoins être évalué séparément par rapport à une annotation humaine. Les erreurs de fournisseur restent des erreurs ; aucune classification implicite de leur légitimité n'est faite. Les comptes de recherche sur les erreurs fournisseur conservent une limitation connue.

## Batterie locale

```powershell
.\.venv\Scripts\python.exe -m experiments.eval_injection_guard
```

80 textes courts synthétiques, 40 malveillants et 40 bénins, étiquetés par l'auteur de cette règle en connaissance de sa conception. Ils incluent volontairement des évasions connues. Le résultat donne TP, FN, FP et TN ainsi que les identifiants par cas ; il ne mesure ni le modèle ni un taux réel en production. Des exemples bénins peuvent contenir des instructions légitimes de visite : la distinction reste approximative. Ne pas ajuster le détecteur sur ce jeu avant de constituer une évaluation indépendante, réaliste et annotée. Ajouter ensuite des documents complets, des variations multilingues, des faux positifs et des tests sur les autres points d'entrée.

Le passage `SYN_PANNEAU` est renvoyé dans les trois premiers résultats aussi bien pour RS01 que pour RS02. Le choix conservateur bloque donc les deux scénarios même si RS01 porte sur un autre document. Tester RS01 seul exige un corpus séparé ne contenant pas ce passage, sans présenter ce retrait comme une protection.
