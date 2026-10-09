# TCC — inventaire tarifaire global et déploiement progressif du calcul

Date de cadrage : 2026-10-09. **Audit en lecture seule**, sans remplacer le moteur V9 qui fonctionne ni déployer des prix erronés.

## Objectif

Identifier et classer **tous les schémas de facturation**, **Tesla inclus**, dans les sources Data Lab et les catalogues de production des neuf pays TCC : **FR, IT, CH, DE, ES, NL, UK, MA, BE**. Tester d'abord en France avec les offres eMSP publiées et les offres CPO/abonnements réellement compilées, puis étendre les tests nationaux selon la maturité des données. Ne jamais confondre inventaire des *formats* et nombre d'EVSE avec prix validé.

## Périmètre des composants de calcul

| Famille | Données à examiner | Risques |
|---|---|---|
| Énergie | EUR/CHF/GBP/MAD/kWh, paliers, gratuité, arrondi kWh/Wh | mauvais tarif par puissance ou énergie facturée |
| Minutes | durée de charge, connecté, parking, idle | double décompte ou durée non disponible |
| Frais fixes | session, connexion, réservation, minimum et frais conditionnels | frais facturés plusieurs fois |
| Grilles progressives | tranches OCPI, franchise, plafonnement, après seuil, blocs entamés | plafond/arrondi implicite non prouvé |
| Temps & calendrier | fenêtres horaires, jour/semaine, promotions, changement de créneau | répartitions incompatibles des composantes |
| SOC et congestion | seuil explicite ; 80 % par défaut seulement lorsque frais existent | charge dépassant 80 % sans contexte SOC |
| Power & plugs | AC/DC, classes de puissance, groupe homogène ou variante EVSE | attribution d'une règle au mauvais connecteur |
| Abonnement | mensualité séparée, remise, réseau éligible, cartes et eMSP | montant fixe réparti sans consentement |
| Taxe/monnaie | TVA incluse ou exclue, CHF/GBP/MAD, FX | fausses comparaisons transdevises |
| Qualité & provenance | Direct CPO vs eMSP vs candidat/stock brut vs production | tarif de candidat traité comme disponible |

## Référentiels de base

- France : `reports/france/tariff-coverage/` et SOP `docs/france-irve-tariff-coverage-frozen-sop-v1.md` (**P1 identifiant / P2 overlays / P3 GPS validé**).
- Tesla : catalogue global canonique `tesla-charge-companion-stable/data/tesla_stations.json` (configs de charge, règles par pays, puissance délivrée, tarif minute/kWh, MAD/EUR/CHF/GBP, créneaux, congestion). Le snapshot `data/suc-tracker/` du Data Lab est une source de comparaison distincte (jamais substituée au Maroc), pas un tarif CPO certifié.
- Formats des sources : `data/operator_direct/`, `data/national/`, `data/switzerland/`, `data/spain_reve/`, `data/belgium/`, `data/platforms/electra/france/`, `data/platforms/electroverse/france-evse/`, `v9-production-runtime/data/v9/` et autres sources explicitement listées dans l'inventaire.
- Moteur de référence, inchangé : `tesla-charge-companion-stable/v9-production-runtime/assets/v9/pricing-engine.js` épinglé au commit `38ac26e029ba1c4779d4d8fa43e7d5d300858624`.

## Méthode

