# TCC V9 — Convention commune de traçabilité et de reprise ChatGPT / Codex CLI

**Décision utilisateur : 21 novembre 2026.** Convention permanente applicable à toute intervention sur TCC V9, sans création d'une nouvelle architecture de mémoire. Cette convention organise le travail ; **elle ne donne pas à elle seule l'autorisation de lancer une collecte, de modifier des secrets, d'activer un workflow, de fusionner sur main ou de publier Production**. Les autorisations explicites de la mission, la spécification G0–G9 et les protections GitHub restent applicables.

## 1. Références obligatoires à lire AVANT toute intervention

1. `AGENTS.md` dans Data Lab, puis le présent `memory/WORKING_AGREEMENT.md`.
2. `memory/README.md` et `memory/CURRENT.md`, en distinguant **date de constat** et **état actuel vérifié**.
3. `memory/V9_REBUILD_PROGRESS.md` et `docs/v9-rebuild/PROJECT_SPEC_G0_G9.md` ; consulter les documents techniques sources concernés.
4. Dans **Data Lab et Production**, vérifier la branche cible réelle (`rebuild/v9-20261020` tant que la reconstruction demeure active), les HEAD distants, les changements récents, PR ouvertes, tests et runs GitHub. Ne jamais confondre `main` avec la branche de reconstruction. Pour un chantier transversal, tenir compte de Stable et Updater Test sans divulguer de contenu privé.
5. Depuis Codex CLI, contrôler en plus `git status --short`, `git branch --show-current`, `git fetch origin`, `git log HEAD..origin/<branche>` et `git log origin/<branche>..HEAD`. Examiner tout changement local avant pull/rebase/merge. Depuis ChatGPT, relire directement GitHub et ne pas prétendre connaître l'arbre local du Mac.

Une nouvelle conversation ou session **commence par cette lecture et cette vérification**, même si l'agent croit se souvenir du projet. Une session passée ou un message conversationnel ne remplace jamais les fichiers versionnés.

## 2. Source de vérité et responsabilité des données

- **Git / commits** : source de vérité du code et des décisions versionnées ; chaque modification identifiée par dépôt, branche, SHA complet et chemin.
- **Artefacts et catalogues** : source de vérité des octets, manifestes, SHA-256, fenêtres, versions d'entrée et provenance ; les références seules ne garantissent pas leur disponibilité après expiration.
- **`CURRENT.md`** : tableau de bord synthétique, état vérifié et prochaine opération concrète, avec horodatage. Une entrée datée ancienne n'est pas une preuve d'état courant.
- **`V9_REBUILD_PROGRESS.md`** et **`HISTORY.md`** : journal chronologique cumulatif des validations, incidents, décisions et passages de relais ; conserver les anciennes preuves, sans les réinterpréter comme une réussite actuelle.
- **`memory/README.md`** : point d'entrée et index ; **`PROJECT_SPEC_G0_G9.md`** : besoins fonctionnels et critères d'acceptation. Toute nouvelle décision utilisateur modifiant une règle métier doit être répercutée dans la source normative concernée, sans inventer une autorisation.
- Lorsqu'un même fichier contient des états datés successifs, le plus récent **ne vaut pas automatiquement PASS** : contrôler la preuve externe correspondante.

## 3. Relevé de modification obligatoire

Pour **chaque changement significatif** (code, méthode, workflow, schéma, mapping, snapshot, règle ou procédure) conserver au minimum :

- **Contexte et but** : problème concret, comportement antérieur, hypothèse, raison de la solution et restrictions du cahier des charges.
- **Identification** : dépôt, branche, SHA parent et SHA résultat, chemins modifiés, contrat d'entrée/sortie, effets éventuels sur Data Lab, Production et les autres collecteurs.
- **Preuves d'exécution** : commandes/tests réellement lancés, résultats PASS/FAIL/NOT TESTED, erreurs connues ; run ID et job ID GitHub, statut et conclusion, SHA du code exécuté, artefact ID, génération, SHA-256, date, mode, source et portée.
- **Traçabilité des données** : identités demandées/traitées/restantes, files de reprise, checkpoints parents, fenêtres réussies/échouées, dédoublonnage, exclusions/ambiguïtés, statut source `last-good`, originalité des données et fraîcheur réellement démontrée. Ne jamais inventer une identité, un tarif ou un rattachement EVSE.
- **Chaîne jusqu'à l'utilisateur** : distinction entre (a) données collectées, (b) artefact techniquement validé, (c) import Production, (d) bundle servi sur URL vérifiée, (e) approbation utilisateur G9.
- **Sécurité et rollback** : secrets non exposés, protections du site public, chemin de restauration, version précédente connue, problèmes ouverts, prochaine opération exacte et propriétaire du composant.
- **Concurrence** : vérifier avant chaque écriture si une autre session/CI agit sur les mêmes fichiers ou checkpoints ; réconcilier plutôt que pousser en aveugle.

