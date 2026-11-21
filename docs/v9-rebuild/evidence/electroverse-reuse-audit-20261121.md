# TCC V9 — Audit de réutilisabilité du patrimoine Electroverse France

**Date de constat : 21 novembre 2026. Statut : AUDIT TECHNIQUE EN LECTURE SEULE — premiers contrôles de fond réalisés, validation métier/intégration actualisée non terminée.**

**Mandat utilisateur :** réutiliser les tarifs déjà collectés, ne pas déclencher un renouvellement complet par défaut ; avant de qualifier une jointure nationale d'indisponible, essayer **(1) borne/EVSE/prise + opérateur**, puis **(2) adresse OU GPS + opérateur** avec preuves de portée et d'unicité. Préparer une méthode réutilisable pour les autres pays sans présumer qu'Electroverse y est couvert. Aucune modification des méthodes de collecte/fonctions tarifaires, aucun appel live fournisseur, aucune exécution Actions, aucun import/déploiement Production.

## 1. Sources exactes et méthode

- Branche Data Lab auditée : `rebuild/v9-20261020` ; état Git de départ après décision G5 : `bd434d034bb0582950d1143991aab42caeac7dea`.
- Artefact **[14711673559](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/44912790561)**, run `44912790561`, SHA code `2d19e361530f5a66072a56b6491f16779a9a823f` ; ZIP SHA-256 `a31e1630c39271e7f912a5d4e3262aa95a924a1f0d5dbb291f61d337b82c2879`.
- Parent **[14710945245](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/44909970308)**, run `44909970308`, SHA code `b1a8773d6b22275d36e0713e8d137d9ac554f9cf` ; ZIP SHA-256 `164b96f87b45cf632847b3c9cace554bb563197d1849d893912f665a7f6c55ca`.
- ZIP téléchargés et ouverts localement ; vérification indépendante par SHA-256 de **136/136 chemins annoncés** dans `checkpoint-manifest.json`, aucune entrée absente/altérée ; 128/128 fichiers shard, tous les comptes/taille des shards cohérents avec le manifeste, sharding SHA-1 déterministe, aucun doublon de PK cache ni de PK mapping, aucune divergence station/PDC entre cache et mapping. Contrôles de structure, pas de certification des prix par le fournisseur.
- Références historiques : `data/electroverse/tariff_cache/manifest.json`, `data/electroverse/irve_location_mapping.json`, `data/electroverse/live_statuses/parts/`, `data/platforms/electroverse/france-evse/manifest.json`, `docs/v9-rebuild/evidence/emsp-restoration-20261105/{electroverse-cache-status,electroverse-restoration}.json`, `memory/V9_REBUILD_PROGRESS.md`. Les anciennes sources et captures servent d'archives de règles/identité, non d'autorisation à déclarer des prix actuels.
- L'intégrité ZIP GitHub (SHA-256) correspond aux empreintes du fournisseur GitHub pour les deux artefacts. Aucune analyse de transactions réelles, aucune confirmation visuelle Netlify, et aucune confirmation indépendante de tous les prix affichés.

## 2. Tarifs déjà disponibles : conservation recommandée

| Contrôle | Résultat vérifié |
| --- | --- |
| Cache historique et dernier checkpoint | **22 818 lieux source**, 128 shards complets (nombres historiques descriptifs, jamais seuils de rejet) |
| Mapping source ↔ national | **22 818** lignes ; zéro PK du cache sans mapping ; zéro station nationale dupliquée dans ce mapping |
| Données tarifaires détaillées | **95 530 EVSE source**, **116 007 connecteurs** dans le dernier checkpoint ; leurs `priceComponents` sources sont présents, ce qui ne prouve pas la calculabilité de chaque offre |
| Absence d'EVSE source | **306 lieux** sans EVSE source au dernier relevé : conserver le lieu sans attribuer de prix |
| `checked-at.json` | **7 400 lieux contrôlés le 21/11**, **15 418 contrôlés en octobre** ; les anciennes lignes ne sont pas supprimées |
| Historique du champ `fetchedAt` | **4 351 lieux** portent une extraction tarifaire modifiée/datée du 21/11 ; la différence avec `checked-at` est attendue pour des prix revérifiés mais inchangés |
| Sauvegarde et promotion | `manifest.json` du dernier run : `partial_failure`; `checkpoint-manifest.json` : `partial_checkpoint`, `completeSnapshotValidated=false` |

Le run **44912790561** a bien une conclusion GitHub `success`, **mais cette réussite n'est pas une collecte complète**. Le bloc initial de 6 000 lieux est marqué terminé ; 4 600 lieux restent en attente dans le bloc suivant (offset 6 000). Cela correspond à **7 400 lieux vérifiés dans la campagne de renouvellement**, pas à 22 818. Les **15 418** autres demeurent réutilisables comme données historiques, non comme prix fraîchement confirmés.

