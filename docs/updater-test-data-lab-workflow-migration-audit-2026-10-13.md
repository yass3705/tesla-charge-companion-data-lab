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

## 13 octobre, complément : traçage des consommateurs réels (pas seulement des schedules)

- Règle utilisateur : **ne pas déduire l'utilité d'une collecte de l'existence d'un workflow**. Pour chaque source, établir la chaîne depuis les sorties exactes du job jusqu'à un lecteur actif (script, workflow, snapshot compilé, site V9), avec preuve du dernier chemin exécuté. Un YAML peut être actif tout en étant orphelin ; un YAML supprimé peut avoir produit un fichier toujours référencé.
- Contrôle GitHub Production `main`, `config/refresh-policy.json` : `collection.cpoDirect.ownerRepo`, `collection.electra.ownerRepo` et `collection.electroverse.ownerRepo` désignent **Data Lab**. La politique de développement sélectionne le snapshot `2026-10-13-be-energyvision-official-cpo-candidate` au SHA Data Lab `94d4fc6785a0c1d2ed4df1d01b5a30d203bd4cd3` ; aucune promotion live automatique.
- Mais le snapshot sélectionné comporte encore des références de provenance à `legacyUpdater` au SHA `3e4c26b...` et à `germanyRecovery` au SHA `59573b8...` (branche `work/germany-v9-cpo-recovery`, PR #6). Ses jeux nationaux déclarent `primarySource=dataLab` pour FR/NL/CH/MA/DE/UK/BE et `stable` pour ES/IT/TESLA. **Ces références au dépôt historique ne prouvent ni consommation runtime, ni absence de dépendance de build** ; les champs de provenance restent à confronter aux scripts d'assemblage et aux manifestes exécutés.
- Le dépôt updater-test possède 1 228 éléments de tree Git versionné, dont 84 YAML après les huit suppressions. Production : 271 éléments versionnés et 51 YAML. Le listing Data Lab via l'API Contents atteint une première page de 1 000 workflows et ne doit PAS être traité comme un recensement exhaustif.
- **Conclusion provisoire seulement** : la politique de sélection des sources oriente les nouveaux snapshots CPO/eMSP vers Data Lab, mais le graphe complet des lecteurs et artefacts actifs n'est pas encore prouvé. Ne pas supprimer les 84 YAML restants, fichiers de données ni chemins de secours sur la seule base de la cadence ou des noms.
- Suite : pour chaque fichier produit par `updater-test`, relever ses lecteurs directs et indirects dans les quatre dépôts, les appels API/checkout d'un SHA historique, les dispatchs inter-dépôts, les runs et artefacts, puis classer `runtime active`, `build/pin active`, `historical provenance only`, `orphan proven`, ou `not yet proven`. Ne supprimer que les orphelins prouvés ou doublons couverts ; préserver Tesla/Mac.

## 13 octobre, revue consommateurs : REVE, OZECAR, Tesla et Electroverse

### REVE Espagne — dépendance inter-dépôts prouvée, **ne pas supprimer**
- Workflow historique `.github/workflows/reve-v2-monthly-production-refresh.yml` : checkout de la branche historique `reve-v2-web-extraction`, construction REVE, puis checkout du dépôt **`tesla-charge-companion-stable`** et copie vers `v9-production-runtime/data/v9/spain-static` et `spain-reve-offers`, commit/push sous validation. Exécution planifiée chaque premier du mois ; [échec 2026-10-01](https://github.com/yass3705/tesla-stations-updater-test/actions/runs/36847109484), réussite non présumée.
- Le manifeste Stable Espagne actuellement consulté a `generatedAt=2026-09-27T09:08:02.333Z`, `stationCount=13980`, `uniqueEvseIds=42887` et `ambiguousEvseIds=139` ; le snapshot Production de développement sélectionne `primarySource=stable` pour ES. **Dépendance de publication historique potentiellement encore nécessaire**, même si dernier run en échec.
- Data Lab dispose de `spain-reve-v9-stream-refresh.yml` avec cadence horaire, mais ce pipeline ne prouve pas à lui seul le remplacement du transfert vers Stable. Toute migration doit inclure consommation du snapshot ES, offers et garde d'équivalence.

### OZECAR — activité historique mais consommation Production non établie
- `ozecar-france-extract.yml` programmé chaque jeudi, écriture `data/ozecar/france/ozecar-france-current.json.gz` et rapport dans updater-test ; [run 2026-10-08 réussi](https://github.com/yass3705/tesla-stations-updater-test/actions/runs/37770196420). Aucun chemin de copie vers Production constaté dans le YAML inspecté. Un pipeline national WAAT/Monta Data Lab existe, mais équivalence d'IDs, prix et consommateurs OZECAR non prouvée. **Conserver** en attendant preuve.

### Autres
- `export-charge-companion.yml` fonctionne sur Mac self-hosted et compare un export Tesla à SuC Tracker ; conserver avec Tesla.
- `electroverse-incremental-refresh.yml` est manuel ou sur fichier trigger (pas de cadence schedule) et écrit dans l'ancien dépôt ; Data Lab dispose de `electroverse-france-daily-delta.yml` programmé. Ne pas déduire l'inutilité des caches historiques sans rechercher les lecteurs des chemins correspondants.
- `ze-watt-france-extract.yml` est manuel ou push sur script ; il publie un snapshot Ze-Watt dans l'ancien dépôt. Aucun homonyme direct trouvé lors du contrôle Data Lab ; **conserver en attendant analyse des consommateurs**.
- Huit suppressions antérieures portaient sur des YAML ; rien ne démontre encore que toutes les données déjà extraites soient devenues inutiles, donc garder les fichiers de données historiques.

## 13 octobre — correction de critère demandée : Production est l'unique destination de publication TCC V9

- **Stable ne doit plus être traité comme une destination finale justifiant à elle seule le maintien d'une collecte**. Stable peut servir de référence, archive, source transitoire de snapshot épinglé ou contrôle de parité, mais le critère d'utilité d'un workflow est sa contribution **effective et prouvée au dépôt Production et, s'il s'agit de publication live, au runtime déployé**.
- Le snapshot actuellement désigné par `tesla-charge-companion-production/config/refresh-policy.json`, `2026-10-13-be-energyvision-official-cpo-candidate`, utilise encore `primarySource=stable` pour **TESLA, ES et IT** ; le SHA Stable épinglé est `0a6d2c3415504397310d3dc92fae40be843b2435`. Il faut mesurer ces lectures réelles dans le build Production et migrer ce reliquat si Data Lab dispose des données vérifiées. **Ce n'est pas une autorisation à republier sur Stable**.
- Le workflow REVE mensuel de updater-test publie vers Stable ; cela explique une provenance ancienne mais **ne prouve pas l'actualisation de Production**, car Production utilise un snapshot candidat immuable avec SHA Stable explicite et les promotions sont manuelles. Réviser son statut : **candidat à retrait/migration**, sous réserve d'auditer le chemin de données effectif jusqu'à Production et la couverture REVE Data Lab. La conclusion précédente « conserver impérativement parce que Stable reçoit des données » était trop forte.
- Même règle pour OZECAR, Ze-Watt, Electroverse, GOFAST, Suisse, etc. : un workflow peut être actif, publier dans un dépôt et rester sans aucun lecteur dans le build Production. Ne pas déduire une dépendance des seules références de provenance, d'un nom identique, d'une production d'artefact ou de l'activité GitHub Actions.
- Classification demandée : (1) **consommateur direct Production démontré**, (2) **consommateur indirect dans un build Production démontré**, (3) **référence historisée / snapshot figé seulement**, (4) **aucun lien Production prouvé**, (5) **audit incomplet**. Ne supprimer les processus potentiellement utiles qu'après évaluation des pertes de données et de la migration, mais ne jamais considérer Stable comme une destination finale.

## 15 octobre — delta depuis l'inventaire #302 (sans refaire le recensement)

Références `origin/main` après fetch : Updater Test `899929bb6cd444ed2866a853bb4c7b329273c727`, Stable `39c5bcaadd42b9ba932824f89dc8b97e20ebb762`, Data Lab `709fcce2cb444d954e34274bd84dfdeaa7797504`, Production `61b72136ed24c1c4ab34b1efb0c525c2ab71d5a4`. Les SHA servent à dater le constat ; les branches locales historiques n'ont pas été avancées.

| Chaîne / source | Destination cible | Statut au SHA cité | Preuve et condition suivante |
| --- | --- | --- | --- |
| Tesla Mac `update-stations.yml` (Updater Test) | Collecte **conservée** ; consommation Production à vérifier | Exception permanente | Runner `[self-hosted, macOS, X64]` et dispatch dans Updater Test `899929bb`; ne modifier ni runner, ni secrets, ni exécution. |
| SuC Tracker historique (Updater Test) | Data Lab pour la collecte SuC, fallback historique manuel | Déjà migré, fallback conservé | `suc-tracker-weekly.yml` dans les deux dépôts ; l'ancien n'a que `workflow_dispatch`. Priorité Tesla et secours à conserver. |
| REVE scheduler checkpoint et rafraîchissement mensuel (Updater Test) | Data Lab collecte, Production build ES | Migration partielle | `reve-v2-api-scheduler.yml` persiste sur branche de checkpoint ; `reve-v2-monthly-production-refresh.yml` écrit encore vers Stable. Data Lab `spain-reve-v9-stream-refresh.yml` est horaire. Issue #303 / PR #306 : attendre complétude, deux runs comparables et consommation ES Production épinglée. |
| Electroverse historiques (Updater Test) | Data Lab collecte, Production offres eMSP | Migration partielle, certains anciens chemins manuels | Updater `electroverse-incremental-refresh.yml` est dispatch/trigger et écrit dans l'ancien dépôt ; Data Lab `electroverse-france-daily-delta.yml` et `electroverse-france-full-refresh.yml` existent. Établir lecteurs exacts des caches anciens avant extinction ; ne pas fusionner avec CPO direct. |
| OZECAR France (Updater Test) | Data Lab si fonction nationale réellement manquante | Non migré prouvé, consommateur Production non prouvé | `ozecar-france-extract.yml` garde un cron jeudi et produit `ozecar-france-current.json.gz` ; Data Lab `corse-regional-coverage.yml` ne couvre que la preuve Corse et ne remplace pas cette collecte nationale. Garder le cron jusqu'à analyse IDs/prix/lecteurs et deux runs équivalents. |
| Huit YAML non-Tesla supprimés (Updater Test) | Data Lab existant | Workflows obsolètes supprimés, données historiques conservées | Commits `0b6128e6` à `2172e27c` entre le SHA local précédent et `899929bb` : Electroverse bootstrap, Greenspot, GOFAST et cinq chaînes suisses. Les données historiques n'ont pas été supprimées ; équivalence des consommateurs toujours à vérifier. |
| France IRVE relay `sync-france-irve-static.yml` (Stable) | Data Lab → Production direct | Migration partielle | Stable `39c5bcaa` exécute encore le relais ; Production #104 au commit `19d53c0` est opt-in et bloquée sur supplément Belib déjà présent dans la nouvelle génération. Aucun retrait avant parité multiensembles, consommateurs et rollback. |
| `pages.yml` et `publish-tesla-global.yml` (Stable) | Publication et build V9 Production | Migration partielle ; Stable conservé | Stable `39c5bcaa` a encore Pages et reconstruction Tesla ; Production #97/#102/#103 ont apporté runtime, pins et gates. Canary, URLs/PWA/asset graph et chemin Mac → Production restent à prouver avant désactivation. Aucune bascule publique. |
| Production build, validation, fraîcheur et publication | Production | Déjà présente, cutover non validé | `build-snapshot.yml`, `v9-refresh-candidate-dry-run.yml`, `v9-source-freshness-audit.yml` et les gates Pages sont versionnés à `61b72136`. Les workflows de publication ont une condition dispatch explicite ; les candidats et rapports ne valent pas promotion. |

Les autres YAML manuels de l'inventaire du 13 octobre gardent le statut **audit des consommateurs incomplet** ; leur présence seule ne prouve ni alimentation V9 ni obsolescence. Aucun workflow historique supplémentaire n'est retiré sur cette seule matrice.
