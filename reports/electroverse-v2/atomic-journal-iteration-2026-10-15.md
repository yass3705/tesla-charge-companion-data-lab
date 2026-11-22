# R&D Electroverse V2 — Journal atomique par lot (15/10/2026)

## Objet et isolation
Prolongement de la PR Draft #331 uniquement. Prototype autonome `generation_store.mjs` et tests `generation_store.test.mjs` dans `experiments/electroverse-v2/`. Aucun import du collecteur V1, aucune requête HTTP, aucun workflow, secret, cache ou donnée Production modifié. Le journal n'est pas raccordé à `runV2`.

## Stratégie implémentée
Un **fichier JSON immuable par lot** stocke la progression et les enregistrements dans une même unité. Chaque fichier comporte `sourceHash`, index du lot, contenu et SHA-256 interne ; création provisoire suivie de renommage atomique. Au redémarrage, les lots sont lus dans l'ordre, vérifiés et reconstitués. Le rejeu identique ne réécrit pas un lot. Un conflit, un trou d'index, une source différente, une corruption ou un doublon PK stoppe la restauration. Les fichiers temporaires non validés sont ignorés.

Par comparaison avec l'ancien V2 qui écrit **deux fichiers logiques par lot** (état complet + checkpoint), le prototype ne crée qu'**un segment par lot**. Sur 5 lots, cela signifie 5 créations logiques contre 10 dans l'ancien prototype, **sans garantir un gain de durée**. Contrairement aux checkpoints groupés, les lots déjà commités ne sont pas rechargés par le modèle.

## Tests exécutés
Le module et ses neuf tests ont été exercés avec Node.js v22.16.0 dans un environnement local indépendant : **9/9 passent**. Couverture : reprise à deux lots, replay identique, conflit, corruption, fichier temporaire incomplet, trou d'index, source différente, duplication entre lots et garde de chemin. Les tests GitHub Actions de cette PR n'ont pas été relancés : il n'y a pas de workflow expérimental automatique.

## Limites et tâches ouvertes
- `runV2` **n'utilise pas encore** ce journal : on n'a pas de comparaison de performance exécutable V2 initial vs journal.
- Les lignes du journal sont actuellement synthétiques dans les tests ; parité des 24 stations avec ce moteur **non prouvée**.
- Une atomisation par renommage est un modèle local ; la durabilité contre coupure électrique exige flush/fsync du fichier et répertoire, ainsi qu'une discipline de concurrence et verrouillage non implémentés.
- Le stockage grandit par segment ; il faut un mécanisme de compaction sûr, streaming et mesures I/O sur corpus représentatif.
- Aucune validation des réponses GraphQL réelles, pagination réseau, incidents fournisseur ou coût GitHub Actions.
- Rien ne permet encore de sélectionner ce moteur à la place de V1 ou V2.

**Verdict :** progression R&D utile sur le protocole de reprise. Conserver V1 inchangé ; poursuivre uniquement la simulation et les tests isolés si souhaité.
