# Mémoire technique TCC V9

Point d'entrée versionné pour reprendre le travail depuis Codex Mac ou ChatGPT mobile via GitHub. Ce répertoire est un **index et un journal**, pas une copie des dossiers `docs/`, `reports/` ni des données. Les liens ci-dessous pointent vers la source de référence dans chaque dépôt. Une affirmation ancienne reste datée ; vérifier le code, les artefacts et les commits avant de la présenter comme déployée.

## Carte des quatre dépôts

| Dépôt | Rôle | Références |
| --- | --- | --- |
| [Data Lab](../README.md) | Collecte publique, preuves, données nationales et règles candidates. | [README](../README.md), [inventaire tarifaire](../docs/global-tariff-calculation-inventory-and-rollout-20261009.md) |
| [Production](https://github.com/yass3705/tesla-charge-companion-production) | Runtime V9, adaptateurs, snapshots épinglés, contrôles et publication. | [architecture](https://github.com/yass3705/tesla-charge-companion-production/blob/main/docs/ARCHITECTURE.md), [état](https://github.com/yass3705/tesla-charge-companion-production/blob/main/docs/STATUS.md) |
| [Stable](https://github.com/yass3705/tesla-charge-companion-stable) | Référence V7/V8, prévisualisation et base de retour arrière pendant la migration. | [README](https://github.com/yass3705/tesla-charge-companion-stable/blob/main/README.md), [historique](https://github.com/yass3705/tesla-charge-companion-stable/blob/main/CHANGELOG.md) |
| Updater Test (`tesla-stations-updater-test`, privé) | Prototype et sources héritées non encore migrées par pays. | Consulter sa documentation localement avec accès autorisé ; aucun contenu privé n'est recopié ici. |

Le flux cible est : preuve et collecte dans Data Lab → validation et épinglage par commit/artefact → compilation du snapshot dans Production → tests et promotion explicite. Le dépôt Stable sert de référence et de retour arrière. Voir l'architecture Production pour les détails Cloudflare et les règles de publication.

## Décisions et règles métier : sources de vérité

- [Libellés et critères calculé / ambigu / incalculable / indisponible](../docs/v9-pricing-result-labels-policy-2026-10-10.md). Décision par EVSE/prise et par offre ; une offre conflictuelle ne fournit aucun montant au classement.
- **Instruction utilisateur du 11/10/2026 pour V9 :** présenter « Tarif incalculable » lorsqu'une offre identifiée ne permet pas un calcul fiable ; garder « ambigu » comme diagnostic interne si utile. [CURRENT.md](CURRENT.md) consigne l'écart constaté dans le code UI. Le document de libellés antérieur doit être harmonisé avant toute modification métier.
- [Périmètre des overlays Electroverse et Electra](../docs/tcc-v9-multicountry-emsp-overlays-scope-2026-10-11.md). Les offres eMSP restent distinctes du direct CPO ; aucune substitution sans preuve.
- [Calcul tarifaire global et déploiement progressif](../docs/global-tariff-calculation-inventory-and-rollout-20261009.md), [analyse détaillée](../docs/tcc-global-tariff-deep-analysis-20261010.md) et [revue des frais différés](../reports/tariff-scenarios/after-minutes-production-review-2026-10-11.md).
- [Priorité de source DOT-NL](../docs/netherlands-dotnl-tariff-source-priority-2026-10-11.md), [règles Electra officielles](../docs/electra-v9-tariff-rules-official-2026-10-10.md) et [SOP France IRVE](../docs/france-irve-tariff-coverage-frozen-sop-v1.md).
- [Filtre des EVSE actifs](../docs/france-irve-active-only-evse-reconciliation-policy.md) : l'audit France compte seulement les EVSE explicitement `en_service`, sans supprimer les autres des archives. La SOP fixe les preuves P1/P2/P3 et interdit d'attribuer par simple proximité un prix hétérogène à une station.
- [Résolution des frais différés](../reports/tariff-scenarios/after-minutes-resolution-2026-10-11.md) et [revue de production](../reports/tariff-scenarios/after-minutes-production-review-2026-10-11.md) : six offres vérifiées ; 78 offres Electra eMSP restent incalculables faute de nature du temps facturé.
- [Rapprochement des captures Electra](../docs/electra-user-app-pricing-reconciliation-2026-10-10.md) et [état UK Midhope](../docs/uk-midhope-release-readiness-2026-10-10.md) : décisions propres aux offres et corrections ultérieures à lire jusqu'à la fin des documents.
- Les règles de sûreté publique et de données sensibles figurent dans le [README Data Lab](../README.md). Ne placer ici que des résumés et liens publiables.

## Reprise après interruption ou modification depuis mobile

1. Lire [État courant](CURRENT.md), puis ce fichier et les sources citées pour le sujet concerné. La date et les SHA locaux sont un constat, pas une preuve que GitHub est identique. Depuis ChatGPT mobile, lire les fichiers de `main` et examiner les PR ouvertes ; depuis Codex Mac, suivre aussi le [fichier d'instructions commun](../AGENTS.md).
2. Dans **chacun** des quatre dépôts, relever `git branch --show-current`, `git status --short`, `git log -1 --oneline` et les changements distants avec `git fetch origin` lorsque le réseau est autorisé. Ne jamais écraser un arbre local modifié.
3. Si ChatGPT mobile a modifié GitHub, comparer `git log --oneline HEAD..origin/main` et `git diff --stat HEAD..origin/main` avant d'intégrer ; utiliser `git pull --ff-only origin main` seulement sur branche propre et sans divergence. En cas de divergence, examiner les commits et résoudre explicitement sur une branche de travail.
4. Relire les documents source affectés, les tests/rapports et les éventuelles PR. Reprendre depuis les preuves consignées ; ne relancer un audit complet que si ses entrées, règles, code ou risques ont changé. Mettre à jour `CURRENT.md` avec preuve, statut exact et prochaine action ; ajouter une entrée datée à `HISTORY.md` pour toute décision ou transition notable. Si une règle change, modifier d'abord son document source existant, puis mettre l'index à jour.
5. Avant toute publication : vérifier les changements, les tests utiles, l'absence de secrets et le périmètre du commit. La synchronisation distante reste une action distincte soumise à accord.

`git fetch` actualise seulement les références distantes. Il ne met pas à jour les fichiers du Mac ; pour lire la dernière version sans pull, utiliser `git show origin/main:chemin/du/fichier` ou `git diff HEAD..origin/main -- chemin/du/fichier`.

Au début d'une session mobile, ouvrir `memory/README.md` puis `memory/CURRENT.md` sur GitHub et lire les PR pertinentes. À la fin, conserver les décisions et preuves dans les fichiers sources et la mémoire, sur la branche ou PR du travail. Une décision qui reste seulement dans la conversation doit être annoncée **non synchronisée** ; la session suivante ne doit pas la traiter comme une règle publiée. À la fin d'une session Codex, consigner dans `CURRENT.md` les SHA, tests, blocages et prochaine action, puis vérifier le statut Git. Le contenu devient commun aux appareils après publication GitHub ; une branche non fusionnée doit être citée explicitement.
