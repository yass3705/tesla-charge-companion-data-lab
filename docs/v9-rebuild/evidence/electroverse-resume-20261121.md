# Electroverse — checkpoint conservé et reprise bornée dans GitHub Actions

**21 novembre 2026 — intervention sur `rebuild/v9-20261020`. Périmètre : les deux premières étapes demandées par l'utilisateur (sécurisation du checkpoint, continuation automatique de fenêtres dans un job). Pas de rematching IRVE, pas d'import Production ni Netlify, pas de changement sur `main`.**

## 1. Point de reprise prouvé

- Run historique : [44912790561](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/44912790561), conclusion Actions `success` mais source `partial_failure` pour `collector_window_budget`.
- Artefact de reprise : `14711673559` (`tcc-v9-tariff-window-0`), expirant le **21 décembre 2026** selon l'API GitHub. SHA-256 ZIP : `a31e1630c39271e7f912a5d4e3262aa95a924a1f0d5dbb291f61d337b82c2879`.
- Source `FR:electroverse_full` ; branche `rebuild/v9-20261020` ; `headSha=2d19e361530f5a66072a56b6491f16779a9a823f` ; SHA-256 jeu de fichiers `3a7059c1648668fe5a27ff4465b1355a63370d1c35d7cc5ce6f73b403491608b`.
- ZIP téléchargé et ouvert en lecture seule. **136/136 empreintes de fichiers internes vérifiées**, 128 shards présents, aucun fichier absent, aucun contenu invalidé. `v9-electroverse-checkpoint.json` : `mode=full`, `completed=[0]`, `pending.offset=6000`, **4 600 PK en attente dans le deuxième chunk**. Cumul **7 400 localisations revérifiées** ; **15 418 historiques non revérifiées en novembre** ; le cache conserve 22 818 lieux.
- Les archives ZIP ont été sauvegardées comme fichiers de travail de la conversation, indépendamment de l'artefact GitHub. Ce dépôt ne contient **pas** de copie brute ajoutée à Git ; prévoir une conservation pérenne autorisée si la reprise doit dépasser les 30 jours. Ne pas confondre archive intègre et génération complète/fraîche.

## 2. Correction de la boucle de fenêtres

- Commit `725cb00e58083ccba84b559b7efe1452c5ceb2c0` : `scripts/pilot_v9_tariff_chunks.py` et `tests/test_v9_tariff_chunk_pilot.py`.
- Avant : le premier `collector_window_budget` interrompait le job alors qu'une fenêtre supplémentaire pouvait encore être exécutée dans le même temps GitHub.
- Après : `advance()` poursuit les fenêtres source **de 1 800 secondes maximum** lorsque le job dispose encore du temps d'une fenêtre complète + **300 secondes de réserve** pour valider et conserver le checkpoint. Le curseur demeure celui du bloc historique, sans recommencer les PK déjà traités ; pas de changement de requêtes fournisseur, de clés, de mapping ou de politique tarifaire.
- Cas interdits : échec fournisseur/timeout non récupérable ; fenêtre sans progression ; `pending` du mauvais chunk, PK dupliquées ou structure invalide ; il reste une archive d'échec distincte et **aucune promotion vers Production**.
- Fin de budget : sortie `checkpointed` avec `completeSnapshotValidated=false` et vérification de l'état, non un faux `PASS`.

## 3. Workflow isolé et choix du parent

