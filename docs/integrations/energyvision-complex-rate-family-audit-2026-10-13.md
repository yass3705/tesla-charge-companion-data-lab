# EnergyVision BE — audit des cinq structures tarifaires DATEX du 13 octobre 2026

Source authentifiée : GitHub Actions Data Lab [run 38435009280](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/38435009280), artefact `energyvision-datex-staging-38435009280`, fichier `artifacts/energyvision-datex-stage.json.gz`, empreinte statique `a412de196e0f92b71d2a5a0892b75fc9fbdb40cd9a06af917b86af5ac2a8423d`. Audit structurel reproductible du contenu, sans appel fournisseur supplémentaire ni nouveaux tarifs publiés.

## Répartition de toutes les 1 228 grilles station ad-hoc

| Nombre de grilles | Structure DATEX | Règles de prix |
|---:|---|---|
| 810 | 4 pricePerKWh + 1 pricePerMinute ; seuil 360 min, plage horaire sur plusieurs composants | 597 grilles à 0,38 €/kWh et 213 à 0,28 €/kWh ; minute supplémentaire 0,06 €/min uniquement avec fenêtre locale 09:00–21:59 et fromMinute 360 |
| 248 | 1 pricePerKWh sans condition | 0,28 / 0,38 / 0,39 / 0,48 / 0,61 €/kWh |
| 142 | 1 pricePerKWh + 1 basePrice + 1 pricePerMinute, fromMinute 1080 | 0,37 €/kWh + 2,04 €/session + 0,02 €/min après minute 1080 |
| 27 | 1 pricePerKWh + 1 pricePerMinute, fromMinute 45 | 0,61 €/kWh + 0,33 €/min après minute 45 |
| 1 | 1 pricePerKWh + 1 basePrice | 0,37 €/kWh + 2,04 €/session |

Les cinq catégories sont exclusives, somme 1 228. Les familles complexes sont exactement 810+142+27=979 grilles ; une partie des anciens compteurs (980) regroupait également la famille simple avec basePrice, selon la définition précédente. Ne pas additionner les catégories d'applicabilité.

## Exemples réels vérifiables, identification exacte

- **Brussel**, site `1f00efd4-b0b5-6de4-bf7c-02b5aad4a865`, EVSE `BE*NRG*EEDCC0014EVSE*1` / `*2` : 0,28 €/kWh toujours ; passé 360 min de durée de recharge, un composant 0,06 €/min conditionné à 09:00–21:59 est présent. Attention : trois composants kWh après 360 min, chacun dans une fenêtre complémentaire 09:00–21:59, 22:00–23:59 ou 00:00–08:59 ; ce ne sont pas trois prix cumulables sur la même période. L'application et les bornes de créneaux au passage 21:59/22:00 doivent être confrontées au tarif consommateur.
- **Aalter**, site `1f0fc1ea-3ce8-68ac-8584-02b5aad4a865`, EVSE `BE*NRG*E05116*1` / `*2` : 0,37 €/kWh + 2,04 €/session + composant 0,02 €/min à partir de 1 080 min ; sans preuve supplémentaire on ne sait pas si la minute est facturée en durée de recharge ou interprétée comme stationnement.
- **Aalter**, site `1f0ed32a-76cd-6aa4-9c1a-06f945fc8557`, EVSE `BE*NRG*E09261*1` / `*2` : 0,61 €/kWh + 0,33 €/min à partir de 45 min. L'identité de la grille est vérifiée, mais l'applicabilité effective au consommateur et la sémantique de la minute exigent une confrontation au checkout.
- **Zingem**, site `1f159977-4329-676a-8f72-06f945fc8557`, EVSE `BE*NRG*E05095*1` / `*2` : 0,37 €/kWh + 2,04 €/session, sans seuil ni fenêtre ; même famille déjà supportée dans le candidat Production.

## Décisions simulation utilisateur

- Les pénalités d'occupation après la fin de charge ne sont appliquées **que si l'utilisateur fixe explicitement un horaire de départ/fin permettant de mesurer l'occupation après recharge**. Sinon débranchement immédiat par défaut et zéro occupation. Cette règle ne permet pas de requalifier sans preuve toutes les composantes DATEX `pricePerMinute` comme frais d'occupation ; leur nature doit être attribuée correctement avant de les faire dépendre de cette politique.
- Pour les plages horaires E55C, appliquer provisoirement le tarif local de chaque segment effectivement traversé (cas B) jusqu'à preuve contraire, marquer la convention comme provisoire.
- Pour EnergyVision, le schéma DATEX officiel décrit `timeBasedApplicability` comme bornes de durée de recharge en minutes, mais ne prouve ni arrondis, ni déroulement du paiement, ni définition des frais post-charge. **Ne pas transformer ces structures en prix numériques V9 sans tests de scénarios et preuve de sémantique.**

## Statut d'intégration

Détection et inventaire des 979 grilles conditionnelles : **effectués**. Aucune nouvelle offre complexe n'est promue ou publiée par cet audit. Les 778 offres Direct déjà validées dans le candidat restent inchangées. Étape requise : valider trois parcours utilisateur (un par famille conditionnelle), implémenter les segments avec oracles puis CI complète avant intégration Production. Aucun déploiement Pages/Cloudflare.
