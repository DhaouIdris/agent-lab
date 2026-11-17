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

## Comparaison locale de deux détecteurs

```powershell
.\.venv\Scripts\python.exe -m experiments.compare_injection_guards
```

Le programme compare le détecteur branché dans le RAG à une variante lexicale candidate uniquement évaluée hors ligne. Le second jeu `injection_guard_challenge.json` contient 24 nouveaux textes, 12 attaques et 12 textes bénins, distincts des 80 textes de développement. Il est rédigé par le même auteur avec connaissance du projet : ce n'est pas une annotation indépendante. Ne pas l'utiliser pour ajuster la candidate puis revendiquer une mesure indépendante. Les noms, empreintes et résultats par cas sont fournis ; les entrées ne sont pas recopiées dans le rapport.

Résultats expérimentaux : sur les 80 exemples de développement, baseline 27 TP / 13 FN / 0 FP / 40 TN ; variante candidate 32 / 8 / 0 / 40. Sur les 24 exemples séparés, baseline 0 / 12 / 1 / 11 ; variante 6 / 6 / 1 / 11. Le faux positif inclut une consigne de prudence légitime citant une instruction. Les règles ne garantissent pas la sûreté et le second échantillon ne mesure pas les performances réelles. Les deux jeux sont synthétiques. La candidate reste hors du chemin de production expérimental pour ne pas masquer ses erreurs.

Pour évaluer des exemples annotés indépendamment, enregistrer un JSON local respectant le même format et lancer :

```powershell
.\.venv\Scripts\python.exe -m experiments.compare_injection_guards --cases local_data/guard_cases.json
```

Utiliser des documents dont on a les droits, sans secrets ni données personnelles. Le script est local ; il ne teste aucun modèle spécialisé ni fournisseur Azure. Une future comparaison doit fixer à l'avance la configuration exacte du détecteur distant, ses coûts, ses refus fournisseur et les mêmes cas ; un refus d'Azure doit rester distinct d'une prédiction du détecteur.
