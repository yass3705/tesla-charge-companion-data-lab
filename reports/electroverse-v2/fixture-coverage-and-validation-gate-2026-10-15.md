# V2 Electroverse — vérification de corpus et gate de validation (15/10/2026)

## Vérifications effectuées par lecture seule
État PR #331 : Draft, SHA `02f2d6c29ddec6e8dbbbd24d520bb476d6452458` au début de la passe. Recherche des GitHub Actions de la branche R&D : **0 workflow run** retourné. Aucun test d'intégration exécuté ou confirmé par CI.

Analyse effective de la fixture archivée `experiments/electroverse-v2/fixtures/archived-24.json` :
- **24 stations, 113 EVSE, 150 connecteurs** ;
- **142 connecteurs** portent `complexPricingDetail`, sur **22 stations** ;
- **92 occurrences** de restrictions `TIME_BASED` et **65 occurrences** `DURATION_BASED` ;
- cinq types de composantes présents sur chacun des 150 connecteurs : `ConsumptionRate`, `TimeRate`, `VAT`, `ParkingTimeRate`, `ConnectionFee` ;
- **0 connecteur gratuit** : le test gratuit actuel est synthétique, pas un cas réel archivé dans cette fixture.

Ce comptage est fait à partir des valeurs JSON déjà archivées et **n'est pas un benchmark ni une preuve de parité d'exécution**. Les restrictions sont comptées par occurrence ; elles ne représentent pas nécessairement des règles indépendantes.

## Bloqueur
L'environnement d'exécution local ne résout pas `github.com`. Le connecteur GitHub permet de lire les sources mais pas de transférer un checkout Node exécutable au conteneur. Le benchmark trois voies et les suites intégrées restent donc **non exécutés sur le SHA de la PR**.

## Prochain gate unique (ne pas ajouter de fonctionnalités en amont)
Dans un environnement disposant du checkout de la branche :

```sh
node --test experiments/electroverse-v2/*.test.mjs experiments/electroverse-v2/test/*.test.mjs
node experiments/electroverse-v2/benchmark-three-way.mjs
```

Vérifier le code de sortie, la parité exacte, les chiffres de reprise, puis enregistrer dans la PR les résultats et versions Node avec SHA. Ne jamais convertir des assertions des tests en résultats avant leur exécution. Élargir ensuite la couverture réelle des connecteurs gratuits et des autres types de restrictions absents. Le test à trois voies reste un modèle V1, pas le collecteur canonique.

**Isolation impérative :** aucun workflow planifié, collecteur existant, cache canonique, secret, PR #219 ou Production modifié. PR #331 en Draft.
