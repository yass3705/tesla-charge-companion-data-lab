# UK validated open feeds — différentiel avant promotion, 13 octobre 2026

Le candidat Production `2026-10-13-fr-spie-neuilly-timewindow-candidate` épingle Data Lab `e39a4466096b520b3c459e75539bf9b112235165`. Le workflow Data Lab [38400775080](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/38400775080) a collecté avec succès le 13 octobre et publié `data/national/uk_validated_open_feeds.json.gz` au commit `49bd7ced1`. Le succès du workflow prouve la collecte, pas la complétude des tarifs ni leur présence dans le runtime épinglé.

| Mesure | Pin du candidat (7 octobre) | Collecte du 13 octobre |
| --- | ---: | ---: |
| Sources demandées / obtenues | 12 / 12 | 12 / 12 |
| Sites | 11 171 | 11 205 (+34) |
| EVSE | 22 538 | 22 588 (+50) |
| Connecteurs | 22 568 | 22 618 (+50) |
| Sources complètes / partielles | 11 / 1 | 10 / 2 |

`char.gy` reste partiel : les mêmes cinq IDs tarifaires manquent, désormais référencés par **1 128 EVSE** contre 1 092 dans le pin. ChargePlace Scotland devient partiel : deux IDs tarifaires référencés par **116 EVSE distincts** manquent dans la réponse actuelle (84 `AVAILABLE`, 11 `CHARGING`, 18 `UNKNOWN`, 3 `INOPERATIVE`). Ces deux objets tarifaires figuraient dans la source épinglée, avec `last_updated` du 25 novembre 2024, mais leur présence historique ne prouve pas qu'ils sont encore valables. Les identifiants et les usages exacts sont dans `reports/uk/validated-open-feeds-latest.json` ; aucun tarif historique n'est transféré par cet audit.

La source courante apporte des sites et des EVSE, mais une promotion brute ferait disparaître des preuves tarifaires actives. La décision est donc **pas de repin UK** sans réponse fournisseur pour les sept IDs manquants et comparaison connecteur par connecteur. Les connecteurs dont le `tariff_id` est sans objet courant doivent rester « Prix non disponible » ou « Tarif incalculable » selon l'association déjà vérifiée ; ils ne doivent pas recevoir le prix d'un autre groupe. Le snapshot Production et Pages restent inchangés.
