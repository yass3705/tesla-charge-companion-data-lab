# Electroverse France — réparation de la collecte des statuts (10 octobre 2026)

## Diagnostic établi
- Trois runs nationaux monolithiques ont échoué avec erreurs GraphQL génériques. Le dernier a validé 78 emplacements, échoué sur 26 puis arrêté les requêtes, sur 22 818 emplacements prévus.
- Le [diagnostic ciblé](../reports/electroverse/status-fallback-diagnostic-2026-10-10.json) a retrouvé **10/10** emplacements (dont huit précédemment en échec) par requêtes **individuelles paginées** et **batch à un alias**. Les erreurs ne constituent pas une preuve de suppression des stations ; la charge, la forme des requêtes ou le débit restent des hypothèses à surveiller.
- L'ancien balai national a été retiré de la planification. La reconstruction électroverse est désormais **fail-closed** si le registre national de statuts n'existe pas.

## Nouvelle chaîne de collecte
- Script : `scripts/electroverse_status_incremental.mjs` ; GitHub Actions : `.github/workflows/electroverse-status-incremental.yml`.
- 16 partitions déterministes sur les références `chargingLocation(pk)` du cache actuel, environ 1 426 emplacements par partition.
- Requêtes GraphQL avec **deux stations maximum par batch**, tentative individuelle en cas d'échec partiel, pagination et limitation des appels, temporisation et arrêt sur budget d'erreurs.
- Sauvegarde **d'une partition à la fois** dans `data/electroverse/live_statuses/parts/part-NN.json`. Les références déjà vérifiées ne sont plus interrogées après redémarrage au sein de la même période d'observation.
- Le code conserve la date réelle de début des observations ; un checkpoint antérieur à 16 h est rejeté puis réinterrogé, sans actualisation fictive des statuts.
- Un inventaire national `data/electroverse/live_statuses/manifest.json` + `evses.json.gz` **ne peut être généré** qu'après présence et validation de toutes les partitions, dates récentes et provenance identique au cache. La publication suivante reconstruit l'overlay et lance `scripts/audit_electroverse_status_gate_postbuild.mjs`.
- Horaires : 16 passages répartis sur la fenêtre nocturne en France, plus deux reprises supplémentaires ; action manuelle possible par partition dans GitHub Actions. Pas de revendication de couverture nationale avant résultat complet.

## Règles métier inchangées
- Electroverse `AVAILABLE` et `CHARGING` uniquement, **au niveau du PK EVSE source**.
- `UNKNOWN`, `OUTOFORDER`, `BLOCKED`, `MISSING` et autres : aucune offre tarifaire Electroverse attribuable à cette source.
- En cas de conflit entre plusieurs PK admissibles du même EVSE : **« Tarif ambigu »**, pas de coût forcé.
- Le CPO direct et les autres offres eMSP indépendantes restent distincts.
- Les 23 ambiguïtés de la dernière vérification **ciblée** ne préjugent pas du nombre national après cette reconstruction.

## Test et état
- Requêtes de diagnostic : succès sur 10 emplacements au moment du test, toutes les variantes `single-paged5` et `batch-one` retournent une réponse.
- Premier run incrémental GitHub Actions lancé : [Electroverse FR incremental status census](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/workflows/electroverse-status-incremental.yml).
- La première partition et la reconstruction globale restent soumises à leurs propres résultats GitHub Actions. Le fichier de ce registre ne prouve pas une publication en V9.
