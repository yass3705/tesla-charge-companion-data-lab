# Benchmark hors ligne du prototype (15 octobre 2026)

Commande : `node experiments/electroverse-v2/benchmark.mjs` depuis la racine Data Lab. Code et fixture issus de `origin/main=2d4a0ebeb746bfad79a507afa333378d2790307c`. Mesures brutes : [benchmark.json](benchmark.json). Cinq répétitions par mode sur le même Mac/Node, médiane pour temps/CPU/requêtes/octets/écritures. V1 est un **modèle local du chemin batch heureux** (5 alias, fallback par station, écriture finale), pas une exécution du script canonique. Les réponses sont fournies en mémoire par la même fixture, sans latence ni quota API. RSS observé dans un même processus, donc non comparable comme pic indépendant.

Fixture : 24 stations publiques archivées dans `shard-000.json`, 113 EVSE, 150 connecteurs, 24 mappings IRVE. Exactement les mêmes en entrée V1 et V2. Les composants bruts et restrictions sont conservés à l'identique.

| Mesure simulée | V1 modèle | V2 prototype | Lecture |
|---|---:|---:|---|
| Couverture finale | 24/24 | 24/24 | Équivalente sur cette fixture. |
| Requêtes sans incident | 5 | 5 | **Aucun gain** normal. |
| Octets de réponse simulés | 178 250 | 178 250 | Aucun gain. |
| Durée locale médiane | 9,354 ms | 23,851 ms | V2 **plus lent**, surtout écritures atomiques. |
| CPU local médian | 7,764 ms | 20,300 ms | V2 plus coûteux sur petit échantillon. |
| Écritures logiques | 1 | 10 | Coût explicite de la reprise fine. |
| RSS observé maximal | 46,83 MB | 47,40 MB | Même processus, pas des pics comparables. |

**Interruption simulée après 2 lots sur 5 :** V1 modèle 2 requêtes avant arrêt + 5 au redémarrage = **7** ; V2 2 avant arrêt + 3 au redémarrage = **5**, soit 2 requêtes évitées (**28,6 % dans ce seul scénario**). Couverture finale 24/24 dans les deux cas. Le gain est dû au checkpoint et ne doit pas être extrapolé aux 22 818 stations, aux minutes Actions ni au réseau réel.

Les chiffres historiques du collecteur réel restent séparés : benchmark du 28/09 à 1 000 stations = 312 requêtes et 1 188,62 s, 1 000/1 000 couverts ; dernier bloc hebdomadaire du 11/10 = 2 148 requêtes et 6 232,79 s pour 4 818 lieux ; delta du 15/10 = 568 tuiles et 0 station tarifaire sélectionnée. Ces jeux, dates et conditions ne sont pas comparables numériquement au prototype de 24 stations.

**Conclusion performance :** aucun argument pour remplacer V1 aujourd'hui. L'amélioration démontrée est la reprise après coupure ; son coût CPU/I/O doit être résolu avant une expérimentation nationale. Les minutes Actions, octets HTTP réels et efficacité multi-pays restent non mesurés.
