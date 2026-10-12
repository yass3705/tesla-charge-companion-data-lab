# Journal de la mémoire technique

## 2026-10-13 — Voies tarifaires Tesla, libellés et PR obsolètes

- Production [#61](https://github.com/yass3705/tesla-charge-companion-production/pull/61) fusionnée (`1b23b11`) : Direct/Electra/Electroverse restent visibles aussi sur Tesla, même sans prix ; CI PR et `main` global/pin verts, Pages ignoré. [#62](https://github.com/yass3705/tesla-charge-companion-production/pull/62) fusionnée (`a56f6d0`) : frais fixes, blocs, minimums, paliers et frais différés affichés sans changer les montants ; CI PR et `main` global/pin verts.
- [Production #63](https://github.com/yass3705/tesla-charge-companion-production/pull/63) fusionnée (`a0db2fb`) : refus des conversions sans fichier FX daté et sourcé, tests ciblés, CI PR et `main` global/pin verts. [#64](https://github.com/yass3705/tesla-charge-companion-production/pull/64) fusionnée (`9631f4b`) pour le libellé `Prix calculé` ; première CI globale a trouvé une assertion navigateur littérale périmée, corrigée au commit `42bc3e2`, relance PR et `main` globale/pin vertes. [Run Electroverse 38323475271](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/38323475271) : checkpoint partiel 319/1 427, arrêt au budget de 49 erreurs API comme la partition 12 précédente ; registre national 1 550/22 818, aucun manifeste. Suspendre les appels en attente d'une correction fondée. Aucun Pages/Cloudflare.
- Data Lab #72 (bootstrap REVE historique), #104 (ancien overlay PD1) et #123 (ancien état PARERA) fermées après comparaison avec les workflows, l'overlay et la classification FR plus récents sur `main`. Les autres PR restent ouvertes tant que leurs changements propres n'ont pas de validation sur les sources actuelles ; Production #28 a reçu le lien vers les ports ciblés #59/#61/#62. Aucun Pages/Cloudflare.

## 2026-10-13 — Bélib exact et reprise Electroverse

- Production [#59](https://github.com/yass3705/tesla-charge-companion-production/pull/59) fusionnée (`f923054`), 1 419 règles Bélib liées aux EVSE officiels ; moteur Production corrigé pour conserver l'identité et la puissance du connecteur. Six checks PR et quatre suites `main` réussis ; Pages ignoré.
- Production [#60](https://github.com/yass3705/tesla-charge-companion-production/pull/60) fusionnée (`2a76090`), nouveau pin de développement à neuf pays `2026-10-13-nine-country-be-belib-exact-candidate`, mêmes sources Data Lab/Stable. [CI PR 38322048812](https://github.com/yass3705/tesla-charge-companion-production/actions/runs/38322048812) et `main` #38322194033/#38322193937 vertes, 2 442 empreintes vérifiées ; ancien candidat préservé. Aucun Pages/Cloudflare.
- Data Lab [#219](https://github.com/yass3705/tesla-charge-companion-data-lab/pull/219) ouverte en brouillon pour le filtre de connecteurs Electroverse FR ; ancienne #191 fermée après portage. Tests et scan public verts, mais recensement EVSE national incomplet (5/16 partitions et aucun manifeste) : pas de fusion ni de pin. La PR Production #28 reste en revue pour ses changements distincts.

## 2026-10-13 — Lots 2 et 3 : GeniePoint, pin et preuve d'abonnement

- Production [#56](https://github.com/yass3705/tesla-charge-companion-production/pull/56) fusionnée `a3a56c8a` : 46 offres walk-up GeniePoint exactes en plus, 281/1 138 prises tarifées, 857 sans montant ; CI global/pin verts, Pages ignoré. [#57](https://github.com/yass3705/tesla-charge-companion-production/pull/57) fusionnée `15309bf0` : nouveau pin de développement immuable `2026-10-13-uk-geniepoint-ad-hoc-candidate` validé sur PR ; anciens pins conservés. Ubitricity/Evyve bloqués par périmètre fournisseur, Zest/ChargePoint sans preuves tarifaires complètes.
- Data Lab [#203](https://github.com/yass3705/tesla-charge-companion-data-lab/pull/203) fusionnée `047e1911` après tests, scan public et collecte Powerdot officielle ; remises Electroverse conservées comme métadonnées non tarifaires par EVSE. [Inventaire international](../docs/v9-emsp-international-coverage-differential-2026-10-13.md) : seuls les overlays FR ont une source exacte épinglée. Production [#58](https://github.com/yass3705/tesla-charge-companion-production/pull/58) fusionnée `6926c98b` après CI candidate/global/r9 verte : neuvième pays BE et 41 706 offres ad-hoc énergie seule TTC, 28 337 EVSE pris en charge sans montant ; nouveaux et anciens pins conservés. Runs `main` post-fusion encore à relever. Aucun Pages/Cloudflare.

## 2026-10-12 — Collecte Powerdot réelle validée sans publication

- [Run Data Lab 38298531234](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/38298531234) terminé success : scan public, tests, collecte live et assertion CPO/eMSP réussis ; Powerdot Electroverse France 22 % pour 1,99 €/mois, direct CPO QR/station sans tarif national unique. Inventaire statique de 6 636 lignes, non live ; [artefact de collecte 11769846643](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/38298531234/artifacts/11769846643). Aucun push de donnée canonique ni promotion Production ; correction contenue dans la PR #203 jusqu'à fusion validée.


## 2026-10-12 — Préparation Powerdot et IONITY dans la mémoire partagée

- Preuve d'abonnement Electroverse officielle : Powerdot FR 22 %, ES 29 %, BE 30 %, PT 25 % (1,99 €/mois) et IONITY France 40 % (11,99 €/mois indicatifs) ; aucune valeur de remise ne se substitue à un prix eMSP par EVSE.
- Branche Data Lab `fix/electroverse-subscriptions-powerdot-ionity-20261012` : correction de l'analyse de page par opérateur/pays, assert Powerdot 22 %, tests déterministes et registre de preuves `data/emsp/electroverse_subscription_public_evidence_202610.json`. Statut non fusionné, ni déploiement V9 ni changement historique.
- [Première CI PR #203](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/38295400173) : 5/6 tests réussis ; le remplacement global `1,99 €` modifiait par erreur le montant IONITY `11,99 €` dans la fixture. Test corrigé par commit `7524144d`; contrôle complet non encore attesté.
- IZIVIA FAST/Express : [run 38288551568](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/38288551568) réussi ; le FAST national était alors bloqué sur tarification et rapprochement. La résolution ultérieure 616/616 et sa promotion de développement sont consignées dans l'entrée IZIVIA plus bas.

## 2026-10-13 — Lot 1 V9 : échecs historiques différenciés, rejeu DOT-NL réparé

- Production `9bedc84` déjà fusionné corrige le doublon navigateur UK PCPR ; global, Midhope, pin et r9 verts sur `160e2e2`. La [PR #55](https://github.com/yass3705/tesla-charge-companion-production/pull/55) fusionnée en `cbe4dd286` corrige seulement l'assertion du rejeu DOT-NL figé : 24 connecteurs USD/XXX restent sans offre EUR, les 161 485 autres restent calculables dans chacun des six profils ; [CI 38318304587](https://github.com/yass3705/tesla-charge-companion-production/actions/runs/38318304587) réussie. La PR historique #45, dont le merge aurait régressé le candidat, est fermée avec justification. Aucun déploiement Pages/Cloudflare, aucun changement de pin ; détails et reprise dans [CURRENT.md](CURRENT.md).

## 2026-10-12 — Ubitricity : condition des frais après charge confirmée

- Data Lab [#215](https://github.com/yass3705/tesla-charge-companion-data-lab/pull/215) fusionnée en `c7d8c9a40`, run 38311301464 réussi avec 17 tests. Production [#54](https://github.com/yass3705/tesla-charge-companion-production/pull/54) fusionnée en `160e2e22a` ; six checks PR et cinq runs `main` réussis, dont le global 38311766949. Le constructeur évite désormais le doublon `uk-pcpr.js` qui cassait le global sur le `main` précédent. Pages ignoré ; source Ubitricity inactive faute de collecte PCPR fraîche.
- L'utilisateur a vérifié sur le site PAYG que les frais des prises 7–22 kW ne commencent qu'après 60 minutes suivant la fin de recharge si le véhicule reste branché, et ne s'appliquent qu'entre 8 h et 20 h. La page officielle confirme 5 p/min. Le validateur remplace les anciens champs ignorés par V9 par `postChargeFee` avec grâce et exemption nocturne ; la nouvelle référence `b02a...` peut être évaluée seulement après collecte PCPR fraîche et identité exacte. Les 33 restent hors classement dans le snapshot actuel. Voir [l'audit](../docs/uk-ubitricity-rejected-tariffs-audit-2026-10-12.md).

## 2026-10-12 — IZIVIA FAST : 616/616 intégrées au pin de développement V9

- [CI exhaustive #38308710299](https://github.com/yass3705/tesla-charge-companion-production/actions/runs/38308710299) : 616/616 stations jointes, 1 212 tarifs directs, 0 erreur. [CI combinée FR + UK #38309263354](https://github.com/yass3705/tesla-charge-companion-production/actions/runs/38309263354) réussie, ainsi que la [CI de promotion #38309567151](https://github.com/yass3705/tesla-charge-companion-production/actions/runs/38309567151) (browser, manifeste, sécurité des pins). 12 affectations CHAdeMO non prises en compte.
- [Production PR #52](https://github.com/yass3705/tesla-charge-companion-production/pull/52) fusionnée `91b8273acac18dbea4f66fa65f8ee42b24690410` et pin développement `2026-10-12-izivia-fast-direct-candidate` contrôlé sur `main`, Data Lab `66ec5a67b5498a5e95ff5896d2d7b9ebc25fde60`. **Pas de Pages/release.** Anciennes versions de retour arrière conservées.


## 2026-10-12 — Rectification de la priorité PCPR Ubitricity

- Data Lab [#212](https://github.com/yass3705/tesla-charge-companion-data-lab/pull/212) fusionnée en `eb0443662` et Production [#53](https://github.com/yass3705/tesla-charge-companion-production/pull/53) en `150f77c`. Run Ubitricity Data Lab 38309335991 réussi ; quatre checks PR et cinq runs Production post-fusion réussis. Le job Pages a été ignoré ; dernier déploiement `796e7fca`. Aucun nouveau prix Ubitricity actif.
- La règle OCPI est le premier élément compatible par dimension, dans l'ordre publié. L'ancien constat de conflit lundi 20 h–minuit sur 183 prises reposait sur une priorité erronée à la fenêtre courte et est retiré ; le PAYG devient un diagnostic. Les 33 prises à nouvelle référence publique sont 21 prises de 7,4 kW et 12 de 22 kW. Leurs composantes `PARKING_TIME` (2,46/2,52 GBP/h hors TVA, pas 60 s) ne détaillent pas la grâce et la plage horaire annoncées officiellement. Source V9 inactive faute de collecte PCPR fraîche. Voir [l'audit rectifié](../docs/uk-ubitricity-rejected-tariffs-audit-2026-10-12.md).

## 2026-10-12 — Ubitricity UK : correction du validateur et preuve des blocages résiduels

- Audit officiel public des 458 prises rattachées aux trois références PCPR rejetées : 202 prix désormais corroborés à la prise après TVA et priorité de la fenêtre courte, 183 avec conflit lundi soir, 33 avec nouvelle référence et frais de stationnement, 39 sites déplacés et un détail indisponible. Voir [le dossier source](../docs/uk-ubitricity-rejected-tariffs-audit-2026-10-12.md). Le run PCPR quotidien 38231569077 renvoie toujours 0 site / 0 tarif avec le jeton actuel. Correctif du validateur et tests fusionnés via [#209](https://github.com/yass3705/tesla-charge-companion-data-lab/pull/209) (`a1efdd75f`) ; [run post-fusion 38307222593](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/38307222593) réussi, appels au CPO et persistance ignorés. Source Production inactive, aucune publication.

- [Validation effective run #38299651696](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/38299651696) **success** : 620 stations et tarifs directs officiels, 616 avec connecteurs éligibles, quatre sans connecteur pris en charge. Détails carte 0 échec, aucune repasse sollicitée, couverture précédente 482 → 616 (+134). 665 codes carte, 45 codes carte hors inventaire ; pas d'élargissement des correspondances exactes. [Artefact](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/38299651696/artifacts/11769129182). Le succès de la première passe ne prouve pas l'utilisation des retries. Aucune promotion Production.

## 2026-10-12 — Récupération IZIVIA FAST (candidate)

- [Run historique 38271411552](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/38271411552) : 482 stations tarifées sur 620, 76 erreurs tarifaires, 59 non-appariements carte et 65 fiches carte en échec. Hypothèse testée : interruptions/rate limit de l'API pendant les requêtes concurrentes, non disparition nécessaire des sites.
- Branche Data Lab `fix/izivia-fast-recover-map-prices-20261012` : quatre workers, repasse séquentielle des détails et prix échoués, rapports de récupération, aucun tarif inventé. [Validation nationale sans publication 38299651696](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/38299651696) déclenchée ; décision de fusion suspendue à la validation effective et aux preuves.


Entrées append-only, datées, avec liens vers les documents et commits sources. L'historique exhaustif du code reste dans Git (`git log`) et dans les changelogs propres aux dépôts ; ce journal consigne les passages de relais et décisions transverses.

## 2026-10-12 — Vingt CPO UK intégrés prudemment au candidat, Ubitricity toujours bloquée

- Data Lab [#207](https://github.com/yass3705/tesla-charge-companion-data-lab/pull/207) fusionnée en `0942299c4`, puis Production [#51](https://github.com/yass3705/tesla-charge-companion-production/pull/51) en `660fe0b`. Les quatre checks de PR et cinq runs Production post-fusion ont réussi ; [run global 38304183240](https://github.com/yass3705/tesla-charge-companion-production/actions/runs/38304183240), Pages ignoré. Le dernier déploiement Pages reste `796e7fc` du 11 octobre. L'audit de 31/32 CPO présents concerne le candidat construit, pas le site publié. La PR documentaire #206 conflictuelle a été fermée après reprise de ses preuves dans #207.
- La consolidation précédente a été fusionnée via Data Lab [#204](https://github.com/yass3705/tesla-charge-companion-data-lab/pull/204) (`f54dd4954`) puis Production [#50](https://github.com/yass3705/tesla-charge-companion-production/pull/50) (`4aa88f5ee`). Les cinq runs Production post-fusion ont réussi, Pages ignoré ; dernier déploiement connu `796e7fca`. La note de la PR documentaire #206 est reprise dans `CURRENT.md` après conflit avec des changements indépendants.
- La collecte publique GeniePoint a été épinglée en Data Lab : 306 sites, 1 138 prises, 530 tarifs et zéro référence tarifaire manquante. Le candidat Production ne classe que 235 offres exactes TTC. Les 19 autres CPO intégrables du lot sont traités comme prix vérifiés, inventaire de prises sans prix ou sites sans identité de prise, selon leurs preuves. Le [dossier Production](https://github.com/yass3705/tesla-charge-companion-production/blob/feat/uk-direct-ocpi-batch-20261012/docs/V9_UK_21_CPO_FOLLOWTHROUGH_20261012.md) détaille les limites.
- Audit du build global local : 31 des 32 CPO terminés présents en inventaire, 15 avec au moins une offre ; Ubitricity reste inactive sous blocage support. Tests du snapshot, manifeste, parité Stable et runtime multi-pays réussis. Aucune publication Pages. Les branches de travail doivent encore passer la CI GitHub avant fusion.

## 2026-10-12 — Candidat UK publié en PR de revue, quatre checks Production réussis

- [Data Lab #204](https://github.com/yass3705/tesla-charge-companion-data-lab/pull/204) et [Production #50](https://github.com/yass3705/tesla-charge-companion-production/pull/50) ouvertes après accord utilisateur, non fusionnées. La CI de #50 a corrigé successivement la compatibilité des pins historiques, la parité Stable et les chemins relatifs des tests. Le [run global 38298692518](https://github.com/yass3705/tesla-charge-companion-production/actions/runs/38298692518), r9, développement épinglé et Ubitricity ont réussi ; job Pages ignoré. Le dernier déploiement Pages reste `796e7fca` du 11 octobre.
- Le candidat local final sous Data Lab `2ea858eeb` et Stable `3b2d4776` passe la parité, le manifeste SHA-256 et le smoke runtime. Les 21 CPO terminés absents du runtime restent un écart ouvert ; aucune promotion du pin de développement ni publication Pages.

## 2026-10-12 — Audit de couverture UK et candidat Connected Kerb/Allego local

- Les preuves du jour sont rassemblées dans `docs/uk-cpo-consolidation-2026-10-12.md`. Le candidat Production local intègre les 8 100 prises Connected Kerb validées et épingle Allego avec son audit ; Source EV et Midhope sont contrôlés. ChargePoint conserve zéro prix direct promu ; les trois références Ubitricity rejetées n'ont pas de nouvelle preuve.
- Contrôle de publication : 32 CPO marqués terminés, 11 présents dans des sources V9 actives, 9 avec au moins une offre, 21 absents. La publication UK complète reste ouverte. Branches locales `feat/uk-consolidation-20261012` dans Production et Data Lab, sans synchronisation GitHub ni déploiement Pages.

## 2026-10-12 — Source EV publié dans les pipelines Data Lab et Production, sans Pages

- Data Lab [#201](https://github.com/yass3705/tesla-charge-companion-data-lab/pull/201) fusionnée (`dd53905ab`), puis [collecte 38294034888](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/38294034888) réussie avec audit et scan public ; commit de données `054c48cbe`, 36 stations et 323 connecteurs exacts. La collecte continue quotidiennement à 03:43 UTC.
- Production [#49](https://github.com/yass3705/tesla-charge-companion-production/pull/49) fusionnée (`1f1b593b`) après quatre checks réussis. Le [run global post-fusion 38294581197](https://github.com/yass3705/tesla-charge-companion-production/actions/runs/38294581197) a réussi avec Source EV et le parcours navigateur ; Pages ignoré. Dernier déploiement Pages inchangé à `796e7fc` ; aucune promotion du pin de développement.

## 2026-10-12 — Source EV quotidien validé localement, Evyve transmis au support

- Le [run Source EV 38289984508](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/38289984508) a collecté 36 sites publics actifs et 321 connecteurs Type 2/CCS avec prix exact. L'audit indépendant et son ajout au workflow quotidien sont préparés sur `feat/source-ev-daily-audit-20261012` (`d099e7a10`, puis fusion locale `8da6c953b`) ; l'activation candidate sous pin et audit concordants est préparée dans Production sur `feat/v9-source-ev-integration-20261012`. Build local avec les SHA Stable `3b2d4776` et Data Lab `8da6c953b`, validateur, manifeste et smoke runtime Alloa réussis. Scan public du dépôt Data Lab réussi. Aucun changement n'est encore publié depuis ces branches locales.
- Le [run Evyve 38288653559](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/38288653559) prouve que le jeton distinct renvoie pourtant 869 sites Blink ; le collecteur a rejeté cette réponse. L'utilisateur sollicitera le support pour corriger le périmètre Evyve/GB*EVY.

## 2026-10-12 — Compatibilité historique r9 Electra préparée localement

- Le [workflow r9](https://github.com/yass3705/tesla-charge-companion-production/actions/runs/38181406471) exigeait l'overlay Electroverse EVSE compilé introduit après son pin Data Lab `fece067b`. La branche Production locale `fix/v9-r9-electra-historical-overlay`, commit `6474b5b`, recompile uniquement les sources r9 vérifiées, contrôle les rejets et conserve les gardes complètes des snapshots récents. Voir la [preuve technique Production](https://github.com/yass3705/tesla-charge-companion-production/blob/fix/v9-r9-electra-historical-overlay/docs/R9_ELECTRA_HISTORICAL_CI.md) après publication autorisée.
- Reconstruction, parité, manifestes, graphe, smoke et tests tarifaires locaux réussis. NL r9 reste sans résultat Amsterdam en mode hors ligne ; r8 manuel reste incompatible séparément. Aucun push, PR, fusion, promotion ou déploiement n'a été effectué pour ce correctif.

## 2026-10-12 — Vérifications GitHub avant fusion des PR #195 et #39

- [Production #40](https://github.com/yass3705/tesla-charge-companion-production/pull/40) fusionnée dans `main` par `c48ad07aeb4085606e205ce0fdb59fa33253ddce` ; [run RC1 38178557177](https://github.com/yass3705/tesla-charge-companion-production/actions/runs/38178557177) réussi sur l'artefact historique figé. Ancien timeout expliqué par l'incompatibilité test/contrat RC1.
- [Production #39](https://github.com/yass3705/tesla-charge-companion-production/pull/39) mise à jour au HEAD `e5ea99cb0bbcdb35c921b914ba509c56846877c3` : [audit DE](https://github.com/yass3705/tesla-charge-companion-production/actions/runs/38180622767), [Ubitricity](https://github.com/yass3705/tesla-charge-companion-production/actions/runs/38180625542), [candidat épinglé + navigateur](https://github.com/yass3705/tesla-charge-companion-production/actions/runs/38180625476), [global V9 + navigateur](https://github.com/yass3705/tesla-charge-companion-production/actions/runs/38180625622) tous réussis ; étapes Pages et job deploy ignorés.
- La [PR Data Lab #195](https://github.com/yass3705/tesla-charge-companion-data-lab/pull/195) reste uniquement documentaire. La fusion à venir changera le SHA de `main` Data Lab sans forcément modifier les deux fichiers nationaux DE ; tout nouvel identifiant checkout doit être enregistré explicitement dans le manifeste de provenances de Production #39 **après vérification des identités des blobs**. Ne pas neutraliser ce contrôle fail-closed.
- Limite toujours signalée : provenance de l'archive source Electra historique absente et contrôles du manifeste compilé/tuiles sur le pin autorisé. Aucune publication V9 ni promotion de snapshot autorisée par ces opérations.

## 2026-10-11 — Correction locale de la provenance IONITY allemande

- [Run Production 38172211767](https://github.com/yass3705/tesla-charge-companion-production/actions/runs/38172211767) échoué sur le candidat de développement immuable : 199/3 observés contre 200/4 imposés par une assertion plus récente. Son artefact uploadé n'est pas validé. Aucun déploiement Pages.
- Branche Production locale `fix/de-ionity-snapshot-provenance`, commit `548ae48068e78f8980324401a43ce98c9bff880e` : manifeste de provenance IONITY, vérification du checkout épinglé, comptes et identités fail-closed, tests des générations historiques et récentes, validation du snapshot reconstruit et rectification du format Electra historique. Les huit sites ambigus demeurent en quarantaine ; aucune base Data Lab n'a changé. Mémoire préparée sur `docs/de-ionity-provenance-ci-local`, sans push ni PR.

## 2026-10-11 — Revalidation des PR avant fusion

- Production [#36](https://github.com/yass3705/tesla-charge-companion-production/pull/36) : merge local sans conflit de `origin/main=226530f6` (PR #37 et #38) dans la branche tarifaire, commit `ee4f9deee5e03d8c36d42d08248a06f908330cda`. Les validations tarifaires et les gardes Pages coexistent ; r8 reste manuel. Data Lab [#194](https://github.com/yass3705/tesla-charge-companion-data-lab/pull/194) reste basé sur son `origin/main` actuel.
- Snapshot candidat local `2026-10-11-r36` construit avec les commits exacts Stable `b1284080` et Data Lab `01f6c2a1`, puis validé. Tests ciblés locaux réussis pour fuseaux, OCPI, SOC80, Tesla, Midhope, Electroverse, regroupements, smoke multinationaux et protection Pages. [CI PR 38171626049](https://github.com/yass3705/tesla-charge-companion-production/actions/runs/38171626049) réussie, parcours navigateur compris ; étapes et job Pages ignorés. Playwright absent localement, donc parcours navigateur local non exécuté. Aucun artefact `dist/` suivi, déploiement ni fusion.

## 2026-10-11 — Revue corrective des PR tarifaires

- Production [#36](https://github.com/yass3705/tesla-charge-companion-production/pull/36), commit `ca8e3e55ddb7a0f017fc564b4f457a46c831ea7b` : priorité des fuseaux source, tests DST/date/chronologie, exclusion des totaux incomplets des classements et distinction Tesla corrigées localement ; validation CI à relever après push.
- Data Lab [#194](https://github.com/yass3705/tesla-charge-companion-data-lab/pull/194) : critères actuels de l'interface ajoutés à la [politique](../docs/v9-pricing-result-labels-policy-2026-10-10.md) sans réécrire la décision historique. Stable reste aligné ; Updater Test a avancé d'un commit indépendant sur `origin/main`, laissé intact.
- Après push : [validation Production 38166416425](https://github.com/yass3705/tesla-charge-companion-production/actions/runs/38166416425) réussie, job Pages ignoré ; [build r8 38166413200](https://github.com/yass3705/tesla-charge-companion-production/actions/runs/38166413200) bloqué par l'overlay Electroverse épinglé absent. Aucun déploiement Pages de la PR observé ; dernier déploiement `main=796e7fc`.

## 2026-10-11 — Initialisation locale

- Inventaire des quatre dépôts sur `main`, arbres propres, sans interrogation distante. SHA consignés dans [CURRENT.md](CURRENT.md).
- Création d'un index transversal vers les documents existants et d'une procédure de reprise Mac/mobile. Aucun code métier, donnée ou workflow modifié ; aucune publication effectuée.
- Point de cohérence à traiter : terminologie des ambiguïtés entre le périmètre eMSP et la politique détaillée des libellés (voir `CURRENT.md`).

## 2026-10-11 — Audit distant en lecture seule

- `git fetch origin` dans les quatre dépôts : Production inchangé ; Data Lab +24 commits ; Stable +2 ; Updater Test +1. Aucun commit local absent de GitHub, aucun pull/commit/push effectué. Les SHA et les sujets sont dans [CURRENT.md](CURRENT.md).
- La dernière archive de couverture France distante est un audit validé, non une publication V9. L'index des règles a été complété avec les politiques EVSE actif, frais différés, captures Electra et UK Midhope.
- Points non résolus : divergence de vocabulaire des libellés, garde Midhope annulée par rectification tardive, sections de statut Production périmées et preuve contractuelle absente pour 78 offres Electra eMSP.

## 2026-10-11 — Synchronisation locale autorisée et vérification fonctionnelle

- Nouveau fetch ; contrôle d'ascendance, d'absence de modifications suivies et d'absence de collision `memory/` avec Data Lab distant. Pull en avance rapide réussi dans Data Lab (24 commits), Stable (2) et Updater Test (1) ; Production était déjà à jour. SHA finaux dans [CURRENT.md](CURRENT.md). Aucun commit, push, workflow ou déploiement effectué.
- Lecture HTTP du shell V9 public : `snapshotId=2026-10-11-r38134963436`, candidat Stable `ce1b2649666de6528cecea0bcf7c87ef248e4483`. Développement Production distinct : `2026-10-03-nl-datalab-candidate` / Data Lab `40806cdd10c428579ed7c6b0bbecca0a01b70d12`.
- Vérification statique du moteur : frais différés non prouvés → `complete:false`; Midhope utilise `Europe/London` et la garde du 24 octobre est retirée par l'adaptateur. L'interface et les métadonnées du registre gardent des libellés antérieurs ; écarts décrits dans `CURRENT.md`.
- Tests Midhope non exécutables sur ce Mac : `node` disponible est v6.7.0, sans support du programme de tests `.mjs` ni de `--test`. Les tests du dépôt n'ont donc pas été déclarés passés localement.

## 2026-10-11 — Préparation de la première publication

- Branche locale Data Lab `docs/tcc-v9-shared-memory` créée à partir de `main=28f1aba30` ; publication et fusion soumises à validation distincte. Seuls `memory/README.md`, `memory/CURRENT.md` et `memory/HISTORY.md` appartiennent à cette préparation.
- Références directes vers la documentation du dépôt privé retirées de l'index public ; contrôle de confidentialité et déclencheurs Actions vérifiés avant commit local.

## 2026-10-11 — Continuité commune en préparation

- Nouveau fetch des quatre dépôts ; #192 est fusionnée dans Data Lab `main=b5ef9caf8`, les trois autres `main` n'ont pas avancé. Data Lab local a été avancé sans fusion depuis `28f1aba30`.
- Branche documentaire `docs/tcc-v9-agents-continuity` issue de ce `main` : ajout d'un `AGENTS.md` versionné et compléments ciblés du protocole de reprise. Aucun ancien `AGENTS.md` n'était présent à la racine de `/Users/yassine/Projects/TCC` lors de l'inspection ; le lien symbolique local pointe vers la référence Data Lab.

## 2026-10-11 — Validation Node 22 et branches locales de correction

- Fetch des quatre dépôts ; Data Lab avancé en fast forward au commit `01f6c2a1d`. Branches locales `fix/v9-tariff-labels-local` (Production) et `docs/v9-tariff-labels-validation-local` (Data Lab).
- Tests Midhope et frais différés relancés localement sous Node 22. Le build local Production a débloqué SOC80 et OCPI ; OCPI a révélé que la règle `pricing.timeZone` n'était pas appliquée par le moteur. Rectification des libellés dans la politique Data Lab et correction locale du bridge/moteur Production. Snapshot local validé, SOC80, OCPI (aussi sous `TZ=UTC`), classements par catégorie et Midhope passent ; aucun push, workflow ni déploiement.

## 2026-10-11 — Revue ciblée avant commits locaux

- Nouveau fetch sans avance distante dans les quatre dépôts. Revue OCPI : `pricing.timeZone` appliqué ; fuseau manquant ou invalide sur règle horaire désormais incalculable ; cas DST dans les deux sens et passage de minuit testés. SOC80 et classement par catégorie revérifiés. Commit Production local `7b471d6` sur `fix/v9-tariff-labels-local` ; `dist/` exclu du commit. Publication toujours soumise à accord.

## 2026-10-11 — PR de revue et correction de fixture CI

- GitHub a refusé les premiers SHA locaux à cause d'un e-mail d'auteur privé. Les commits ont été recréés avec l'adresse GitHub `noreply` sans changer la logique. PR Production #36 et Data Lab #194 ouvertes et liées, sans fusion.
- Build r8 historique échoué sur un overlay Electroverse épinglé absent ; validation PR Production échouée après les tests runtime sur une fixture navigateur omettant `result.complete:true`. Commit Production `1dda721` corrige cette fixture et a été poussé pour revérification. Le job Pages de la validation PR était `skipped` ; aucun nouveau déploiement confirmé.
- Validation PR Production relancée sur `1dda721` : [run 38165386824](https://github.com/yass3705/tesla-charge-companion-production/actions/runs/38165386824) `success`, parcours navigateur réussi ; configuration Pages, upload et déploiement `skipped`. Le dernier déploiement Pages observé reste celui du SHA `796e7fc`, antérieur aux PR.

## Format des prochaines entrées

`YYYY-MM-DD — sujet` ; décision ou constat ; preuves et liens ; fichiers/commits concernés ; vérification ; statut de publication ; action restante. Ne jamais présenter un résultat expérimental comme déployé.
