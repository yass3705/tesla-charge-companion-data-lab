# Journal de la mémoire technique

- [Validation effective run #38299651696](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/38299651696) **success** : 620 stations et tarifs directs officiels, 616 avec connecteurs éligibles, quatre sans connecteur pris en charge. Détails carte 0 échec, aucune repasse sollicitée, couverture précédente 482 → 616 (+134). 665 codes carte, 45 codes carte hors inventaire ; pas d'élargissement des correspondances exactes. [Artefact](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/38299651696/artifacts/11769129182). Le succès de la première passe ne prouve pas l'utilisation des retries. Aucune promotion Production.

## 2026-10-12 — Récupération IZIVIA FAST (candidate)

- [Run historique 38271411552](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/38271411552) : 482 stations tarifées sur 620, 76 erreurs tarifaires, 59 non-appariements carte et 65 fiches carte en échec. Hypothèse testée : interruptions/rate limit de l'API pendant les requêtes concurrentes, non disparition nécessaire des sites.
- Branche Data Lab `fix/izivia-fast-recover-map-prices-20261012` : quatre workers, repasse séquentielle des détails et prix échoués, rapports de récupération, aucun tarif inventé. [Validation nationale sans publication 38299651696](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/38299651696) déclenchée ; décision de fusion suspendue à la validation effective et aux preuves.


Entrées append-only, datées, avec liens vers les documents et commits sources. L'historique exhaustif du code reste dans Git (`git log`) et dans les changelogs propres aux dépôts ; ce journal consigne les passages de relais et décisions transverses.

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
