# TCC V9 — Cahier des charges permanent de reconstruction (G0 à G9)

**Décisions utilisateur consolidées au 20 octobre 2026.**
**Statut : spécification cible et critères de recette, NON rapport de réalisation.**
**Branche de travail initiale : rebuild/v9-20261020 dans tesla-charge-companion-data-lab.**

Ce document doit rester lisible et applicable après une interruption du quota Codex, un redémarrage du CLI ou la création d'une nouvelle session. Il décrit **ce qu'il faut construire**. Le fichier [memory/V9_REBUILD_PROGRESS.md](../../memory/V9_REBUILD_PROGRESS.md) décrit **où en est l'exécution** : toujours le consulter pour les preuves, SHA, portes PASS/FAIL, anomalies et la prochaine opération exacte. Ne jamais considérer une phase réalisée du seul fait qu'elle figure ici.

## 1. Mandat et résultat attendu

Reconstruire Tesla Charge Companion V9, de la collecte à l'interface de préproduction, en réutilisant les connaissances, méthodes et données déjà acquises. La reconstruction remplace une orchestration historique trop complexe (1 207 workflows YAML inventoriés en G1) par un petit nombre de workflows communs et des modules réutilisables.

**Livrable final pour l'utilisateur : une URL de préproduction TCC complète, utilisable sur ordinateur et téléphone, permettant de vérifier directement les stations, EVSE/prises, puissances, tarifs Direct/Electra/Electroverse, calculs et filtres.** L'utilisateur n'a pas à inspecter du code, des SHA, de la CI ou des rapports techniques pour approuver l'interface.

L'utilisateur délègue les arbitrages techniques ordinaires, le développement, les tests, les corrections et le séquencement. Codex travaille aussi loin que le permettent la session, le quota, les permissions et les vérifications. Ne pas s'arrêter volontairement après chaque CPO ou chaque lot si d'autres tâches sont réalisables. Une session Codex arrêtée **ne continue pas en arrière-plan** : enregistrer l'état reprenable.

## 2. Périmètre des dépôts et limites impératives

- Conserver les deux dépôts publics existants : **tesla-charge-companion-data-lab** (collecte, données, preuves, artefacts) et **tesla-charge-companion-production** (consommation, calculs, interface, préproduction/publication). Aucun nouveau dépôt privé.
- Couvrir les méthodes existantes pour FR, IT, CH, DE, ES, NL, UK, MA et BE, les CPO, sources nationales et eMSP concernés, ainsi que l'interface d'import Tesla/Mac.
- **Ne pas modifier la collecte Tesla/Mac dans Updater Test.** Garder la chaîne d'import, sa provenance et ses règles existantes ; ne pas transférer ses secrets ni le code privé dans Data Lab public.
- Stable demeure référence historique et possibilité de retour arrière. La Production publique existante ne doit pas être remplacée avant validation explicite.
- Les anciennes collectes quotidiennes Data Lab peuvent rester interrompues pendant toute la refonte. Aucune obligation de maintenir leur continuité.
- Ne pas reprendre la réparation individuelle des anciens workflows ; conserver seulement leurs méthodes, scripts, entrées/sorties, règles documentées, preuves et tests utiles.

### Ce qui est expressément HORS périmètre des migrations de collecteurs

**Aucune recherche de nouveaux tarifs, aucune nouvelle recherche d'API/endpoints, aucun audit de véracité des prix, aucune enquête sur les sites/apps fournisseurs, aucune nouvelle campagne de rapprochement tarifaire et aucune réouverture des investigations métier déjà terminées.** Ne pas améliorer la collecte pour le plaisir de l'améliorer. Ne pas confondre exécution technique d'une méthode connue et investigation métier.

Les fixtures et anciennes preuves servent à confirmer qu'une méthode transférée garde son contrat et sa sortie, PAS à réévaluer la réalité commerciale des montants. Lorsque la méthode historique est indisponible ou insuffisamment documentée, conserver last-good/provenance, signaler l'exception nominative et désactiver cette seule acquisition ; ne jamais inventer un parseur équivalent, une offre ou un tarif.

**Ubitricity NL :** l'acquisition historique à deux scripts absents est classée legacy_method_unavailable, désactivée, avec intégrateur et candidat last-good conservés. Ne pas rouvrir ce dossier automatiquement et ne pas le faire bloquer la migration d'autres sources.

