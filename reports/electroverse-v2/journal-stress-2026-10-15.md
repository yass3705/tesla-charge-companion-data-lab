# Stress test du journal V2 — 15/10/2026

## Exécution effective
Commande `node /mnt/data/electroverse-v2-local/journal-stress.mjs` avec Node.js v22.16.0, sur une copie locale du module `generation_store.mjs`. Test entièrement **synthétique et hors ligne** : 5 000 enregistrements simples dans 1 000 lots de 5, un seul prix de consommation par connecteur. Aucun appel à Electroverse, aucun accès aux caches ou workflows canoniques.

Résultat d'une seule exécution :
- 5 000/5 000 enregistrements restaurés, 1 000/1 000 lots retrouvés ;
- 1 174 450 octets de payloads JSON sérialisés (mesure de longueur renvoyée par le module) ;
- 491 ms pour les créations de segments ;
- 139 ms pour la reconstruction intégrale.

La copie locale du test a été incorporée sous `experiments/electroverse-v2/journal-stress.mjs` pour permettre la reproduction sur checkout GitHub. Ce rapport ne prétend **pas** avoir exécuté le script GitHub au SHA de la branche : l'accès réseau du conteneur vers GitHub reste indisponible. Ne pas considérer la durée comme un benchmark représentatif des 22 818 stations réelles : complexité du JSON très inférieure à celle des structures tariffaires, un seul run, système de fichiers local, aucun coût API ni GitHub Actions.

## Validation restante
Exécuter sur checkout complet les tests intégrés `journal_runner.test.mjs`, puis `benchmark-three-way.mjs`. Instrumenter ensuite les octets réellement écrits, CPU, peak RSS et panne pendant commit; échantillonner des shards archivés. Aucun changement V1, Production ou PR #219.
