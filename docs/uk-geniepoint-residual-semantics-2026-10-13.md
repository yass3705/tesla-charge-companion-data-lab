# GeniePoint UK — diagnostic des 857 prises sans prix candidat

## Reproduction sur la source épinglée

Lecture seule de `data/national/uk_geniepoint_official_ocpi.json.gz` au pin national Data Lab `e39a4466096b520b3c459e75539bf9b112235165`, SHA-256 `40c6a494a59f0b946614d2ef80920b9211d9bc7276dd9ac496a4744701106687`, avec la même sélection d'offre que `compile_uk_direct_batch.py` en Production `f08c5d60`. La source porte 306 sites, 1 138 connecteurs, 530 objets tarifaires et 91 IDs tarifaires référencés. Le candidat a **281 prix directs exacts**. Les **857** autres se décomposent ainsi :

| Motif | Connecteurs | État |
| --- | ---: | --- |
| Aucun `tariff_ids` sur le connecteur | 5 | Prix non disponible ; demander l'ID au CPO. |
| Offre sélectionnée avec `PARKING_TIME` non nul et second élément `min_duration` | 852 | Tarif applicable, mais montant complet non certifiable sans la sémantique de seuil et d'arrondi GeniePoint. |

Les 852 connecteurs utilisent **55 objets tarifaires distincts**. Le second élément se répartit ainsi (montants source **hors TVA**, non présentés comme prix finaux) :

| `min_duration` = `step_size` | Composante `PARKING_TIME` source | Connecteurs |
| ---: | ---: | ---: |
| 5 400 s | 5,56 GBP/h | 648 |
| 14 400 s | 2,08 GBP/h | 166 |
| 86 400 s | 0,35 GBP/h | 34 |
| 10 800 s | 1,39 GBP/h | 4 |

Parmi ces 852 connecteurs, 645 ont l'état `AVAILABLE` et 49 `CHARGING` ; 105 sont `OUTOFORDER`, 27 `BLOCKED`, 20 `INOPERATIVE` et six `UNKNOWN`. L'inventaire et le statut restent distincts du droit d'afficher un prix. Aucun montant historique ou ENERGY seul n'est promu pour ignorer le frais de stationnement.

## Règle à confirmer avant correction

La [spécification OCPI 2.2.1 officielle](https://evroaming.org/ocpi-downloads/) définit le composant `PARKING_TIME` et les restrictions de durée, mais l'[issue OCPI #225](https://github.com/ocpi/ocpi/issues/225) laisse explicitement ouverte l'interprétation d'un `min_duration` associé à `PARKING_TIME` : seuil depuis le début de session, cumul des seules minutes sans charge ou temps après la fin de la dernière charge. Il faut aussi confirmer si le `step_size` facture la première tranche entière au franchissement du seuil, puis chaque tranche commencée, et comment le seuil interagit avec une charge qui dépasse déjà la durée indiquée. Appliquer l'une de ces interprétations à 852 prises sans confirmation créerait potentiellement des faux prix.

**Demande précise au support GeniePoint :** fournir un devis ou CDR détaillé pour chacun des quatre seuils avec (a) charge seule au-delà du seuil, (b) charge plus 1 minute de stationnement avant et après le seuil, (c) 1 minute puis une tranche entière de stationnement après charge ; préciser la base temporelle du `min_duration`, le calcul et l'arrondi de `step_size`, le montant TTC, et les cinq IDs tarifaires absents. Une seule réponse contractuelle applicable aux 55 grilles permettrait un correctif moteur/compilateur et des tests d'oracle ; les autres preuves restent nécessaires pour les cinq connecteurs sans ID.

Le nouveau pin BUMP `2026-10-13-fr-bump-active-supplement-candidate` ne modifie pas la source GeniePoint ni ses 281/1 138 prix directs. Le site Pages public conserve un snapshot antérieur.
