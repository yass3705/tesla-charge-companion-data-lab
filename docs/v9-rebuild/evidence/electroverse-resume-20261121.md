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
- Demande de test en lecture seule `d14a5326d0b06dcd09c7429d374694946d6aa56e`. [Run GitHub 44947769520](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/44947769520) **démarré**, résultat à relever explicitement avant toute proclamation PASS de la transmission GitHub.

## 4. Frontière d'automatisation : fait vs non fait

**Implémenté** : progression automatique entre fenêtres **dans une même exécution GitHub Actions** ; reprise **entre exécutions distinctes** sur le dernier checkpoint validé, à partir d'un nouveau push explicite de demande ; aucun recalcul des jointures IRVE.

**Non mis en service** : auto-déclenchement d'un nouveau workflow après chaque checkpoint, ou cron Electroverse permanent. Selon [GitHub Actions](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows), `workflow_dispatch`, `workflow_run` et `schedule` nécessitent que le workflow approprié existe sur la branche par défaut ; le `GITHUB_TOKEN` ne déclenche pas de nouveaux jobs sur un simple push automatisé. Aucun workflow sur `main` n'a été modifié pour contourner ces restrictions. Une automatisation permanente nécessitera un mécanisme approuvé et des preuves spécifiques de sécurité.

**Tests** : le code et les tests sont versionnés ; le résultat du run 44947769520 fait foi pour l'exécution distante. Tant que cette vérification n'est pas un succès confirmé, le transport de checkpoint reste `NOT TESTED / IN PROGRESS`. **Aucun appel massif fournisseur ni collecte ne résulte des commits ou de la demande `mode=verify`.** Les portes G2–G9 restent dans leur état antérieur.

## 5. Reprise sans perdre l'historique

Lire `AGENTS.md` et `memory/WORKING_AGREEMENT.md` puis ce rapport et `CURRENT.md`. Vérifier que `main` ne possède aucun déclencheur indirect pour la branche. Examiner le [run 44947769520](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/44947769520), puis le manifeste `checkpoint-manifest.json` de l'artefact parent. Si le test est `PASS`, un futur push explicite de demande `mode=collect` peut démarrer des fenêtres réelles sur la même branche, avec rapprochements et snapshots existants inchangés. Ne jamais relancer deux générations concurrentes.
