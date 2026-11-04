# Electroverse V2 — intégration expérimentale générations + journal (15/10/2026)

## Livrables
- `experiments/electroverse-v2/generation_journal_runner.mjs` : compose le planificateur des générations, la validation des enregistrements et le journal par lot sur un sous-ensemble sélectionné.
- `experiments/electroverse-v2/generation_journal_runner.test.mjs` : cinq tests à lancer sur la fixture archivée de 24 stations.

## Règles du modèle
1. Valider les enregistrements précédents (identité et empreinte tarifaire).
2. Refuser une génération lorsque l'appelant signale un inventaire incomplet.
3. Actualiser seulement les stations sélectionnées et les nouvelles stations absentes de l'historique ; regrouper ces demandes en lots de 5 maximum dans un journal séparé.
4. Réconcilier les résultats sans perdre le tarif ancien des stations non sélectionnées. Leur provenance indique explicitement `previous_verified_not_refreshed` : **elles n'ont pas été revérifiées**.
5. Refuser une réconciliation incomplète et les corruptions détectées.
6. Le journal reste soumis à sa vérification de génération, fondée sur la sélection en cours et ses empreintes ; un vrai usage incrémental entre changements de tarifs doit encore distinguer le worklist stable du résultat observé.

## Tests prévus, non encore exécutés
- Parité du corpus après refresh d'un sous-ensemble de 3 stations.
- Évolution d'un prix sélectionné sans modifier les stations non sélectionnées.
- Rejet de l'inventaire explicitement incomplet.
- Rejet d'un ancien enregistrement au hash corrompu.
- Interruption après 2 lots sur 12 stations sélectionnées, reprise du troisième lot uniquement.

**Important : les cinq tests sont ajoutés mais ne sont pas validés par une exécution dans ce tour.** Sur le checkout :
`node --test experiments/electroverse-v2/generation_journal_runner.test.mjs`

## Limites
- Le booléen `inventoryComplete` est une assertion du simulateur ; il ne prouve pas qu'une collecte réelle de toutes les tuiles est complète. Il faudra vérifier les manifestes, couverture et anomalies avant de traiter les disparitions.
- Le journal ne reprend pas encore une génération quand son jeu de travail lui-même change.
- Aucun état fusionné n'est publié ; le simulateur renvoie des objets en mémoire. Aucune nouvelle mesure de vitesse, quota, coût GitHub, parité nationale ou tarif calculé.
- Aucun collecteur, workflow, cache, secret ou pin Production n'a été modifié. PR #331 reste Draft, non fusionnée.

## Suites prioritaires
Exécuter les tests complets du checkout et le benchmark à trois voies, puis introduire un protocole de génération durable, et valider que tous les scénarios de corruption interrompent sans écrire ni afficher un tarif incomplet.
