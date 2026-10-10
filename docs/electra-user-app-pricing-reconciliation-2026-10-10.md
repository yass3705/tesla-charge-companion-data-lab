# Electra eMSP — vérification des captures du 10/10/2026

**Nature :** données Electra eMSP, *pas* tarifs CPO directs/ad-hoc. Les captures ont été fournies par l'utilisateur dans TCC. Les identifiants et prix de source ont été vérifiés par `reports/france/electra/user-screen-reconciliation-2026-10-10.json`.

## Décisions sûres

- **Powerdot, Intermarché Jarville** — `01df2390-d20f-4199-9b15-b2b6c95c94c3`: 60 kW / EVSE `FR*PD1*EITM*JLM*EKO60*3` → `deb8f441-4306-4735-9990-3165dbeefffc` à **0,62 €/kWh** ; 22 kW / EVSE `FR*PD1*EITM*JLM*EKO60*2` → `9d3380b6-bfef-4f52-a50e-11f72cff552c` à **0,49 €/kWh**. Les deux tarifs source ne comportent que le composant `ENERGY`. Correspondances inscrites dans `data/platforms/electra/verified-app-evse-tariff-map.json`, sous garde exacte EVSE/puissance/CPO/chargeTariffId. **CHAdeMO 50 kW / EVSE `FR*PD1*EITM*JLM*EKO60*1` reste non attribué**.

## Preuves confirmées mais non intégrées à la tarification complète

- **Pessac – Hôtel Ibis** : fast 400 kW, courbe tarifaire dynamique 0,39/0,49/0,61 €/kWh. Capture à 13 h 42 le jour présenté au calendrier (samedi) : **0,49 €/kWh**; source `50f6dcec-5b31-4db8-a861-7e59ea75dc82` prévoit précisément 0,49 €/kWh pour le créneau samedi 13:00–17:00. La grille concurrente `95cc5df1-69ff-466d-a4df-3f0ce0e6e60c` est fixe à 0,49 €/kWh ; l'égalité ponctuelle n'est **pas** une preuve de l'affecter aux EVSE 400 kW. La capture montre en outre des frais de congestion de **0,40 €/min après 80 % uniquement si station saturée**. Tarifs des bornes lentes 22 kW non affichés dans l'onglet sélectionné.
- **Marseille – Sofitel Vieux Port** : 200 kW, 13 h 42, **0,61 €/kWh** ; la grille `42e80897-f1e1-406f-bc7c-faadfa6883c2` prévoit précisément 0,61 €/kWh de 12:00 à 22:00 (contre une grille fixe à 0,49 €/kWh). Congestion 0,40 €/min uniquement à partir de 80 % si station saturée. **Nouvelle capture 14h06 : onglet lent 22 kW = 0,49 €/kWh sur toute la journée**, cohérent avec le tarif source fixe `95cc5df1-69ff-466d-a4df-3f0ce0e6e60c`. La fiche de station affiche toujours +0,40 €/min après 80 % si la station est saturée : l'application de ce frais aux EVSE lents n'est pas entièrement démontrée.
- **La Plagne Bellentre** : 100 kW à 0,66 €/kWh, 22 kW à 0,54 €/kWh, frais annoncés **2,40 €/h**. Deux tarifs source différents affichent 0,66 €/kWh : l'un a 2,45 €/h après 4 h, l'autre 2,40 €/h après 45 min, ce dernier est plus compatible avec la capture ; la preuve du déclencheur manque. Pour 22 kW, source 0,54 €/kWh de 8 h à 20 h / 0,48 €/kWh de 20 h à 8 h avec frais TIME et PARKING_TIME de 18 €/h après 4 h — ce niveau ne correspond pas à la présentation agrégée de la capture. **Attention : deux composants identiques TIME et PARKING_TIME ne doivent pas être additionnés automatiquement à 4,80 €/h** sans contrat prouvant leur cumul.
- **Campanile Saint-Quentin (DRIVECO)** : 200 kW à 0,59 €/kWh ; une **seconde capture à 14h05 confirme +12 €/h de stationnement dans l'app**, alors que le tarif rapide source affiche **18 €/h après 15 min**. Ce conflit de frais reste ouvert ; ne pas facturer 18 €/h sur la seule foi du snapshot.  Le tarif lent à 0,44 €/kWh avec 12 €/h après 15 min est cohérent commercialement, mais l'interface affiche **7 kW** alors que l'IRVE source renseigne 22,1 kW. Ne pas écraser la puissance sans preuve technique.
- **Albi, Jardinerie Tarnaise Fonlabour** : retrouvée dans l'app Electra, capture 14h02. **Rapide 50 kW = 0,55 €/kWh**, **lent 22 kW = 0,46 €/kWh**, stationnement annoncé **+6 €/h**. Les tarifs source correspondants sont respectivement `e9a289c6-cb47-40ce-b68f-5fc06889aee6` et `9505942a-595c-4a2d-994c-b8f0c63dbbe7`. Le tarif 25 kW à 0,50 €/kWh reste non vérifié par capture. La grille 50 kW possède à la fois `PARKING_TIME:6` et `TIME:6` ; ne pas cumuler par défaut en 12 €/h. Le tarif 22 kW ne porte pas ce frais, alors que la fiche station le mentionne : les conditions d'application restent à clarifier. **Retirer le statut « introuvable »**.

