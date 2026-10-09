# TCC — France, couverture tarifaire EVSE et rapprochements P1/P2/P3

**Répertoire permanent**, conservé sur la branche `main` du dépôt public **tesla-charge-companion-data-lab**. La tâche GitHub Actions **France EVSE tariff coverage — permanent archive** reconstruit les données après les validations IRVE, Electra eMSP, Electroverse et certains CPO français, ainsi qu'une fois par jour et sur demande.

### Accès rapide (toujours sur la version la plus récente)

| Fichier | Détails |
|---|---|
| [latest.json](latest.json) | Résumé complet : 8 combinaisons tarifaires, P1/P2/P3, statut actif, 167 puissances distinctes, comptages par source, erreurs/diagnostics, dates, empreintes de sources et qualité |
| [evse-latest.jsonl.gz](evse-latest.jsonl.gz) | **Une fiche par EVSE IRVE explicitement `en_service`** : identifiants, station, adresse/GPS, opérateur, puissance, catégorie tarifaire, correspondances P1/P2 et identifiants de toutes les offres eMSP publiées |
| [offers-latest.jsonl.gz](offers-latest.jsonl.gz) | Offres eMSP **complètes** et toutes leurs règles de tarification, par EVSE, avec provenance, identité originale, métadonnées, granularité/puissance et source tile |
| [cpo-prices-latest.jsonl.gz](cpo-prices-latest.jsonl.gz) | Preuves CPO directes : lignes tarifaires officielles exactes quand disponibles, sinon références vérifiables aux sources canoniques nationales dans ce dépôt (sans inventer de tarif par EVSE) |
| [history.jsonl](history.jsonl) | Journal append-only de **chaque vérification réussie**, dates, source fingerprints, chiffres P1/P2/P3, diagnostics et sommes de contrôle |
| [snapshots/](snapshots/) | Un récapitulatif JSON daté par exécution validée, accessible de manière permanente |
| [Workflow GitHub Actions](../../../.github/workflows/france-irve-tariff-coverage-archive.yml) | Fréquence, déclencheurs de vérification, contrôles et persistance du rapport |

### Règles de lecture

- **P1** : même EVSE après normalisation alphanumérique, toutes les ponctuations exclues.
- **P2** : complément des rapprochements documentés et **déjà publiés** dans les overlays Data Lab Electra et Electroverse, source `identityMode`.
- **P3** : rapprochement GPS/technique inédit, seulement après validation non ambiguë **EVSE par EVSE** : GPS <= 10 m, même nombre d'EVSE par station, tolérance AC `max(2 kW;10 %)`, DC `max(15 kW;10 %)`, CPO/adresse concordants, prix attribuables.
- **IRVE** : seul `en_service` explicite entre dans la revue. `hors_service`, `inconnu` ou statut dynamique absent ne signifie pas que la station est définitivement arrêtée; ils ne sont pas comptés comme actifs confirmés. Station active dès qu'un de ses EVSE est `en_service`.
- **CPO** : tarif direct/ad-hoc uniquement. Les offres Electra et Electroverse sont des **eMSP séparés** et n'écrasent jamais un tarif direct.
- Les 4 catégories avec prix CPO sont **exclusives**, leur somme correspond aux EVSE couverts par au moins une preuve CPO. Les autres 4 catégories conservent les offres eMSP même si le tarif direct du CPO manque.
- L'export est une **archive d'audit**. Il ne publie aucun tarif dans le runtime V9.

### Historique et fidélité

À chaque vérification réussie, les quatre fichiers `latest.*` sont actualisés et le récapitulatif est ajouté à `history.jsonl` et `snapshots/`. **Les anciennes versions des exports détaillés restent accessibles via l'historique Git de ces fichiers**. Les empreintes SHA-256 des exports et manifestes d'origine garantissent la traçabilité. Toutes les sources originales CPO et eMSP restent dans leurs répertoires Data Lab.

Les `.jsonl.gz` sont des fichiers texte JSON Lines compressés au format gzip. Sur macOS : `gzip -dc evse-latest.jsonl.gz | head` après téléchargement.

Création : 9 octobre 2026.
