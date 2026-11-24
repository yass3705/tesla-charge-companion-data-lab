## 2026-11-24 — G5 : audit résiduel puissance lancé

Commit fonctionnel bfe95d6df5ae29393d0e7374db5ad02cc5e26566, parent 62dc560122984a0c936fec3bdf501dde537208a0, rebuild/v9-20261020. Run [45476756404](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45476756404), SHA exécuté vérifié, job 138738887366, état observé in_progress/sans conclusion. 1 254 DC et 63 multitypes au-dessus nominal, références 14950692711 et 14958472327, 9 tests prévus, non vérifiés. Vérifier G5_RESIDUAL_POWER, G5_RESIDUAL_POWER_TOP, cohorte, bandes, sens, autres matchs validés, artefact/SHA. Champ within_dc_candidate_search_band interprétable uniquement pour DC. Aucune preuve indépendante d'équivalence fournie par cet audit ; valeur numérique Electroverse archivée sans précision lexicale originale. Pas de changement de règle, collecte, prix, main/Production ; G5 PARTIAL, Mac local inaccessible. Résultats non vérifiés.

## 2026-11-24 — G5 : audit résiduel DC et multitypes au-dessus nominal autorisé

Accord utilisateur reçu. Préflight Data Lab 62dc560122984a0c936fec3bdf501dde537208a0, Production b1d102d97ba8647e79514e89b15f82d8dce97a78, aucun run Data Lab en cours/en file ni PR depuis/vers rebuild ; Production ancien run 37642387836 autre branche intact. Mac local inaccessible. Audit exclusivement hors ligne des 1 254 couples DC mono-type et 63 couples multitypes source au-dessus nominal, sources ZIP/CSV épinglées 14950692711 et 14958472327, jointure des 21 980 couples exacts par IDs, référence v4 13 786 validés, réconciliation exacte exigée. Tranches absolues <=5, (5,15], (15,30], (30,50], >50 kW ; relatives <=5%, (5,10]%, (10,20]%, (20,50]%, >50% avec dénominateur nominal IRVE ; sens, type/courant, opérateur, combinaisons kW, présence d'autres matchs v4, autres FAIL. Valeurs brutes nominales IRVE issues de l'audit de projection ; conversion unité/arrondi reproduits, pas preuve indépendante de puissance équivalente. Electroverse valeur numérique archivée, pas précision lexicale source. Aucune modification de matching ni nouvelle tolérance ; 15 kW DC recherche uniquement, aucun appel fournisseur, aucun prix promu. Exports CSV gzip + JSON et logs synthèse, 9 tests et scan public prévus non vérifiés. G5 PARTIAL ; aucun changement main/Production. Prochaine action lire résultats, proposer décision distincte après accord ; pas de nouveau match présumé.

## 2026-11-24 — G5 : tolérance AC 1 kW validée en replay exact, +912 couples sans perte

Run [45473344809](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45473344809), job 138726913757, code 9802768e96495fd4329d927f62fa5310e9072a74, completed/success 19:46:13Z. 9+11+17+13 = 50/50 tests, public safety PASS. ZIP sources, SQLite et CSV épinglés vérifiés dans runner, reproduction v2 et v3, unicité B et réconciliation PASS. Artefact 14958472327 (576 556 octets), nom identique au précédent tcc-v9-g5-irve-power-scope-ab mais ID/run/SHA distincts ; SHA256 ZIP GitHub 9f96dc19461a6d5ed4392a5b3652f5468c8813c81da6d7a745a4614f5950e5a5, expiration 24/12/2026 19:46:06Z ; exact-ab.csv.gz SHA 31f3c5117af6eb666fed3efae7d6f8ec98bbddf9c8db96f480bb2b73da1fe6c8 + ab-report.json. Logs et métadonnées vérifiés ; ZIP résultats non retéléchargé indépendamment dans chat.

Sur 21 980 couples exacts : 12 874→13 786 MATCH_VALIDATED (+912 profils/PDC distincts concernés, +7,1%), 8 956→8 027 contradictions, 142→159 ambiguïtés, 8 insuffisances inchangées. 929 FAIL→PASS puissance dans la cohorte approuvée ; 912 validés (98,2%), 17 toujours rejetés pour ambiguïté (SPIE 9, Bouygues 6, Révéo 2). Zéro perte, zéro doublon. Portée NOT_EVALUATED→PASS 912, 12 874 PASS conservés. Gains Bouygues 376, SPIE 236, Plug Inn 69, ROAD 55, Révéo 48, Freshmile FR1 41, Borneco 29, ChargePoint 24, autres 34. Cumul depuis v2 9 612 : +4 174 (+43,4%). 559 998 couples non exacts inchangés par conception ; dispositions projetées total 581 978 : 13 786 validés, 62 905 ambiguïtés, 343 792 contradictions, 161 495 insuffisances, pas de nouveau registre complet. 4 666 FAIL puissance subsistent dans exacts (inclut contradictions de prise/courant) ; 6 575 MISSING, 10 739 PASS. Règle v4 opt-in --ac-tolerance avec preuve scope ; décision utilisateur déjà normative, pas de changement de puissance brute, de règle DC ou multi-type au-dessus nominal. Aucun appel fournisseur ni prix promu, MATCH_VALIDATED ne vaut pas calculabilité/publication.

Prochaine étape recommandée après accord : audit hors ligne ciblé des 1 254 écarts DC mono-type et des 63 multi-type source au-dessus nominal identifiés dans l'audit de granularité ; ventiler par écart absolu et relatif, puissance/prise/opérateur, comparer valeurs brutes et précision, vérifier preuve et distinguer contradictoire de non comparable, sans modifier le seuil DC de 15 kW réservé à la recherche de candidats. Les effectifs sont des couples, non des PDC distincts ni des gains garantis. Préserver les 13 786 matchs v4 et les autres motifs de blocage ; ensuite alias, adresse/GPS et portée, archivage durable, génération/recette. G5 PARTIAL, G8/G9 non validés. Préflight Data Lab 0ba455ded31c5f9fc305089ac67a0e60b7d5a87c, Production b1d102d97ba8647e79514e89b15f82d8dce97a78, aucun run Data Lab actif/en file, aucune PR depuis/vers rebuild ; Mac local inaccessible. Entrée documentaire uniquement, aucun nouveau run ou changement de règle/Production/main.

## 2026-11-24 — G5 : run cumulatif AC 1 kW lancé

Code 30629f29606d3369a4d67f2af2086b5615908eda, décision normative et déclenchement 9802768e96495fd4329d927f62fa5310e9072a74, branche rebuild/v9-20261020. Run [45473344809](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45473344809), SHA exécuté vérifié, job 138726913757, état observé in_progress/sans conclusion. Sources 14940176512/14950692711/14957845777 épinglées ; 50 tests prévus, non vérifiés. Vérifier G5_AC_1KW_AB, réconciliation v2/v3, 929 FAIL->PASS puissance, gains/pertes à partir des 12 874, doublons et portée, artefact/SHA. L'artefact de sortie conserve le nom tcc-v9-g5-irve-power-scope-ab mais doit être identifié par ID/run/SHA, jamais par nom seul. Aucun prix promu ni nouvelle collecte, aucune modification Production/main, Mac local inaccessible, G5 PARTIAL. Résultats non encore vérifiés.

## 2026-11-24 — G5 : décision utilisateur tolérance AC 1 kW et replay cumulatif autorisés

Utilisateur : « Gardons une tolérance de 1kw pour les 929 à traiter ». Décision normative versionnée PROJECT_SPEC_G0_G9.md, périmètre exact FR mono-type, type/courant AC PASS, nominal positif non conflictuel, écart absolu <=1 kW dans les deux sens. Motif AC_1KW_TOLERANCE_USER_APPROVED et seuil/valeurs/écart enregistrés, aucun élargissement DC/alias/GPS/multi-type au-dessus nominal, aucun changement des puissances nationales. Nouvelle règle opt-in --ac-tolerance avec --power-scope épinglé, code fonctionnel 30629f29606d3369a4d67f2af2086b5615908eda. Même compatibilité dans le contrôle de portée bidirectionnel ; tous autres critères restent. Rejouer v2 et v3 sur SQLite 14940176512, scope 14950692711, comparer chaque décision/vecteur/motif v3 au CSV précédent 14957845777 et vérifier exactement 929 FAIL->PASS, gains/pertes, unicité et portée ; référence A 12 874, pas d'objectif de gain imposé. Épinglage ZIP/CSV/SQLite, nouvelle sortie CSV gzip de 21 980 couples et JSON, pas de nouvelle collecte ni publication. Tests v2, scope, v3 et 13 nouveaux prévus, non vérifiés. Préflight Data Lab 7d81408be5592d6f879af5e570ef94fed0112143, Production b1d102d97ba8647e79514e89b15f82d8dce97a78, aucun run Data Lab en cours/en file ni PR vers/depuis rebuild, ancien run Production 37642387836 autre branche inchangé. Mac local inaccessible. G5 PARTIAL, pas de changement main/Production. Rollback désactiver --ac-tolerance et neutraliser workflow ciblé. Prochaine étape vérification du run, réconciliation et diagnostic des éventuelles pertes avant promotion.

## 2026-11-24 — G5 : correction candidate de granularité validée sur replay exact A/B, +3 262 couples sans perte

Run [45469217885](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45469217885), job 138712271413, code d94ae48476119e426e916fc24b6ebdf20ead6488, completed/success 19:22:53Z. 9/9 tests v2, 11/11 scope, 17/17 A/B = 37/37, public safety PASS. ZIP sources, SQLite et CSV épinglés vérifiés dans runner ; intégrité SQLite, reproduction exacte de chaque décision/vecteur/motif A et réconciliation des effectifs, unicité profil et connecteur B PASS. Artefact 14957845777 (573 768 octets), SHA256 ZIP GitHub e89715b16894f4f3962763ebe002efe172ee4368cbc99a8e1991bbf726b945aa, expiration 24/12/2026 19:22:50Z ; exact-ab.csv.gz SHA ba8d1be2e760ff6dc7706a576bcbc506e443491b10471b5b20e18d1be9a20e33 + ab-report.json. Logs/métadonnées vérifiés ; ZIP résultats non téléchargé indépendamment dans chat.

A/B sur 21 980 couples exacts : 9 612→12 874 MATCH_VALIDATED (+3 262, +33,9%, 3 196 PDC distincts concernés par les gains, pas nécessairement tous nouvellement couverts), 12 238→8 956 contradictions, 124→142 ambiguïtés, 6→8 insuffisances. Les 9 612 paires initiales conservées, zéro perte, zéro doublon. Puissance FAIL→MISSING 3 282, PASS→MISSING 3 268 (accord avec nominal ne prouve pas puissance individuelle), FAIL→FAIL 5 595, MISSING→MISSING 25, PASS→PASS 9 810. Parmi les 3 282 anciens rejets reclassés : 3 262 validés, 18 ambiguïtés, 2 insuffisances. Portée NOT_EVALUATED→PASS 3 262, PASS conservé 9 612. Gains CITEOS 1 642, Interparking 690, SPIE 251, E.Leclerc 201, Freshmile FR1 136, Load Stations 105, autres 237. Aucun prix promu ; MATCH_VALIDATED = identité/rattachement et portée technique auditée, pas calculabilité ni publication. Les 559 998 candidats non exacts restent inchangés par conception ; dispositions projetées sur 581 978 couples (non nouveau registre complet) 12 874 validés, 62 888 ambiguïtés, 344 721 contradictions, 161 495 insuffisances. Option --power-scope strictement épinglée, pas encore intégrée à une nouvelle génération complète ni à Production.

Prochaine étape recommandée après accord : examiner hors ligne les 929 petits écarts AC mono-type de l'audit scope (<=1 kW descriptif), en regroupant par puissance brute nationale, valeur source, précision numérique, type/opérateur et preuves de nominal/arrondi déjà archivées ; distinguer 22,1/22, 7,4/7 et autres cas, sans nouvelle tolérance globale ni inférence de précision non documentée. Autoriser uniquement les écarts justifiés, refaire A/B cumulatif et préserver les 12 874 correspondances ou expliquer toute régression. Les 63 multi-type au-dessus nominal et 1 254 écarts DC mono-type restent à instruire sur preuves, 15 kW recherche uniquement. Puis aliases/fallback, preuves de portée, archive durable et génération Production. G5 PARTIAL, G8/G9 non validés. Préflight Data Lab bb094b778d3c58e6f8a0f01574b9c89830f58206, Production b1d102d97ba8647e79514e89b15f82d8dce97a78, aucun run Data Lab actif/en file, aucune PR depuis/vers rebuild ; Mac local inaccessible. Entrée documentaire uniquement, aucun nouveau run ni changement règle/Production/main.

## 2026-11-24 — G5 : comparaison A/B puissance lancée, résultats en attente

Commit fonctionnel d94ae48476119e426e916fc24b6ebdf20ead6488, parent 9fb6f855b8cea8c53fb04919a4dab94b44b2741e, rebuild/v9-20261020. Run [45469217885](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45469217885), SHA exécuté vérifié, job 138712271413, état observé in_progress/sans conclusion, étapes actives ["Run actions/checkout@11d5960a326750d5838078e36cf38b85af677262"]. 9 tests v2 + 11 audit scope + 17 tests nouveaux prévus (comptes à confirmer), scan public et preuves A/B non vérifiés à cette entrée. Sources 14940176512/14950692711 épinglées. Prochaine action : lire G5_POWER_SCOPE_AB, vérifier reproduction de chaque décision A, transitions et gains/pertes B, absence de doublon, garde d'identité et portée, artefact et SHA ; résultats NON vérifiés. Pas de nouvelle collecte, pas de promotion de prix, aucun changement main/Production. G5 PARTIAL, Mac local non accessible. Comparaison limitée aux couples exacts, pas de nouvelle validation alias/GPS ni recalcul complet du catalogue. Règle candidate opt-in --power-scope, aucun changement de puissance brute.

## 2026-11-24 — G5 : correction candidate de granularité et replay exact A/B autorisés

Accord utilisateur reçu. Préflight Data Lab 9fb6f855b8cea8c53fb04919a4dab94b44b2741e, Production b1d102d97ba8647e79514e89b15f82d8dce97a78, aucun run actif/en file Data Lab, aucune PR depuis/vers rebuild ; ancien run Production 37642387836 en file sur branche tierce, intact. Mac local inaccessible. Sources immuables registre SQLite 14940176512 et preuve de granularité 14950692711, SHA ZIP/CSV/SQLite épinglés dans migration/v9/irve-g5-power-scope-ab-request.json. Règle candidate G5 v3 : seulement identité exacte, multi-type IRVE sans puissance individuelle prouvée, type ET courant PASS, source positive <= nominal PDC : puissance MISSING avec POWER_SCOPE_NOT_COMPARABLE, même si nominal égal ; valeurs nominales, source et delta conservés. Source supérieure au nominal, mono-type, petits écarts AC sans justification et écarts DC non automatiquement assouplis. Pas de kW individuel inventé. Recalcul de portée/cardinalité dans les deux sens avec la même fonction de compatibilité, maintien des autres critères, doublons, ambiguïtés, prix source manquant et preuve positive de portée. Baseline A doit reproduire chaque vecteur, motifs et décision v2 sur 21 980 couples, B utilise la même fonction intégrée au comparateur avec option --power-scope strictement épinglée au snapshot national ; option absente conserve v2, non-exacts inchangés. Export CSV gzip exhaustif des transitions, rapport JSON, gains/pertes par profils/PDC, aucun prix promu. Workflow lecture seule push ciblé, concurrence audit overlay, tests v2 + granularité + nouveaux tests et public safety prévus, non vérifiés à cette entrée. Règle source normative inchangée (application candidate, pas promotion), constructeur IRVE et Production/main intacts ; rollback désactiver l'option et workflow ciblé. G5 PARTIAL. Prochaine action vérifier le run, baseline, tests et artefact, gains/pertes, absence de doublon, portée et cas contradictoires avant toute promotion ou nouvelle étape.

## 2026-11-24 — G5 : audit granularité IRVE terminé et réconcilié, correction à instruire

Run [45457895665](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45457895665), job 138672185707, code e119cd0646328a72dc859e9b5d75eeb1555e7422, completed/success 18:19:32Z. 11/11 tests et public safety PASS, ZIP d'entrées et empreintes fichiers vérifiés dans runner, projection active reconstruite depuis CSV brut égale à celle épinglée. Artefact résultats 14950692711, 1 733 874 octets, ZIP SHA256 aa3cba1e5ee9dde74c0f3d10adf2bb9d511607a582edda6461bde7962575e7e1, expire 24/12/2026 18:19:26Z ; active-pdc-power-scope.csv.gz SHA 196bb587904635159e7d5bbc774a9cd931d7903320ff0b177cf51df59d0637a3, exact-pair-power-scope.csv.gz SHA 149694af388d30104796a632875716a913248c9f28d9d546e4b4baa0f1db5a99, power-scope-report.json. Logs et métadonnées vérifiés ; ZIP résultat non retéléchargé indépendamment dans chat. Sources 14937133575 et 14945123454 inchangées. Aucun fournisseur, nouvelle correspondance, changement constructeur/matching ni publication.

101 856 PDC actifs/124 918 profils réconciliés. Classes exclusives PDC/profils : mono-type nominal seul 70 528/70 528 ; multi-type puissance individuelle non prouvée 24 159/46 458 ; nominal manquant/non positif/conflictuel 7 169/7 932. CSV brut : puissance_nominale unique, cinq colonnes type de prise (EF, Type 2, CCS, CHAdeMO, autre), cable_t2_attache séparé ; pas de champ kW individuel par prise. Mono-type n'est pas preuve indépendante de puissance individuelle. La classe nominal manquant/conflictuel est composite et non ventilée ; ne pas présenter 7 169 comme tous des conflits. 21 980 couples exacts, dispositions inchangées 9 612 validés, 12 238 contradictions, 124 ambiguïtés, 6 insuffisances. Sur 8 877 FAIL puissance : 3 331 ont aussi prise ou courant non PASS (peut inclure MISSING, à ne pas présenter exclusivement comme FAIL), 3 282 multi-type même prise/courant avec source sous nominal, 63 multi-type même prise/courant avec source au-dessus nominal, 929 petits écarts AC mono-type (<=1 kW descriptif, pas tolérance), 1 254 écarts DC mono-type, 18 autres. Somme réconciliée. 3 345 couples multi-type même prise/courant = 37,7% des FAIL puissance, pas 3 345 nouveaux matchs ni nombre d'EVSE distincts ; autres échecs dont unicité restent possibles. Sous nominal surtout CITEOS 1 642, Interparking 690, SPIE 257, E.Leclerc 205 ; petits écarts AC Bouygues 382, SPIE 245 ; DC SPIE 437, Plug Inn 372. Source Electroverse non réputée exacte par défaut, puissance nominale PDC conservée intacte.

Prochaine opération recommandée : après accord, créer projection de preuve séparant puissance nominale PDC, puissance individuelle prouvée et provenance/portée, sans modifier valeurs nationales brutes ni inventer kW EF. Audit A/B hors ligne épinglé : même type/courant et identité exacte, multi-type puissance individuelle non démontrée -> non comparable (MISSING avec motif POWER_SCOPE_NOT_COMPARABLE), conserver valeur originale et écart ; source au-dessus nominal ou conflit réel documenté -> revue, pas acceptation automatique. Ne pas appliquer la règle à toutes les prises sans distinguer portée/preuve ; vérifier petit écart AC uniquement sur justification de nominal/arrondi, DC 15 kW recherche candidat uniquement ; préserver autres FAIL, unicité, portée tarifaire et absence de duplication, ne pas confondre compatibilité technique et autorisation de prix. Examiner impacts par PDC/prise et candidats alternatifs, séparer changements de décisions/rejets et preuve de tarif ; étudier 7 169 PDC nominaux manquants/non positifs/conflits et leurs profils sans extrapoler le gain. G5 PARTIAL, archivage durable et recette non réalisés. Préflight Data Lab 0a42ae6874409a53be7ac8b78e8f2fb76e0585e1, Production b1d102d97ba8647e79514e89b15f82d8dce97a78, aucun run Data Lab actif/en file ni PR vers rebuild, Mac local inaccessible. Cette entrée est uniquement documentation de résultats, aucun nouveau run ni modification Production/main.

## 2026-11-24 — G5 : audit de granularité lancé, résultat à vérifier

Commit d'audit e119cd0646328a72dc859e9b5d75eeb1555e7422 (parent 2a3f762e1d145adb3c38641d0c6855aaec9255f8), branche rebuild/v9-20261020. Run [45457895665](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45457895665), job 138672185707, état observé in_progress/sans conclusion, étapes actives ["Run actions/checkout@11d5960a326750d5838078e36cf38b85af677262"]. SHA exécuté vérifié. Tests et rapport non vérifiés à ce stade ; ne pas traiter le lancement comme un PASS. Entrées IRVE 14937133575 et audit exact 14945123454, empreintes dans migration/v9/irve-g5-power-scope-request.json. Prochaine opération : contrôler ce run, logs G5_POWER_SCOPE_AUDIT / G5_POWER_SCOPE_TOP_OPERATORS, artefact et empreintes, réconcilier les 101 856 PDC, 124 918 profils, 21 980 couples et 8 877 FAIL puissance, puis instruire une correction prouvée. Aucun nouveau run, aucun changement de matching, aucune collecte fournisseur, aucun changement Production/main. G5 PARTIAL. Mac local non vérifiable.

## 2026-11-24 — G5 : audit ciblé de la granularité de puissance IRVE autorisé

Autorisation utilisateur de poursuivre l'audit recommandé. Préflight Data Lab 2a3f762e1d145adb3c38641d0c6855aaec9255f8, Production b1d102d97ba8647e79514e89b15f82d8dce97a78, aucun run Data Lab actif/en file ni PR vers rebuild ; ancien run Production 37642387836 en file sur autre branche, aucune intervention dessus. Mac local non accessible. Sources immuables : IRVE 14937133575 (CSV statique brut, statique compact, dynamique), audit exact 14945123454 (21 980 couples, 8 877 FAIL puissance), SHA ZIP et fichiers épinglés dans migration/v9/irve-g5-power-scope-request.json. Audit-only : reconstruire la projection active depuis le CSV brut et comparer exactement ses identités/profils (101 856 PDC, 124 918 profils), inventorier toutes les colonnes de type de prise y compris non supportées, valeurs nominales brutes et doublons, distinguer multi-type, mono-type nominal seul, valeurs manquantes/conflits. Classifier écarts même prise/courant, source au-dessus/au-dessous nominal, petits écarts AC et écarts DC à instruire ; garder tous autres échecs et décisions initiales. Aucune puissance individuelle inventée, aucune tolérance de validation nouvelle, aucun changement de matching ni de catalogue, aucune collecte fournisseur ni publication. Workflow push ciblé lecture seule, même concurrence que l'audit overlay ; tests unitaires et public safety prévus, NON VÉRIFIÉS à cette entrée. Résultat attendu : CSV gzip par PDC actif et couple exact, rapport JSON et empreintes. Prochaine action : vérifier run, logs, réconciliation, artefact et analyser résultats avant correction justifiée. G5 PARTIAL ; retour arrière = supprimer/neutraliser le workflow isolé, données et moteur inchangés.

## 2026-11-24 — Audit G5 des contradictions exactes terminé : granularité de puissance IRVE à corriger avant nouveau rapprochement

Run https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45444835720, job 138625610539, SHA 8475fdaa3bccb0b2352404b959ea6d35316bea10, success 17:07:30Z. 7/7 tests PASS, vérification ZIP et SQLite épinglés, intégrité et réconciliation des cohortes PASS dans runner. Artefact résultats 14945123454, ZIP 1 806 492 octets, SHA256 GitHub d398d11848fb31e7bda57b54dc8ff84fc487ef2e67533a19ab5f3de888ed2c6f, expire 24/12 17:07:23Z. Sorties CSV gzip exhaustives par couple, profil et EVSE + rapport JSON. Logs/metadata vérifiés, ZIP résultats non retéléchargé indépendamment dans chat. Source unique registre 14940176512, IRVE 14937133575. Aucun appel fournisseur, rebuild, modification de matching ou publication.

Population exacte 21 980 couples : 9 612 validés, 12 238 contradictions, 124 ambiguïtés, 6 insuffisances. Contradictions : 12 avec alternatives validées des deux côtés, 3 131 profil national avec autre connecteur validé, 3 218 connecteur source avec autre profil validé, soit 6 361 (52,0%) avec alternative sur au moins un côté ; 5 834 sans paire compatible des deux côtés, 43 autres alternatives compatibles/non vérifiées. Une alternative validée ne couvre pas automatiquement le profil restant. 12 066 EVSE nationales distinctes dans cohorte exacte : 6 389 tous profils validés, 3 217 partiellement, 2 389 aucun profil compatible, 71 aucune validation mais profil non contradictoire ; 9 606 avec au moins un profil validé (79,6% de cohorte, PAS du catalogue total). 15 416 profils nationaux : 9 612 validés, 5 731 sans paire compatible, 71 techniquement concordants non validés, 2 non contradictoires avec données techniques manquantes. Source : 12 182 EVSE composites, 6 482 totalement, 3 124 partiellement, 2 450 aucun profil compatible, 126 non validés avec alternative non contradictoire. 15 472 connecteurs source : 9 612 validés, 5 732 sans paire compatible, 126 concordants non validés, 2 données manquantes non contradictoires. Motifs non exclusifs sur 12 238 couples : puissance 8 877, type 6 691, courant 98, unicité 153 ; 5 427 puissance seule, 3 277 prise seule, 3 287 prise+puissance (autres combinaisons dans rapport).

Écarts même type et même courant les plus fréquents : CITEOS EF IRVE 22 kW / source 4 kW 1 468 couples ; Interparking EF 22/2 kW 409 et 7/2 kW 281 ; Plug Inn CCS 320/380 kW 372 ; Bouygues TYPE2 22,1/22 kW 364 ; SPIE TYPE2 7,4/7 kW 184, EF 22/2 kW 177 ; E.Leclerc EF 22/3 kW 162 ; CITEOS EF 22/3 kW 149. Type brut : IRVE EF 22 vs source Type 2 2 803, IRVE Type 2 22 vs source Schuko 2 639, etc. Ne pas assimiler EF et Type 2 ; la plupart des permutations peuvent être des candidats normaux de PDC multi-prise. Contrôle direct scripts/france/build_france_irve_static_v9.py : lit puissance_nominale (ou puissance) par ligne PDC, convertit/arrondit à 0,1 kW, réplique cette même valeur pour CHAQUE plug_types de la ligne ; pas de preuve d'une puissance individuelle par prise. C'est un défaut de granularité de la projection TCC pour comparer puissance EVSE nominale avec connecteur Electroverse. Il ne prouve pas que toutes les valeurs source sont correctes ni que toutes les différences sont expliquées. Les 22,1/22 et 7,4/7 sont des cas de nominal/arrondi à instruire sur preuves, non tolérance nouvelle ; 320/380 et autres écarts DC restent à justifier sur données techniques existantes, 15 kW n'est pas tolérance de validation. Les profils IRVE dont la puissance individuelle n'est pas démontrée doivent être distingués des contradictions réellement comparables ; ne pas inventer puissance EF standard ni modifier silencieusement la puissance nominale nationale.

Prochaine étape recommandée (attendre accord avant correction) : audit ciblé sur CSV IRVE brut déjà archivé dans 14937133575 et registre exact, inventorier PDC multi-type et portée réelle de puissance_nominale, isoler les EF dont la puissance nominale a été dupliquée, conserver nominal PDC séparé de puissance individuelle non vérifiable ; corriger la comparaison de granularité sans relâcher les critères ni attribuer une valeur arbitraire, tester avant/après par EVSE/prise, réexaminer petits écarts AC justifiés et écarts DC sur preuves existantes. Ne pas assimiler MISSING à PASS ni ignorer une puissance vraiment contradictoire. Maintenir preuves de portée/unicité, journal des motifs et sources. Puis poursuivre alias/fallback et archivage pérenne. G5 PARTIAL, aucun nouveau run lancé lors du bilan. Préflight parent e7e8de39d9f1434f1a32e7a728e88105d6839279, Production b1d102d97ba8647e79514e89b15f82d8dce97a78, aucune exécution active/en file, aucune PR rebuild parmi celles vérifiées ; Mac local non accessible.

## 2026-11-24 — Analyse ciblée des écarts exacts G5 autorisée et lancée

Préflight distant Data Lab ecc0717176d05c4a3a236887fbe5a7c6cd8f7070, Production b1d102d97ba8647e79514e89b15f82d8dce97a78, aucune exécution active/en file ni PR rebuild parmi celles vérifiées ; local Mac/Codex non accessible. Autorisation utilisateur de lancer l'étape suivante. Commit 8475fdaa3bccb0b2352404b959ea6d35316bea10 sur rebuild/v9-20261020 : scripts/audit_electroverse_g5_exact_mismatches.py, tests/test_electroverse_g5_exact_mismatches.py, .github/workflows/v9-electroverse-g5-exact-audit.yml et migration/v9/electroverse-g5-exact-audit-request.json. Workflow dédié push ciblé, sans schedule, permissions lecture, concurrence commune avec audit overlay. Ne pas modifier la requête pour relancer sans coordination. Run https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45444835720, SHA exécuté 8475fdaa3bccb0b2352404b959ea6d35316bea10, état constaté [{"id":138625610539,"status":"in_progress","conclusion":null,"active":["Run actions/checkout@11d5960a326750d5838078e36cf38b85af677262"]}]. Résultats/tests/artefact NON VÉRIFIÉS à cette entrée.

Entrée unique : registre du run 45432872279, artefact 14940176512, ZIP SHA 0dad4250be2ae38942fdaec1895643db76784c9352e209507a8a56b2434d6d37, SQLite SHA da247ada9981e2b17dda2aee192a413fb31e3691d1a4f2b0366029e557067287, IRVE artefact 14937133575. Contrôles ZIP, SQLite intégrité, provenance métadonnées et réconciliation des effectifs exacts prévus. Analyse en lecture seule, sans reconstructeur ni appels IRVE/Electroverse, sans changement de règle ni publication. Population attendue selon le manifeste épinglé : 21 980 couples exacts dont 9 612 validés, 12 238 contradictions, 124 ambiguïtés, 6 insuffisances. Vérifier ces totaux par lecture réelle. Classification des alternatives par source connecteur ET profil national ; agrégation séparée par EVSE source (locationPk,evsePk) et EVSE national (stationId,id_pdc). Distinction entre absence de paire compatible et autre profil déjà validé, sans considérer toute borne validée sur une prise comme entièrement couverte. Ventilation des motifs cumulables, type brut/normalisé, courant, puissance (bandes <=1, <=5, <=15, <=30, <=50, <=100, >100 kW, séparées par AC/DC et même prise/courant), combinaisons par CPO national et code source non vérifié. Les valeurs de puissance nominale IRVE et connecteur source peuvent mesurer des réalités différentes : ne pas valider par simple tolérance ; un écart sans alternative reste une anomalie à instruire, pas preuve de faute fournisseur. Export exhaustif CSV gzip des couples, profils et EVSE, rapport JSON, hashes export, artefact Actions temporaire. Sept tests unitaires ajoutés ; résultat en attente. G5 PARTIAL, registre durable/liaison au snapshot servi non réalisés. Prochaine étape : lire G5_EXACT_MISMATCH_ANALYSIS, examiner les causes réellement discriminantes et preuves existantes, proposer corrections ciblées documentées, puis alias/fallback. Aucun changement Production/main ni nouveau snapshot.

## 2026-11-24 — G5 v2 sur IRVE actualisé : audit terminé, G5 PARTIAL

Run https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45432872279, job 138582660769, SHA exécuté 0b1ae85a7432d6cc89da80a0f33ae1d710b7419a, completed/success 24/11 16:07:39Z. 38/38 Node +9/9 Python PASS, public safety PASS, trois ZIP sources téléchargés et SHA vérifiés dans runner, IRVE_PIN_VERIFIED et G5_REAL_COMPARISON attestent la nouvelle paire nationale sans fallback : artefact 14937133575, set SHA 11793e0425b15327737543b1b68f0cd00033c2c74bb430083665651516d1071d ; statique all SHA e721014651a59570fd4a8602a8d284f3ee5990c41b4d82f18099926a3478d567, dynamique gzip SHA d7ad73c88e359f4823481e2ec969b4da53cf671cb4f590c040e580b22ae46286. Sources tarif/statut Electroverse 14760747281 /14838028097 inchangées, zéro fournisseur/publication.

IRVE 24/11 15:48:51Z : 174 948 PDC /53 765 stations statiques ; 101 856 PDC en_service /31 438 stations /124 918 profils actifs ; 8 863 hors_service, 5 204 inconnu, 59 025 sans statut. 581 978 couples candidats, 21 980 exacts, 9 612 MATCH_VALIDATED exacts (contre 9 485 sur 20/10, différence nette +127, pas une liste de 127 nouveaux IDs vérifiée), 12 238 contradictions exactes, 124 ambiguïtés exactes, 6 preuves insuffisantes exactes ; 9 725 couples exacts passent courant/type/puissance. Tous candidats : 348 003 contradictions, 62 870 ambiguïtés, 161 493 preuves insuffisantes, 9 612 validés ; dispositions profils IRVE : 9 612 validés, 59 927 candidats non résolus, 55 379 sans candidat dans cache, total 124 918. 33 495 lignes connecteur source sans candidat ; tous 581 978 couples pays/CPO MISSING non bloquant autonome. Motifs non exclusifs tous candidats : power FAIL 291 059, plug FAIL 207 177, current FAIL 79 109, evse_uniqueness FAIL 188 288 ; ne pas attribuer ces totaux à la seule population exacte. Pour identifier de vraies anomalies il faut dédupliquer par EVSE/prise et distinguer candidats alternatifs incompatibles d'une borne sans aucun profil compatible, puis contrôler les nomenclatures et la granularité puissance nominale IRVE vs connecteur source. Résumé agrégé ne permet pas de ventiler les 12 238 contradictions exactes par cause. Audit-only, aucune conclusion sur calculabilité/prix réellement servis. Registry CPO encore 0, alias/fallback/groupes à prouver.

Artefact de comparaison #14940176512, ZIP 33 183 670 octets, SHA256 GitHub 0dad4250be2ae38942fdaec1895643db76784c9352e209507a8a56b2434d6d37, expire 24/12 16:07:30Z ; SQLite 640 471 040 octets, SHA déclaré runner da247ada9981e2b17dda2aee192a413fb31e3691d1a4f2b0366029e557067287 ; 72 patterns, intégrité et réconciliation runner PASS. ZIP/SQLite résultats non téléchargés indépendamment dans chat. Overlay historique #14939831973, ZIP SHA 6221c62ab451602f1a316b5137d01dc719cea987622a8b56f2a4908d00b2be16, 84 309 offres, A/B 84 309→84 309, 0 ajouts, 0 variation prix/cible/portée, 0 panne filtrée car observations historiques hors fenêtre 24 h (ne prouve pas remise en service). Ce n'est pas un overlay conforme au nouveau scope G5 ; ne pas promouvoir ni assimiler aux 9 612 matchs. Workflow ponctuel IRVE neutralisé, Production/main intacts. Préflight parent 51c070a958febb87a6986dca2ee618c895a4130c, Production b1d102d97ba8647e79514e89b15f82d8dce97a78, aucun run actif/en file, aucune PR rebuild ouverte parmi celles vérifiées, Mac local non accessible.

Prochaine priorité recommandée : audit hors ligne ciblé du registre déjà généré (artefact épinglé 14940176512), ventilation des contradictions exactes par critère, opérateur, type, AC/DC, amplitude puissance, par identifiant source/national unique ; séparer incompatibilités normales d'autres profils de vrais échecs sans alternative valide et mesurer recouvrement des anciens/nouveaux matches si nécessaire. Puis corriger seulement écarts justifiés (normalisation, puissances nominales vs connecteur, alias connus), sans relâcher les règles ni nouvelle collecte. Étudier preuves alias/groupe/fallback existantes ensuite, portée tarifaire, archive pérenne avant expiration des artefacts, index versionné par génération. G5 PARTIAL ; aucune nouvelle exécution ou correction code déclenchée lors de ce bilan, uniquement mémoire/evidence. Ne pas déclarer G5/G8/G9 PASS.

## 2026-11-24 — IRVE actualisé, artefact épinglé et comparaison G5 relancée

Collecte ponctuelle #45429451268, job 138570363599, code c6d0f037b3d3de324da5d490e9506afcff9f5250, success à 15:49:36Z. Test dynamique et public safety PASS ; valid_output + digest de l'objet et réconciliation scope actif PASS dans runner. Snapshot statique/dynamique du 24/11 15:48:51.663109Z (heure d'acquisition, pas fraîcheur universelle des observations) : 53 765 stations, 174 948 PDC statiques ; 101 856 en_service sur 31 438 stations, 124 918 profils actifs ; 8 863 hors_service, 5 204 inconnu, 59 025 sans statut, total réconcilié. 136 011 lignes dynamiques, 115 923 PDC statiques renseignés, 7 893 lignes dynamiques non rapprochées, 0 invalide. Comparaison précédente IRVE 20/10 : 94 791 PDC actifs, +7 065. Artefact national 14937133575 (17 958 784 octets, ZIP SHA256 b538f0b420e046dcd597f5c3b32fd5a2ff76451a9ad6ff97f2ea66892a9f3719, expiration 24/12 15:49:29Z), set SHA 11793e0425b15327737543b1b68f0cd00033c2c74bb430083665651516d1071d. Statique source SHA 6556dea1a9237640fca0c9c50ca380ea46f8044031a13d2c684f53b9837d094f, all SHA e721014651a59570fd4a8602a8d284f3ee5990c41b4d82f18099926a3478d567 ; dynamique source SHA 186fb45b97e41f9120b4fd74babf7c6f2538802365cd29b917fc23e9d1c3999f, gzip SHA d7ad73c88e359f4823481e2ec969b4da53cf671cb4f590c040e580b22ae46286. Logs + metadata vérifiés ; téléchargement/contrôle ZIP indépendant prévu dans nouveau run, non effectué dans chat. Checkout statique ancien intact, pas d'import Production.

Autorisation utilisateur de continuer reçue ; préflight Data Lab a4b5b91cf20eb1c047674bb6fc7b314f188ad01c, Production b1d102d97ba8647e79514e89b15f82d8dce97a78, aucun run actif/en file avant intervention, PR vérifiées, Mac local non vérifiable. Commit 0b1ae85a7432d6cc89da80a0f33ae1d710b7419a, parent a4b5b91cf20eb1c047674bb6fc7b314f188ad01c, branche rebuild/v9-20261020 : .github/workflows/v9-electroverse-overlay-offline-audit.yml, scripts/audit_electroverse_g5_real_matching.py, migration/v9/electroverse-overlay-audit-request.json, .github/workflows/v9-irve-national-one-time-refresh.yml (job neutralisé if false après collecte unique, aucune réactivation de calendrier). Épinglage run/artefact/ZIP SHA/code SHA/set SHA/fichiers statique-dynamique ; vérification ZIP, chemin sûr, manifeste/objets complets, validate_output, provenance dans résumé SQLite. Le script exige désormais --national-root et --national-provenance ; aucun fallback silencieux vers le 20/10. Tarifs/statuts Electroverse immuables inchangés 14760747281 / 14838028097. Même règles G5 v2 et même cache, aucune nouvelle collecte, aucun changement de prix/constructeur ni Production/main. Overlay historique reste comparateur candidat, non validation nouvelle ; fenêtre de panne historique peut vieillir.

Run offline #45432872279 https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45432872279, SHA 0b1ae85a7432d6cc89da80a0f33ae1d710b7419a, lancé/queued/in_progress, état jobs au constat [{"id":138582660769,"status":"in_progress","conclusion":null,"active":["Run actions/checkout@11d5960a326750d5838078e36cf38b85af677262"]}]. Résultat/tests/artefacts NON VÉRIFIÉS. Prochaine action : contrôler logs IRVE_PIN_VERIFIED et G5_REAL_COMPARISON, réconcilier scope 101 856 PDC /124 918 profils, examiner correspondances exactes vs précédent 9 485 et motifs non exclusifs ; vérifier intégrité/size/retention du journal. Compléter preuves alias, groupes et fallback, contrôle des contradictions réellement observées, archive durable liée au snapshot servi ; G5 PARTIAL. Ne pas confondre nouvelles correspondances audit et prix publiés.

## 2026-11-24 — Actualisation ponctuelle IRVE autorisée, run lancé ; G5 v2 sur ancien snapshot validé techniquement

Autorisation utilisateur : actualiser IRVE une fois avant réactivation globale des workflows. Préflight : Data Lab f7aa39285e2c47acec6cf45a60de67d8abc2ed6b, Production b1d102d97ba8647e79514e89b15f82d8dce97a78, aucun run actif/en file avant lancement, PR contrôlées ; état local Mac non accessible. Collecteur migré FR:irve_national / v9_rebuild/france_irve.py réutilisé sans changement de méthode, pas de secret requis. Une collecte plus récente que le checkout existe déjà : job 132420724919 du 14/11, run 43586082154 (global failure pour autre source), artifact 14110427373 SHA ZIP 3c3434b3bf18551dfd130054e43dac8233899d25381116c5b3aed14cabd0a011, evidence docs/v9-rebuild/evidence/restoration-20261114/france-national-handoff.json ; jamais utilisée par le dernier audit, conservée comme précédent last-good validé selon cette preuve. Ne pas supposer dernier snapshot réellement servi.

Commit c6d0f037b3d3de324da5d490e9506afcff9f5250 : .github/workflows/v9-irve-national-one-time-refresh.yml et migration/v9/irve-national-refresh-request-20261124.json, déclencheur push uniquement sur fichier de demande et branche rebuild/v9-20261020, ni schedule ni workflow_dispatch général, permissions lecture, un source ID exact, un worker/une tentative, aucun appel Electroverse, aucune publication. Connecteur ne permet pas workflow_dispatch ; choix d'un workflow ponctuel isolé plutôt qu'un rerun de l'ancien job sur SHA ancien. Ne pas retoucher le fichier de demande sans nouvelle autorisation. Retirer/neutraliser ce déclencheur ponctuel au closeout, pas de changement des workflows récurrents ni main/Production. Run https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45429451268, exécuté sur c6d0f037b3d3de324da5d490e9506afcff9f5250, état au constat in_progress, jobs [{"id":138570363599,"status":"in_progress","conclusion":null,"active":["Verify single-source authorization and existing dynamic fixture"]}]. Validation et nouvel artefact NOT VERIFIED. Vérifier hashes bruts, manifeste/objets immuables, projection enServicePdcIds, comptes exclusions et absence d'identités incohérentes ; si échec last-good intact. Artefact attendu tcc-v9-collection-FR_irve_national, irve-refresh-summary.json, aucune mise à jour silencieuse du checkout. Prochaine étape : vérifier run, artefact ZIP et SHA ; épingler la nouvelle paire statique/dynamique vérifiée dans l'audit G5 (chemin artifact distinct du checkout), avec manifeste de provenance ; relancer comparaison hors ligne après validation de la collecte. G5 reste PARTIAL.

Résultat précédent G5 v2 (run 45390422307, job 138432339721, SHA f7841ea629347f1746455e46e7de8bd03be44cbe, success 24/11 12:09:56Z) : 38 tests Node + 9 Python PASS, scan sécurité PASS. Sur IRVE 20/10 : 171 042 PDC statiques / 52 755 stations ; 94 791 en_service / 29 121 stations et 116 348 profils actifs, 8 504 hors_service, 4 289 inconnu, 63 458 statut manquant. 542 119 couples candidats dont 21 553 exacts, 9 485 MATCH_VALIDATED exacts, 11 935 contradictions, 127 ambiguïtés, 6 insuffisances exactes ; 118 matchs validés avec panne récente au moment de l'écran historique (éligibilité distincte). Ensemble candidats : 314 644 contradictions, 59 417 ambiguïtés, 158 573 insuffisances et 9 485 validés. Tous 542 119 couples ont pays/CPO non vérifiables, non bloquants par eux-mêmes. 54 130 profils actifs avec candidats non résolus, 52 733 sans candidat dans cache, 9 485 validés. SQLite 598 401 024 octets, SHA fff0c6a404a917f5ca5181e6351bfddc0100657fc591f5ce4eae7fe9e6c5e64a ; 58 patterns. ZIP artefact 14919240406, 31 393 545 octets, SHA 82bdc90d1ba4d97a5413b3d633281c2a15c2fadd2fd4218d812ec6302d8bae54, expire 24/12 12:09:48Z. Contrôle runner PASS, ZIP non retéléchargé indépendamment. Overlay historique reconstruit 83 032 offres (fenêtre de panne historique vieillissante, distincte des nouveaux matchs et de Production), artefact 14918068387 digest 25bebf8cfee5c043f33877dc49754135fa1036afc179bf283a71842055a0896d. Pas de validation intégrale G5, alias/fallback et portée groupée, contrôle positif CPO/pays quand renseignés, archive pérenne et liaison au snapshot servi restent à traiter. Ne pas conclure à un taux de couverture global à partir des couples candidats.

## 2026-11-24 — Corrections G5 autorisées et implémentées : IRVE opérationnel et MISSING non bloquant ; run lancé

Commit f7841ea629347f1746455e46e7de8bd03be44cbe (parent bd59d7c0486fe2383fada9fbebed53c4eedb7dc9), branche rebuild/v9-20261020 : scripts/audit_electroverse_g5_real_matching.py, tests/test_electroverse_g5_real_matching.py, migration/v9/electroverse-overlay-audit-request.json (seulement blancs, mêmes pins). Préflight branches Data Lab/Production, PR et runs vérifiés, aucun run concurrent avant déclenchement ; local Mac non vérifiable. Exécution offline #45390422307 https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45390422307, SHA f7841ea629347f1746455e46e7de8bd03be44cbe ; état constaté queued/in_progress, résultat/artefact NON VÉRIFIÉS. Jobs au constat : [{"id":138432339721,"status":"in_progress","conclusion":null}].

Sources nationales : fichiers statique et dynamique du 20/10 retrouvés identiques dans main/rebuild ; la preuve du rapport de crosswalk permet de vérifier leurs hashes source, propriétaires, couverture et réconciliation dans le runner. Aucun IRVE plus récent vérifié dans ces branches (ne pas prétendre absence de tout autre artefact). Projection strictement enServicePdcIds, raw exact IDs, garde non vide/last-good, table national_operational_scope pour toutes exclusions (hors_service/inconnu/MISSING), contrôle d'unicité sur maître statique entier, statique intact. Date historique, pas disponibilité actuelle. Cache tarifs/statuts source inchangé : 14760747281 et 14838028097.

MISSING pays/CPO/autres attributs non bloquant à lui seul, valeurs non vérifiables tracées séparément, FAIL réel et ambiguïtés séparés, NOT_EVALUATED explicite. Exact unique + scope positif par connecteur et profil national, cardinalité bijective, absence de contradiction permettent MATCH_VALIDATED même si attributs manquants ; preuve limitée aux profils compacts et au prix source identifiable, pas calculabilité tarifaire. Groupe/fallback/aliases nécessitant preuves complémentaires restent UNRESOLVED_INSUFFICIENT_EVIDENCE, pas de promotion. Les motifs multiples sont conservés dans SQLite avec table criterion_pattern pour réduire redondance ; résultat exact distinct et comptage des motifs manquants. Recette ajoutée pour MISSING pays/CPO accepté avec preuve scope, portée insuffisante et 4 statuts nationaux, dont chevauchement invalide. G5 PARTIAL, tests réels et volume à vérifier sur run. L'audit peut encore sous-classer certains opérateurs/aliases ou confondre des incompatibilités de candidats et défauts réels ; à analyser après exécution. Aucun appel fournisseur, aucun changement constructeur historique, aucun import Production/main, aucun archivage permanent achevé. Dernier overlay historique 81 700 offres inchangé. Prochaine étape : lire logs, résultats exacts, exclusions nationales, comparaison des motifs, intégrité et taille registre ; compléter preuves alternatives et pérennisation. Ne pas déclarer G5 PASS ou prix effectivement servi sans preuve.

## 2026-11-24 — Précision utilisateur : IRVE en_service uniquement dans projection comparative ; attributs Electroverse absents non bloquants

Décision normative : voir PROJECT_SPEC_G0_G9.md, complément G5 du 24/11. Filtrer la projection nationale de comparaison sur les seuls PDC explicitement en_service dans le snapshot dynamique IRVE compatible, disponible ou occupé au sens opérationnel ; hors_service, inconnu et statut national absent exclus de la projection (conserver source brute, motifs et réintégration ; last-good si source indisponible). Ne pas confondre en_service IRVE et libre/occupé live. Vérifié dans scripts/france/build_france_irve_dynamic_status_v9.py : enServicePdcIds déjà produit, états en_service/hors_service/inconnu, statique intact. Le dernier audit réel #45350803713 utilisait toutefois all.json.gz statique sans filtre dynamique ; corriger son périmètre et utiliser dernier snapshot statique/dynamique compatible vérifié.

Un champ Electroverse vide/non comparable est MISSING (non vérifiable), non bloquant à lui seul ; code opérateur sans preuve de libellé également non vérifiable, pas contradiction. Conserver tous les contrôles/motifs et valeurs. Ne pas inventer de données ni confondre absence et FAIL ; accepter exact/alias unique avec identité et portée tarifaire positivement prouvées malgré attributs manquants. Fallback adresse/GPS avec preuves positives suffisantes pour identité EVSE unique, sans proximité seule ; sinon UNRESOLVED_INSUFFICIENT_EVIDENCE, distinct de contradiction. Les contradictions réelles non justifiées, ambiguïté, portée/homogénéité non prouvée demeurent bloquantes. NOT_EVALUATED n'est pas MISSING. Corriger code d'audit qui ajoutait MISSING à blocking, tester les cas acceptés/rejetés et absence de preuve, analyser sur périmètre actif ; conserver les anciens résultats comme historique. Aucun nouveau run/collecte ni modification Production. Règles enregistrées, implémentation NOT TESTED ; G5 PARTIAL. Parent 8b2e2744c95aeeef2cb0fee73a6d254ea25b074c vérifié, aucun run actif/en file au préflight, HEAD Production b1d102d97ba8647e79514e89b15f82d8dce97a78, local Codex non accessible. Prochaine opération : identifier sources nationales compatibles disponibles, corriger les deux points et relancer comparaison offline sans nouvelle collecte fournisseur, après accord de poursuite. Optimiser et archiver le journal durable avant G5/G8/G9 PASS.

## 2026-11-24 — Comparaison réelle IRVE ↔ Electroverse #45350803713 terminée : audit PASS, G5 PARTIAL

Run https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45350803713, job 138296452238, SHA exécuté 1cc6451b048dfe86cb464a3ecaf9f4f152bc65df, completed/success le 24/11 à 07:52:07Z. 38/38 Node + 6/6 Python PASS, scan public PASS, intégrité et réconciliation SQLite contrôlées dans le runner, 0 fournisseur, 0 publication. Artefact comparaison #14899674011, ZIP 62 273 132 octets, digest GitHub sha256:9d51c1ce608b94bd24b6f00d74da94315f9c72fdf2cdf417aac0bb3bbdc935e4, expire 24/12/2026 07:51:41Z ; SQLite 4 231 417 856 octets, SHA256 déclaré par le run 163ada1f54b62f4943e4ed1602b7886498b27cd7d8b795906d4fe184da38b834. ZIP/SQLite non retéléchargés ni contrôlés indépendamment dans cette session ; compteurs issus des logs CI. Artefact overlay historique #14901030259, digest sha256:94ab977c31a445a0f2f7c946d88ca969f9566f457ef8871bddc1180f955be65d. A/B 84 309 →81 700, 2 609 suppressions de la vue active par panne, 0 ajout et 0 dérive prix/cible/portée parmi offres communes. Ne pas confondre cet overlay historique avec validation nouvelle G5.

Périmètre : IRVE statique du 20/10/2026 (52 755 stations, 171 042 EVSE uniques, 218 239 profils EVSE/type/puissance), cache Electroverse 22 818 sites, 113 383 lignes connecteur (incluant éventuel placeholder sans prise). 881 376 couples candidats comparés ; 107 984 profils nationaux avec candidats, 110 255 sans candidat dans ce cache ; 698 lignes sources sans candidat. 37 745 couples à identifiant exact, dont 14 110 passent simultanément courant/type/puissance ; 23 635 ne passent pas tous ces tests (échecs ou manque, pas autant de bornes distinctes). 0 MATCH_VALIDATED, tous les couples UNRESOLVED. Motifs non exclusifs sur couples candidats : country MISSING 881 195 / FAIL 181 ; operator MISSING 881 376 ; evse_identity MISSING 841 393 ; power FAIL 538 839/MISSING 124 ; plug FAIL 293 813/MISSING 922 ; current FAIL 81 587/MISSING 922 ; evse_uniqueness FAIL 264 096. Ces chiffres ne sont PAS des nombres d'erreurs réelles par borne : le repli compare aussi des candidats incompatibles. Le pays manquant masque les autres premiers motifs. Le cache mapping contient lat/lon pour 22 818 sites, operatorId pour 22 816, champs address/name/operator pour 2 seulement ; aucun champ pays observé. Registry CPO 0 pair. Portée, cardinalité/homogénéité restent NOT_EVALUATED par conception : aucun PASS G5 possible. L'IRVE compact ne fournit pas les IDs physiques de prises individuelles.

Prochaine action recommandée avant nouveau run (attendre accord si changement de scope) : (1) retrouver le snapshot IRVE le plus récent déjà collecté et vérifier sa provenance/format, ne pas imposer une collecte nouvelle ; (2) rétablir preuve pays depuis inventaire/filtrage national historique vérifiable en gardant cas BE/frontaliers, sans simplement assigner FR par défaut ; (3) établir CPO sur toute preuve indépendante recevable, non seulement operatorId, vérifier sources disponibles ; (4) hiérarchiser les motifs réellement discriminants par EVSE/candidat (exact et alias en priorité, sans confondre incompatibilités de candidats alternatifs avec défauts de données), auditer les 23 635 couples exacts non entièrement conformes et compléter cardinalité, portée, homogénéité ; (5) compacter SQLite en normalisant/dédupliquant les valeurs et motifs par tables et en conservant tous les candidats, puis assurer archive pérenne autorisée et index par génération. Vérifier raisons, valeurs et récupération après renouvellement avant G5/G8/G9 PASS. Aucune nouvelle modification du constructeur ni Production ; aucun nouveau run lancé par cet audit. HEAD parent 83090cb879fc229baff9a9d882b7472861055dad, aucun run actif/en file constaté, Mac local inaccessible.

## 2026-11-24 — Comparaison réelle IRVE ↔ Electroverse (G5) autorisée et lancée hors ligne

Décision utilisateur du 24/11 (b65613cb48ca44fa4845b901c5eb07a3b4860aff) lue et vérifiée avant intervention ; HEAD Data Lab et Production contrôlés, aucun run actif/en file avant lancement. État local Mac/Codex inconnu. Commit d'implémentation et déclenchement 1cc6451b048dfe86cb464a3ecaf9f4f152bc65df sur rebuild/v9-20261020, parent b65613cb48ca44fa4845b901c5eb07a3b4860aff : scripts/audit_electroverse_g5_real_matching.py, tests/test_electroverse_g5_real_matching.py, workflow offline existant et changement blanc dans la requête de lancement (valeurs fonctionnelles et artefacts source inchangés).

Run https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45350803713 ; job 138296452238 ; SHA exécuté 1cc6451b048dfe86cb464a3ecaf9f4f152bc65df ; in_progress constaté 24/11 ; résultat final et artefact de comparaison NON VÉRIFIÉS à cette entrée. Utilise les artefacts immuables 14760747281 (tarifs) et 14838028097 (statuts) ; maître national IRVE statique versionné 2026-10-20T07:36:07Z, allSha256 f5bbc827032409cd2242b7429327af93ba3c0efce88785deea260b128065d2df, 52 755 stations /171 042 identifiants EVSE (date du snapshot, ne pas prétendre au dernier IRVE national collecté). Comparaison sur tous profils station/EVSE/type/puissance du snapshot et connecteurs du cache ; candidats ID exact, aliases documentés, liens overlay historiques et repli site adresse/GPS/ancien mapping. SQLite indexé par identifiants nationaux et source, nom/adresse station, valeurs originales, raisons multiples PASS/FAIL/MISSING/NOT_EVALUATED/NOT_APPLICABLE, mesure et seuil, dispositions nationales/source même sans candidat. L'ancien overlay est une piste, non preuve indépendante ; le registre CPO reste vide, les contrôles de portée tarifaire/cardinalité/homogénéité non réalisés restent explicitement NOT_EVALUATED. Audit sans promotion de prix. Le futur artefact tcc-v9-electroverse-g5-real-matching doit contenir g5-matching.sqlite et summary.json avec SHA, compteurs et filiation. Rétention Actions 30 jours : archive durable et liaison au snapshot réellement servi restent à mettre en oeuvre avant G5/G8/G9 PASS.

Prochaine action : inspecter le run et les logs, vérifier les tests et le ZIP, l'intégrité SQLite et les compteurs réconciliés, analyser les écarts réels (notamment type/puissance), établir preuves CPO et portée par prise, puis valider/archive durable. Aucun appel fournisseur, aucun import Production, aucun changement main ou constructeur tarifaire. G5 PARTIAL, dernier overlay validé 81 700 offres / artefact 14867028669 ; ne pas le confondre avec le résultat de cette nouvelle comparaison. Ne pas relancer en concurrence.

## 2026-11-24 — Décision utilisateur : grille G5 station/EVSE/prise et historique des motifs de rapprochement

Le cahier des charges G5 est complété par la grille approuvée : identifiants exacts/alias + CPO, sinon adresse OU GPS 5–10 m + CPO ; contrôle systématique par prise même avec ID exact (AC/DC, type, puissance AC hors arrondi justifié, DC tolérance 15 kW uniquement pour rechercher des candidats et écart à justifier, unicité/cardinalité, portée du prix et homogénéité des groupes). La preuve du CPO n'est pas exclusivement un crosswalk numérique : toute preuve indépendante fiable et documentée est recevable. IRVE reste maître, contrôle technique de panne après matching.

Exigence nouvelle : conserver, par station/EVSE/prise et par candidat examiné, chaque critère bloquant constaté et premier motif, résultats PASS/FAIL/MISSING/NOT_EVALUATED/NOT_APPLICABLE, valeurs observées/normalisées, écarts, seuils, justification, méthode et provenance de génération. Inclure les absences de candidats et matches acceptés, sans confondre absence, ambiguïté, tarif incalculable et panne. Index consultable après Production par station/adresse/identifiant ; historique durable lié au snapshot réellement servi, non limité aux logs ou artefacts expirants, sans secrets et sans alourdir les tuiles publiques. Recette obligatoire G5/G8/G9 avec restitution du motif réel y compris après renouvellement.

**État : décision documentaire uniquement, implémentation et tests NOT TESTED.** Aucun run fournisseur ou CI lancé, aucune modification de prix, données, constructeur, Production ou main. Dernière validation réelle inchangée : run 45278131994, 38/38 tests, 81 700 offres ; artefact 14867028669. G5 global PARTIAL. Prochaine opération : implémenter les comparaisons techniques réelles pour les deux méthodes et le journal de décision exhaustif, avec preuves CPO recevables, puis valider les critères, l'index, le stockage durable et la reproductibilité avant import. Voir docs/v9-rebuild/PROJECT_SPEC_G0_G9.md. Parent distant vérifié : 17871ca83731b73d84b22cbcb05bc43c00cac46d ; aucun run concurrent actif/en file ; état local Codex non vérifiable depuis GitHub.

## 2026-11-23 22:19 UTC — G5 : audit de la hiérarchie et du crosswalk CPO, aucune paire approuvée

Commits e30c80d1 puis c7b96534 sur rebuild/v9-20261020 : fonction diagnostique séparée du constructeur, 7 nouveaux tests de rapprochement, registre de crosswalk CPO indépendant vide, audit CI de toutes les offres. Aucun code de tarif modifié.

Validation GitHub : run https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45278131994 ; job 138055161888 ; SHA exécuté c7b965349ddf6d6eeece807c3082c9cd3cf75b08 ; completed/success 2026-11-23T22:19:09Z.

38 tests Node sur 38 PASS, public_safety_check PASS, artefacts source tarifs/statuts immuables contrôlés, reconstruction et comparaison A/B PASS, aucun appel fournisseur, aucune publication.

Artefact 14867028669 : sha256:8af82171fd8af09ecba8ecfc951644261fe5e2fc905bb9951c2bdb83aedab7ae ; 4 255 802 octets ; expiration 2026-12-23T22:19:05Z.

81 700 offres en 318 tuiles inchangées ; 93 stations à distance >10 m avec 446 offres techniquement justifiées (411 identifiants source exacts, 35 Powerdot), aucune offre indirecte >10 m sans preuve ; 157 quarantaines GPS et 28 nationales conservées.

Le nouveau diagnostic indépendant recense zéro paire supplierOperatorId Electroverse ↔ CPO national approuvée ; les 81 700 offres restent non certifiées quant à cette équivalence, SANS être déclarées fausses ni exclues à nouveau. Le registre validé est volontairement vide.

Les nouvelles règles testées sur fixtures exigent d'abord identité exacte EVSE et opérateur prouvé ; à défaut seulement adresse ou GPS <=10 m avec opérateur prouvé, unicité station, pays et preuve de la portée par prise/puissance/type. Les tests synthétiques ne constituent pas des preuves fournisseur.

G5 global reste PARTIAL, G4/G6/G8/G9 non validés par cette étape ; aucune modification du constructeur tarifaire, du cache source, de la base nationale, de main, Production, Stable ou Updater Test.

Prochaine action : chercher uniquement dans les sources déjà autorisées une preuve explicite et indépendante reliant un code numérique fournisseur au CPO national ; examiner les 33 codes multi-libellés et 326 offres sans libellé national sans inférence par majorité. Ne pas approuver de paire ou fallback non démontré ; exiger identité/portée par EVSE et revalider hors ligne avant tout import Production.

Concurrence : aucun run actif au préflight ; la situation locale du Mac/Codex CLI n'est pas vérifiable via GitHub. Avant écriture ultérieure, comparer branches, statuts locaux et HEAD distant.

## 2026-11-23 — G5 Electroverse : 136 outliers GPS et opérateurs audités, 157 offres mises en quarantaine, 81 700 restantes

Audit indépendant depuis les artefacts complets Electroverse (tarif 45024846774/14760747281, statut 45214188791/14838028097), sans accès fournisseur. **136 ChargingLocation PK /603 offres à >10 m** dans l'ancien rapprochement `spatial_mutual_nearest_v1` (max 15m) : **411** source EVSE IDs exacts, **35** Powerdot vérifiées contre inventaire national officiel PDC/puissance/type de prise (2025-09-14), **157** autres indirectes non prouvées sur **44 locations**. 169 codes opérateurs source, 33 associés à plusieurs noms nationaux après normalisation ; **aucun crosswalk CPO indépendant prouvé** et aucun code réputé faux sur fréquence seule. 326 offres sans nom opérateur national. [Premières preuves](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45258954840) : 29 Node PASS, 0 fournisseur.

Correctif sur `rebuild/v9-20261020` : librairie d'audit GPS/CPO, contrôles d'identité official Powerdot (PDC+puissance+prise), filtres réversibles en sortie du builder et tests ; aucune mutation du cache source ni de la base nationale, sans prix déplacé. Les 157 offres indirectes à >10m non prouvées sont quarantainées dans `manifest.g5OperatorGpsGate` avec cible et motif, `Tarif incalculable` comme diagnostic futur. [Run de preuve #45259545372](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45259545372), job 137990296195, SHA exécuté `bfe1d696183afe23397a05929957748693600a65`, `completed/success`, **31/31 Node PASS**, sécurité PASS, providerCalls=0, Production inchangée. **81 700 offres en 318 tuiles**, 93 sites >10 m avec 446 offres prouvées techniquement, 0 indirect sans preuve ; 28 quarantaines nationales préexistantes +157 GPS. A/B statut : 84 309 sans filtre panne →81 700 avec, −2 609 offres, **0 déplacement prix/EVSE/portée**. ZIP artefact **14861200044**, sha256 `99720d6fb03e1df6e7ea816a294fce1c8156c7e10233bc74a7ce05279c57b973`, 4 255 411 octets et CRC PASS. Ancien artefact rollback #14857208533. [Audit écrit et limite G5](../docs/v9-rebuild/evidence/electroverse-g5-operator-gps-20261123.md). **G5 demeure PARTIAL** en attendant correspondances indépendantes des CPO source/nationaux et fallback opérateur+adresse/GPS ; aucune importation G4 ni G8/G9.

## 2026-11-23 — G5 Electroverse France : bornes nationales authentifiées et quatre collisions quarantainées, 81 857 offres

**Source** : 22 818 sites tarifaires Electroverse `45024846774/14760747281`, 22 818/22 818 statuts validés `45214188791/14838028097`. Reprise G5 depuis [run #45222315069](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45222315069) / artefact 14841627210, 81 885 offres, sans réinterroger fournisseur ni changer un prix. Vérification indépendante : 24 offres provenant de cinq stations situées en Belgique dans le catalogue FR ; 12 PDC supplémentaires apparemment absents du mapping source original mais déjà prouvés par des dossiers d'extensions GEEVE (8) et Soregies (4) datés 02/10 ; quatre PDC français partagés entre deux ChargingLocation source et donc dangereux sans unicité. Les identifiants `ESZUN`, `DKMONE`, `MEL` peuvent représenter des stations en France : ne pas utiliser de simple filtre sur préfixe pays.

**Travail branch `rebuild/v9-20261020`** : nouveau garde `scripts/lib/electroverse_g5_national_scope.mjs` sur le mapping maître original + les deux extensions station-locked, intégré au constructeur `scripts/build_electroverse_france_evse_overlay.mjs` **après** toutes les jointures prix/prises et les filtres de panne, pas avant ; audit autonome `scripts/audit_electroverse_g5_national_scope.mjs`, tests `tests/electroverse_g5_national_scope.test.mjs` et workflow offline A/B renforcé. Aucune station/EVSE nationale ou brute détruite. Les revendications multiples d'un PDC par plusieurs locations entraînent une quarantaine sur la seule vue France. Erreurs et vérifications : #45251708431 (12 extensions non revalidées indépendamment), #45252505385 (bug regex date d'un test), les deux corrigées puis #45252747385 PASS ; **final #45253373553 completed/success**, job 137968646108, SHA `8d7185cf3e2cf38982a655abb39cf9ad2c0e156c`, 22 tests Node PASS, sécurité publique PASS.

**Preuve immuable** : artifact [#14857208533](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45253373553/artifacts/14857208533), ZIP SHA256 `ae20fb06bb6a9824b41b3664a010b95670adf969369ef943af49e7a88b89afcb`, 4 244 969 octets, 325 membres / CRC PASS. **81 857 offres, 318 tuiles**, 0 cibles hors mapping original + extensions validées, 12 suppléments conservés, 28 quarantaines (24 belges +4 collisions source), 0 offre dupliquée, 0 panne récente encore publiée, 0 changement de prix/EVSE cible/portée par rapport au contrôle sans filtre de panne. **G5 ciblé PASS, G5 global PARTIAL** : preuves indépendantes exact+opérateur, fallback adresse/GPS+opérateur et cas à >10 m (136 locations) non validés. Production, main, Updater Test, préprod, G4, G8/G9 non modifiés. [Rapport](../docs/v9-rebuild/evidence/electroverse-g5-national-scope-20261123.md).

## 2026-11-23 — Electroverse statuts : run résilient #45086131828 achevé à 5h, 14 091 vérifiées

**[Run 45086131828](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45086131828)** (SHA exécuté `d104ec09a0725c053f8aa4b42d0f1c380f830af4`) : GitHub `completed/cancelled` le 23/11 à **04:59:28Z / 05:59 Paris**, EXACTEMENT au plafond de 300 min, `Bounded sweep 11` interrompue avant upload ; **pas une perte de runner ni une rupture 429**. **11/16 partitions (00–10) et 11 artefacts intermédiaires uploadés avec succès**, rattrapage final non entamé, aucune publication. Dernier état durable [artefact 14790727210, sweep-10](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45086131828/artifacts/14790727210), **14091/22818 vérifiées (61,75%, +10107), 393 erreurs différées, 1204 non visitées dans 00–10, 7130 stations des partitions 11–15 non sauvegardées, total 8727 non vérifiées**. Erreurs : 362 `single_paged_unavailable` + 31 `pagination:page_failed:200`. Partitions 06–08 particulièrement incomplètes (568/404/232 non visités). Les **3984 succès parent intacts** (comparaison JSON PK/valeurs, 0 perte, 0 modification), timestamps inchangés.

**Dernier artefact ZIP** 316179 octets, SHA256 `13df5d3920803d3f56e8cbc71cd5068f3a6709b84f54e8d2f2c77c78e9c17b5e`, ZIP CRC et SHA/tailles de 15 fichiers d'inventaire PASS, delta digest `3d1f06aca2a1eedbce4734a026635373ff4ae08ce3271528bac13187c7713f3a`, fileset CANONIQUE déclaré `28fb15b237f7868a294703ef27cdd0ee7f83303879e28cf83a8ba55133ef43b7`, sourceFingerprint `3365025ffc1f0f57ac4b48101e4e78517797a8cbb5a8b2a72fea60bce1cd12b4`, `partial_checkpoint` sans état national complet. Artefact delta rétention **7 jours**, prévoir reprise avant expiration. **429 par PK validé live** : part-10 1080s de pauses cumulées mais max180s pour une station ; ~7560s cumulées (126min) sur les partitions, n'a pas déclenché de stop global.

**Bloquant de fraîcheur** : première part-00 `startedAt=2026-11-22T16:46:58.837Z`. Expire **23/11 08:46:58Z (09:46:58 Paris)** et seuil de reprise avec marge de 10min **08:36:58Z (09:36:58 Paris)** ; les 14k vérifiées restent preuve historique mais ne peuvent pas devenir un snapshot national frais au-delà de cette fenêtre. **Ne pas relancer les cinq partitions en aveugle, ni rajeunir les anciens statuts**. Prochaine phase : utiliser `checkpointKind=segmented_delta` sur dernier artefact pour archivage/reconstitution contrôlée, puis définir un nouveau cycle de collecte frais, adapté aux plafonds d'exécution de GitHub, au traitement des 393 erreurs et des 1204 non visitées, aux règles anti-rejeu et aux 480s/PK. Aucune nouvelle collecte ou modification code déclenchée par cet audit. [Preuves détaillées](../docs/v9-rebuild/evidence/electroverse-status-stage3-20261122.md).

## 2026-11-23 — Première sauvegarde live réussie du workflow résilient Electroverse

[Run #45086131828](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45086131828), SHA fournisseur `d104ec09a0725c053f8aa4b42d0f1c380f830af4`, job 137405075413 : préflight, restauration du parent et **balayage de la partition 00 + téléversement du delta intermédiaire réussis**, puis partition 01 lancée. **Artefact vérifié [#14778693321](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45086131828/artifacts/14778693321)**, `tcc-v9-electroverse-status-stage-sweep-00`, **94 717 octets**, ZIP SHA256 `fa2e4314aa73d5c658a8f03f797fa479d36d5ee516aab5e5b886c12ab34193e1`, digest status delta `703e08c6526984a6c325ed7833195e8e22adcebf63b0419ef1214a6187d72696`, fileset complet reconstructible `a65b7e4dc492e6065dc2e112cf860abda796b7dd15c8a02bd91e7b80d5084bd2`. ZIP CRC, 7 fichiers inventoriés et empreintes individuels PASS ; **3984 succès, 31 erreurs en attente, 3 partitions entamées** conservés, sourceFingerprint `3365025ffc1f0f57ac4b48101e4e78517797a8cbb5a8b2a72fea60bce1cd12b4`. Aucune publication ni promotion nationale. **Point capital : un checkpoint est maintenant téléchargeable alors que le run continue ; la perte future du runner ne détruirait pas cet état**. Ne pas inférer complétude ou succès des autres partitions ; prochains audits en lecture seule, sans relance parallèle. [Rapport technique](../docs/v9-rebuild/evidence/electroverse-status-stage3-20261122.md).

## 2026-11-23 — Electroverse status : checkpoints par unité, reconstructibles après perte du runner ; live #45086131828

Suite à la déconnexion du runner sur #45066431395, orchestration Data Lab `rebuild/v9-20261020` rendue **résiliente** : 16 unités de balayage puis 16 unités de rattrapage, avec **upload GitHub d'un delta de statuts vérifié après chaque unité** ; SHA-256 de chaque fichier, fingerprint tarifaire, manifeste de filiation, archive complète reconstituable depuis le parent tarif immutable, y compris si le run créateur échoue APRÈS un upload. Aucun fichier de tarifs recopié dans les 32 sauvegardes allégées ; arrêt sur 429 par ChargingLocation PK (480s/station, 60/120/300s puis stop 4e), garde fraîcheur 16h, 300min de job, aucune publication automatique.

**Code/travaux :** script `scripts/resilient_v9_electroverse_status.py` (a10bc94, 14b17eb, ff00e7c, b1b601c), workflow `.github/workflows/v9-electroverse-status-rebuild.yml` (b6bc0bb, 16e695b, 536309b), tests `tests/test_v9_electroverse_status_resilient.py` (45bd7a6, d11a0ba, 4bb6c02). Préflight initial [#45085409243](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45085409243) PASS 35 Python/25 Node. Premier test delta [#45085818313](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45085818313) FAIL 5 erreurs d'export (chemin source), puis correctif `ff00e7c`. **Préflight final [#45085965304](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45085965304) PASS 37 Python +25 Node + scan sécurité et SHA source, supplierCalls=0**, checkpoint parent éligible au contrôle.

**Relance live unique autorisée :** commit demande `d104ec09a0725c053f8aa4b42d0f1c380f830af4`, [run #45086131828](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45086131828) lancé le 23/11/2026 à 00h59 Paris, initialement en cours, sans résultat d'acquisition confirmé. Repart du seul checkpoint durable **45058177243 / artifact 14770651817**, 3 984 bons +31 erreurs/3 partitions, ZIP SHA `4cf93712be20773313666c8c27a0a2fa80f6f612074f264de856c36d6e9551fd`, fileset `49b4c47764fc5147673c1139ba4efdf898600ac12b489f1658e26daa5336ea0c`. Aucune promotion de statuts ou publication Production. **Prochain contrôle** : surveiller premier artefact `tcc-v9-electroverse-status-stage-sweep-XX`, contrôler son ZIP, delta-manifest, couverture et éventuels 429 ; ne pas relancer en concurrence. [Rapport probatoire complet](../docs/v9-rebuild/evidence/electroverse-status-stage3-20261122.md).

## 2026-11-23 — Electroverse : run live 45066431395 FAILED (runner perdu, aucun artefact)

[Run #45066431395](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45066431395) / [job #137343510842](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45066431395/job/137343510842), SHA exécuté `e34e2723d02e632b01bd1232ccce25f083f96568`, 22/11 20:26:26–21:40:27 UTC : GitHub `completed/failure`. Les tests offline, contrôles des deux artefacts parents et téléchargement du checkpoint sont PASS. L'étape de collecte a été interrompue sans code de sortie. **Annotation exacte GitHub : `The hosted runner lost communication with the server`** ; cause ultime CPU/mémoire/réseau/hébergement non établie, ne pas attribuer la panne aux 429. Logs job indisponibles (`404 BlobNotFound`), **0 nouvel artefact** ; impossible de connaître les PK/partitions collectés localement avant l'arrêt. Pas de publication. Dernier checkpoint **durable** = run 45058177243 / artefact 14770651817, **3 984 vérifiées, 31 erreurs, 3 partitions**, ZIP SHA `4cf93712be20773313666c8c27a0a2fa80f6f612074f264de856c36d6e9551fd`, fileset `49b4c47764fc5147673c1139ba4efdf898600ac12b489f1658e26daa5336ea0c`. **Suivant recommandé :** rendre la persistance des checkpoints indépendante du succès d'un long step, avec uploads après unités bornées avant tout nouveau run live ; respecter la fraîcheur et la règle 429 par ChargingLocation PK. Ne pas relancer en aveugle. [Evidence](../docs/v9-rebuild/evidence/electroverse-status-stage3-20261122.md).
## 2026-11-22 — Electroverse statuts : reprise réelle autorisée / run 45066431395 lancé

Vérifié avant lancement (20:25–20:26 UTC) : aucune collecte concurrente, branche `rebuild/v9-20261020` identique au SHA documentaire `29b68e54f1d681d0db8fda6ee7ce0f936ad3dd8f`, préflight offline [45065751191](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45065751191) PASS (**31 Python + 25 Node + scan sécurité, supplierCalls=0**), checkpoint 45058177243 / artifact **14770651817** (**3984 succès, 31 erreurs, 3 partitions**) valide, ZIP SHA `4cf93712be20773313666c8c27a0a2fa80f6f612074f264de856c36d6e9551fd`, fileset `49b4c47764fc5147673c1139ba4efdf898600ac12b489f1658e26daa5336ea0c`. Fenêtre de fraîcheur active (part-00 depuis 22/11 16:46:58Z), cooldown 429 `resumeNotBeforeUtc=20:10:34Z` dépassé au lancement, sans garantie de quota renouvelé.

**Demande live** `e34e2723d02e632b01bd1232ccce25f083f96568` : mode=collect + autorisation utilisateur explicite, budget 480 secondes **PAR chargingLocation PK**, pauses consécutives 60/120/300 puis arrêt au 4e 429, 16 partitions puis rattrapage différé, 18000 sec de runner, automaticPublication=false. **[Run GitHub #45066431395](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45066431395)** créé le 22/11 à 20:26:23 UTC, en cours de préparation au premier contrôle. Aucun résultat fournisseur encore vérifié ni publication. [Rapport détaillé](../docs/v9-rebuild/evidence/electroverse-status-stage3-20261122.md). Prochain audit lecture seule en fin de run ; ne pas lancer de deuxième collecte concurrente.

## 2026-11-22 — Per-station HTTP 429 budget final validation

Verified final offline [run 45065751191](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45065751191), SHA f95da82eee6d672c36834a54ba0ce5aa43b64d1a; 31 Python, 25 Node and public-safety PASS, supplierCalls=0, checkpoint 3984 statuses/31 errors verified. 480s wait cap now per ChargingLocation PK with same-run sweep/recovery continuity, not partition-wide or run-wide; initial 60/120/300 and fourth-429 stop preserved. No provider run or publication started. [Evidence](../docs/v9-rebuild/evidence/electroverse-status-stage3-20261122.md).

## 2026-11-22 — Electroverse: plafonnement 429 corrigé PAR STATION, pas par partition/run

**Décision utilisateur:** la limite cumulée d'attente 429 de 480 secondes s'applique à chaque station Electroverse (ChargingLocation PK) et non au cumul des partitions ou du run. Chaque requête batch impute la pause aux PK concernés ; pages et fallback individuel consomment le même budget de la station. Pauses sur 429 consécutifs: 60s, 120s, 300s, puis stop sur quatrième 429; les autres stations ne sont pas pénalisées par la consommation de la première. Total des pauses physiques d'un run permis >480s si PK distincts; limite du runner et fenêtre de fraîcheur 16h inchangées. Aucun prix, overlay IRVE ou Production ne dépend des statuts live.

**Implémentation branchée et versionnée:** helper station 429 524042e + 4df07d6 + 4781376, collecteur 95efd01 + 82e5e52, pilote f65c60b + bba464d, workflow 8f188df et tests fbc2b68/f0d882e/6dad9ff/c166837. Important: les compteurs restent entre balayage et rattrapage du MÊME run via fichier de partition, mais sont réinitialisés au début d'un NOUVEAU run dans la copie de travail, sans modifier l'artefact source. Cahier des charges G0-G9 mis à jour au commit 0f0f577.

**QA en lecture seule:** [offline run 45065357594](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45065357594), completed/success, 30 Python + 23 Node + contrôle public PASS, archive 14770651817 et tarif parent vérifiés; supplierCalls=0. Second [offline run 45065751191](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45065751191) lancé au commit f95da82eee6d672c36834a54ba0ce5aa43b64d1a afin de vérifier les ajouts de persistance ; conclusion à contrôler avant revendication PASS. Demande status actuellement mode=verify, explicitProviderAuthorization=false, aucune collecte fournisseur ni publication autorisée. Checkpoint source 45058177243/14770651817, 3984 réussites, 31 erreurs, 3 partitions, ZIP SHA 4cf93712be20773313666c8c27a0a2fa80f6f612074f264de856c36d6e9551fd, fileset 49b4c47764fc5147673c1139ba4efdf898600ac12b489f1658e26daa5336ea0c.

**Prochaine opération:** inspecter le résultat du second preflight, ne pas lancer de run de collecte sans accord explicite. [Rapport source](../docs/v9-rebuild/evidence/electroverse-status-stage3-20261122.md).
## 2026-11-22 — Electroverse : 16-part sweep run #45058177243 audité, 3 984 statuts, arrêt 429 borné

[Run GitHub #45058177243](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45058177243), job 137317994778, SHA fournisseur \`7f1696d3566517db992101e235396e0c3217f36d\` : GitHub \`completed/success\` mais **\`checkpointed\` / \`provider_rate_limited\`**, aucune promotion. Le balayage a **franchi les 4 erreurs de partition 00** comme demandé, parcouru 00–02 avant le nouveau 429 : part-00 1423/1427, 4 erreurs ; part-01 1404/1427, 23 erreurs ; part-02 1157/1426, 4 erreurs + 265 PK non visités. **3 984/22 818 vérifiées (+2 561), 18 834 restantes nationalement ; 31 échecs individuels en file et 296 restants sur trois partitions**, 13 partitions non visitées. Rattrapage final non lancé puisqu'il exige le balayage 16/16. **429 : 360 s d'attente part-01, 120 s part-02 = cap de 480 s** ; dernier 429 en status_page le 22/11 19:55:34.691Z, stopReason=run_wait_budget_exhausted, cooldown indicatif (sans garantie fournisseur) au plus tôt 20:10:34.691Z (21:10:34 Paris). Deux pauses de 60 s ont réellement permis des reprises sur part-02 ; séquence 2/5 min testée hors réseau, non prouvée live.

**Nouvel artefact CHECKPOINT** [#14770651817](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45058177243/artifacts/14770651817), ZIP SHA256 \`4cf93712be20773313666c8c27a0a2fa80f6f612074f264de856c36d6e9551fd\`, fileset SHA \`49b4c47764fc5147673c1139ba4efdf898600ac12b489f1658e26daa5336ea0c\`. Vérification locale : 141/141 fichiers avec SHA et tailles concordants, CRC ZIP PASS, cacheFingerprint \`3365025ffc1f0f57ac4b48101e4e78517797a8cbb5a8b2a72fea60bce1cd12b4\`, 1423/1423 PK précédents identiques, ni perte ni écrasement, horodatage ancien inchangé, file différée concordante, aucun ledger complet. Tests du run 29 Python +20 Node + sécurité publique PASS. **Pas de nouvelle collecte déclenchée par audit** ; priorité maintenant à la stratégie de plusieurs runs sous plafond 8 min et fenêtre de fraîcheur 16h, sans bloquer développement des tarifs. [Rapport détaillé](../docs/v9-rebuild/evidence/electroverse-status-stage3-20261122.md).

## 2026-11-22 — Electroverse statuses: 16-partition sweep + final deferred retry LAUNCHED

User approved skipping individual errors during the first pass of 16 status partitions, collecting all residual PK in one bounded final recovery. Live availability remains NONBLOCKING for TCC V9 tariffs and Production. Source tariff parent: run 45024846774 / artifact 14760747281 (22,818 locations); current immutable status source: run 45053244431 / artifact 14766791724 (1,423 verified, 4 errors; ZIP SHA ccffa65c09b54afed7e5792911d60a65fdd08ea8af1418414b0c9c46ec2169b4, fileset 5d2c7008c3ebd9d405245279e1dbe09b36dc48b95f5f1a4c756572b735685f42). Changes on rebuild/v9-20261020: collector 94d8682, pilot ad1764e, Python tests cda4a625, Node test b3eede98 plus safety fix 466f6bc, workflow gate 1975a9c. **Offline preflight [45057927160](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45057927160) PASS:** 29 Python + 20 Node + public_safety_check, immutable checkpoint/fingerprint valid, supplierCalls=0, resumeEligible=true. **Explicit authorized live request commit 7f1696d3566517db992101e235396e0c3217f36d** triggered [run 45058177243](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45058177243), initial state in_progress, outcome not yet verified. 429 safety policy remains 60/120/300s then stop at fourth, cumulative 480s. No automatic publication, overlay, price collection or Production changes. **Next:** audit the new run, checkpoint and deferred PK, no concurrent relaunch. [Detailed evidence](../docs/v9-rebuild/evidence/electroverse-status-stage3-20261122.md).

## 2026-11-22 — Run Electroverse 45053244431 audité : 1 423 / 22 818, zéro 429, arrêt sur 4 erreurs isolées

[Run GitHub #45053244431](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45053244431) / job 137302782723 / SHA exécuté `2a06438896ce55af5acd709509400e4c883e534a` : `completed/success` GitHub **mais `checkpointed`** (`partition_incomplete_or_stale`, précisément 4 erreurs restantes dans part-00). **1 423 résultats sur part-00 / 1 427 attendus, soit +444** depuis les 979 précédents ; **4 erreurs non-429** : `4220774` (`pagination:page_failed:200`), `4339948`, `4466910`, `4609637` (single_paged_unavailable). Les 2 erreurs de l'artefact précédent sont résolues. 0/16 partitions complètes ; national 1 423/22 818, restant 21 395. **0 nouveau HTTP/GraphQL 429, aucune pause ni retry 1/2/5 min consommé**, totalWaitSeconds=0 ; la politique est validée par tests offline (25 Python + 19 Node PASS), mais **pas encore éprouvée sur un 429 réel**.

**Nouvel artefact audité :** [#14766791724](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45053244431/artifacts/14766791724), ZIP SHA256 `ccffa65c09b54afed7e5792911d60a65fdd08ea8af1418414b0c9c46ec2169b4` ; fileset `5d2c7008c3ebd9d405245279e1dbe09b36dc48b95f5f1a4c756572b735685f42`. 138/138 fichiers SHA et bytes valides, ZIP CRC PASS, 979 anciens succès intacts, +444 nouveaux ; sourceFingerprint `3365025ffc1f0f57ac4b48101e4e78517797a8cbb5a8b2a72fea60bce1cd12b4`, prix/source nationale inchangés. Seuls la partition, son rapport et les deux manifestes de packaging évoluent ; pas de promotion.

**Prochaine priorité :** ne pas laisser **4 erreurs de disponibilité** bloquer les 15 autres partitions. Préparer hors fournisseur un correctif qui poursuit les partitions et conserve les quatre échecs en file de rattrapage, tout en gardant la validation complète/fraîche strictement bloquée tant que les statuts manquent ; traiter séparément `page_failed:200`. Les données tarifaires et jointures V9 peuvent avancer indépendamment. Aucun nouveau run déclenché pendant l'audit. [Rapport complet](../docs/v9-rebuild/evidence/electroverse-status-stage2-20261122.md).

## 2026-11-22 — Electroverse statuts : politique 429 1/2/5 minutes implantée, run lancé

**Décision utilisateur :** retenter la même requête de statut après 60 s, 120 s puis 300 s pour 3 HTTP/GraphQL 429 consécutifs ; au quatrième, arrêter avec checkpoint, **maximum 480 s d'attente 429 sur tout le run**, Retry-After supérieur respecté ou arrêt prudent sans requête anticipée. Statuts live toujours non bloquants pour tarifs, G3–G8 et Production. **Code Data Lab reconstruction** : module ca0eac3, tests 0ce2a57, raccordement dd444d1, workflow a9dbd39, pilot multi-partitions d204fec, diagnostic fcf28af. **Préflight offline** [45052996884](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45052996884) 25 Python + 19 Node PASS, supplierCalls=0, checkpoint 979 validé ; ajustements ultérieurs du pilote à revalider sur run live. **Demande fournisseur** 2a06438896ce55af5acd709509400e4c883e534a, checkpoint 45049654722 / 14765227405 (979 entrées, 2 erreurs, digest e36719c21b03551539f8a2fbc352dfd66ce7821b0fb4677b2feb213e54e47075). **[Run live 45053244431](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45053244431)**, créé 18:07:16 UTC, initialement queued ; conclusion fournisseur NON ENCORE VÉRIFIÉE. Aucun main, Production, Stable, Updater Test, tarif ou déploiement changé. Prochaine opération : auditer le run et les artefacts sans relance. [Preuve complète](../docs/v9-rebuild/evidence/electroverse-status-stage2-20261122.md).

## 2026-11-22 — Electroverse : run statuts 45049654722 terminé, checkpoint 979 / live non bloquant

**Preuve :** [run #45049654722](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45049654722), job 137291747535, SHA c5d76615e2033a876006759fd2df6d1f11aa11f2, `completed/success` du job **mais collecte partielle** `checkpointed/provider_rate_limited` après un nouveau 429 `status_single` à 2026-11-22T17:36:27.171Z (18:36 Paris), refroidissement 900 s au plus tôt 17:51:27Z (18:51 Paris), non preuve de rétablissement du quota. Tests Python 25/25, Node 8/8, sécurité publique et origines/ZIP PASS. Artefact checkpoint [#14765227405](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45049654722/artifacts/14765227405), ZIP SHA-256 e36719c21b03551539f8a2fbc352dfd66ce7821b0fb4677b2feb213e54e47075, fileset fcc91b40e3aa376983225b24b232b36e6a97c410c56a63bf90d2bd37f158c478, 138 fichiers tous validés ; fingerprint et parent tarifaire inchangés. **979/22 818 vérifiées**, soit +312 depuis 667 ; première partition 979/1 427, 448 restantes, **0/16 partitions complètes** ; 2 nouveaux échecs conservés (PK 1915379 et 1992388). Comparaison byte/data : les 667 précédents conservés à l'identique, les cinq erreurs précédentes converties en succès ; seuls part-00 et son rapport ont changé. Pas de ledger national, pas de promotion ni de déploiement.

**Priorité utilisateur maintenue :** la disponibilité live n'est pas un frein. Ne pas multiplier les runs statuts ; **prochaine opération** : fiabiliser la mise à jour des tarifs Electroverse et l'overlay tarifaire IRVE, indépendamment de 16 partitions live, sans inventer d'information de disponibilité. Document technique complet [rapport étape 2](../docs/v9-rebuild/evidence/electroverse-status-stage2-20261122.md). Conserver le run et l'artefact comme preuves ; aucune nouvelle collecte déclenchée par cet audit.

## 2026-11-22 — Décision utilisateur : la disponibilité live Electroverse ne bloque plus le développement

**Nouvelle priorité normative :** fiabiliser d'abord la mise à jour technique Electroverse (tarifs/cache, incrémental, reprise, erreurs 429, checkpoints, SHA, provenance, import et actualisation). Les 16 partitions de disponibilité **AVAILABLE/CHARGING** sont un enrichissement facultatif ultérieur : leur absence, leur fraîcheur ou leurs échecs ne doivent pas empêcher G3–G8, les jointures **tarifaires** IRVE/Electroverse, la carte, l'affichage des prix, les tests ni la préproduction. Le référentiel national « en service » reste distinct de la disponibilité instantanée : aucune disponibilité inventée, périmée rendue actuelle, ni borne nationale/tarif valide effacé faute de statut live. Afficher « Disponibilité non disponible » le cas échéant. Les validations fonctionnelles et techniques des autres composants demeurent requises ; ne pas revendiquer G2–G9 PASS sans leurs preuves.

**Source de vérité :** [cahier des charges G0–G9 — décision du 22/11](../docs/v9-rebuild/PROJECT_SPEC_G0_G9.md), paragraphe « disponibilité live non bloquante ». Cette décision remplace les formulations historiques présentant le ledger national live des 16 partitions comme blocage préalable de l'overlay **tarifaire** ; seul un futur enrichissement live requiert ce ledger. **Run statuts existant** [45049654722](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45049654722), job 137291747535, encore in_progress au contrôle de décision : pas d'annulation ou relance, pas de publication. Prochaine opération : auditer le résultat sans laisser cette source conditionner l'avancement des autres travaux, puis poursuivre en priorité l'intégrité et le renouvellement tarifaire. Pas de code, de workflow, ni de demande de collecte modifiés par cette décision.

## 2026-11-22 — Electroverse France : reprise live autorisée depuis checkpoint après contrôle de fraîcheur

SHA de demande `c5d76615e2033a876006759fd2df6d1f11aa11f2`, branche Data Lab `rebuild/v9-20261020`. Réutilisation épinglée du checkpoint `14763184200` depuis run 45045530435, ZIP `1439fbde2f8670bf45eef872dda1fba10f9c253dce1001e0c4622b1a694b748d` ; 667 résultats, 5 erreurs, parent tarifaire complet inchangé. HTTP 429 précédent refroidi, période de fraîcheur historique respectée. [Run #45049654722](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45049654722) en cours au constat initial, job 137291747535 ; nouvelle progression non démontrée. Aucun changement de prix, jointure, public ou Production. Pas de publication ni réexécution concurrente ; audit du nouveau run requis. Détails : [rapport de statuts](../docs/v9-rebuild/evidence/electroverse-status-stage2-20261122.md).

## 22 novembre 2026 — Electroverse FR : reprise du checkpoint 429 validée sans fournisseur

**Fait nouveau vérifié :** run statuts [45045530435](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45045530435) completed/success **mais checkpointed** après un HTTP 429 réel le 22/11 à 16:58:07 UTC ; 667/22 818 localisations vérifiées, 5 erreurs conservées, partition 00 incomplète. Artefact 14763184200, ZIP SHA-256 1439fbde2f8670bf45eef872dda1fba10f9c253dce1001e0c4622b1a694b748d, fileset 86d5253d27e34b29e38fc985851aa06417f1375a25f0fcb235d74158cd277925, parent tarifaire 14760747281 inchangé. Pas de status national ni d'overlay.

**Étapes 1–2 autorisées : PASS** sur branche rebuild/v9-20261020. Correctif pilote 41bb1aa (checkpoint immuable, anti-rejeu, cooldown et fraîcheur), tests f15bcf6, workflow 3b55b7a + f104d98, demande OFFLINE cef33ce1. [Run de vérification 45048950087](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45048950087) job 137289595777 **completed/success** : 25 tests Python + 8 Node + sécurité publique PASS ; origine GitHub, ZIP/digests et 138 fichiers du checkpoint contrôlés ; réponse pilote checkpointValidated=true, resumeEligible=true, supplierCalls=0 ; aucun nouvel artefact de statuts ni aucune requête fournisseur. Le checkpoint est éligible **au moment du test seulement** : partition démarrée 16:46:58 UTC, fraîcheur 16 h, garde de 10 min imposant reprise avant environ 23/11 08:36:58 UTC (09:36:58 Paris) ; au-delà, ne pas prétendre conserver les anciens statuts frais.

**Décision et prochaine opération :** conserver request en mode verify / explicitProviderAuthorization=false. L'étape 3 overlay reste interdite avant statuts nationaux complets. Le futur mode collect exige nouvel accord utilisateur, contrôle de non-concurrence, exactitude du parent, respect de fraîcheur et audit de l'artefact résultant ; jamais de relance automatique. Data Lab main, Production, Stable, Updater Test et site public non modifiés. **Rapport de preuve** : [electroverse-status-stage2-20261122.md](../docs/v9-rebuild/evidence/electroverse-status-stage2-20261122.md).

## 2026-11-22 — Étape 2 Electroverse FR : statuts 16 partitions lancés depuis le cache complet

**Source de vérité détaillée :** [docs/v9-rebuild/evidence/electroverse-status-stage2-20261122.md](../docs/v9-rebuild/evidence/electroverse-status-stage2-20261122.md). Nouvelle demande expresse utilisateur de lancer l'**étape 2**, après le run tarifaire complet [`45024846774`](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45024846774) / artefact `14760747281`, ZIP SHA256 `0d3abcc15dc4762b360c5816b6e783accdcafa664442c8ce99b7c0500743a5fe`, fileset `c06886fec4b9117e920d7ee50af66d5fb0ebfa00944c452012d771a033a9b965`, **22 818 localisations**. Collecteur de statuts historique 16 partitions, rythme 800 ms, deux alias par requête et contrôles de fraîcheur conservés. Patch coupe-circuit status sur premier HTTP/GraphQL 429 `f2fcc76279060f462535fa8e7ee5b19004ec8466` ; pilote source épinglée et checkpoint `3cb4c1f0655b81afc33fa624fb38a8332c2ad3c8` ; workflow de branche en lecture seule `3df5c2e3df8cd76c0ca180c12a2641b2b2b45352`, correctif `408586139ea476effd4a593a9c4b9e171a8ce355` (PYTHONPATH). Premier préflight `45045047597` : tests et ZIP PASS, échec de chemin Python avant fournisseur ; **préflight corrigé** [`45045314084`](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45045314084), code `d87791e210d2991700bc39443e8a38f439779bfc`, `completed/success`, 20 Python+8 Node+public safety, parent complet vérifié, `supplierCalls=0`. **Run statuts réellement déclenché** [`45045530435`](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45045530435), SHA demande `b2f3ff554f1f297421c00425232a7d38c3510433`, job `137279198848`, démarré `2026-11-22T16:44:42Z`; à la passation son résultat/avancement fournisseur est **INCONNU**. Durée job bornée 330 min et budget pilote 18 000s avec réserve ; checkpoints de statuts séparés de la finalisation nationale, zéro relance automatique et zéro promotion. **Prochaine opération** : suivre run `45045530435`, examiner logs/artefacts `-status-complete` / `-status-checkpoint` / `-status-failure`, intégrité ZIP SHA, 16 partitions fraîches et `sourceFingerprint` parent, 22 818 PK, ledger et erreurs, éventuel 429 et délai. Ne pas démarrer overlay étape 3 sans preuve d'un statut national complet. Data Lab `main`, Production, Stable et Updater Test inchangés ; ne pas relancer ni modifier les prix/jointures. 

## 2026-11-22 — Electroverse France V9 : collecte 22 818/22 818 terminée, audit indépendant PASS

**Référence complète** : [rapport Electroverse 22/11/2026](../docs/v9-rebuild/evidence/electroverse-throttle-guard-20261122.md), section « Résultat final : 22 818 / 22 818, run 45024846774 ». Run [`45024846774`](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45024846774) au SHA `67ba3287bfceeaf463c43ddc15ed4658e212cc8c` : `completed/success`, 2026-11-22 12:56–15:30 UTC, 17 tests Python + 8 Node + safety OK, traitement `{"status":"complete","chunks":4}` ; **aucun HTTP 429 réel**, aucun nouvel échec, aucun retry ni artefact de panne. Artefact **complet** [`14760747281`](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45024846774/artifacts/14760747281), ZIP SHA256 `0d3abcc15dc4762b360c5816b6e783accdcafa664442c8ce99b7c0500743a5fe`, `artifact_set_sha256=c06886fec4b9117e920d7ee50af66d5fb0ebfa00944c452012d771a033a9b965`, **136/136 fichiers** sous `objects/FR_electroverse_full/<digest>/`, **128/128 shards** et 22 818 PK intactes, `manifest.status=complete`, source `status=ok`, absence de curseur incomplet. Audit indépendant ZIP avec parent `14754262864` (SHA ZIP `d8782e866628a23cffebb5bcfaa00ffb19541e1893edc934a7d21b8bdd3fa6ca`) : mapping national IRVE et inventaire byte-identiques, **5 024 PK supplémentaires exactement contrôlées et 17 794 autres inchangées** selon `checkedAt` ; aucun shard/record hors sélection modifié ; `tariffHash` 3 112 modifiés / 1 912 inchangés. Attention au sélecteur : les 206 pending du lot [12000,18000] et les 4818 dernières PK proviennent du **tri lexicographique** du mapping et ne se recoupent pas. Nouveau `rateLimit=null`, échecs `[]`, journal de diagnostics inchangé (ancien 429 de `44968499274` seulement). **Couverture réelle fournisseur :** 22 001 localisations avec EVSE, 22 000 avec connecteur et `priceComponents` renseignés ; 817 sans EVSE et 1 avec EVSE sans connecteur ; 93 510 EVSE et 113 372 connecteurs. Le 100 % concerne les contrôles des localisations, **pas l'exhaustivité des tarifs valides par EVSE/PDC** : auditer les 818 manques, les restrictions et la jointure à la seule base maîtresse nationale IRVE avant une quelconque promotion. **GO acquisition source complète ; NO-GO publication automatique**. Data Lab main, Production, Stable et Updater Test inchangés. Aucun nouveau run de collecte.

## 2026-11-22 — Electroverse France : run complet autorisé et lancé (en cours)

**Source de vérité** : [docs/v9-rebuild/evidence/electroverse-throttle-guard-20261122.md](../docs/v9-rebuild/evidence/electroverse-throttle-guard-20261122.md), section « Tentative de finalisation complète ». **Autorisation utilisateur explicite :** tenter les **5 024 PK restant sur 22 818** depuis le dernier artefact `14754262864` (run `45019468889`, ZIP SHA `d8782e866628a23cffebb5bcfaa00ffb19541e1893edc934a7d21b8bdd3fa6ca`, fileset `b7bbb7fccd051dfbf3bced1c8a1624b87f4c007afd7f7c457707546a7ccd0e56`, **17 794 déjà validées**), finir à 100 % ou au **premier HTTP 429**, sans retry, même débit (batch 5, concurrence 1, pause 3000 ms), sans promotion. Adaptations branche `rebuild/v9-20261020` uniquement : `756332f7e5dd13503d7292935e8747ebb3c1e491` (orchestrateur : une seule invocation traverse les deux derniers chunks avec garde forte), `1324d04e6d98067a3aad612683af995937e6884f` et `11a5d14947de8b1eda7bda2c3b833c008c048dae` (pilotage et rétention du curseur inter-chunk, pas de retry), `bc46bab70098cf6136ffc1eabf767f2671b6c380` (3 tests de plus), `cf5c6ec34cfb129e21ffcd627e2ca19344a74697` (workflow : budget fournisseur 16 200 s, subprocess 17 100 s, job 330 min, parent explicitement épinglé). **Vérification offline** [`45024653710`](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45024653710) SUCCESS : 17 Python + 8 Node + public safety + filiation/pinned parent, fournisseur skipped. **Collecte déclenchée** [run `45024846774`](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45024846774), SHA requête `67ba3287bfceeaf463c43ddc15ed4658e212cc8c`, résultat **INCONNU** à cette passation. Si `complete` : auditer `tcc-v9-electroverse-complete` sans publier ; si 429/échec : auditer `-failure` + `-failure-diagnostics`, reprendre seulement après décision, préserver les succès ; si budget atteint : `-window` partiel. Audit 128 shards, mapping France, checkedAt, SHA, rateLimit/cooldown avant toute suite. **Aucune répétition automatique, ni Data Lab main/Production/Stable/Updater Test.** 

## 2026-11-22 — Audit final Electroverse 30 min : aucun nouveau 429, 17 794/22 818

**Résultat et preuve:** [docs/v9-rebuild/evidence/electroverse-throttle-guard-20261122.md](../docs/v9-rebuild/evidence/electroverse-throttle-guard-20261122.md). Test voulu pour observer un vrai HTTP 429 sans hausse de débit. Workflow de budget `1800 s` ajouté par commit `174dfa36b721266675756109e80c79d58830b863`; vérification sans fournisseur [run `45019291398`](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45019291398) success (14 Python, 8 Node, safety et checkpoint strict OK). Collecte unique [run `45019468889`](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45019468889), SHA `b32261dedd45fac950cb5fbf4e00e32ac65002e5`, `completed/success`, `checkpointed` sur limite de fenêtre, ~32 min 37 s d'activité fournisseur du fait des sous-lots. Nouvel artefact [`14754262864`](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45019468889/artifacts/14754262864) ZIP SHA-256 `d8782e866628a23cffebb5bcfaa00ffb19541e1893edc934a7d21b8bdd3fa6ca`, file-set SHA `b7bbb7fccd051dfbf3bced1c8a1624b87f4c007afd7f7c457707546a7ccd0e56`, 137/137 fichiers et 128 shards vérifiés. Parent exact `14751573628` ZIP SHA `0ed8c16ca2ce57cec16cc201f4bb41748ca3620e5eee81b7e4e3b9d807bcccf3`. Diff parent/enfant exhaustive : mapping et inventaire national byte-identiques, pending troisième lot `1306→206`, **+1100 identifiants contrôlés**, 1100 checkedAt strictement croissants, hash tarifaires **446 changés / 654 inchangés**, aucune mutation hors sélection ; **17 794/22 818 = 77,98 %, 5 024 restantes**. `hybrid-refresh-failures=[]`, `lastIncrementalRefresh.rateLimit=null`, seule trace de 429 **ancienne** au run `44968499274` : **AUCUN nouveau HTTP 429**. L'arrêt au 429 réel n'est donc toujours pas démontré par cette expérience (les tests synthétiques existent). `manifest.status=partial_failure` uniquement pour `collector_window_budget`, `completeSnapshotValidated=false` : **ne jamais promouvoir en Production**. Conseil : 30 min est la plus longue durée réussie à cadence inchangée, candidate d'exploitation sous supervision mais ni seuil API établi ni quota glissant connu ; ne pas enchaîner automatiquement et valider bout-en-bout un 429 par injection contrôlée hors fournisseur. Aucune relance fournisseur autorisée par cet audit. 

## 2026-11-22 — Electroverse V9 : essai fournisseur 30 minutes sur HTTP 429

**Source de vérité complète :** [docs/v9-rebuild/evidence/electroverse-throttle-guard-20261122.md](../docs/v9-rebuild/evidence/electroverse-throttle-guard-20261122.md). Nouvelle instruction de l'utilisateur : faire un test de durée de 30 minutes pour **observer un éventuel HTTP 429 réel et le comportement d'arrêt/reprise**, avant de décider du créneau normal ; **le 429 n'est pas garanti**. Base audité `14751573628`, ZIP SHA256 `0ed8c16ca2ce57cec16cc201f4bb41748ca3620e5eee81b7e4e3b9d807bcccf3`, fileset `a6d4cf84436f157b8c38719afcfedae9389cbf7fca5bdab75eba067ab6677e14`, **16 694/22 818 PK** traitées, **6 124** restant. Workflow seul `rebuild/v9-20261020` modifié au SHA `174dfa36b721266675756109e80c79d58830b863` pour autoriser `windowBudgetSeconds=1800` dans une seule fenêtre, cadence **identique** (batch=5, concurrence=1, pauses de 3s), arrêt HTTP/GraphQL rate-limit, diagnostics assainis, aucune seconde tentative automatique. Vérification préalable sans fournisseur [`45019291398`](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45019291398), SHA `0c864034142d598b30e9241937aabfd2231f7ef0` : succès, 14 Python + 8 Node + sécurité + filiation checkpoint exact. **Run fournisseur lancé** [`45019468889`](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45019468889), SHA `b32261dedd45fac950cb5fbf4e00e32ac65002e5`, résultat **inconnu** au moment de cet enregistrement. **Automation d'audit ponctuel créée** : `Automation_be40eca1fc3c819194fb5895bd7e6913` (lecture seule, aucun fournisseur, après fenêtre). **Relais Codex :** Ne pas relancer avant examen du statut, des logs et des artefacts `tcc-v9-electroverse-window` ou `-failure` / `-failure-diagnostics`; vérifier exact SHA, 128 shards, checkedAt, mapping, pending, cause et heure d'un 429, cooldown et absence de nouvelles requêtes après 429. Un `failure` contrôlé sur 429 n'est pas régression. Ne jamais publier les données incomplètes. Data Lab `main`, Production, Stable et Updater Test restent intacts.

## 2026-11-22 — Electroverse V9 : vérification + 3e fenêtre prudente + 10 minutes TERMINÉES

**Preuves complètes :** [docs/v9-rebuild/evidence/electroverse-throttle-guard-20261122.md](../docs/v9-rebuild/evidence/electroverse-throttle-guard-20261122.md). Vérification initiale `45014353664` success depuis parent `14749539699`, SHA `01a676c23aabd5e54e7538ffbf9d66be742124ffd78d3b0709d75099ba6b1d4d`. Troisième fenêtre prudente `45014553502` success +200 PK, 16 294/22 818 et aucun HTTP 429 ; artefact `14751387907`, ZIP SHA `508aec063baaad4327fa35c318512ebf5889cd138f866f3a6dac9f206f010833`, fileset SHA `6e4ca34581a78322893807ff4320ac82e3daa2189e97c9b92edb2550e15130ad`. Workflow amélioré au commit `41d05a6c6b82eb90773b802b79792f96da3e4fb4` : budget explicite borné à 300/600/900, limite 1 fenêtre, SHA et identité exacts du checkpoint vérifiés, même cadence et coupe-circuit anti-429 ; validation offline `45015397835` success, 14 Python+8 Node, safety et parent strict OK.

**Fenêtre étendue 10 minutes** [run `45015561660`](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45015561660), SHA `9efa60dd5556b242a1ee6db4cb5dcd0a127bf2af`, `completed/success`, `checkpointed` ; nouvel artefact [`14751573628`](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45015561660/artifacts/14751573628) ZIP SHA256 `0ed8c16ca2ce57cec16cc201f4bb41748ca3620e5eee81b7e4e3b9d807bcccf3`, fileset SHA256 `a6d4cf84436f157b8c38719afcfedae9389cbf7fca5bdab75eba067ab6677e14`, 137/137 fichiers intègres, 128 shards. Comparaison complète parent-enfant : mapping et inventaire national identiques, pending 1706→1306, **+400 PK** et 400 checkedAt croissants correspondants, **261 hash tarifaires différents, 139 inchangés**, aucune mutation hors fenêtre. **16 694/22 818 = 73,16 %, reste 6 124** ; **0 échec actuel, 0 HTTP 429**, `rateLimit=null`. Artefact partiel `collector_window_budget`, `completeSnapshotValidated=false`, **NE PAS PUBLIER**. Relais : reprendre UNIQUEMENT depuis `14751573628` après vérifications SHA/run/identités et examen des quotas pour la phase à 100 %. Pas d'autres runs autorisés ou lancés dans ce lot ; Data Lab `main`/Production inchangés.

## 2026-11-22 — Electroverse V9 : 3e fenêtre propre, expérimentation de 10 minutes

Preuve détaillée : [docs/v9-rebuild/evidence/electroverse-throttle-guard-20261122.md](../docs/v9-rebuild/evidence/electroverse-throttle-guard-20261122.md). Vérification sans fournisseur `45014353664` OK depuis checkpoint `14749539699` (16 094). Troisième fenêtre `45014553502` / SHA de demande `85744d8e24acfc2f9fd5aebae15a2ea6f30e3357` **completed/success** ; nouvel artefact `14751387907` SHA ZIP `508aec063baaad4327fa35c318512ebf5889cd138f866f3a6dac9f206f010833`, fileset `6e4ca34581a78322893807ff4320ac82e3daa2189e97c9b92edb2550e15130ad`, 137/137 fichiers OK, 128 shards comparés, **+200** PK, **16 294/22 818 (71,41 %)**, **6 524 restantes**, 130 hash changés/70 identiques, pas de hors sélection ni mapping changé, 0 nouvel échec / 0 HTTP 429. État **partiel non publiable**.

Workflow modifié au SHA `41d05a6c6b82eb90773b802b79792f96da3e4fb4` : budget demandé borné à `300,600,900` secondes, exactement une fenêtre fournisseur par run, parent run+artefact+SHA strictement vérifié, mêmes batch=5, concurrence=1, pauses=3 s, circuit breaker anti-429. Validation sans fournisseur `45015397835` **success** depuis artefact `14751387907` (14 tests Python, 8 Node, sécurité, identité exacte OK). Fenêtre étendue 10 minutes autorisée lancée en run [`45015561660`](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45015561660) au SHA `9efa60dd5556b242a1ee6db4cb5dcd0a127bf2af` ; **son résultat reste à auditer**. Aucun autre run en parallèle, aucun main/Production changé. Ne pas déclencher automatiquement une autre collecte ; inspecter statut du run et ZIP, hashes, mapping, checkedAt, 128 shards, diagnostics et complétude avant toute reprise.

## 22 novembre 2026 — Electroverse V9 : deuxième fenêtre anti-429 réussie, checkpoint à 16 094

**Rapport principal et preuves immuables :** [docs/v9-rebuild/evidence/electroverse-throttle-guard-20261122.md](../docs/v9-rebuild/evidence/electroverse-throttle-guard-20261122.md). **Demande utilisateur :** lancer la phase suivante depuis 15 894 PK. Vérification sans fournisseur [run 45011861850](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45011861850) sur `06eda4d511a7f96e3f7ae8f963f49ef66789881d`, `completed/success` (14 Python, 7+1 Node, public safety OK ; source exacte `14749803005`, parent `45010546128`, ZIP SHA `11a47057a7cade7f6fec50735027222e3f390aa9dd734b6905189c62f88f37e8`; mode `verify`, fournisseur skipped). **Collecte** [run 45012004902](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45012004902), SHA de demande `7def0a44c54a15daec5252388422a3dd253c83ee`, job `137176147909`, `completed/success`, `checkpointed` après UNE fenêtre prudente ; nouvel artefact de checkpoint `14749539699` créé 2026-11-22 10:30:05 UTC, ZIP SHA-256 `01a676c23aabd5e54e7538ffbf9d66be742124ffd78d3b0709d75099ba6b1d4d`, fileset `4bcc98dc454cfcea0c323598b7de1b7776e20b9518752f8091b101f61d8c8a9f`, 137/137 fichiers et 128 shards validés, origine et checksums prouvés. Mapping et inventaire France inchangés ; `pending` 2106→1906, +200 PK contrôlées (15 894→**16 094/22 818 = 70,53 %**, **6 724** restent), 200 `checkedAt` croissants, 146 hash tarifaires changés, 54 identiques, zéro modification hors fenêtre. `hybrid-refresh-failures=[]`, `lastIncrementalRefresh.rateLimit=null` : **zéro nouvel HTTP 429**, ne pas inférer quota global/fin de saturation. Source manifest `partial_failure` raison `collector_window_budget`, `completeSnapshotValidated=false` : **jamais promouvable en Production**. Batch 5, concurrence 1, pauses 3s, limite d’une fenêtre. Aucune autre collecte, aucun changement main/Production. **Relais Codex CLI** : lire le rapport versionné, reprendre uniquement du nouveau ZIP SHA et valider provenance/monotonicité avant de déclencher la prochaine fenêtre ; l’ID numérique du dernier artefact est inférieur à l’ancien malgré une date de création postérieure. 

## 2026-11-22 — Electroverse anti-429 : premier essai fournisseur réussi, checkpoint partiel

**Rapport/version :** [docs/v9-rebuild/evidence/electroverse-throttle-guard-20261122.md](../docs/v9-rebuild/evidence/electroverse-throttle-guard-20261122.md). Après validation no-provider [run 45010329672](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45010329672) (14 tests Python, 8 Node, sécurité et filiation PASS), le run fournisseur plafonné [45010546128](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45010546128), code `818629b221e1b474210c39b61a922bd14008be16`, est **`completed/success`** et `checkpointed` (NON complete). Nouvel artefact `14749803005` `tcc-v9-electroverse-window`, ZIP SHA-256 `11a47057a7cade7f6fec50735027222e3f390aa9dd734b6905189c62f88f37e8`, fileset `93d7f3542fd62a9d1dbc8a59cc71757b580819a20399580e4dc011f968f38809` (137/137 checks, 128 shards), parent `14734805610`. Comparaison complète du parent : mapping/inventaire inchangés, +200 PK (15 694→**15 894**/22 818, reste **6 924**), pending 2306→2106, 200 horodatages correspondants croissants, 117 hash tarifaires modifiés, 83 identiques, zéro mutation hors fenêtre, **0 échec et 0 HTTP 429 nouveau**. Arrêt volontaire `collector_window_budget`, `completeSnapshotValidated=false`. Source non publiable ; le collecteur a été préparé avec batch=5/concurrence=1/pauses de 3 s et coupe-circuit au 429 ; cette réussite courte ne valide pas un quota durable. Aucune autre collecte concurrente ni promotion main/Production. **Relais :** conserver l'artefact SHA exact, auditer une nouvelle fenêtre sous contrôle avant généralisation ; le sélecteur peut choisir le nouvel artefact `-window` sous provenance et SHA vérifiés. 

## 22 novembre 2026 — Electroverse circuit breaker / filiation / collecte limitée

**Preuve source :** [docs/v9-rebuild/evidence/electroverse-throttle-guard-20261122.md](../docs/v9-rebuild/evidence/electroverse-throttle-guard-20261122.md). Modifications autorisées sur Data Lab `rebuild/v9-20261020` seulement : `fa3eabd2` (arrêt immédiat sur HTTP/GraphQL 429, conservation des PK validées/pending, délai Retry-After ou 900 s, journaux assainis), `81592cc3` (checkpoint strict `14734805610` à 15 694/22 818, ZIP SHA256 `60bbd578cc6a8193e5dbc6c3105bacc16407c06bd42f431bad2ae803f6099f01`, 128 shards, preuve +2498/1077 hash vs `14730224631`), `88fdebbb` (tests d'intégration sans API et limite 1 fenêtre), `55e661cb` (false positive scanner corrigé). **Validation :** run `45010329672` `completed/success` : 14 Python + 8 Node, scanner sécurité OK, SHA et filiation PASS, aucune requête fournisseur. Première validation `45010102457` bloquée par scanner sur valeur synthétique de test, sans appel fournisseur. **Collecte supervisée :** run `45010546128` au SHA `818629b221e1b474210c39b61a922bd14008be16`, `mode=collect`, 1 fenêtre, budget 300 s contrôlé entre fenêtres de 100 PK, batch=5/concurrence=1/pauses 3 s, issue encore inconnue au moment de cette entrée. Aucune promotion d'un partiel, aucun changement main/Production/Tesla. **Relais Codex CLI** : ne pas relancer avant examen du run et de ses artefacts, digests, PK réellement avancées, statuts 429, pending et source complète/non complète ; le sélecteur échoue fermé sur un nouvel artefact d'échec non épinglé.

## 2026-11-22 — Electroverse 429 : run #44968499274 audité (ne pas relancer en l'état)

Preuve durable : [docs/v9-rebuild/evidence/electroverse-rate-limit-diagnostic-20261122.md](../docs/v9-rebuild/evidence/electroverse-rate-limit-diagnostic-20261122.md). Run `44968499274` / job `137042831416` sur code `1c8c6d1b` terminé en `failure` ; 13 tests Python + 4 Node + safety + filiation **PASS** ; collecteur non complet. Ancien parent `14730224631` (ZIP SHA256 `92ffb6c8…`), nouvel artefact `14734805610` (ZIP SHA256 `60bbd578cc6a8193e5dbc6c3105bacc16407c06bd42f431bad2ae803f6099f01`, file-set `1aea5283a310f637410db62b9743891122ba33d2126269648dadb9cbfb6231fe`), 137/137 fichiers intègres. `13 196 → 15 694 / 22 818`, **+2 498**, reste **7 124**, `pending 4804 → 2306` ; 128 shards, mapping et inventaire intacts, 1077 hash modifiés et 1421 identiques, aucune mutation hors PK vérifiées. Les trois anciens échecs sont résolus ; deux nouvelles PK `4475895/4475896` enregistrent chacune cinq `HTTP 429` (2 single + 3 paged) à réponse vide, sans Retry-After ni quotas. Diagnostic indépendant `14734885341`, ZIP SHA `6ef10fdc4fdd1c045156a34b09dec2166ac382ae4222cda80bb1723eb3c999f9`. Limitation fournisseur prouvée, quota exact inconnu, couverture des statuts batch à améliorer. **Checkpoint partiel, interdiction de promotion Production.** Avant toute nouvelle collecte : mécanisme anti-429/circuit breaker, validation et épinglage du nouveau checkpoint, tests hors ligne, puis courte reprise sous contrôle sans répétition des 2 498. Audit sans run supplémentaire, aucune modification de main/Production. 

## 22 novembre 2026 — reprise diagnostique Electroverse autorisée et lancée (résultat fournisseur à vérifier)

- **Branche** : Data Lab `rebuild/v9-20261020`, aucune modification de `main`, Production, Stable, Updater Test ou des prix/jointures. Correctifs versionnés sur la branche : `8ed37d79` (sanitisation), `9f891e46` (tests Node), `1e3ce8a7` (trace single/paged et historique de cache), `99ef7fc2` (transaction checkpoint), `c3dc11c4` (sélection SHA strict), `f8f7e626` (preuve du successeur), `37153d9d` (workflow et artefact de diagnostic).
- **Preuve distante avant collecte** : run `44968308102`, SHA `81609e3a970f4a72d0540c7b5379747b51c2ad88`, `completed/success`. 13 tests Python et quatre tests Node `PASS`, `Public safety scan: OK`, sélection du parent `44962339493/14730224631` SHA ZIP `92ffb6c827fdfe805518746aa0eba13730a8f26ef6254ef9b69e149de655e5c1`, validation contre `44956526554/14729002853` `PASS`. 128 shards, mapping et inventaire inchangés, 697 PK vérifiées conservées ; total `13 196/22 818`, `9 622` restant, erreurs `426269/426271/426272` toujours pending. Mode `verify` : étape fournisseur `skipped`, aucun appel.
- **Nouveau run fournisseur** : `44968499274` (https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/44968499274), commit de demande `1c8c6d1b377d266ab2f82b053326aeb5c3604b97`, `mode=collect`, dernier état initial `queued`, aucune conclusion ni nouveaux PK démontrés à cet instant. Le protocole préserve le last-good et empêche toute promotion d'un checkpoint partiel.
- **Nouvelle télémétrie** : le client collecte déjà HTTP/status/durée/quota ; le script conserve maintenant les métadonnées de chaque tentative single/paged non résolue avec type, page, essai, code HTTP, durée, poids, présence JSON, GraphQL count/code et classe réseau, sans corps, URL, messages ni secret. `reports/electroverse/hybrid-refresh-failures.json` conserve les détails de l'échec courant ; `reports/electroverse/failure-diagnostics.json` conserve l'historique dans le cache avec rollback transactionnel ; artefact indépendant `tcc-v9-electroverse-failure-diagnostics` en cas d'échec. La cause des échecs fournisseurs reste INCONNUE avant examen du nouvel artefact.
- **Passage de relais** : ne pas déclencher de reprise concurrente. À l'issue du run `44968499274`, vérifier statut, logs, artefact, SHA-256, fichiers du manifeste, 128 shards, horodatages, sorties hors fenêtre, PK échouées/pending, diagnostics assainis et état `completeSnapshotValidated`; ne pas convertir `success` Actions en snapshot complet. En cas de nouvel échec, le sélecteur refuse volontairement un artefact non validé et une nouvelle reprise exige l'audit de filiation. Aucun déploiement ni nouvelle collecte avant cet examen.

## 22 novembre 2026 00:53 CET — troisième run Electroverse `44962339493` terminé FAILURE, progression conservée

[Run 44962339493](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/44962339493) : **FAILURE** après restauration réussie de l'artefact d'échec parent `14729002853`. Trois nouvelles `fetch_failed` : PK `426269`, `426271`, `426272`; ancienne `4234003` résolue. Nouvel artefact d'échec `14730224631`, ZIP SHA-256 `92ffb6c827fdfe805518746aa0eba13730a8f26ef6254ef9b69e149de655e5c1`, fileset SHA `1969e550c139db2dfdad6f0709b0bc4084002d424a6d9e66c90ccc56cb6d4fa9`, **136/136 hashes PASS et 128 shards intacts**. **+697 PK** revérifiées, total **13 196/22 818 (57,83 %)** ; 498 `tariffHash` modifiés, 199 identiques, hors fenêtre intact. `completed=[0,6000]`, `pending.offset=12000`, `pending=4804`, reste **9 622**. **Aucun run suivant à lancer tel quel** : sélecteur a un pin contrôlé sur un ancien `-failure` et bloque le nouvel échec sans audit. Ne pas refaire les 697 appels ; prochain chantier = contrôle automatique sûr de la chaîne des échecs successifs, puis run `verify` sans fournisseur. Rapport intégral : `docs/v9-rebuild/evidence/electroverse-resume-20261121.md`. Pas de mise à jour Production ni de `main`.

## 22 novembre 2026 00:33 CET — reprise de l'artefact d'échec vérifiée sur GitHub, collecte relancée

**Problème initial :** run #44956526554 terminé `failure`, mais artefact 14729002853 préservant **2 199 vérifications** nouvelles ; le sélecteur ignorait cette archive `-failure` et aurait retraité inutilement 2 199 PK depuis l'ancien checkpoint `14727835115`.

**Correctif `eb6849414bafca67764f282c52bed5df86e03404`** sur `rebuild/v9-20261020` : `scripts/select_v9_electroverse_checkpoint.py` autorise uniquement **l'artefact d'échec précisément audité** (run `44956526554`, artifact `14729002853`, head `1edd310ebbad1d554f7bbe3c8599678dacbd440f`, ZIP sha `2e1c1b9c4a8feeb3049f99db8e4df9ef9a1a24cc890359d0ea2aa1bb1a42ecf7`) et refuse tout nouvel échec non audité plus récent. `scripts/verify_v9_electroverse_failed_parent.py` compare l'intégralité des deux ZIP, SHA/tailles de 136 fichiers, 128 shards, identité du mapping et inventaire, curseur monotone, PK horodatées, `tariffHash` hors fenêtre, rapport fournisseur et PK échouée conservée en attente. Le workflow de branche `.github/workflows/v9-electroverse-resume.yml` impose la preuve **avant toute reprise fournisseur**. Trois tests de sélection ajoutés ; aucune politique de prix ni rapprochement IRVE modifiés.

**Validation distante :** [run #44962135060](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/44962135060), job `137023060349`, code `0da5afaba6c7c2833e86db65f6eb9b1e333029dc`, `completed/success`. **13 tests PASS**, `Public safety scan: OK` ; sélecteur renvoie `state=recovered_failure`, `run=44956526554`, `artifact=14729002853`. Parent et descendant ZIP sha OK ; script de preuve rapporte `completed=[0,6000]`, `newlyChecked=2199`, `totalChecked=12499`, `remaining=10319`, `pendingOffset=12000`, `pending=5501`, `failedPk=4234003`, `tariffHashChanged=971`. `verify_checkpoint` a ensuite confirmé le contenu et mapping intègres. **Aucun appel fournisseur** pendant ce run `mode=verify`.

**Reprise réelle :** sur autorisation utilisateur « D'accord lance la suite », push du seul fichier `migration/v9/electroverse-resume-request.json` en `mode=collect`, parent explicitement demandé `basisRun=44956526554`, `basisArtifact=14729002853`, `verifiedRecoveryRun=44962135060`; commit `5fffc5bbf931533d2b177d414484e9a9f6a78167`. Nouveau [run #44962339493](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/44962339493), job `137023677341`, déclenché le 21/11/2026 à 23:33:03 UTC, **in_progress** au dernier contrôle ; étape fournisseur et progression **non encore démontrées**. Ne pas inventer de gain avant vérification de l'artefact sortant. Aucune exécution concurrente observée avant push. Aucun changement sur `main`, Production, Netlify, les statuts ni les jointures.

**Prochain contrôle exact** : ouvrir les logs et le nouvel artefact du run `44962339493`, s'assurer que le parent choisi est `14729002853`, confirmer la preuve `recovered_failure`, examiner `collector_window_budget` vs `collector_exit_nonzero`, valider ZIP SHA, fileset, 128 shards, dates `checkedAt`, `pending`, échecs et tarifications hors fenêtre. Ne pas lancer de quatrième run automatiquement ni assimiler `success` GitHub à collecte complète. Tous les échecs supplémentaires non audités doivent rester bloquants afin d'éviter le retraitement.

## 22 novembre 2026 — deuxième run Electroverse #44956526554 : échec après progression, ne pas relancer tel quel

[Run #44956526554](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/44956526554) **completed/failure** : source `collector_exit_nonzero`, une seule PK en erreur fournisseur `4234003/fetch_failed`, garde `Incomplete tariff chunk retained; no automatic provider retry`. Artefact `14729002853` **`tcc-v9-electroverse-failure`** (ZIP SHA `2e1c1b9c4a8feeb3049f99db8e4df9ef9a1a24cc890359d0ea2aa1bb1a42ecf7`, fileset SHA `789fbf0f55d3d38ba8d9a84695215f81edd0e374db08549f0e011c8d3df58dd8`) : 136/136 SHA/tailles PASS et 128 shards ; +2199 PK vérifiées, total **12499/22818 (54,8%)**, 971 `tariffHash` modifiés, **aucune donnée hors fenêtre ni mapping altéré**. `completed=[0,6000]`, `pending.offset=12000`, `pending=5501` (dont la PK en erreur), reste **10319** à vérifier. **ATTENTION : le sélecteur actuel ignore les artefacts d'échec ; il reprendrait 14727835115 et rejouerait 2199 vérifications. Ne pas relancer avant correctif d'une reprise vérifiée depuis l'artefact d'échec.** Détails et preuve : `docs/v9-rebuild/evidence/electroverse-resume-20261121.md` § audit 22/11. Aucun autre run lancé.

## 21 novembre 2026, 22:23 UTC — deuxième run réel Electroverse lancé (non terminé)

Demande explicite utilisateur « Ok lance le 2e run ». Contrôle préalable : aucun run de reconstruction actif dans les 40 derniers runs de `rebuild/v9-20261020`, artefact 14727835115 du run #44950136959 disponible, `expired=false`, digest `sha256:3622a321b6885434d7c4541199d2ffc58703c82f790a0511a6b3cf998e6e7aac` (expiration 21/12/2026). Le sélecteur `scripts/select_v9_electroverse_checkpoint.py` donne priorité aux artefacts `tcc-v9-electroverse-window` de la branche et valide run, SHA et digest avant récupération ; **le choix effectif du parent par le nouveau job doit être confirmé dans ses logs**.

Push atomique du seul `migration/v9/electroverse-resume-request.json` `mode=collect`, `basisRun=44950136959`, `basisArtifact=14727835115`, commit `1edd310ebbad1d554f7bbe3c8599678dacbd440f` depuis `3010111750b1764ccbbf85ab08a79f4e26fb7d94`.

[GitHub Actions #44956526554](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/44956526554), job `137005752077` : déclenché le 21/11/2026 à 22:23:44 UTC, **in_progress** au contrôle initial ; aucune conclusion encore. Périmètre : continuation de la campagne `FR:electroverse_full` sur cache 22 818 localisations, après 10 300 vérifications au dernier checkpoint et 1 700 PK `pending` au deuxième bloc (12 518 non revérifiées à l'échelle de la campagne). **Aucun gain n'est revendiqué pour ce nouveau run sans analyse de son ZIP**. Aucune modification du mapping IRVE, de la branche `main`, des workflows Production ni de Netlify. Automatisation entre runs séparés toujours non active. À clôture : vérifier conclusion, `collector_window_budget`, nouvel artifact, SHA du ZIP et 136 chemins, 128 shards, curseur, horaires et différences sous fenêtre uniquement. Ne jamais promouvoir automatiquement le checkpoint partiel.

## 21 novembre 2026 22:14 UTC — conclusion du premier run réel de continuation Electroverse

Run `44950136959`, job `136986031949`, SHA code `78d3c997` : GitHub success mais collecte `checkpointed`/`collector_window_budget`, donc partielle. Artefact `14727835115`, ZIP SHA256 `3622a321b6885434d7c4541199d2ffc58703c82f790a0511a6b3cf998e6e7aac`, fileset `b04dfb1565024c06a40b5fc75069ea07cad2f03e24f7fa8032634657a662d1e3` : 136/136 fichiers internes OK, 128 shards intacts. Comparaison au parent `14711673559` : +2 900 checked (10 300 cumulés), 1 604 `tariffHash` modifiés, aucun changement hors ces PK, mapping identique ; `pending.offset=6000, pending.pks=1700`. Aucun nouveau run ni changement de Production/main ; suite dans rapport Electroverse.

## 21 novembre 2026 — lancement réel Electroverse #44950136959 (à contrôler après terminaison)

**Autorisation explicite utilisateur :** « D’accord lance le run ». Après vérification qu'aucun workflow de reconstruction n'était actif, checkpoint de départ `14711673559` non expiré, SHA-256 ZIP `a31e1630c39271e7f912a5d4e3262aa95a924a1f0d5dbb291f61d337b82c2879` et HEAD initial `df7ae13ce237e23f131dc1d810bf1508f46209fd`, push **du seul fichier** `migration/v9/electroverse-resume-request.json` en `mode=collect` : commit `78d3c997c156a54c7954808969c2fe369918a330`. Nouveau [run 44950136959](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/44950136959), job `136986031949`, démarré le 21/11/2026 21:10 UTC, **`in_progress` au dernier contrôle**. Aucun autre run concurrent observé lors du lancement.

**Source** `FR:electroverse_full`. Reprise attendue de `completed=[0], pending.offset=6000, pending=4600` ; les 7 400 revérifiés antérieurement restent dans le checkpoint, les 15 418 autres restent archives jusqu'à un contrôle effectif. **Ne pas affirmer un traitement nouveau ou un succès avant les journaux, l'artefact et les empreintes en sortie.** Chaque fenêtre ne déclenche que les appels de la méthode déjà validée. Aucun rematching IRVE, changement Production/Netlify/`main`. La continuation automatique **entre jobs distincts** n'est pas activée. Après terminaison, examiner `conclusion`, états des steps, journaux, `checkpoint-manifest.json`, nombre de PK revérifiées, filiation, fichiers SHA/ZIP et absence de prix de faux positif. Toute nouvelle relance doit être fondée sur ce résultat et sur l'absence de concurrence.

## 21 novembre 2026 — preuve distante PASS de la restauration Electroverse, mode verify

Run `44947769520` / job `136978761119`, code `d14a5326` : succès GitHub Actions ; 10 tests offline PASS et scan public OK ; parent `44912790561` / artefact `14711673559` sélectionné automatiquement puis archive ZIP sha et contenu validés sur runner, mapping conservé. L'étape fournisseur a été sautée par conception ; aucune donnée tarifaire acquise. Autorésolution inter-runs non installée. État et limites reportés dans `docs/v9-rebuild/evidence/electroverse-resume-20261121.md` §6.

## 21 novembre 2026 — correctif Electroverse de continuation bornée, test Actions en lecture seule

`725cb00e5` : le pilote conserve `completed/pending`, continue plusieurs fenêtres dans le même job si budget suffisant, et impose réserve 1800+300 secondes, validations de curseur et arrêt avant retard. `ee7bd6a3` : nouveau workflow dédié branche reconstruction, permission GitHub read-only, sélecteur provenance/digest/manifest/root immuable ; artefacts partiel/complet/échec séparés. `d14a5326` : déclencheur `mode=verify` uniquement, run `44947769520` lancé (résultat à confirmer). Archive 14711673559/136 fichiers/128 shards SHA vérifiés, 7400/22818 localisations contrôlées ; 4600 PK pending du chunk 6000. Aucune modification de Production/main ou mapping, aucune acquisition nouvelle. Autoréexécution inter-runs non configurée. Voir `docs/v9-rebuild/evidence/electroverse-resume-20261121.md`.

## 21 novembre 2026 — Audit du cache historique Electroverse (réutilisabilité, lecture seule)

Rapport daté : `docs/v9-rebuild/evidence/electroverse-reuse-audit-20261121.md`. Deux ZIP réels téléchargés ; SHA externe et 136/136 SHA internes validés, 128 shards et mapping sans divergence ; 22 818 lieux / 7 400 contrôlés en novembre / 15 418 octobre. Dernier run 44912790561 : succès workflow mais checkpoint partiel, non promotionnable. 1 058 objets `tariff` modifiés entre deux checkpoints, pas nécessairement des prix numériques. Mapping historique : 22 816/22 818 correspondances spatiales, opérateur pas démontré pour chaque ligne ; 13 partitions de statuts datées/incomplètes et incompatibles. Réutiliser archive last-good, audit exact+opérateur puis adresse/GPS+opérateur **à venir**, aucune requalification PASS ni nouvel appel fournisseur. Uniquement documentaire.

## 21 novembre 2026 — priorité de rapprochement Electroverse avec bases nationales

Instruction fonctionnelle utilisateur : **correspondance des bornes + opérateur d'abord ; en cas d'échec, adresse ou coordonnées GPS + opérateur ; seulement ensuite marquer la liaison non résolue**. France pilote, politique générique pour extension internationale ultérieure. Alignement documentaire avec les règles historiques de rapprochement, groupes homogènes et non-propagation tarifaire. Norme G5 et documents eMSP mis à jour ; `CURRENT.md` et registre V9 aussi. Validation de code/run/Production : NOT TESTED. Aucun déclencheur Actions activé et aucune publication effectuée.

## 21 novembre 2026 — Audit des accès, documenté sans action fonctionnelle

Compte GitHub et écriture sur `rebuild/v9-20261020` confirmés (commit de convention `c4c8d1483`). Lecture GitHub Actions, logs et téléchargement ZIP (FX, artefact `14709882404`) vérifiés. Pas de commande de dispatch direct exposée par le connecteur GitHub ; permissions Actions à l'exécution non testées. Navigateur TinyFish inaccessible faute de crédit ; accès de déploiement Netlify non établi. Réserves et suite enregistrées dans la section 8 de `WORKING_AGREEMENT.md`. Aucune collecte Electroverse déclenchée, aucun changement de Production ni de main.

## 21 novembre 2026 — Accord intersessions ChatGPT / Codex CLI

Décision utilisateur : tracer les modifications significatives, preuves, SHA, runs/artefacts, checkpoints, états partiels, dépendances, sécurité, rollback et prochaine reprise ; assurer lecture commune des références dans toute nouvelle conversation ou session Codex. Nouvelle référence `memory/WORKING_AGREEMENT.md`, reliée à `AGENTS.md` et `memory/README.md`. Modification **strictement documentaire**, sans collecte, activation de workflow, changement de prix, de Production ou de cahier des charges. Autorisation d'exécuter Electroverse à demander séparément. Les capacités non testées des connecteurs restent explicitement non garanties.

## État de reprise — 21 novembre, 14 h 16 UTC

La version de recette distante est le [brouillon 6b01a403](https://6b01a403ef31f5a551927fa2--tcc-v9-preproduction-20261028.netlify.app). La preuve Production b1d102d couvre le manifeste et 3 242 fragments, les parcours Firefox, le mobile, les contrôles nationaux et le retour arrière. Le registre Data Lab 628927825 compte 77 transferts prouvés et 58 ouverts.

Deux opérations GitHub ont démarré et ne comptent pas comme transferts validés. Pour 44912790561, attendre la fin, puis exécuter `scripts/verify_v9_tariff_checkpoint.py --run 44912790561 --head 2d19e361530f5a66072a56b6491f16779a9a823f --out <nouveau-dossier-hors-checkout>` si le run contient une fenêtre partielle. Si le manifeste indique une collecte complète, employer le vérificateur de handoff avec contrôle de toutes les générations. Pour 44912916198, vérifier le ZIP du job GB:connected_kerb_app sur 8962d5da0f425e1f9ce63fa92205f51ebd6a4195 avec le validateur renforcé 9c7c879e1. Les erreurs HTTP ou de budget empêchent la promotion. Ce run précède la distinction renforcée des recherches QR : conserver les exclusions non démontrables et exiger un run du code corrigé en cas de réponses ambiguës. Les cadences permanentes sur main 669c53ce8 doivent encore produire leurs propres événements schedule. Les taux, tarifs et états partiels postérieurs au brouillon ne sont pas présentés comme servis.

## Recette distante du nouveau paquet suisse

Le brouillon 6b01a403 (Production b1d102d) a passé la recette distante de ses 3 242 fragments, 24 parcours tarifaires, 11 recherches sur les neuf pays, mobile, neuf parcours Tesla et rollback. Amsterdam à 100 km : 56,796 s à froid pour 64 019 stations ; signatures identiques. G7/G8 restent ouverts. Le run Electroverse 44912790561 a démarré sur 2d19e3615 avec le checkpoint 14710945245 ; vérifier son ZIP et ses lignes par scripts/verify_v9_tariff_checkpoint.py avant toute nouvelle reprise. Le rapprochement Connected Kerb doit restaurer le parent vérifié 14710885308.

## Reprise Electroverse et collectes britanniques du 21 novembre

Le run 44909970308 a terminé volontairement une fenêtre après 1 400 identités supplémentaires. Vérification des 128 shards, des empreintes des lignes antérieures et du curseur exact : 5 200 identités cumulées, 800 restantes dans le premier bloc de 6 000. Le ZIP 14710945245 est un checkpoint partiel. Les statuts et l’overlay attendent le cache complet. Les deux sorties britanniques du run 44912549458 ont réussi les contrôles de transfert et de contenu ; la portée PAYG et la TVA Eco-Movement restent non démontrées. Le registre compte 77 transmissions prouvées, 58 ouvertes. Le brouillon suisse 6b01a403 a passé les contrôles distants de ses 3 242 fragments. Prochaine opération : reprendre le checkpoint vérifié, puis contrôler la prochaine fenêtre et les événements programmés.

## Cadence des taux de change du 21 novembre

GL:fx a obtenu la table datée du 20 novembre, sans taux ancien reporté. Le ZIP 14709882404 du run 44911943370 est vérifié. Les réponses partielles, montants booléens ou non finis et dates fournisseur absentes empêchent la promotion. PR 346 : FX en job isolé à son horaire historique de 03:37 UTC sur main 669c53ce8. Une défaillance FX est indépendante de l’import IONITY. Le déclenchement programmé reste à démontrer. Les 1 207 workflows archivés restent restaurables. Registre global : 75 handoffs vérifiés, 60 ouverts. Le brouillon 6b01a403 est en recette distante.

## Import des sources dérivées et candidat suisse

Le run 44911508448 transmet trois sorties vérifiées depuis deux ZIP parents identifiés et restaurés (Kilowatt et EBS). Aucun nouvel appel fournisseur pour ce lot. G2 compte 75 transferts démontrés sur 135 et 60 ouverts. Le nouveau brouillon Netlify 6b01a403 sert le bundle afee49dc ; sa recette distante est en cours. La prochaine vérification Electroverse doit comparer toutes les fenêtres précédentes aux lignes conservées et aux identités encore en attente.

## Renouvellements Direct et contrôles d’archives

Run 44910925626 : les transferts de FastVolt, Greenspot et des tarifs fixes secondaires français ont réussi. Deux autres jobs ont traité uniquement les archives de fiabilité et de résidus Electra. Le contrôle des tarifs fixes principaux français a échoué et son dernier état valide est conservé. Registre G2 : 72 transferts démontrés sur 135 ; 63 restent ouverts. Le nouveau bundle local afee49dc contient les entrées suisses renouvelées et a été importé. La nouvelle recette suisse et ses contrôles distants demeurent en attente.

## Inventaire national suisse et portée des offres

L’ancien constructeur remplaçait une ligne nationale par la dernière occurrence de son EVSE_ID. Sur l’entrée nationale du 21 novembre, 94 identifiants appartiennent à plusieurs couples opérateur/station. Le constructeur conserve les lignes physiques, marque l’ambiguïté avant le filtre d’accès public et exclut ces identités des jointures et calculs. Le replay des quatre artefacts suisses et des autres contrats conservés produit 163 lignes publiques concernées, sans offre attribuée par leur identifiant ambigu. Dix-sept tests ciblés passent. Le brouillon 6b019c9c utilise encore la Suisse antérieure à cette correction. Contrôler ensuite le nouveau paquet suisse et les parcours distants avant de le proposer.

## Nouvelle préproduction vérifiée et reprise des collectes du 21 novembre

Le candidat [6b019c9c](https://6b019c9cdd3d0f7827ea0491--tcc-v9-preproduction-20261028.netlify.app) a passé la recette distante. Le commit Production ba1d2dd conserve les 3 244 empreintes, 24 parcours tarifaires, recherches neuf pays, contrôles mobiles et retour arrière. Amsterdam à 100 km reste lent (52,961 s à froid en mesure isolée).

Le run suisse 44910057641 a rejoué les octets nationaux authentifiés du run 44909322062. Les trois artefacts autoSense, Partino et Saascharge ont été téléchargés et contrôlés. Les quatre identités Saascharge ambiguës sont conservées sans prix. Ces artefacts suisses sont en amont du candidat servi. Le registre comporte 67 transferts prouvés, 68 ouverts. Electroverse 44909970308 reprend le checkpoint vérifié 14709253407 à partir de b1a8773d6b22275d36e0713e8d137d9ac554f9cf. À sa fin, vérifier le ZIP et la filiation avec scripts/verify_v9_tariff_checkpoint.py, puis préparer la prochaine fenêtre. Attendre les événements cron réels et vérifier leurs SHA et imports. G2–G8 restent ouverts.

## Reprise des fenêtres Electroverse et de la source nationale suisse

Le ZIP 14709253407 du run 44906379578 est conservé et les 128 shards sont vérifiés. La même génération a progressé de 1 800 identités supplémentaires ; il en reste 2 200 dans le premier bloc. Le checkpoint reste isolé. Prochaine fenêtre bornée à 30 minutes, puis vérification du ZIP et des identités avant toute reprise.

Suisse : le ZIP national 14709390954 a permis de renouveler le périmètre CHEVP. Le registre passe à 64 transferts prouvés sur 135. Le replay des mêmes octets établit que l’appartenance OICP de Partino et autoSense ne se déduit pas du préfixe des identifiants. La correction compare les identités et leur propriétaire exact ; deux replays passent. Les quatre identités Saascharge présentes chez deux opérateurs empêchent la promotion de sa sortie. Ces replays ne valent pas transfert GitHub.

## Cadence Direct étendue sur main

PR 345 intègre neuf méthodes quotidiennes ayant chacune un transfert réel validé. Le groupe permanent de 08:53 UTC exécute désormais 26 méthodes, avec deux collectes simultanées au maximum. Chaque nouvelle entrée épingle son code testé. Main 157f7e86f, un seul workflow actif, 1 207 anciens YAML restaurables. Les vérifications sur événements programmés restent ouvertes. Le paquet consolidé en préparation regroupe le renouvellement IONITY, les connecteurs EVGO et le catalogue Tesla/Mac du 23 octobre. G2 demeure ouvert (63/135 transferts vérifiés).

## Import réel Tesla/Mac du 21 novembre

La collecte Mac reste dans Updater Test. Le pilote Data Lab 44907714124 a importé le catalogue validé publié le 23 octobre, différent des octets du brouillon 6b01917b. Artefact 14708846562, catalogue SHA 5794c76480ceaee63d73a6cf39ee8fb24ed68357cafdaa44b90ddd09a80f01d4. Les dates par pays sont conservées. Le registre compte 63 transferts prouvés et 72 ouverts. Le lot EVGO renouvelé a également passé l’import Production local (deux connecteurs ajoutés et deux retirés, aucun prix ajouté). Préparer le paquet groupé avec ces deux entrées et contrôler ses scénarios navigateur avant transfert. Electroverse 44906379578 et la cadence REVE restent à contrôler.

## Espagne et Maroc, 21 novembre

Le run 44907080870 a transmis le lot tarifaire secondaire espagnol et les données EVGO du Maroc. Les deux ZIP ont été téléchargés et leurs sorties revérifiées avec les validateurs de source. Le lot tarifaire principal espagnol a échoué et conserve son dernier état valide. Ces deux nouveaux transferts ne figurent pas dans le brouillon 6b01917b. Le registre compte 62 transferts prouvés et 73 ouverts. L’import Production du catalogue Tesla/Mac a également passé ses contrôles sur l’archive réelle après retrait du seuil historique (b40c0a0). Prochaine opération : vérifier le checkpoint Electroverse 44906379578, l’événement horaire REVE, puis comparer EVGO au snapshot servi avant toute intégration.

## Reprise Electroverse et recette distante Amsterdam

Le pilote Electroverse 44906379578 reprend le ZIP 14707049235 depuis f943911ba. Son YAML est archivé. Le workflow permanent est 425938005. G2 conserve deux motifs ouverts : 75 transferts à démontrer et registre d’exécution partiel. Le vérificateur 17990d2cc contrôle la filiation et les empreintes des lignes tarifaires dans chaque fenêtre de collecte. À la fin du run, vérifier son artefact avec scripts/verify_v9_tariff_checkpoint.py (SHA f943911ba5b585a850d00f55521ae98350b1f88c en cas de checkpoint), puis comparer les identités acquises. Contrôler aussi l’événement REVE programmé à :27 et son quota. Production 7d4013d consigne 51,419 s à froid sur Amsterdam à 100 km et l’égalité des résultats pour 64 019 stations.

## Préproduction 33 sources et reprise Electroverse du 21 novembre

Le brouillon https://6b01917b60790d93e2aff701--tcc-v9-preproduction-20261028.netlify.app sert le bundle 96bfbdaf. Production 0124ce6 conserve les contrôles HTTPS/noindex, SHA des 3 244 fragments, 24 parcours tarifaires Firefox et 11 recherches sur neuf pays, ordinateur et mobile. IONITY a été renouvelé, importé et vérifié dans les données servies. Le paquet précédent reste restaurable.

Le run Electroverse 44902743843 a atteint sa limite de temps après avoir vérifié 2 000 entrées. Son ZIP et ses 128 shards sont intègres. Il reste 4 000 entrées dans le premier bloc de 6 000. Le reçu electroverse-checkpoint-44902743843.json identifie la génération et son empreinte. Reprendre depuis 14707049235, vérifier le prochain checkpoint et sa filiation avant toute promotion. 60 transferts sur 135 prouvés. Les délais fournisseur et les déclenchements programmés restent à valider.

## Reprise REVE et collectes Direct — 21 novembre

PR 344 : reprise permanente du flux REVE sur son horaire historique (minute 27 UTC). Le run manuel 44905451849 a restauré la génération vérifiée du 5 novembre et reçu cinq réponses HTTP 200. Les pages suivantes sont désormais 43/29 au lieu de 40/27 ; tout nouveau lot attend le quota. L’artefact 14707553257 a été restauré indépendamment avec contrôles SHA. Il reste partiel et ne peut pas être importé comme tarif national. Les échecs fournisseur conservent leur curseur et aucun ancien workflow ne s’est activé. L’événement programmé reste à vérifier. Sept reçus Direct supplémentaires sur le run 44905026998. Registre 60 handoffs vérifiés sur 135, 75 en attente. Brouillon 6b01917b en cours de vérification distante pour le bundle 96bfbdaf, antérieur aux renouvellements Direct de ce jour, hormis IONITY. Vérifier son intégrité complète, la reprise Electroverse 44902743843 et les premiers événements programmés.

## Cadences permanentes des preuves Direct — 21 novembre

Le calendrier permanent regroupe 17 collecteurs Direct ayant déjà réussi leur transfert réel et dont le YAML archivé prévoit une collecte quotidienne. Les méthodes historiques manuelles sont exclues. PR 343 : un seul workflow actif, deux sources Direct simultanées maximum, 1 207 workflows archivés restaurables. IONITY reste à 03:37 UTC et les preuves Direct sont regroupées à 08:53 UTC. L’exécution cron est encore NOT TESTED ; les destinations sont des artefacts isolés et aucun prix générique n’est attribué à un PDC.

## Handoffs suisses et intégrité des fenêtres Electroverse — 21 novembre

Huit nouvelles transmissions ont été vérifiées sur le run 44904301044. AIL, EBS et IWB sont des transformations d’archives ; cinq validations ont utilisé leur méthode d’acquisition. Trois jobs ont échoué. Les reçus de chaque artefact figurent dans docs/v9-rebuild/evidence/restoration-20261121/direct-receipts. Registre à 53 transferts vérifiés sur 135. Electroverse : le nouveau journal de fenêtre restaure les 128 shards et le curseur après interruption pendant une écriture ; 29 tests Python et deux tests Node passent. Le run 44902743843 a démarré avant cette protection supplémentaire. Le candidat local en préparation 96bfbdaf incorpore le snapshot Production issu d’IONITY ; aucun contrôle distant de ce candidat à cette étape.

## Import GitHub vers un snapshot Production isolé

Le 21 novembre, le workflow permanent IONITY a acquis quatre pays. La PR Data Lab 342 relie le workflow Production épinglé fd9adbe à la collecte, en lecture seule. La réexécution 44903986822 importe la collecte 44902592666 sans seconde acquisition. Les dix fichiers du snapshot GitHub 14707341515 sont identiques octet par octet à l’import local indépendant ; l’entrée corrompue est refusée sans sortie. Le premier déclenchement programmé demeure à observer. Le registre compte 45 transmissions prouvées sur 135. La recette du brouillon 6b0189a1 utilise toujours c49ade5f. Prochaine opération : valider le candidat incorporant le renouvellement IONITY, vérifier le run Electroverse 44902743843 et les transmissions suisses séparément.

## 21 novembre — 19 transmissions Direct supplémentaires vérifiées sur GitHub (11 règles officielles et 8 sources régionales). Sept jobs ont échoué. Les deux matrices et les SHA par source sont conservés dans docs/v9-rebuild/evidence/restoration-20261121/families-*.json. Une règle opérateur nécessite toujours une portée PDC prouvée avant affichage. La collecte manuelle permanente IONITY 44902592666 a produit quatre sources importées dans le bundle da9ad190. Le déclenchement cron reste à observer. Reprise Electroverse 44902743843 démarrée avec le checkpoint du 14 novembre. Vérifier son artefact avant tout transfert national.

Le brouillon Netlify 6b0189a12171bc09025b975d sert le bundle groupé c49ade5f. Contrôles distants réussis sur les 3 242 fragments, 24 parcours tarifaires Firefox, 11 recherches, neuf pays et mobile. Le rollback précédent reste accessible. Preuves Production b356916. Le nouveau renouvellement IONITY et les règles Direct du 21 ne sont pas inclus dans ce brouillon. G2–G8 ouverts. Prochaine opération : prouver l’import automatisé isolé à partir du run IONITY existant, puis traiter le checkpoint Electroverse et les motifs des sept échecs.

## 21 novembre — checkpoint Electroverse récupéré et premier calendrier installé

L’artefact 14116783407 du run 43599593600 est sauvegardé. Son ZIP, ses 136 fichiers et ses 128 shards passent les contrôles. Le timeout de 40 minutes laisse 6 000 identités en attente au premier offset et aucun chunk achevé. La reprise utilise ce checkpoint exact. Le collecteur sauvegarde désormais les fenêtres terminées dans le chunk historique. 14 tests locaux passent, dont une interruption suivie de reprise sans répéter les fenêtres terminées. Preuves dans docs/v9-rebuild/evidence/restoration-20261121.

L’ancien pilote était resté actif durant l’interruption. Arrêt effectué et vérifié. La PR 341 installe le seul workflow permanent IONITY sur main Data Lab, code épinglé, lecture seule, sans secret ni écriture croisée. La désactivation et la restauration du seul workflow ont été testées. Le déclenchement manuel 44902592666 et le premier déclenchement programmé doivent être vérifiés séparément. Le mandat du 21 novembre autorise le maintien des workflows V9 éprouvés. G2–G8 restent ouverts. Registre recompté à 26 transferts vérifiés sur 135. Vérifier la reprise réelle Electroverse et le nouveau brouillon groupé c49ade5f avant promotion.

## 14 novembre - integrite des reponses et dependance statuts Electroverse corrigees localement

Le collecteur historique pouvait exploiter un objet partiel GraphQL/HTTP ; ajout de gardes techniques sans changer les requetes, prix ni frequences : reponse 2xx, identite exacte, listes imbriquees, pagination sans cycle/doublon. Deux tests Node dont execution du vrai collecteur sur reponses locales montrent le refus et la conservation du last-good/des reponses independantes. 41 tests Python PASS : reprise/timeout et selection du cache tarifaire pour les statuts. Le workflow commun exige ce cache independant ; un checkpoint d'une autre generation est archive sans fusion. Ces gardes additionnels restent NOT TESTED sur fournisseur/GitHub ; ne pas les attribuer au run en cours.

Run 43599593600/087afd631 en cours de renouvellement complet par chunks ; son controleur hors checkout referme Actions. Ne pas relancer ni remplacer ce run. Aucune modification du brouillon distant ou de main. Apres fin : verifier controle ferme, resultat/ZIP/SHA/manifestes, preserver tout checkpoint partiel et traiter les erreurs avant transfert national.

## 14 novembre — pilote cache tarifaire Electroverse préparé

Cache complet renouvelé par les chunks historiques de6000, strictement séquentiels, mêmes scripts/API/temporisations et128shards. Chaque frontière réussie peut reprendre ; une erreur/timeout conserve un manifeste de checkpoint lié au run/branche/SHA et arrête les appels. Aucun état partiel accepté par Production.8 tests helper/transfert PASS ;29tests timeout/inventaire précédents conservés. Mainc7204b3ef et1207blobs d’archives vérifiés, zéro déclencheur actif. Actions encore désactivé à la préparation. Driver horscheckout resume-20261114/electroverse-tariff-renewal/run-pilot.py fermeActions dansfinally.

Ne pas renouveler les16partitions sur un ancien cache qui sera invalidé. Aucun succès fournisseur/artefact revendiqué avant exécution. Candidat localc49ade5fvalidé/Production531127c ; brouillon distantb87a89b7inchangé. G2–G8FAIL,26handoffsprouvés/109ouverts.

## 14 novembre — reprise sécurisée après timeout et candidat groupé validé localement

Le runner de collecte arrête le groupe de processus avant de vérifier les checkpoints. Les checkpoints techniquement valides survivent au timeout et sont repris ; aucun état incomplet n’est promu. 18 tests d’orchestrateur PASS, dont arrêt réel d’un descendant et reprise simulée de partition ; cette nouvelle branche timeout n’est pas encore éprouvée sur GitHub. Garde nominatif Evyve : aucun nouvel appel ni accès au last-good tant que le périmètre fournisseur n’est pas corrigé (5 tests PASS).

Candidat groupé c49ade5f : 24 parcours tarifaires Firefox, 11 recherches/neuf pays, contrôles G9/mobile, hébergement et scan différentiel PASS localement. Le correctif Production conserve les métadonnées des deux offres lors d’une fusion exactement équivalente, sans changement de prix/portée. Le brouillon distant reste 6af855c4/b87a89b7, intact et vérifié ; le nouveau candidat n’est pas déployé. Preuves Production docs/v9-rebuild/evidence/restoration-20261114/grouped-local.

26 handoffs complets prouvés, 109 ouverts ; G2–G8 FAIL. Inventaire Electroverse daily sécurisé : tuiles échouées/reportées et compteurs internes incohérents bloquent la promotion ; reprise testée,29 tests ciblés PASS. Prochaine opération : renouveler le cache tarifaire par chunks historiques avant toute reconstruction des 16 partitions de statuts ; tester le runner corrigé dans le pilote borné, sans activation permanente. Préserver les bundles/paquets de rollback.

## 14 novembre — Fastned / EnergyVision transmis ; Evyve bloqué par le périmètre fournisseur

Run43597937731 globalFAIL : jobsFastnedFR/GB etEnergyVisionBE réussis, ZIP/manifeste/SHA/contrats réellement vérifiés.26handoffs prouvés et109ouverts ; aucun de ces deux artefacts n’est encore normalisé/importé/servi. EnergyVision reste explicitement non publiable en prix selon son contrat. Actions fermé, zéroworkflow actif,main inchangé.

Evyve échoue sur le garde de périmètre du collecteur (ligne232) : flux non vide sans opérateurEvyve. Ce blocage fournisseur était déjà documenté en octobre ; les noms d’opérateur de cette nouvelle réponse ne sont pas conservés. Aucun nouvel essai avant confirmation de périmètre corrigé, aucun fauxsite/prix ni déclassementN/A. Exception nominative evyve-scope-block.json. Correction du budget partagé28requêtes et tests de garde conservés.

Candidat local groupé en préparation : bundlec49ade5f, seules OZECAR/IZIVIA/SourceEV changent parmi33sources. Chemin site-grouped-renewed-20261114 ; préparation et recette via resume-20261114/grouped-checkpoint-renewal. Production corrige une perte de provenance lors de fusion d’offres exactement équivalentes, trois suites de portée/classement PASS ; correction pas encore servie. Nouveau test navigateur distingue SourceEV AC prouvé etDC hors preuve. Brouillon distant vérifié6af855c4 inchangé. G2–G8 FAILglobal.

## 14 novembre — familles indépendantes préparées, aucun succès anticipé

Fastned FR/GB, EnergyVision BE et Evyve UK réutilisent leurs méthodes historiques avec dépendances et secrets limités par job. Evyve partage désormais le budget28requêtes entre locations,tarifs et retries (même correction technique que Blink) ; test du dernier appel et429 PASS, aucune modification de prix/pagination.8tests de modules PASS ; validateur de transfert étendu aux trois contrats. EnergyVision reste non tarifable selon sa preuve historique ; un transfert réussi ne changera pas cette restriction. Contrôleur shared-public-renewal/run-pilot.py borné et réversible ; préparation seulement.

## 14 novembre — transmission et reprise réelles Electroverse vérifiées

Run43597034709 / HEADe59d01692 : deux jobs réussis.30réponses conservées après transfert GitHub puis30autres acquises ; manifeste/150fichiers/SHA des deux ZIP vérifiés localement, même fenêtre d’observation, aucun changement des partitions indépendantes. Les128shards et le mapping restent conservés. Preuve electroverse-status-checkpoint-handoff.json. Ce PASS concerne exclusivement un checkpoint partiel et sa reprise :0/16collecte nationale complète, aucune publication de statut ou tarif, FR:electroverse_status reste non vérifié pour la finalisation.24handoffs complets prouvés et111ouverts ; G2–G8 restent FAIL. Actions fermé/zéro workflow actif/main inchangé.

Workflow commun : les secrets ne sont désormais injectés que dans les modules qui les déclarent ; aliasREVE et bootstrapAtlante inchangés, credentialscheckout non persistés. Deux tests de portée des secrets PASS ; aucun déploiement ou cadence activés. SourceEV renouvelé :336offres hors preuve conservées brutes,14offres AC historiques reproduisent5.40GBP/10kWh dans le moteur empaqueté. Ce nouvel import reste séparé du brouillon FR/UK vérifié.

Suite : poursuivre les familles indépendantes dans des pilotes bornés ; préparer un candidat regroupé avec OZECAR, IZIVIA et SourceEV renouvelés. Ne pas réutiliser un statut partiel comme preuve nationale. Le checkpoint complet téléchargeable du run43597034709 est conservé horscheckout pour une future continuation respectant16h de fraîcheur et la cadence historique sans paralléliser les requêtes Electroverse.

## 14 novembre — essai réel de reprise Electroverse préparé

Pilote borné :30locations maximum par passage, deux passages successifs sur le même checkpoint,16partitions et128shards historiques conservés. Premier job collecte un état partiel ; second job télécharge son artefact du même run, vérifie le SHA du manifeste, tous les fichiers, branche/HEAD/source et reprend sans perdre les réponses réussies ni modifier les partitions indépendantes. Aucun snapshot national ni prix nouveau promu. Script scripts/pilot_v9_status_checkpoint.py et tests de corruption/provenance/perte de données ajoutés. Résultat réel encore NON VÉRIFIÉ ; FR:electroverse_status reste non vérifié dans G2. Contrôleur resume-20261114/electroverse-status-resume/run-pilot.py fermera Actions après le seul run.

## 14 novembre — Source EV renouvelé sans prix inventé ; brouillon FR/UK vérifié

Run43596509114 / HEADd57d8be10 réussi, artefact14115145865 vérifié puis normalisé/importé en espace isolé (c0bfe484).350offres conservées avec portée exacte ; les composantes ne correspondant plus à la preuve PAYG historique restent brutes, incalculables, hors classement. Aucun montant renouvelé n’est approuvé par le seul succès de collecte. Les données ne sont pas encore servies. OZECAR également normalisé/importé (a39894e9),269EVSE/465offres brutes ; mêmes réserves de portée et calcul. Compteurs informatifs uniquement.24handoffs prouvés,111ouverts. Actions fermé, zéro workflow actif/main inchangé.

Brouillon https://6af855c43ab7f937570c2a74--tcc-v9-preproduction-20261028.netlify.app désormais vérifié réellement :3241fragments SHA et fichiers critiques intégraux, HTTPS/noindex,23parcours tarifaires et11recherches/neufpays,contrôlesG9/mobilePASS. Bundleb87a89b7 ; preuves Production5f28eba. Rollback6af8470a conservé/vérifié,public inchangé. G2–G8 restent FAIL globalement, cadence et latence dense non validées.

Prochaine opération : éprouver la transmission et la reprise réelles des checkpoints Electroverse dans une fenêtre bornée, sans promouvoir un état national partiel ; poursuivre les familles indépendantes et regrouper les acquisitions validées avant un prochain candidat global. Ne pas répéter les recettes inchangées.

## 14 novembre — OZECAR renouvelé ; reprise Source EV bornée

Run43595900013 / HEAD01b8864a : acquisition OZECAR réussie sur Ubuntu24.04, artefact14114561544 vérifié par ZIP, manifeste, SHA et contrat. Actions fermé, aucun workflow actif, main inchangé.23handoffs prouvés et112ouverts ; normalisation/import OZECAR restant à vérifier, pas encore servi. Le changement de runner corrige le défaut technique sans modifier le collecteur. Preuves ozecar-handoff.json / ozecar-control.json et YAML archivé.

Source EV seul préparé pour reprendre après12:46UTC, budget horaire historique respecté. Les sorties non couvertes par la preuve tarifaire sont conservées brutes hors classement ; aucun nouveau prix approuvé. Contrôleur source-ev-ozecar-retry/run-retry-pilot.py referme Actions dans finally. Brouillon6af855c4 : parcours distants PASS, intégrité exhaustive encore en cours. G2–G8 FAIL globalement.

## 14 novembre — IZIVIA transmis ; runner OZECAR corrigé avant reprise

Run43594993525 globalFAIL : IZIVIA FAST réussi, artefact14114325677 et import isolé3c517e8a vérifiés.22handoffs prouvés,113ouverts. Les616groupes station restent bruts, zéro EVSE inventé ni prix propagé ; pas encore servi. OZECAR n’a effectué aucun appel fournisseur : Playwright1.55.0 refuse Ubuntu26.04 installé par ubuntu-latest. Workflow commun épinglé Ubuntu24.04 ; nouvel essai OZECAR seul préparé, même méthode et dépendance.16tests locaux préservés, résultat réel du runner encore en attente.

Actions refermé après le run. Nouveau brouillon FR/UK6af855c43ab7f937570c2a74 prêt côté Netlify, recette distante en cours : ne pas annoncer sa validation. Bundleb87a89b7,928profils FR renouvelés reproduits entièrement par l’oracle ; preuves sousfr-direct-renewal. Source EV attend toujours12:46UTC avant essai corrigé. G2–G8 restent FAIL globalement.

## 14 novembre — pilote borné OZECAR / IZIVIA FAST préparé

Méthodes historiques et dépendance Playwright1.55.0 du workflow commun conservées. Tests adaptateurs, erreurs et intégrité dans resume-20261114/fr-public-renewal/tests.log. Préflight main c7204b3ef,1207archives exactes et zéro YAML actif. Aucun renouvellement revendiqué avant reçu distant. Driver run-fr-pilot.py referme Actions dans finally. Ces acquisitions ne changent ni portée nationale ni règle de prix ; les preuves historiques insuffisantes restent brutes. Candidat FR/UK en recette indépendante.

## 14 novembre — renouvellement Zephyre / Ze-Watt vérifié, alimentation nationale exacte

Pilote 43594190154 / HEAD f8c14d4e2 : deux acquisitions réussies, ZIP, manifestes, SHA et contrats vérifiés après fermeture. Actions désactivé, zéro workflow actif, main c7204b3ef inchangé. 21 transferts prouvés, 114 encore ouverts ; G2–G8 restent FAIL globalement.

Les compilateurs historiques sont rejoués hors checkout sur chaque artefact renouvelé, avec égalité des sorties hors horodatage de compilation. Six tests incluant altération de tarif et refus d’exécuter du code d’artefact PASS. Canonique Direct 2ba80dfc7d0a33d2e9d7a7f314842c21c9b2a1f4cbff1fd698c7de59045ea85c : 928 offres exactement attribuées à l’IRVE, 11 identités absentes conservées dans le rapport de rejet, aucun site CPO ajouté. Compteurs diagnostiques uniquement. Preuves docs/v9-rebuild/evidence/restoration-20261114/fr-direct-* et reçus nominatifs.

Candidat UK 8fd3c1b2 : 23 parcours Firefox, 11 recherches ordinaires/neuf pays, G9 ordinateur/mobile, pagination20/+20 et hébergement PASS localement. Runtime exact d97e420. Pas encore déployé. Regroupement des nouvelles acquisitions FR/UK en cours dans resume-20261114/fr-direct-renewal ; préserver les derniers Netlify et bundles.

Prochaine opération : terminer build/prepare/validate-candidate.py de ce dossier, vérifier import Production et recette distante globale si conforme. Source EV corrigé doit attendre12:46UTC pour un nouvel essai borné ; Ubitricity UK reste attente fournisseur, REVE utiliseMAPA_REVE_API_KEY et Atlante le bootstrap historique sans secret utilisateur. Latence Amsterdam toujours ouverte.

## 14 novembre — renouvellement Direct France borné préparé

Zephyre/Ze-Watt : collecteurs et compilateurs historiques exacts, quatre requêtes concurrentes, sans secret ni nouvelle investigation.10tests de méthode/transfertPASS. Pilote commun deuxjobs,mainneutraliséet1207archivesrestaurablesrecontrôlés,Actionsdésactivéàlapréparation. Driver resume-20261114/fr-direct-renewal/run-fr-pilot.py fermeActionsdansfinally. Aucun succès revendiquéavantreçus. GB33bundleenrecettelocaleindépendante, pasdenouveauNetlifyparsource.

## 14 novembre — Blink/GRIDSERVE renouvelés ; raccordement tarifaire GRIDSERVE corrigé

Run43592866220, HEAD0e00cf0be : deux jobs réussis, ZIP/manifestes/SHA/contrats vérifiés réellement après fermeture Actions.19handoffs prouvés,116ouverts. Ancien dispositif toujours neutralisé,maininchangé,aucunworkflowactif. Le quota Blink est partagé entre endpoints et reprises.

Défaut démontré GRIDSERVE : la normalisation utilisait la paire brute sans rejouer le constructeur historique d’accès public. Elle réutilise désormais uk_gridserve_v9_prepare.build, conserve le brut par SHA, exclut les dépôts/tests/nonpublics et garde les références exactes.23tests ciblés PASS. Production raccorde les seuls éléments ENERGY OCPI sans restriction avec TVA20explicitement fournie, identités exactes et puissance connue ; oracle indépendant, loader et tests de mutation PASS.2580offres réellement acquises calculées, cinq offres d’un garage exclues selon la règle existante. Aucun frais inconnu/minimum/condition n’est ignoré. Blink etAllegoUK restentbruts : puissanceabsente,aucuneinvention.

Bundle33isolé8fd3c1b20b838d34968faa9d422de33991b3ef0d693aa7d0ecd50fd55c6aa89e : seules AllegoUK/Blink/GRIDSERVE changent,30sources inchangées. Préparation site-uk-renewed-20261114 et recette locale en cours ; pas encore déployé. Candidat distant6af8470a conservé intégralement. G2–G8 FAILglobal ; latenceAmsterdam nonrésolue.

Prochaine opération : terminer préparation/recette UK, poursuivre les renouvellements FR Zephyre/Ze-Watt préservés dans un pilote borné, puis regrouper les résultats vérifiés avant nouveau brouillon. Source EV corrigé surfixtures, retrylive pas avant12:46UTC ; nepasreprendre sonacquisition avantquota.

## 14 novembre — préparation bornée Blink et GRIDSERVE

Allego UK vérifié et Source EV isolé dans80578636f. Deux prochains jobs indépendants Blink/GRIDSERVE : secrets existants par nom, mêmes endpoints/méthodes historiques ; aucun renouvellement encore revendiqué. Quota Blink corrigé en budget commun28appels (locations+tariffs+retries), au lieu de deux budgets séparés.14tests adaptateurs/transfert PASS. Préflight mainc7204b3ef restaurable1207archives,aucunYAMLactif. Driver horscheckout resume-20261114/uk-open-renewal/run-uk-pilot.py ; activer uniquement le workflow temporaire après vérification, fermer immédiatement après le run.

Actions encore désactivé à cette entrée ; G2FAIL118handoffs non vérifiés. Source EV ne doit pas être rejoué avant12:46UTC après sa fenêtre précédente, etaucunjetonUbitricityUKàredemander. Aucun déploiement Netlify à ce lot.

## 14 novembre — Allego UK transmis, Source EV isolé sans inventer de prix

Run43591511750 : Allego UK réussi, reçu SHA/manifeste/fichiers vérifié ; Source EV échoué sur la ligne54 de l’audit historique (écart à la référence PAYG), pas un secret manquant. Actions refermé, zéro workflow actif, main inchangé.17handoffs prouvés,118ouverts ; G2–G8 restent FAIL. Le brut de l’échec n’était pas conservé, donc aucun nouveau montant fournisseur n’est déclaré connu/valide.

Correction commune : les offres Source EV non démontrées sont gardées brutes avec motif et références exactes ; la normalisation PCPR accepte désormais des prises non tarifables sans rejeter tout leur catalogue. Aucun tarif hors preuve n’entre dans le moteur ; audit historique conservé intact. Les sorties PCPR échouées sont mises en quarantaine hors objets/last-good.41tests ciblés PASS ; test moteur Production des offres retenues/incalculables PASS. Le nouvel essai Source EV reste à faire après expiration du quota horaire de l’exécution11:45UTC (pas avant12:46UTC), sans appeler le fournisseur pour rechercher un prix.

Allego UK réellement normalisé/importé en espace isolé : bundle b6ea9d13f160eaaf4abdd7a7ec4b151e588c5073e18ad1bc36bce3528aeced0e ; jamais encore servi dans le brouillon courant. Les variations d’identités/offres sont diagnostiques, aucun seuil de volume.

Le brouillon6af8470ab1f6ac03083a27f4 est maintenant entièrement vérifié à distance :3245fragments SHA, ressources critiques dont11.7Mo,20parcours,11recherches/neufpays etcontrôlesG9mobilePASS. Ancienbrouillonconservé/rollbackvérifié,publicinchangé. Preuves détaillées Production docs/v9-rebuild/evidence/restoration-20261114/national-renewal. Il reste partiel : pas de cadence,118transferts ouverts, latenceAmsterdam66.7s etexceptions fournisseurs.

Prochaine opération : poursuivre les familles PCPR Blink/GRIDSERVE avec secrets existants nommés, préflight sécurisé, pilote borné et fermeture Actions ; vérifier puis importer leurs artefacts. Préserver les brouillons et bundles, regrouper les prochains renouvellements avant tout nouveau déploiement. Ubitricity UK reste attente fournisseur ; REVE utilise MAPA_REVE_API_KEY ; Atlante bootstrap historique déjà prouvé, aucune nouvelle demande d’accès.

## 14 novembre — régression d’isolation Belgique identifiée et corrigée

Run43587027521 échoué et Actions refermé. Les18pages ont été reçues jusqu’au dernier nextOffset=null ; aucune erreurHTTP. L’échec est FileNotFoundError à l’écriture docs/belgium-cpo-progress-2026-09.json : ce dossier existe dans Git mais manquait dans l’espace isolé. Les36fichiers bruts/canoniques reçus sont conservés dans l’artefact d’échec vérifié, sans promotion. Preuves belgium-diagnostic-failure/control.json.

L’orchestrateur crée maintenant le dossier de sortie nécessaire, sans modifier le collecteur ou ses paramètres.16tests orchestration PASS, dont exécution réelle du constructeur historique horscheckout avec réponse locale contrôlée ; l’ancien test simulait directement les fichiers et ne couvrait pas cette erreur. Une vérification distante bornée du chemin normal corrigé est préparée, sourceBEseule ; aucune nouvelle API ni règle tarifaire.

Bundle33 français renouvelé474a18a065b4dde765ef728911bec3db264fd25243e64e9d1e5ad94a598aad1f :32sources inchangées. Préparation des fragments/jointures puis empaquetage en cours via session22245, état national-renewal/pipeline-state.json. Le dernier Netlify vérifié reste6af8365acf7552d1d9e1768a. G2–G8 FAIL globalement,14handoffs prouvés/121ouverts. Prochain : exécuter le piloteBE corrigé, le fermer, vérifier son artefact, puis intégrer seulement les sources valides et continuer la recette.

## 14 novembre — reprise belge en cours, ne pas dupliquer

Fenêtre Actions bornée actuellement active pour le seul run43587027521, HEAD e3667ff377cbb7acc0fae03f2523d8b0945b9d04, sourceBE:nap. Driver/session3371 ; contrôle persistant `.tcc-v9-cache/emsp-restoration-20261105/resume-20261114/national-belgium-retry/national-control.json`. Délai1800s et fermeture enfinally ; vérifier réellement enabledAfter=false avant tout autre pilote ou interruption. Le premier run43586082154 est clos ; FR vérifié, BE en échec non diagnostiqué. Cette reprise conserve des diagnostics structurés sans secrets et les pages échouées hors last-good.

Canonique français renouvelé PASS : SHA4a034e8a86f951690e4980fbf8c887e66b035d4de482f42c95f1e0323c5ca876 ; sourceRetrievedAt2026-11-14T10:36:59.248119Z conservé depuis manifeste signé. Assemblage du bundle33 remplaçant seulement FR:irve_static en cours, session23649, sortie national-renewal/bundle-france.json. Ne pas reconstruire les32sources inchangées. Prochaineopération : terminer ces deuxprocessus, fermerActions, examiner le diagnosticBE/valider son artefact si succès, préparer/importer le bundle national avec les jointures exactes puis recette locale avant autre déploiement. Le brouillon Atlante6af8365acf7552d1d9e1768a reste vérifié et inchangé.

## 14 novembre — IRVE renouvelé et validé ; Belgique en échec, diagnostic corrigé

Run43586082154 est globalement FAILURE : jobFR:irve_national SUCCESS et artefact réellement vérifié ; jobBE:nap FAILED. Actions de nouveau désactivé, zéro workflow actif, main inchangé. Le reçu français conserve la conclusion globale failure, sans l’effacer.14handoffs vérifiés,121encore ouverts. Dernier snapshot belge conservé.

L’échec belge n’a laissé qu’un code collector_exit_nonzero : le diagnostic était perdu par l’orchestrateur. Correction commune : conservation de la classe d’exception, codes HTTP, frames et compteurs numériques, sans texte libre ni jeton ; pages BE déjà reçues conservées dans failures/unvalidated-output, jamais objects/last-good. Tests :2diagnostics,15orchestration/reprise/last-good PASS. Une seule reprise technique BE est préparée pour obtenir la cause réelle, sans nouvelle méthode ou enquête fournisseur.

Autre perte confirmée : la date sourceRetrievedAt du manifeste IRVE disparaissait dans le canonique. Elle est désormais conservée avec SHA du manifeste, séparément de la date de construction ; si absente, reste absente.4tests normaliseur dont mauvaisSHA/date et identités invariantes +2tests bundles PASS. Canonique FR renouvelé en cours horscheckout, source acquise14novembre10:36UTC. La préproduction6af8365acf7552d1d9e1768a reste inchangée et entièrement vérifiée pour son propre paquet.

Prochaine opération : piloteBE borné sur la branche seulement, driver persistant resume-20261114/national-belgium-retry/run-national-pilot.py, fermerActions puis examiner le diagnostic avant toute autre reprise. Préparer indépendamment l’import du catalogueFR validé ; ne pas promouvoir de sortieBE partielle. G2–G8 restentFAIL globalement.

## 14 novembre — préparation du renouvellement national FR/BE

Candidat Netlify6af8365acf7552d1d9e1768a désormais vérifié :3247fragments signés etressourcescritiquesSHA/HTTPS/noindex,19parcours,11recherchesneufpays,mobile,classementdenseexact ; la latence66.7s resteFAILperformance. Sitepublicinchangé,retourarrière6aed03e7vérifié.

Prochainpiloteborné : FR:irve_national etBE:nap, méthodeshistoriques déjàmigrées, BE utilise le secretexistantBELGIUM_NAP_TOKEN sansconsultationdevaleur. Deuxjobsindépendants,aucunpushautomatique/publication. Préparation pendantActionsdésactivé ; contrôleHEADmain/workflowsavantactivationparledriverpersistant `resume-20261114/national-renewal/run-national-pilot.py`. Délai1800s,fermetureActionsenfinally,preuves `national-control.json`. Àcetteentrée aucuneacquisitionnouvelleencoreréussie. Les122handoffs restentnonvérifiés jusqu’aureçudistant. Ne pasécraserlast-goodsuréchec,nepasréduirepaginationniinventerprixpourpasser.

## 14 novembre — transmissions de constructeurs prouvées, Actions fermé

Run43585513906/8faa6c081 success pour FR:canonical,GB:midhope_verified,BE:final_gap_archive. Les trois ZIP,manifestes,contrats et SHA sont réellement vérifiés après désactivation ;13handoffs prouvés,122restent ouverts. Archives rejouées, pas collectes fraîches. Import Production isolé de la sortie GB PASS ; identités/puissances/offres inchangées, seules dates archivées et empreinte changent (20octobre vs10octobre). Preuves `docs/v9-rebuild/evidence/restoration-20261114/`. Workflow temporaire archivé, mainc7204b3ef inchangé,enabled=false,zéro workflow actif. G2 FAIL :122handoffs +registrepartiel uniquement.

Brouillon Netlify6af8365acf7552d1d9e1768a :19parcours+11recherches/neufpays+contrôlesG9mobile PASS àdistance. Classement dense64019résultats/montants/carte/pages exactement identiques ancien/nouveau avecFirefox160 ;66.7s àfroid sous vérificationréseauconcurrente, toujoursPASacceptablecommePASSperformance. Contrôle exhaustif nouveau fragments encoreen cours, reçu persistant resume-20261114/atlante-fragment-receipt.jsonl. Prochainchemincritique : finirSHA etpreuvesProduction ; renouveler les cataloguesnationauxFR/BE parméthodesexistantes dansunpilote bornéaprèspréflight,importerseulementlesrésultatsvalides,conserverlast-goodetdatesfournisseur. Aucun nouveauprixenquête ni seuilvolume.

## 14 novembre — nouveau brouillon Atlante et préparation des transmissions d’archives

Brouillon isolé `6af8365acf7552d1d9e1768a` ready, jamais --prod ; bundle33 `0bce189c967136aa3c0a46ad298e6b1be4304c80c8eb8c6ff4abb2d5e080ceb6`.31sources inchangées, seules Atlante FR/IT issues du run42122453243 du5novembre remplacées.19parcours locaux et distants PASS,11recherches locales et contrôlesmobile PASS ; intégrité exhaustive distante et suite G9 distante en cours, aucune promotionG8. Ancien6aed03e7 :3245fragments/manifestes/largeledger/crosswalk vérifiés intégralement le14novembre ; rollback conservé.

Préparation d’un pilote groupé de trois constructeurs historiques (`FR:canonical`, `GB:midhope_verified`, `BE:final_gap_archive`) : aucun fournisseur, secret ni tarif recherché. Sorties isolées, artefacts indépendants, reprise/last-good vérifiés par tests existants. Le vérificateur de transfert connaît ces contrats et distingue explicitement `archived_replay` d’une acquisition fraîche. G2 n’accepte cette exception de fraîcheur que pour ces modules et avec reçu distant vérifié ; elle ne supprime aucun handoff. Préflight main c7204b3ef :1207archives restaurables,aucun workflow actif ;6tests de provenance transfert PASS. À cette entrée Actions est encore désactivé et le pilote n’est PAS exécuté.

Prochaine opération : push de préparation pendant Actions désactivé, pilote borné sur branche reconstruction seulement après contrôle des workflows/permissions/HEAD, fermeture immédiate à fin ; vérifier ZIP/manifestes/contrats avant de consigner un succès. Driver persistant horscheckout `emsp-restoration-20261105/resume-20261114/run-builder-pilot.py`, résultats `builders-control.json`. Continuer parallèlement la recette du brouillon, sans nouveau transfert Netlify. G2–G8 FAIL global,125handoffs ouverts tant que preuves nouvelles absentes. Ubitricity UK demeure attente fournisseur ; REVE checkpoint partiel conservé ; aucune demande de secret Atlante/REVE.

## 14 novembre — reprise des opérations interrompues, aucun pilote relancé

Branches reconstruction alignées avec origin : DataLab bf958eecb, Production1264896 ; modifications locales REVE conservées. Actions enabled=false recontrôlé. Atlante42122453243 est réussi/vérifié ; REVE42123311317 a reçu cinq HTTP200, puis refusé la publication car flux incomplets. Checkpoint exact conservé dans migration/v9/checkpoint-seeds/ES_reve_stream, SHA du ZIP et égalité avec l’artefact vérifiés. Cinq tests de seed/reprise PASS ; G2 FAIL uniquement125handoffs non vérifiés et registre partiel. Ubitricity UK reste attente fournisseur, aucune nouvelle demande de clé Atlante/REVE.

Les fichiers temporaires /private/tmp ont disparu pendant l’interruption. Les archives horscheckout, bundles, sites et preuves versionnées sont intacts. Le résultat final du contrôle intégral6aed03e7 n’était pas sauvegardé : reprise justifiée du contrôle distant, reçu persistant `emsp-restoration-20261105/resume-20261114/previous-fragment-receipt.jsonl`, session40894. Pas de nouveau déploiement à cette entrée.

Le bundle33 avec Atlante FR/IT renouvelé est `0bce189c967136aa3c0a46ad298e6b1be4304c80c8eb8c6ff4abb2d5e080ceb6` ; prepared-atlante-renewed vérifié,31sources inchangées. Empaquetage site-atlante-renewed en cours, sortie persistante resume-20261114/atlante-package.json. Les acquisitions Atlante datent du5novembre, pas du14 ; aucune fraîcheur inventée. Prochaineopération : terminer paquet et scan, recette ciblée Atlante puis intégrée neufpays/G9, nouveau brouillon isolé seulement après succès, SHA/navigateur distants, préserver6aed03e7 etpublic. Aucune promotion G2–G8 globale.

## 5 novembre — Atlante renouvelé réellement, REVE reprise bornée préparée

Run42122453243/HEAD45475b3c8 success ; bootstrap myAtlante historique et collecte FR/IT réels. ZIP93bbc5038e642f5cc0ac00b82c8a68400b86f03c3ada6fc3bd3af11667732a24, contrat/manifeste/fichiers vérifiés après fermeture Actions(enabled=false). Preuves atlante-handoff/control/preflight.10handoffs prouvés,125encore non vérifiés ; aucune clôture globale. Normalisation des deux pays et bundle33 renouvelé en cours session99723 ; aucun nouveau tarif attribué par proximité.

Prochain pilote préparé ES:reve_stream : reprendre exactement les archives partielles au lieu de page1, au maximum5requêtes, respect quota horaire/Retry-After. Une sortie incomplète doit rester en checkpoint et peut donc terminer le job en échec contrôlé, jamais en artefact publiable. Driver `/private/tmp/tcc-emsp-reve.py` à lancer seulement après nouveau préflight, état `renewal-reve/control.json`.4tests de reprise et archive réelle PASS. Aucun appel REVE encore réalisé à cette entrée.

Brouillon6aed03e7c375ce290aaa79a9 :19parcours,11recherches/neufpays, contrôlesG9/SOC/mobile et équivalence dense PASS ;64 019résultats,56.4s dense sous lecturesréseau concurrentes, pas de PASS performance. Intégrité exhaustive encore en cours session29712. Prochaineopération : vérifier REVE borné, finir preuveNetlify ; préparer l’import des seuls Atlante renouvelés en conservant31autressources, puis recette pertinente. G2–G8 toujoursFAIL globalement.

## 5 novembre — brouillon corrigé distant, pilote Atlante en cours

Production1264896 ; nouveau brouillon6aed03e7c375ce290aaa79a9 ready/deploy-preview, paquet `site-served-manifest-final`, bundle8ad8e081 inchangé.19parcours distants,11recherches/neufpays avec parité exacte local/distant à heure fixe, contrôles G9/SOC manquant/mobile PASS ; rollback/public inchangés. Contrôle intégral3245fragments en cours session29712, reçu `/private/tmp/tcc-emsp-final-fragment-receipt.jsonl`; ne pas déployer de nouveau ni annoncer intégrité complète avant résultat. Dense distant en cours, limiteperformance toujours ouverte.

**Pilote Atlante actif** : run42122453243 sur DataLab45475b3c8, driver session83782 ; état `.tcc-v9-cache/emsp-restoration-20261105/renewal-atlante/control.json`. Bootstrap historique a réellement réussi sans secret utilisateur ; collecte en cours, non déclarée validée. Driver ferme Actions après essai. Ne pas pousser de nouvelle requête pendant cette fenêtre.

Correction REVE locale non committée : initialisation du checkpoint depuis les quatre fichiers historiques seulement en absence d’un checkpoint runtime ; SHA/cursors/quota conservés.4tests PASS dont archive réelle sans réseau. REVE doit encore être vérifié réellement avec MAPA_REVE_API_KEY ; cinq requêtes maximum par heure, état partiel jamais promu. Ubitricity UK toujours attente fournisseur. Prochaineopération : terminer pilote, fermerActions, vérifier artefact Atlante et normaliser/importer si réussi ; vérifier la reprise bornée REVE ensuite. ConserverpreuvesNetlify etjournal, G2–G8 globalementFAIL.

## 5 novembre — correction des préconditions Atlante/REVE, pilote borné préparé

Retour utilisateur enregistré : REVE utilise déjà MAPA_REVE_API_KEY via son alias runtime ; aucune clé nouvelle à demander. Atlante réutilise le bootstrap historique myAtlante4519 épinglé par SHA ; correction du workflow qui écrasait la valeur générée par un secret vide, et extension aux deux modules Atlante concernés. Ubitricity UK reste bloqué par absence de réponse fournisseur, last-good conservé. Tests de routage hors ligne PASS ; réussite de collecte Atlante non encore démontrée. Dossier `credential-resolution.json` remplace l’interprétation erronée des seuls noms de secrets.

Pilote FR:atlante_fr_it préparé, lecture seule, un run30min, activation temporaire uniquement après main archivé vérifié et zéro autre workflow actif/file. Driver `/private/tmp/tcc-emsp-atlante.py`, contrôle `.tcc-v9-cache/emsp-restoration-20261105/renewal-atlante/control.json`; fermeture Actions obligatoire après essai. Aucun nouveau pilote déjà exécuté à cette entrée. Paquet final préparé `site-served-manifest-final`, même bundle8ad8e081, garde SOC inconnue testée et manifeste des4503fichiers servis vérifié, ancien manifeste conservé en provenance.19parcours/11recherches/contrôlesmobile et équivalence dense PASS local ; pas encore de nouveau déploiement. G2–G8 globalement FAIL,126handoffs non vérifiés.

Prochaine opération : terminer préflight et scan, committer puis pilote borné Atlante ; fermer Actions et vérifier artefact si succès. Déployer ensuite seulement le nouveau paquet autonome et vérifier intégralement sa nouvelle URL ; ne pas confondre un renouvellement Atlante avec les archives servies tant que son import n’est pas démontré.

## 5 novembre — premier brouillon33 vérifié ; garde SOC et empaquetage corrigés

Brouillon `6aecf99e6ec824559152b1aa` : intégrité distante PASS,3245fragments signés, ledger/crosswalk complets,19parcours,11recherches/neufpays àheure fixe identiques local/distant, contrôles G9/mobile et rollback/public PASS. Problème réseau Netlify temporaire résolu sans redéploiement ; reçus parfragment maintenant reprenables seulement sur mêmeURL immuable+bundle+index. Preuves Production `evidence/emsp-restoration-20261105/FINAL_CANDIDATE.md` et JSON associés.

Défaut transversal supplémentaire réellement reproduit : SOC null traité en0 par Number(null), fabriquant0ou64kWh. Production13c869f corrige le planificateur/modèle, refuse SOC vide au formulaire et teste les entrées inconnues.108scénarios renseignés identiques,5classements et64Midhope PASS. L'empaquetage recopie désormais ces deux modules explicitement (ils seraient sinon hérités de l'ancien paquet). `site-input-presence-guard` intermédiaire NON DÉPLOYABLE ; préparation corrigée `site-input-presence-final` en cours session45213, bundle8ad8e081 identique.

Prochaine opération exacte : vérifier les3fichiers charge/planner/bridge du paquet contre Production13c869f, comparer tous les fichiers àsite-renewal-complete (données inchangées), scanner différences ; recette locale19parcours+11recherches+contrôlesG9 enrichis+équivalence dense. Seulement alors nouveau brouillon distinct et contrôles distants complets avec reçuparfragment. Ne pas redéployer6aecf99e ni toucherpublic. Actionsdésactivé,126handoffs encore nonvérifiés ; accès fournisseur manquants demandés sans valeurs dans le chat. G2–G8 restentFAIL globalement.

## 5 novembre — préproduction33 enrichie, recette distante en cours

Nouveau brouillon immuable `6aecf99e6ec824559152b1aa`, bundle `8ad8e0811e8ae0ecdb879affc1a38e0fa299f1b4d93c33c2ae920fa745941fc2`, paquet horscheckout `emsp-restoration-20261105/site-renewal-complete`. Restauration eMSP/Direct +renouvellement Electra/DOT-NL ; anciennes URL et sources conservées. Productione11f562, CI42117804692 success.19parcours distants,11recherches/neufpays, contrôles G9/mobile, rollback/public PASS. Àheure fixe,classements/montants/marqueurs des11recherches identiques local/distant. Contrôle SHA exhaustif encore en cours après interruption réseau Netlify temporaire : reprise2workers, reçu parfragment lié àURL+bundle+SHAindex, aucune validation fictive. Session9425 ; `/private/tmp/tcc-emsp-fragment-receipt.jsonl`, `tcc-emsp-remote-integrity.json`. Ne pas redéployer.

Actions désactivé.9handoffs réellement prouvés,126non vérifiés (anciencompteur incomplet corrigé). G2–G8 restent FAIL globalement ; aucune cadence quotidienne généralisée. Accès nommés GitHub manquants pour Atlante/REVE/UbitricityUK documentés, valeurs jamais consultées. Archives suisses/UK/Electroverse ne sont pas présentées comme collectes fraîches. Amsterdam100km reste lente ; aucune donnée retirée. Prochaineopération : finir SHA àpartir du reçu, contrôle dense distant aux mêmes entrées renouvelées, enregistrer résultats et poursuivre la chaîne restante sans retester les acquisitions déjàprouvées.

## 5 novembre 20:25 UTC — Belib national restauré, collecte contrôlée en cours

Les deux identifiants Belib local/itinérance sont préservés ; 1 754 EVSE ont une cible nationale exacte. Les 16 parcours Firefox du candidat `site-belib-identity` passent, dont Belib réellement tarifé. Bundle `aa6c9ea41bb1340f3f313ba742d64e4406e6374edb6fa4b5aff557612fb72cc0`, aucun nouveau déploiement. Un rapport de jointures49Mo nécessite transport gzip avec SHA compressé/original ; correction Production testée, aucune donnée retirée.

Run borné42101119558 toujours en cours (Electra/Suisse) au SHAfc06c7f02 ; **contrôler sa fermeture et enabled=false avant toute fin de session**. Driver et prochaine opération dans `V9_REBUILD_PROGRESS.md`. 115 handoffs non vérifiés à ce point, G2–G8 FAIL. Main/Productionpublique/Updater/Stable intacts.

## 5 novembre — restauration eMSP, premiers renouvellements et correction du chargeur

Production `295d5fb` et Data Lab `5eef8ea28` sauvegardés. Bundle archivé gardé `5ea2991914043b462505b5b7b40490df37213cc9a469703057582320bed64f8f` : 31 022 offres Electroverse / 95 417 Electra attribuées par identité nationale exacte, jamais par GPS. Oracle complet : 160+5 anciennes offres calculables préservées ; 30 907 Electroverse / 64 435 Electra calculables au scénario fixe, autres explicitement non calculées. 50 offres Electra contradictoires sur 25 EVSE mises en réserve, restrictions source non préservées également ; ces nombres sont diagnostiques.

Le navigateur a trouvé un verrou supplémentaire du chargeur : règles eMSP complètes refusées malgré l’adaptateur correct. Correction Production et test du chargeur signé en cours, faux prix injecté rejeté. Ne pas déployer `site` ni `site-guarded` de ce lot avant nouvel empaquetage avec ce correctif.

Run réel `42089328886` : jobs Belib et Driveco success, ZIP SHA GitHub et fichiers/manifestes/validateurs source PASS. Electra annulé par limite job20min, alors que le module préexistant autorise3000s : aucune nouvelle donnée Electra validée. Actions désactivé après essai. 115 handoffs restent non vérifiés ; succès des deux jobs indépendants enregistré sans prétendre que le run entier a réussi. Bundle renouvelé Belib/Driveco `ffac88c083736457df45c7105a7e9a8f725f7cbb787f90ca057b5e4302f67b3a`, préparation en cours ; Driveco conserve ses frais OSF non interprétés et ne devient pas artificiellement calculable.

Suite : achever paquet renouvelé et correction du chargeur, relancer les recherches ordinaires/neuf pays et parcours tarifaires ; retenter uniquement Electra dans une fenêtre bornée60min cohérente avec le timeout du module, puis désactiver Actions. Aucun main/site public/Updater/Stable modifié. G2–G8 FAIL global ; dernier Netlify inchangé.

## 5 novembre 2026 — second brouillon de recette G9

Un brouillon Netlify isolé `6aec9f2fb223d58706efe5b5` a été déployé sans `--prod`. Le contrôle SHA de 2 521 fragments et du crosswalk 11,7 Mo, dix tarifs, onze recherches ordinaires et neuf pays/mobile passent sur l’URL distante. Les quatre demandes suivantes sont préparées sans changement de code. Le site public, l’ancien brouillon et Actions restent inchangés. Voir `memory/V9_REBUILD_PROGRESS.md`.

## 28 October 2026 — Bump exact rules connected in code

Data Lab preserves the archived Bump source and exact national EVSE join; Production `1130c26` evaluates only the historically compiled rules on that exact identity. Targeted historical fee and merge oracles pass. The 30-source preview is unchanged; G2–G8 remain FAIL and Actions stays disabled. See [reprise](V9_REBUILD_PROGRESS.md).

## 28 October 2026 — archived Bump exact EVSE candidate

A frozen Bump source and its previously compiled offers now have a canonical normalizer and a national join restricted to equal official EVSE IDs and operator BUMP. Thirteen targeted tests pass; 1,353 exact Direct offers remain raw and unranked in the isolated candidate. The 30-source preview is unchanged. G2–G8 remain FAIL, Actions disabled. See [reprise](V9_REBUILD_PROGRESS.md).

## 28 October 2026 — planner preserves missing charge energy

Production `26a353e` retains unknown energy through station planning. Source, global ranking, 30-source bundle integrity and nine-country/mobile Firefox pass; Amsterdam 100 km keeps 62,770 matching stations and identical ranking/map/evaluation hashes. G2–G8 remain FAIL, Actions disabled, remote preview unverified. See [reprise](V9_REBUILD_PROGRESS.md).

## 2026-10-26 — IZIVIA FAST archived map topology

A new canonical route preserves the pinned IZIVIA FAST map at exact national station identity while retaining socket groups only as raw source fields. No tariff or official EVSE is assigned from the map. Production has an exact-station merge regression protecting the national EVSE topology. The source remains a candidate until the full bundle and browser replay finish; details are in `memory/V9_REBUILD_PROGRESS.md`.

## 2026-10-26 — V9 performance and map decision, pilot preparation

The user limited search radius to 100 km and required progressive access to all matching stations, independent map grouping, preservation of canonical data and measured Firefox performance. The reconstruction branches contain a local bounded-page implementation and a safe GitHub Actions pilot plan; no activation, main change or public deployment occurred. Evidence and remaining gaps: `memory/V9_REBUILD_PROGRESS.md`.

- 2026-10-20 : migration G2 de trois sources UK PCPR (Blink, Allego UK, Source EV) et de leurs audits ; flux vides visibles sans prix inventé, mauvaise identité CPO rejetée.
- 2026-10-20 : migration G2 du constructeur canonique France dans un espace isolé ; entrées archivées et règles de priorité conservées, divergence du snapshot ancien identifiée sans réinterprétation de prix.
- 2026-10-20 : migration G2 de la chaîne France IRVE statique/dynamique/audit ; retrait des minima historiques de lignes, stations et EVSE ; validations SHA, schémas et relations conservées.
- 2026-10-20 : migration G2 e-Totem inventaire et règles officielles ; retrait du seuil d'identifiants de réseaux, préservation des contrôles techniques et des canaux distincts.
- 2026-10-20 : migration G2 des règles officielles Allego/Fastned/IONITY/Atlante, du rafraîchissement FX et du catalogue SuC Tracker isolés ; retrait du seul seuil de baisse de stations SuC. Tests locaux PASS ; G2 reste FAIL, aucun déploiement.
# 18 octobre 2026 06:42 UTC — #333 : cinq workflows corrigés vérifiés, Electroverse en cours

- **Code fusionné** : [#334](https://github.com/yass3705/tesla-charge-companion-data-lab/pull/334) `cb41b1c` (Atlante, Zephyre, Suisse, IONITY), [#335](https://github.com/yass3705/tesla-charge-companion-data-lab/pull/335) `8a48428` (nouveau cycle REVE), [#336](https://github.com/yass3705/tesla-charge-companion-data-lab/pull/336) `f1f8d5f` (total des lignes REVE), [#337](https://github.com/yass3705/tesla-charge-companion-data-lab/pull/337) `f056c9f` (quota inter-runs, aucun déclencheur push). 21 tests Python ciblés réussis sur main ; compilateur Zephyre sur nouveau snapshot : 16 profils, 133 EVSE exacts. Scan public avant publication réussi.
- **Atlante** : [officiel #39104550167](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/39104550167) et [direct station #39104712486](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/39104712486) réussis. Sortie officielle publiée `a24d4ea` : ChargeBack non confirmé (`evidenceConfirmed=false`, valeurs de crédit nulles), tarifs Go officiels 0,29/0,42/0,49 EUR/kWh séparés du direct sans abonnement. Carte directe vérifiée : 170 stations FRATL, 1 463 connecteurs tarifés, zéro connecteur sans prix. Aucun crédit déduit du tarif de base.
- **IONITY** : [FR/IT/DE #39104550297](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/39104550297) et [UK #39104550292](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/39104550292) réussis, validations et publication réussies (`06c2fdc`, `d6a5cff`). Version fournisseur `v2.500.1` ; FR 181 stations/1 857 UUID connecteurs, IT 43/331, DE 200/1 589, UK 84/878, tous UUID non vides et uniques, zéro connecteur sans prix dans chaque carte. `sourceEvseId` est absent dans les réponses API de ce lot ; aucun EVSE public n'a été inventé. Tarifs Direct restent séparés des offres eMSP.
- **Zephyre** : [run #39104550143](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/39104550143) réussi et snapshot publié `c6d54ed`. 133 stations de détail, 133 EVSE directs exacts, 16 profils ; 141 précédents → 133 actuels acceptés. 371 EVSE IRVE source, 148 coordonnées seed, zéro erreur nearby/détail, 133 tarifs présents et paiements directs. Réponse vide reste bloquante.
- **Suisse** : [bundle #39104550322](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/39104550322) et [intégration #39104623008](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/39104623008) réussis, commits `7c34702` et `b66659e`. Source nationale comparable : 13 659 → 13 529 stations (-0,95 %), 20 273 → 20 137 EVSE (-0,67 %), donc acceptation sans avertissement selon <=5 %. Aucun pin Production ni snapshot public promu.
- **REVE** : [premier run nouveau cycle #39104576137](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/39104576137) réussi ; commit `b024ade`. Pages tarif 1–3/468 : 300 lignes ; statut 1–2/454 : 200 lignes. Chemins `data/spain_reve/full_20261018` isolés, archives historiques intactes. `complete=false`, `PRE_INTEGRATION_ONLY`, aucun snapshot promu. [Run #39104823833](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/39104823833) annulé pendant checkout, avant collecte, pour éviter une seconde requête dans l'heure. Le cron 27 de chaque heure reste ; le prochain cycle avant fin du délai d'une heure doit sauter les requêtes. À chaque fin de flux, vérifier pages contiguës, nombre d'IDs distincts et `total-count` fournisseur. Fin complète probablement après plusieurs jours ; ne pas promettre une date sans quota observé.
- **Electroverse V1** : [run hebdomadaire #39097661647](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/39097661647) encore `chunk1 in_progress` depuis 04:36 UTC à 06:42 UTC ; aucun second dispatch. Audit local du manifeste pré-run existant : 128/128 shards, 22 818 stations égales au mapping, 117 292 connecteurs, zéro ID doublon, shard erroné, manque, extra ou hash invalide. Cela valide la base avant run, **pas** la consolidation du run hebdomadaire. Quatre chunks prévus : 6 000 + 6 000 + 6 000 + 4 818 ; vérifier leurs checkpoints et refaire l'audit après fin. PR #219 et prototype V2 #331 restent ouverts et non intégrés.
- **Reste à faire** : surveiller l'avancement REVE sans doublon ni promotion ; contrôler le prochain run quota, puis la complétude finale des deux flux. Attendre les quatre chunks Electroverse, vérifier échecs par chunk, fraîcheur des 22 818 sélections et manifeste final ; corriger si nécessaire. Ne fermer #333 qu'après ces deux validations. Aucune modification Production, Stable ou Updater Test.

# 18 octobre 2026 — reprise ciblée des six collectes (#333), validation en cours

- Base Data Lab `5cc177afe642ca76fc36f71248f67357ffcb4d85` au début ; issue #333 lue. Les PR Electroverse #219 (filtre) et #331 (prototype V2) restent ouvertes et ne sont pas intégrées.
- Atlante : le contrôle obligatoire ChargeBack 50 % dans `scripts/atlante_official.py` bloquait le workflow officiel #39029951811. L'extraction officielle locale du 18/10 a réussi avec les tarifs directs et abonnement vérifiés, `chargeback.evidenceConfirmed=false`, aucun crédit appliqué au tarif. Le workflow de tarif direct station #39017594363 avait réussi avant correction.
- Zephyre : le workflow #39017974686 échouait ; les gardes de baisse de couverture sont remplacés par des gardes de réponse non vide, cohérence des détails et identifiants EVSE exacts. Compilation locale du snapshot existant : 14 profils et 141 EVSE exacts. La collecte live corrigée reste à exécuter.
- Suisse : le garde compare maintenant source/pays et comptes station/EVSE au dernier bundle validé ; <=5 % accepté, >5 à <=30 % accepté avec `coverageWarning` inclus dans le bundle et rapport, >30 % bloqué avant écriture. Tests exacts 5 % et 30 % réussis. Le run antérieur #39085644947 était en échec ; le nouveau run reste à vérifier.
- IONITY : l'endpoint public `/api/v1/location/static` renvoie 412 pour l'en-tête `x-adhoc-app-feature-version: v2.428.0`, corps `App Feature Version v2.428.0 is not supported anymore! Please update your app.` La fiche Google Play officielle `com.cleevio.ionity.android.app` annonce `v2.500.1` ; avec cette version, le même endpoint renvoie 200 et 902 locations. Hydratation `/api/v3/location/{uuid}` vérifiée avec offres IONITY DIRECT sur FR, IT, DE, GB. Les quatre sorties complètes et workflows restent à valider ; les derniers prix validés sont conservés tant que cela échoue.
- REVE : l'ancien checkpoint 404/270 et les deux stores restent archivés ; le dernier run #39102745041 a échoué au preflight qui exigeait à tort la réussite de la dernière requête. Nouveau cycle isolé `data/spain_reve/full_20261018`, curseurs 1/1, vérification des pages contiguës, identités exactes et délai 429. Le workflow horaire doit reprendre après fusion ; aucun snapshot n'est complet ou promu.
- Electroverse : cron hebdomadaire dimanche 00:17 UTC. Run #39097661647 lancé et encore actif au contrôle du 18/10 06:32 UTC (chunk1), donc aucun dispatch doublon. Manifeste préexistant : 128/128 shards, 22 818 stations ; cela ne valide pas encore le run hebdomadaire ni la consolidation. V1 maintenu, #219/#331 non fusionnées.
- Tests locaux ciblés : 19 tests Python réussis, compilation Zephyre réussie, scan public `scripts/public_safety_check.py .` réussi. Attendre CI, runs réels, validation des sorties et statut du run Electroverse avant de déclarer les données finalisées ou de fermer #333. Aucun changement Production/Stable/Updater, aucune promotion de snapshot.

## 2026-10-15 — Handoff Tesla/Mac publié via ingress public Production

- Après refus HTTP 403 du jeton vers Data Lab (#19), le choix utilisateur a été le relais d'artefact public Production ; la voie GitHub App #21 a été fermée. Updater #20 `3bb96f9d` et contrôle de jeton #38768018372 (tentative 2) établissent l'écriture. Production #118/#119 déposent l'artefact Mac historique exact ; Data Lab #326 l'importe au commit `55e17a89c2bba0800c6d4639653ec8762533f641` (run #38767112592). Les deux catalogues historiques #323/#324 et le test de préservation #328 restent disponibles. Aucun nouveau lot Mac, changement de runner, secret ou tarif.
- Production #117 `4ac2acbd` et #120 `603e933f` publient le nouveau pin via Pages #38768065297 : snapshot `2026-10-15-v9-tesla-mac-ingress-verified`, 2 465 fichiers, catalogue Tesla 1 179 stations / 4 472 574 octets / SHA-256 `363af2e8…`. Stable #151 `04389226` conserve les commandes manuelles de rollback et retire les déclencheurs de transit. Stable Pages #38768670252 a réussi ; site historique HTTP 200 avec catalogue de rollback intact. Issue Data Lab #302 clôturée le 15 octobre 2026 avec le relevé GitHub final.

## 2026-10-15 — Handoff Tesla Mac : source Data Lab préparée, droit inter-dépôts refusé

Data Lab #323 `c800e7d5` et #324 `b7952f95` conservent deux catalogues Mac publics exacts (1 178 puis 1 179 stations), empreintes et provenances. Production #117 ajoute le constructeur épinglé et la validation candidate ; Pages PR #38765178210 réussie sans publication. Updater #19 a vérifié le secret existant sur une branche jetable : HTTP 403 au run #38764852818, sans changement de Data Lab main. Updater #20 reste ouverte et non fusionnée ; Mac/Stable actuels intacts. Le transfert automatique, la publication Production actualisée et le retrait Stable attendent une autorisation inter-dépôts vérifiée.

## 2026-10-15 — Limite vérifiée du handoff Tesla/Mac
- Dans un worktree isolé d'Updater Test `425b4fca`, `src.exporter_global_v6` a été exécuté avec le catalogue Stable public courant (1 179 stations, 11 pays) comme baseline ; arrêt immédiat `RuntimeError: Groupe incomplet: BE-001`. Aucun fichier distant, secret, runner ou workflow Mac modifié, aucun candidat publié. `lot_publish.py` garde Stable comme source/cible et `dispatch_v9_preview.py` épingle son SHA ; dernier lot Mac #37962729987 du 9 octobre réussi. Le transfert du catalogue courant exige un handoff de l'artefact validé après lot, non une reconstruction depuis les seuls groupes versionnés. Verdict global inchangé : migration technique incomplète.

## 2026-10-15 — Déclencheurs Updater Test et watchdog Production
- Updater Test #18 `425b4fca` : 70 anciens `push` non-Tesla retirés, dispatch/archives gardés ; parité CI #38760123825 réussie ; seuls maintenance et contrôles sur PR ont encore des déclencheurs automatiques. Tesla/Mac inchangé.
- Stable #149 `13ea0d0e` : le site V8 reçoit les taux FX validés du Data Lab, run #38759917864, Pages #38760000686 et SHA public `56b8c401` vérifiés. Production #116 `5ebd408a` contrôle désormais Pages V9, run #38760506831 réussi ; Stable #150 `39f3097d` conserve l'ancien watchdog en manuel. L'export Tesla/Mac courant via Stable reste la dépendance de transfert prioritaire.

## 2026-10-15 — Transfert des compilations Suisse et relais IRVE Stable
- Data Lab #318/#319, source suisse brute `5058290c` et runs #38758459777/#38758672942 réussis ; Production #114 `09b384a1`, compilateur CH épinglé hors ligne, run #38758717393 réussi. Stable #147 `cb5fb8c1` retire cron/push CH avec dispatch et archives conservés. Le candidat CH reste distinct du snapshot publié : 15 anciens EVSE absents de la source brute actuelle, 51 nouveaux ; aucune offre d'un EVSE commun supprimée.
- Stable #148 `8bdc42e6` retire cron/push du relais IRVE ; Data Lab collecte encore, Production #104 et Pages valident le dernier lot épinglé. Les 449 BUMP de la génération nationale plus récente restent une anomalie de source séparée. FX/Pages/Tesla sync Stable restent actifs pour son site et le transport Mac ; migration technique globale toujours incomplète.

## 2026-10-15 — Publication V9 Production et delta de migration
- Data Lab #312–#315 ont conservé des lots validés Italie, FX, France et le socle historique 0a6 ; Production #104/#110–#112 les consomme. Build #38755773180 réussi ; publication Pages Production #38756331049 réussie sur `29b0ae54`, shell et manifeste publics vérifiés (`2026-10-15-v9-datalab-baseline-candidate`, 2 463 fichiers). Stable Pages et Cloudflare inchangés.
- Data Lab #316 fusionnée `fc3cfd2e` : cron suisse et garde last-good, CI PR #38757135676 réussie. Stable #146 fusionnée `be4cfbd9` : seul le cron/push DOT-NL est retiré, dispatch et données historiques conservés. Le cron suisse Stable reste actif en attendant une validation de consommateur CH.
- Restent le relais Tesla/Mac vers Stable, le constructeur CH, les workflows nécessaires au site Stable et les incidents de collecte Electroverse/REVE. La migration technique demeure incomplète ; prochaine étape Tesla/Mac consommateur, sans toucher à son acquisition.

## 2026-10-15 — transfert Ze-Watt, REVE et Zephyre ; extinctions ciblées

- Updater Test #14/#15/#16/#17 fusionnées : preuve Ze-Watt, retrait des déclencheurs Ze-Watt/Electroverse/REVE, dispatch historiques et Tesla/Mac conservés. Stable #143/#144 fusionnées : cinq miroirs V8 et Ze-Watt manuels seulement ; Pages Stable maintenu.
- Data Lab #309 fusionnée (`8f7754c7`) avec seed REVE validé `d5bff031`; Production #105/#107/#108 fusionnées jusqu'à `3216c317`, build Espagne épinglé, parité et Pages en validation sans déploiement. REVE API 429 reste incident externe.
- Data Lab #310 fusionnée (`0b358fcf`) : Zephyre ePowerDirect et offre exacte épinglée ; refresh #38750594661 réussi. Production #109 fusionnée `e799be46` après CI de développement et Pages réussie (sans déploiement) ; Stable #145 fusionnée `3aba11c3`, cron/push retirés et dispatch de rollback conservé. Aucune formule de prix modifiée.

## 2026-10-15 — reprise différentielle du développement Codex

- Session Codex locale retrouvée : dernier chantier OZECAR/Electroverse/REVE. OZECAR #308 déjà fusionnée avec deux runs Data Lab réussis ; cron Updater Test retiré via #13, fallback manuel gardé. Les anciens worktrees Production n'ont aucun commit unique en avance sur main. Reprise indépendante de Data Lab #301 au SHA `11617312b` : comparaison exacte EVSE/station/puissance Stable épinglé contre candidat PUN, rapport en artefact, sans tarif ni cutover. Tests locaux 2/2, CI #38734681101 en cours au dernier relevé. Blocages : 2 314 anciens IDs absents de PUN, 18 divergences de puissance à qualifier ; France #104 et REVE/Electroverse laissés à leurs chantiers spécifiques.

## 2026-10-15 — migration non-Tesla : OZECAR en PR, Electroverse et REVE qualifiés

- Electroverse France déjà collecté dans Data Lab avec runs quotidiens et hebdomadaires réussis ; overlay filtré bloqué par le recensement de statuts #219. PR Data Lab #308 au SHA `f38fedbe7` migre OZECAR national avec projection publique et tests, sans supprimer Updater Test ni publier. REVE progresse à 403/468 pages tarifs, 269/454 statuts puis rencontre HTTP 429 au curseur 404 ; checkpoints préservés. Rapport différentiel, mémoire et issues mis à jour ; aucun prix ou snapshot Production modifié.

## 2026-10-15 — France IRVE #104 : origine des 449 EVSE BUMP établie

- 449/449 identifiants retrouvés dans le CSV national brut de même SHA que la génération Data Lab du 15/10 ; disparition au rebuild du 11/10 à SHA source inchangé, par le filtre EF/Type 2/CCS (`d89b0ebf6`). 373 sans prise déclarée, 76 avec seule prise « autre » ; aucune activité dynamique explicite. Rapport individuel versionné sur #104. Le filtre et le validateur BUMP sont conservés ; la qualification source/CPO des prises et de l'activité bloque toujours le canary. Aucun nouveau run ni changement tarifaire.


## 2026-10-15 — France IRVE #104 : blocage BUMP confirmé par CI unique

- Run Production #38724599850 : test d’idempotence passé, build bloqué sur 449 EVSE BUMP historiquement tarifés absents de la nouvelle source nationale (0 statut dynamique `en_service`). Rapport exact Production `e9c33ed`, mémoire sur Data Lab #307. Aucun second run, aucune modification d’offre, publication ou extinction Stable. Action restante : décision de couverture fondée sur les sources approuvées.

## 2026-10-15 — France IRVE #104 : écarts globaux intergénérations explicités

- Ancien résultat supplémenté contre nouveau national : 8 027 IDs de station anciens absents, 9 129 nouveaux, 31 821 paires station/EVSE anciennes absentes et 31 102 nouvelles. Aucun de ces écarts n’a été masqué par le comparatif ciblé des 25 stations. Commentaire dans Production #104 ; canary encore non qualifié.

## 2026-10-15 — France IRVE #104 : traitement idempotent préparé

- Production `2401c2b` sur #104 ; comparaison ciblée de 25 stations et 11 EVSE supplémentaires, tests locaux ajout/présent/divergent réussis ; CI de build comparatif lancée une seule fois. Offres/prix inchangés, aucune bascule. Preuves dans les deux rapports France IRVE de la PR #104 ; prochaine action : résultat CI et parité des deux sorties.

## 2026-10-15 — Delta EVSE France du candidat IRVE

- Comparaison ciblée des pins : 17 EVSE Belib et 39 BUMP approuvés déjà présents dans la nouvelle source ; 1 EVSE Belib et 10 BUMP supplémentaires sur ces mêmes stations, 1 127 stations France de plus avant supplément. Preuve Production #104 `3d928a1`. Aucun prix attribué, cutover bloqué.

## 2026-10-15 — France IRVE #104 : diagnostic de générations et candidat comparable

- Le run Production #38506877130 compare deux générations incompatibles (48 058/165 792 contre 49 185/165 129). PR #104 mise à jour au SHA `834101c` avec pin Stable de même génération, builds comparatifs stricts et diagnostic préalable ; CI #38722672261 en échec sur collision Belib déjà présent dans la nouvelle génération ; preuve Production `19d53c0`. Source détaillée : `docs/FRANCE_IRVE_HANDOFF_2026-10-15.md` sur la branche Production #104. Aucun cutover, déploiement ou extinction Stable. Prochaine action : conclusion CI et preuve de parité métier.

## 2026-10-13 — B01 Electric 55 identifiée ; frontière de clôture EnergyVision

- Preuve E55C Place Lully enrichie avec borne B01, EVSE exact `FR*55C*EFR78210*P21PL*0` et 22 kW ; les conditions de déclenchement du parking restent non établies, donc aucune promotion tarifaire V9 pour ce point. EnergyVision Production #94/#95 et CI main #38448522469 vérifiées : 778 tarifs Direct calculables dans le candidat, grilles complexes non résolues, déploiement public non déclenché. Voir [état courant](CURRENT.md).

## 2026-10-13 — rationalisation des GitHub Actions historiques

- Règle confirmée : updater-test réservé au Tesla/Mac historique, Data Lab canonique pour CPO/eMSP ; supprimer seulement les doublons vérifiés.
- 92 workflows historiques recensés ; 8 YAML non-Tesla supprimés dans updater-test (Electroverse bootstrap, Greenspot, GOFAST, Swisscharge, CPO counts Suisse, PowerUp, target CPO full/second pass). 84 restants et prochaines vérifications documentés dans [l'audit](../docs/updater-test-data-lab-workflow-migration-audit-2026-10-13.md). Aucune modification des workflows Tesla.

# Journal de la mémoire technique

## 2026-10-15 — Ze-Watt et déclencheurs Electroverse historiques

- Updater Test [#14](https://github.com/yass3705/tesla-stations-updater-test/pull/14) fusionnée `cb1ff4bf` après le run #38738305550 ; [#15](https://github.com/yass3705/tesla-stations-updater-test/pull/15) fusionnée `c243b555`, supprime le seul déclencheur automatique Ze-Watt historique. Data Lab conserve le collecteur planifié et les offres compilées ; archives et dispatch privé préservés.
- Updater Test [#16](https://github.com/yass3705/tesla-stations-updater-test/pull/16) fusionnée `3111b462`, retire les déclencheurs `push` des sélecteur et rafraîchisseur Electroverse historiques. Collectes quotidiennes et hebdomadaires Data Lab déjà validées ; overlay EVSE #219 reste soumis à son gate de statuts. Aucun changement Tesla, secret, prix, snapshot Production ou publication.
- Distinction explicite : ces retraits de déclencheurs ne prouvent pas l'autonomie Espagne/Italie/France ni la publication V9. REVE mensuel vers Stable, France #104 et publication Stable restent opérationnels. Voir `CURRENT.md` pour la prochaine étape.

## 2026-10-13 — EnergyVision BE : supplément Direct V9 à 778 PDC, Lully 22 kW confirmé

- [Production #94](https://github.com/yass3705/tesla-charge-companion-production/pull/94) fusionnée : 3 795 PDC source EnergyVision, 776 offres directes simples à identité exacte dans le nouveau candidat de développement `2026-10-13-be-energyvision-official-cpo-candidate`. [Production #95](https://github.com/yass3705/tesla-charge-companion-production/pull/95) fusionnée `77d56025`, deux PDC supplémentaires à 0,37 €/kWh + 2,04 €/session, oracle de 20 kWh = 9,44 €. Total 778 Direct calculables ; les grilles conditionnelles/minutes sans validation restent indisponibles ou incalculables, sans faux tarif. CI PR [38445027765](https://github.com/yass3705/tesla-charge-companion-production/actions/runs/38445027765) verte ; vérifier la [CI main 38448522469](https://github.com/yass3705/tesla-charge-companion-production/actions/runs/38448522469). Aucune publication du candidat.
- Electric 55 Place Lully : 22 kW ajouté à la preuve de portail par confirmation utilisateur ; PDC exact et nature du parking non prouvés, pas de propagation au réseau.

## 2026-10-13 — extraction nationale eMSP par checkpoints engagée

- Electra NL : collecte source des pages mondiales 0–59 sur 3 230 attendues, 4 548 lieux NL et 4 476 occurrences EVSE jointes par ID/GPS avec prise normale/Type 2/CCS ; 4 474 ID distincts. Deux répétitions et couverture incomplète restent à résoudre. Electroverse UK : 19 239 lieux CPO éligibles issus de huit sources forment une file de découverte nationale, sans présumer d'une offre eMSP. Scripts, workflows manuels, empreintes et limites détaillés dans `docs/v9-emsp-national-staging-2026-10-13.md`. Aucun tarif ni snapshot V9 promu, aucun déploiement.

## 2026-10-13 — EnergyVision BE, source de tarification simple isolée

- [Data Lab #267](https://github.com/yass3705/tesla-charge-companion-data-lab/pull/267), fusion `658b0852`, [CI #38436662460](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/38436662460) verte : **248 stations / 817 PDC à source TTC kWh simple**, dont **778 à état positif**, avec arithmétique de preuve indépendante. L'applicabilité EVSE et le prix checkout restent non confirmés, donc **0 tarifs V9 promus**. Rapport [preuve EnergyVision](../docs/integrations/energyvision-simple-kwh-proof-audit-2026-10-13.md). Aucun nouveau pin ni déploiement.


## 2026-10-13 — pilotes eMSP internationaux limités aux prises admissibles

- [Data Lab #264](https://github.com/yass3705/tesla-charge-companion-data-lab/pull/264) fusionnée `c182a73aaedf62a9300699a5f6d2de43ed29dabf` après [CI #38436011014](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/38436011014) verte : filtre explicite prise normale/Type 2/CCS dans les scripts Electra NL et Electroverse UK, tests de rejet CHAdeMO/Type 1, et rapport Electra NL renouvelé. Deux EVSE Type 2 exacts/GPS du lieu Electra `fae3d27f-4a75-4824-bf52-a1853729b4fe` validés comme échantillon d'identité et de grille source ; voies eMSP 0,61 €/kWh et Direct 0,605 € TTC/kWh séparées. [Run Electroverse UK #38435395373](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/38435395373) réussi : 2 Type 2 Allego exacts, 8 CCS MFG en groupe candidat, 8 CCS Source EV rejetés pour tarif eMSP contradictoire. Prix finaux eMSP et publication restent suspendus aux preuves de frais/TVA. Détails dans `docs/v9-emsp-bounded-pilots-2026-10-13.md` ; aucun déploiement.

## 2026-10-13 — Supplément EnergyVision CPO indépendant vérifié, tarif Place Lully consigné

- Data Lab [#262](https://github.com/yass3705/tesla-charge-companion-data-lab/pull/262) fusionnée `2ff9e647`, correctif de variation [#263](https://github.com/yass3705/tesla-charge-companion-data-lab/pull/263) fusionnée `3635cef7`. [Run principal EnergyVision #38435009280](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/38435009280) **success** : **1 238 sites, 3 795 PDC, 3 633 actifs**, 1 228 grilles station non rattachées, 0 correspondance EVSE au NAP sélectionné. Artefact CPO autonome de sept jours, aucune offre V9 publiée. Accès public site par site et seuils minutes restent à qualifier ; source [EnergyVision Public Charging Network](https://transportdata.be/en/dataset/energyvision-public-charging-network-afir-datex). [Détail](../docs/integrations/energyvision-independent-cpo-supplement-2026-10-13.md).
- Observation utilisateur Electric 55 Place Lully : **0,60 €/session + 0,08 €/min charge et 0,08 €/min parking entre 07–23h ; 0,06 €/min charge et 0,06 €/min parking entre 23–07h**. [Source séparée à PDC non identifié](../data/station_verifications/electric55_place_lully_direct_portal_user_2026_10_13.json), conservée sans attribution de prix avant clarification EVSE et nature du stationnement. Aucun nouveau pin ni Pages/Cloudflare.


## 2026-10-13 — Pilotes eMSP UK/NL fusionnés, CI verte

- Data Lab [#260](https://github.com/yass3705/tesla-charge-companion-data-lab/pull/260) fusionnée `301364b6bdaf278bc3f5a663d57053a02ed427f5`, [CI PR #38432749548](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/38432749548) réussie sans appel fournisseur ; scan public local OK. Deux groupes GPS UK candidats sur trois sites, Source EV bloqué par conflit 0,89/0,71 £ et MFG 0,69 £ encore sous vérification TVA/périmètre ; 342 candidats identité+puissance+grille Electra NL, sans promotion. Production/pin/Pages inchangés. Prochaines preuves : prix payable Electroverse UK avec TVA et type de prise/grille eMSP Electra NL.

## 2026-10-13 — Équivalence GPS eMSP UK autorisée, conflit Source EV détecté

- [Pilote #38431179952](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/38431179952) : 8/8 prises de même puissance, type et GPS pour Source EV et MFG malgré IDs EVSE différents ; aucune offre promue. Source EV présente deux montants Electroverse incompatibles (0,89/0,71 £/kWh) : statut incalculable. MFG 0,69 £/kWh homogène reste candidat avec TVA à vérifier. La règle de groupe GPS autorisée par l'utilisateur est documentée dans le [rapport des pilotes](../docs/v9-emsp-bounded-pilots-2026-10-13.md) et un contrôle des deux couches tarifaires est ajouté. [Sonde API #38431374082](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/38431374082) : 60/60 HTTP 200, aucun 429 ni en-tête de quota, limite maximale inconnue. Aucune modification Production ni Pages.
- Qualification Electra NL sur quatre pages : 367 liens EVSE/GPS exacts et puissance compatible ; 366 types de connecteur non renseignés par la source Electra, 342 candidats à grille unique/statut positif, 14 multigrilles encore ambigus et 11 statuts rejetés. Unité `maxPower` source corrigée en watts. Aucun prix Electra NL promu.

## 2026-10-13 — Electroverse GB, test authentifié réussi

- [Run #38429086271](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/38429086271) après Data Lab #255 `44760b5f5` : 35 requêtes, aucune erreur ; deux EVSE Allego exacts et actifs avec composants eMSP source £0.63/kWh ; Source EV et MFG zéro EVSE exact malgré lieux proches. Direct CPO Allego 2099 reste distinct ; métadonnée TVA eMSP 0 % versus normalisation CPO 20 % à clarifier. [Rapport source](../reports/emsp-pilots/electroverse-uk-cpo.json), [interprétation](../docs/v9-emsp-bounded-pilots-2026-10-13.md). Aucun overlay tarifaire V9, pin, Pages ou Cloudflare modifié.

## 2026-10-13 — Pilote Electra NL réel ; sonde Electroverse GB préparée

- Script reproductible Electra sur quatre pages GraphQL et base DOT-NL courante : 257 lieux, 597 EVSE, 367 identités EVSE/GPS uniques, 356 statuts positifs bilatéraux, 351 prises situées sur une grille Electra unique, 16 multigrilles, 360 avec référence Direct DOT-NL. Aucun prix attaché ou publié ; [résultat et limites](../docs/v9-emsp-bounded-pilots-2026-10-13.md), rapport JSON et SHA source. Workflow manuel Electroverse GB borné à trois sites CPO UK, sans exposition du secret ni modification canonique ; run à effectuer après validation du code. Aucun Pages/Cloudflare.

## 2026-10-13 — Exploration de collecte eMSP internationale et identité CPO

- IT, CH, DE, ES, NL, GB et BE étudiés, MA exclu explicitement. Sondage borné de la liste Electra multicountry : 322 938 lieux annoncés, charge utile de 19,6 Ko en listing léger contre 107,8 Ko pour les mêmes 100 lieux avec tarifs complets ; aucun débit soutenu extrapolé. Sept pages Electra espacées (700 lieux au total) attestent BE/NL/DE/FR/IT/ES/CH dans l'échantillon, zéro GB observé sans conclusion de couverture nationale. Les tuiles Electroverse restent un index d'IDs sans tarifs, et son recensement de statuts FR reste bloqué. Proposition versionnée : découverte en deux phases, collecte ciblée, rafraîchissement tarifaire périodique et graphe d'identité EVSE/prise traçable ; pilote GB Electroverse, BE/NL Electra. [Méthode, preuves et critères](../docs/v9-emsp-international-acquisition-crosswalk-2026-10-13.md). Aucun tarif, pin Production, Pages ou Cloudflare modifié.

## 2026-10-13 — EnergyVision BE direct staging succeeded, not released

- [Data Lab stage run #38419429972](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/38419429972) succeeded: 1,236 sites, 3,791 Type2/CCS PDC with 100% exact static/dynamic ID reachability, four status-only extras, 1,226 station-level ad-hoc rates with 4,778 XML price components, ten stations lacking a rate. No invented direct offer in Production. [Evidence and next reconciliation requirements](../docs/integrations/energyvision-datex-live-evidence-2026-10-13.md).


## 2026-10-13 — EnergyVision BE DATEX static/dynamic acquisition confirmed

- [Data Lab authenticated workflow #38417695881](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/38417695881) succeeded on all four routes (`200`): 1,236 static sites / 3,791 refillPoint elements / 4,778 energyPrice components, 1,238 dynamic site statuses / 3,795 refillPoint status elements. This is XML structural coverage, not validated payable tariffs. [Proof and safe staging plan](../docs/integrations/energyvision-datex-live-evidence-2026-10-13.md), [PR #250](https://github.com/yass3705/tesla-charge-companion-data-lab/pull/250) merged and [PR #251](https://github.com/yass3705/tesla-charge-companion-data-lab/pull/251) prepares exact site/point/rate/status staging. No prices deployed or guessed.


## 2026-10-13 — EnergyVision BE : première collecte XML sûre préparée

- Secret `ENERGYVISION_API_KEY` déjà validé sur deux routes authentifiées `/metadata` et `/health` par le [run #38288652812](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/38288652812). [PR #250](https://github.com/yass3705/tesla-charge-companion-data-lab/pull/250) ajoute un diagnostic des flux DATEX statique/dynamique, journalisant seulement formes XML, volumes et SHA-256. La PR valide ses tests sans secret, puis un merge en main déclenche une collecte authentifiée, sans publication. L'identité EVSE et les prix directs consommateurs devront être certifiés dans une phase suivante.


## 2026-10-13 — GeniePoint UK, 857 prises hors prix

- Relecture de la source OCPI officielle épinglée et du compilateur Production : 852 connecteurs ont un frais `PARKING_TIME` avec `min_duration`/`step_size` par paliers (648/166/34/4), cinq n'ont pas de référence tarifaire. 281/1 138 restent tarifés exactement ; aucun prix partiel ajouté. L'ambiguïté OCPI de la base temporelle et de l'arrondi est documentée dans `docs/uk-geniepoint-residual-semantics-2026-10-13.md` avec une demande précise au support GeniePoint. Aucun code, pin ou Pages modifié.

## 2026-10-13 — BUMP Direct exact, supplément IRVE actif et pin de développement

- Production #90 `c6b9ea9` a épinglé le catalogue BUMP Direct courant : 1 744 EVSE exacts/55 groupes, 543 EVSE tarifés source non joints ; oracle charge seule 1,055 €, CI candidat `38405972501` et `main` `38406305858` vertes. Production #91 `f08c5d6` ajoute 21 stations/39 EVSE positivement actifs et démontrés dans l’IRVE plus récent, sans substituer la base entière : 1 783 EVSE tarifés/58 groupes, 504 non joints, trois conflits géographiques exclus. CI PR `38408105581` et preview `38408105702` vertes ; CI `main` `38408405218` et preview `38408405107` réussies, navigateur compris ; déploiement ignoré. Le nouveau candidat `2026-10-13-fr-bump-active-supplement-candidate` garde Data Lab `e39a44660`, Stable `0a6d2c34`, BUMP isolé `e22c23b1c`. Pages HTTP reste sur `2026-10-13-nine-country-be-belib-exact-candidate`, sans déploiement. Production #92 `a61164e` synchronise le rapport consolidé après CI, sans code runtime. Détails et blocages dans `CURRENT.md` et le rapport Production.


## 2026-10-13 — UK flux ouverts post-pin et CI BUMP

- Collecte UK 12/12 réussie au run `38400775080`, commit Data Lab `49bd7ced1`, mais deux sources partielles : `char.gy` cinq tarifs absents/1 128 EVSE, ChargePlace Scotland deux tarifs absents/116 EVSE. Pin antérieur : une source partielle, `char.gy` 1 092 EVSE affectés, ChargePlace complet. Pas de repin ni de transfert des tarifs ChargePlace historiques 2024. Voir `docs/v9-uk-open-feeds-post-pin-diff-2026-10-13.md`.
- Data Lab #241–#246 fusionnées pour l'audit France et BUMP. CI parseur `38401775841`, TCC-ready `38401773477`, export final `38403584628` et audit de fiabilité `38403585890` réussies ; l'export `e22c23b1c` porte le runtime à 2 287 EVSE/65 offres sur 2 500 points français. Seize doubles seuils énergie/durée et six frais différés pendant la charge ont un oracle moteur aux frontières. Huit grilles horaires restent en quarantaine, 205 points sont sans tarif source classable. Cinquante-quatre liens EVSE perdus concernent 27 enregistrements de station, dont 44 prises à SAGS Paris Lobau sur la même localisation applicative ; aucun ancien prix n'est réattaché sans ID courant. Production #89 fusionnée `eadaddf5` met à jour le bilan sans code ni pin. Production et Pages restent épinglés à leurs snapshots antérieurs.

## 2026-10-13 — Gate des collectes directes France post-pin

- Comparaison des sources post-pin : l'inventaire BUMP et ETotem ne portent aucun prix, mais le catalogue GraphQL distinct de BUMP contient 2 316 points avec objet tarif. Le parseur BUMP variable a été corrigé : 343 échecs locaux sur cinq formes deviennent 0/1 039, frais pendant et après charge séparés ; TCC-ready 2 295/2 500 points classables, contre 2 290/2 480 au 4 octobre. Son export runtime copiait un schéma de règles interne illisible par le moteur ; correction fail-closed et composants conditionnels du moteur réutilisés. Le détail avant/après du second correctif de durée et les huit grilles encore bloquées figurent dans `docs/v9-france-post-pin-direct-source-gate-2026-10-13.md`. 54 points perdent leur mapping courant. Monta rapproche 550 stations mais 407 groupes directs sans EVSE explicite ; QualiCharge ne retourne aucune WAAT. WAAT historique du 26 août inchangé (452 stations/507 configurations). Pas de repin ni de publication publique ; prochaine action : preuves EVSE/frais WAAT et audit des 54 pertes BUMP.

## 2026-10-13 — Neuilly horaire #87 et bilan #88

- Production #87 fusionnée `56dc2f7a` : 14 offres Neuilly auparavant exclues ajoutées au calcul Direct CPO, 740/740 offres Métropolis exactes attachées. Garde sur fuseau/fin de charge/fenêtres/limite dans une minute, oracle horaire et DST, libellés des seules plages facturées. Nouveau pin de développement `2026-10-13-fr-spie-neuilly-timewindow-candidate`, Data Lab `e39a44660`, Stable `0a6d2c34`, 2 447 fichiers / 745 876 157 octets. CI PR `38399876380`, DOT-NL `38399876357`, preview `38399876515`, CI `main` `38400218056` et preview `38400217874` vertes ; Pages ignoré. Production #88 fusionnée `b49ece6f`, bilan consolidé à jour. Shell Pages public inchangé. Data Lab `main=b2d4ba799` a des collectes post-pin non promues.

## 2026-10-13 — Métropolis direct #85, pin e39 et bilan #86

- Production #85 fusionnée `30f2c275` : 726 offres Métropolis Direct à EVSE exact publiées dans le **candidat de développement**, 14 exceptions horaires Neuilly exclues. Data Lab pin `e39a44660`, Stable `0a6d2c34`, manifest 2 447 fichiers / 745 853 449 octets. CI PR `38398045169`, `main` `38398355560` et previews `38398045097`/`38398355687` vertes ; jobs Pages ignorés. Production #86 fusionnée `ee86a060` : bilan consolidé actualisé. Les collectes Data Lab ultérieures, dont BUMP `30d8c050b`, ne sont pas automatiquement dans le pin ; snapshot public Pages inchangé. Voir `memory/CURRENT.md` et le rapport Production `docs/v9-spie-metropolis-exact-candidate-2026-10-13.md`.

## 2026-10-13 — Bilan candidat #84 et synchronisation de reprise

- Data Lab #237 fusionnée `fb6ec091`, preuve normalisée des 62 anciens IDs DOT-NL absents ; Production #84 fusionnée `5b23b7d8`, rapport transversal `docs/v9-technical-tariff-readiness-2026-10-13.md`. Pin de développement inchangé, CI du code candidat `38393575432` réussie, shell Pages encore sur l'ancien snapshot. Les collectes Data Lab ultérieures au pin restent non promues ; fournisseurs requis pour les identités et prix manquants. Aucun déploiement public.

## 2026-10-13 — Diagnostic source des 62 sites DOT-NL sortants

- Script et rapport de transition exacts entre les pins Data Lab `047e1911` et `2cc230af` ; 62 anciens sites tarifés sans remplacement ont aussi zéro correspondance d'ancien ID dans la source normalisée du 13/10. Cinquante et un étaient auparavant `IN_SERVICE`, onze `UNKNOWN`. Huit autres anciens sites ont un candidat au même lieu avec son propre tarif nouveau, sans transfert historique. Voir `docs/v9-dotnl-pinned-transition-2026-10-13.md`. Aucune donnée tarifaire ni pin modifié ; correspondance d'identité et statut fournisseur requis pour les 62.

## 2026-10-13 — Production #83 Tesla congestion et preuve runtime Belib

- Production #83 fusionnée `32e20e22` après CI `38393330007` verte, navigateur inclus ; nouveau pin de développement `2026-10-13-fr-belib-tesla-congestion-evidence-candidate`, sans modification Pages. La règle Tesla officielle exige l'occupation du site ; les 1 112 montants source restent non facturables et portent `conditionVerified:false`. Test runtime renforcé : quatre directs Belib calculables, 17 jointures Electra et 12 Electroverse supplémentaires. Le différentiel France exact et les résidus NL/UK sont dans les rapports Production #82/#83.

## 2026-10-13 — Production #82 fusionnée après CI navigateur

- Production #82 fusionnée `d459fa0d` ; nouveau pin de développement Belib exact + Connected Kerb, Data Lab `2cc230af`, Stable `0a6d2c34`. CI PR `38391773395` entièrement verte, navigateur et SHA-256 inclus ; job Pages ignoré. Vérification HTTP après fusion : le site public sert encore `2026-10-13-nine-country-be-belib-exact-candidate`. Le rapport différentiel dans Production garde 62 anciens sites DOT-NL tarifés sans identité actuelle prouvée comme résidu à investiguer avant publication publique.

## 2026-10-13 — Audit IRVE #233 fusionné, candidat Belib/Connected Kerb #82 en validation

- Data Lab #233 fusionné `2cc230af` : comparaison exacte du pin FR et de la source du 13/10. Production #82 construit localement le supplément de 4 stations / 17 EVSE Belib actifs et remplace l'assertion fixe Connected Kerb par la parité aux rapports épinglés. Premier run CI complet avec navigateur `38390558857` vert, Pages ignoré ; nouvelle CI du commit documentaire `95e8f12` en attente. Différentiel de couverture détaillé dans la PR Production : 62 anciens sites DOT-NL tarifés sans identité actuelle prouvée restent en investigation. Aucun pin public ni prix historique ambigu promu.

## 2026-10-13 — Comparaison différentielle du pin France IRVE

- Script, JSON et rapport ajoutés sur `audit/v9-irve-reconciliation-20261013` : base du 13/10 (49 185 stations, 165 129 EVSE) comparée au pin public (48 058/165 792). Une substitution perdrait 3 955 jointures Electroverse et 34 Electra tout en en gagnant 2 173 et 4 514 ; elle est refusée. Quatre stations Belib absentes du pin ont 17 EVSE exacts et actifs dans la nouvelle source ; les trois autres restent sans statut positif. Aucun prix ni pin modifié. Détails et preuves dans `docs/v9-france-irve-pinned-transition-2026-10-13.md`.

## 2026-10-13 — Pertes de jointure des catalogues directs France

- Production #81 documente la jointure au pin IRVE des catalogues directs français. BUMP 1 750/1 750, Belib 466/473, Electric 55 1/1, Freshmile 2/2, IZIVIA 54/54, Ze-Watt 39/39, Zephyre 16/16, IONITY 4/4 offres avec EVSE explicite jointes ; Loadmotion 37/41. Une offre ETotem à station explicite ne joint pas. Les sept stations Belib absentes du pin nécessitent une vérification de statut et d’identité avant une éventuelle extension de l’inventaire. Aucune offre non jointe n’est affectée par ressemblance ou proximité.

## 2026-10-13 — Offre directe Electric 55 exacte préservée

- Production #80 `ed8f470` fusionnée après CI globale/pin et smoke neuf pays verts, Pages ignoré. La source directe nationale Electric 55 ne publie aucun prix consommateur général ; une offre de checkout indépendante, déjà validée pour l'EVSE de Lons-le-Saunier `FR55CEFR39000P7PPFG1`, est bien compilée et jointe à la seule station nationale `FR55CP39000LSAP7PPFG`. Nouveau garde contre sa perte ou sa propagation aux autres stations. Place Lully et Bois-d'Arcy restent sans tarif direct exact ; leur Electroverse exact demeure applicable. Rapport Production mis à jour.

## 2026-10-13 — Frais Electric 55 omis après passage du créneau horaire

- Production #77 `fabeda6` fusionnée après CI globale/pin et régressions NL/IZIVIA vertes, Pages ignoré. Les minutes après charge sont ventilées par créneau et facturées une fois ; le résumé affiche seulement les composantes du créneau réellement facturé. L’oracle des offres EVSE exactes Place Lully/Bois-d’Arcy trouve 1,80/3,60 € contre 1,50/3,00 € avant correction au scénario 22h45 + 45 min charge + 10 min stationnement. Une comparaison nationale déterministe montre 2 222 offres Electroverse FR corrigées à la hausse parmi 3 859 offres horaires avec stationnement ; aucun montant ne baisse. Rapport Production #78 pour les limites.

## 2026-10-13 — Audit V9 : abonnement, classement, devises Tesla et contrôle global des identités

- Production #70 `ed4d34a`, #71 `323645a` et #72 `e18e58e` fusionnées après CI globale et pin vertes, Pages toujours ignoré. Les tarifs Electra+ ne sont dérivés que sur 320 grilles directes uniques. Le tri explicite devient strict. Tesla PT utilise la carte commune ; les prix Tesla GBP/CHF/MAD conservent leur devise source.
- Le contrôle des 187 362 offres eMSP FR du pin public trouve 92 850 Electra et 86 782 Electroverse rattachées à une station unique, zéro EVSE national dupliqué et zéro offre multistation ; 4 521 et 3 209 offres restent non jointes. Production #73 `269811f` a créé un nouvel identifiant candidat à sources inchangées et enregistre ce garde en CI. Production #74 `0ecb47d` corrige les unités AC IRVE (675 groupes / 663 stations), marque neuf groupes DC / six stations incalculables, et archive des captures Firefox comparatives ; CI globales et épinglées vertes, Pages ignoré. Production #75 `3a0c6ae` fusionnée après CI globales et pin vertes ; libellé source opérateur + adresse pour les titres techniques, IDs tarifaires préservés. Voir [CURRENT.md](CURRENT.md) et le rapport Production #73. Aucune publication Pages/Cloudflare.

## 2026-10-13 — Audit public V9 : restauration Electra, résumé tarifaire et carte Tesla

- Production #66 (tarifs directs Electra), #67 (résumé du tarif réellement appliqué) et #69 (Tesla Portugal en carte V9) fusionnées après CI globale et pin verts ; runs respectifs `38330916176/38330916172`, `38330924891/38330924854`, `38331242520/38331242524`. Jobs Pages ignorés.
- Production #70 en validation : Electra+ ne réduit que l'énergie de 320 stations FR à grille directe unique et vérifiée ; 201 stations à plusieurs grilles attendent une preuve d'attribution EVSE. Aucun déploiement ; pin public inchangé. Reprise détaillée dans [CURRENT.md](CURRENT.md).

## 2026-10-13 — Début de l'audit fonctionnel du site publié

- Contrôle HTTP du pin et des six stations citées. Deux prix eMSP supposés mal affectés sont liés à des EVSE exacts : Lidl Electra 0,39 €/kWh et Electric 55 Bois-d'Arcy Electra 0,084 €/min ; les offres Electroverse Electric 55 sont également exactes. La source directe Electric 55 locale reste non publiable.
- Défaut reproduit du chargement direct Electra : `kind: direct` devenait un type de prise `DIRECT`, ce qui supprimait 724 règles avant calcul. [Production #66](https://github.com/yass3705/tesla-charge-companion-production/pull/66) ouverte, test ciblé et rebuild local validés. La liaison de plusieurs grilles à chaque EVSE reste à prouver.
- Base France du site plus ancienne que celle des overlays eMSP ; remplacement brut refusé après mesure des liens restaurés et perdus. [Production #67](https://github.com/yass3705/tesla-charge-companion-production/pull/67) prépare les descriptions de tarifs utilisés ; [#68](https://github.com/yass3705/tesla-charge-companion-production/pull/68) répare le test de garde Pages devenu obsolète, fusionnée à `4f2cae2` après CI verte. Aucun nouveau déploiement.

## 2026-10-13 — Première V9 GitHub Pages publiée

- [Workflow manuel Production #38326551657](https://github.com/yass3705/tesla-charge-companion-production/actions/runs/38326551657) terminé : `candidate=success`, `deploy=success`, déploiement `7026921334` avec statut GitHub `success`. Publication autorisée et approuvée par l'utilisateur, SHA `6e3eaef101d72bf6d4855a819bcc2e4408e94528`. URL https://yass3705.github.io/tesla-charge-companion-production/ servie et redirigée vers V9, `shell-config.json` public confirme le snapshot `2026-10-13-nine-country-be-belib-exact-candidate` et FR/NL/IT/ES/CH/DE/GB/MA/BE. La validation de l'interactivité utilisateur reste post-publication, distincte du succès Pages.


## 2026-10-13 — Préparation sécurisée de la première V9 publique

- Production [PR #65](https://github.com/yass3705/tesla-charge-companion-production/pull/65) fusionnée `6e3eaef101d72bf6d4855a819bcc2e4408e94528`. Elle ajoute un workflow manuel autonome `publish-v9-pinned-pages.yml` qui reproduit exactement le snapshot de développement épinglé plutôt que la variante dynamique R14 du workflow Global Mac. [CI sans publication #38325871695](https://github.com/yass3705/tesla-charge-companion-production/actions/runs/38325871695) verte. Pages est uniquement autorisé sous `workflow_dispatch`, `publish=true` et après validation du snapshot, des neuf pays, du navigateur et des SHA-256.
- **En attente** : lancement GitHub Actions par utilisateur authentifié, puis vérification du job Pages et de l'URL; aucun lancement, aucune publication live affirmée.


## 2026-10-13 — Vérification finale du pin après les changements UI

- Production `main=9631f4b` ; pin source neuf pays inchangé. [Run épinglé 38324386726](https://github.com/yass3705/tesla-charge-companion-production/actions/runs/38324386726) vert : neuf pays + Tesla, 2 442 fichiers et 743 661 633 octets vérifiés. CI globale navigateur #38324386772 verte ; Pages toujours sur `796e7fca` du 11 octobre. Les artefacts #60 et #64 diffèrent par le code Production, pas par les SHA Data Lab/Stable épinglés.

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

## 2026-10-13 — listing UK Electroverse autour des CPO connus terminé

- Après Data Lab #269–#271, onze lots logiques de tuiles (douze artefacts, car un lot londonien a été scindé) ont terminé avec succès : 415/415 tuiles semences, 42 322 PK distincts, aucune tuile résiduellement tronquée. Le plafond observé de 10 000 points sur une tuile a imposé la subdivision ; la zone dense livre 16 872 PK. [Audit](../reports/emsp-national/electroverse-uk-tile-audit.json).
- Rapprochement géographique **préparatoire** : 24 448 PK à ≤250 m des 19 239 sites CPO admissibles ; 17 591 avec plusieurs CPO proches ; 17 874 sans site semence proche. [Rapport](../reports/emsp-national/electroverse-uk-coarse-candidates.json). Aucun de ces PK n'est une offre tarifaire ni une jointure EVSE validée. Étape suivante : détails GraphQL par lots bornés, puis contrôle prise normale/Type 2/CCS, EVSE et prix. Aucune publication Production/Pages/Cloudflare.

## 2026-10-13 — détails UK Electroverse : pagination et contrainte GraphQL

- [Data Lab #276](https://github.com/yass3705/tesla-charge-companion-data-lab/pull/276) et [#277](https://github.com/yass3705/tesla-charge-companion-data-lab/pull/277) fusionnées : collecte par PK bornée, seulement prises normale/Type 2/CCS et pages EVSE complètes ; CI [38444424081](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/38444424081) et [38444768491](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/38444768491) vertes.
- [Run source 38444899024](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/38444899024) : 10/10 lieux, 181 EVSE admissibles, trois appels GraphQL ; [run 38445079323](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/38445079323) : lot de 100 interrompu à l'offset 60 par cinq erreurs GraphQL 200 ; [run 38445474465](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/38445474465) : mêmes cinq PK valides dans un run isolé. Limite officielle inconnue ; nouvelle garde à une relance transitoire, trente appels maximum et sauvegarde partielle avec offset de reprise. Artefacts de 10 et cinq PK conservés sans attribution EVSE/CPO ni prix. Aucun pin ni Pages modifié.

## Format des prochaines entrées

`YYYY-MM-DD — sujet` ; décision ou constat ; preuves et liens ; fichiers/commits concernés ; vérification ; statut de publication ; action restante. Ne jamais présenter un résultat expérimental comme déployé.
# 20 octobre 2026 — démarrage reconstruction V9

- Après fetch et comparaison des quatre dépôts, le risque des anciens workflows Data Lab capables d'écrire sur `main` a été neutralisé par désactivation des Actions au niveau du dépôt. Trois runs actifs ont été annulés ; aucune exécution active au contrôle suivant. Deux références Git locales restaurables conservent le `main` distant et l'ancien HEAD local. Branche locale `rebuild/v9-20261020`, sans publication ni déploiement. Tableau de bord et prochaine opération : [V9_REBUILD_PROGRESS.md](V9_REBUILD_PROGRESS.md).

# 20 octobre 2026 — reprise de l'inventaire G1

- G2 démarré au commit `2003a7073` après G1 PASS : retrait sur la seule branche de reconstruction des 1 207 anciens workflows, code restaurable au commit `15657f4a8`. Deux nouveaux YAML lecture seule, registre partiel de dix sources à manifeste et Belgique NAP, orchestrateur à artefacts isolés. Onze tests hors réseau, essai technique réel `FR:sdey` et scan public réussis ; validateur G2 FAIL sur 143 méthodes actives restantes. Data Lab Actions désactivé ; pas de push `main`, ni de modification Production/site public.

- Porte G1 validée sur `15657f4a8` après revue regroupée des commandes, chemins `git add`, artefacts, scripts, secrets nommés et consommateurs Production. Le registre final couvre 1 207 workflows et 756 scripts ; dix tests ciblés, validateur G1, compilation et scan public réussis. Sept méthodes dormantes et cinq planifiées gardent une sortie partielle explicite à tester en G2. Actions Data Lab désactivé, aucun site public modifié. G2 ouvert.

- Décision de migration : Ubitricity NL PAYG est `legacy_method_unavailable` ; acquisition désactivée, candidat et intégrateur conservés. Le validateur vérifie l'exception nominative et refuse les absences supplémentaires (cinq tests réussis). Une correction de la porte empêche désormais le faux PASS tant que 670 workflows avec scripts, 756 scripts et 220 méthodes prioritaires gardent des statuts provisoires ; les 536 méthodes inline sont vérifiées séparément. G1 reste FAIL, G2 non commencé.

- Après rebase sur `def205b0d`, validateur G1 rejoué : seul échec, les deux scripts Ubitricity NL absents. Scan public complet réussi, Actions Data Lab toujours désactivé, aucun run actif ; branche `rebuild/v9-20261020` publiée seule sur GitHub pour reprise. Aucun changement Production ni site public.

- Nouveau fetch après scan public complet : deux commits Blink UK issus de runs déjà lancés ont avancé `main` à `def205b0d`, sans modifier workflows ni scripts. Rebase propre de la branche G1 ; Actions toujours désactivé, aucun run actif au contrôle. Les quatre fichiers de données/rapports distants sont préservés. Porte G1 à rejouer avant toute publication de branche.

- Le registre a été enrichi des indicateurs de planification, déclenchement indirect et références manquantes. Le registre central provisoire groupe 221 méthodes prioritaires dans 108 modules candidats, y compris 43 scripts historiques sans référence YAML littérale. La matrice complémentaire rattache provisoirement 756/756 scripts historiques à un module unique, avec revue explicite des 18 méthodes partagées par plusieurs familles. Les 536 méthodes inline sont inventoriées avec SHA-256 et classées : 23 critiques, 147 liées aux données (y compris les sorties dynamiques et IZIVIA hors `data/`), 366 références historiques. Le croisement statique avec Production a trouvé 80/80 chemins littéralement référencés présents dans Data Lab. Le validateur G1 vérifie inventaire, destinations, empreintes et dix périmètres ; la porte **échoue uniquement** sur les deux extracteurs Ubitricity NL absents. La PR historique #151 et les commits de création ne les contiennent pas. Son intégration `--no-write` a réussi sur 3 670 correspondances avec zéro rejet, sans acquisition ni modification de données. Un seul essai HTTP technique sur une URL connue a identifié la structure HTML/JS, sans intégrer de nouveau prix. Voir `migration/v9/G1_METHOD_AUDIT.md`. G1 reste ouverte, Actions Data Lab désactivé, G2 non commencé.

# 20 octobre 2026 — reconstruction V9, DOT-NL en G2

La chaîne nationale néerlandaise historique a été adaptée en module isolé réutilisant les scripts existants. La fixture technique et 21 tests ciblés passent ; le validateur G2 reste FAIL avec 142 méthodes actives en attente. Aucun seuil de volume ni écriture `main` dans le nouveau module ; Actions Data Lab toujours désactivées. Détails et prochaine action dans `memory/V9_REBUILD_PROGRESS.md`.

# 20 octobre 2026 — reconstruction V9, Electroverse en G2

Adaptateur isolé daily/full et checkpoint technique ajoutés à l'orchestrateur sans changer les scripts historiques. Tests de reprise, shards, chunk borné et intégrité des artefacts réussis sur fixtures ; sélection automatique du plus récent checkpoint ou jeu validé GitHub testée localement. G2 reste FAIL sur 140 méthodes ; transfert en run Actions non vérifié. Actions Data Lab désactivées, site public inchangé. Voir `memory/V9_REBUILD_PROGRESS.md`.

# 20 octobre 2026 — reconstruction V9, statuts et overlay Electroverse

Adaptateur de statuts en 16 partitions, reprise et fusion historique, finalisation nationale hors checkout ; les checkpoints partiels restent séparés des artefacts validés. L'overlay exige le recensement complet et audite les tuiles, mais son constructeur historique complet et le passage des deux dépendances via Actions restent à valider. Le seuil artificiel de 5 000 offres a été retiré. Vingt tests ciblés PASS sans appel API ; G2 FAIL avec 138 méthodes en attente. Actions désactivées et site public inchangé. Voir `memory/V9_REBUILD_PROGRESS.md`.

# 20 octobre 2026 — reconstruction V9, dépendances Electroverse

Sélection locale de deux artefacts indépendants par source et branche, vérification du manifeste et de tous les SHA avant overlay. Le workflow commun télécharge ces deux états hors checkout et sépare les manifestes d'échec des collections validées. Le constructeur et l'audit historiques ont réellement été exécutés sur une fixture FR réduite ; les échecs et la reprise sont couverts. Transfert GitHub Actions encore non testé en run réel, Actions désactivées. G2 reste FAIL avec 138 méthodes. Voir `memory/V9_REBUILD_PROGRESS.md`.

# 20 octobre 2026 — reconstruction V9, Atlante Direct

Le collecteur historique Atlante Direct, déjà référencé par Production, est raccordé au module `isolated_script` et produit un artefact vérifié hors checkout. Les gardes arbitraires sur le nombre de sites ont été retirées ; la complétude de l'hydratation reste obligatoire. Tests de parseur et d'orchestration hors ligne réussis. G2 FAIL sur 137 méthodes restantes ; Actions désactivées, aucune publication. Voir `memory/V9_REBUILD_PROGRESS.md`.

# 20 octobre 2026 — reconstruction V9, chaîne Belib

Les méthodes `belib_official.py` et `belib_station_base.py` partagent désormais un espace de collecte isolé : tarif officiel validé puis construction et contrôle de la base de stations. La reprise d'un artefact Belib vérifie source, SHA et fichiers ; les rapports historiques restent conservés. Seule la garde de volume arbitraire a été retirée de l'extracteur. Fixtures et tests hors ligne réussis, aucun nouveau prix ni API. G2 FAIL avec 135 méthodes ; Actions désactivées. Voir `memory/V9_REBUILD_PROGRESS.md`.

# 20 octobre 2026 — reconstruction V9, IONITY Direct

Un module familial exécute les scripts historiques IONITY Direct FR/IT/DE et GB dans un espace isolé ; les quatre sorties sont vérifiées avant versionnement. Seuls les seuils historiques de volume ont été retirés ; identifiants, CPO, devise et relations restent contrôlés. Sept tests sur fixtures hors ligne PASS ; G2 FAIL avec 133 méthodes en attente. Actions désactivées, aucune publication. Voir `memory/V9_REBUILD_PROGRESS.md`.

# 20 octobre 2026 — reconstruction V9, Fastned Direct

Les inventaires historiques Fastned FR/GB tournent dans un module familial isolé, avec validation commune des sorties et du rapport UK. Seuls les seuils de pages et stations ont été retirés. Sept tests de parseur et d'orchestration sur fixtures hors ligne PASS ; G2 FAIL avec 131 méthodes en attente. Actions désactivées, aucune publication. Voir `memory/V9_REBUILD_PROGRESS.md`.

# 20 octobre 2026 — reconstruction V9, garde de porte G2

Le validateur G2 exige désormais la preuve de transfert GitHub pour les cinq sources marquées `unverified`, indépendamment du nombre de méthodes enregistrées. Il expose également les sept collectes `live_pending` sans les présenter comme essais réels. Résultat actuel FAIL sur 131 méthodes, cinq transferts et registre partiel ; scan public OK, Actions désactivées. Voir `memory/V9_REBUILD_PROGRESS.md`.

# 20 octobre 2026 — reconstruction V9, inventaires Bump

Les scripts historiques d'inventaire officiel et de base tabulaire Bump sont exécutés hors checkout dans une famille commune, avec contrôle des quatre sorties. Vingt-deux tests ciblés PASS ; pagination prématurée et sortie corrompue sont rejetées. G2 FAIL avec 129 méthodes restantes, Actions désactivées, aucune publication. Voir `memory/V9_REBUILD_PROGRESS.md`.

# 20 octobre 2026 — reconstruction V9, chaîne Bump GraphQL/TCC

Deux scripts historiques supplémentaires et leur parseur conservé sont exécutés hors checkout, avec vérification des requêtes, schémas et prix non inventés. Les seuils de couverture/volume arbitraires ont été supprimés. Vingt-deux tests ciblés PASS ; G2 FAIL avec 127 méthodes restantes. Actions désactivées, aucune publication. Voir `memory/V9_REBUILD_PROGRESS.md`.

# 20 octobre 2026 — reconstruction V9, Bump officiel

Le script historique de règles officielles Bump est migré dans l'orchestrateur isolé, avec son JSON et rapport d'origine. Seize tests ciblés PASS hors réseau ; G2 FAIL avec 126 méthodes restantes, Actions désactivées, aucune publication. Voir `memory/V9_REBUILD_PROGRESS.md`.

# 20 octobre 2026 — reconstruction V9, stations Allego

La chaîne historique Allego DXP → normalisation → coordonnées de repli est migrée dans un seul module isolé. Le minimum EVSE et la présence obligatoire d'une station précise ont été retirés ; relations et identité restent validées. Dix-sept tests ciblés PASS hors réseau ; G2 FAIL avec 125 méthodes. Actions désactivées, aucune publication. Voir `memory/V9_REBUILD_PROGRESS.md`.


# 20 octobre 2026 — V9, PCPR UK exacts

Quatre méthodes PCPR UK historiques migrées en espace isolé avec tests hors ligne ; 39 tests ciblés PASS. G2 reste FAIL avec 110 méthodes utiles et 23 transferts GitHub non vérifiés. Actions désactivées, aucune publication.

# 20 octobre 2026 — V9, règles officielles FR

DRIVECO, eborn, E55C et Freshmile migrés par le module commun et testés hors ligne. Seuil de volume DRIVECO retiré ; schéma CSV et identité préservés. G2 FAIL : 106 méthodes restantes, 27 transferts GitHub non vérifiés. Aucune publication.

# 20 octobre 2026 — V9, règles Qovoltis, Vianeo, Métropolis

Trois méthodes historiques de règles officielles supplémentaires migrées et testées dans l’orchestrateur isolé. G2 FAIL : 103 méthodes restantes, 30 transferts GitHub non vérifiés. Aucune publication.

# 20 octobre 2026 — V9, Plenitude, Zunder, IECharge

Trois méthodes officielles supplémentaires migrées et testées hors ligne par l’adaptateur commun. G2 FAIL : 100 méthodes utiles, 33 transferts GitHub non vérifiés. Aucune publication.

# 20 octobre 2026 — V9, Lidl Plus et Plug Inn

Deux méthodes officielles consommées par Production migrées en espace isolé et testées hors ligne. G2 FAIL : 98 méthodes utiles et 35 transferts GitHub non vérifiés. Aucune publication.

# 20 octobre 2026 — V9, Qwello et Révéo

Les deux scripts historiques à sorties relatives tournent en espace isolé. Révéo conserve le flux OCPI comme preuve de roaming, sans tarif Direct inventé ; anciens minimums de volume retirés. G2 FAIL : 96 méthodes utiles, 37 transferts GitHub non vérifiés.

# 20 octobre 2026 — V9, import Tesla/Mac

L’import historique du lot Mac validé est raccordé à l’orchestrateur isolé, avec reprise du dernier artefact signé et tests de corruption. Les anciens seuils de stations et d’inclusion de tous les pays sont retirés ; Updater Test reste inchangé. G2 FAIL : 95 méthodes utiles, 38 transferts GitHub non vérifiés.

# 20 octobre 2026 — V9, GRIDSERVE UK PCPR

Collecte et préparation historiques isolées et testées sur fixtures hors réseau. Les tarifs restent liés aux connecteurs exacts ; les références absentes restent non tarifées. G2 FAIL : 94 méthodes utiles, 39 transferts GitHub non vérifiés. Aucune publication.

# 20 octobre 2026 — V9, Ubitricity UK PCPR

La collecte et la validation historiques UK tournent en espace isolé sur archives figées. Les offres restent liées aux connecteurs exacts et les absences de prix sont explicites. G2 FAIL : 93 méthodes utiles, 40 transferts GitHub non vérifiés. Aucune publication.

# 20 octobre 2026 — V9, La Borne Bleue

Le collecteur historique est isolé et testé sur CSV réduit. Les anciens seuils de volumes sont retirés ; réseau Direct et abonnement restent distincts. G2 FAIL : 92 méthodes utiles, 41 transferts GitHub non vérifiés. Aucune publication.

# 20 octobre 2026 — V9, AVIA Picoty stations

Le collecteur national historique est isolé et testé sur fixture IRVE réduite. Les prix observés restent des preuves, sans attribution tarifaire Direct. G2 FAIL : 91 méthodes utiles, 42 transferts GitHub non vérifiés. Aucune publication.

# 20 octobre 2026 — V9, AVIA Picoty PAN brut/index

Les deux processeurs historiques PAN sont migrés ensemble et testés hors réseau. Le CSV brut et les sorties restent séparés et les anciens minimums de stations sont retirés. G2 FAIL : 90 méthodes utiles, 43 transferts GitHub non vérifiés. Aucune publication.

# 20 octobre 2026 — V9, E55C stations et Direct

La base E55C et son enrichissement Scan Pay exact sont enchaînés hors checkout avec reprise d’un dernier état validé. Les seuils de stations et de couverture tarifaire sont retirés ; les identités et SHA restent contrôlés. G2 FAIL : 89 méthodes utiles, 44 transferts GitHub non vérifiés. Aucune publication.

# 20 octobre 2026 — V9, inventaire WAAT

Le collecteur national FR*WA2 historique est isolé et testé hors réseau ; aucune tarification Monta n’est attribuée par la seule proximité. G2 FAIL : 88 méthodes utiles, 45 transferts GitHub non vérifiés. Aucune publication.

# 20 octobre 2026 — V9, Freshmile Direct CPO

Les deux scripts historiques d’inventaire et d’exclusion régionale sont isolés et testés. Les textes tarifaires restent des candidats non classables ; les seuils de volume nul sont retirés. G2 FAIL : 87 méthodes utiles, 46 transferts GitHub non vérifiés. Aucune publication.

# 20 octobre 2026 — V9, WAAT/Monta sharded

Le collecteur historique à quatre partitions est isolé, lié à un inventaire WAAT validé et doté d'une reprise conservant les partitions bonnes. Tests hors réseau de la fusion, des erreurs de carte, de la dépendance et du SHA : 24 PASS. G2 reste FAIL : 86 méthodes utiles, 47 transferts GitHub non vérifiés. Actions désactivé, aucune publication.

# 20 octobre 2026 — V9, Fastned Suisse

La finalisation suisse historique est isolée et testée sur flux national réduit ; identité EVSE, sorties et échec de collecte sont vérifiés. G2 reste FAIL : 85 méthodes utiles, 48 transferts GitHub non vérifiés. Actions désactivé, aucune publication.

# 20 octobre 2026 — V9, Lidl Suisse

Le finaliseur historique est isolé et testé pour AC, DC et puissance absente ; le prix manquant reste explicite. G2 reste FAIL : 84 méthodes utiles, 49 transferts GitHub non vérifiés. Actions désactivé, aucune publication.

# 20 octobre 2026 — V9, IONITY Suisse national

Le rapprochement historique national/officiel est isolé avec entrée archivée et testé par coordonnées et puissance exactes ; un EVSE non résolu reste sans prix. G2 reste FAIL : 83 méthodes utiles, 50 transferts GitHub non vérifiés. Actions désactivé, aucune publication.

# 20 octobre 2026 — V9, Plenitude Suisse

La finalisation historique est isolée avec catalogue archivé et testée sur deux EVSE classés exactement et un cas 75 kW non résolu. G2 reste FAIL : 82 méthodes utiles, 51 transferts GitHub non vérifiés. Actions désactivé, aucune publication.

# 20 octobre 2026 — V9, AIL et EBS Suisse

Les deux finaliseurs historiques utilisent leurs entrées archivées hors checkout et sont testés sur fixtures réduites, avec cas non résolu conservé. G2 reste FAIL : 80 méthodes utiles, 53 transferts GitHub non vérifiés. Actions désactivé, aucune publication.

# 20 octobre 2026 — V9, EWD et Migrol Suisse

Les deux finaliseurs historiques sont isolés et testés sur flux national réduit ; un EVSE Migrol sans puissance reste non tarifé. G2 reste FAIL : 78 méthodes utiles, 55 transferts GitHub non vérifiés. Actions désactivé, aucune publication.

# 20 octobre 2026 — V9, WAAT/Monta public

La méthode publique historique est isolée avec inventaire WAAT signé et fixture hors réseau ; sorties brutes et détails restent non classables jusqu'à normalisation. G2 reste FAIL : 77 méthodes utiles, 56 transferts GitHub non vérifiés. Actions désactivé, aucune publication.

# 20 octobre 2026 — V9, WAAT/Monta monolithique supplanté

Le collecteur à quatre partitions produit les mêmes chemins, conserve les champs historiques et ajoute les configurations exactes par connecteur. Le monolithique reste archivé ; sa non-exécution est nominative et vérifiée. G2 reste FAIL : 76 méthodes utiles, 56 transferts GitHub non vérifiés. Actions désactivé, aucune publication.

# 20 octobre 2026 — V9, autoSense/AMAG, CHEVP et Shell/evpass Suisse

Les trois finaliseurs historiques sont isolés et testés sur flux national réduit. L'offre de marque reste conditionnelle et les EVSE sans puissance demeurent non tarifés. G2 reste FAIL : 73 méthodes utiles, 59 transferts GitHub non vérifiés. Actions désactivé, aucune publication.

# 20 octobre 2026 — V9, Saascharge et Partino Suisse

Saascharge est limité aux plages tarifaires explicites ; Partino sépare l'accès restreint du prix inconnu. Tests hors réseau réussis. G2 reste FAIL : 72 méthodes requises, 61 transferts GitHub non vérifiés. Actions désactivé, aucune publication.

# 20 octobre 2026 — V9, IWB Bâle

L'overlay historique IWB est isolé et testé avec cas à Bâle et hors Bâle ; l'accès public seul ne devient jamais un prix. G2 reste FAIL : 71 méthodes utiles, 62 transferts GitHub non vérifiés. Actions désactivé, aucune publication.

# 20 octobre 2026 — V9, TAE Matterhorn

Le finaliseur historique est isolé et testé sur 22 et 50 kW ; le second EVSE reste explicitement non résolu. Son fichier brut contient des montants indicatifs sur la ligne non résolue : G3 devra les exclure du calcul. G2 reste FAIL : 70 méthodes utiles, 63 transferts GitHub non vérifiés. Actions désactivé, aucune publication.

# 20 octobre 2026 — V9, EWO/eCarUp Suisse

Le finaliseur historique est isolé avec catalogue eCarUp archivé et correspondance exacte opérateur, distance et connecteur public. G2 reste FAIL : 69 méthodes utiles, 64 transferts GitHub non vérifiés. Actions désactivé, aucune publication.

# 20 octobre 2026 — V9, DRIVECO EVSE exact

Le collecteur CSV historique est isolé et testé sur une valeur et une matrice OSF archivées. Le coût de session reste explicitement incalculable tant que la sémantique OSF manque ; aucun seuil de volume. G2 reste FAIL : 68 méthodes utiles, 65 transferts GitHub non vérifiés. Actions désactivé, aucune publication.

# 20 octobre 2026 — V9, Midhope exact UK

Le constructeur historique Midhope est isolé avec preuve et snapshot Connected Kerb archivés. Les deux workflows de reconstruction équivalents sont couverts, avec EVSE, connecteurs et QR exacts. G2 reste FAIL : 66 méthodes utiles, 66 transferts GitHub non vérifiés. Actions désactivé, aucune publication.

# 20 octobre 2026 — V9, Chargezy/TE63

Le collecteur historique Chargezy/TE63 est isolé, avec jointure PAN par EVSE exact, cas spécial et lacunes conservés. Son ancien seuil de 280 lignes a été retiré ; la dépendance HTTP historique est installée uniquement pour cette source. G2 reste FAIL : 65 méthodes utiles, 67 transferts GitHub non vérifiés. Actions désactivé, aucune publication.

# 20 octobre 2026 — V9, garde historique de volumes

L'ancien contrôle global `validate_v9_source_guards.py` est classé obsolète : il n'écrit pas de donnée et impose des volumes 2026 interdits par V9. Sa retraite est nominative et vérifiée par le validateur G2 ; les fichiers source restent couverts par leurs méthodes indépendantes. G2 reste FAIL : 64 méthodes utiles, 67 transferts GitHub non vérifiés. Actions désactivé.

# 20 octobre 2026 — V9, Connected Kerb opérateur UK

Le collecteur API opérateur et l'audit de snapshot sont isolés ; la pagination déclarée et les références exactes sont testées hors réseau. Le résultat reste non publié vers V9. G2 reste FAIL : 63 méthodes utiles, 68 transferts GitHub non vérifiés. Actions désactivé.

# 22 octobre 2026 — V9, Connected Kerb app UK

La branche de reconstruction a été avancée sans conflit vers le cahier des charges permanent. Le collecteur invité et le rapprochement Connected Kerb utilisent désormais le snapshot opérateur signé ; les offres restent candidates et le cas sans prix demeure explicite. G2 reste FAIL : 62 méthodes utiles, 69 transferts GitHub non vérifiés. Actions désactivé.

# 22 octobre 2026 — V9, Connected Kerb daily

La chaîne historique complète opérateur → audit → app → rapprochement et son état documentaire sont exécutés sur fixtures avec dépendance signée. Aucun push main n'est reproduit. G2 reste FAIL : 61 méthodes utiles, 69 transferts GitHub non vérifiés. Actions désactivé.

# 22 octobre 2026 — V9, Eco-Movement PCPR UK

Le collecteur inline archivé est extrait et exécuté hors checkout avec son audit sur deux pages de fixture. Les tarifs UK restent au stade candidat, sans classement Direct tant que les conditions historiques manquent. G2 reste FAIL : 59 méthodes utiles, 70 transferts GitHub non vérifiés. Actions désactivé.

# 22 octobre 2026 — V9, Electra plateforme France

Le constructeur historique national a été isolé avec ses données d'identité et d'association archivées. Pagination et SHA des sorties sont vérifiés ; le seuil arbitraire de 1 000 offres a été retiré. Les tests hors réseau couvrent EVSE exact, échec de page, interruption et corruption. G2 reste FAIL : 58 méthodes utiles, 71 transferts GitHub non vérifiés. Actions désactivé.

# 22 octobre 2026 — V9, EnergyVision Belgique

Les méthodes DATEX, CPO indépendante et rapprochement NAP s'enchaînent hors checkout sur tous les fichiers NAP référencés. Un tarif de station reste hors EVSE et hors classement. Les anciens rejets de volume ont été retirés ; tests hors réseau sur un PDC et échecs techniques réussis. G2 reste FAIL : 55 méthodes utiles, 72 transferts GitHub non vérifiés. Actions désactivé.

# 22 octobre 2026 — V9, eCarUp Suisse par coordonnées

Le script historique de rapprochement se déroule hors checkout avec états archivés. Les fixtures distinguent correspondance sûre, prix ambigu et absence de candidat ; seuls les prix identiques des connecteurs publics dans la tolérance historique sont retenus. G2 reste FAIL : 54 méthodes utiles, 73 transferts GitHub non vérifiés. Actions désactivé.

# 22 octobre 2026 — V9, eCarUp Suisse propriétaire exact

Le rapprochement par Hubject ID exact et la sélection de son artefact immuable sont raccordés à la chaîne eCarUp. L'adaptateur géographique exige maintenant cet état validé et rejette absence ou SHA incorrect. Les tests restent hors réseau. G2 reste FAIL : 53 méthodes utiles, 74 transferts GitHub non vérifiés. Actions désactivé.

# 22 octobre 2026 — V9, finalisation eCarUp Suisse

Le constructeur final utilise l'état signé du rapprochement et compte séparément bornes tarifées, accès restreints et cas non résolus. La constante historique de 6 764 EVSE a été retirée ; les identités et les SHA restent contrôlés. G2 reste FAIL : 52 méthodes utiles, 75 transferts GitHub non vérifiés. Actions désactivé.

# 22 octobre 2026 — V9, MOVE Suisse CCI/SOC/MMN

Les trois finaliseurs CPO réutilisent un adaptateur isolé commun et les sources CCI/SOC archivées. Les tests couvrent segments AC/DC, cas MMN AC et prises non résolues, sans nouvelle enquête tarifaire. G2 reste FAIL : 49 méthodes utiles, 78 transferts GitHub non vérifiés. Actions désactivé.

# 22 octobre 2026 — V9, clôtures Plenitude Suisse

Les deux méthodes historiques de rapprochement résiduel et de classification restreinte utilisent un snapshot officiel immuable, sans nouvelle collecte ni enquête tarifaire. Les identifiants et tarifs déjà vérifiés sont conservés. G2 reste FAIL : 47 méthodes utiles, 79 transferts GitHub non vérifiés. Actions désactivé.

# 22 octobre 2026 — V9, inventaires Maroc FastVolt/Kilowatt

Deux inventaires publics historiques sont migrés sans collecte live ; leurs candidats, exclusions et provenance sont testés sur fixtures. G2 reste FAIL : 45 méthodes utiles et 81 transferts GitHub non vérifiés. Actions désactivé.

# 22 octobre 2026 — V9, diagnostic Kilowatt

Le rapport historique de regroupement géographique consomme le dernier inventaire signé, sans modification de Production ni promotion de correspondance. G2 reste FAIL : 44 méthodes utiles et 82 transferts GitHub non vérifiés.

# 22 October 2026 - V9 Kilowatt tariff overlay

The archived constructor consumes a signed inventory and preserves existing evidence. Only the fixed station-count gate was removed. G2 FAIL: 43 useful methods and 83 unverified handoffs.

# 22 October 2026 - V9 Swiss EBS closeout

The archived exact-location method now consumes a signed first pass. Existing priced EVSE are preserved and the separately archived Sahli proof is retained. G2 FAIL: 42 useful methods and 84 unverified handoffs.

# 22 October 2026 - V9 Swiss CPI closeout

The preserved exact-EVSE finalizer runs off checkout. Historical fixed totals were removed while same-snapshot identity checks remain. G2 FAIL: 41 useful methods and 85 unverified handoffs.

# 22 October 2026 - V9 Swiss PowerUp/Monta collector

The existing public collector runs off checkout and exposes original source IDs to validate exact set relations. No volume threshold or live provider request was used. G2 FAIL: 40 useful methods and 86 unverified handoffs.

# 22 October 2026 - V9 Swiss PowerUp residual closeout

The preserved direct-page method consumes a signed first pass, keeps other EVSE unchanged and uses no fixed historical total. G2 FAIL: 39 useful methods and 87 unverified handoffs.

# 22 October 2026 - V9 Swisscharge shards

The preserved four-shard collector has isolated retry state and immutable merge validation. No live provider request was made. G2 FAIL: 38 useful methods and 88 unverified handoffs.

# 22 October 2026 - V9 legacy audit retirement

The fixed-tariff refresh audit was archived because it infers management from workflows removed by V9. A fixture demonstrates the dependence, while the historical code remains restorable. G2 FAIL: 37 useful methods, 88 unverified handoffs.

2026-10-22 — V9 G2 Greenspot France : methode historique executee hors checkout, fixture et tests cibles PASS ; G2 reste FAIL (36 methodes utiles, 89 transferts GitHub non verifies). Actions Data Lab inactif ; aucune publication. Voir `memory/V9_REBUILD_PROGRESS.md`.

2026-10-22 — V9 G2 REVE Espagne stream : collecte historique isolee, reprises par checkpoint SHA, aucun artefact partiel ; 22 tests PASS, G2 reste FAIL (35 methodes, 90 transferts GitHub non verifies). Actions inactif ; voir `memory/V9_REBUILD_PROGRESS.md`.

2026-10-22 — V9 G2 REVE national v2 : chaine historique isolee, fixture compilee, controles SHA/pagination et suppression des seuils de volume ; 11 tests PASS. G2 reste FAIL (34 methodes, 91 transferts GitHub non verifies). Voir `memory/V9_REBUILD_PROGRESS.md`.

2026-10-22 — V9 G2 Delmonicos : surveillance historique executee hors checkout sur fixture source, valeurs archivees preservees, contexte change et prix modifie rejetes ; 2 tests PASS. G2 reste FAIL (33 methodes, 92 transferts GitHub non verifies). Voir `memory/V9_REBUILD_PROGRESS.md`.

2026-10-22 — V9 G2 France fixed watch : trois sources historiques executees hors checkout, tarif archive et contextes preserves ; 2 tests PASS. G2 reste FAIL (32 methodes, 93 transferts GitHub non verifies). Voir `memory/V9_REBUILD_PROGRESS.md`.

2026-10-22 — V9 G2 tarifs Espagne secondaires : methodes EMT/Endesa/Plenergy executees hors checkout sur fixtures archivees ; changement de contexte/PDF/prix refuse, 2 tests PASS. G2 reste FAIL (31 methodes, 94 transferts GitHub non verifies). Voir `memory/V9_REBUILD_PROGRESS.md`.

2026-10-22 — V9 G2 Espagne core : cinq parseurs historiques executes hors checkout, fixture issue des valeurs archivees, mutation tarifaire rejetee ; 2 tests PASS. G2 reste FAIL (30 methodes, 95 transferts GitHub non verifies). Voir `memory/V9_REBUILD_PROGRESS.md`.

2026-10-22 — V9 G2 BFC fixed tariffs : cinq surveillances et SIED70 executes hors checkout sur fixtures archivees ; contexte et prix changes refuses, 2 tests PASS. G2 reste FAIL (29 methodes, 96 transferts GitHub non verifies). Voir `memory/V9_REBUILD_PROGRESS.md`.

2026-10-22 — V9 G2 tarifs France core : Lidl, STATIONS-E et eborn executes hors checkout sur fixtures de valeurs archivees ; mutation refusee, 2 tests PASS. G2 reste FAIL (28 methodes, 97 transferts GitHub non verifies). Voir `memory/V9_REBUILD_PROGRESS.md`.

2026-10-22 — V9 G2 France secondary : INDIGO, Interparking, SEOLIS executes hors checkout sur tarifs archives ; changement de prix rejete, 2 tests PASS. G2 reste FAIL (27 methodes, 98 transferts GitHub non verifies). Voir `memory/V9_REBUILD_PROGRESS.md`.

2026-10-22 — V9 G2 OZECAR France : collecteur producteur/Monta execute hors checkout sur fixtures, erreurs techniques visibles, identite EVSE et fichiers controles ; 7 tests PASS. G2 reste FAIL (26 methodes, 99 transferts GitHub non verifies). Voir `memory/V9_REBUILD_PROGRESS.md`.

2026-10-22 — V9 G2 Zephyre : extracteur/compilateur historiques executes hors checkout sur fixture archivee, EVSE exact et erreurs techniques controles, zero offre Direct permis ; 2 tests PASS. G2 reste FAIL (25 methodes, 100 transferts GitHub non verifies). Voir `memory/V9_REBUILD_PROGRESS.md`.

2026-10-22 — V9 G2 Ze-Watt : extraction/compilation historiques hors checkout, deux EVSE archives exacts, pagination et erreurs controlees, zero offre Direct permis ; 2 tests PASS. G2 reste FAIL (24 methodes, 101 transferts GitHub non verifies). Voir `memory/V9_REBUILD_PROGRESS.md`.

2026-10-22 — V9 G2 Atlante FR/IT : collecteur historique hors checkout, deux sorties et reprise par cache SHA sur fixture ; 2 tests PASS. G2 reste FAIL (23 methodes, 102 transferts GitHub non verifies). Voir `memory/V9_REBUILD_PROGRESS.md`.

2026-10-22 — V9 G2 Belgique gap archive : replay exact du constructeur et des sorties 2026-09-28, refus de toute mutation de prix ou d entree. Import Python des adaptateurs corrige et teste en sous-processus reel ; 19 tests cibles PASS. G2 reste FAIL (22 methodes, 103 transferts GitHub non verifies). Voir `memory/V9_REBUILD_PROGRESS.md`.

2026-10-22 — V9 G2 Electroverse probe cible : investigation ponctuelle de deux stations classee historique inactive ; scripts, rapport, mapping et cache conserves. Test de la disposition 1 PASS. G2 reste FAIL (21 methodes, 103 transferts GitHub non verifies). Voir `memory/V9_REBUILD_PROGRESS.md`.

2026-10-22 — V9 G2 IZIVIA FAST : scripts historiques executes hors checkout sur fixture Dole archivee, quatre sorties, prix manquant explicite et erreurs techniques bloquees ; 17 tests cibles PASS. G2 reste FAIL (20 methodes, 104 transferts GitHub non verifies). Voir `memory/V9_REBUILD_PROGRESS.md`.

2026-10-22 — V9 G2 audit France traite : methode historique rejouee hors checkout sur entrees archivees ; rapport et empreintes conserves, 2 tests reels PASS. G2 reste FAIL (19 methodes, 105 transferts GitHub non verifies). Voir `memory/V9_REBUILD_PROGRESS.md`.

2026-10-22 — V9 G2 Soregies Mobilites : collecteur officiel hors checkout, planchers de lignes retires, erreur HTTP 503 correctement rejetee, montants marketing archives non generalises ; 3 tests PASS. G2 reste FAIL (18 methodes, 106 transferts GitHub non verifies). Voir `memory/V9_REBUILD_PROGRESS.md`.

2026-10-22 — V9 G2 audit Electra residuel : script historique rejoue hors checkout avec SHA source valide ; cas non attribues conserves, zero publication automatique, 2 tests PASS. G2 reste FAIL (17 methodes, 107 transferts GitHub non verifies). Voir `memory/V9_REBUILD_PROGRESS.md`.

2026-10-22 — V9 G2 e-Vadea : decouverte image/OCR et grille historique executees hors checkout sur fixture archivee ; prix/frais changes et image absente rejetes, 16 tests cibles PASS. G2 reste FAIL (16 methodes, 108 transferts GitHub non verifies). Voir `memory/V9_REBUILD_PROGRESS.md`.

2026-10-22 — V9 G2 Powerdot : methode officielle hors checkout, CSV vide permis avec schema valide, Direct et abonnement Electroverse separes ; 9 tests cibles PASS. G2 reste FAIL (15 methodes, 109 transferts GitHub non verifies). Voir `memory/V9_REBUILD_PROGRESS.md`.

2026-10-22 — V9 G2 Shell Recharge : cinq pages configurees requises en fixture, ancien etat partiel conserve, nouvelle sortie rejetee si page/HTTP/prix change ; 2 tests PASS. G2 reste FAIL (14 methodes, 110 transferts GitHub non verifies). Voir `memory/V9_REBUILD_PROGRESS.md`.

2026-10-22 — V9 G2 TotalEnergies officiel : methode historique isolee, absence de garde de volume, faux prix promotionnel corrige, 16 tests cibles PASS. G2 FAIL (13 methodes, 111 transferts GitHub non verifies). Voir `memory/V9_REBUILD_PROGRESS.md`.

2026-10-22 — V9 G2 MobiSDEC officiel : methode historique isolee, garde de volume retire, fixture CSV reduite et erreurs techniques verifiees ; 16 tests cibles PASS. G2 FAIL (12 methodes, 112 transferts GitHub non verifies). Voir `memory/V9_REBUILD_PROGRESS.md`.

2026-10-22 — V9 G2 IZIVIA officiel : FAST/Express/Grand Lyon/Pass executes hors checkout sur fixtures archivees ; 16 tests PASS. G2 FAIL (11 methodes, 113 transferts GitHub non verifies). Voir `memory/V9_REBUILD_PROGRESS.md`.

2026-10-22 — V9 G2 flux ouverts UK : douze sources historiques isolees, pagination incomplete et PoGo partiel bloques ; 17 tests cibles PASS. G2 FAIL (10 methodes, 114 transferts GitHub non verifies). Voir `memory/V9_REBUILD_PROGRESS.md`.

- 2026-10-22 : bundle suisse et intégration publique V9 testés hors ligne sur instantané signé ; gardes de volumes retirés ; G2 toujours FAIL (8 méthodes utiles).
- 2026-10-22 : AVIA guest Suisse migre hors checkout, reconstitution nationale et erreurs techniques testées ; G2 FAIL (7 méthodes utiles).
- 2026-10-22 : closeouts suisses AGR/Atlas/SOC migres hors checkout sur archives et fixtures ; G2 FAIL (6 méthodes utiles).
- 2026-10-22 : EVGO Maroc migre sur fixtures archivée et réduite ; versions complètes et champs statut vérifiés ; G2 FAIL (5 méthodes).
- 2026-10-22 : Load Motion France (quatre tenants et compilation) migre sur fixtures archivées ; G2 FAIL (4 méthodes).
- 2026-10-22 : quatre audits/orchestrations historiques sortis nominativement de G2 actif, avec preuves et destination G5/G6 ou remplacement ; G2 FAIL sur 120 transferts GitHub.
- 2026-10-23 : aperçu local de préproduction raccordé au candidat préparé Production ; carte physique, filtres et prix explicitement non calculés testés hors ligne. G7 reste FAIL, aucun déploiement.
- 2026-10-23 : raccordement du candidat au shell TCC et packaging isolé vérifiés sur fixtures ; intégrité station/EVSE/prise/offre renforcée dans Data Lab et Production. G3/G4/G7 restent FAIL en attente des autres sources, du transfert GitHub et du navigateur complet.
- 2026-10-23 : Belib FR normalisé à partir de son archive, avec profils bruts et portée par prise, opérateur et enseigne séparés ; bundle préparé puis importé en préproduction locale. G3/G4/G7 restent FAIL.
- 2026-10-23 : Atlante Italie normalisé depuis son archive nationale, EVSE/prise/offres exacts et tarifs bruts non évalués ; bundle préparé puis importé hors ligne. G3/G4 restent FAIL.
- 2026-10-23 : replay navigateur réel de la carte TCC sur candidat isolé IONITY FR/GB, sources/date et offres non calculées vérifiées ; captures versionnées en Production. G7/G8 restent FAIL, aucune URL distante ni publication publique.

- 2026-10-23 — Reconstruction V9 G3/G7 : normalisation de l'archive Zéphyre ePowerDirect à EVSE exact et connecteur technique sans ID physique inventé ; candidat isolé à cinq sources validé dans Firefox sur FR/GB/IT. Tarifs bruts non évalués, portes G3/G5/G6/G7/G8 encore FAIL. Voir `V9_REBUILD_PROGRESS.md`.
- 2026-10-23 — Reconstruction V9 G5 : replay exact du crosswalk Electra NL archivé avec station/EVSE/prise/tariffKey, 51 lignes vérifiées sans seuil ; validation des identifiants connecteurs officiels seulement lorsqu'ils sont fournis par la source. Portes G5/G6 toujours FAIL.
- 2026-10-23 — Reconstruction V9 G3 : normaliseur Driveco/Partner de l'archive exacte, EVSE non tarifés conservés et frais complexes bruts, import six sources et navigateur isolé validés. Aucune coordonnée ou somme facturée inventée.
- 2026-10-23 — Reconstruction V9 G3/G7 : archive OZECAR Corse normalisée avec EVSE exacts et offres brutes ; candidat sept sources et navigateur Corse vérifiés sans prix ou statut live inventé. Portes non promues.
- 2026-10-23 — Reconstruction V9 G7 : correction de la liste qui omettait les prises sans puissance propre ; fiches EVSE exactes désormais visibles et offres brutes limitées à leur portée. Tests Node et navigateur isolé PASS, G7 reste FAIL globalement.
- 2026-10-23 — Reconstruction V9 G3/G6/G7 : Midhope UK normalisé à quatre EVSE/prises exacts ; oracle historique de calcul PASS, mais offre maintenue hors classement du candidat faute d'entrée de durée/puissance prouvée dans l'interface. Navigateur isolé à huit sources PASS, portes globales FAIL.

- 2026-10-23 : construction canonique batch multi-pays et France IRVE statique, avec bundle immuable ; rapport de jointure exacte France intégré au candidat isolé Production. G3–G8 toujours FAIL.

- 2026-10-23 : raccordement prudent des offres IONITY FR et Atlante IT ENERGY simple au moteur du candidat V9 ; garde navigateur sur identité, SHA et structure, autres offres exclues du classement. Firefox multi-pays PASS ; portes G6–G8 ouvertes.

- 2026-10-23 : statistiques de couverture des jointures nationales exactes par source et canal, sans seuil ni propagation de prix ; G5 toujours ouvert.

- 2026-10-23 : Belgique NAP ajoutée au batch canonique multi-pays ; pagination archivée contrôlée et variantes sources conservées. Parcours navigateur 13 sources PASS sur candidat isolé, portes G3/G7/G8 ouvertes.

- 2026-10-23 : raccordement des offres Belgique NAP énergie simple et TVA prouvées au moteur V9, sans prix pour les composantes non couvertes ; navigateur multi-pays PASS, G6–G8 ouverts.

- 2026-10-23 : DOT-NL national rejoint le batch canonique et le candidat isolé sept pays ; identités et tarifs OCPI exacts préservés, prix NL encore non évalués. Import et navigateur PASS, portes aval ouvertes.

- 2026-10-23 : catalogue tarifaire DOT-NL dédupliqué ; sous-ensemble énergie seule raccordé au moteur avec oracle du pas Wh et contrôle de prise exacte. Candidat sept pays testé, G6–G8 ouverts.

- 2026-10-23 : paramètres véhicule modifiables dans le candidat V9 isolé ; vérification Node et navigateur multi-pays PASS. Aucune activation Actions ni publication publique.

- 2026-10-23 : la simulation V9 préproduction refuse une saisie véhicule invalide au lieu de calculer avec une valeur implicite ; navigateur multi-pays PASS.

- 2026-10-23 : sous-ensemble OCPI composé déjà prouvé raccordé au candidat isolé ; frais détaillés et offres incomplètes hors classement. Preuves eMSP exactes rejouées par canal sans propagation de prix. Portes G5–G8 ouvertes.

- 2026-10-23 : restriction OCPI `start_date` seule et valide intégrée avec rejet des dates futures ; candidat isolé et contrôles d'import/jointure repassés. Aucun prix hors preuve promu.

- 2026-10-23 : preuves eMSP exactes transformées en source brute canonique et importées dans le candidat isolé, sans calcul non prouvé ni remplacement des stations nationales. Navigateur multi-pays PASS ; G5/G7/G8 restent ouverts.

- 2026-10-23 : calcul Electroverse eMSP limité aux EVSE exacts et aux règles compilées historiquement prouvées ; oracles complets et navigateur multi-pays PASS. Les autres offres restent incalculables.

- 2026-10-23 : durée de charge estimée désormais visible avec les offres calculables dans le candidat isolé ; Firefox sept pays et mobile PASS, performance NL encore insuffisante pour G7/G8.

- 2026-10-23 : présélection spatiale des fragments du candidat, avec fermeture transitive par identifiants exacts ; navigateur sept pays sans perte d’offres, performances améliorées mais G7/G8 ouverts.

- 2026-10-24 : trois archives PCPR UK normalisées par un module commun, avec offres brutes exactes et sans tarif inventé ; candidat isolé 18 sources testé sur navigateur.

- 2026-10-24 : calcul Source EV PCPR UK limité aux prises à puissance et tarif exacts, à partir du convertisseur et des oracles historiques ; Blink/Allego restent bruts. Firefox multi-pays PASS.

- 2026-10-24 : sélection multiple des opérateurs et frais temporels Electroverse contrôlés dans Firefox ; scénario PCPR avec date et frais fixes confirmé par oracle.

- 2026-10-24 : REVE Espagne ajouté au canonique depuis l’archive et le manifeste validés ; 19 sources/huit pays dans le candidat navigateur isolé, aucun EVSE officiel ni tarif inventé.

- 2026-10-24 : archive EVGO Maroc ajoutée au canonique avec identités natives et puissance inconnue ; candidat isolé neuf pays validé au navigateur sans prix artificiel.

- 2026-10-24 : restrictions OCPI date, jour et horaire raccordées au moteur pour les offres néerlandaises à prise exacte, avec refus indépendant des recettes mutées.

- 2026-10-24 : seuils OCPI de durée et puissance vérifiés indépendamment dans le candidat DOT-NL ; sessions hors borne explicitement incalculables.

- 2026-10-24 : commande Production unique pour reconstruire bundle, jointures eMSP, import et paquet V9 isolé depuis les deux dépôts ; replay navigateur neuf pays réussi.

- 2026-10-24 : paquet de préproduction V9 spatial à index et fragments SHA, reconstruction complète locale et parité navigateur neuf pays ; aucun déploiement ni activation Actions.

- 2026-10-24 : IONITY Direct FR/DE/IT/GB raccordé au calcul kWh sur prise et prix archivés exacts, avec GBP et conversion conditionnelle ; contrôle navigateur neuf pays.

# 25 octobre 2026 — préproduction V9 compressée et inventaire Tesla épinglé

- Production `a40faac`/`35d3008`/`4b93ea6`/`3238f64` reconstruisent hors checkout le paquet neuf pays avec fragments gzip SHA, racine V9, directives noindex et import Tesla/Mac historique contrôlé par SHA sans tarif non prouvé. Firefox desktop/mobile PASS ; hébergement seulement local. G2–G8 FAIL, Actions Data Lab désactivé et site public inchangé. Preuves et prochaine opération dans `V9_REBUILD_PROGRESS.md`.

# 25 octobre 2026 — abonnements candidats isolés

- Production `3238f64` interdit aux anciens catalogues et sélections Electra+ d'entrer dans l'aperçu V9 ; paquet local final et Firefox neuf pays/mobile validés, sans hébergement ni déploiement public. Voir `V9_REBUILD_PROGRESS.md`.

# 25 octobre 2026 — aperçu V9 sans boucle de secours

- Production `84e59e9` ferme l'échec de démarrage dans la copie isolée ; le parcours Firefox valide le cas HTTP 503 en plus des neuf pays/mobile. Aucun site public ou transfert GitHub activé. Voir `V9_REBUILD_PROGRESS.md`.

# 25 octobre 2026 — composantes PCPR britanniques dans le candidat

- Production `ebe7561` raccorde les composantes OCPI historiquement prouvées (énergie, temps, fixe, stationnement) et empêche le classement si une durée facturée manque. Session complète, parité oracle, candidat neuf pays et navigateur desktop/mobile PASS ; G2–G8 restent FAIL, aperçu seulement local. Preuve dans `V9_REBUILD_PROGRESS.md` et Production `docs/v9-rebuild/evidence/uk-pcpr-compound-candidate-20261025.md`.

# 25 octobre 2026 — correspondance Electra NL exacte, offres brutes conservées

- Data Lab ajoute le replay technique de l'archive Electra NL sur prise DOT-NL exacte ; Production `1281cf5` ajoute la source au candidat et réunit les offres brutes de toutes les provenances. Replay 21 sources/neuf pays, tests d'intégrité et Firefox desktop/mobile PASS ; aucun prix Electra NL calculé faute de composantes complètes. G2–G8 FAIL, aperçu local seulement. Voir `V9_REBUILD_PROGRESS.md`.

- Production `664cf3b` conserve aussi la preuve et l'identifiant source de prise jusqu'à l'interface ; Firefox neuf pays/mobile et contrôle d'intégrité PASS sur le nouveau paquet isolé. Aucun tarif partiel promu. Détails dans `V9_REBUILD_PROGRESS.md`.

# 25 octobre 2026 — oracle de session complète sur le paquet V9

- Production `b3072de` valide sur le paquet isolé une session à frais combinés, trois canaux, abonnement, conversion explicite et classement. Données de test synthétiques, aucun prix fournisseur créé ; G2–G8 FAIL. Voir `V9_REBUILD_PROGRESS.md`.

# 25 octobre 2026 — fragments français proches

- Production `ebbd9f4` filtre les fragments français dans l'aperçu V9 ; parité des zones contrôlées, Firefox neuf pays/mobile et intégrité PASS. Paquet local uniquement, G2–G8 FAIL. Voir `V9_REBUILD_PROGRESS.md`.

# 25 octobre 2026 — prix incomplets refusés par le moteur

- Production `750073c` rejette explicitement les bornes OCPI sans oracle et les offres marquées incomplètes. Calculs combinés prouvés inchangés ; tests et Firefox neuf pays/mobile PASS, paquet seulement local et G2–G8 FAIL. Voir `V9_REBUILD_PROGRESS.md`.

# 25 octobre 2026 — moteur unifié et oracle de session combinée

- Production `f2b2f14`, `dddb961`, `bbbab11` : même moteur pour les tests source et le paquet ; oracle hors ligne des frais combinés, SOC et minimum PASS. Portes G2–G8 FAIL, Actions désactivé. Voir `V9_REBUILD_PROGRESS.md`.

# 25 octobre 2026 — énergie manquante explicitement incalculable

- Production `507b726` refuse un prix énergie calculé avec kWh absent ; tests et navigateur local neuf pays/mobile PASS. Bundle source inchangé, G2–G8 FAIL. Voir `V9_REBUILD_PROGRESS.md`.

# 25 octobre 2026 — archives OCPI UK Gridserve et Ubitricity

- Data Lab `b330d126d` et Production `9a2aa0f` : normalisation commune des archives UK, références absentes signalées, offres hors calcul ; candidat 23 sources, import et navigateur local PASS. G2–G8 FAIL, Actions désactivé. Voir `V9_REBUILD_PROGRESS.md`.

# 25 octobre 2026 — refus des durées manquantes sur les frais temporels

- Production `666e7e9` refuse les totaux partiels de connexion, charge ou stationnement sans durée ; tests et navigateur 23 sources PASS. G2–G8 FAIL. Voir `V9_REBUILD_PROGRESS.md`.

# 25 octobre 2026 — oracle belge sans seuil historique

- Production `cefe1fe` conserve les vérifications tarifaires et techniques NAP sans égalité de volumes ; suite hors ligne PASS. Voir `V9_REBUILD_PROGRESS.md`.

# 25 octobre 2026 — garde des paliers OCPI

- Production `3b25f60` couvre les bandes énergie, durée de charge et stationnement dans le refus de sessions incomplètes ; tests et navigateur local PASS. Voir `V9_REBUILD_PROGRESS.md`.

# 25 octobre 2026 — jointure exacte UK dans le navigateur

- Production `2e17948` vérifie la portée EVSE/prise Gridserve et Ubitricity dans le candidat 23 sources ; navigateur desktop/mobile PASS, aucun prix inventé. Voir `V9_REBUILD_PROGRESS.md`.

# 25 octobre 2026 — intégrité relationnelle des fragments V9

- Production `87807c9` contrôle toutes les relations station/EVSE/prise/offre et les collisions entre fragments ; paquet 23 sources et test de mutation PASS. Voir `V9_REBUILD_PROGRESS.md`.

# 25 octobre 2026 — identités EVSE explicites dans la carte

- Production `52334cd` sépare l'identifiant officiel, l'UID source et la clé technique ; tests et navigateur local PASS. Voir `V9_REBUILD_PROGRESS.md`.

# 25 octobre 2026 — position actuelle en préproduction

- Production `e19377e` vérifie l'accès à la position via une fixture navigateur ; recette locale neuf pays/mobile PASS. Voir `V9_REBUILD_PROGRESS.md`.

# 25 octobre 2026 — oracle source historique

- Production `e826898` rejoue les 36 évaluations Midhope à entrées archivées identiques et refuse les durées ambiguës ; paquet local, intégrité et navigateur neuf pays/mobile PASS. Les autres oracles historiques restent à vérifier et G2–G8 restent FAIL. Voir `V9_REBUILD_PROGRESS.md`.

# 25 octobre 2026 — composants OCPI dans le moteur reconstruit

- Production `9d89e55` rejoue l'oracle transversal OCPI en source et dans le paquet ; Production `2a43b44` retire une ancienne borne arbitraire Electroverse. L'ancien test Electroverse requiert encore son snapshot absent et n'est pas déclaré PASS. Voir `V9_REBUILD_PROGRESS.md`.

# 25 octobre 2026 — sessions invalides et empaquetage isolé

- Production `0b4b308` refuse les mesures de session négatives/non numériques et permet le renouvellement contrôlé d'un paquet V9 isolé. Tests tarifaires, intégrité et Firefox neuf pays/mobile PASS ; G2–G8 restent FAIL. Voir `V9_REBUILD_PROGRESS.md`.

# 25 octobre 2026 — archive Powerdot dans le candidat

- Data Lab `47cbe3b78` conserve les identifiants source et les tarifs bruts Powerdot sans jointure PDC présumée. Production `4441afe` vérifie le candidat local 24 sources/neuf pays, ses prises exactes et l'absence de prix promu. Tests, import SHA et Firefox desktop/mobile PASS ; G2–G8 restent FAIL. Voir `V9_REBUILD_PROGRESS.md`.

# 25 octobre 2026 — routage pays Powerdot corrigé

- Le candidat local précédent est supplanté : Data Lab `375e1c30f` sépare FR/BE et `02400ca4f` verrouille le pays du schéma canonique. Production `571e925` valide le candidat 25 sources, les parcours Firefox français et belge et l'absence de prix inventé. G2–G8 restent FAIL ; aucune URL distante. Voir `V9_REBUILD_PROGRESS.md`.

# 25 octobre 2026 — frais conditionnels sans total partiel

- Production `f0dd024` refuse les frais conditionnels ou après charge lorsque les mesures requises manquent ; tests tarifaires et Firefox du paquet local 25 sources PASS. G2–G8 restent FAIL. Voir `V9_REBUILD_PROGRESS.md`.

# 25 octobre 2026 — fuseau et fin de charge explicites

- Production `c2f24b7` calcule une exonération horaire seulement avec l'heure locale tarifaire et une fin de charge connue ou déductible explicitement ; paquet local 25 sources, oracles et Firefox PASS. G2–G8 restent FAIL. Voir `V9_REBUILD_PROGRESS.md`.

# 25 octobre 2026 — fenêtres après charge mal formées

- Production `ffac324`, `7571434`, `dd20df8` refuse les fenêtres tarifaires invalides, avec tests source, paquet isolé et Firefox neuf pays/mobile PASS. G2–G8 restent FAIL ; aucune publication distante. Voir `V9_REBUILD_PROGRESS.md`.

# 25 octobre 2026 — pays source vérifié à l'import Production

- Production `cd50f96` rejette un bundle au SHA recalculé avec pays canonique incohérent ; sept tests d'import et les sources réelles Powerdot FR/BE PASS. G2–G8 restent FAIL. Voir `V9_REBUILD_PROGRESS.md`.
- 2026-10-25 : source IRVE France V9 : décisions `exclude_non_public` du registre d'accès historique ajoutées au canonique avec SHA de provenance ; stations brutes conservées, exclusion réservée à la carte. Le dérivé eMSP exact hérite du champ national. Tests ciblés et replay isolé 25 sources/neuf pays réussis ; aucune porte G2–G8 promue.
- 2026-10-25 : Production `979e3fe` affiche désormais le détail des composantes facturées du moteur et la préautorisation non facturée séparément ; oracles empaquetés, scénario historique, Firefox neuf pays/mobile et contrôle SHA PASS sur le candidat isolé 25 sources, sans publication.
- 2026-10-25 : archive UK Eco-Movement ajoutée au canonique commun en offres brutes exactes (`b68d96c0a`), sans prix promu ; Production `375c8de` vérifie leur portée et la carte. Bundle isolé 26 sources/neuf pays, SHA, oracles et Firefox desktop/mobile PASS. G2–G8 restent FAIL ; 120 transferts GitHub non vérifiés, Actions désactivé, aucune URL distante ni publication publique.
- 2026-10-25 : Production `c05c971` enlève la limite de 20 stations visibles dans la carte V9 et rend les fiches par pages de 80 ; Firefox neuf pays/mobile confirme tous les points de la requête Paris. Candidat local uniquement, G2–G8 FAIL.
- 2026-10-25 : Production `6a4bf9f` affiche un état de chargement accessible pendant les recherches V9 ; Firefox neuf pays/mobile et contrôle SHA/hébergement du paquet local 26 sources PASS. Aucune URL distante ni publication publique ; G2–G8 FAIL.
- 2026-10-25 : Production `938ccfb` enlève le plafond de stations des requêtes denses sans modifier le budget d'itinéraires ; fixture de croissance, paquet SHA et oracle PASS. Site local `site-uncapped`, G2–G8 FAIL.


2026-10-26 — Reconstruction V9 : candidat local 27 sources ; correction du tri global par lots bornés et carte indépendante de la page. Tests ciblés, huit parcours tarifaires réels et neuf pays/mobile PASS sur `site-ranked-final`. Une mesure Amsterdam 100 km a dépassé le délai Selenium ; sélection d'itinéraires mise en cache et chargement limité à quatre fragments, nouveau paquet `site-bounded-fetch` en mesure. Ne pas déclarer G7/G8 complets. Pilote Actions IONITY précisé et dry-run local seulement ; Actions toujours désactivé, aucun main ni site public modifié. Changements de cette reprise encore locaux ; voir [V9_REBUILD_PROGRESS.md](V9_REBUILD_PROGRESS.md) pour preuves et prochaine opération.

Production `1dbbbbb` sauvegarde le lot global et le cache de formateurs G6 ; paquet local courant `site-g6-cached-formatters`, benchmark Amsterdam encore en cours. Le dossier pilote IONITY et le journal sont préparés pour synchronisation sur `rebuild/v9-20261020` uniquement. Aucun main ni site public modifié.

# 26 October 2026 — Exact offer scopes and global pagination

- Production `ee6b2af` is saved on `rebuild/v9-20261020`: equal-price offers on distinct EVSE/connector scopes survive deduplication, raw offers remain visible alongside calculated offers. Eight exact tariff Firefox journeys, nine-country/mobile navigation, full-session/global-ranking oracles and six packaging tests pass. Candidate `site-exact-offer-scopes` retains the immutable 27-source bundle. Paris 100 km: 9.536 s; Amsterdam 100 km: 82.066 s, further 10 km steps ongoing. Dense-search latency remains open. Main and the public site are untouched; Actions remains disabled. Follow-up G5/G6 tests now cover EVSE-only eligibility and distinct validity windows; not yet packaged or committed. See [V9_REBUILD_PROGRESS.md](V9_REBUILD_PROGRESS.md).


# 26 October 2026 — Exact eligibility saved; documented threshold fees in progress

- Production `dcbba5a` is pushed on the reconstruction branch. Exact EVSE evaluation groups, distinct validity windows and reused immutable offer sort keys pass the packaged oracle, nine targeted tests, eight tariff Firefox journeys, nine-country/mobile smoke and local feedback UI checks. `http://127.0.0.1:8769/` now serves `site-exact-eligibility` on this Mac only. Amsterdam 100→20 km: 72.301/53.419/46.305/42.309/34.217/21.732/14.961/11.945/7.177 s; later radii use warm cache. Dense searches remain slow; no radius is silently reduced.
- G6 continuation found archived `afterMinutes` mechanisms missing from the rebuilt engine. Local work restores proved duration phases, thresholds, whole-session/night caps and visible fee components using the existing October 11 library/oracles. Unproved semantics remain incalculable: 84 untouched archived offers, 588 evaluations, zero silently calculated results. Synthetic caps, DST, minimum and segmented grace tests pass. `site-after-minutes` is prepared for browser checks but is not yet committed or served. No canonical source or supplier price changed. See [V9_REBUILD_PROGRESS.md](V9_REBUILD_PROGRESS.md).



**G6 sauvegardé, G3 Allemagne préparé, 26 octobre :** Production `5e4c3b7` poussé : mécanismes après seuil/plafond nocturne, garde du chemin tarif fixé au début, détail des frais et tests historiques. Recettes Firefox huit tarifs, neuf pays/mobile et signalement PASS ; intégrité/hébergement PASS (3 267 fichiers, 263 840 133 octets). L’aperçu local 127.0.0.1:8769 sert maintenant `site-after-minutes`. Aucun tarif source ni attribution EVSE nouvelle.

Le normaliseur G3 `DE:bnetza_afir_archive` conserve l’archive nationale allemande (63 405 sites et 57 378 occurrences EVSE dans cette archive, chiffres informatifs), champs bruts complets, coordonnées et IDs exacts. Aucun connecteur, puissance de prise ou prix n’est inféré depuis les agrégats de site ; les données AFIR/CPO et tarifs restent bruts en attente de portée prouvée. Cinq tests normaliseur, deux tests batch, import SHA et adaptateur Production sur archive complète PASS. Bundle source `769bccad6a335d56a2d1f8f93ff873182e89715d4a6ac3cf26a272087717595c` sous `/tmp/tcc-v9-germany-national-canonical-20261026`. Aucun rapprochement au seul GPS ; contrat `docs/v9-rebuild/GERMANY_NATIONAL_ARCHIVE_CONTRACT_20261026.md`. Composition du bundle 28 sources en cours sous `.tcc-v9-cache/reproducible-28-germany-2026-10-26`, avec conservation des 27 SHA précédents. Le shell local conserve maintenant aussi les EVSE sans connecteur dans le groupe puissance inconnue ; tests de regroupement et classement en cours. Changements G3 non encore committés. Prochaine opération exacte : terminer `snapshot.prepare`, construire les données préparées/fragmentées à partir du bundle 28, empaqueter depuis `site-after-minutes`, puis recette Allemagne et neuf pays avant bascule de l’aperçu. Les limites de performance dense restent documentées, sans relancer un chantier autonome de carte. Actions désactivé et site public inchangé.


2026-10-26 — Production `66a3b90` : candidat local 28 sources, topologie allemande conservée, recette multi-pays et navigation aller-retour PASS. Dossier pilote inactif avec patch main non appliqué et vérification offline reproductible ; Actions désactivé. Détails et limites dans V9_REBUILD_PROGRESS.md.
## 2026-10-28 — V9 targeted historical tariff parity

Tesla Morocco power-minute pricing was restored in the isolated Production candidate from the pinned archive, preserving MAD and exact configuration scope (`caec2b7`). Belib Flex exact EVSE and aligned connected-time blocks were restored without assigning parking fees (`dd365ba`); ambiguous cut blocks remain incalculable. Archived IZIVIA FAST and Dutch subscription offers without exact canonical connector proof remain unranked. Agadir and nine-country/mobile browser replays pass; evidence is committed through Production `6e92a5e`. Details and resume instruction: `memory/V9_REBUILD_PROGRESS.md`. No Actions activation or public deployment.

The archived Allego France route now preserves exact source EVSE IDs and Direct raw offers in an immutable one-source bundle. It creates no connector or calculated tariff. Integration into the multi-country preview remains pending; see `memory/V9_REBUILD_PROGRESS.md`.

## 2026-10-28 — V9 tariff currency guard

The common tariff and session engines now fail closed when a tariff currency is absent or contradictory, including the locked and timeline paths. Archived CHF remains CHF; no EUR default can turn an incomplete offer into a comparable price. The 30-source isolated package passes targeted historical tariff, nine-country/mobile and SHA/hosting checks. The public site and Data Lab Actions remain unchanged; see `memory/V9_REBUILD_PROGRESS.md`.

## 2026-10-28 — Atlante France canonical source and shared AC Type 2 parity

The previously archived Atlante France source now uses the existing exact connector normalizer shared with Italy. The 30-source immutable candidate retains all 29 prior source SHA values. Production recognizes the preserved `AC_3_PHASE` plus `TYPE2` pair and evaluates only fully proved simple energy tariffs on each source connector. The exact national join report has no Atlante EVSE match and does not transfer prices. Targeted nine-source and nine-country/mobile Firefox, local hosting integrity, snapshot and pricing tests pass. Data Lab Actions and the public site remain unchanged; G2–G8 are not promoted. See `memory/V9_REBUILD_PROGRESS.md`.

## 2026-10-28 — Allego France added to isolated 29-source candidate

The 29-source immutable bundle retains the prior 28 SHA values. Production SHA import, 2,333 signed fragments, local hosting integrity, nine-country/mobile Firefox, and targeted Allego Gaillac display pass. Its four raw offers remain unranked with no connector or price inferred. The exact national join report preserves EVSE matches, while station-level merging is withheld because one Allego station can map to multiple national stations. Data Lab Actions and the public site remain unchanged; G2–G8 are not promoted. See `memory/V9_REBUILD_PROGRESS.md`.

## 2026-10-28 — V9 remote preflight and dense search profile

Production `69cd426` provides a read-only remote preview verifier for a separate HTTPS origin. Local integrity and negative tests pass; no remote project or URL exists yet. The 30-source Amsterdam 100 km cold query returned 62,770 matching stations in about 70 seconds; profiling showed per-power evaluations and per-batch queries dominate. The experimental batch-size change and profiling copy were discarded. G7/G8 remain FAIL on dense performance and missing remote proof; Actions and public site remain unchanged. See `memory/V9_REBUILD_PROGRESS.md`.

## 2026-10-28 — V9 dense ranking work reused without tariff changes

Production `fff5357` reduces the 30-source Amsterdam 100 km cold query from 70.2 to 50.0 seconds in the paired test. Hashes of 62,770 ranked stations, map pages, offers and evaluations match the baseline; nine-country/mobile and targeted tariff browser tests pass. Only identical charge-plan estimates, local clock readings, canonical station objects and stable all-day timeline decisions are reused. G7/G8 remain FAIL on dense latency and remote proof; Data Lab Actions and public site are unchanged. See `memory/V9_REBUILD_PROGRESS.md`.

## 2026-10-28 — V9 missing energy fail-closed

Production `3bbf4a4` preserves absent `energyKwh` as null, preventing a positive energy tariff from appearing as a free session. Historical priced inputs stay unchanged; the 30-source package retains exact dense ranking hashes and passes Firefox nine-country/mobile and SHA/hosting tests. G2–G8 remain FAIL and the public site is unchanged. See `memory/V9_REBUILD_PROGRESS.md`.

## 2026-10-28 — V9 Bump exact in isolated 31-source candidate

Data Lab `541de5b72` and Production `7a4879d` preserve the archived Bump source and exact national EVSE/connector scope. The immutable 31-source bundle retains all 30 prior source hashes; SHA/hosting, ten targeted browser flows and nine-country/mobile browser tests pass. The preview remains local and undeployed. G2–G8 remain FAIL pending full coverage, GitHub handoffs and remote preview. See `memory/V9_REBUILD_PROGRESS.md`.

## 2026-10-28 — V9 simple pricing guard and capability matrix

Production `38c654f` rejects unsupported simple tariff components; exact historical simple prices remain unchanged. The immutable 31-source bundle is reused in an isolated package; SHA/hosting, combined-session oracle, ten tariff browser flows and nine-country/mobile Firefox pass. G3/G5/G6 coverage remains open and G2–G8 FAIL. See `memory/V9_REBUILD_PROGRESS.md`.

## 2026-10-28 — G6 historical 64-case replay and compound-rule guard

Production `07a43cb` documents all named G6 mechanisms from historical PR #134–#146. The exact PR #144 source and golden yield 64/64 Midhope evaluations in source and isolated package. Unknown billed keys in rules fail closed; ten targeted tariff and nine-country/mobile Firefox flows, SHA/hosting, and representative packaged oracles pass. The PR #141 721-row report lacks full per-row inputs, so no identical-input V9 parity is claimed. G2–G8 remain FAIL. See `memory/V9_REBUILD_PROGRESS.md`.

## 2026-10-28 — V9 nested billing guard on final local candidate

Production `47e45f6` rejects unknown billed keys at component-group scope while retaining the proven UK tax-conversion provenance. The derived 31-source package passes SHA/hosting, packaged historical oracles, ten tariff and nine-country/mobile Firefox journeys. No remote deployment; G2–G8 remain FAIL. See `memory/V9_REBUILD_PROGRESS.md`.

## 2026-10-28 — Critical-path gate audit and hosting decision

Documented G2–G8 proof gaps without promoting gates. Offline pilot patch restored the reviewed main tree; Actions stayed disabled. Cloudflare Pages was removed as the active preview proposal following the user's decision; the future isolated host remains undecided.

## 2026-10-28 — Offline handoff replay

Replayed 39 Data Lab and 13 Production tests against the current contracts; corrected only a stale CPO-country fixture. Kept GitHub handoffs and remote hosting as unverified gates.

## 2026-10-28 — Authorized IONITY pilot and main neutralization

Archived 1,207 historic workflows on Data Lab main, disabled stale registered workflows, ran one reviewed read-only IONITY pilot, validated its immutable artifact and four-country Production import, then disabled Actions and removed the pilot definition. Other handoffs and Netlify deployment remain open.

## 2026-10-28 — Netlify preview preflight

Confirmed local package integrity, noindex header and public safety before any upload. Recorded Free-plan hard cap, large-file transfer risk and the missing dedicated Netlify access; deployment remains pending.
## 2026-11-05 — Première recette G9, correction locale de présentation

Le shell local limite maintenant l'affichage initial à 20 fiches et explicite les repères cartographiques sans prix. Le diagnostic exact de Carrefour Fécamp trouve huit EVSE nationaux mais aucune offre attribuable ; les tarifs Electra historiques sont retenus hors portée EVSE. Onze recherches ordinaires, dix tarifs de référence, neuf pays/mobile et le classement global passent. Le bundle 31 sources et le brouillon Netlify précédent restent immuables. Voir `memory/V9_REBUILD_PROGRESS.md` et les preuves Production `docs/v9-rebuild/evidence/g9-first-user-recipe-20261105.md`.

## 2026-11-05 — Préproduction Netlify V9 vérifiée à distance

L'URL immuable du brouillon 31 sources répond en HTTPS ; gros fichier et 2 521 fragments signés vérifiés par SHA. Dix parcours tarifaires et neuf pays/mobile Firefox passent sur ce déploiement. Les paquets de retour arrière sont conservés. G9 est ouvert pour la validation visuelle ; G8 global et les autres portes non closes restent FAIL, sans changement du site public ni des Actions. Voir `memory/V9_REBUILD_PROGRESS.md` et les preuves Production `docs/v9-rebuild/evidence/netlify-draft-20261105.md`.

## 2026-11-05 — Brouillon Netlify V9 transféré, accès privé à corriger

Le déploiement brouillon CLI du paquet 31 sources est `ready` sur le nouveau projet Netlify isolé, sans GitHub ni publication de production. L'URL anonyme répond 401 à cause de la visibilité privée des préversions ; les SHA et parcours Firefox distants restent donc non vérifiés. La prochaine action est le réglage de visibilité des préversions dans l'interface Netlify du seul projet V9, puis la recette distante. Voir `memory/V9_REBUILD_PROGRESS.md` et la preuve Production `docs/v9-rebuild/evidence/netlify-draft-20261105.md`. G2–G8 restent FAIL.

## 5 novembre 2026 — mandat finalisation

Les quatre corrections utilisateur sont maintenant autorisées. Les preuves Electra archivées retrouvent leur comparaison historique de format EVSE ; aucune enquête fournisseur. Production consolide le catalogue national et prépare un nouveau brouillon. Actions Data Lab demeure désactivé ; portes globales non promues. Voir le journal et le contrat `docs/v9-rebuild/ELECTRA_EMSP_EXACT_REPLAY_20261105.md`.

## 2026-11-05 - Nouveau candidat distant

**5 novembre 2026 - Nouveau candidat distant verifie, conformite globale partielle.** Data Lab `72b8b2256f10fad1e624e35d08540391f00bd2f7`, Production `1b9df09d5e27693ee331d110ed2a649ca0d25247` puis harnais CI `2c3bbe238876349dcd196894a728f9387ca43905`. URL **https://6aecb7777c40e2f98d53a4fb--tcc-v9-preproduction-20261028.netlify.app**, deploy `6aecb7777c40e2f98d53a4fb`, ready/deploy-preview/published_at=null. Bundle32 `3f5a9b347aaf824c3433728b8e54dae3051e07bd918efbc597c801150bbf2bb9` : 31 SHA anterieurs intacts, ajout Electra eMSP cinq preuves historiques. Paquet `.tcc-v9-cache/finalization-20261105/site`, 3780 fichiers. SHA distants, crosswalk11669931 octets, 2523/2523 fragments, onze parcours de portee/tarifs, onze recherches/neuf pays, filtres, vehicule, Buc/Milan/Chesnay, 20/40/60 cartes, pagination et mobile390 PASS distant. Trois cas CPO autonomes sont exclus selon la regle nationale, deux cohortes restent brutes : ne pas annoncer onze tarifs calculables. Buc unique conserve six EVSE IRVE, Milan retrouve son tarif, Le Chesnay reste non attribuable faute d'identite EVSE Mac. Fecamp reste sans prix. Libelles EVSE et adresse par defaut corriges. CI Production read-only42071503610 PASS apres correction du harnais dist ; 64 YAML archives a SHA identiques sur la branche seulement. Site public index/manifest et ancien brouillon inchanges, rollback local et URL verifies. Scans publics PASS. **G0/G1 PASS, G2-G8 FAIL, G9 attend recette utilisateur** : 119 handoffs/renouvellements non demontres, couverture tarifaire partielle, performance dense48,1s ouverte. Actions Data Lab reste desactive ; aucun main/Updater/Stable modifie. Preuves Production `docs/v9-rebuild/evidence/g9-finalization-preview-20261105.md` et `evidence/finalization-20261105/`, matrice `FINALIZATION_CONFORMANCE_20261105.md`. **Prochaine operation exacte :** reutiliser cette URL pour la recette utilisateur. Avant nouvelle execution Data Lab, obtenir une autorisation administrative bornee, reprendre le dossier pilote avec preflight SHA/declencheurs puis tester familles renouvelables, last-good et import. Ne pas redeployer ni rejouer les tests acquis sans modification, ne pas fusionner main ni publier. Candidat disponible pour test, pas declare conforme globalement.

## 5 novembre 2026 — Tesla autonome et renouvellement contrôlé en recette

Mandat utilisateur actuel : Tesla/Mac autonome dans tous les pays, sans identité nationale requise ; règle nationale exclusive pour les autres CPO. CDC mis à jour dans fb2efece1. Production corrige la consolidation, préserve les entrées brutes nationales Tesla, les six EVSE Buc et les offres non attribuées. Tesla neuf pays, Le Chesnay (45 kWh → 18,90 EUR au scénario fixé), Milan, treize parcours ciblés dont IONITY renouvelé, neuf pays/mobile et oracles locaux PASS. Aucune modification de l’acquisition Mac.

Actions : préflight main c7204b3ef, 1207 archives restaurables, zéro déclencheur actif ; deux runs bornés réels push42076511189 et manuel42076753318 au SHA fb2efece12321c7dcb347166f7a6b4f5eec1e4b5. IONITY, FX, Kilowatt réussis ; Actions désactivé ensuite et workflow temporaire désactivé/archivé. 117 handoffs restent non vérifiés. Pas de cadence quotidienne ni permission de fusion main déduite du pilote.

Bundle renouvelé a81e1defb94b88629e06bc09880bb1623aaeeea7de930987fa439cc5a3575a5c : IONITY FR/DE/IT/GB renouvelés, 28 autres sources inchangées ; FX renouvelé et épinglé au paquet. Kilowatt : transfert/validation technique seulement, pas de raccordement UI revendiqué. Préparation et paquet hors checkout `.tcc-v9-cache/renewal-20261105/`, site `site`. Anciens bundles et brouillons conservés.

Optimisation commune : préparation des offres immuables réutilisée, aucun total tarifaire mis en cache. Amsterdam100 conserve62 770 résultats et toutes empreintes de classement/carte/évaluation ; mesure49,102s contre68,981s mêmes entrées, reste une limite G7. Preuves Production `docs/v9-rebuild/evidence/renewal-20261105/`, Data Lab même dossier pour pilote et SHA.

**G0/G1 PASS, G2–G8 FAIL global, G9 en cours. Prochaine opération exacte :** terminer scans/CI, déployer uniquement le nouveau paquet `site` en nouveau brouillon Netlify sans --prod, vérifier tous les SHA/fragments puis rejouer Tesla neuf pays, treize parcours ciblés, recherches ordinaires et recette utilisateur/mobile sur son URL réelle. Ne pas réactiver Actions, modifier main/Stable/Updater ni le site public.

## 5 novembre 2026 — nouvelle URL vérifiée, conformité globale encore partielle

**URL : https://6aecc65c572ac7778d850e91--tcc-v9-preproduction-20261028.netlify.app**. Déploiement ready/deploy-preview, published_at=null, aucune liaison Git. Code empaqueté Production `cd0a5a4282f4299ea9b386e253fe3be92570ce7a`, Data Lab `6900df609c0dd3baf131da56e574b74b03311740` (preuves du pilote au SHA `fb2efece1`). Bundle `a81e1defb94b88629e06bc09880bb1623aaeeea7de930987fa439cc5a3575a5c`, paquet `.tcc-v9-cache/renewal-20261105/site`. Ancien brouillon `6aecb7777c40e2f98d53a4fb` et tous les bundles last-good conservés.

**Exécuté à distance PASS :** HTTPS/200/noindex ; SHA du crosswalk 11 669 931 octets, des ressources critiques/FX et de 2 526 fragments ; Tesla/Mac autonome neuf pays ; Le Chesnay/Milan, Buc unique et Fécamp sans prix ; treize parcours ciblés (dont IONITY IT/GB réellement renouvelé), onze recherches/neuf pays ; carte, filtres, véhicule, 20/40/60 fiches, pagination et mobile390px. Les parcours bruts/exclus ne sont pas déclarés tarifables. Midhope64 et oracles combinés empaquetés PASS local, CI GitHub Production read-only42081476692 PASS. Scans publics PASS. Ressources du site public, ancien brouillon et main inchangés ; Updater/Stable inchangés.

**Performance mesurée distante :** Amsterdam100 à froid52,336s,62 770 résultats et toutes empreintes d’ordre/montants/évaluations/carte/pages identiques à la référence ;49,102s local contre68,981s avant préparation commune des offres. Gain réel, limite dense encore ouverte : aucun PASS G7performance.

**État exact :** G0/G1 PASS ; G2–G8 FAIL global, G9 peut se poursuivre sur ce candidat partiel. Actions Data Lab désactivé, zéro run incomplet. IONITY/FX renouvelés le5novembre, autres archives explicitement conservées ; Kilowatt transport seulement. 117 handoffs non vérifiés ; installation d’une cadence sur main et activation permanente non autorisées. Ne pas annoncer une alimentation quotidienne intégrale.

**Prochaine opération exacte :** poursuivre la validation des familles restantes avec le registre `v9_rebuild/sources.json` et le dossier `docs/v9-rebuild/evidence/renewal-20261105/`, sans rejouer les trois méthodes vérifiées ni leurs recettes tant que les entrées sont inchangées. Utiliser le workflow commun isolé et des fenêtres bornées avec préflight main/permissions, vérifier chaque nouvel artefact avant import ; conserver toute dépendance de secret/appareil non accessible comme non vérifiée. Préparer séparément l’installation de la cadence (aucune fusion main ni activation permanente sans permission). Pour la performance, conserver `dense-equivalence-remote.json` et ne modifier que le prochain goulot démontré ; aucun résultat retiré. Aucun nouveau déploiement requis pour montrer à l’utilisateur le candidat actuellement vérifié.

## 5 novembre — restauration tarifaire en cours (aucun nouveau déploiement)

Perte de raccordement eMSP confirmée. Constructeur `scripts/build_v9_archived_emsp.py` rétablit les identités normalisées exactes historiquement prouvées, sans station CPO autonome. Canonique local31022Electroverse/95417Electra,8769réserves de restrictions source ; les chiffres ne sont pas des prix calculables navigateur. Six tests de normalisation/erreurs et trois suites moteur/adapter PASS. Bundle85aef37658277fccae722a6f767be22a518de36e529ad3182fd1edded03bfa56, préparation isolée en cours. Cache128shards validé ;13partitions/16, pas de fusion nationale fraîche revendiquée. Preuves `docs/v9-rebuild/evidence/emsp-restoration-20261105/`.

Prochaine opération : finir l’extension préparée, empaqueter hors checkout depuis le site renouvelé existant, vérifier les calculs sur toutes les offres restaurées puis recherches ordinaires et cas G9 ; ne pas déployer avant recette globale significative. Pilote borné Electra/Driveco/Belib préparé, activation uniquement après préflight main et workflows désactivés ; désactivation garantie en fin d’essai. G2–G8 restent FAIL, aucun main/site public/Updater/Stable modifié.

## 5 novembre — eMSP élargi, Direct restauré, renouvellement Electra non validé

Bundle immuable `3ad0c0ea896f5a44fbcd9cf795a77c4cb91e3a804836117e375a1799d6950d06`,32sources. Normaliseur parent Electroverse : identifiant parent/suffixe historique, prise et puissance exactes ;248offres supplémentaires sans nouvelle jointure.9tests DataLabPASS ; oracle toutes archives PASS. Production restaure aussi Belib(5757profils/offres), Suisse(3167offresCHF) et Allego(612énergie+idle) uniquement sur contrats complets prouvés.20tests transversauxPASS ; recette locale G9 `site-restored` et parcours Belib/SuissePASS ; Allego ajouté dans `site-complete-restoration`, recette en cours. Aucune nouvelle URL ni conformité distante annoncée.

Pilote Electra42093326295 au SHA06f287c6 : completed/failure après32min, `collector_exit_nonzero`. Actions global et workflow pilote de nouveau désactivés. Artefact d'échec13449160770, digest `bcc46a97090132a02667e4cd6178b733021dc04ee10ac9ba3949ec8457894570`, sans nouveau snapshot validé. Journaux sous `.tcc-v9-cache/emsp-restoration-20261105/renewal-electra-retry/`. Le diagnostic du sous-processus a été perdu par l'ancien wrapper ; corriger cette perte avant répétition. L'archive historique contient13IDs d'offre répétés rejetés par le validateur ; ne pas prétendre que cette cause distante est démontrée sans diagnostic.115handoffs toujours ouverts.

Prochaine opération : achever recette `site-complete-restoration` (mêmebundle), conserverpreuvesetcommits ; corriger le diagnostic d'échec Electra et l'isolation des identités répétées sans accepter de tarif ambigu ; poursuivre transmissions de familles contrôlées. G0/G1PASS, G2–G8FAIL. Main/sitepublic/Updater/Stable inchangés.

## 5 novembre 21:55 UTC — fenêtre Actions fermée, Electra renouvelé, restauration UK en recette

Run42101119558 success sur fc06c7f02 : Electra renouvelé, Swiss bundle et intégration réexécutés avec leurs entrées archivées signées. Actions global de nouveau désactivé et zéro workflow actif vérifiés ; pilote retiré du dossier actif et archivé. ZIP/manifestes/fichiers des trois artefacts PASS, preuves `docs/v9-rebuild/evidence/emsp-restoration-20261105/{electra,swiss-bundle,swiss-integration}-handoff.json`. Le validateur G2 reste FAIL :112handoffs non vérifiés, registre partiel. Les données suisses sont identiques aux archives ; la date de construction GitHub ne doit pas être présentée comme une collecte fournisseur fraîche.

Correctif d'intégrité portable : gzip Linux/Python3.11 OS=3 et macOS/Python3.9 OS=255 portent les mêmes octets décompressés signés. Comparaison intégrale au snapshot signé et mtime0 conservées, SHA compressé/ZIP inchangés ; tests PASS. Reprise d'une vérification ZIP sans redownload testée, avec provenance distante/SHA vérifiés à nouveau.

Electra renouvelé :105509offres brutes,96191attribuées exactement,9601réserves de restrictions/conflits (chiffres diagnostiques, pas seuils). UK Ubitricity :9431offres compilées historiques du20octobre retrouvées ; restauration hors ligne aux mêmes entrées OCPI/identités exactes,4701brutes préservées. Trois scénarios par offre PASS au moteur, horaires/VAT/frais après charge et chargeur signé testés ; aucune acquisition UK ni enquête PAYG. Ubitricity NL reste legacy_method_unavailable, inchangé.

Candidat intermédiaire `site-transfer-compressed` : transport ledger gzip sans perte,4407fichiers352929999octets, plus grand16168736octets, SHA brut+transport vérifiés ; recherches ordinaires11/neuf pays et G9contrôles/mobile PASS local. Aucun nouveau Netlify. Nouveau bundle combinant Electra renouvelé, UK restauré et preuve suisse en préparation ; conserver tous les sites/bundles précédents. Production HEADaf448aa, DataLabHEAD5d7de9aef avant ce lot. Prochaine opération : terminer ce bundle et son import préparé en réutilisant les fragments inchangés, empaqueter, recette locale ciblée UK/Electra+globale puis nouveau brouillon Netlify seulement après scans. G2–G8 restent FAIL global ; main/public/Updater/Stable inchangés.

## 5 novembre — reprise en cours : pilote NL actif, couverture tarifaire restaurée en recette

DataLab1bf60eb8deaa188e1af0c04df39dcc5222c5e5e7, Production2a52282f782bc41883ab56f1ef89fbccdf3245d2. CI Production42112577297 PASS. Bundle33 ffbee82a4ba5f38d6d72b1c3aa66515b2b183df84521b3363cf149a317b4401d en préparation `prepared-direct-final`, sortie finale attendue `site-direct-final`.32précédent `site-renewed-uk` passe17parcours Firefox ; aucun nouveau Netlify.925profils exacts Ze-Watt/Zephyre raccordés aux identités nationales, compilateurs historiques identiques et oracles combinés PASS ;10EVSE absents restent hors catalogue, aucun prix géographique.

**Fenêtre Actions NL active : run42112592017, HEAD1bf60eb8d.** Driver `/private/tmp/tcc-emsp-dotnl.py`, session40910, sortie `/private/tmp/tcc-emsp-dotnl-result.json`, contrôle `.tcc-v9-cache/emsp-restoration-20261105/renewal-dotnl/control.json`. Borné31min, un seul workflow lectureseule. Préflight main c7204b3ef,1207archivesrestaurables,zéroautre workflowactif oufile PASS. Désactivation garantieparfinally ; vérifier réellement enabled=false avant clôture. Ne pas relancer Electra/Suisse/IONITY/FX/Kilowatt.

Correction de compteur découverte :112handoffs explicitement non vérifiés n'incluaient pas15sources sans champ renseigné (dont DOT-NL). Totalexhaustif127/135sources à ce point,8preuvesdistantes ; aucun handoff n'a été artificiellement supprimé. Registre maintenant explicite, défaut de comptage G2corrigé ; porte toujoursFAIL. Prochaineopération : terminer empaquetage33, tests navigateur19/neufpays/mobile et scanpublic, vérifier le runNL et fermerActions, puis seulement transfertNetlifybrouillon et recetteSHA/navigateurdistante. Main/public/Updater/Stableetancienscandidatsintacts.

## 5 novembre — pilote DOT-NL terminé, Actions fermé, candidat33 en recette

Run42112592017 success, HEAD1bf60eb8deaa188e1af0c04df39dcc5222c5e5e7. Actions enabled=false vérifié par le driver, workflowpilote archivé. Artefact DOT-NL téléchargé et validé (ZIP/manifeste/fichiers/contrat) ; preuve `docs/v9-rebuild/evidence/emsp-restoration-20261105/dotnl-handoff.json`. Acquisition nationale et Electra Direct NL renouvelées par leurs méthodes existantes ; overlay Ubitricity NL reste le last-good archivé, aucune enquête ni méthode recréée.126handoffs réellement non vérifiés après correction exhaustive du registre (le112précédent omettait15sources). G2resteFAIL.

Bundle33 `ffbee82a4ba5f38d6d72b1c3aa66515b2b183df84521b3363cf149a317b4401d` et préparation33 compressée prêts ; empaquetage `site-direct-final` en cours, session76547. UK9431etDirect925+eMSP31k/96k restaurés surpreuves ;17parcours navigateur32PASS. La normalisation de l'artefact NL renouvelé tourne séparément session62558 vers `verified-dotnl/NL__dotnl_static.json` ; l'intégrer au bundle33avant recetteglobale finale. NetlifyFree confirmé, aucun auto-topup/overage, aucun lienGit, toujoursaucunnouveaudéploiement. Sitepublichashvérifié séparément. Prochaineopération : acheverNL, préparerunbundle33renouvelé enréutilisantles32sourcesinchangées, recette19tarifs/neufpays/mobile/scanSHA puisbrouillonNetlifydistinct. Ne pas relancerpilotesvalidés ; touslesanciensbundles/sitespréservés.

## 14 novembre — pilote belge corrigé réussi et Actions fermé

Run 43587934900 / HEAD 17734182fbfd1494a04e51cae7fb48949565606e : collecte BE:nap réussie, 18 pages complètes, 40 fichiers vérifiés par SHA/manifeste/contrat. Actions désactivé et zéro workflow actif ; main c7204b3ef inchangé. Le défaut de dossier docs manquant est corrigé dans l’isolation, sans modification fournisseur. Reçu : docs/v9-rebuild/evidence/restoration-20261114/belgium-national-handoff.json. 15 handoffs réellement prouvés, 120 ouverts ; G2–G8 restent FAIL globalement.

Le candidat français local est terminé : bundle 474a18a065b4dde765ef728911bec3db264fd25243e64e9d1e5ad94a598aad1f, site-national-france-20261114 ; 19 parcours, 11 recherches/neuf pays, contrôles G9/mobile, hébergement et scan différentiel PASS. Les pays inchangés restent exactement identiques ; les variations FR sont diagnostiques, sans seuil. Pas encore déployé.

Prochain : terminer la normalisation BE et le bundle combiné FR/BE via resume-20261114/national-belgium-fixed/build-candidate.py (état et preuves hors checkout), préparer depuis prepared-national-france-20261114, vérifier les parcours pertinents puis un nouveau brouillon global. Dernière URL réellement vérifiée : https://6af8365acf7552d1d9e1768a--tcc-v9-preproduction-20261028.netlify.app. Ubitricity UK toujours attente fournisseur ; REVE utilise MAPA_REVE_API_KEY ; Atlante sans secret utilisateur. Aucun changement public/Mac/Stable.


## 14 novembre — préparation du pilote Direct Allego/Bump

Les méthodes FR:allego_stations et FR:bump_tariffs sont conservées, sans secret utilisateur ni API nouvelle. Les validateurs existants sont raccordés au vérificateur de transferts ; 6 tests de provenance, 3 Allego et 5 Bump PASS. Préflight réel : main c7204b3ef, zéro workflow actif sur main, 1207 archives avec blobs restaurables. Un pilote commun borné à deux jobs est préparé, sans push automatique ni publication. Actions reste désactivé à cette entrée ; aucun nouveau succès revendiqué. Driver persistant : resume-20261114/direct-allego-bump/run-direct-pilot.py, fermeture en finally après 1800s maximum.

Candidat national combiné b2f37b27510bc115bf66211e33e4ee06eeaed095c2003cb34caaa4ce5a41d309 en empaquetage/recette locale, pas encore déployé. Dernier Netlify vérifié inchangé. Prochain : effectuer le pilote borné, fermer Actions, vérifier chaque résultat indépendamment ; poursuivre la recette du candidat national sans promouvoir d’échec partiel.


## 14 novembre — Allego renouvelé ; Bump rejeté, dernier état préservé

Run 43589225728 global FAILURE : Allego source job SUCCESS et artefact/SHA vérifiés, Bump refusé par le contrôle de complétude GraphQL (requêtes ou compteurs). Actions fermé. 16 handoffs prouvés,119 ouverts. Reçu Allego et diagnostic Bump sous docs/v9-rebuild/evidence/restoration-20261114/. Allego : mêmes identités et offres que l’archive, nouvelles acquisition/provenance réelles ; canonique SHA8e9be93b13db60489c344a3d43e1644b6513526073fc7f6c525a38afe64a4fb0.

Les détails de sortie Bump étaient supprimés lors d’un rejet. Correction : conservation de ses six fichiers publics déclarés en quarantaine failures/unvalidated-output, jamais objects/checkpoint/last-good. 6 tests Bump et16orchestration PASS. Une reprise bornée Bump seule est préparée pour préciser la cause, sans changer API, paramètres, validation ou prix. Driver resume-20261114/direct-bump-diagnostic/run-direct-pilot.py ; Actions désactivé avant cette reprise.

Le candidat national b2f37b27 passe20parcours,11recherches/neufpays,contrôlesG9/mobile, hébergement et scan différentiel. Pas déployé : préparation d’un seul candidat combiné incluant Allego renouvelé, site-national-direct-20261114. Prochain : refermer le piloteBump et examiner les sorties ; terminer le candidat et sa recette distante. G2–G8 FAIL global, sitepublic/Mac/Stable inchangés.


## 14 novembre — refus fournisseur Bump identifié, aucun résultat partiel promu

Run43589681840 FAILURE et Actions fermé/zéro workflow actif/main inchangé. Le reçu d’échec SHA et les six sorties en quarantaine établissent :70tuiles HTTP200 contenant « Too many requests. Please try again later. », aucun échec de groupe tarifaire, compteurs rapport/données identiques. Il s’agit d’une limitation fournisseur applicative, pas d’un secret manquant. Aucun troisième essai immédiat, aucun contournement de quota, aucune sortie partielle transmise. Le dernier Bump valide reste utilisé. Preuves bump-rate-limit-receipt.json / bump-diagnostic-control.json ; fichiers bruts horscheckout direct-bump-diagnostic/quarantine. La conservation des diagnostics est corrigée et testée ; le renouvellement fournisseur n’est PAS validé.16handoffs prouvés/119ouverts.

Candidat regroupant acquisitions FR/BE/Allego : bundle29ab85449b08a68376e1b6b726476614a771aa96b12452f4d2e4014451d3e7f1,33sources dont30inchangées depuis le précédent Netlify. Préparation/recette en cours via resume-20261114/direct-allego-bump/pipeline-state.json et validation-state.json ; site-national-direct-20261114. Ne pas reconstruire les bundles validés. Prochaine : terminer tests locaux, scan/manifestes, puis un seul nouveau brouillon isolé et contrôles distants. G2–G8 restent FAIL ; dernière URL vérifiée6af8365a inchangée.


## 14 novembre — brouillon national/Direct en recette distante ; préparation PCPR UK

Nouveau brouillon6af8470ab1f6ac03083a27f4 ready/deploy-preview, aucun --prod. URL https://6af8470ab1f6ac03083a27f4--tcc-v9-preproduction-20261028.netlify.app ; bundle29ab85449b08a68376e1b6b726476614a771aa96b12452f4d2e4014451d3e7f1.20parcours et11recherches/neufpays identiques local/distant ; contrôlesG9/mobilePASS. SHA exhaustif encore en cours, reçu direct-allego-bump/fragment-receipt.jsonl ; ne pas annoncer sa fin avant remote-state.json/remote-integrity.json. Ancien brouillon6af8365a revérifié disponible, sitepublic inchangé. Audit de portée sur les neuf pays PASS, mêmes moteurs que le paquet servi ; Buc unique/sixEVSE, aucun CPO autonome dans les bases nationales.

Prochaine famille utile : deux collecteurs PCPR historiques Allego UK / Source EV, mêmes méthodes et budget partagé28requêtes par identifiant/h. Noms des deux secrets existants confirmés sans valeurs ;3tests adaptateur,9testscollecteur,6teststransfertPASS. Pilote commun borné préparé ; Actions encore désactivé à cette entrée. Driver resume-20261114/uk-pcpr-renewal/run-uk-pilot.py ; fermer Actions avant vérification des artefacts. Aucun renouvellement UK revendiqué avant reçu réel.

Registre Atlante précisé pour les deux modules : le nom ATLANTE_API_SUBSCRIPTION_KEY est un environnement technique alimenté par le bootstrap APK historique ; aucun secret utilisateur à créer. Ubitricity UK reste attente fournisseur, REVE utiliseMAPA_REVE_API_KEY, Bump est limité par le fournisseur et last-good intact. G2–G8 FAIL global,16handoffs prouvés/119ouverts.

