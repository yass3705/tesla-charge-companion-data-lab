# Régression fonctionnelle et robustesse

Commandes : `node --test experiments/electroverse-v2/test/model.test.mjs` puis `node experiments/electroverse-v2/benchmark.mjs`. **16/16 tests passent** sur la branche expérimentale. Données exactes dans [regression.json](regression.json). Aucun accès réseau.

| Multiensemble comparé, V1 modèle vs V2 | Ancien | Nouveau | Écart manquant/ajouté |
|---|---:|---:|---:|
| Stations PK | 24 | 24 | 0 / 0 |
| EVSE PK | 113 | 113 | 0 / 0 |
| Connecteurs (PK, type, kW, vitesse, gratuité) | 150 | 150 | 0 / 0 |
| Mappings IRVE/provenance | 24 | 24 | 0 / 0 |
| Charges tarifaires complètes (`priceComponents` + `complexPricingDetail`) | 150 | 150 | 0 / 0 |

Les 24 `tariffHash` V1/V2 sont identiques. Cette comparaison inclut en JSON exact les prix au kWh, temps de charge, stationnement, frais fixes, TVA, devise, restrictions heure/date/semaine/durée et éventuels seuils/plafonds présents dans l'échantillon. Elle ne prouve pas que **chaque type de règle** existe parmi les 150 connecteurs : la fixture archivée ne contient notamment aucune gratuité. Un test **synthétique, identifié comme tel**, vérifie la conservation de `isChargingFree`, `0 €`, TVA, devise et restriction hebdomadaire ; il n'établit aucune parité sur un vrai site gratuit.

Robustesse simulée : 429, 500, 503, timeout persistants conservent le dernier bon et laissent 5 stations du lot à reprendre ; un alias GraphQL partiel est isolé et récupéré par un seul fallback ; station introuvable, pagination incomplète et curseur bloqué ne remplacent pas l'ancien tarif ; checkpoint corrompu ou incohérent avec le dernier bon arrête sans écriture ; interruption après 2 lots reprend à 10/24 et termine à 24/24 ; doublon d'identité et hash non conforme sont refusés ; modification tarifaire avec hash exact est acceptée. Un garde de chemin refuse toute sortie dans le cache canonique.

Limites : aucune pagination API réelle, aucun appel fournisseur, aucune preuve de statut EVSE national, aucun test à 346 MB, aucun contrôle de tarif calculé par le moteur V9. La parité démontrée est la **préservation de l'entrée tarifaire brute** et des identités sur un échantillon archivé, pas une autorisation de publication.
