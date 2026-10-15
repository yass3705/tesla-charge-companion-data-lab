# TCC V9 — Migration des dépendances amont vers Data Lab et Production (13/10/2026)

## Delta validé au 15/10/2026 (les constats du 13/10 ci-dessous sont historiques)

| Chaîne | Transfert technique | Legacy conservé | Preuve / suite |
| --- | --- | --- | --- |
| Runtime V9 et Pages | Production #112 `29b0ae54`, Data Lab #315 `20ad7b21` et archive seed `0181a0fb` ; publication Pages Production #38756331049 réussie. | Stable Pages pour V7/V8 et rollback ; aucun changement Cloudflare. | Shell public et manifeste Production : snapshot `2026-10-15-v9-datalab-baseline-candidate`, 2 463 fichiers. Contrôler les données Tesla courantes avant d'archiver Stable Pages. |
| France IRVE | Production #104 `99093d82`, Data Lab lot validé #314. | Sync Stable pour son propre site. | Parité France 48 083 stations/165 848 couples/169 165 connecteurs ; génération nationale récente et 449 BUMP non promus. |
| Italie et FX | Data Lab #312/#313, Production #110/#111. | FX Stable pour V8. | Build complet #38755773180 ; PUN #301 reste brouillon séparé. |
| Pays-Bas DOT-NL | Data Lab canonical quotidien, Production consommateur Data Lab. | Stable #146 `be4cfbd9` manuel/archives. | Runs Data Lab #38384698477, #38537318827, #38704887974 réussis. |
| Suisse national | Data Lab #316 `fc3cfd2e` : cron 23:20 UTC et garde last-good ; bundle + intégration existent. | Stable constructeur CH quotidien encore nécessaire au runtime miroir. | CI PR #38757135676 réussie ; valider le run `main` et le consommateur Production avant retrait. |
| Tesla/Mac | Acquisition inchangée dans Updater Test. | Export courant et sync transitent encore par Stable. | Dernier catalogue archivé dans le baseline Data Lab ; raccordement courant Production à créer sans déplacer Mac. |

**Statut global : migration technique incomplète.** L'indisponibilité Electroverse et les 429 REVE sont des incidents de collecte distincts ; les processus déjà transférés ne sont pas remis en cause.

## Décision utilisateur et portée
Ne supprimer **aucun** workflow d'Updater Test avant présentation ici de sa liste et accord. Avant toute classification comme doublon ou inutile, suivre toute la chaîne jusqu'aux données effectivement chargées par le build et le runtime du dépôt `tesla-charge-companion-production`. La cible : **Data Lab = source unique des données CPO/eMSP et données d'entrée validées ; Production = code, compilation, validation et publication V9 ; Updater Test = acquisition Mac/Tesla distincte si nécessaire ; Stable = archive/parité optionnelle**, pas étape obligatoire de publication.

## Preuves vérifiées dans Production main
- `config/refresh-policy.json` : snapshot de développement `2026-10-13-be-energyvision-official-cpo-candidate`, Data Lab SHA `94d4fc6785a0c1d2ed4df1d01b5a30d203bd4cd3`; promotion manuelle, pas de déploiement automatique.
- Le snapshot a dix entrées dataset : **TESLA, ES, IT** sont actuellement `primarySource=stable` ; FR, NL, CH, MA, DE, UK, BE sont `primarySource=dataLab`. La présence des métadonnées `legacyUpdater` et `germanyRecovery` ne prouve pas à elle seule une lecture active.
- `scripts/build_snapshot.py` utilise réellement Stable pour : copier le répertoire entier `v9-production-runtime` dans `runtime`, copier `assets`, `data`, `v9-production-shell`, certains fichiers PWA, une base historique `france-bump-offers.json`, ainsi que la configuration du shell. Des overrides et adaptateurs de Production remplacent ensuite certaines parties du runtime ; il est donc **incorrect** de conclure que seules ES/IT/Tesla dépendent de Stable.
- La construction Production actuelle fournit `--stable` et `--datalab` à `scripts/build_snapshot.py` ; `.github/workflows/v9-refresh-candidate-dry-run.yml` checkout Stable au SHA épinglé, et exécute des tests de parité ainsi que des tests exigeant son arborescence.
- Le collecteur REVE historique `reve-v2-monthly-production-refresh.yml` pousse vers **Stable**, pas Production ; le snapshot Production épingle Stable immuablement. Une publication de données dans Stable ne change donc pas automatiquement le build Production. Ne pas classer le workflow comme consommé par Production uniquement à cause de cette publication.

## Grille de migration sans perte
1. **Runtime/shell** : inventorier les fichiers Stable copiés avant/après overrides, leur présence dans le bundle final et les appels runtime ; migrer le socle requis sous contrôle Production en gardant les comparaisons de parité historiques séparées.
2. **TESLA** : maintenir l'acquisition Mac dans Updater Test ; tracer l'export exact vers une entrée validée Data Lab et préserver la priorité Tesla/SuC à dix jours (exception MA). Ne pas remplacer le catalogue Mac par SuC sans équivalence.
3. **ES / REVE** : vérifier et transférer les stations, EVSE, tuiles, grilles tarifaires et offres du snapshot réellement utilisé ; comparer manifestes et SHA, puis compiler un candidat Production depuis Data Lab, sans modifier le pin de développement ni le live avant réussite.
4. **IT** : même inventaire, identification des fichiers/consommateurs réellement conservés depuis Stable ; contrôle des CPO nationaux et des offres par puissance.
5. **Données historiques FR, etc.** : détecter les fichiers hérités du runtime Stable qui restent servis même si `primarySource=dataLab` pour le pays ; pour chaque élément préciser propriétaire, couverture, politique de prix et chemin final.
6. **Gates** : comparaisons station/EVSE exact, Type 2/CCS/prise normale, statut actif, puissance, montants Direct vs eMSP, erreurs fail-closed, empreintes et tests build/smoke. Les données validated doivent survivre aux pannes upstream.
7. **Suppression** : présenter la liste exacte des YAML d'Updater Test à l'utilisateur **avant chaque suppression**. Ne retirer que les workflows sans lecteur Production ni rôle de secours nécessaire, après migration et validation effectives.

## Statut
**Audit et plan seulement**, pas de migration de données certifiée, aucune suppression de workflow dans cette passe. Les métadonnées seules ne constituent pas une preuve de remplacement. Suivre les validations avant de modifier le pin ou la publication live.