## Risques transverses moteur TCC

1. **Prix Electra dynamique figé au branchement.** L'app précise : « Vous payez toujours le prix affiché au moment de charger ». Le moteur V9 `pricing-engine.js` dispose d'un calcul par segments temporels lors du passage d'un créneau à un autre. **Cela ne doit pas être appliqué automatiquement au prix énergie Electra dont le tarif est fixé au début de la session**. Les frais temporels et de congestion restent évalués selon leurs propres conditions.
2. **Congestion conditionnelle à saturation.** La règle Electra 0,40 €/min requiert à la fois SOC >= 80 % et station saturée. Ne jamais déclencher sur le seul SOC. Si la saturation ne peut pas être déterminée, le frais doit rester optionnel/conditionnel et le total non conditionné affiché séparément.
3. **Doublons TIME/PARKING_TIME et déclencheurs.** Pour Bellentre, les tarifs exposent à la fois TIME et PARKING_TIME avec le même taux. L'app n'annonce qu'un frais de 2,40 €/h. Ne pas afficher une somme de 4,80 €/h par défaut.
4. **Fraîcheur.** Instantané eMSP source au 08/10, captures du 10/10 ; seuls les couples EVSE/tarif dont ID+composants restent cohérents sont publiables. Toute évolution du tarif exige un nouveau contrôle de concordance.

## Vérifications complémentaires prioritaires dans l'app

- **Pessac** : ouvrir **« Lente 22 kW »** (encore absent). Marseille 22 kW est maintenant confirmé à 0,49 €/kWh toute la journée.
- **Jarville** : ouvrir le **CHAdeMO 50 kW** dans la liste des connecteurs pour voir si son prix est explicitement celui du rapide à 0,62 €/kWh.
- **Saint-Quentin** : les deux captures confirment 12 €/h dans l'app ; vérifier **les conditions de déclenchement (dès le début ou après 15 minutes)** et demander si le montant est identique pour chaque connecteur. Le tarif source rapide à 18 €/h est désormais un conflit explicite à traiter.
- **Albi** : vérifier le connecteur **25 kW** et si le frais +6 €/h concerne toutes les puissances ou uniquement certaines.
- **Bellentre** : vérifier sur l'écran détaillé quel tarif et quels frais s'appliquent au connecteur 22 kW et à quel moment les 2,40 €/h démarrent.

Les cas non vérifiés restent **« tarif incalculable »** pour le canal Electra en cas d'ambiguïté, pas « tarif indisponible ». Toute règle CPO directe valide reste affichable indépendamment.
