# Tesla Charge Companion Data Lab

Ce dépôt sert de laboratoire de données pour Tesla Charge Companion. Il contient les scripts, configurations, rapports et tests utilisés pour explorer, collecter, normaliser et valider les données des opérateurs de recharge avant publication vers l'application stable.

## Objectifs

- isoler les expérimentations de collecte du dépôt stable ;
- conserver des collecteurs reproductibles ;
- documenter les sources et hypothèses ;
- générer des jeux de données contrôlables avant publication ;
- ajouter des tests de non-régression sur les opérateurs et tarifs.

## Structure

- `.github/` : workflows GitHub Actions du laboratoire ;
- `config/` : paramètres et règles de collecte ;
- `data/` : données intermédiaires ou générées ;
- `izivia/` : travaux dédiés au réseau IZIVIA ;
- `reports/` : résultats de validation et rapports ;
- `scripts/` : collecteurs et outils de normalisation ;
- `tests/` : tests automatiques.

## Principes de validation

Les données tarifaires ne doivent pas être publiées comme tarif opérateur direct lorsqu'elles proviennent uniquement d'un eMSP ou d'un acteur de roaming. Les sources officielles ou techniques directement rattachées au CPO sont privilégiées. Lorsqu'une valeur ne peut pas être vérifiée de façon suffisante, elle reste explicitement inconnue plutôt que d'être extrapolée.

Les jeux nationaux doivent conserver, lorsque la source le permet, l'identifiant de station, l'identifiant EVSE, l'opérateur, la puissance, les connecteurs et les métadonnées de provenance nécessaires à une fusion déterministe dans Tesla Charge Companion.

## AVIA / Picoty

Le collecteur national AVIA/Picoty filtre le CPO Picoty via l'identifiant `FR*PY2`. `AVIA VOLT` est conservé comme marque commerciale, mais les tarifs sont séparés en trois catégories : paiement direct CPO, offre AVIA Carte/Deft Power, et roaming tiers. Un tarif national ne doit jamais être déduit d'une source secondaire ou d'un prix eMSP.
