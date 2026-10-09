# TCC Data Lab — procédure figée FR IRVE ↔ tarifs P1/P2/P3 (v1.0)

**Statut : FIGÉ — 2026-10-09.** Toute évolution de politique de rapprochement, de filtre de service ou d'attribution tarifaire doit passer par une révision explicite de cette SOP, des contrôles CI et du schéma d'archive. Le mécanisme ne publie PAS de tarifs en production V9.

## 1. Déclencheur quotidien : lié à l'IRVE dynamique réellement publiée

1. **France IRVE static refresh and residual audit** (Data Lab, `.github/workflows/france-irve-static-refresh.yml`) télécharge la source PAN dynamique. Créneaux existants : 02:17 et 03:17 UTC, avec bascule de récupération.
2. Il calcule et **publie sur main** `data/national/france-irve-dynamic-status-v9.json.gz`, qui contient `enServicePdcIds`, `generatedAt` et `sourceSha256`. La base IRVE statique et le suivi résiduel conservent leur historique.
3. Aussitôt **après la clôture réussie** de ce workflow, `.github/workflows/france-irve-tariff-coverage-archive.yml` se lance automatiquement via `workflow_run`, sans dépendre d'un push de bot GitHub.
4. Avant de recalculer, `scripts/france/check_irve_tariff_review_gate.py` vérifie la source positive, la cohérence du compteur, sa fraîcheur (<=72 heures), puis compare `generatedAt + sourceSha256` avec la **dernière vérification archivée**. Si le flux PAN a échoué, si l'ancien snapshot a été conservé ou si cette version a déjà été revue, **aucune nouvelle revue ne sera fabriquée**.
5. Un contrôle planifié de secours à **04:17 UTC chaque jour** attrape une publication IRVE qui n'aurait pas déclenché la revue; il ne duplique pas un rapport déjà réalisé.
6. Les validations des CPO et overlays déjà surveillées restent des **déclencheurs supplémentaires** de recalcul, avec la même base de référence dynamique. `workflow_dispatch` permet une vérification manuelle. La persistance de rapports ne déclenche pas de boucle, car les archives ne sont pas des chemins `push` surveillés.
7. Concurrency `france-irve-tariff-coverage-permanent-main` avec `cancel-in-progress:false`, pour ne pas écraser des travaux déjà en cours.

**Les échecs sont visibles dans Actions.** La revue est *réussie* uniquement une fois validée **et** poussée sur `main`.

## 2. Règles de correspondances figées

| Niveau | Preuve obligatoire | Attribution |
|---|---|---|
| P1 | Identifiant EVSE normalisé identique dans la source originale et la base IRVE | Automatique |
| P2 | Association EVSE déjà **validée et publiée** dans un overlay Data Lab, avec `identityMode` documenté | Reprise de l'association sans doublon, en vérifiant le statut IRVE |
| P3 | Association **nouvelle**, unique à <=10 m, nombre d'EVSE identique, même opérateur/adresse, puissance compatible (AC max[2 kW;10 %], DC max[15 kW;10 %]), preuve permettant l'attribution non ambiguë d'un tarif au bon EVSE | Audit distinct; promotion uniquement après validation des preuves; aucune transmission aveugle d'un prix station aux EVSE |

Une station est active si et seulement si au moins un EVSE est explicitement `en_service`; **le LEFT JOIN et l'audit tarifaire ne comptent que les EVSE avec `en_service` positif**. `hors_service`, `inconnu` et absence de preuve dynamique sont exclus du comptage prioritaire, sans supprimer la station ou déclarer qu'elle est définitivement hors service.

Le référentiel canonique est `EVSE_ID_NORMALISÉ` : uppercase, suppression de tous les caractères non alphanumériques. Une ligne de correspondance par EVSE; plusieurs grilles de tarifs par puissance ou abonnement restent des variantes distinctes. **Interdiction d'assigner par simple GPS un tarif hétérogène au niveau station.**

Ordre de vérité en cas de conflit : **P1 > P2 > P3 > absent**. Ne jamais choisir le prix le plus bas pour résoudre un conflit d'identité; les tarifs CPO directs et eMSP demeurent indépendants. Ne pas mélanger CPO direct et offre eMSP. Les tarifs directs relèvent des données ad-hoc du CPO, pas des prix eMSP tiers.

## 3. Audit et archivage permanents

Répertoire d'accès : [reports/france/tariff-coverage](../reports/france/tariff-coverage/).

À chaque **nouvelle revue validée**, versionner les fichiers :

- `latest.json` : huit combinaisons tarifaires, P1/P2/P3, périmètre actif, 167 classes de puissance (variable selon source), dates et empreintes des manifestes, couverture CPO et eMSP, source CPO et anomalies, **différence chiffrée par rapport à la revue précédente**, `dynamicShaChanged`.
- `evse-latest.jsonl.gz` : chaque EVSE, état opérationnel, groupe de puissance, station, GPS/adresse, opérateur, sources directes, offres eMSP, identité et preuves.
- `offers-latest.jsonl.gz` : toutes les **offres eMSP tarifées** avec règles et métadonnées, par EVSE.
- `cpo-prices-latest.jsonl.gz` : preuves tarifaires directes CPO extraites avec leur ligne d'origine, ou **lien explicite vers la source vérifiée** quand le tarif n'est pas matérialisé; ne jamais inventer un taux.
- `history.jsonl` (append-only) et `snapshots/<date>-run-<id>.json` : chaque revue validée, sa provenance et ses deltas.

Les anciennes versions intégrales sont accessibles par l'historique des commits Git. Les sources brutes restent dans leurs emplacements Data Lab et la revue consigne leurs SHA-256. Le fichier latest n'est jamais considéré « actuel » si l'instant de la source dynamique est obsolète.

Contrôles fail-closed : dynamique valide et <72h, somme des **8 catégories = EVSE actifs**, total des **4 catégories CPO = EVSE avec CPO direct**, références P1 et P2 dans l'IRVE, fichiers archives accessibles et non vides, JSONL compressé lisible, historique daté cohérent; aucun P3 indéterminé ne doit devenir un tarif publié automatiquement.

## 4. Dernier référentiel au gel

Snapshot actif de référence `2026-10-09T18:01:03Z` :

- **94 586 EVSE actifs**, **77 751** avec au moins une source tarifaire validée et **16 835** sans tarif trouvé.
- CPO seul : **3 135**; CPO + Electra : **11 946**; CPO + Electroverse : **7 428**; CPO + les deux : **17 889**; soit **40 398 EVSE** disposant d'une source de prix CPO direct dans ce périmètre (travail national CPO **non terminé**).
- Electra eMSP : **53 668** EVSE avec overlay tarifé validé. Electroverse : **51 891**.
- Aucun nouveau P3 approuvé, après contrôle GPS + technique + opérateur + adresse. Les preuves insuffisantes restent des pistes de diagnostic, non des tarifs publiés.

**Cette SOP fige l'identité et la couverture; elle ne définit pas encore la formule complète du prix.** L'étape suivante est le moteur tarifaire indépendant (énergie, temps, session, frais de congestion/SOC, puissance, abonnements), avec tests exhaustifs et gestion de toute ambiguïté restante.
