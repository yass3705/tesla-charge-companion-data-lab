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
