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


## 22 novembre 2026 — audit de l'échec du deuxième run réel `44956526554`

**Run :** [44956526554](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/44956526554), job `137005752077`, SHA code `1edd310ebbad1d554f7bbe3c8599678dacbd440f` ; **completed/failure**, fin le 21/11/2026 à 23:08:20 UTC (22 novembre 2026 00:08 (heure de Paris)). Tests, scan public, sélection de parent `44950136959` / `14727835115`, SHA ZIP et validation du checkpoint **PASS**. La poursuite fournisseur a échoué : `RuntimeError: Incomplete tariff chunk retained; no automatic provider retry` dans `scripts/pilot_v9_tariff_chunks.py:102`. Manifeste source `partial_failure`, `reason=collector_exit_nonzero`. Le rapport source `reports/electroverse/hybrid-refresh-failures.json` indique **un seul échec `pk=4234003`, `error=fetch_failed`, `pages=1`**. Il ne prouve pas si le problème est réseau, autorisation, délai ou réponse fournisseur ; ne pas en inventer la cause.

**Archive réelle récupérée en lecture seule :** artefact [14729002853](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/44956526554/artifacts/14729002853), nom **`tcc-v9-electroverse-failure`**, taille **13 253 677 octets**, ZIP SHA-256 officiel et local **`2e1c1b9c4a8feeb3049f99db8e4df9ef9a1a24cc890359d0ea2aa1bb1a42ecf7`**, expire le 21/12/2026 à 23:08:15 UTC. Archive de 138 entrées, dont **136 fichiers de contenu tous vérifiés par empreintes SHA-256 et tailles du `checkpoint-manifest.json`**, 128 shards intègres. Fileset SHA-256 `789fbf0f55d3d38ba8d9a84695215f81edd0e374db08549f0e011c8d3df58dd8`. `headSha=1edd310ebbad1d554f7bbe3c8599678dacbd440f`, `runId=44956526554`, `state=partial_checkpoint`, `completeSnapshotValidated=false`. Le ZIP est cohérent en tant qu'archive d'échec ; **ce n'est PAS une collection complète ni un checkpoint automatiquement éligible à la sélection**.

**Comparaison du nouveau ZIP à l'artefact parent 14727835115 :** +**2 199** localisations vérifiées le 21/11 (`10 300 → 12 499/22 818`), soit **54,8 %** cumulées, reste **10 319**. `tariffHash` différent pour **971** des 2 199 PK nouvellement vérifiées ; **1 228** sans changement `tariffHash`. Zéro modification de `tariffHash` hors la fenêtre des 2 199 PK ; 22 818 lignes conservées, mapping IRVE et inventaire source octet-identiques. Il s'agit d'empreintes de contenu tarifaire, pas nécessairement de changements de prix final.

**Curseur :** `completed=[0,6000]`, `pending.offset=12000`, `pending.pks=5501`. Les 6 000 localisations du deuxième bloc sont terminées ; dans le troisième, 499 sont vérifiées, et la PK échouée `4234003` est conservée au début des 5 501 en attente. La présence de cette PK dans `pending` démontre qu'elle n'a pas été considérée comme traitée.

**Risque de relance actuelle :** le sélecteur `scripts/select_v9_electroverse_checkpoint.py` ne choisit que les artefacts `tcc-v9-electroverse-window`/`-complete` associés à des runs `success`; **il ignore l'artefact `-failure`**. Sans correction et preuve de validation de sa reprise sûre, une nouvelle demande `collect` choisirait le parent plus ancien `14727835115` et pourrait **rejouer 2 199 vérifications** (gaspillage d'appels). **Ne pas lancer de troisième run en l'état.**

**Action suivante conseillée :** isoler une procédure de récupération contrôlée des artefacts `-failure` lorsque le checkpoint et sa filiation sont intègres : vérification ZIP + file-set + mapping + provenance, statut partiel et raison d'échec, `completed/pending` cohérents, progression et absence de lignes hors fenêtre, conservation de PK échouées. Adapter les tests/choix de parent pour préserver les 2 199 vérifications ; tester sans appel fournisseur, puis seulement lancer la reprise avec autorisation. Ne pas assouplir les contrôles ni traiter `fetch_failed` comme succès. Les jointures, Production, main et G2–G9 restent inchangés.


