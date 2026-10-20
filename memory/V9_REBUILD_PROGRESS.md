# Reconstruction V9 — état reprenable

Date : 20 octobre 2026. Branche locale Data Lab : `rebuild/v9-20261020`, base `0b1b9d75463121b6ff86f94764b32d3349ee3e3c`. Ce document est local tant que la branche n'est pas publiée.

| Phase | Statut | Preuve / tests | Blocage |
| --- | --- | --- | --- |
| G0 Sécurité | Validée localement | Actions Data Lab `enabled=false` vérifié par API ; trois runs actifs annulés ; aucun run actif au dernier contrôle ; références locales de restauration vérifiées | Réactivation seulement après retrait des anciens YAML actifs et contrôle du nouveau dispositif |
| G1 Méthodes | En cours | Registre statique `migration/v9/legacy-inventory.json` : 1 207 YAML, 757 fichiers scripts, secrets nommés, références et déclencheurs ; compilation Python, reproductibilité SHA-256 et scan public ciblé réussis | Correspondance source → module non terminée ; 367 indices de pays indéterminés ; deux références script sans fichier correspondant |
| G2 Workflows | À faire | — | G1 |
| G3 Données | À faire | — | G2 |
| G4 Production | À faire | — | G3 |
| G5 Jointures | À faire | — | G4 |
| G6 Tarifs | À faire | — | G5 |
| G7 Interface | À faire | — | G6 |
| G8 Recette technique | À faire | — | G7 |
| G9 Validation utilisateur | En attente | — | G8 et URL de préproduction |

## Sécurité et retour arrière

- Dépôt Data Lab GitHub Actions désactivé au niveau du dépôt par API (`PUT /repos/yass3705/tesla-charge-companion-data-lab/actions/permissions`, `enabled=false`), puis relu. Cette protection couvre aussi les déclencheurs indirects définis sur `main` ; une garde YAML de branche ne suffit pas.
- Trois runs encore actifs au moment de la désactivation, `39394415476`, `39394403942`, `39394373840`, ont reçu une demande d'annulation. La liste des runs non terminés était vide au contrôle suivant.
- Références locales restaurables dans le dépôt Data Lab : `refs/tcc-recovery/pre-rebuild-main-20261020` = `0b1b9d75463121b6ff86f94764b32d3349ee3e3c` ; `refs/tcc-recovery/pre-rebuild-local-20261020` = `e64fa057791bce9ad1516c28516fc0f02f440867`. Les deux objets sont lisibles (`git cat-file -t` = `commit`). L'ancien `main` distant et son historique n'ont pas été modifiés. Retour arrière : désactiver les nouveaux workflows, rétablir le SHA archivé sur une branche de restauration, vérifier les données et Actions, puis seulement envisager une promotion autorisée.
- Aucun push, aucune PR, aucune fusion, aucun déploiement Production. Les branches et modifications locales préexistantes restent intactes.

## Dépôts après `git fetch origin --prune`

| Dépôt | Branche locale | HEAD local | `origin/main` | Écart local → distant |
| --- | --- | --- | --- | --- |
| Production | `fix/de-ionity-snapshot-provenance` | `e5ea99cb0bbcdb35c921b914ba509c56846877c3` | `fba450da9092450fa7315d4c5b44e7e80394c8b4` | 0 / 192 ; `.DS_Store` non suivi |
| Data Lab | `docs/r9-electra-historical-ci-local` | `e64fa057791bce9ad1516c28516fc0f02f440867` | `0b1b9d75463121b6ff86f94764b32d3349ee3e3c` | 0 / 959 |
| Stable | `main` | `aad27bca174bbb62fc54affb93621071e2c0af43` | `97c841955b1978333ac1f076c9ac2ac0d4ed53cc` | 0 / 37 |
| Updater Test | `main` | `1fdb3051f0f65e51ce1917c1a97e3f082ae695a3` | `86d9a60bc454214f2f6d59c0f2819c26b7b89978` | 0 / 25 |

## Références métier conservées

Lire `memory/README.md` et les documents qu'il indexe avant chaque module. Les PR Production #134–#146 sont des références fonctionnelles, pas des changements à fusionner directement. Le flux Tesla/Mac Updater Test → Data Lab → Production est documenté comme validé le 15 octobre dans `memory/CURRENT.md` ; ne pas toucher à son acquisition. Les sources et données existantes restent inchangées pendant l'inventaire.

## Prochaine action exacte

Résoudre les 367 indices de pays indéterminés et les deux références script absentes (`audit_nl_ubitricity_payg_portal.py`, `reconcile_nl_ubitricity_payg_overlay.py`) depuis l'historique, puis compléter les destinations de chaque méthode utile et classer les autres. Le registre actuel est **statique et provisoire** : ses champs `migration_status=unreviewed` et `destination_module=null` interdisent de le traiter comme validation G1. Ne retirer aucun YAML avant ce contrôle. Garder Actions désactivé.