## 3. Règles techniques transversales non négociables

### Aucune porte fondée sur des volumes historiques

N'utiliser **aucun** nombre absolu fixe de stations, EVSE, connecteurs ou offres, ni pourcentage d'augmentation/baisse, ni parité avec une collecte précédente comme critère autonome de validation/rejet. Les anciennes constantes EXPECTED, seuils et correctifs associés ne doivent PAS être migrés.

Une augmentation, baisse, disparition ou apparition est admise si l'exécution technique est cohérente. Vérifier les HTTP, schémas, identifiants, pagination menée à son terme, intégrité des fichiers, compteurs **internes au même artefact** et SHA ; ne pas bloquer parce que le nombre de stations/EVSE ne ressemble pas à hier. Un zéro n'est pas à lui seul la preuve d'une erreur : qualifier toute anomalie par un échec technique réellement démontré.

### Identités et provenance

Conserver les ID station, EVSE et connecteurs officiels ou fournisseur. Générer une **clé technique interne** stable et unique, différente d'un EVSE_ID physique. Ne jamais fabriquer un EVSE_ID officiel absent. Préserver la distinction entre source, CPO, exploitant, station, EVSE, connecteur, puissance, offre, canal, portée, justificatif et date d'extraction. Conserver les entrées brutes lorsque nécessaire, sans effacer une donnée source à cause d'un manque de tarif.

### Sécurité, états et artefacts

- Collecteurs exécutés **hors du checkout** Git dans des répertoires isolés ; sorties validées en artefacts immuables avec manifestes et empreintes SHA ; reprise par source et branche seulement sur état compatible.
- Checkpoint incomplet distinct d'un artefact utilisable par Production. Une erreur doit rester visible ; pas de publication implicite d'une sortie partielle.
- Les workflows PR/tests sont en lecture seule ; aucun push automatique sur main, aucun workflow_run en chaîne, aucune écriture inter-dépôts non maîtrisée, aucune exposition de secrets dans le dépôt public.
- Actions Data Lab a été désactivé pendant G0 à cause des anciens workflows présents sur main ; **ne pas le réactiver sans neutralisation vérifiée des anciens déclencheurs, procédure de test sûre et autorisation explicite**. Des tests locaux ne prouvent pas un transfert GitHub Actions réel.
- **Décision utilisateur du 28/10/2026 : Cloudflare Pages est abandonné pour la préproduction V9.** Aucun hébergeur de remplacement n'est choisi ni déployé sans validation appropriée. L'URL finale doit rester isolée du site public et satisfaire les contrôles SHA, noindex, navigateur et rollback de G8.
- Pas de fusion, changement administratif GitHub, activation d'Actions, déploiement de Production/public, bascule de trafic ou opération irréversible sans autorisation appropriée.
- Respecter le caractère public du dépôt et exécuter public_safety_check.py avant les publications de branche.

### Valeurs de tarification

Trois canaux distincts : **Direct CPO**, **Electra**, **Electroverse**. Jamais d'agrégation de tarifs eMSP et directs, de prix attribué à une borne voisine par simple regroupement physique, ni de prix inventé. Une offre identifiée dont les composants sont incomplets donne **Tarif incalculable** ; absence d'offre exploitable donne **Prix non disponible**. Les diagnostics d'ambiguïté/inéligibilité restent traçables ; un prix ambigu ou incomputable ne doit pas servir au classement.

## 4. Plan de reconstruction et portes G0–G9

Les portes signifient **PASS seulement sur preuves exécutées et enregistrées**. Distinguer test sur fixture, essai live, essai GitHub Actions, intégration Production, préproduction et publication publique. Un mock ne remplace pas un run réel.

### G0 — Sécurisation et possibilité de restauration

**Travail :** vérifier les branches, SHA et arbres locaux ; archiver les commits d'origine et les méthodes ; inventorier/désactiver les anciens déclencheurs dangereux ; protéger le site public et les dépôts connexes.

**Porte PASS :** sauvegardes/restaurations démontrées, Actions historiques désactivées et aucun run risqué actif, aucune écriture indésirable sur main, aucune perte des méthodes, état des dépôts documenté. Ne jamais conclure qu'un YAML sur branche Draft protège le YAML actif sur main.

**Historique au 20/10 :** G0 signalée PASS dans le journal de reconstruction ; ne pas la refaire en l'absence de risque nouveau.