Entre les deux derniers checkpoints, **2 200** localisations supplémentaires ont été contrôlées ; **1 058** objets `tariff`/empreintes ont changé, dont **746** avec modification de structure tarifaire sur au moins un connecteur présent dans les deux générations, **292** avec différence de `priceComponents` simples, **694** avec différence de `complexPricingDetail`, **60** avec changement du nombre d'EVSE source et **65** avec modification du jeu d'IDs de connecteurs. Ces catégories **se recouvrent** ; elles ne sont pas à additionner. Cela ne démontre ni 1 058 hausses de prix ni 1 058 prix numériques modifiés. Le programme ne doit pas écraser aveuglément les offres anciennes par une génération partielle.

**Interprétation :** le cache stocke des données source substantielles et techniquement intègres ; il serait injustifié de le jeter ou d'en exiger immédiatement une recollecte exhaustive. Cependant le prix eMSP *courant* de chaque entrée ancienne n'est pas prouvé par sa simple présence. Maintenir le `last-good` daté et renouveler par rotation/fraîcheur/erreurs et nouveaux lieux, avec audit des différences réelles de composants et des identités.

## 3. Jointure nationale : différence démontrée avec la nouvelle décision utilisateur

Le `irve_location_mapping.json` est daté du **6 octobre 2026** et provient de la base IRVE nationale datée du 26 septembre. Il relie 22 818 lieux Electroverse à des stations de la base nationale. **22 816/22 818** lignes portent `matchMethod=spatial_mutual_nearest_v1` : proximité réciproque à 15 m ou moins et marge vis-à-vis du second candidat ; **2** correspondent à une vérification ciblée station/opérateur/connecteurs.

La table conserve `irve.operator` (texte) et `electroverse.operatorId` (identifiant numérique), **mais les enregistrements spatiaux ne fournissent pas `operatorVerified=true` ni de preuve d'équivalence de ces deux identités**. 157 lignes n'ont pas de libellé opérateur national ; 2 n'ont pas d'ID opérateur Electroverse. Le libellé `confidence=high` issu de la proximité ne doit pas être réinterprété comme la preuve d'une concordance opérateur/prise.

Le manifeste historique cite un **échantillon externe de 500** : 372 identités corroborées, 121 métadonnées corroborées, 7 rapprochements seulement spatiaux et zéro contradiction observée. Ce bon résultat d'échantillon ne certifie pas les 22 818 jointures et ne remplace pas le nouveau contrôle obligatoire de l'opérateur.

**Plan de requalification, dans l'ordre imposé :**

1. Sur une base nationale datée et versionnée, essayer les identifiants officiels de station/EVSE/prise, et les alias **déjà validés**, avec une correspondance prouvée de l'opérateur/CPO, du pays et de la portée de l'offre ; préserver la distinction station ↔ prise.
2. À défaut, chercher une station unique par **adresse normalisée OU coordonnées GPS** et **opérateur concordant** ; vérifier également type, puissance, inventaire/compte des connecteurs et statut quand disponible. La géographie ne crée aucun lien tarifaire de prise par elle-même.
3. N'attribuer un tarif à une prise que sur portée source démontrée, ou sur un **groupe homogène** déjà permis par la politique avec égalité de prix et caractéristiques concordantes ; garder les candidats ambigus/rejetés avec une raison. Ne jamais transférer un prix direct CPO vers Electroverse.
4. Documenter par pays : source nationale, SHA, `operator_id`/alias, méthode de jointure, candidat unique ou conflit, EVSE/prise exacte ou groupe, décision calculable/incalculable/non disponible. La même logique devra fonctionner avec les bases nationales d'autres pays sans inventer de couverture Electroverse.

**Limite de cet audit :** aucun rapprochement requalifié n'a été recalculé sur une nouvelle base nationale ; aucun taux de réussite selon les nouveaux critères ne peut encore être annoncé.

## 4. Les offres compilées ne sont pas équivalentes à la fraîcheur

Le manifeste de l'overlay historique du **10 octobre 2026** contient **89 991 offres** (compilées selon ses méthodes historiques, pour 318 tuiles). Le contrôle de restauration du **5 novembre** retrouve **31 022 offres Electroverse attribuées par identité nationale exacte** ; les autres restent non attribuées ou mises en réserve selon les raisons du rapport, et ne doivent pas être considérées comme des prix affichables. Les 31 022 restent un *résultat historique de portée exacte*, non une confirmation de leur fraîcheur ni de conformité à la nouvelle règle `+ opérateur`.

