# Pilote GitHub Actions V9 — dossier de préparation (26 octobre 2026)

État : **préparé localement, non autorisé, non exécuté**. Actions Data Lab reste désactivé ; `main` et le site public sont inchangés. Les 120 handoffs du journal restent `github_handoff_unverified`.

## Préconditions à vérifier avant toute activation

1. Inventorier les déclencheurs réellement présents sur `origin/main` après `git fetch origin`, y compris `schedule`, `workflow_dispatch`, `workflow_run`, `push`, permissions et écritures inter-dépôts. Un YAML sur la branche de reconstruction ne sécurise pas `main`.
2. Neutraliser les anciens déclencheurs actifs sur `main` par une modification revue séparément, avec diff précis, contrôle de sécurité public et restauration préparée. Cette étape et toute modification de `main` requièrent autorisation explicite.
3. Vérifier que le pilote choisi travaille hors checkout, publie uniquement un artefact immuable et un rapport de provenance, sans push, déploiement, écriture Production ni secrets exposés. Vérifier les permissions effectives du jeton et l'absence de chaîne `workflow_run`.
4. Préparer une entrée figée et une source représentative avec contrat connu ; vérifier en local échec explicite, SHA, schéma, pagination complète et reprise. Ne pas utiliser de seuil historique de volume.

## Déroulé pilote proposé, après autorisation

1. Capturer SHA `main`, SHA de branche, état Actions et inventaire des runs actifs ; comparer les commits dans les deux sens.
2. Exécuter une seule collecte représentative via `workflow_dispatch` sur branche isolée et permissions minimales. Conserver run ID, logs expurgés, manifeste, SHA de chaque artefact et compteurs internes.
3. Vérifier les artefacts et le comportement d'échec/reprise ; comparer le contrat de sortie à la fixture et au replay local, sans juger les volumes historiques.
4. Confirmer qu'aucune écriture n'a eu lieu sur `main`, Production, Stable ou Updater Test. Désactiver le pilote si une garde échoue ; conserver les preuves et restaurer l'état initial.
5. Étendre par famille seulement après revue du premier run. Les autres handoffs restent non vérifiés jusqu'à leur propre preuve.

## Décision attendue ultérieurement

Autorisation distincte pour neutraliser les anciens déclencheurs sur `main`, réactiver Actions Data Lab et lancer le pilote borné. Aucune de ces opérations n'est entreprise dans ce dossier.
