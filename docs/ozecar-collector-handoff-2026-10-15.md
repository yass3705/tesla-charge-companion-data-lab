# OZECAR France — transfert de collecte candidat (15 octobre 2026)

Cette branche ajoute à Data Lab le collecteur national OZECAR déjà exécuté dans Updater Test, sans modifier les offres ni les prix Production. Le workflow historique reste actif jusqu'à deux exécutions Data Lab comparables et à la vérification des consommateurs.

## Référence et comparaison

| Élément | 8 octobre | 15 octobre |
| --- | ---: | ---: |
| Snapshot Updater Test | `d407aa12361dfeabac306e750f1210a7c43c0089` | `899929bb6cd444ed2866a853bb4c7b329273c727` |
| Run réussi | `37770196420` | `38711403033` |
| EVSE exacts / stations exactes | 269 / 269 | 269 / 269 |
| Tarifs directs relevés / non résolus | 246 / 23 | 246 / 23 |
| Écart d'IDs, prises, puissance, composants tarifaires | 0 | 0 par rapport au 8 octobre |

Le blob historique du 15 octobre est `f369c17967df88c6c248e5d7b5a155c0c256a5f0` et son rapport `5a9bdac451722258321e1b0c4db2f7ee7503be8a` (SHA Git de blobs dans Updater Test). Le snapshot Data Lab France statique `045283b7c` contient ces 269 IDs et 269 stations, chacun à 22 kW avec Type 2 déclaré ; il ne fournit pas pour autant les 246 tarifs directs observés sur la surface publique Monta. La preuve Corse `data/operator_direct/ozecar_official_corse.json` décrit une portée régionale et des tarifs variables par site : elle ne remplace pas ce collecteur national.

## Chaîne et limites

- Inventaire : jeu producteur public OZECAR sur data.gouv.fr, ID exact `FROZE…` ; le collecteur choisit la ressource CSV la plus récente et conserve la ligne EVSE la plus récente. Prix/statut : page conducteur Monta publique `/d/{id_pdc_itinerance}`, sans secret ni compte ; six navigateurs Playwright concurrents. Les composants tarifaires sont conservés séparément ; les EVSE privés ou non résolus restent non classables.
- Nouveau workflow Data Lab : dispatch et cron jeudi 04:23 UTC, comme Updater Test, avec validation ciblée en PR. Il n'est exécutable en collecte que sur `main` ; la PR ne lance ni navigateur ni écriture de données. Il n'y a pas de secret à copier.
- Les sorties gardent les noms `data/ozecar/france/ozecar-france-current.json.gz` et `docs/france-ozecar-direct-report-current.json`. Le rapport garde le même schéma et les mêmes compteurs. Dans le snapshot public, les lignes IRVE sont projetées sur ID, station, localisation, prises, puissance, accès et dates ; le texte brut de page et les contacts du CSV ne sont pas persistés conformément aux règles publiques Data Lab. Les identités exactes et composants de prix ne changent pas.
- Aucun consommateur direct ou indirect du snapshot OZECAR Updater Test n'a été trouvé dans les scripts/builds Production, Stable ou Data Lab examinés. Production sélectionne les sources CPO via Data Lab, mais n'importe pas encore ce nouveau fichier ; **collecte migrée en PR, intégration Production non prétendue**.

## Gate avant extinction Updater Test

Après fusion explicitement autorisée, obtenir deux runs Data Lab du collecteur, comparer chacun aux sorties Updater Test de même période par ID exact, station, prise, puissance, statut et composants tarifaires, puis vérifier le chemin des consommateurs. Conserver le cron historique et ses snapshots versionnés jusqu'à cette preuve. En cas de régression, conserver Updater Test comme rollback ; aucun pin Production ni relais Stable n'est changé par cette PR.
