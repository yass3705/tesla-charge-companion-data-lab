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

### Tesla/Mac : catalogue autonome (decision utilisateur du 5 novembre 2026)

Tesla est une exception prioritaire a la consolidation nationale/CPO dans les neuf pays. Seul le catalogue Tesla/Mac cree ses Superchargeurs et configurations ; aucun EVSE_ID national n'est requis pour afficher ou tarifer ces configurations. Les identifiants Tesla restent des identifiants source, jamais des EVSE_ID officiels inventes. Les tarifs ne quittent jamais leur portee de configuration prouvee. Les entrees nationales explicitement identifiees Tesla sont exclues de l'affichage et conservees brutes pour audit, sans jointure ni transfert de prix. Les autres reseaux restent exclusivement nationaux lorsqu'une base nationale qualifiee existe. Tester Le Chesnay, Milan, MAD et les neuf pays, y compris absence de correspondance nationale et erreur d'une source nationale lors d'une recherche Tesla uniquement. L'acquisition Tesla/Mac dans Updater Test reste inchangee.

La nouvelle mission autorise les tests de remise en service Actions Data Lab dans une fenetre bornee et reversible, apres preuve que main et les anciens workflows enregistres ne peuvent rien declencher. Cette autorisation ne vaut ni fusion main, ni activation permanente, ni publication publique.

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

### Précision utilisateur du 23 novembre 2026 — snapshot technique pour alléger le catalogue tarifaire actif

**Finalité du statut acquis à l'instant de collecte :** l'utilisateur demande de récupérer les états des bornes/EVSE Electroverse pour écarter les équipements effectivement défectueux ou hors service du **catalogue tarifaire actif servi par TCC**, et ainsi limiter son volume. Ce snapshot technique n'a **pas** pour objectif d'indiquer la disponibilité libre/occupée à l'utilisateur. Les statuts sont relevés successivement : conserver l'heure réelle par ChargingLocation PK et, si disponible, EVSE/prise, sans les présenter comme un instant T universel.

**Sémantique par EVSE, sans suppression irréversible :**
- `AVAILABLE` ou `CHARGING` : équipement opérationnel au moment de la mesure, à conserver dans le catalogue tarifaire actif ; `CHARGING` est occupé mais non défectueux.
- `OUTOFORDER` (et équivalent explicitement documenté de panne/inopérabilité) : marquer l'EVSE hors service et l'exclure **de la projection active Electroverse**, seulement si le statut fournisseur lui est rattaché sans ambiguïté avec une observation techniquement exploitable. Réintégrer lors d'une mesure ultérieure établissant le retour en service.
- `BLOCKED`, `UNKNOWN`, absence d'information, appel API en erreur/429, défaut de jointure, hors communication ou snapshot non suffisamment récent pour conclure à une panne actuelle : **pas de suppression sur cette seule base**. `UNKNOWN` peut signifier une absence de télémétrie, pas un défaut avéré. Un blocage/occupation temporaire ne retire pas un tarif.
- `REMOVED`/désactivation administrative si représenté et confirmé par une source faisant autorité : appliquer la politique de retrait **du référentiel compétent** et conserver le journal des changements. Ne pas extrapoler cette signification aux autres états.

**Maître de catalogue et granularité :** dans les pays disposant d'une base nationale (France : IRVE), **celle-ci reste la seule maîtresse des stations/EVSE visibles**. La décision nationale `en_service`/hors service prévaut pour la présence dans le catalogue réglementaire. Un état Electroverse ne supprime ni station ni EVSE de la base nationale : il sert uniquement au filtrage de l'overlay Electroverse et, si souhaité, d'une vue active dérivée. Sur une station multiborne, n'écarter que l'EVSE/prise réellement défectueuse ; ne pas éliminer les voisins opérationnels. Les données brutes, identifiants, offres d'origine, provenance, changements de statut et checkpoints restent conservés pour audit, recalcul et restauration. Mesurer séparément les gains sur la **projection active servie** ; l'archivage peut accroître le volume brut, ce n'est pas un objectif de suppression physique des sources.

