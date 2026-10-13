# EnergyVision BE — résultat de rapprochement DATEX vs Belgium NAP — 13/10/2026

## Sources vérifiées
- EnergyVision DATEX staging authentifié [#38419429972](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/38419429972), artefact temporaire de sept jours, source sans secret.
- Belgium NAP épinglé dans `data/belgium/nap-belgium-manifest.json` : **17 pages**, 16 961 localisations déclarées dans le manifeste.
- Script de diagnostic `scripts/energyvision_datex_nap_audit.py` intégré par [PR #258](https://github.com/yass3705/tesla-charge-companion-data-lab/pull/258) ; contrôle CI sur `main` [#38431651109](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/38431651109), **success**. Aucun tarif publié.

## Identités
- EnergyVision : **3 791 connecteurs** distincts, aucun ID externe dupliqué ; tous les identifiants externes portent un préfixe `BE*NRG`.
- Référentiel NAP : **70 655 connecteurs**, **70 349 couples station/EVSE distincts** représentés par au moins un connecteur, répartis sur **16 902 localisations comportant au moins un connecteur**. Le manifeste national compte 16 961 localisations au total (certaines dépourvues de connecteur), d'où les deux chiffres différents.
- **Zéro correspondance** pour les 3 791 identifiants EnergyVision, après exact puis normalisation alphanumérique univoque. Tous sont classés `unmatchedIds` et aucun tarif n'est joint. Cet audit ne démontre pas l'inexistence physique : couverture NAP sélectionnée ou format/identité du CPO à établir indépendamment.
- Aucune jointure GPS seule ou par nom CPO/puissance n'est autorisée. Les futurs candidats exigent identité univoque, connecteur, puissance et GPS cohérents.

## Grilles collectées : taxonomie non tarifée
- **1 226 grilles ad-hoc station**, 10 stations sans grille.
- **246** grilles simples avec une seule composante kWh et sans seuil/horaire ; **980** nécessitent une revue des composantes, dont **810** avec fenêtre horaire et **979** avec seuil de minutes (catégories qui se chevauchent).
- Familles : 246 `pricePerKWh`; 837 `pricePerKWh+pricePerMinute`; 142 `basePrice+pricePerKWh+pricePerMinute`; 1 `basePrice+pricePerKWh`. Les données DATEX déclarent EUR/TTC avec TVA 21%, mais ce n'est pas une attribution prouvée à chaque PDC.
- `sourceLastUpdated` des grilles varie de 2025-03 à 2026-05 ; date de collecte récente **ne vaut pas** date d'actualisation tarifaire.

## Suite sûre
1. Vérifier si EnergyVision/Nrg est absent du périmètre des CPO sélectionnés par NAP. Interroger les preuves officielles et le propriétaire des flux, **sans** fabriquer de correspondances GPS.
2. Vérifier la déclaration d'accès public, les statuts et l'application station/PDC des tarifs DATEX ; assurer une non-duplication lors de l'ajout éventuel d'un inventaire CPO supplémentaire.
3. Confirmer la sémantique `fromMinute`, `toMinute`, fenêtres horaires et composantes cumulatives par source contractuelle ou oracle indépendant (incluant DST).
4. Construire un supplément EnergyVision indépendant seulement si les conditions précédentes sont prouvées ; séparer les cas tarifés valides des ambiguïtés, puis candidats Production épinglés.
5. Garder `v9PricePublicationReady=false`. **Aucun changement de pin V9, Pages ou Cloudflare.**

## Piste parallèle Electric 55 Charging
Le [tutoriel officiel](https://www.e55c.com/tutoriel-de-recharge/) confirme l'affichage du prix ad-hoc avant paiement, avec sélection de la station et du numéro exact de borne. Le domaine utilisateur `https://e55c.evse-portal.com/` a été sollicité, mais les tentatives de lecture directe n'ont pas fourni de page exploitable. La capture du prépaiement Place Lully / allée des Chevreuils avec EVSE et composants tarifaires reste à obtenir ; ne pas convertir les taux de gros E55C en tarifs directs consommateurs.
