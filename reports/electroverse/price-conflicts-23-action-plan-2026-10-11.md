# Electroverse France — contrôle des 23 conflits de prix encore actifs (11/10/2026)

## Périmètre et précautions

- Évidence : [filtre de statut des 28 sites du 10 octobre](../status-filter-2026-10-10.json) et [détails des offres source](./full-reconciliation/priority-review-evidence.json).
- **23 EVSE en conflit sur 9 stations** ; les deux PK Electroverse retenus par EVSE étaient éligibles (AVAILABLE/CHARGING) à la date du contrôle du 10 octobre. Il ne s'agit **pas** d'une synthèse nationale ni d'un prix actualisé en temps réel.
- Les données tarifaires du cache datent du 28 septembre pour Chargezy et du 4 octobre pour Métropolis. Les tarifs actuels sont donc à reconfirmer dans l'application Electroverse.
- Sources officielles : [Métropolis tarifs](https://www.metropolis-recharge.fr/) et [FAQ post-charge](https://www.metropolis-recharge.fr/faq/), [Chargezy / TE63 tarifs](https://www.te63.fr/nos-metiers/mobilite-electrique/), [Stations-e tarifs](https://stations-e.com/fr). **Attention : prix CPO ≠ prix Electroverse en itinérance**.
- Arbitrage du moteur : **TARIF_AMBIGU / Tarif incalculable** tant qu'aucune preuve eMSP spécifique à la bonne source EVSE ne départage les deux variantes.

## Vue des 9 stations

| Réseau | Station | EVSE conflictuels | Station ID |
|---|---|---:|---|
| Métropolis | Metropolis - Citadine - Villetaneuse - Division Leclerc | 4 | `FRMGPP93079B` |
| Métropolis | Metropolis - Citadine - Bry-sur-Marne - Pasteur | 4 | `FRMGPP94015A` |
| Métropolis | Metropolis - Citadine - Bry-sur-Marne - Charles de Gaulle | 4 | `FRMGPP94015B` |
| Métropolis | Metropolis - Express - Charenton-le-Pont - Général de Gaulle | 1 | `FRMGPP94018A` |
| Chargezy | CHARGEZY - Puy Guillaume - Jaures | 2 | `FRS63P63291A` |
| Chargezy | CHARGEZY - Saint Antheme - Ambert | 2 | `FRS63P63319A` |
| Chargezy | CHARGEZY - Saint Genes Champanelle - Cassin | 2 | `FRS63P63345B` |
| Chargezy | CHARGEZY - Villeneuve - Mairie | 2 | `FRS63P63458B` |
| Stations-e | Espace Nautique Canada - BEAUVAIS | 2 | `FRSE1PSE60BVNA` |

## Détails par EVSE (deux sources valides mais incompatibles)

| Station | EVSE ID normalisé | Source PK A / puissance / offre | Source PK B / puissance / offre |
|---|---|---|---|
| Metropolis - Citadine - Villetaneuse - Division Leclerc | `FRMGPE93079BB1P1` | PK `708484` — 22 kW : 0.53 €/kWh + 0.08 €/min | PK `3569104` — 22 kW : 0.53 €/kWh ; frais de 0.10 €/min après 10 min |
| Metropolis - Citadine - Villetaneuse - Division Leclerc | `FRMGPE93079BB1P2` | PK `708487` — 22 kW : 0.53 €/kWh + 0.08 €/min | PK `3569111` — 22 kW : 0.53 €/kWh ; frais de 0.10 €/min après 10 min |
| Metropolis - Citadine - Villetaneuse - Division Leclerc | `FRMGPE93079BB1P3` | PK `708489` — 22 kW : 0.53 €/kWh + 0.08 €/min | PK `3569117` — 22 kW : 0.53 €/kWh ; frais de 0.10 €/min après 10 min |
| Metropolis - Citadine - Villetaneuse - Division Leclerc | `FRMGPE93079BB1P4` | PK `708491` — 22 kW : 0.53 €/kWh + 0.08 €/min | PK `3569123` — 22 kW : 0.53 €/kWh ; frais de 0.10 €/min après 10 min |
| Metropolis - Citadine - Bry-sur-Marne - Pasteur | `FRMGPE94015AB1P1` | PK `951893` — 22 kW : 0.53 €/kWh + 0.08 €/min | PK `3568499` — 22 kW : 0.53 €/kWh ; frais de 0.10 €/min après 10 min |
| Metropolis - Citadine - Bry-sur-Marne - Pasteur | `FRMGPE94015AB1P2` | PK `951894` — 22 kW : 0.53 €/kWh + 0.08 €/min | PK `3568504` — 22 kW : 0.53 €/kWh ; frais de 0.10 €/min après 10 min |
| Metropolis - Citadine - Bry-sur-Marne - Pasteur | `FRMGPE94015AB1P3` | PK `951895` — 22 kW : 0.53 €/kWh + 0.08 €/min | PK `3568510` — 22 kW : 0.53 €/kWh ; frais de 0.10 €/min après 10 min |
| Metropolis - Citadine - Bry-sur-Marne - Pasteur | `FRMGPE94015AB1P4` | PK `951896` — 22 kW : 0.53 €/kWh + 0.08 €/min | PK `3568514` — 22 kW : 0.53 €/kWh ; frais de 0.10 €/min après 10 min |
| Metropolis - Citadine - Bry-sur-Marne - Charles de Gaulle | `FRMGPE94015BB1P1` | PK `951876` — 22 kW : 0.53 €/kWh + 0.08 €/min | PK `3569094` — 22 kW : 0.53 €/kWh ; frais de 0.10 €/min après 10 min |
| Metropolis - Citadine - Bry-sur-Marne - Charles de Gaulle | `FRMGPE94015BB1P2` | PK `951877` — 22 kW : 0.53 €/kWh + 0.08 €/min | PK `3569100` — 22 kW : 0.53 €/kWh ; frais de 0.10 €/min après 10 min |
| Metropolis - Citadine - Bry-sur-Marne - Charles de Gaulle | `FRMGPE94015BB1P3` | PK `951879` — 22 kW : 0.53 €/kWh + 0.08 €/min | PK `3569106` — 22 kW : 0.53 €/kWh ; frais de 0.10 €/min après 10 min |
| Metropolis - Citadine - Bry-sur-Marne - Charles de Gaulle | `FRMGPE94015BB1P4` | PK `951880` — 22 kW : 0.53 €/kWh + 0.08 €/min | PK `3569114` — 22 kW : 0.53 €/kWh ; frais de 0.10 €/min après 10 min |
| Metropolis - Express - Charenton-le-Pont - Général de Gaulle | `FRMGPE94018AB1P5` | PK `2119297` — 22 kW : 0.53 €/kWh + 0.08 €/min | PK `3579227` — 22 kW : 0.53 €/kWh ; frais de 0.10 €/min après 10 min |
| CHARGEZY - Puy Guillaume - Jaures | `FRS63E63291AB1DCCS` | PK `824547` — 25 kW : 0.59 €/kWh + 2.00 € de connexion | PK `3569293` — 31 kW : 0.69 €/kWh + 2.00 € de connexion |
| CHARGEZY - Puy Guillaume - Jaures | `FRS63E63291AB1DCHADEMO` | PK `824551` — 25 kW : 0.59 €/kWh + 2.00 € de connexion | PK `3569296` — 31 kW : 0.69 €/kWh + 2.00 € de connexion |
| CHARGEZY - Saint Antheme - Ambert | `FRS63E63319AB1DCCS` | PK `824681` — 25 kW : 0.59 €/kWh + 2.00 € de connexion | PK `3579220` — 31 kW : 0.69 €/kWh + 2.00 € de connexion |
| CHARGEZY - Saint Antheme - Ambert | `FRS63E63319AB1DCHADEMO` | PK `824680` — 25 kW : 0.59 €/kWh + 2.00 € de connexion | PK `3579221` — 31 kW : 0.69 €/kWh + 2.00 € de connexion |
| CHARGEZY - Saint Genes Champanelle - Cassin | `FRS63E63345BB1DCCS` | PK `824718` — 25 kW : 0.59 €/kWh + 2.00 € de connexion | PK `3569192` — 31 kW : 0.69 €/kWh + 2.00 € de connexion |
| CHARGEZY - Saint Genes Champanelle - Cassin | `FRS63E63345BB1DCHADEMO` | PK `824733` — 25 kW : 0.59 €/kWh + 2.00 € de connexion | PK `3569197` — 31 kW : 0.69 €/kWh + 2.00 € de connexion |
| CHARGEZY - Villeneuve - Mairie | `FRS63E63458BB1DCCS` | PK `824844` — 25 kW : 0.59 €/kWh + 2.00 € de connexion | PK `3579177` — 31 kW : 0.69 €/kWh + 2.00 € de connexion |
| CHARGEZY - Villeneuve - Mairie | `FRS63E63458BB1DCHADEMO` | PK `824846` — 25 kW : 0.59 €/kWh + 2.00 € de connexion | PK `3579178` — 31 kW : 0.69 €/kWh + 2.00 € de connexion |
| Espace Nautique Canada - BEAUVAIS | `FRSE1ESE60BVNA1` | PK `1457214` — 24 kW : 0.45 €/kWh + 0.10 €/min | PK `4444349` — 24 kW : 0.59 €/kWh ; frais de 0.10 €/min après 15 min |
| Espace Nautique Canada - BEAUVAIS | `FRSE1ESE60BVNA2` | PK `1457215` — 22 kW : 0.45 €/kWh + 0.10 €/min | PK `4444348` — 22 kW : 0.59 €/kWh ; frais de 0.10 €/min après 15 min |

## Captures demandées à l'utilisateur (3 cas représentatifs)

1. **Métropolis — Bry-sur-Marne, boulevard Pasteur 226** : borne 22 kW `FRMGPE94015AB1P1`. Vérifier dans **Electroverse** le prix 0,53 €/kWh et le tarif du temps (0,08 €/min immédiatement OU 0,10 €/min après 10 min). Photographier aussi tout libellé « post-charge » ou « après l'arrêt de charge ».
2. **Chargezy — Puy-Guillaume, place Jean-Jaurès** : prise CCS `FRS63E63291AB1DCCS`. Vérifier **puissance affichée** 25 kW ou 31 kW, prix 0,59 € ou 0,69 €/kWh, frais de 2 € ; relever le statut de la prise et la possibilité d'une autre puissance à cette même station.
3. **Stations-e — Espace nautique Canada, rue de la Mie-au-Roy à Beauvais** : CCS `FRSE1ESE60BVNA1` et idéalement Type 2 `FRSE1ESE60BVNA2`. Vérifier 0,45 €/kWh + 0,10 €/min ou 0,59 €/kWh avec frais après 15 min.

Demander **capture du tarif détaillé par prise et de son statut**, et la date/heure de consultation si elle n'est pas visible. Une capture d'une seule prise par famille permet de tester la typologie, pas de valider d'office les 23 prises.

## Décision

Aucune offre ne doit être sélectionnée automatiquement sur la seule base du tarif CPO ou du fait que deux sources EVSE partagent un identifiant physique. La résolution exige une preuve Electroverse propre à chaque PK ou une règle vérifiée reproductible.