## 22 novembre 2026 00:33 CET — reprise de l'artefact d'échec vérifiée sur GitHub, collecte relancée

**Problème initial :** run #44956526554 terminé `failure`, mais artefact 14729002853 préservant **2 199 vérifications** nouvelles ; le sélecteur ignorait cette archive `-failure` et aurait retraité inutilement 2 199 PK depuis l'ancien checkpoint `14727835115`.

**Correctif `eb6849414bafca67764f282c52bed5df86e03404`** sur `rebuild/v9-20261020` : `scripts/select_v9_electroverse_checkpoint.py` autorise uniquement **l'artefact d'échec précisément audité** (run `44956526554`, artifact `14729002853`, head `1edd310ebbad1d554f7bbe3c8599678dacbd440f`, ZIP sha `2e1c1b9c4a8feeb3049f99db8e4df9ef9a1a24cc890359d0ea2aa1bb1a42ecf7`) et refuse tout nouvel échec non audité plus récent. `scripts/verify_v9_electroverse_failed_parent.py` compare l'intégralité des deux ZIP, SHA/tailles de 136 fichiers, 128 shards, identité du mapping et inventaire, curseur monotone, PK horodatées, `tariffHash` hors fenêtre, rapport fournisseur et PK échouée conservée en attente. Le workflow de branche `.github/workflows/v9-electroverse-resume.yml` impose la preuve **avant toute reprise fournisseur**. Trois tests de sélection ajoutés ; aucune politique de prix ni rapprochement IRVE modifiés.

