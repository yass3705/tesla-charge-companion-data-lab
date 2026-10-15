# REVE Espagne : transfert du constructeur national

Le dernier bundle V9 complet connu est disponible dans le dépôt public Stable au
commit `39c5bcaadd42b9ba932824f89dc8b97e20ebb762`. Le mode manuel `seed`
le copie une seule fois dans `data/reve_v2/validated_runtime/`, puis vérifie
les empreintes et le versionne dans Data Lab. Ses manifestes datent du
27 septembre 2026 : 13 980 stations, 42 887 identifiants EVSE uniques,
43 026 occurrences physiques et 44 281 offres directes. Le validateur vérifie
les empreintes SHA-256, les fichiers compressés et les totaux des tuiles.
Ce bundle est un **dernier état validé conservé**, pas une collecte fraîche.
Avant l'exécution réussie du mode `seed`, le transfert reste incomplet et le
rafraîchissement mensuel refuse de démarrer.

Les cinq scripts `reve-v2-*.mjs` utiles à l'extraction, la normalisation et la
compilation sont portés sans changement fonctionnel depuis la branche
historique de l'extracteur. Le workflow mensuel Data Lab exécute la collecte
complète dans un répertoire temporaire. Il ne remplace le bundle validé que
si toutes les pages sont capturées, que le rapport de compilation est valide,
que les empreintes concordent et qu'aucun compteur station/EVSE/offre ne
baisse sans revue. Si l'API échoue, les données versionnées restent intactes.
Le flux horaire `spain-reve-v9-stream-refresh.yml` et ses checkpoints sont
indépendants et ne sont ni modifiés ni réinitialisés.

Le transfert du **constructeur source** ne bascule pas à lui seul Production :
le build ES doit encore être raccordé au bundle Data Lab par SHA immuable et
validé avant le retrait du workflow mensuel Updater Test qui écrit vers Stable.
Le 429 courant relève de l'exploitation de l'API ; il ne justifie aucune
réinitialisation de curseur ni promotion d'un overlay incomplet.
