# Comparaison synthétique V2 vs journal — 15 octobre 2026

## Résultat exécuté hors ligne

Une expérience locale sur **2 000 stations synthétiques**, 400 lots de 5, Node 22.16.0, a comparé :
- une simulation d'écriture V2 qui réécrit à chaque lot un fichier JSON cumulatif `last-good.json` et un petit checkpoint JSON ;
- le vrai module expérimental `generation_store.mjs`, avec un segment immuable par lot et reconstruction finale.

Résultats d'**une seule passe** :

| Indicateur | Simulation réécriture V2 | Journal V2 |
|---|---:|---:|
| Écritures logiques | 800 | 400 |
| Octets de JSON cumulativement sérialisés | 84 118 456 | 465 050 |
| Durée de la phase écriture locale | 614 ms | 184 ms |
| Reconstruction supplémentaire du journal | N/A | 61 ms |
| Stations recouvrées | 2 000 attendues (pas de relecture instrumentée) | 2 000 vérifiées |

La simulation V2 **n'est pas l'exécution du runner canonique ni du runner V2 complet**. Les enregistrements synthétiques sont simples et identiques de structure, sans restrictions riches, erreurs API, opérations hash de tarifs, ni appels réseau. La simulation V2 emploie `fs.writeFile` sans l'atomicité réelle du V2 (`atomic`+rename), de sorte que les temps ne sont **pas comparables en conditions strictement identiques**. Les temps dépendent aussi des caches OS. Les volumes démontrent surtout l'amplification asymptotique de la réécriture cumulative et ne peuvent être transposés au national.

## Architecture : limitation importante constatée

Le runner `journal_runner.mjs` construit actuellement son `sourceHash` à partir des `tariffHash` contenus dans **toute** la fixture. Si un seul tarif change entre deux exécutions, la reprise des segments de la version précédente est refusée pour la nouvelle source. Cette protection est pertinente pour éviter des mélanges d'époques **mais ne constitue pas une stratégie de mise à jour incrémentale inter-runs**. Un futur prototype doit dissocier identité/version du jeu de travail, génération de collecte, et empreinte des prix, avec compaction et validation de changement de génération. Aucune réutilisation automatique de données anciennes ne doit être faite sans preuve de fraîcheur.

## Gate avant suite

- Exécuter la suite Node intégrée et le benchmark à trois voies sur checkout complet.
- Ajouter une variante réelle du simulateur avec mesures *cumulées* des écritures, atomicité identique, échantillon de tarifs réels riche et scénarios de relance quand la source change.
- Ne pas promouvoir ce résultat synthétique en preuve de gain de collecte, quota API, temps GitHub Actions ou parité nationale.

**Isolation** : aucun appel Electroverse, aucun changement V1, production ou workflows. PR #331 doit rester Draft.
