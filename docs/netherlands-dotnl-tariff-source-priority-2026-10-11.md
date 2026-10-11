# TCC V9 — Politique NL : priorité de la base nationale DOT-NL
Date : 11 octobre 2026. Décision utilisateur.

## Règle de référence

**DOT-NL est la source tarifaire canonique aux Pays-Bas.** Utiliser par défaut le tarif fourni et associé à l'EVSE/connecteur exact, sans le recontrôler individuellement dans le QR du CPO ni dans une application.

Un objet de tarif **AD_HOC_PAYMENT**, **REGULAR** ou **sans type** émis par le CPO propriétaire de la station est recevable tant que son prix est cohérent, calculable et non explicitement signalé comme eMSP/itinérance/contrat tiers. En présence d'une alternative dans le même flux, préférer AD_HOC_PAYMENT ; en cas de contradictions réellement insolubles entre tarifs de même priorité, déclarer « tarif incalculable ».

Déclencher des recherches complémentaires auprès du CPO **uniquement si** :
1. aucun tarif DOT-NL n'est renseigné ou relié à ce connecteur → « prix non disponible » tant qu'aucune solution n'est validée ;
2. des tarifs concurrents contradictoires ou une règle de calcul non prise en charge empêchent un résultat fiable → « tarif incalculable » tant que non résolu.

Le besoin éventuel d'un moyen de paiement QR ne justifie **pas** une deuxième vérification systématique des tarifs nationaux existants. Écarter explicitement les offres eMSP/roaming/abonnement tiers ; Electroverse et Electra sont des overlays séparés, jamais des substitutions au tarif CPO national.

## Application opérationnelle (snapshot DOT-NL du 10/10/2026)

| CPO | Connecteurs tarifés par la base nationale | Sans tarif national exploitable |
| --- | ---: | ---: |
| Laadnet (LNT) | 5 356 | 504 |
| StellaPower (SPA) | 328 | 0 |
| Agri Go Charge (AGO) | 0 | 2 578 |
| WattHub (WAT) | 0 | 124 |

- **StellaPower : dossier résolu côté récupération de prix national** ; garder les deux références OCPI nationales sans les remplacer par l'ancien barème 0,57 €/kWh obtenu hors DOT-NL. Les règles de durée doivent rester calculables, sinon l'anomalie précise est à traiter.
- **Laadnet :** conserver les 5 356 tarifs nationaux et investiguer uniquement les 504 connecteurs sans tarif.
- **Agri Go Charge :** 2 578 sans tarif ; dossier mis en attente selon la décision utilisateur du jour.
- **WattHub :** 124 sans tarif ; prix dynamiques, dossier distinct.
- Les audits publiés avant cette décision qui marquent les REGULAR comme « à vérifier obligatoirement via QR » sont **supplantés par ce document**.

## Modification effective

- Workflow .github/workflows/netherlands-dotnl-canonical.yml : retrait de l'override automatique StellaPower ; le pipeline national fait foi.
- Script scripts/integrate_stellapower_nl_official.py : devenu fallback facultatif **uniquement pour les connecteurs sans aucune référence nationale** ; ne remplace jamais un tarif présent.
- Le compilateur scripts/dotnl_netherlands_runtime.py accepte déjà AD_HOC_PAYMENT / REGULAR / type absent avec préférence AD_HOC_PAYMENT et rejette les conflits tarifaires de même priorité.

## Sources d'audit

- reports/netherlands/nl-cpo-unpriced-evse-inventory-2026-10-11.json
- reports/netherlands/nl-direct-price-provenance-2026-10-11.json

Les tarifs historiques des snapshots nationaux demeurent traçables. Aucune approximation ni prix eMSP ne sont injectés dans Direct.