- Commit `ee7bd6a30015c93bd7f400b40efcd0191c73374f` : nouveau `.github/workflows/v9-electroverse-resume.yml`, `scripts/select_v9_electroverse_checkpoint.py`, tests de sélection.
- Déclencheur unique : **push du chemin** `migration/v9/electroverse-resume-request.json` sur **`rebuild/v9-20261020`**. Aucune permission d'écriture GitHub ; `contents: read`, `actions: read` ; `persist-credentials: false`.
- Modes : `verify` = tests offline, scan public et vérification ZIP/manifestes/mapping **sans appel Electroverse** ; `collect` = même validation préalable, puis avance bornée du collecteur historique avec secret `ELECTROVERSE_API_KEY` injecté uniquement dans l'étape fournisseur.
- Le parent est sélectionné par sa **provenance exacte** (nom d'artefact, branche, workflow, run réussi, SHA, empreinte ZIP, manifeste). En l'absence de nouvelle génération dédiée, le parent est **l'artefact historique 14711673559**. Une génération complète dédiée plus récente empêche une nouvelle reprise sur l'ancien partiel.
- Artefacts étiquetés différemment : `tcc-v9-electroverse-window` (partiel), `tcc-v9-electroverse-complete` (complet sous réserve des validations métier dédiées), `tcc-v9-electroverse-failure` (échec). Rétention 30 jours, aucun push de données brutes sur le dépôt public.
- Demande de test en lecture seule `d14a5326d0b06dcd09c7429d374694946d6aa56e`. [Run GitHub 44947769520](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/44947769520) **SUCCESS vérifié**, comme détaillé en section 6 ; aucune collecte en mode verify.

## 4. Frontière d'automatisation : fait vs non fait

**Implémenté** : progression automatique entre fenêtres **dans une même exécution GitHub Actions** ; reprise **entre exécutions distinctes** sur le dernier checkpoint validé, à partir d'un nouveau push explicite de demande ; aucun recalcul des jointures IRVE.

**Non mis en service** : auto-déclenchement d'un nouveau workflow après chaque checkpoint, ou cron Electroverse permanent. Selon [GitHub Actions](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows), `workflow_dispatch`, `workflow_run` et `schedule` nécessitent que le workflow approprié existe sur la branche par défaut ; le `GITHUB_TOKEN` ne déclenche pas de nouveaux jobs sur un simple push automatisé. Aucun workflow sur `main` n'a été modifié pour contourner ces restrictions. Une automatisation permanente nécessitera un mécanisme approuvé et des preuves spécifiques de sécurité.

**Tests** : le code et les tests sont versionnés ; le run 44947769520 a confirmé le transfert, les 10 tests et le scan public. La continuation sur API réelle n'a pas été exercée. **Aucun appel massif fournisseur ni collecte ne résulte des commits ou de la demande `mode=verify`.** Les portes G2–G9 restent dans leur état antérieur.

## 5. Reprise sans perdre l'historique

Lire `AGENTS.md` et `memory/WORKING_AGREEMENT.md` puis ce rapport et `CURRENT.md`. Vérifier que `main` ne possède aucun déclencheur indirect pour la branche. Examiner le [run 44947769520](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/44947769520), puis le manifeste `checkpoint-manifest.json` de l'artefact parent. Si le test est `PASS`, un futur push explicite de demande `mode=collect` peut démarrer des fenêtres réelles sur la même branche, avec rapprochements et snapshots existants inchangés. Ne jamais relancer deux générations concurrentes.

## 6. Résultat du pilote read-only — validation distante confirmée

[Run GitHub **44947769520**](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/44947769520), job **136978761119**, SHA de code `d14a5326d0b06dcd09c7429d374694946d6aa56e`, branche `rebuild/v9-20261020`, conclusion **SUCCESS** le 21/11/2026 à 20:45 UTC.

Contrôles observés dans les logs :
- **10 tests unitaires PASS** (`tests.test_v9_tariff_chunk_pilot`, `tests.test_v9_electroverse_resume` ; 0 erreur).
- **Public safety scan: OK**.
- Sélecteur : parent `run=44912790561`, `artifact=14711673559`, `head=2d19e361530f5a66072a56b6491f16779a9a823f`, SHA-256 ZIP `a31e1630c39271e7f912a5d4e3262aa95a924a1f0d5dbb291f61d337b82c2879`.
- Téléchargement GitHub Action `parent.zip: OK` au contrôle SHA ; `verify_checkpoint()` et validation des 136 entrées/SHA, 128 shards et mapping de la génération héritée **PASS** en runner Linux.
- Étape « Continue bounded windows » **skipped** conformément à `mode=verify`. Aucun secret fournisseur utilisé par le code de collecte, aucune requête tarifaire initiée, aucun artefact source renouvelé.
- Branche `main`, Production, Stable et Updater Test inchangés. Aucune collecte eMSP en cours du fait de cette vérification.

**Statut exact :** installation branche et reprise de checkpoint **PASS**, continuation intra-job **tests offline PASS, collecte réelle NOT TESTED** ; reprise autonome **entre runs** **NOT IMPLEMENTED** (pas de workflow permanent/main). Ce résultat ne vaut pas PASS pour G2–G9 ou un nouveau jeu de prix.

## 21 novembre 2026 — lancement réel Electroverse #44950136959 (à contrôler après terminaison)

**Autorisation explicite utilisateur :** « D’accord lance le run ». Après vérification qu'aucun workflow de reconstruction n'était actif, checkpoint de départ `14711673559` non expiré, SHA-256 ZIP `a31e1630c39271e7f912a5d4e3262aa95a924a1f0d5dbb291f61d337b82c2879` et HEAD initial `df7ae13ce237e23f131dc1d810bf1508f46209fd`, push **du seul fichier** `migration/v9/electroverse-resume-request.json` en `mode=collect` : commit `78d3c997c156a54c7954808969c2fe369918a330`. Nouveau [run 44950136959](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/44950136959), job `136986031949`, démarré le 21/11/2026 21:10 UTC, **`in_progress` au dernier contrôle**. Aucun autre run concurrent observé lors du lancement.

**Source** `FR:electroverse_full`. Reprise attendue de `completed=[0], pending.offset=6000, pending=4600` ; les 7 400 revérifiés antérieurement restent dans le checkpoint, les 15 418 autres restent archives jusqu'à un contrôle effectif. **Ne pas affirmer un traitement nouveau ou un succès avant les journaux, l'artefact et les empreintes en sortie.** Chaque fenêtre ne déclenche que les appels de la méthode déjà validée. Aucun rematching IRVE, changement Production/Netlify/`main`. La continuation automatique **entre jobs distincts** n'est pas activée. Après terminaison, examiner `conclusion`, états des steps, journaux, `checkpoint-manifest.json`, nombre de PK revérifiées, filiation, fichiers SHA/ZIP et absence de prix de faux positif. Toute nouvelle relance doit être fondée sur ce résultat et sur l'absence de concurrence.


## Bilan réel du run #44950136959 — clôture le 21/11/2026 à 22:14 UTC

**Exécution de collecte fournisseur réussie, génération encore partielle.** [Run 44950136959](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/44950136959), job `136986031949`, code `78d3c997c156a54c7954808969c2fe369918a330`, `status=completed/conclusion=success`, démarrage 21:10 UTC / clôture 22:14 UTC. Étapes offline (10 tests, scan public), sélection du parent, vérification ZIP/mapping, collecte et upload **PASS**. `manifest.json` du collecteur conserve `status=partial_failure`, `reason=collector_window_budget`, et le pilote imprime `{"status":"checkpointed","chunks":4}` : **ce n'est PAS une génération complète et aucun import Production n'a eu lieu.**

**Nouvel artefact canonique de reprise :** `14727835115` nommé `tcc-v9-electroverse-window` ([lien GitHub](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/44950136959/artifacts/14727835115)), ZIP **13 224 817 octets**, SHA-256 **`3622a321b6885434d7c4541199d2ffc58703c82f790a0511a6b3cf998e6e7aac`**, expiration annoncée **21 décembre 2026 à 22:14:30 UTC**. Archive récupérée et ouverte ; **138 entrées ZIP**, dont **136 chemins listés par le manifeste de checkpoint, 136/136 SHA-256 + tailles contrôlés**, 128 shards intacts. `checkpoint-manifest.json` : source `FR:electroverse_full`, `headSha=78d3c997c156a54c7954808969c2fe369918a330`, `runId=44950136959`, `state=partial_checkpoint`, `completeSnapshotValidated=false`, SHA-256 du jeu de fichiers **`b04dfb1565024c06a40b5fc75069ea07cad2f03e24f7fa8032634657a662d1e3`**. Le SHA ZIP est égal au `digest` officiel GitHub et à la valeur remontée par upload-artifact.

**Delta indépendant par comparaison binaire/données avec le parent 14711673559 :**
- Cache de **22 818** localisations conservé, clés station identiques, mapping national/Electroverse **octet pour octet identique**.
- Écritures de vérification `checked-at.json` : **7 400 → 10 300** localisations horodatées du 21/11 (**+2 900**), aucune modification des horodatages des **19 918** autres.
- De ces 2 900 localisations revérifiées, **1 604 enregistrements ont changé de `tariffHash`** et 1 296 ont gardé leur `tariffHash` ; aucune des **19 918** autres entrées sources n'a changé. `tariffHash` modifié **ne signifie pas** prix au kWh modifié.
- Curseur `completed=[0]`, `pending.offset=6000`, `pending.pks=1700` : deuxième bloc de 6 000 entamé et **1 700** non encore revérifiées. **12 518** localisations globales n'ont pas été revérifiées le 21 novembre (majoritairement datées du 18/10, une du 20/10), conservées last-good.
- Preuve de progression **PASS** : 2 900 nouveaux PK, zéro PK hors fenêtre altérée, aucun reset des shards, coût fournisseur sans extrapolation. La validation de prix facturés et des statuts reste **NOT TESTED**.

**Suite sûre :** le sélecteur `scripts/select_v9_electroverse_checkpoint.py` doit choisir le nouvel artefact 14727835115 au prochain push ciblé `migration/v9/electroverse-resume-request.json` ; il vérifie branche/workflow/SHA/digest puis le ZIP/manifestes. Un nouveau run **n'est PAS encore lancé** et la reprise **entre runs** demeure manuelle. Ne pas modifier `main`, Production, les jointures IRVE, les statuts ni le fournisseur. Conserver le parent en secours ; vérifier l'unicité de sélection et l'absence d'exécution concurrente avant toute future collecte.


## 21 novembre 2026, 22:23 UTC — deuxième run réel Electroverse lancé (non terminé)

Demande explicite utilisateur « Ok lance le 2e run ». Contrôle préalable : aucun run de reconstruction actif dans les 40 derniers runs de `rebuild/v9-20261020`, artefact 14727835115 du run #44950136959 disponible, `expired=false`, digest `sha256:3622a321b6885434d7c4541199d2ffc58703c82f790a0511a6b3cf998e6e7aac` (expiration 21/12/2026). Le sélecteur `scripts/select_v9_electroverse_checkpoint.py` donne priorité aux artefacts `tcc-v9-electroverse-window` de la branche et valide run, SHA et digest avant récupération ; **le choix effectif du parent par le nouveau job doit être confirmé dans ses logs**.

Push atomique du seul `migration/v9/electroverse-resume-request.json` `mode=collect`, `basisRun=44950136959`, `basisArtifact=14727835115`, commit `1edd310ebbad1d554f7bbe3c8599678dacbd440f` depuis `3010111750b1764ccbbf85ab08a79f4e26fb7d94`.

[GitHub Actions #44956526554](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/44956526554), job `137005752077` : déclenché le 21/11/2026 à 22:23:44 UTC, **in_progress** au contrôle initial ; aucune conclusion encore. Périmètre : continuation de la campagne `FR:electroverse_full` sur cache 22 818 localisations, après 10 300 vérifications au dernier checkpoint et 1 700 PK `pending` au deuxième bloc (12 518 non revérifiées à l'échelle de la campagne). **Aucun gain n'est revendiqué pour ce nouveau run sans analyse de son ZIP**. Aucune modification du mapping IRVE, de la branche `main`, des workflows Production ni de Netlify. Automatisation entre runs séparés toujours non active. À clôture : vérifier conclusion, `collector_window_budget`, nouvel artifact, SHA du ZIP et 136 chemins, 128 shards, curseur, horaires et différences sous fenêtre uniquement. Ne jamais promouvoir automatiquement le checkpoint partiel.