**Validation distante :** [run #44962135060](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/44962135060), job `137023060349`, code `0da5afaba6c7c2833e86db65f6eb9b1e333029dc`, `completed/success`. **13 tests PASS**, `Public safety scan: OK` ; sélecteur renvoie `state=recovered_failure`, `run=44956526554`, `artifact=14729002853`. Parent et descendant ZIP sha OK ; script de preuve rapporte `completed=[0,6000]`, `newlyChecked=2199`, `totalChecked=12499`, `remaining=10319`, `pendingOffset=12000`, `pending=5501`, `failedPk=4234003`, `tariffHashChanged=971`. `verify_checkpoint` a ensuite confirmé le contenu et mapping intègres. **Aucun appel fournisseur** pendant ce run `mode=verify`.

**Reprise réelle :** sur autorisation utilisateur « D'accord lance la suite », push du seul fichier `migration/v9/electroverse-resume-request.json` en `mode=collect`, parent explicitement demandé `basisRun=44956526554`, `basisArtifact=14729002853`, `verifiedRecoveryRun=44962135060`; commit `5fffc5bbf931533d2b177d414484e9a9f6a78167`. Nouveau [run #44962339493](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/44962339493), job `137023677341`, déclenché le 21/11/2026 à 23:33:03 UTC, **in_progress** au dernier contrôle ; étape fournisseur et progression **non encore démontrées**. Ne pas inventer de gain avant vérification de l'artefact sortant. Aucune exécution concurrente observée avant push. Aucun changement sur `main`, Production, Netlify, les statuts ni les jointures.

**Prochain contrôle exact** : ouvrir les logs et le nouvel artefact du run `44962339493`, s'assurer que le parent choisi est `14729002853`, confirmer la preuve `recovered_failure`, examiner `collector_window_budget` vs `collector_exit_nonzero`, valider ZIP SHA, fileset, 128 shards, dates `checkedAt`, `pending`, échecs et tarifications hors fenêtre. Ne pas lancer de quatrième run automatiquement ni assimiler `success` GitHub à collecte complète. Tous les échecs supplémentaires non audités doivent rester bloquants afin d'éviter le retraitement.


## 22 novembre 2026, 00:53 CET — audit réel du troisième run de continuation `44962339493`

**Run et mode :** [GitHub Actions #44962339493](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/44962339493), job `137023677341`, code `5fffc5bbf931533d2b177d414484e9a9f6a78167`, du 21 novembre 2026 23:33:03 UTC au 21 novembre 23:53:08 UTC, **`completed/failure`**. 13 tests, safety scan, sélection du parent et contrôle des deux archives (parent vérifié et enfant d'échec) **PASS**. Le sélecteur a effectivement choisi l'artefact `14729002853`, `state=recovered_failure`, et la preuve avant fournisseur a bien contrôlé `newlyChecked=2199`, `totalChecked=12499`, `pending=5501`, `failedPk=4234003`. **Le fix de récupération a fonctionné, sans retraiter les 2 199 PK du run précédent.**

**Arrêt de l'acquisition :** l'étape `Continue bounded windows with the historical collector` est **FAILURE** avec `RuntimeError: Incomplete tariff chunk retained; no automatic provider retry`, `manifest.json.status=partial_failure`, `reason=collector_exit_nonzero`. `reports/electroverse/hybrid-refresh-failures.json` rapporte **3 PK** `426269`, `426271`, `426272` en `fetch_failed` (pages=1 chacune). C'est un autre incident que la PK `4234003`, désormais traitée ; ne pas déduire un motif fournisseur précis sans preuve. Les trois nouvelles erreurs restent `pending`.

**Artefact conservé, sans promotion :** `14730224631` `tcc-v9-electroverse-failure`, [archive sur le run](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/44962339493/artifacts/14730224631), taille **13 256 967 octets**, SHA-256 ZIP GitHub et fichier téléchargé **`92ffb6c827fdfe805518746aa0eba13730a8f26ef6254ef9b69e149de655e5c1`**, expire le **21 décembre 2026 à 23:53:01 UTC**. Archive **138 entrées**, dont **136/136** fichiers listés dans son manifeste SHA-256 + tailles conformes, **128 shards** ; `checkpoint-manifest.json` : `state=partial_checkpoint`, `completeSnapshotValidated=false`, `runId=44962339493`, `headSha=5fffc5bbf931533d2b177d414484e9a9f6a78167`, file-set SHA-256 **`1969e550c139db2dfdad6f0709b0bc4084002d424a6d9e66c90ccc56cb6d4fa9`**.

**Comparaison intégrale des données au parent 14729002853, validée en lecture seule :**
- Mapping `irve_location_mapping.json` et inventaire `france-current.json` **octet pour octet inchangés**, population **22 818** entrées dans les 128 shards, aucune création ni suppression.
- `checkedAt` : **+697** PK nouvellement horodatées, toutes sorties de l'ancien `pending` ; **aucune modification hors ces 697**, aucune nouvelle ou ancienne clé supprimée. Comptage de campagne **12 499 → 13 196 / 22 818 (57,83 %)**, reste **9 622**.
- **498** enregistrements sources ont changé (et leur `tariffHash`), **199** sont identiques après contrôle. Zéro modification tarifaire en dehors des 697 PK vérifiées. Un hash changé ne garantit pas un prix au kWh changé.
- Curseur `completed=[0,6000]` inchangé, `pending.offset=12000`, `pending.pks: 5501 → 4804` ; 697 PK retirées de `pending`, 0 PK nouvellement introduites. `4234003` ne figure plus dans `pending` et est revérifiée.
- L'archive est une **preuve de progression en échec**, jamais un état `complete`, ni source directement promotionnable en Production.

**Décision de sécurité :** le sélecteur actuellement en branche n'a autorisé que l'artefact d'échec précis `14729002853`. Il **refusera tout nouveau `-failure` plus récent non audité**, comme `14730224631`, et **ne faut pas relancer en l'état** : reprise depuis un ancien checkpoint provoquerait une répétition des 697 appels réussis ou serait bloquée par les gardes. Prochaine action : passer de la pin manuelle d'un échec à la validation automatique stricte de chaque checkpoint successeur (identités, fileset, monotonicité des `checkedAt`, 128 shards, absence de mutation hors fenêtre, provenance, rapport et PK échouées toujours pending), sans accepter de fausse génération complète ni rejouer l'ancien. Effectuer une validation `verify` sans appel fournisseur avant toute collecte supplémentaire. Pas de relance ni de changement Production/`main` dans cet audit.

