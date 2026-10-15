# Décision R&D

**Conserver V1 tel quel. Ne pas migrer vers V2 à ce stade.** Le prototype prouve sur 24 stations archivées une reprise plus fine après interruption et un refus sûr des données incomplètes, avec parité brute de 24 stations / 113 EVSE / 150 connecteurs et leurs composants tarifaires. Il ne réduit ni les requêtes ni les octets en fonctionnement normal ; il est ~2,6 fois plus lent dans ce microbench local et effectue 10 écritures contre 1 pour le modèle V1. Une API indisponible ou des statuts incomplets demeurent des incidents distincts.

| Sujet | Bénéfice démontré | Risque / limite |
|---|---|---|
| Checkpoint par lot | 5 requêtes contre 7 après coupure simulée à 2/5 lots, couverture identique | Réécriture trop fréquente du petit état ; stockage national non testé. |
| Validation complète et dernier bon | Réponses partielles, hash faux, pagination/cursor défectueux refusés en fixture | Ne prouve pas la forme de toutes les réponses GraphQL réelles. |
| Lots/quota | Maintien prudent à 5 ; aucune concurrence ni requête API du prototype | Aucun gain normal mesuré ; les essais historiques >5 et concurrence 3 ont échoué/été partiels. |
| Inventaire et mapping | Aucun EVSE/IRVE inventé | 3 057 nouveaux IDs du delta du 15/10 restent non mappés dans V1 comme V2. |

Avant toute décision ultérieure de migration, il faudrait (1) un stockage expérimental segmenté performant sur un échantillon national archivé, (2) une preuve de pagination et complétude sur des réponses représentatives, (3) un benchmark isolé des quatre blocs avec CPU/RAM/octets et quota, (4) des scénarios réseau réels **après autorisation explicite** avec budget maximal de requêtes et absence d'impact sur les collectes canoniques, (5) la validation indépendante de l'overlay et du runtime V9. L'approbation de cette PR Draft ne vaut aucune autorisation pour ces étapes ni pour modifier V1.

Statut : **prototype indépendant et mesures partielles, non prêt au remplacement**. Aucun workflow, secret, cache, pin Production ou PR #219 n'est modifié.
