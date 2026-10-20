# Reconstruction V9 — état reprenable

Date : 20 octobre 2026. Branche Data Lab : `rebuild/v9-20261020`, base `origin/main=def205b0de51dd55bd36a2e7fa672031364e6f75`. Commit de porte G1 : `15657f4a89c98e5e7c1d119c91c6cb55a891a913`. Premier lot G2 : `2003a7073919cb927f356cd022e56ea91fe634ff` (porte encore FAIL). Lot DOT-NL : `befd10bf0`. Lots Electroverse : `84c733cb3`, `05cd249f1`, `ddf3abe19`, puis base de reprise `eb7127785`. L'archive G0 précédente reste `0b1b9d75463121b6ff86f94764b32d3349ee3e3c`.

| Phase | Statut | Preuve / tests | Blocage |
| --- | --- | --- | --- |
| G0 Sécurité | Validée localement | Actions Data Lab `enabled=false` vérifié par API ; trois runs actifs annulés ; aucun run actif au dernier contrôle ; références locales de restauration vérifiées | Réactivation seulement après retrait des anciens YAML actifs et contrôle du nouveau dispositif |
| G1 Méthodes | **PASS** | `scripts/validate_v9_g1.py` : 1 207/1 207 workflows, 756/756 scripts, 536 inline, dix périmètres ; deux registres régénérés à l'identique ; dix tests ciblés et compilation réussis ; scan public `OK` ; commit `15657f4a8` | Sept méthodes dormantes partielles et cinq planifiées partielles attendent les tests d'exécution G2 ; Ubitricity NL désactivée et last-good conservé |
| G2 Workflows | **FAIL — migration partielle** | 1 207 anciens YAML retirés et restaurables au commit G1 ; deux nouveaux workflows en lecture seule ; orchestrateur isolé pour dix manifestes, Belgique NAP, DOT-NL et Electroverse daily/full/status/overlay ; 20 tests ciblés du lot status/overlay/orchestrateur PASS, dont fusion historique des partitions et finalisation nationale sans réseau ; `scripts/validate_v9_g2.py` : 15 workflows migrés, 16 sources, FAIL | 138 méthodes actives restantes ; overlay seulement testé sur contrats de sortie et rejet d'entrée partielle, pas encore sur reconstruction historique complète ni transfert des deux dépendances GitHub ; transfert full non vérifié en run Actions ; collectes live non lancées ; Actions désactivé |
| G3 Données | À faire | — | G2 |
| G4 Production | À faire | — | G3 |
| G5 Jointures | À faire | — | G4 |
| G6 Tarifs | À faire | — | G5 |
| G7 Interface | À faire | — | G6 |
| G8 Recette technique | À faire | — | G7 |
| G9 Validation utilisateur | En attente | — | G8 et URL de préproduction |

## Sécurité et retour arrière

- Dépôt Data Lab GitHub Actions désactivé au niveau du dépôt par API (`PUT /repos/yass3705/tesla-charge-companion-data-lab/actions/permissions`, `enabled=false`), puis relu. Cette protection couvre aussi les déclencheurs indirects définis sur `main` ; une garde YAML de branche ne suffit pas.
- Trois runs encore actifs au moment de la désactivation, `39394415476`, `39394403942`, `39394373840`, ont reçu une demande d'annulation. Deux commits de données Blink UK ont pourtant atteint `main` depuis des exécutions déjà lancées (`0ce74bc2c`, `def205b0d`) ; aucun YAML, script ni mémoire n'a changé. Après un nouveau `fetch`, Actions reste `enabled=false` et la liste des runs non terminés est vide. La branche de reconstruction a été rebasée sans conflit sur ce nouveau `main` ; les données distantes n'ont pas été écrasées.
- Références locales restaurables dans le dépôt Data Lab : `refs/tcc-recovery/pre-rebuild-main-20261020` = `0b1b9d75463121b6ff86f94764b32d3349ee3e3c` ; `refs/tcc-recovery/pre-rebuild-local-20261020` = `e64fa057791bce9ad1516c28516fc0f02f440867`. Les deux objets sont lisibles (`git cat-file -t` = `commit`). L'ancien `main` distant et son historique n'ont pas été modifiés. Retour arrière : désactiver les nouveaux workflows, rétablir le SHA archivé sur une branche de restauration, vérifier les données et Actions, puis seulement envisager une promotion autorisée.
- Branche de reconstruction Data Lab publiée seule sur `origin/rebuild/v9-20261020` après scan public réussi ; aucune PR, fusion ou déploiement Production. Les branches et modifications locales préexistantes restent intactes.

## Dépôts après `git fetch origin --prune`

| Dépôt | Branche locale | HEAD local | `origin/main` | Écart local → distant |
| --- | --- | --- | --- | --- |
| Production | `fix/de-ionity-snapshot-provenance` | `e5ea99cb0bbcdb35c921b914ba509c56846877c3` | `fba450da9092450fa7315d4c5b44e7e80394c8b4` | 0 / 192 ; `.DS_Store` non suivi |
| Data Lab historique | `docs/r9-electra-historical-ci-local` | `e64fa057791bce9ad1516c28516fc0f02f440867` | `def205b0de51dd55bd36a2e7fa672031364e6f75` | 0 / 961 |
| Stable | `main` | `aad27bca174bbb62fc54affb93621071e2c0af43` | `97c841955b1978333ac1f076c9ac2ac0d4ed53cc` | 0 / 37 |
| Updater Test | `main` | `1fdb3051f0f65e51ce1917c1a97e3f082ae695a3` | `86d9a60bc454214f2f6d59c0f2819c26b7b89978` | 0 / 25 |

