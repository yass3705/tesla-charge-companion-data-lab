# TCC — audit approfondi du calcul tarifaire (lot 9 pays)

Statut : validation GitHub en cours. **Lecture seule pour le moteur et la publication V9.** Le fichier `reports/tariff-scenarios/review-latest.json` est l'état daté validé du workflow mondial; `deep-review/` contient les diagnostics approfondis du workflow prioritaire.

## Résultats du pilote précédent et correctifs d'analyse

- 1 306 fichiers de sources Data Lab + 1 178 stations Tesla (9 pays) recensés par le run #37995141492.
- 84 offres de l'échantillon France comportent des frais après un délai que le V9 épinglé ignore; elles ont été testées avec sept durées : 168 simulations de correction provisoirement calculables et 420 incomplètes. Ces **420 représentent des profils de simulation**, pas 420 bornes distinctes.
- Parmi ces 420, 413 étaient classées « sélection règle à vérifier » pour 78 offres Electra eMSP, 7 « plafond nocturne à vérifier » pour une offre SIGEIF. Le moteur expérimental est maintenant capable de parcourir les créneaux de facturation et distingue les règles inapplicables des ambigüités réelles. La source Electroverse reste distincte de la source Electra.
- **SIGEIF** : le guide officiel d'octobre 2025 confirme un plafond **de 4 € uniquement sur les frais de stationnement nocturnes entre 20 h et 8 h** pour les bornes douces jusqu'à 22 kW, avec surcharge de 0,05 €/minute après 3 h, soit un plafond de la portion nocturne, pas de tous les frais de séjour. Vérification par simulation de jour, de nuit et de charge chevauchante. Référence : https://www.sigeif.fr/sites/default/files/2025-10/GUIDE%20D%27UTILISATION%20IRVE%202025%20OCTOBRE_0.pdf
- **Plug Inn / Charge Pass** : Renault confirme des frais de stationnement supplémentaires au-delà d'1 h à 0,30 €/min sur Plug Inn fast charge. Les tarifs eMSP et leur contrat restent indépendants du tarif direct CPO. Référence : https://www.renault.fr/solutions-de-recharge/charge-pass.html
- **Tesla** : l'ancien échantillon isolait une règle horaire à chaque test. Les 16 « no_matching_time_rule » ne démontrent **pas** de lacune tarifaire réelle : il faut simuler les configurations complètes et leurs créneaux. Le nouveau diagnostic vérifie la couverture 24h complète par pays.
- Devise Tesla : ne jamais convertir implicitement CHF, GBP ou MAD en EUR. Ne jamais comparer le champ numérique `totalEur` d'un moteur qui calcule en devise native à un montant EUR sans contrat FX vérifié.
- Maroc Tesla : des tranches à la minute dépendantes de la **puissance réellement délivrée** et pas de la puissance nominale de la borne. Sans courbe temporelle de puissance, afficher **« calcul incomplet »**. La simulation V9 ancienne pouvait facturer deux fois une minute de charge parce que `chargePerMinute` et `pricePerMinute` étaient activés simultanément.
- Fraîcheur Mac/SuC : utiliser les **dates d'observation de la source**, pas l'heure d'un run. Mac de moins de 10 jours prime; sinon SuC prime uniquement si plus récent, comparable et réconcilié sur un ID non ambigu; sinon Mac. **MA prime toujours depuis Mac**, y compris si SuC répertorie six stations marocaines. Les frais annexes non fournis par SuC ne doivent pas être supprimés.

## Sorties persistantes prévues dans `reports/tariff-scenarios/`