1. **Inventaire global** : détecter pays, source, état de publication, structure JSON, composants facturables, règles de granularité et familles. Les fichiers de données gigantesques, échantillonnés ou non lisibles sont déclarés explicitement : leur couverture n'est pas extrapolée.
2. **Pilote France** : exécuter des régressions déterministes (tarif à l'énergie, minutes, frais, SOC, fenêtres, OCPI...) puis appliquer le moteur **sans modifications** à un échantillon de vrais `emspOffers` Electra/Electroverse et de `directOffers/subscriptionOffers` V9.
3. **Classification des résultats** : `computed`, `incomplete`, `ambiguous`, `unavailable`; raisons exactes. Tests sur différentes heures, durées, SOC et puissances au fil des itérations.
4. **Corrections minimales** : conserver tous les cas conformes; modifier uniquement les familles présentant des écarts avérés avec des règles documentées. Jamais de prix inventé.
5. **Déploiement par pays** après tests :
   - Lot A **France** (validation intégrale).
   - Lot B **Suisse + Italie**, avec abonnements, CHF et profils multi-puissances.
   - Lot C **Royaume-Uni + Pays-Bas + Espagne**, avec PCPR/OCPI, GBP, tarifs de roaming, DOT-NL et REVE.
   - Lot D **Allemagne + Maroc + Belgique**, avec par minute, règles composites, données partielles et restrictions d'accès.
   Cet ordre est provisoire et doit être ajusté aux preuves de l'inventaire réel.

## Règles de qualité

- **Une ligne par (EVSE, puissance, type de connecteur, source, offre, abonnement)** ; une station peut avoir plusieurs prix distincts.
- Offres CPO direct/ad-hoc et eMSP **toujours séparées**, ne pas appliquer un eMSP d'un autre opérateur au tarif CPO.
- Aucun tarif sans source exacte, statut public vérifié et correspondance P1/P2/P3 validée ne doit devenir classable.
- Les frais de congestion suivent le contrat de source ; seuil implicite SOC 80 % uniquement pour un **vrai composant congestion** sans seuil explicite, avec option par ligne.
- Tous les paramètres nécessaires doivent être disponibles ou la simulation doit être `incomplete`, jamais un nombre fictif.
- Les variantes/sous-tarifs sont conservés dans les archives de scénarios.
- Le pilote ne remplace ni l'audit quotidien IRVE ni la publication V9 : fonctionnalités et publications restent indépendantes.

## Artefacts et exécution

- `scripts/tariff_global_inventory_20261009.py` : inventaire de formes et exemples tarifaires eMSP réels.
- `scripts/france_runtime_offer_fixtures_20261009.py` : offres françaises directes et abonnements des catalogues V9 épinglés.
- `scripts/france_pricing_real_offer_pilot_20261009.cjs` : regressions + test de vrais exemples.
- `.github/workflows/global-tariff-inventory-france-pilot-20261009.yml` : pipeline expérimental.
- `reports/tariff-scenarios/` : inventaire, fixtures et statistiques par cause de calcul incomplet.

**Statut à ce stade :** inventaire/pilote en cours de vérification CI ; ne pas déclarer exhaustive une source structurée qui ne l'est pas.

## Correctif de périmètre — Tesla / 9 pays (2026-10-09)

Le premier rapport de 1 308 fichiers **n'incluait pas le catalogue Tesla global du dépôt `stable`** : les neuf pays désignaient seulement des répertoires non-Tesla parcourus. Cette lacune était contraire à la demande d'audit de *toutes* les bases. La correction est intégrée au workflow `global-tariff-scenario-review.yml` : téléchargement du catalogue Tesla actuel avec empreinte SHA256, décompte distinct par pays des stations/configurations/règles et audit des vrais exemples via l'adaptateur et le moteur V9 **épinglés au même commit**. Le snapshot SuC-Tracker est recensé séparément comme comparaison. Aucune base tarifaire V9 n'est modifiée.

Le suivi garde **trois dimensions différentes** : fichiers de sources non-Tesla, configurations/règles Tesla, et offres réellement simulées. La réussite d'un pipeline n'atteste pas que tous les tarifs soient calculables : `powerMinute` doit tenir compte de la **puissance effectivement délivrée au fil du temps** ; les devises sources et règles de congestion doivent être conservées ; les champs non modélisés restent signalés. Les traitements par pays sont à exécuter ensuite pour couvrir chaque variante réelle, sans extrapolation ni publication anticipée.
