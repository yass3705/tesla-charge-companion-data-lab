# Tesla Charge Companion — Data Lab

Dépôt dédié aux travaux de collecte, de contrôle et de validation des données de recharge destinées à Tesla Charge Companion.

Le principe est de séparer les expérimentations de données du dépôt applicatif stable afin de pouvoir tester les sources, comparer les opérateurs, produire des rapports de validation et ne publier que des données suffisamment vérifiées.

## Organisation

- `config/` : configuration des opérateurs, sources et règles de normalisation.
- `data/` : données collectées et jeux de données de travail.
- `izivia/` : travaux spécifiques IZIVIA.
- `reports/` : rapports et résultats de validation.
- `scripts/` : collecteurs, convertisseurs et outils de contrôle.
- `tests/` : tests automatiques.
- `.github/workflows/` : automatisation des collectes et validations.

## Méthode générale

Pour chaque opérateur :

1. identifier en priorité les sources officielles et techniques disponibles ;
2. distinguer clairement opérateur direct, application, abonnement, ad hoc et itinérance ;
3. relever les composantes tarifaires : prix au kWh, prix à la minute, frais de session, occupation et parking ;
4. conserver les puissances, connecteurs, horaires et règles particulières lorsque disponibles ;
5. contrôler plusieurs stations réelles ;
6. conserver explicitement les incertitudes au lieu de fabriquer ou extrapoler une valeur ;
7. publier vers Tesla Charge Companion seulement après validation.

## Règle de provenance tarifaire

Un prix provenant d'un eMSP ou d'un badge de roaming ne doit pas être publié comme tarif direct du CPO. Les données doivent conserver leur provenance et, lorsque c'est nécessaire, un niveau de confiance. Les tarifs abonnés ne doivent être pris en compte par l'application que lorsque l'abonnement correspondant est sélectionné par l'utilisateur.

## AVIA / Picoty

Le jeu national AVIA/Picoty repose sur le CPO Picoty identifié par le préfixe `FR*PY2`. `AVIA VOLT` est conservé comme marque commerciale.

Les couches tarifaires sont volontairement séparées :

- `direct_cpo` : paiement direct Picoty/AVIA VOLT ;
- `avia_carte` : offre AVIA Carte / Deft Power ;
- `roaming` : tarifs d'eMSP tiers.

Aucun tarif national n'est extrapolé tant qu'il n'est pas établi par une source suffisamment fiable. Les données de stations et d'EVSE peuvent en revanche être générées indépendamment via les identifiants Picoty afin de constituer la base nationale avant enrichissement tarifaire.