Le niveau de détail doit permettre de **reproduire un diagnostic et reprendre au point exact**, sans réexécuter inutilement de grosses acquisitions. Privilégier les liens vers rapports et preuves canoniques plutôt que recopier de gros fichiers dans la mémoire.

## 4. Discipline de modification et de passage de relais

1. Un seul intervenant modifie à la fois un composant, une branche ou un checkpoint partagé. Se coordonner explicitement entre ChatGPT/GitHub et Codex CLI. Pas de relance parallèle d'une même génération Electroverse.
2. Réutiliser la branche de reconstruction commune quand une modification sûre et compatible peut y être réalisée avec un historique propre ; créer une branche temporaire **seulement** si isolation nécessaire, et en documenter l'intégration. Ne pas créer de nouvelle architecture ou de branche permanente par défaut.
3. Commits ciblés et lisibles, vérification du diff, de l'absence de secrets, des déclencheurs Actions et du contrôle de sûreté publique avant publication. Ne jamais écraser une modification locale/distante ou forcer une branche sans décision spécifique.
4. Après une étape validée, publier les preuves immuables, puis actualiser **`CURRENT.md`** et ajouter le détail à **`V9_REBUILD_PROGRESS.md` / `HISTORY.md`** selon leur rôle. Consigner explicitement ce qui reste ouvert et ne pas marquer `PASS` faute de preuve.
5. Avant une interruption, laisser un état reprenable : SHA, run/artefact, checkpoint parent et curseur, résultats, erreurs, dépendances, prochaine commande sûre, vérification de non-concurrence.
6. Après une reprise, **vérifier** l'état réel des runs et artefacts ; corriger une mémoire périmée avant toute nouvelle opération. Les jobs GitHub qui affichent `success` avec `checkpointed` restent **partiels**, pas une collecte complète.
7. Les artefacts GitHub peuvent expirer. Pour une reprise au-delà de la rétention, prévoir une sauvegarde pérenne **autorisée**, horodatée et liée par empreintes ; ne jamais publier des secrets ou de grandes archives brutes dans un dépôt public par défaut.

## 5. Mandat fonctionnel et frontières de sécurité

- Priorité immédiate évoquée : **Electroverse de bout en bout**, en conservant la méthode de collecte fournisseur existante, les pauses nécessaires, le last-good, les 128 shards, les checkpoints avec filiation contrôlée, les statuts/overlays, l'import et la recette du navigateur. La présente formalisation documentaire **ne lance pas** ce chantier ; attendre l'ordre explicite.
- Ne jamais confondre un cache Electroverse `checkpointed`, un rafraîchissement partiel, un cache complet validé et un prix effectivement servi dans TCC.
- Les travaux non Electroverse restent attribuables à Codex CLI après synchronisation, sans que leurs progrès antérieurs soient effacés.
- Les collectes peuvent tourner de manière autonome dans GitHub Actions si elles ont été délibérément autorisées/configurées ; ni ChatGPT ni Codex CLI ne continuent à travailler en arrière-plan après leur session.
- Pas de modification du site Production public ni de `main` sans autorisation applicable et contrôles requis. Updater Test privé / Tesla-Mac reste hors modification de ce protocole.

## 6. Vérification des accès AVANT démarrage effectif

Contrôler pour la session courante : lecture + écriture Git des dépôts requis, accès aux workflows et logs, capacité effective de **déclencher** les collectes nécessaires, accès aux ZIP d'artefacts et aux règles/secrets **via l'exécution autorisée**, capacité d'import Production et de recette Netlify. Une permission générale de dépôt ne garantit pas chacune de ces opérations. Documenter les impossibilités et choisir des chemins de repli sûrs. Ne jamais affirmer que les tests de permissions non effectués ont réussi.

## 7. Message de reprise minimal

« Reprenons TCC V9. Lis `AGENTS.md` et `memory/WORKING_AGREEMENT.md` depuis `rebuild/v9-20261020` de Data Lab, puis `memory/README.md`, `memory/CURRENT.md`, `memory/V9_REBUILD_PROGRESS.md` et `PROJECT_SPEC_G0_G9.md`. Vérifie les commits et les runs/artefacts actuels Data Lab/Production, les éventuelles modifications locales Codex et les autorisations. Restitue l'état réellement démontré avant toute modification. »
