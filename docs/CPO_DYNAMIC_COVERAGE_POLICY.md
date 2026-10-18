# Couverture dynamique des CPO — règle commune Data Lab / Production

Décision utilisateur du 18 octobre 2026. Cette règle remplace toute garde historique de variation de volume incompatible, sans réécrire les sources ou rapports anciens.

## Acceptation

Pour chaque CPO et chaque pays, le nombre de stations, EVSE, prises et offres peut augmenter ou diminuer sans limite prédéfinie. Les apparitions, disparitions, déplacements et changements de prix sont des observations, jamais des motifs de rejet à eux seuls. Les compteurs du précédent run ou d'un pin historique servent à diagnostiquer, pas à exiger l'égalité. Cette règle vaut pour les collectes, imports, compilateurs, snapshots, contrôles de parité et CI. Aucun seuil de variation de remplacement n'est permis.

La validation porte sur la collecte complète (API, pagination et total déclaré), le schéma, le pays et le CPO réels, la visibilité publique, les identifiants source exacts, les relations station/EVSE/prise, les tarifs référencés, la devise, les unités, les composantes, la date et le SHA source. Un total annoncé par l'API doit correspondre aux pages reçues : c'est une preuve de complétude du *run présent*, pas une cible historique. La comparaison des SHA avec un pin immuable est une vérification d'identité de ce pin, pas une règle sur le réseau courant.

Ne jamais inventer un identifiant EVSE physique absent de la source, ni transférer un prix par proximité ou identité de site. Une prise identifiée sans tarif reste visible avec « Prix non disponible ». Une offre identifiée mais non calculable garde « Tarif incalculable ». Un prix zéro est admis uniquement lorsqu'il est explicite et prouvé. Une source tarifaire absente ne vaut pas zéro et une offre différente ne sert pas de substitution.

## Incident et dernier état valide

Zéro station soudain pour un CPO auparavant non vide, sans preuve officielle de fermeture, fichier tronqué, erreur API, pagination incomplète, structure inutilisable, identités insuffisantes ou perte prouvée par une erreur de collecte : le nouveau lot de ce CPO est invalide. Ne pas le promouvoir. Conserver le dernier snapshot **validé de ce CPO**, son SHA, sa date de collecte et un indicateur explicite de fraîcheur ; ne jamais annoncer ses anciens prix comme fraîchement collectés. Les autres CPO valides poursuivent leur traitement. Une fermeture réelle demande une preuve explicite et une décision de retrait, pas un seuil de volume.

Une anomalie locale est mise en quarantaine au niveau le plus fin possible : tarif orphelin, prise sans identité ou station non publique ne doit pas effacer les stations valides. Le rapport de validation contient le motif, les identifiants concernés, les compteurs avant/après à titre indicatif, les SHA et dates source, et le statut de promotion de chaque CPO. Une erreur globale de transport ou de schéma peut invalider tout le lot du CPO. Aucun fallback vers un autre CPO ou un autre canal tarifaire.

## CI : exemples et contre-exemples

| Situation | Décision |
| --- | --- |
| IONITY UK 83/872/872 → 84/878/878, source complète et cohérente | Accepter. |
| Réseau de 1 000 → 100 stations, pagination et identités vérifiées | Accepter et signaler la variation. |
| Ajout/retrait de prises ou de références tarifaires cohérentes | Accepter ; les prises sans prix restent sans prix. |
| Prix explicite de 0 GBP/kWh | Conserver le zéro et sa preuve. |
| Zéro station inattendu, page manquante, doublon contradictoire ou tarif orphelin | Refuser le lot ou isoler l'anomalie ; garder le dernier état valide daté. |
| Prix absent traité comme 0, EVSE inventé, transfert par site, seuil de baisse de 5 % ou 30 % | Interdit. |

Les tests CI doivent couvrir ces cas, l'isolation entre CPO et la préservation du dernier état valide. Le pin tarifaire du 15 octobre 2026 garde ses octets et SHA ; la politique concerne les nouveaux lots dynamiques.

## Inventaire ciblé des contrôles existants

| Classe | Exemples examinés | Traitement |
| --- | --- | --- |
| A — volume seul | Triplets UK, baisses CH/Zephyre/Ze-Watt/REVE, minimums France IRVE, BUMP, Gridserve, Fastned, Allego, IONITY, Electra, Atlante, EVSE/offres Electroverse | Retirer le pouvoir bloquant dans les branches correctives ; garder les compteurs en observation. |
| B — qualité du run courant | Pages reçues contre total annoncé, fichier lisible, identité pays/CPO, unicité, SHA du pin, référence tarifaire existante, somme des catégories du même lot | Conserver. Un `0` inattendu reste incident, sans seuil de baisse. |
| C — mixte | Taux de réponse ou de rapprochement, proportion de prix visibles, nombre de stations à tarification « rankable » | Réduire au diagnostic par station/prise ; n'utiliser comme gate globale que si la perte résulte d'une erreur de collecte démontrée. |
| D — historique/non promotion | Rapports de recherche, sondes régionales, règles du pin figé et contrôles de présentation sans promotion de CPO | Préserver avec annotation de cette décision ; ne pas les réactiver comme seuils pour un nouveau lot. |

Le contrôle de couverture d'une cohorte tarifaire exhaustive est distinct : il interdit *la promotion de la cohorte non prouvée*, sans supprimer les stations ni bloquer la collecte du CPO. Les conclusions des phases tarifaires #133 sur le pin du 15/10 ne sont pas extrapolées aux réseaux courants.