### G1 — Inventaire exhaustif et destinations des méthodes

**Travail :** inventorier workflows, scripts (y compris non appelés littéralement), code inline, sources/catégories, dépendances, secrets *par nom seulement*, sorties, consommateurs dynamiques de Production. Classer méthodes réutilisables, partielles, historiques, redondantes ou indisponibles. Destination explicite pour toute méthode réellement utile. Garder les preuves des neuf pays et du flux Tesla.

**Porte PASS :** registres reproductibles et complets, aucun code utile perdu par la purge, méthodes prioritaires et archivées classées, exceptions nominatives justifiées, tests du validateur G1 et scan public réussis.

**Historique au 20/10 :** G1 signalée PASS ; Ubitricity NL explicitement hors collecte active.

### G2 — Nouvelle orchestration, modules d'acquisition et suppression des vieux YAML actifs

**Travail :** éliminer les ~1 207 anciens YAML du nouveau dispositif, sans détruire leur archive ; créer quelques workflows partagés en lecture seule et des adaptateurs par famille technique. Registre unique de sources, scripts historiques réutilisés, secrets nommés, entrées/sorties et dépendances, exécution isolée, reprise, échec explicite, artefacts immuables, absence de push main. Utiliser les modules communs déjà migrés plutôt qu'un nouvel adaptateur par CPO.

Conserver la chaîne Electroverse daily/full (128 shards et checkpoints), status (16 partitions, fusion), overlay (dépendances tarif + statuts, provenance et SHA), DOT-NL, sources directes, constructeurs nationaux et autres familles. Pour chaque méthode conservée : contrat testé, provenance, destination et source enregistrée ; les méthodes dormantes/non récupérables restent désactivées avec raison.

**Porte PASS :** toutes les méthodes utiles G1 migrées et techniquement testées ou exceptions explicites isolées ; tests d'orchestration/échec/reprise, intégrité et sécurité ; ancien dispositif actif absent. **Les transferts Actions réels encore non vérifiés restent marqués github_handoff_unverified et ne deviennent pas PASS par déclaration.** La réactivation/test distant exige l'autorisation et la neutralisation des anciens déclencheurs.

**État au 20/10 :** G2 partielle. Lire exclusivement le dernier résultat de scripts/validate_v9_g2.py et le journal V9_REBUILD_PROGRESS pour le solde exact ; ne pas figer les compteurs historiques dans cette spécification.

### G3 — Normalisation des données et identité canonique

**Travail :** schémas versionnés Pays/Source/CPO/Station/EVSE/Connecteur/Offre/Portée/Provenance ; données brutes séparées des données normalisées ; clés techniques déterministes, identifiants source exacts, puissances par EVSE/prise et unités/devise. Un site sans offre reste dans le catalogue ; les cas non résolus ne transportent jamais un prix calculable indu.

**Porte PASS :** tests de schéma, stabilité/unicité des clés, non-collision, conservation des champs et liens, séparation des canaux et cas de données manquantes, cohérence des comptes internes. Aucune comparaison de volume avec les anciennes collectes.

### G4 — Contrat Data Lab → Production

**Travail :** produire des artefacts vérifiés et manifestes de version/SHA/provenance/fraîcheur ; sélectionner le bon état par source, gérer last-good, snapshots immuables, import Production par pin, contrôle d'intégrité, rollback. Préserver l'import Tesla/Mac sans toucher à sa collecte. Éviter la propagation de mutations via git push et les dépendances circulaires.

**Porte PASS :** export/import reproductible sur plusieurs familles/pays, intégrité de tous fichiers, restauration d'un snapshot, isolation d'une source en échec, aucune modification du site public. Les vraies opérations GitHub non exécutées restent explicitement non vérifiées.

### G5 — Jointures nationales, CPO, Electra, Electroverse

**Travail :** réutiliser les règles et rapprochements déjà documentés ; joindre les offres avec **identité EVSE/prise et portée source prouvées**. Correspondance par GPS/puissance seulement selon les règles déjà établies et sans propagation tarifaire arbitraire à la station. Distinguer données nationales, CPO direct et eMSP ; traiter les EVSE non rapprochés sans les supprimer arbitrairement.

**Porte PASS :** absence de duplication artificielle ou de propagation de prix, tests des correspondances exactes et supplémentaires déjà justifiées, identités et provenances auditées, canaux distincts, cas ambigu/inconnu explicites. Les taux de couverture sont indicatifs, jamais des seuils de rejet.