- `france-after-minutes-candidate-latest.json` : un résultat par tarif et par durée, avec composants, échecs et tests.
- `tesla-global-inventory-latest.json` : source mondiale, empreinte SHA, devises et familles par pays, dates et continuité des créneaux.
- `tesla-global-complete-config-fixtures.json` : ensembles complets de règles représentatifs, pas des créneaux isolés.
- `tesla-complete-config-pricing-audit-latest.json` : validation des fenêtres Tesla, correction expérimentale devise native, facturation à la minute, puissance dynamique, comparaison avec moteur actuel.
- `tesla-source-selection-audit-latest.json` et `tesla-source-selection-station-detail-latest.json` : **une ligne par station Mac**, décision de fraîcheur, méthode de correspondance, cause si tarif SuC inéligible, règles d'exclusion MA.
- `deep-review/` : copie indépendante de l'ensemble des diagnostics après exécution du workflow prioritaire.
- `review-latest.json`, `history.jsonl` et `snapshots/` : bilan global et historique des runs validés.

## Critères de publication V9

Une correction ne peut être publiée que si la source est prouvée, la granularité (borne/EVSE) préservée, les variantes temporelles et abonnements séparés, la devise conservée et les paramètres nécessaires connus. Les `computed` expérimentaux restent **non validés pour publication**, en particulier Electra eMSP multi-créneaux. Tout statut manquant/ambigu reste signalé, sans montant inventé.

**Ces audits sont des tests de compatibilité du moteur sur les sources disponibles, pas une preuve que tous les tarifs CPO nationaux sont déjà connus ou que tous les prix observés sont actuels.**


## Résultats des calculs approfondis (run #37997213907, tests réussis, archivage relancé)

Les étapes de calcul et de contrôle sont passées ; la persistance GitHub a rencontré un problème de rebase des fichiers de travail et est relancée via le workflow prioritaire.

| Domaine | Résultat vérifié |
|---|---|
| Tarifs France après durée | **84 offres × 7 profils = 588 calculs expérimentaux**, 588 calculés, 0 incomplet, 0 régression |
| Plafond SIGEIF | Tests jour (6 €), nuit (4 €), jour/nuit (13 €) validés selon la limite de 4 € sur frais nocturnes |
| Tesla configurations complètes | 151 configurations représentatives × 4 horaires = 604 profils, **600 calculés**, 4 incomplets UK faute de règles tarifaires source |
| Tesla devises | 68 écarts de devise en Suisse, 96 UK, 20 Maroc dans les profils d'essai de l'ancien adaptateur |
| Tesla calcul à la minute | Un test montre 40 au lieu de 20 avec l'ancien adaptateur ; le calcul expérimental facture 20 une seule fois |
| Tesla Maroc | Cas de courbe : 10 min à 50 kW + 10 min à 120 kW = **25 MAD** en tarification dynamique expérimentale ; sans courbe, calcul incomplet |
| Tesla Mac / SuC, 9 pays | 1 167 stations Mac inspectées ; 1 147 désignent SuC plus récent **comme candidat tarif de charge**, 20 conservent Mac |
| Différences entre relevés | **451 écarts tarifaires** à réconcilier : FR 129, DE 315, IT 2, CH 1, NL 1, UK 3 |
| Références SuC non réconciliées | 11 entrées (FR 2, DE 3, IT 4, UK 2) ; aucune publication par inférence |
| Maroc | **6/6 Mac exclusivement** malgré 6 entrées MA dans le snapshot comparatif SuC |

**Attention aux conclusions :** le niveau « calculé » ici atteste du comportement sur les profils testés, pas d'une source fraîche, d'une correspondance EVSE prouvée ni de la validation des conditions commerciales eMSP. Les quatre anomalies UK sont des configurations sans règles tarifaires dans la source et non un défaut de couverture horaire démontré. **V9 production reste inchangée.**


## Résolution de l'unique défaut Tesla UK du banc d'essai

Les quatre simulations incomplètes ne concernent **qu'une station**, `tesla-dartford-uk-tesla-service-centre`. Sa configuration `main` est dépourvue de règles tarifaires dans le catalogue Mac. Le site officiel Tesla indique pourtant que **Dartford UK – Tesla Service Centre** est un Supercharger **ouvert au public et accessible 24 h/24** : https://www.tesla.com/findus/location/supercharger/30168. Sa dénomination « Service Centre » ne justifie donc **pas** l'exclusion comme concession privée. Statut TCC correct tant qu'aucune source tarifaire comparée n'est validée : **station conservée, tarif indisponible**.
