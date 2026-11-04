# Electroverse V2 — gestion des générations, prototype hors ligne — 15/10/2026

## Avancement
Le prototype **pur, sans I/O et sans réseau**, `generation_planner.mjs`, sépare l'identité d'une génération de l'empreinte des tarifs. Il classe les stations en trois catégories : à actualiser (`fetch`), conservées mais **pas revérifiées dans cette génération** (`retained`), et absentes de l'inventaire actuel (`absent`). Les réponses du lot sont rapprochées avec la sélection ; les absences restent `pending`, les doublons et injections d'identifiants sont rejetés. L'empreinte de l'inventaire est distincte des hashes tarifaires.

## Tests effectués
`node --test /mnt/data/tcc-research/generation_planner.test.mjs` sous Node.js 22.16.0 : **8/8 réussis** en 69,7 ms. Le code et la suite ont été ajoutés à la branche de la PR #331, sans modifier le collecteur canonique. Les tests portent sur logique de planification pure, **pas** sur l'écriture/reprise durable du journal ni la collecte réelle.

## Limites critiques
- Une station simplement retenue conserve une donnée historiquement valide mais **sa fraîcheur n'est pas attestée**. Ne pas la marquer actualisée, ni remplacer un contrôle de fraîcheur métier.
- Le modèle n'est pas raccordé à `journal_runner.mjs` ; pas de comparaison V1/V2 ni parité nationale, pas d'économie de requêtes démontrée.
- Les mises à jour acceptées vérifient actuellement présence du hash et identité mais **ne recalculent pas le hash**, contrairement à la validation complète de `model.mjs` ; **ne pas utiliser comme validateur tarifaire final**.
- Une disparition de l'inventaire peut provenir d'une erreur partielle de tuile et ne doit déclencher aucune suppression canonique automatique.
- Des générations indépendantes nécessiteront un protocole atomique de publication, un contrôle de provenance, une politique d'expiration et des tests adversariaux avant intégration.

## Décision
Expérimentation R&D uniquement. **Aucun passage à V2, aucune fusion**. Maintenir la V1, les workflows, caches, secrets et Production absolument inchangés.