**Séparation du traitement et garde anti-faux positifs :** la collecte de statuts est souhaitée pour enrichir le snapshot technique, mais l'échec/absence d'une collecte complète ne bloque ni tarifs ni jointures ni calculs. Le retrait automatique pour panne repose sur un état explicite, daté, fiable, vérifié et suffisamment récent **pour cette décision locale**, sans réintroduire une échéance globale de 16 h sur l'inventaire historique. Si la preuve devient trop ancienne ou contradictoire, cesser d'appliquer le retrait automatique plutôt que prétendre que la panne perdure. Aucun `UNKNOWN` ne doit être assimilé à `OUTOFORDER`.

**Dette technique à corriger :** `scripts/audit_electroverse_status_gate_postbuild.mjs` exige actuellement `AVAILABLE`/`CHARGING` pour toutes les offres Electroverse ; cette ancienne règle exclut aussi `UNKNOWN`/`BLOCKED`, à tort au regard de la présente décision. Refondre ce contrôle, les vues dérivées et leurs tests **après coordination avec le run Electroverse en cours**, sans lancer une nouvelle collecte ni toucher à Production automatiquement. Ne pas déclarer cette politique entièrement implémentée avant preuve.

### Décision utilisateur du 23 novembre 2026 — TCC comparateur TARIFAIRE, statuts live facultatifs

**Principe permanent confirmé explicitement : Tesla Charge Companion est et restera un comparateur de tarifs de recharge.** L'utilisateur vérifiera toujours la disponibilité réelle dans l'application de recharge avant utilisation. TCC ne doit pas présenter de disponibilité instantanée comme une fonctionnalité fiable attendue, ni exiger les statuts live pour afficher une station, une borne éligible au référentiel national, un connecteur, les offres CPO/eMSP ou le calcul/comparaison des coûts.

**Fin de la limite de 16 h comme blocage de collecte :** la fenêtre historique de 16 h ne vient pas de l'API Electroverse et ne doit plus déclencher le retraitement de stations déjà vérifiées, le rejet d'un checkpoint, l'arrêt d'un job ou l'interdiction de constituer un inventaire historique de couverture. Conserver les vraies valeurs de statut et leurs dates de provenance. Les nouvelles observations doivent disposer d'un horodatage par ChargingLocation PK ; pour les anciennes, dont l'heure individuelle n'avait pas été enregistrée, ne pas inventer cet horaire : seules les bornes de temps de partition restent attestées. Un indicateur de fraîcheur peut exister comme diagnostic, mais **ne constitue plus une porte de collecte ou de tarification**. Ne jamais annoncer une observation ancienne comme disponibilité « actuellement libre » ou « actuellement occupée ».

**Priorités d'exécution :** la robustesse du cache tarifaire, les rapprochements officiels par EVSE et les comparaisons de coûts priment sur tout recensement live. Les collectes de statuts résiduelles sont facultatives, découplées, non bloquantes et sauvegardées par checkpoints vérifiables ; le rythme peut dépasser 16 h si nécessaire. Les erreurs/429 ne doivent pas entraîner de relecture des succès conservés. L'état administratif « en service » fourni par une base nationale reste distinct des informations de disponibilité Electroverse. La disponibilité live n'est pas une condition d'attribution d'un tarif Electroverse ni un substitut à l'identification station/EVSE/prise.

**Publication et traçabilité :** aucun statut ancien ne doit être promu en disponibilité live, aucune publication Production n'est autorisée par cette décision ; la tarification et la provenance demeurent les sources de vérité du produit. Les invariants de sécurité, la provenance, les règles 429 par station et l'interdiction d'inventer un tarif ou un statut sont maintenus.

### Décision utilisateur du 22 novembre 2026 — disponibilité live non bloquante

**Priorité impérative : fiabiliser d'abord la chaîne d'actualisation technique des données Electroverse (tarifs, cache, incrémentalité, erreurs/HTTP 429, checkpoints, intégrité, provenance, import et mise à jour)**, puis poursuivre les autres volets TCC V9. **La disponibilité en temps réel d'une borne/EVSE ne constitue pas un prérequis ni une porte bloquante pour développer, tester et préparer les tarifs, les jointures nationales, le moteur de calcul, la carte, l'interface ou la préproduction.** Une collecte des 16 partitions de statuts incomplète, périmée ou ralentie par le fournisseur ne doit donc pas arrêter ces travaux.

