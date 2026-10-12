# V9 — inventaire différentiel Electra / Electroverse par pays (13 octobre 2026)

Le code Production épinglé compile actuellement les overlays EVSE `data/platforms/electra/france` et `data/platforms/electroverse/france-evse` sous `snapshot-inputs/FR` ; les offres compilées portent `countries: ['FR']`. Le pin de développement `2026-10-13-nine-country-be-candidate` ne contient aucune archive EVSE eMSP équivalente pour les huit autres pays cibles. La Belgique ajoutée par la PR Production #58 concerne le **direct CPO NAP**, pas ces deux eMSP.

| Pays cible | Electra eMSP par EVSE dans le pin | Electroverse eMSP par EVSE dans le pin | Décision |
| --- | --- | --- | --- |
| FR | Oui | Oui | Conserver les deux voies indépendantes et leurs tests. |
| IT, CH, DE, ES, NL, GB, MA, BE | Non | Non | Garder les voies sans montant jusqu'à une collecte officielle et un appariement EVSE/prise/puissance validés. |

La [preuve publique d'abonnements Electroverse](../data/emsp/electroverse_subscription_public_evidence_202610.json), fusionnée dans Data Lab #203, porte des pourcentages Powerdot FR/ES/BE/PT et IONITY FR. Elle ne fournit ni tarif eMSP de base par EVSE, ni frais complets, ni statut de prise, ni droit d'appliquer automatiquement le pourcentage à un tarif direct CPO. Le tarif mensuel IONITY est indicatif et doit être confirmé dans l'application. Ces métadonnées sont **non classables** et ne créent aucun montant V9 international.

L'extension requiert, pour chaque pays et service, une preuve de couverture opérateur, une source officielle de prix par EVSE/prise et puissance, les frais et taxes, un rapprochement exact ou univoque, puis simulation et validation dans un snapshot explicitement épinglé. Les stations direct CPO existantes restent visibles ; l'absence d'overlay ne les retire pas.
