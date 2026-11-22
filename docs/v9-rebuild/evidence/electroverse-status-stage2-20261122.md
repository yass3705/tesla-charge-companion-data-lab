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
