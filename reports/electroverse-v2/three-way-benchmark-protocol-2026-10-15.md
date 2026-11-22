# V2 R&D — protocole benchmark trois variantes (15/10/2026)

## Livraison
Ajout de `experiments/electroverse-v2/benchmark-three-way.mjs` sur la branche Draft #331. Script **offline uniquement**, utilisant le transport simulé déjà présent et la même fixture archivée de 24 stations / 113 EVSE / 150 connecteurs. Aucun module du collecteur canonique, aucun client HTTP.

Le script exécute 7 passages appariés du modèle V1, du simulateur V2 et du nouveau runner journal, dans des répertoires temporaires séparés. Il mesure : durée murale, CPU du processus, requêtes simulées, tailles des fichiers produits et nombre de fichiers. Il vérifie pour chaque passage l'équivalence multiensemble V2/journal (stations, EVSE, connecteurs, mappings et composants tarifaires). Il exécute ensuite le scénario d'interruption au deuxième lot pour V2 et journal et vérifie la parité complète à la reprise. Résultats JSON imprimés sur stdout pour ne pas écrire dans Production.

Commande : `node experiments/electroverse-v2/benchmark-three-way.mjs`.
Tests obligatoires préalables : `node --test experiments/electroverse-v2/generation_store.test.mjs experiments/electroverse-v2/journal_runner.test.mjs experiments/electroverse-v2/test/model.test.mjs`.

## État de la preuve
**Code publié, pas exécuté au cours de cette session.** Le conteneur courant ne résout pas `github.com`, empêchant de récupérer un checkout Git complet. Les valeurs du rapport précédent sont une estimation de longueur JSON en mémoire et ne doivent pas être présentées comme des mesures disque. Aucun chiffre de vitesse V2-journal, score national ou gain Actions n'est revendiqué ici.

## Réserves méthodologiques
- Modèle V1 distinct du collecteur canonique.
- CPU et I/O sur 24 stations insuffisants pour extrapoler aux 128 shards.
- Comparaison séquentielle V1/V2/journal : possibles effets du cache du système et de l'ordre de passage.
- La taille de fichiers mesure un volume final, **pas** le cumul des bytes écrits, particulièrement défavorable à V2 par réécriture cumulative ; un futur test instrumenté doit comptabiliser les bytes de chaque écriture.
- Aucun scénario GraphQL réseau, quota, latence ni coût GitHub Actions.

## Gate de décision
Avant toute recommandation : exécution prouvée et répétée, extension contrôlée du corpus, tests d'incidents et preuve de parité des tarifs calculés. Jusqu'alors V1 est inchangée et la PR reste Draft.