### G6 — Moteur tarifaire unique et complet

**Travail :** utiliser les travaux et oracles existants de Production, notamment PR #134–#146, comme bibliothèque fonctionnelle plutôt que fusionner l'ancienne pile sans examen. Implémenter tous les **mécanismes tarifaires documentés**, sans nouvelle recherche de prix : kWh, minute, session, connexion, après charge, stationnement, congestion, seuils, paliers, plafonds, minimums, horaires/jours, fuseaux DST, TVA, devises/FX, arrondis, abonnements, éligibilité, frais conditionnels et combinaison de composantes. Différencier préautorisation et frais réellement facturés.

**Porte PASS :** tests unitaires/combinés, historiques et oracle indépendant ; aucun mécanisme documenté ignoré silencieusement, aucune conversion FX inventée ; traitement explicite des données manquantes, ambiguës et inéligibles. **100 % de couverture des règles documentées ne signifie PAS 100 % des offres chiffrables.** Réutiliser notamment les cas Midhope et les autres scénarios prouvés lorsque leurs entrées sont identiques.

### Complément utilisateur du 26/10/2026 — performance et carte (G7/G8)

Le rayon demandé dans l’interface est limité explicitement à **100 km**. Ne jamais le réduire silencieusement. La recette de performance commence à 100 km et, si nécessaire, répète les mesures par paliers de 10 km ; chaque rayon est mesuré, sans supposer qu’un rayon donné est fluide.

La recherche spatiale, les calculs, la liste et la carte doivent traiter les résultats progressivement : toutes les stations correspondantes restent accessibles par pagination, zoom ou déplacement, sans charger simultanément des milliers de fiches ou marqueurs. Le regroupement dépend du zoom et de la densité ; les meilleures offres calculables ont priorité visuelle. Un plafond de 500 stations affichées est strictement transitoire et ne satisfait pas G7/G8.

Les données sources, jointures EVSE et tarifs canoniques sont conservés intégralement. Aucune optimisation d’affichage ne supprime ces données ni ne confond offre calculable, offre brute et tarif incalculable. Ce travail s’inscrit dans la recette G7/G8 et ne retarde pas les priorités G0–G9.

### G7 — Interface TCC V9

**Travail :** carte interactive avec position actuelle ; **une carte par station regroupant ses puissances** ; détail bornes/EVSE/prises, puissance et nombre de bornes ; lignes et tarifs correctement associés à chaque prise. Trois canaux affichés Direct/Electra/Electroverse, y compris « Prix non disponible ». Filtres multi-CPO, multi-abonnements, Tesla uniquement/tous réseaux, critères de puissance et conditions. Batterie, SoC, objectif, date/heure, coût total, temps et coût/km, décomposition des frais et tri sur les combinaisons valides. Sources, dates, devise locale et EUR quand conversion disponible. Vue mobile et ordinateur, carte réellement utilisable ; pas de statut de disponibilité live inventé.

Respecter les exclusions déjà approuvées des garages/non-public et les distinctions entre borne publique, réseau et canal. Un regroupement physique ne transfère aucun prix d'un EVSE à un autre.

**Porte PASS :** tests fonctionnels de carte/filtres/tri, prix/puissance par prise, calcul, absence de frais cachés, états indisponibles, responsive, accessibilité et performance ; données issues de la chaîne réelle ou snapshot identifié, pas de valeurs d'interface codées en dur.

### G8 — Recette technique de bout en bout et préproduction

**Travail :** vérifier collecte/artefacts → import Production → normalisation → jointures → calcul → UI avec une préproduction séparée du site public. Tests de non-régression, sécurité des workflows, intégrité, provenance, performances et restauration. Corriger les écarts avant une mise à disposition déclarée « prête ».

**Porte PASS :** tests d'intégration réellement exécutés, preuves par famille représentative, blocages critiques résolus, rollback disponible, URL de préproduction vérifiée. Une fixture ou simulation seule ne constitue pas une preuve de transfert GitHub ou de déploiement réel.

### G9 — Recette utilisateur et promotion ultérieure

**Livrable :** URL de préproduction et parcours simple permettant à l'utilisateur de vérifier directement des stations représentatives, puissances AC/DC, Direct/Electra/Electroverse, filtres, carte, batterie/objectifs, prix et coût/km, sur ordinateur et téléphone. Mécanisme simple de signalement d'anomalie visible dans l'interface.

