# Diagnostic des quatre appels manqués

Sur le rapport partiel externe au seuil 0,48, les cas `anglais_1.2`, `anglais_1.5`, `anglais_3.5` et `arabe_1.2` ont été étiquetés comme urgences et n'ont été repérés ni par le classifieur de caractères ni par la règle lexicale. Les textes transmis par le relecteur décrivent de la fumée sortant d'un bâtiment ou une collision frontale violente. Le filtre lexical initial ne couvre pas ces formulations.

La règle lexicale reconnaît maintenant ces quatre formulations actuelles, et trois questions informatives proches restent autorisées dans les tests. L'appel est interrompu **avant** l'agent pour les quatre exemples. Ceci est une correction issue de cas déjà consultés : leur nouveau score ne mesure pas une généralisation. Le panel externe doit dorénavant être traité comme jeu de développement pour cette règle ; une nouvelle évaluation indépendante doit inclure des urgences moins explicites et des questions bénignes sur les mêmes thèmes.

Ce correctif ne remplace pas le classifieur ni un garde d'urgence fiable. Le rapport reçu contenait 26 urgences, une demande bénigne et une exclusion ; il ne permet pas d'estimer le taux de blocage des demandes bénignes sur l'ensemble des 77 appels.