Par conséquent : **préserver le dérivé last-good et ses preuves SHA**, requalifier ses associations et rejets sur la nouvelle règle ; ne pas déployer un nouvel overlay à partir d'un statut partiel/stale. À la phase d'import, le nouveau résultat doit être testé dans Production sans Netlify, puis faire l'objet d'une recette navigateur ultérieure.

## 5. Statuts : chantier distinct et réellement incomplet

La branche contient **13 partitions de statut sur 16** (manquent 10, 13 et 14) ; au total **6 045 localisations avec entrées sur 22 818 prévues**, **560 erreurs** conservées. Des partitions existantes sont donc elles-mêmes partielles : **terminer seulement les trois manquantes ne suffit pas**.

Les 13 partitions sont datées du 10 au 20 octobre et réparties sur **plusieurs empreintes de cache différentes**, aucune ne correspond à l'empreinte calculée sur le manifeste de la dernière génération du 21 novembre (`9257733a68ecc5d970a51dc1401d20b5fd703a19e20b43b3e0075d67fc773705`). Le code `v9_rebuild/electroverse_status.py` exige la même empreinte et la fraîcheur des partitions sous **16 heures** ; `v9_rebuild/electroverse_overlay.py` exige ensuite un statut national complet vieux de **72 h maximum** et compatible avec le cache. Le fichier de restauration du 5 novembre confirme l'absence de `mergedStatus` national.

**Conséquence :** archive de prix exploitable pour diagnostic/reconstitution, **mais nouveau cycle national de statuts / overlay complet non validé**. Ne pas contourner silencieusement ces gardes ; s'il faut rendre les renouvellements de prix indépendants du recensement des statuts, documenter une décision de conception et tester la sécurité de cette séparation avant de changer le contrat.

## 6. Synthèse opérationnelle et prochaines actions

| Élément | Décision de l'audit |
| --- | --- |
| Cache 128 shards | **CONSERVER** — intégrité de la dernière génération confirmée |
| Checkpoint 21/11 | **CONSERVER COMME PARTIEL** — filiation et reprise possibles, pas de promotion |
| Tarifs octobre | **LAST-GOOD DATÉ** — réutilisables comme archive et base différentielle, pas attestés actuels |
| Mapping 22 818 | **À REQUALIFIER** — majorité spatiale sans preuve opérateur portée par chaque ligne |
| Ancien overlay 89 991 offres | **ARCHIVE** — conserver méthodes et source, ne pas le déclarer frais |
| 31 022 offres attribuées exactement | **BASE DE COMPARAISON** — requalification opérateur et tests Production à faire |
| 13/16 partitions historiques | **INCOMPLET / INCOMPATIBLE** — pas de nouveau ledger national |
| Extension internationale | **CONTRAT GÉNÉRIQUE** — France pilote, autres pays selon couverture et preuves |

**Ordre préconisé avant tout nouvel appel fournisseur massif :**

1. Sauvegarder/épingler les manifestes, hashes, derniers checkpoints et ancienne version validée ; réparer seulement un défaut d'intégrité avéré.
2. Construire **en lecture seule et sur les données existantes** un audit de jointures exactes+opérateur puis adresse/GPS+opérateur. Quantifier par méthode, par opérateur, les vrais conflits et les offres conservées. Garder les données rejetées.
3. Tester la reconstitution de l'offre source par EVSE/prise, homogénéité des groupes et règles de prix existantes ; comparer au last-good historique sans considérer l'ancien nombre d'offres comme seuil.
4. Organiser les renouvellements de prix **progressifs** (nouveaux lieux, échecs, entrées anciennes, rotation des autres) et les statuts avec reprise persistante ; respecter les contraintes fournisseur, ne pas bloquer toute la base tant qu'une génération est partielle.
5. Tester l'import Production à partir des artefacts réellement validés, puis laisser la recette Netlify à Codex CLI conformément à l'organisation convenue.

**État de clôture du présent audit :** les contrôles d'intégrité, de structure, de dates, de filiation entre deux artefacts et l'inventaire des blocages sont réalisés. **Non réalisé** : simulation de correspondances exacte/opérateur et fallback géographique sur la base nationale actualisée, vérification commerciale indépendante, test complet de statut, import Production du nouveau résultat, exécution de nouveaux workflows, tests locaux officiels du dépôt. Aucune phase G2–G9 requalifiée en PASS.

**Rollback :** aucun code/donnée/workflow n'est remplacé ; les ZIP GitHub expirent le **21 décembre 2026** selon leurs métadonnées, prévoir copie pérenne autorisée des octets nécessaires à la reprise. Le présent fichier ne contient pas les archives brutes.
