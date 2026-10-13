# DOT-NL — contrôle des sites tarifés sortants entre deux pins V9

## Références

- Ancien pin Data Lab `047e1911a5dfd4dcce741ad9b461c6096effb9cd` (snapshot Pages public).
- Nouveau pin Data Lab `2cc230af128b316bf980d9e7cd7fc5408301b6a4` (candidat de développement Production).
- Fichiers comparés : `data/national/netherlands_dotnl/runtime/all.json.gz` de chaque pin et `data/national/netherlands_dotnl/normalized.json.gz` du nouveau pin, généré le 13 octobre 2026 à 10:42:49 UTC.
- [Audit reproductible](../scripts/audit_dotnl_pinned_transition.py) et [inventaire machine des 62 sites](../reports/netherlands/dotnl-pinned-transition-2026-10-13.json).

## Résultat

| Mesure | Ancien | Nouveau |
| --- | ---: | ---: |
| Sites runtime | 73 557 | 78 529 |
| Configurations | 83 648 | 89 094 |
| Configurations avec prix | 81 531 | 87 984 |

Les pins conservent 72 557 IDs de site à l'identique ; 1 000 IDs sortent et 5 972 entrent. Parmi les sortants, **70 sites portaient 84 configurations tarifées**. Huit disposent d'un unique candidat de remplacement avec même nom, opérateur et coordonnées arrondies à cinq décimales ; ces huit candidats ont **leurs propres prix dans le nouveau flux**. Cette comparaison n'établit pas une identité canonique et ne migre aucun ancien tarif.

Les **62 autres sites anciennement tarifés** sont absents du runtime nouveau **et absents sous leur ancien ID dans la source normalisée actuelle** (0/62). Leur dernier statut dans l'ancien flux était `IN_SERVICE` pour 51 et `UNKNOWN` pour 11. L'absence du nouveau flux n'établit pas leur fermeture physique. Aucun prix ancien ne doit être transféré par ressemblance de nom ou distance GPS ; la règle DOT-NL canonique et la séparation Direct/eMSP restent intactes.

## Suite sûre

Demander au flux national ou aux CPO la correspondance d'ID / l'état de service des 62 sites, en priorité les 51 anciennement `IN_SERVICE`. La réintégration exige un EVSE/connecteur exact, une station publique et un tarif actuel relié à ce connecteur. Le rapport donne les IDs, opérateurs, coordonnées et statuts pour le suivi. Le candidat de développement reste distinct du snapshot Pages public ; cet audit ne change aucun prix ni pin.
