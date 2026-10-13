# Migration GitHub Actions updater-test → Data Lab — 2026-10-13

## Règle approuvée
Le dépôt historique `yass3705/tesla-stations-updater-test` doit conserver le processus Tesla/Mac distinct. La collecte CPO directe, les données nationales et les offres eMSP sont canoniques dans `yass3705/tesla-charge-companion-data-lab`. Supprimer les doublons **seulement après vérification fonctionnelle et de couverture**, et ne jamais arrêter une collecte sans remplacement établi. Ne pas mélanger les offres CPO et eMSP ; préserver ID EVSE exact, puissance, statuts et données validées.

## Audit initial et changements confirmés
- 92 fichiers de workflow recensés initialement dans updater-test ; 8 suppressions confirmées sur sa branche main ; 84 fichiers restant après action.
- Data Lab contient un catalogue nettement plus vaste (1000 entrées fournies par la première page d'API ; ce nombre n'est pas un inventaire exhaustif).
- Doublons supprimés : `electroverse-bootstrap-auto.yml`, `greenspot-france-extract.yml`, `gofast-audit.yml`, `swisscharge-full-collection.yml`, `switzerland-national-cpo-counts.yml`, `switzerland-powerup-full-scan.yml`, `switzerland-target-cpo-full-scan.yml`, `switzerland-target-cpo-second-pass.yml`.
- Dans updater-test, le bootstrap Electroverse historique était automatique toutes les deux heures, alors que son homonyme Data Lab utilise des événements différents ; migration fonctionnelle du processus de collecte vers Data Lab, et non identité de configuration.
- Les suppressions portent uniquement sur les YAML historiques : les données historiques et les scripts n'ont pas été effacés.
- GOFAST, Swisscharge, Greenspot et les contrôles suisses ont des workflows de même fonction dans Data Lab.
- Les anciennes collectes OZECAR et REVE ont encore des workflows programmés ; elles **ne sont pas supprimées à ce stade**, leur substitution exacte doit être établie.
- Un nom de fichier identique ne suffit pas à démontrer l'égalité de sortie, de calendrier ou de mise à jour ; aucun succès des prochains runs n'est présumé.

## Workflows conservés au titre du processus Tesla / validation Tesla
- `suc-tracker-weekly.yml`
- `update-station-lot.yml`
- `update-stations.yml`
- `validate-v9-preview-dispatch.yml`

## Maintenance ou export spécifique au dépôt, conservé
- `actions-storage-maintenance.yml`
- `export-charge-companion.yml`

## Autres workflows toujours présents, comparaison fonctionnelle et déclencheurs à finaliser
Ces fichiers sont inventoriés mais **non certifiés doublons**. La majorité paraît être des outils exploratoires/diagnostics historiques à la lecture du nom ; la présence d'un équivalent fonctionnel et d'un calendrier actif doit être vérifiée avant suppression.
- `adhoc-tariff-route-discovery.yml`
- `electroverse-adaptive-300.yml`
- `electroverse-direct-1000-benchmark.yml`
- `electroverse-direct-evse-lookup.yml`
- `electroverse-direct-singles-100.yml`
- `electroverse-direct-smoke.yml`
- `electroverse-france-inventory-count.yml`
- `electroverse-incremental-refresh.yml`
- `electroverse-incremental-selector.yml`
- `electroverse-irve-mapping.yml`
- `electroverse-physicalref-batch-benchmark.yml`
- `electroverse-tariff-cache-audit.yml`
- `electroverse-tariff-cache-pilot.yml`
- `electroverse-tariff-cache-recovery.yml`
- `electroverse-tariff-cache-shard-migrate.yml`
- `electroverse-tile-property-probe.yml`
- `energie360-anon-mobile-tariff.yml`
- `energie360-apk-inspect.yml`
- `energie360-config-decode.yml`
- `energie360-direct-probe.yml`
- `energie360-legacy-route-discovery.yml`
- `energie360-public-portal-probe.yml`
- `energie360-residual-evse-probe.yml`
- `energie360-tariff-group-reconcile.yml`
- `energie360-tenant-discovery.yml`
- `france-active-party-irve-batch311.yml`
- `france-cpo-reconcile-291.yml`
- `france-intercharge-direct-probe-batch301.yml`
- `france-intercharge-direct-probe.yml`
- `france-lineage-priority-batch318.yml`
- `france-lineage-promote-batch320.yml`
- `france-lineage-reconcile-batch319.yml`
- `france-mw1-vis-irve-batch304.yml`
- `france-mw1-vis-missing-batch306.yml`
- `france-mw1-vis-wii-dedupe-batch305.yml`
- `france-national-party-inventory-batch313.yml`
- `france-non-tesla-corrected-extraction.yml`
- `france-parera-irve-batch302.yml`
- `france-party-canonical-crosscheck-batch316.yml`
- `france-wii-irve-batch303.yml`
- `inspect-irve-canonical.yml`
- `irve-electroverse-spatial-candidates.yml`
- `irve-electroverse-spatial-uniqueness.yml`
- `irve-electroverse-spatial-validation.yml`
- `morocco-cpo-runtime-config-v4.yml`
- `move-apk-inspect.yml`
- `move-public-probe.yml`
- `ozecar-france-extract.yml`
- `reve-v2-api-scheduler.yml`
- `reve-v2-monthly-production-refresh.yml`
- `reve-v2-web-extraction.yml`
- `swiss-atlas-direct-semantics.yml`
- `swiss-price-atlas-api-sample.yml`
- `swiss-price-atlas-bbox-sample.yml`
- `swiss-price-atlas-collect.yml`
- `swiss-price-atlas-frontend.yml`
- `swiss-price-atlas-probe.yml`
- `swiss-price-atlas-query-decode.yml`
- `swisscharge-cloud-paths.yml`
- `swisscharge-e360-gap-bridge.yml`
- `swisscharge-portal-probe.yml`
- `swisscharge-probe.yml`
- `switzerland-current-gap-adhoc.yml`
- `switzerland-current-scope-reconcile.yml`
- `switzerland-exact-adhoc-residual.yml`
- `switzerland-final-residual-exhaustive.yml`
- `switzerland-final-residual-reconciliation.yml`
- `switzerland-residual-chargepoint-by-id.yml`
- `switzerland-residual-final-atlas.yml`
- `switzerland-residual-national-metadata.yml`
- `switzerland-residual-relationship-audit.yml`
- `switzerland-residual-retry.yml`
- `switzerland-residual-swisscharge-probe.yml`
- `switzerland-unresolved-summary.yml`
- `switzerland-unresolved-targeted.yml`
- `uk-apcoa-open-web-smoke.yml`
- `uk-validated-open-feeds-smoke.yml`
- `ze-watt-france-extract.yml`

## Suite obligatoire du protocole
1. Comparer les déclencheurs `schedule`/`push`/`workflow_dispatch`, scripts, sorties, consommateurs, et dernière réussite pour chacun des workflows non-Tesla restants.
2. Priorité aux collectes programmées : OZECAR, REVE et tout autre workflow encore actif.
3. Pour une vraie duplication prouvée, supprimer le YAML dans updater-test uniquement après confirmation que Data Lab collecte, préserve et publie de manière validée.
4. Enregistrer commits, runs, incidents et décisions dans `memory/CURRENT.md`, `memory/HISTORY.md` et ce rapport ; ne pas considérer les éléments non audités comme finalisés.