**Séparer deux produits de données :** (1) catalogue national/EVSE et statut administratif/technique fourni par la base nationale lorsqu'il existe, utiles à la politique des stations affichées ; (2) disponibilité instantanée Electroverse (par exemple AVAILABLE/CHARGING), facultative et mise à jour indépendamment. L'absence de la seconde ne doit ni supprimer une borne nationale valide, ni effacer les offres/tarifs, ni bloquer une recette d'affichage des prix. Ne jamais inférer AVAILABLE/CHARGING, prolonger artificiellement la fraîcheur, présenter un statut périmé comme actuel ou confondre disponibilité live et « en service » national : afficher **« Disponibilité non disponible »** ou ne pas afficher de statut live, avec date/provenance lorsque utile.

**Découplage de l'overlay :** la préparation du rapprochement **tarifaire** Electroverse ↔ référentiel national (identité station/EVSE/prise, opérateur, adresse/GPS, portée et règles strictes d'attribution) peut avancer sur un cache tarifaire complet et vérifié **sans attendre le ledger national de statuts live**. L'enrichissement par les statuts live reste une tâche ultérieure distincte, non bloquante ; lorsqu'elle sera activée, elle exigera ses contrôles de fraîcheur, de provenance, de portée et une validation de ses 16 partitions. Cela **ne déclare pas une porte G2–G9 PASS** : tout livrable doit toujours réussir ses propres critères de sûreté et de qualité, mais aucune porte ne doit transformer la seule absence de disponibilité live en blocage général.

**Exécution en cours non modifiée par cette décision :** le run statuts déjà autorisé [45049654722](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45049654722) peut poursuivre son exécution bornée et sauvegarder ses checkpoints, sans priorité supplémentaire, relance parallèle ni promotion. L'objectif immédiat reste la fiabilisation du renouvellement des données ; la couverture de disponibilité live complète est reportée après cette fiabilisation. Ce texte est une décision de priorisation et de critères, **pas une implémentation déjà testée du découplage**.

### Décision utilisateur du 22 novembre 2026 — budget 429 par station, jamais par partition/run

Pour la collecte des statuts live Electroverse, la temporisation cumulée **maximum 480 secondes est propre à chaque station identifiée par son ChargingLocation PK**, et ne doit **jamais** être accumulée sur toute une partition, sur plusieurs partitions ou à l'échelle du run GitHub. L'acquisition d'une station comprend potentiellement une requête groupée avec une autre station, ses pages supplémentaires et des appels individuels de secours ; les pauses 429 imputables à ces appels sont décomptées de **chaque station impliquée**, pas des autres. Une fois la station entièrement validée et sauvegardée, libérer son compteur. Les autres stations doivent conserver leurs propres budgets, même si le temps global cumulé d'attente dépasse 480 secondes.

Conserver la règle : **429 → attendre 60 secondes → nouvelle tentative ; nouveau 429 consécutif → 120 secondes ; troisième 429 consécutif → 300 secondes ; quatrième 429 consécutif → arrêt du run et checkpoint**, sans retraitement des succès. Le `Retry-After` explicite ne peut jamais être raccourci par cette politique ; s'il excède les bornes de sécurité, arrêter en sauvegardant. Le budget par station est distinct du **temps maximal du job GitHub**, de la politique de fraîcheur de 16 h et des règles de complétude. Les erreurs individuelles non-429 restent différées après le balayage des 16 partitions ; la publication nationale reste interdite tant que la couverture/fraîcheur stricte n'est pas vérifiée. Ceci ne constitue pas une autorisation de démarrer un run fournisseur.

### G5 — Jointures nationales, CPO, Electra, Electroverse

### Priorité de rapprochement base nationale ↔ Electroverse — décision utilisateur du 21 novembre 2026

