# Architecture V2 expérimentale

## Prototype livré

`experiments/electroverse-v2/model.mjs` est **hors ligne** : aucun import du collecteur V1, aucune fonction réseau, aucun secret. Il accepte une fixture explicite déjà archivée et écrit uniquement sous un répertoire temporaire `/tmp/electroverse-v2-*`. Le garde de chemin refuse les caches canoniques. Aucun workflow automatique n'est créé.

Le flux prototype est : fixture validée → IDs exacts → batch plafonné à **5** → retry borné des codes 429/5xx/timeout simulés → fallback individuel uniquement des alias absents ou invalides → validation du schéma/PK et du SHA tarifaire → état dernier bon + checkpoint atomiques par batch → comparaison exacte multiensemble V1/V2. Un 429 persistant clôt le groupe comme « à reprendre » au lieu de déclencher une tempête de fallbacks. Les réponses partielles, pagination incomplète et curseur bloqué ne remplacent jamais une station validée. Une corruption de checkpoint ou de cache arrête l'exécution.

Le prototype ne transforme aucun composant tarifaire. Il transporte la projection V1 complète, y compris `priceComponents`, restrictions, gratuité, TVA, devise, PK EVSE/connecteur, puissance et mapping IRVE. Un tarif nouveau n'est accepté qu'avec son hash vérifié. La sélection de nouvelles stations non mappées reste hors portée : aucune identité n'est inventée.

## Évolution candidate, non implémentée

1. **Stockage segmenté** : le prototype réécrit son petit `last-good.json` par batch ; cela ne passe pas à l'échelle des 346 MB nationaux. Une V2 opérationnelle devrait utiliser un journal de segments immuables ou des shards expérimentaux avec compaction contrôlée, pointeur atomique et collecte des objets orphelins après validation.
2. **Ordonnancement** : répartir les 4 blocs hebdomadaires sur des fenêtres plus courtes avec âge maximal garanti, sans supprimer la revue complète des 22 818 mappings. Ne pas augmenter automatiquement les lots au-delà de 5 ni la concurrence au-delà de 2 tant que l'API n'a pas été mesurée avec autorisation.
3. **Découverte** : garder le scan à zoom 9 jusqu'à preuve qu'un marqueur de changement ou un zoom alternatif couvre au moins les mêmes IDs. Isoler le mapping des 3 057 nouveaux IDs non mappés ; jamais de jointure par proximité seule.
4. **Instrumentation** : par batch, enregistrer durée, bytes, codes HTTP, erreurs GraphQL, nombre d'alias complets, pagination et latence ; un compteur de réussite du job ne suffit pas.
5. **Multi-pays** : rendre pays/régions et mapping des paramètres explicites, chacun avec son espace de checkpoint et son gate de couverture ; aucun pays nouveau n'est collecté par ce prototype.

## Sécurité de reprise et décision

Le dernier bon est écrit avant le checkpoint ; un crash entre les deux peut provoquer une requête répétée, mais ne peut avancer le checkpoint au-delà des données vérifiées. La reprise garde les anciens prix valides pour les groupes non vérifiés et signale leur manque de fraîcheur. Cette expérimentation **n'est pas recommandée pour remplacer V1** tant que le stockage national, la pagination réelle, les conditions de quota et la parité complète n'ont pas été validés.
