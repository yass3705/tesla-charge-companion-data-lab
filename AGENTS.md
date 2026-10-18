# Instructions communes — Tesla Charge Companion V9

Ce fichier est la référence versionnée du projet. Depuis `/Users/yassine/Projects/TCC`, le fichier parent `AGENTS.md` est un lien symbolique vers celui-ci. Les instructions explicites de la mission en cours priment.

## Au début d'une mission TCC

1. Lire `tesla-charge-companion-data-lab/memory/README.md` et `tesla-charge-companion-data-lab/memory/CURRENT.md` (ou `memory/...` depuis Data Lab). Lire ensuite les documents métier sources cités pour le sujet ; ne pas réinventer une règle déjà validée.
2. Pour une tâche transversale, examiner les quatre dépôts : Production, Data Lab, Stable et Updater Test. Relever branche, état local, SHA local et `origin/main`. Avant d'intégrer des changements GitHub réalisés depuis ChatGPT mobile, faire `git fetch origin`, comparer les commits dans les deux sens et n'avancer une branche propre qu'après vérification. Ne jamais écraser des modifications locales ou distantes.
3. Traiter `CURRENT.md` comme un relevé daté. Vérifier séparément ce qui est collecté, audité, validé et réellement publié ; un résultat de test, un rapport ou un commit Data Lab ne prouve pas un déploiement V9.

## Pendant et à la fin des travaux

- Garder les preuves et règles détaillées dans leurs documents sources. Documenter les décisions importantes et les changements fonctionnels dans la même branche ou PR que le changement concerné ; mettre à jour `memory/CURRENT.md` et ajouter une entrée à `memory/HISTORY.md` après chaque évolution significative.
- Une décision prise seulement en conversation est **non synchronisée** tant qu'elle n'apparaît pas dans GitHub. La signaler comme telle dans le passage de relais ; la versionner avec la modification concernée dès que la publication est autorisée.
- Préserver les secrets et les données du dépôt privé Updater Test. Data Lab est public : n'y copier ni contenu confidentiel, ni identifiants sensibles, ni références internes non nécessaires. Exécuter le contrôle public du dépôt avant publication.
- Ne jamais déclencher un déploiement Production sans autorisation explicite. Vérifier les déclencheurs Actions avant un push ou une PR. Respecter les autorisations de la mission pour commits, push, PR et fusion.
- Pour interrompre ou reprendre, suivre la procédure courte de `memory/README.md` : enregistrer état, preuves, tests, blocages, prochaine action et lien vers la branche ou la PR. Une nouvelle session doit reprendre ces éléments sans relancer tous les audits en l'absence d'un risque concret ou de nouvelles données.
