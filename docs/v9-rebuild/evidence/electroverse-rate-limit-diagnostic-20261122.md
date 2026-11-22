# Electroverse V9 — diagnostic fournisseur du quatrième run (22 novembre 2026)

**Statut : audit d'artefacts terminé en lecture seule, pas de nouvelle collecte.** Repo Data Lab, branche `rebuild/v9-20261020`; pas de changement `main`/Production/site public.

## Identités et provenance

- [Run GitHub Actions 44968499274](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/44968499274), job `137042831416`, code `1c8c6d1b377d266ab2f82b053326aeb5c3604b97`, `completed/failure`, du 22 novembre 00:49 à 01:44 UTC.
- Tests Python (13), Node (4), safety scan, récupération des archives et test de filiation du parent : **PASS**. Collecteur : **FAILURE** (`Incomplete tariff chunk retained; no automatic provider retry`).
- Parent contrôlé : run `44962339493`, artefact `14730224631`, SHA-256 ZIP `92ffb6c827fdfe805518746aa0eba13730a8f26ef6254ef9b69e149de655e5c1`, `13 196` PK vérifiées avant la nouvelle reprise.
- Nouvel artefact partiel : [14734805610](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/44968499274/artifacts/14734805610), `tcc-v9-electroverse-failure`, 13 241 512 octets, ZIP SHA-256 `60bbd578cc6a8193e5dbc6c3105bacc16407c06bd42f431bad2ae803f6099f01` ; `checkpoint-manifest.json` file-set SHA-256 `1aea5283a310f637410db62b9743891122ba33d2126269648dadb9cbfb6231fe`, 137/137 fichiers contrôlés SHA-256, 139 entrées ZIP uniques (137 fichiers + 2 manifests), 128 shards. Expiration annoncée par GitHub : 22 décembre 2026 à 01:44 UTC.
- Artefact diagnostic indépendant : [14734885341](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/44968499274/artifacts/14734885341), `tcc-v9-electroverse-failure-diagnostics`, 700 octets ZIP, SHA-256 `6ef10fdc4fdd1c045156a34b09dec2166ac382ae4222cda80bb1723eb3c999f9`, contenant `failure-diagnostics.json`. Vérifié par extraction indépendante.

## Preuve de cause

Les deux nouveaux échecs de l'extraction sont les PK `4475895` et `4475896`, chacune avec **5/5 réponses HTTP 429** : 2 tentatives `single`, puis 3 tentatives `paged` à la page 1. Toutes les réponses ont **0 octet**, aucun JSON, aucun code d'erreur GraphQL et aucun en-tête `Retry-After` / `RateLimit-*` renseigné. Il s'agit d'une **limitation de requêtes côté fournisseur** pour ces tentatives. Le seuil, la fenêtre de quota et l'éventuelle portée par IP ou clé restent **inconnus**. Les requêtes `batch` ne sont pas encore instrumentées de façon exhaustive : ne pas inférer exactement à quel appel le quota a été franchi.

## Comparaison complète source → checkpoint

- Mapping national et inventaire de France : identiques octet pour octet ; aucune création ni suppression de PK dans les shards.
- Source `FR:electroverse_full`, total inchangé `22 818` : `13 196 → 15 694` vérifiées (**+2 498**), **7 124** restantes (**68,78 %** de progression).
- Curseur `completed=[0,6000]`, `pending.offset=12000` inchangés. `pending.pks` **4 804 → 2 306**, exactement **2 498** PK retirées du pending, **aucune** nouvelle PK ajoutée.
- `checked-at.json` : exactement les mêmes **2 498** PK avancées, horodatages strictement croissants ; aucun autre `checkedAt` changé.
- Comparaison de toutes les entrées dans **128 shards** : 2 498 enregistrements contrôlés, **1 077** `tariffHash` modifiés et **1 421** inchangés ; **aucune** autre entrée altérée (changement de hash ≠ changement prouvé de prix au kWh).
- Les anciennes PK échouées `426269`, `426271`, `426272` sont sorties du pending et font partie des PK nouvellement vérifiées ; les nouvelles PK en échec `4475895`, `4475896` sont conservées dans le pending.
- `manifest.json.status=partial_failure`, `reason=collector_exit_nonzero` ; `checkpoint-manifest.json.completeSnapshotValidated=false`. **Ne pas publier ou servir comme génération complète.**

## Prochaine décision technique proposée (pas encore implémentée)

1. Ajouter un signal fournisseur **429** dès les requêtes `batch` et `fallback` : agrégats de statuts HTTP, journal assaini et horodatages de premier/dernier 429.
2. Instaurer un **circuit breaker** par campagne, avec arrêt rapide et checkpoint durable, au lieu de multiplier les relances de localisations alors que le 429 persiste. Ne jamais déclarer vérifiée une PK sans réponse intègre et ne jamais effacer le `pending` des échecs.
3. Respecter `Retry-After` s'il existe ; sinon exécuter des essais supervisés avec pause progressive, jitter et limite stricte de tentatives/temps, et ralentir la concurrence / le pacing en cas de signaux de saturation. Les valeurs devront être éprouvées sur une fenêtre courte, sans inférer de quota non documenté.
4. Vérifier hors fournisseur que l'artefact `14734805610` se restaure depuis le parent `14730224631` avec exact SHA, manifests, identité, 128 shards et monotonicité ; ne pas relancer depuis `14730224631` en répétant les 2 498 vérifications. Le sélecteur actuel refusera intentionnellement le nouvel échec non encore épinglé.
5. Après validation, faire **une** reprise mesurée à partir de `15 694`, puis auditer les artefacts et la disponibilité de la source ; aucune promotion avant complétude.

**Traçabilité :** rapport produit après la fin du run à partir des métadonnées GitHub, du job log et des deux archives ZIP téléchargées et comparées intégralement. Aucun nouveau run lancé durant l'audit.
