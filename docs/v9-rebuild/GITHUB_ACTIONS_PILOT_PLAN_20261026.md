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

## Pilote concret retenu et preuve locale

Source unique proposée : `FR:ionity_direct_family`, module `ionity_family`, sans secret requis. Elle réutilise les scripts archivés FR/DE/IT/GB ; aucune recherche de prix ni nouvel endpoint. Le workflow dédié proposé est `v9-ionity-pilot.yml`, conservé uniquement comme copie inactive dans le dossier de revue. Le workflow commun existant `v9-collect.yml` n’est pas le pilote retenu. La branche cible est `rebuild/v9-20261020` ; ne jamais lancer le pilote sur `main`.

Contrôles exécutés le 26 octobre : tests offline `tests.test_v9_ionity` (sortie vide techniquement valide, famille complète, échec sans publication partielle), `tests.test_v9_orchestrator`, normalisation canonique et jointures exactes : 31 tests PASS. Le dry-run ci-dessous retourne exactement `{"status":"dry_run","sources":["FR:ionity_direct_family"]}`. Il ne collecte rien et ne prouve pas le transfert GitHub.

```sh
python3 -m v9_rebuild.orchestrator --source FR:ionity_direct_family --out /tmp/tcc-v9-ionity-pilot-dry-run-20261026 --workers 1 --attempts 1 --dry-run
```

Avant la future exécution autorisée, limiter le job pilote à cette source et cette branche, régler `persist-credentials: false` sur checkout, épingler les actions tierces sur leurs SHA revus, fixer `workers=1`, `attempts=1` et une durée maximale. Conserver `contents: read`, `actions: read`, zéro secret de publication et zéro permission d'écriture Production. Ne pas transférer de répertoire `.git`, cache de navigateur ou environnement dans les artefacts.

Commande de déclenchement proposée, **NON exécutée et à utiliser seulement après la neutralisation revue de main et autorisation explicite** :

```sh
gh workflow run v9-ionity-pilot.yml --repo yass3705/tesla-charge-companion-data-lab --ref rebuild/v9-20261020 -f source=FR:ionity_direct_family
```

Après ce run, télécharger l'artefact propre à la source hors checkout, vérifier tous ses SHA et le rapport de statut, tester l'import Production local isolé et conserver le run ID. En cas d'échec, ne pas promouvoir de sortie partielle ; conserver le dernier snapshot validé et remettre Actions dans son état désactivé selon le plan autorisé.

Le contrôle administratif en lecture seule du 26 octobre confirme encore `enabled=false`. `origin/main` Data Lab est `def205b0de51dd55bd36a2e7fa672031364e6f75` au fetch de cette recette. Aucun workflow actif n'a été modifié, aucun run déclenché et aucun handoff n'est promu en PASS.

## Proposition concrète inactive à examiner

- [Workflow pilote](pilot/v9-ionity-pilot.yml.example) : source et branche verrouillées, 20 minutes, un worker, une tentative, aucune liaison de secret, permissions en lecture, actions épinglées par SHA vérifiés via API, artefacts succès/échec séparés et rétention de sept jours.
- [Patch proposé pour main](pilot/MAIN_NEUTRALIZATION_PROPOSAL.patch) : déplace sans changer leur contenu les 1 207 anciens fichiers de workflow hors de `.github/workflows`, puis ajoute uniquement le pilote gardé. Ce fichier est une pièce de revue, jamais appliquée à main ni à l’index réel.
- [Rapport de contrôle](pilot/REVIEW_20261026.json) : application et réversibilité vérifiées exclusivement dans un index Git temporaire basé sur `def205b0de51dd55bd36a2e7fa672031364e6f75`. Aucun ref ni fichier actif modifié.

GitHub exige que la définition du workflow manuel existe sur la branche par défaut pour recevoir `workflow_dispatch` ([documentation officielle](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#workflow_dispatch)). Après autorisation seulement, la même définition devra donc être installée sur main et sur la branche de reconstruction ; sa garde interdit l’exécution sur main.

Avant activation, revérifier le SHA de main, les workflows enregistrés, les runs actifs et les autres branches susceptibles de déclencher un workflow ; cette proposition ne prouve pas leur neutralisation. Tout écart impose une nouvelle revue du patch. Pour un retour arrière, désactiver Actions **avant** de restaurer les anciens workflows, afin de ne pas relancer leurs programmations. Ce dossier n’autorise aucune de ces opérations.

Rejouer la vérification offline depuis Data Lab : `python3 scripts/check_v9_inactive_pilot.py`. Le script vérifie les SHA revus, l’archive exacte de chaque workflow et le retour au tree initial dans un index temporaire ; il ne vérifie pas l’état GitHub distant, n’active rien et ne remplace pas l’autorisation.
