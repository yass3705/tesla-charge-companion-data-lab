# Electroverse France — Étape 2 : reconstruction des 16 partitions de statuts (22 novembre 2026)

**Mandat utilisateur :** déclencher l'étape 2 du chantier Electroverse immédiatement après l'acquisition tarifaire complète. Il ne s'agit ni d'une nouvelle collecte de prix, ni de la construction de l'overlay, ni d'un déploiement public.

## Dépendance immuable et isolation

- Source de prix finalisée : [run 45024846774](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45024846774), SHA source `67ba3287bfceeaf463c43ddc15ed4658e212cc8c`, `completed/success`, manifeste `complete`.
- Archive GitHub [`14760747281`](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45024846774/artifacts/14760747281), ZIP SHA-256 `0d3abcc15dc4762b360c5816b6e783accdcafa664442c8ce99b7c0500743a5fe`, ensemble des 136 fichiers `artifact_set_sha256=c06886fec4b9117e920d7ee50af66d5fb0ebfa00944c452012d771a033a9b965`, **22 818 PK**, 128 shards. Pas de checkpoint de prix partiel.
- Branch unique `rebuild/v9-20261020`, script et workflow isolés, `contents: read`, `actions: read`, `persist-credentials: false` et aucun push ni écriture Production, Stable ou Updater Test. La source est récupérée par run/artifact/digest exact, décompressée sans traversal ni symlink, puis validée par tous les SHA/manifeste/source et le code existant avant la première requête statut.

## Préparatifs et preuves

- Correctif `f2fcc76279060f462535fa8e7ee5b19004ec8466` dans `scripts/electroverse_status_incremental.mjs` : protège les requêtes `status_batch`, `status_single` et `status_page`, stoppe au **premier HTTP 429 ou GraphQL throttling**, sans retry de cette réponse, enregistre `rateLimitPlan`/délai de reprise et conserve les entrées bonnes via checkpoint de partition. Le rythme historique `800 ms`, deux alias par batch, 16 partitions et validateur/finalizer national restent inchangés.
- Driver `scripts/pilot_v9_electroverse_status.py` créé en `3cb4c1f0655b81afc33fa624fb38a8332c2ad3c8` : `verify` sans fournisseur, `collect` séquentiel sur les 16 partitions, une seule tentative de parcours par run ; garde de budget 18 000 s avec réserve pour sauvegarde, contrôle de fraîcheur et provenance à chaque partition ; état `checkpointed` séparé de `complete`. Ne promeut jamais une partition incomplète.
- Workflow dédié `.github/workflows/v9-electroverse-status-rebuild.yml` créé en `3df5c2e3df8cd76c0ca180c12a2641b2b2b45352`, corrigé en `408586139ea476effd4a593a9c4b9e171a8ce355` pour placer le checkout dans `PYTHONPATH`. Déclenchement uniquement sur la modification de `migration/v9/electroverse-status-request.json`, et seulement sur la branche de reconstruction ; durée maximale du job 330 minutes ; séparateur des artefacts `status-complete`, `status-checkpoint`, `status-failure`. Aucune réactivation des anciens workflows ni événement `workflow_run`.
- Premier préflight [`45045047597`](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45045047597) : 20 tests Python + 8 tests Node + public safety, parent GitHub et ZIP SHA, tous OK ; **échec du pilote au moment de l'import Python** (`ModuleNotFoundError: v9_rebuild`) avant tout appel fournisseur ; corrigé avec `PYTHONPATH`.
- Préflight corrigé [`45045314084`](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45045314084), commit `d87791e210d2991700bc39443e8a38f439779bfc` : **completed/success**, 20 tests Python + 8 Node, scanner public PASS, parent exact, ZIP SHA, 137 entrées récupérées, `verified_tariff_parent` et `verified_only,supplierCalls=0`.

## Run réel lancé

