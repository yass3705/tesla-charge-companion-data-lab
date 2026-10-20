# Reconstruction V9 — état reprenable

Date : 20 octobre 2026. Branche Data Lab : `rebuild/v9-20261020`, base `origin/main=def205b0de51dd55bd36a2e7fa672031364e6f75`. Commit de porte G1 : `15657f4a89c98e5e7c1d119c91c6cb55a891a913`. L'archive G0 précédente reste `0b1b9d75463121b6ff86f94764b32d3349ee3e3c`.

| Phase | Statut | Preuve / tests | Blocage |
| --- | --- | --- | --- |
| G0 Sécurité | Validée localement | Actions Data Lab `enabled=false` vérifié par API ; trois runs actifs annulés ; aucun run actif au dernier contrôle ; références locales de restauration vérifiées | Réactivation seulement après retrait des anciens YAML actifs et contrôle du nouveau dispositif |
| G1 Méthodes | **PASS** | `scripts/validate_v9_g1.py` : 1 207/1 207 workflows, 756/756 scripts, 536 inline, dix périmètres ; deux registres régénérés à l'identique ; dix tests ciblés et compilation réussis ; scan public `OK` ; commit `15657f4a8` | Sept méthodes dormantes partielles et cinq planifiées partielles attendent les tests d'exécution G2 ; Ubitricity NL désactivée et last-good conservé |
| G2 Workflows | **FAIL — migration partielle** | Les 1 207 anciens YAML sont retirés sur la branche et restaurables au commit G1 ; deux nouveaux workflows en lecture seule ; orchestrateur isolé pour dix sources à manifeste et Belgique NAP ; onze tests unitaires PASS, dont pagination complète/incomplète, concurrence et exception isolée ; essai technique `FR:sdey` PASS vers `/tmp` avec contrôle du contrat ; `scripts/validate_v9_g2.py` exécuté | 143 méthodes actives restantes non migrées ; Actions Data Lab toujours désactivé |
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

Poursuivre G2 par familles de sources, en priorité les méthodes planifiées ou explicitement consommées par Production. Le nouveau `v9_rebuild/orchestrator.py` traite dix manifestes opérateurs et le collecteur Belgique NAP sans écrire dans le checkout ; dix anciens wrappers sont couverts exactement. La Belgique utilise le script et la pagination existants, avec contrôle technique de chaque page en fixture ; aucun appel réel n'a été fait sans jeton local. Le validateur G2 est **FAIL** sur 143 méthodes actives à migrer et sur le registre explicitement partiel. **Prochaine opération exacte :** adapter `.github/workflows/netherlands-dotnl-canonical.yml` du commit `15657f4a8` en module `national/nl_dotnl`, en réutilisant `dotnl_netherlands_build.py`, `dotnl_netherlands_runtime.py`, `dotnl_netherlands_access_patch.py` et les intégrateurs exacts avec sorties isolées. Tester fichiers, pagination et priorité tarifaire nationale. Retirer du vieux YAML les assertions de volume (`stationCount > 70000`, nombre de connecteurs tarifés, plafond Ubitricity 3 670) ; garder seulement les vérifications techniques de format, identité, intégrité et fin de pagination. Enchaîner avec les plateformes eMSP puis autres CPO. Préserver le flux Tesla/Mac, en supprimant dans son futur adaptateur les gardes de volume interdites sans toucher à Updater Test. Ajouter planification seulement quand le registre et les tests G2 passent. Ne pas réactiver Actions ; ne pas commencer G3 avant G2 PASS.
