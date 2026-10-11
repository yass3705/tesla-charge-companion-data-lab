# Journal de la mémoire technique

Entrées append-only, datées, avec liens vers les documents et commits sources. L'historique exhaustif du code reste dans Git (`git log`) et dans les changelogs propres aux dépôts ; ce journal consigne les passages de relais et décisions transverses.

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