**Porte PASS :** confirmation explicite de l'utilisateur après test de l'interface. **Ne pas confondre validation de préproduction et autorisation de déployer publiquement.** Publication/bascule/traffic switch exige un accord distinct ; snapshots immuables et possibilité de rollback.

## 5. Politique de dépendance entre portes et autorisations

- **Ne jamais afficher PASS pour une porte non vérifiée.** Une méthode migrée seulement sur fixture reste fixture_pass ; un essai live non exécuté reste live_pending ; une transmission Actions non exercée reste github_handoff_unverified.
- Lorsque G2 ne peut pas passer uniquement faute d'autorisation de réactiver Actions, **continuer les travaux réversibles et tests locaux des phases suivantes si leurs entrées sont disponibles**, sans déclarer les portes aval PASS ni contourner leur ordre de promotion. Les travaux préparatoires G3–G8 peuvent avancer en parallèle, mais une livraison « prête » exige ensuite l'ensemble des preuves de bout en bout.
- Une autorisation administrative indispensable (Actions GitHub, secrets manquants, hébergement de préproduction) doit être sollicitée de manière minimale et claire ; le reste se déroule en autonomie.
- Ne jamais prétendre qu'une session Codex continue après sa clôture ou qu'une opération distante non lancée a été testée.

## 6. Mode d'exécution, économie de quota et journal

Traiter des **familles de méthodes homogènes en lots**, pas un CPO par session si d'autres méthodes analogues peuvent être migrées avec le même adaptateur. Utiliser les fixtures sans réseau pendant le développement ; ajouter tests ciblés à chaque famille ; exécuter les validations complètes aux portes. Ne pas refaire les audits G0/G1 ni les enquêtes tarifaires déjà terminées. Ne pas fabriquer un PASS pour faire progresser artificiellement le projet.

Codex doit poursuivre **sans clôture volontaire après un lot réussi**, jusqu'à une limite réelle de session/quota, un blocage irréductible ou une autorisation requise. Lors d'un arrêt, sauvegarder commits sur la branche autorisée, preuves, état de l'arbre local, SHA, tests, blocages et **prochaine commande/opération exacte** dans memory/V9_REBUILD_PROGRESS.md. Préserver les modifications non commitées ; après reprise, commencer par git status, git fetch et comparaison des SHA.

**Communication utilisateur :** ne pas présenter de rapports techniques détaillés après chaque CPO. Un bref état seulement si l'exécution est interrompue ; l'utilisateur attend principalement l'interface de préproduction. Ne pas envoyer des données de secret, des logs complets ou des décisions techniques triviales pour validation.

## 7. Sources de vérité et instructions de reprise

1. **Ce document** : mandat durable G0–G9, choix et restrictions utilisateur.
2. **memory/V9_REBUILD_PROGRESS.md** : statut courant réel, preuves, compteurs de méthodes restants et prochaine opération. Il peut évoluer plusieurs fois par jour et ses passages anciens ne priment pas sur sa dernière entrée.
3. **migration/v9/** : inventaires G1, méthodes, destinations, exceptions et traces du périmètre.
4. **v9_rebuild/** et **scripts/validate_v9_g*.py** : implementation et validations actuellement déployées sur la branche.
5. **memory/README.md**, **memory/CURRENT.md** et documents métier existants : règles spécifiques, archives, évolutions et liens ; les anciennes descriptions de workflows ne sont pas des ordres de les restaurer.
6. **Production docs/ARCHITECTURE.md** et PR Production #134–#146 : versionnement/promotion et preuves du moteur/UI ; ne pas fusionner automatiquement une pile Draft historique.

Au début de toute session Codex : lire AGENTS.md, ce cahier des charges et le tableau de bord, relever git status, HEAD local et branche distante, comparer et préserver les modifications en cours, puis reprendre **la dernière opération non terminée**. Si la spécification doit changer, documenter explicitement la décision utilisateur et modifier ce document ; ne pas faire dériver les règles à partir d'une ancienne instruction de chat ou d'un état transitoire.

---
**Critère ultime :** un TCC V9 de préproduction cohérent et vérifiable visuellement par l'utilisateur, acquis sans perte silencieuse de méthodes utiles, sans nouvelle recherche tarifaire, sans seuils artificiels EVSE et sans toucher au site public avant son accord.