Sur instruction utilisateur, demande `mode=collect` `b2f3ff554f1f297421c00425232a7d38c3510433` : **[GitHub Actions #45045530435](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45045530435)**, job `137279198848`, démarré le 22 novembre 2026 à `16:44:42Z`. **Résultat et avancement fournisseur encore inconnus à ce stade ; vérifier le job et ses artefacts avant de parler de progrès.**

## Critères d'audit obligatoires à la sortie

1. Si `tcc-v9-electroverse-status-complete`, contrôler le ZIP et les fichiers signés, les **16 partitions toutes fraîches**, le `sourceFingerprint` correspondant au cache complet, les 22 818 PK (ou motif technique explicite), le ledger `evses.json.gz`, `status-national-finalization.json`, l'absence d'échecs et le manifeste `complete`. Ne pas publier automatiquement.
2. Si `tcc-v9-electroverse-status-checkpoint`, confirmer `partial_checkpoint`, progression par partition, toutes les entrées valides et l'empreinte parent. Examiner `rateLimit` et `resumeNotBeforeUtc` s'il existe, l'absence d'appels après 429, les éventuels refus fournisseur et la fraîcheur. Un checkpoint **n'est pas un statut national utilisable**.
3. Si erreur sans checkpoint construit, analyser `status-failure` et les logs sans exposer les secrets. Ne pas relancer automatiquement ni fabriquer de statuts `AVAILABLE` ou `CHARGING`.
4. Aucun statut live ne doit être inventé ; ne pas confondre la liste des EVSE dans le cache tarifaire avec la disponibilité réelle. L'étape 3 (overlay) reste **non démarrée** et exige un artefact de statuts national validé.

**Traçabilité :** cette note est un état de lancement, **pas** un rapport de succès. Tout changement ultérieur doit être accompagné du SHA et des preuves du run, puis synchronisé dans `memory/CURRENT.md` / `memory/V9_REBUILD_PROGRESS.md` / `memory/HISTORY.md`.

## Suivi ponctuel programmé

L'automatisation de **lecture et audit uniquement** `Automation_b2f956dcd33c8191b7fc6fce635451d5` est planifiée le **22 novembre 2026 à 21 h 47, heure de Paris**. Elle vérifiera l'issue du run `45045530435`, les fichiers et la qualité des partitions, sans relancer la collecte, modifier les dépôts ni promouvoir une sortie. Un run encore actif à cette échéance doit être déclaré actif, non artificiellement terminé.


## 22 novembre 2026 — audit post-429 et validation réelle de la reprise sans fournisseur

**Run statut :** [#45045530435](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45045530435), job 137279198848, completed/success mais **checkpointed, pas complete**. HTTP 429 réel à 2026-11-22T16:58:07.420Z (phase status_batch), sans Retry-After : arrêt provider_rate_limited, backoffSeconds 900, reprise indiquée au plus tôt à 2026-11-22T17:13:07.420Z. Partition 00 : 1 427 attendues, **667 entrées sauvegardées et 5 erreurs** single_paged_unavailable ; 760 restantes dans cette partition. Aucune partition nationale complète, aucun ledger ni overlay généré.

**Artefact immuable :** [#14763184200](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45045530435/artifacts/14763184200) ; ZIP SHA-256 1439fbde2f8670bf45eef872dda1fba10f9c253dce1001e0c4622b1a694b748d ; fileset SHA-256 86d5253d27e34b29e38fc985851aa06417f1375a25f0fcb235d74158cd277925 ; 138 fichiers signés ; sourceFingerprint 3365025ffc1f0f57ac4b48101e4e78517797a8cbb5a8b2a72fea60bce1cd12b4. Parent tarifaire conservé : run 45024846774 / artefact 14760747281, 22 818 localisations et 128 shards.

**Correctifs versionnés sur rebuild/v9-20261020 :**
- 41bb1aa56975378334aebb710927955fc8260cc9 — scripts/pilot_v9_electroverse_status.py : contrôle du checkpoint et des SHA, provenance et mapping identiques à la source, entrées réussies conservées, refus de l'écrasement implicite, cooldown et limite de fraîcheur.
- f15bcf66405edfee81d5193250864b2e3a8b37e7 — tests/test_v9_electroverse_status_checkpoint.py : cinq nouveaux tests de conservation, corruption, divergence de source, promotion factice, attente et péremption.
- 3b55b7a5ea0c1e6659effbfdb31e5f327f288d41 et f104d98eac904178401a0ccf0f26c2573c9e688e — workflow v9-electroverse-status-rebuild.yml : autorisation fournisseur distincte, contrôle du run et du ZIP GitHub, extraction sécurisée du checkpoint, transmission des pins.
- cef33ce18d6a9fd296aa1906f125c4128b8a70dd — migration/v9/electroverse-status-request.json : mode verify, explicitProviderAuthorization=false ; aucun run fournisseur demandé.

**Preuve distante de l'étape 2 hors fournisseur :** [run #45048950087](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45048950087), job 137289595777, SHA cef33ce18d6a9fd296aa1906f125c4128b8a70dd, **completed/success**. 25 tests Python + 8 Node + public safety PASS ; parent tarifaire, manifeste, run d'origine, ZIP et file-set checkpoint validés. Le pilote a émis verified_status_checkpoint : 667 résultats, 5 erreurs, sourceFingerprint exact, resumeEligible=true ; puis result=verified_only, supplierCalls=0, checkpointValidated=true. Aucune sortie statut nouvelle publiée : les uploads complete, checkpoint et failure sont skipped en mode verify.

**Fenêtre de fraîcheur à respecter :** partition 00 démarrée à 2026-11-22T16:46:58.837Z. Fraîcheur historique 16 h, expiration le **23 novembre 2026 à 08:46:58 UTC**, soit 09:46:58 Paris. Le nouveau garde refuse les reprises à moins de 10 minutes de ce terme, soit à partir d'environ **08:36:58 UTC / 09:36:58 Paris**. Le statut resumeEligible=true est un constat au moment du run de validation, pas une garantie future. Le cooldown de 15 min n'établit pas la durée exacte de rétablissement du quota fournisseur. Ne pas promettre la conservation de statuts frais hors de cette fenêtre.

**Relais Codex CLI :** étapes 1 (correctif) et 2 (vérification sans fournisseur) PASS ; collecte nationale des 16 partitions toujours INCOMPLÈTE ; overlay étape 3 non démarré. Pour passer en mode collect : nouvelle autorisation utilisateur, demande versionnée explicitProviderAuthorization=true, contrôle de non-concurrence et fraîcheur du checkpoint, puis audit du nouveau résultat. Aucun changement Data Lab main, Production, Stable, Updater Test, Netlify, source prix ou règles de jointure.
