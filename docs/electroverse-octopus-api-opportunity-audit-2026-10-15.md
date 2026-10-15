# TCC V9 — Audit ciblé des API Octopus pour Electroverse (15/10/2026)

## Verdict provisoire (documentaire, sans requête authentifiée)

**Aucun endpoint public officiel de catalogue des stations, EVSE et prix Electroverse n'a été confirmé dans la documentation Octopus examinée.** Ne pas remplacer le collecteur existant. L'API REST Octopus documentée concerne notamment les produits/tarifs d'électricité domestique : `GET /v1/products/` ne représente **pas** les prix de recharge Electroverse. GraphQL est une piste de recherche, **pas** une preuve d'accès à un catalogue Electroverse ni d'autorisation pour un client tiers.

Sources : [REST basics](https://docs.octopus.energy/rest/guides/api-basics/), [GraphQL documentation](https://docs.octopus.energy/graphql/), [GraphQL queries](https://docs.octopus.energy/graphql/reference/queries/), [annonces API](https://docs.octopus.energy/announcements/).

## Baseline vérifiée dans Data Lab

- `.github/workflows/electroverse-france-daily-delta.yml` : déclenchement quotidien à 22:47 UTC, sélection ciblée (`scripts/electroverse_daily_delta_selector.mjs`), puis `scripts/electroverse_hybrid_refresh.mjs`. Configuration actuelle : inventaire zoom 9, concurrence tuiles 8, batch 5, concurrence tarifaire 2, pause de vague et fallback 750 ms. Écriture dans cache tarifaire et rapports incrémentaux ; les échecs partiels restent candidats au prochain passage.
- `.github/workflows/electroverse-france-full-refresh.yml` : dimanche 00:17 UTC, quatre chunks **séquentiels** de 6 000 positions (0, 6 000, 12 000, 18 000), timeout maximal 300 min **par job** ; un échec du script ne fait pas systématiquement échouer le job, donc la couleur verte du workflow ne prouve pas l'absence de trous.
- [Audit de migration](updater-test-data-lab-workflow-migration-audit-2026-10-13.md) : trois runs delta et deux runs full réussis antérieurement ; Data Lab propriétaire de l'acquisition, Production consommateur de l'overlay.
- [PR #219](https://github.com/yass3705/tesla-charge-companion-data-lab/pull/219) : le filtre des connecteurs et l'overlay sont soumis à la complétude du manifeste de statuts EVSE ; audit API **indépendant** de ce blocage.

## Comparaison des capacités (constats vs inconnues)

| Critère | Collecteur actuel | REST/GraphQL Octopus officiel |
| --- | --- | --- |
| Inventaire bornes | Balayage par tuiles déjà développé | Endpoint Electroverse non identifié dans les docs examinées |
| Identité EVSE/connecteur/puissance | Cache et rapprochements Data Lab | Schéma public correspondant non identifié |
| Tarif exact détaillé | Hybrid refresh et cache existants | Aucun champ de prix Electroverse par EVSE confirmé |
| Pagination/limites | Concurrence et chunks contrôlés | REST documente la pagination `next` **pour les endpoints correspondants**, pas Electroverse |
| Incrémental / `updated_at` | Delta par sélection propre au projet | Inconnu pour Electroverse |
| Couverture pays | FR aujourd'hui, extension eMSP cadrée | Aucune couverture pays Electroverse documentée dans cette API |
| Authentification | Secret existant géré par Actions | La clé Octopus Energy REST/GraphQL ne doit pas être supposée compatible avec Electroverse |

## Gains et mesures

Aucun pourcentage de gain, volume API ou réduction de coût n'est **mesurable sérieusement** sur la seule documentation. Avant/après exige pour le même lot EVSE : nombre sélectionné, demandes tarifaires, réussites/429/403/5xx, temps de traitement, taux d'offres calculables, égalité des identifiants et décompositions tarifaires. Les 4 chunks du full refresh sont séquentiels ; toute parallélisation doit d'abord démontrer le respect des quotas, des écritures Git concurrentes et de l'intégrité des checkpoints.

## Prochaine investigation à faible coût (read-only)

1. Examiner **dans les scripts déjà présents** les URL et types de réponses Electroverse sans afficher ni journaliser la valeur du secret.
2. Rechercher une **documentation officielle explicitement Electroverse** (OpenAPI, partenaire, licence, quotas et conditions d'accès) avant toute requête de test ; distinguer soigneusement noms d'enum GraphQL liés à Electroverse d'une véritable query catalogue.
3. Si et seulement si une API autorisée est identifiée, produire un pilote limité de 20–50 EVSE publics de puissance et CPO variés, sans écrire les sorties dans Production ni modifier les caches canoniques.
4. Mesurer les composants des offres (énergie, session, temps, stationnement, règles après seuil, TVA, devise, validité) par EVSE/connecteur et la conformité aux règles [multicountry eMSP](tcc-v9-multicountry-emsp-overlays-scope-2026-10-11.md).
5. Si aucune API n'est disponible, optimiser le collecteur actuel : instrumentation des retours partiels, distinction « job réussi » / « couverture complète », contrôle des sélections inchangées, déduplication sûre des requêtes, reprise au checkpoint et statistiques d'erreurs par chunk.

## Garde-fous

Zéro mutation de Production, Stable, Updater Test, Tesla/Mac, des prix existants, des snapshots et des workflows. Ne pas accéder par contournement à une API privée ni publier clés, cookies ou dumps d'authentification. Maintenir les tarifs directs CPO distincts des offres Electroverse eMSP ; conserver les limites de connecteurs EF/Type 2/CCS et le gate #219. Pour l'extension internationale, respecter l'exclusion du Maroc tant que l'application n'y est pas compatible.

**Recommandation : conserver le collecteur actuel ; ouvrir un test API uniquement sur preuve d'un endpoint et des droits d'accès Electroverse.** Cet audit documentaire ne constitue pas un benchmark ni une validation du trafic réel.
