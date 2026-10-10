# Electroverse – preuve manuelle : Bry-sur-Marne Pasteur P1

- Date de revue : 2026-10-10 (date de conversation, l'application ne fournit pas d'horodatage métier des offres).
- Source : deux captures utilisateur de l'application Electroverse, à 12:57 et 12:58 sur le téléphone.
- Station : Métropolis – Citadine – Bry-sur-Marne – Pasteur.
- ID affiché identique sur les deux captures : `FR*MGP*E94015*A*B1*P1`.
- Connecteur : Type 2 ; puissance maximale : 22 kW.

## Capture A (heure affichée 12:57)
- Statut : `Occupé`.
- Tarif énergie : `0,53 €/kWh`.
- Frais d'inactivité de l'opérateur : `0,08 €/min`.
- Aucune condition temporelle visible à l'écran pour ces frais.

## Capture B (heure affichée 12:58)
- Statut : `Disponible` ; dernière utilisation « il y a quelques jours ».
- Tarif énergie : `0,53 €/kWh`.
- Détail de durée affiché : « Jusqu'à 10 min » : `0,53 €/kWh` ; « Au-delà de 10 min » : `0,53 €/kWh` plus « Frais d'inactivité de l'opérateur » : `0,10 €/min`.
- Un bloc supplémentaire `0,53 €/kWh` apparaît en bas, mais ses conditions ne sont pas visibles dans la capture (écran incomplet).

## Confrontation à l'audit Data Lab
Fichier : `reports/electroverse/irve-tariff-conflicts-triage-2026-10-10.json` ; EVSE normalisé : `FRMGPE94015AB1P1`.
- Deux lignes sources déjà en conflit : `sourceEvsePk=3568499` : 0,53 €/kWh sans €/min ; `sourceEvsePk=951893` : 0,53 €/kWh et 0,08 €/min.
- La capture A correspond au composant 0,08 €/min déjà présent ; la capture B introduit **0,10 €/min après 10 min**, qui ne correspond directement à aucune des deux lignes sources résumées.
- Les statuts de disponibilité divergent aussi à une minute d'intervalle, sans établir à eux seuls quelle fiche source est actuelle.

## Décision
- **Conflit confirmé, non résolu** ; ne sélectionner aucun modèle de frais d'inactivité automatiquement.
- Ne pas convertir « frais d'inactivité » en frais inconditionnels de session.
- Afficher « tarif incalculable » pour le scénario incluant ces frais lorsque les conditions ne peuvent être identifiées avec certitude.
- Prochaines preuves demandées : capture complète du tarif jusqu'en bas avec conditions d'application, fiche d'information « i », et si possible précision sur la sélection de l'une ou l'autre entrée P1 depuis la liste de la station (doublon ou fiche actualisée).
- Ne pas étendre cette observation aux trois autres prises P2–P4 sans preuve.

Statut : `EVIDENCE_ONLY_DO_NOT_PUBLISH`.