**Règle commune à tous les pays pris en charge** (France d'abord, puis autres bases nationales lorsque le fournisseur y est effectivement couvert). Avant de déclarer une liaison nationale/Electroverse indisponible, appliquer **obligatoirement et dans cet ordre** :

1. **Correspondance des bornes ET de l'opérateur** : rechercher les identifiants station, EVSE/prise et connecteur officiels ou les alias exacts déjà validés, en vérifiant la concordance de l'opérateur/CPO et du pays. Le niveau exact de la preuve (station, EVSE, prise, groupe) doit être conservé. La correspondance d'une station ne prouve pas à elle seule celle de chacune de ses prises.
2. **En l'absence de correspondance fiable à l'étape 1, adresse OU coordonnées GPS ET opérateur** : rapprocher les stations sur leur adresse normalisée ou sur une proximité GPS conforme aux règles déjà documentées (5–10 m pour les cas concernés), **avec concordance obligatoire de l'opérateur** et du pays. Contrôler l'unicité du site candidat, l'identité/réseau, les types de connecteurs, puissances, effectifs de prises et statuts lorsqu'ils sont disponibles. Une adresse postale commune à plusieurs stations ou une distance géographique seule n'autorise aucun rattachement.
3. **Seulement après échec des deux étapes, liaison non résolue** : garder la station/EVSE nationale et la donnée Electroverse source, ainsi que la raison et les candidats rejetés ; ne pas effacer la borne ni inventer de prix. Si une offre Electroverse identifiée existe mais ne peut être attribuée ou calculée sans ambiguïté, afficher **« Tarif incalculable »** ; si aucune offre exploitable n'est identifiée, **« Prix non disponible »**, selon la politique existante.

**Garde de portée** : même lorsqu'une station est rapprochée par adresse/GPS + opérateur, attribuer un prix **par EVSE/prise uniquement avec preuve de portée** ; les équivalences de groupe déjà autorisées exigent même puissance/type, même site et prix Electroverse homogène entre les prises concernées. En cas de grilles différentes, d'identifiants contradictoires, de plusieurs candidats, de différences d'opérateur ou de données insuffisantes, **aucune attribution automatique**. Ne pas substituer le tarif direct CPO au tarif eMSP. Documenter méthode (`exact+operator`, `validated_alias+operator`, `address+operator`, `gps+operator`, `unmatched/ambiguous`), pays, sources, IDs, distances quand pertinentes, contrôles, provenance/SHA et rejet. Les critères opérationnels doivent être testés en France sans seuil arbitraire de volume, puis appliqués aux autres pays sans inventer de couverture.

**État de cette décision : spécification documentaire, pas correctif déjà implémenté ni résultat de jointure vérifié.** Elle doit être traduite en tests (priorité et fallback, unicité, faux positifs et aucune propagation de prix) avant toute promotion Production.


**Travail :** réutiliser les règles et rapprochements déjà documentés ; joindre les offres avec **identité EVSE/prise et portée source prouvées**. Correspondance par GPS/puissance seulement selon les règles déjà établies et sans propagation tarifaire arbitraire à la station. Distinguer données nationales, CPO direct et eMSP ; traiter les EVSE non rapprochés sans les supprimer arbitrairement.

**Porte PASS :** absence de duplication artificielle ou de propagation de prix, tests des correspondances exactes et supplémentaires déjà justifiées, identités et provenances auditées, canaux distincts, cas ambigu/inconnu explicites. Les taux de couverture sont indicatifs, jamais des seuils de rejet.

### Complément utilisateur du 24 novembre 2026 — grille G5 par station/EVSE/prise et diagnostic pérenne des rejets

**Décision obligatoire :** appliquer la grille approuvée ci-dessous à la France IRVE ↔ Electroverse, puis aux autres bases nationales couvertes. Séparer l'identification de la station, celle de l'EVSE/prise, la validation technique, la preuve de portée tarifaire et le contrôle de panne. L'identité CPO doit être démontrée par une source fiable et indépendante (identité explicite, alias déjà validé ou autre preuve indépendante recevable) ; une table globale des operatorId numériques Electroverse n'est pas une condition exclusive. Ni majorité de libellés, ni préfixe, ni ressemblance de noms seuls ne constituent une preuve.

| Critère station | Priorité 1 : identifiants + CPO | Priorité 2 : adresse OU GPS + CPO |
| --- | --- | --- |
| Pays et CPO | Identiques, alias CPO documenté admis | Identiques, alias CPO documenté admis |
| Identité station/EVSE | Identifiant exact ou alias exact validé à son niveau | Identifiant station exact non obligatoire ; identité EVSE/prise reste à établir |
| Adresse/GPS | Non bloquant seul si identité exacte prouvée | Adresse normalisée exacte OU GPS dans la tolérance documentée de 5–10 m, jamais >10 m pour ce seul repli |
| Unicité | Obligatoire | Obligatoire ; rejeter les sites concurrents non résolus |

**Contrôles systématiques par EVSE/prise pour les deux méthodes, même avec un identifiant exact :** identité source et nationale au niveau effectivement prouvé ; AC/DC identique ; type de prise identique après normalisation des nomenclatures ; puissance AC identique hors écarts d'arrondi/nominal justifiés ; puissance DC identique en priorité, tolérance de 15 kW uniquement pour rechercher des candidats, sans autoriser automatiquement le match. Toute différence de puissance retenue nécessite une justification documentée. Vérifier nombre de bornes/prises et cardinalité, unicité du rattachement, portée du prix par EVSE/prise et, si groupe déjà autorisé, même site, mêmes caractéristiques et homogénéité tarifaire. Une contradiction technique non résolue interdit l'attribution du prix même avec identifiant exact. Le contrôle des pannes confirmées récentes intervient après le rapprochement, reste distinct de l'identité et suit sa politique existante. L'IRVE demeure maître ; aucune création autonome de station, aucun transfert de prix entre prises.

**Journal de décision exhaustif et durable, requis pour le PASS G5 et la recette G8/G9 :** pour chaque station/EVSE/prise nationale comparée à Electroverse, conserver la décision et les candidats effectivement examinés, y compris rejetés, même si aucun prix n'est attribué et si la borne n'apparaît pas dans une vue filtrée. Garder tous les critères bloquants constatés (pas seulement le premier), le premier motif déterminant selon l'ordre de matching, les critères PASS/FAIL/MISSING/NOT_EVALUATED/NOT_APPLICABLE, les valeurs source/nationale observées et normalisées, les écarts et tolérances réellement appliquées, et les preuves/justifications. Ne pas déclarer FAIL pour un critère qui n'a pas été évalué. Ne pas inventer de candidat lorsqu'aucune offre n'a été identifiée. Conserver aussi les correspondances acceptées et leurs méthodes. Les motifs doivent être structurés, stables, interrogeables et différencier notamment : absence de candidat/offre, pays, CPO non concordant ou non prouvé, identité station/EVSE manquante ou contradictoire, adresse, distance GPS (valeur et limite), ambiguïté de site/prise, AC/DC, type de prise, puissance, cardinalité, portée du tarif, homogénéité, prix incalculable et exclusion technique récente. Les statuts de panne, indisponibilité tarifaire et absence de preuve ne doivent jamais être confondus avec un mismatch.

**Traçabilité consultable après mise en production :** associer chaque décision à son pays, identifiant station/EVSE/prise national, identifiants Electroverse (ChargingLocation PK + EVSE PK + connecteur quand disponible), candidat(s), date de comparaison, méthode, version des règles/code et identifiants/SHA des snapshots IRVE/Electroverse. Prévoir un index de recherche par identifiant ou station/adresse permettant de répondre ultérieurement, y compris depuis ChatGPT/Codex CLI, à « pourquoi aucun prix Electroverse pour cette prise ? » sans réinterroger le fournisseur ni reconstituer au hasard une décision ancienne. Associer le diagnostic à la génération effectivement servie et conserver les versions précédentes nécessaires à l'historique et au rollback. Le journal ne peut pas être limité à des exemples, compteurs agrégés, logs CI temporaires ou artefacts Actions voués à expirer ; prévoir un stockage pérenne versionné/archivé autorisé, compact et consultable, sans secret ni données privées, distinct du chargement des tuiles publiques. Ne pas alourdir l'interface de comparaison ; l'accès technique au diagnostic suffit, avec exposition UI éventuelle ultérieure.

**Recette impérative :** vérifier sur données réelles et fixtures des matchs exacts, aliases, adresse/GPS, rejets distincts de CPO, prise, puissance (AC/DC), doublons et absence de candidat, y compris un cas cumulant plusieurs échecs ; contrôler que tous les critères testés et les critères non évalués sont distingués, que le motif et les valeurs originales restent retrouvables dans le snapshot actif et dans une génération archivée après renouvellement, que les comptes réconcilient les décisions, et qu'aucun prix ni EVSE n'est déplacé. G8 doit démontrer la recherche du motif à partir d'une prise réellement servie/non tarifée en préproduction ; ne pas déclarer cette exigence satisfaite sur la seule base de la présente décision documentaire. Aucun changement d'autorisation fournisseur ou de publication.

### Précision utilisateur du 24 novembre 2026 — périmètre IRVE opérationnel et critères Electroverse non vérifiables

**Périmètre actif national :** avant le rapprochement, construire le snapshot de comparaison à partir du référentiel statique national le plus récent effectivement disponible et de son état dynamique compatible, daté et vérifié. En France, ne conserver dans la projection comparative que les PDC explicitement `en_service` dans la base dynamique IRVE (équipements opérationnels, qu'ils soient disponibles ou occupés). Exclure `hors_service`, `inconnu` et l'absence de statut national de cette projection ; garder les données statiques/dynamiques brutes et raisons d'exclusion, et permettre la réintégration dès preuve de remise en service. Ne pas confondre `en_service` IRVE avec un état libre/occupé temps réel : le code national existant utilise `etat_pdc` et non un indicateur de disponibilité. Vérifier la date, provenance, couverture, cohérence des identifiants et réconciliation des effectifs ; ne pas déclarer les anciens statuts actuels ni publier une projection vide si la source dynamique est indisponible. Conserver le last-good et signaler l'incident. Ne pas ajouter de seuil arbitraire de volume. La politique de statuts Electroverse non bloquants en absence de données reste distincte.

**Critères de matching Electroverse :** une valeur absente/vide est `MISSING` (non vérifiable), jamais `FAIL` ni un motif bloquant autonome. Cette décision prévaut sur les formulations antérieures exigeant une concordance positive pour chacun des champs : pays, CPO, adresse, courant, type, puissance et autres attributs Electroverse sont contrôlés lorsqu'ils sont renseignés et comparables. Conserver les valeurs et raisons, distinguer `MISSING`, `NOT_EVALUATED`, `NOT_APPLICABLE`, `PASS`, `FAIL`, y compris pour une correspondance acceptée. Une absence de preuve indépendante CPO alors qu'un code numérique existe n'est pas une contradiction : noter explicitement non vérifiable, sans transformer un code en nom par inférence majoritaire. Aucun remplissage inventé. Un pays ou opérateur réellement contradictoire, un type/courant/puissance contradictoire non justifié, une ambiguïté réelle ou une portée tarifaire non démontrée restent bloquants. Les contrôles de puissance et seuils déjà approuvés restent inchangés.

**Décision d'identité :** permettre le match exact/alias unique dont l'identité et la portée de tarif par EVSE/prise sont démontrées malgré des attributs Electroverse manquants, en conservant leur état non vérifiable. Si l'identifiant exact manque, rechercher l'adresse OU GPS conforme et contrôler les autres éléments réellement disponibles ; ne pas accepter un site ou une prise sur le seul critère de proximité, ni considérer un candidat unique faute de données comme une preuve d'identité. Si les preuves positives restantes ne suffisent pas pour identifier un EVSE unique et la portée de son tarif, classer `UNRESOLVED_INSUFFICIENT_EVIDENCE` (insuffisance de preuve), distinct d'un rejet pour contradiction. L'absence de champ tarifaire ne permet pas d'inventer le prix. Un groupe exige toujours une homogénéité et une portée positives. Les identités et offres historiques sont des candidats, non des validations automatiques. Ne pas traiter un contrôle non exécuté comme une donnée absente. La recette doit vérifier notamment : EVSE exact unique avec pays/CPO manquants et portée établie accepté ; même cas avec puissance ou prise contradictoire refusé ; GPS seul et preuves insuffisantes non résolu ; absence de statut IRVE exclue de la projection, hors service exclu, en_service conservé ; rapprochements et motifs rejouables par génération.

**Constat du 24/11 :** le script existant scripts/france/build_france_irve_dynamic_status_v9.py produit déjà enServicePdcIds sur état en_service et conserve hors_service/inconnu séparément. Le script d'audit réel scripts/audit_electroverse_g5_real_matching.py du run 45350803713 a utilisé le statique IRVE du 20/10 sans ce filtre et classé MISSING dans blocking. Les résultats 0 MATCH_VALIDATED de ce run ne sont donc pas une recette conforme à la présente précision ; reprendre hors ligne avec les deux corrections et des entrées nationales datées. La décision documentaire ne constitue pas une implémentation validée et n'autorise aucune nouvelle collecte fournisseur/publication.

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
