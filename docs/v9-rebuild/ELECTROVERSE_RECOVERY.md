# Electroverse France — récupération des preuves G6.6b

Le workflow 6e crée un ZIP de sauvegarde avec les ZIP originaux inchangés, leur manifeste (artifacts, runs, commits, SHA-256, tailles, dates d'expiration) et contrôle la restauration. Le rapport 6e est séparé. Les preuves G5 consolidées, la génération nationale active, les archives tarifaires d'entrée, les sorties des audits G6 et la recette navigateur/service local sont incluses selon les pins du contrat 6e. Le périmètre ne prétend pas couvrir chaque ancien essai de collecte ou chaque pays.

**Conservation :** le ZIP Actions reste temporaire. Conserver une copie sur un espace privé autorisé (Mac ou stockage privé choisi par l'utilisateur) avant expiration, vérifier SHA-256 par rapport au rapport puis vérifier la restauration. Ne jamais ajouter le ZIP brut dans Data Lab public, Production, main ou les tuiles servies. Pas de nouveau dépôt, fournisseur ni activation.

Depuis le checkout Data Lab reconstruction épinglé, après copie privée du ZIP :

```sh
shasum -a 256 /chemin/prive/TCC_V9_Electroverse_FR_proofs_2026-11-26.zip
python -m scripts.audit_g66b6e_archive restore /chemin/prive/TCC_V9_Electroverse_FR_proofs_2026-11-26.zip /chemin/prive/restore-g66b6e
```

Le mode restore n'utilise ni GitHub Actions ni fournisseur. Il contrôle CRC, SHA et inventaire des ZIP restaurés. Le run de préparation contrôle en outre l'intégrité de la base de décisions G5, la recherche d'un match et d'un rejet (motifs/critères), les preuves du service local et le rejeu hors ligne des 1047 requêtes 6c via le chargeur d'archives locales injecté dans le test. Le runtime de Production reste au SHA épinglé et aucune donnée n'est promue.

Les tables/vues SQLite `v6_candidate_effective`, `criterion_pattern`, `v6_identity_matches`, `v6_national_disposition`, `v6_source_disposition` permettent de retrouver les motifs et les candidats pour la génération archivée. Le journal n'est pas encore rattaché à une génération réellement servie : G5/G6 global, G8/G9 restent ouverts. La clôture 6e exige une copie durable effectivement vérifiée, pas seulement la réussite d'un artefact Actions.
