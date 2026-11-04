# Electroverse V2 — itération sur le journal (15 octobre 2026)

## Réalisation
Deux fichiers nouveaux dans `experiments/electroverse-v2/` :
- `journal_runner.mjs` : simulation hors ligne sur les fixtures déjà archivées, en réutilisant le transport synthétique et les validateurs de V2, mais en enregistrant les lots via `generation_store.mjs`.
- `journal_runner.test.mjs` : 3 scénarios (équivalence brute V2 sur les 24 stations, interruption après 2 lots, refus d'un lot incomplet et reprise).

Le runner refuse les lots incomplets avant tout commit, conserve les PK et hashes vérifiés et ne peut écrire que sous un chemin temporaire `electroverse-v2-*` déjà contrôlé par le journal. Aucun client HTTP n'est importé.

## Hypothèses à vérifier à l'exécution
Sur la fixture de 24 stations / 5 batches : **5 segments** par rapport aux **10 écritures logiques** de V2 initial, sans interruption. Avec interruption après le deuxième lot : seuls les trois lots restants devraient être demandés à la reprise, total théorique **5 requêtes de batch**. Ce sont des **assertions de tests, pas encore des résultats observés**.

## État de validation honnête
Les nouveaux tests sont écrits, mais **non exécutés dans cette session** : l'environnement d'exécution local ne parvient pas à résoudre `raw.githubusercontent.com` pour récupérer ses dépendances historiques et la fixture GitHub. Ils doivent donc être vérifiés sur le checkout complet :

```bash
node --test experiments/electroverse-v2/generation_store.test.mjs experiments/electroverse-v2/journal_runner.test.mjs experiments/electroverse-v2/test/model.test.mjs
```

Un benchmark propre ensuite doit exécuter V1-modèle, V2, et V2-journal dans le même environnement et comparer durée, CPU, octets écrits, nombre de segments et comportement aux interruptions. **Aucune mesure de durée ni parité nationale n'est affirmée.**

## Périmètre
Tous les changements restent strictement dans `experiments/electroverse-v2/` et `reports/electroverse-v2/`. Aucune collecte Electroverse, aucune modification de `main`, des workflows, secrets, caches, overlay ou Production. La PR #331 demeure Draft. V1 reste la référence opérationnelle.