Branche Production de reconstruction séparée, sans modification : `rebuild/v9-20261020` au SHA `fba450da9092450fa7315d4c5b44e7e80394c8b4`.

## Références métier conservées

Lire `memory/README.md` et les documents qu'il indexe avant chaque module. Les PR Production #134–#146 sont des références fonctionnelles, pas des changements à fusionner directement. Le flux Tesla/Mac Updater Test → Data Lab → Production est documenté comme validé le 15 octobre dans `memory/CURRENT.md` ; ne pas toucher à son acquisition. Les sources et données existantes restent inchangées pendant l'inventaire.

## Prochaine action exacte

G1 est validée sur `15657f4a8` : [registre définitif](../migration/v9/method-dispositions.json), [preuves de source](../migration/v9/script-workflow-evidence.json) et [audit](../migration/v9/G1_METHOD_AUDIT.md). Les 221 méthodes prioritaires et les autres méthodes historiques ont une disposition explicite. La comparaison avec le constructeur Production a inclus ses chemins et glob dynamiques ; les données existantes restent préservées. Le scan public a réussi. L'exception Ubitricity NL reste close, désactivée et séparée du candidat last-good. L'API GitHub confirme `Actions enabled=false`, zéro run actif et `origin/main=def205b0d`.

Poursuivre G2 par familles de sources, en priorité les méthodes planifiées ou explicitement consommées par Production. `v9_rebuild/orchestrator.py` traite dix manifestes opérateurs, Belgique NAP, DOT-NL et Electroverse daily/full sans écrire dans le checkout. `v9_rebuild/electroverse.py` copie le mapping, l'inventaire, le cache et ses 128 shards dans un espace isolé ; il lance les scripts historiques `electroverse_daily_delta_selector.mjs`, `electroverse_force_chunk_selection.mjs` et `electroverse_hybrid_refresh.mjs`. Les échecs gardent un checkpoint distinct des objets validés ; la reprise sélectionne seulement les PK en échec et les 128 fichiers doivent concorder avec le manifeste. L'orchestrateur vérifie l'ensemble des SHA avant de réutiliser un artefact précédent. Le workflow de collecte est manuel, en lecture seule, demande un identifiant de source exact et peut télécharger un ancien checkpoint ou jeu validé par run ID. Tous les essais Electroverse sont sur fixtures locales ; aucun appel API live ni recherche tarifaire.

Le validateur G2 est **FAIL** : 13 anciens workflows migrés, 14 sources enregistrées, 140 méthodes actives sans module. Le mode `full` est borné à un chunk historique par exécution et la reprise de deux chunks a réussi sur fixture. Le workflow retrouve automatiquement le plus récent checkpoint ou jeu validé de la même source et branche par l'API GitHub Actions ; les tests couvrent l'ordre des deux, expiration et branche incorrecte. Ce transfert n'a pas été exécuté sur GitHub Actions, qui reste désactivé : état `fixture_pass_github_handoff_unverified`, collecte live complète non encore prouvée. Le `daily` est `fixture_pass_live_pending`. Aucun seuil de volume n'est utilisé ; les nombres historiques ne servent qu'à décrire l'état, pas à rejeter une variation.

**Lot de reprise Electroverse status/overlay :** `v9_rebuild/electroverse_status.py` isole les 16 partitions, les checkpoints, la fusion via le script historique et la finalisation nationale ; un échec conserve les entrées bonnes et empêche l'artefact versionné. L'overlay historique est enveloppé par `v9_rebuild/electroverse_overlay.py`, qui exige un recensement national complet, une provenance de cache cohérente, la fenêtre historique de 72 h, les empreintes des tuiles et le rapport postconstruction. Le contrôle arbitraire `publishedOffers<5000` a été retiré du script historique, conformément à l'interdiction des seuils de volume. Le registre et l'orchestrateur savent aiguiller les deux modules. Aucun appel Electroverse live n'a été effectué. L'orchestrateur refuse l'overlay si les deux dépendances explicites ne sont pas présentes ; la récupération GitHub de ces deux états validés et une fixture complète du constructeur historique restent à faire. Les tests locaux ne valent pas preuve du transfert Actions. Preuves : `python3 -m unittest tests.test_v9_electroverse_overlay tests.test_v9_electroverse_status tests.test_v9_orchestrator -q` : 20 PASS ; compilation Python PASS ; `git diff --check` PASS ; `python3 scripts/public_safety_check.py .` : OK ; `gh api .../actions/permissions` : `enabled=false`.

**Prochaine opération exacte :** terminer le passage d'artefacts validés tariff-cache et status vers l'overlay dans le workflow unique, avec contrôle SHA du manifeste de collecte ; exécuter le constructeur historique sur une fixture nationale réduite couvrant les entrées techniques nécessaires, puis migrer les autres familles utiles, en priorité les consommateurs Production. Rejouer les tests ciblés et `scripts/validate_v9_g2.py` après chaque famille. Actions reste désactivé ; ne commencer G3 qu'après G2 PASS.
