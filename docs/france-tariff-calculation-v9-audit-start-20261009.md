# TCC V9 — passage à l'étape CALCUL après gel de la revue IRVE

Date : 2026-10-09. Référentiel des correspondances **figé** : [SOP P1/P2/P3](france-irve-tariff-coverage-frozen-sop-v1.md). Dernière archive permanente : [latest.json](../reports/france/tariff-coverage/latest.json).

## Clés d'entrée obligatoires

- **EVSE IRVE normalisé** (pas la station), `en_service` dynamique positif.
- Un **scénario par couple (EVSE, puissance/standard)** : AC/DC distinct; plusieurs puissances sur un EVSE restent plusieurs lignes tarifaires.
- Offres séparées et traçables : **CPO direct/ad-hoc**, **Electra eMSP**, **Electroverse eMSP**, **abonnements sélectionnés**; jamais de substitution silencieuse d'un tarif eMSP au tarif CPO.
- Session simulée explicite : énergie kWh, SOC initial/cible, énergie récupérable, courbe de charge, durée en charge et connecté, stationnement/post-charge, début et fuseau, trajet/consommation pour coût au km.
- Source tarifaire complète (règles + conditions + granularité + date/heure + devise), au lieu de simplement inférer un prix depuis une station.

## Modèle de calcul par scénario

`Total = énergie + durée-charge + durée-connectée + stationnement/post-charge + ouverture/session + taxes/frais applicables + congestion + compléments conditionnels`

Appliquer fenêtres horaires/weekday, seuils kWh ou durée, paliers OCPI, arrondis de facturation, gratuité initiale, minima de facture, remises abonnement et devise selon la **sémantique exacte** de la source; éviter les doubles comptages des frais de temps. Arrondir le montant final dans la devise, conserver le détail des composants.

**Congestion :** suivre le seuil officiel lorsqu'il est documenté; sinon utiliser **SOC 80 %** uniquement si un vrai tarif de congestion est présent, avec bascule indépendant `inclure/exclure` par ligne. Si durée après seuil inconnue et impossible à estimer, signaler `scenario_incomplet`, ne pas inventer le coût.

`Coût/km récupéré = montant payable / km effectivement récupérés`, seulement si dénominateur et scénario véhicule valides. Trier la meilleure offre **entre lignes comparables** et conserver les alternatives.

## Audit initial du moteur disponible

Sources inspectées dans `yass3705/tesla-charge-companion-stable/v9-production-runtime/assets/v9/pricing-engine.js` et `yass3705/tesla-charge-companion-production/v9-production-shell/bridge.js`.

**Déjà implémenté, à vérifier par tests :**
- Energie kWh, minute de charge et connectée, minutes de stationnement/parking, frais fixes et session, minimum, paliers OCPI, arrondi de facturation.
- Restrictions temps, jour, SOC, puissance, remise/congé selon règles; frais de congestion à partir de 80 % par défaut, bouton activation au niveau offre/EVSE.
- Frais post-charge avec franchise et exemptions horaires; conditions de frais session; calcul et classement coût/km.

**Écarts identifiés à auditer, sans préjuger de leur fréquence :**
1. `tariff_window_crossing_unsupported_components` : lorsque la session traverse des plages et comporte certains frais fixes, paliers, minima ou arrondis, le moteur renvoie `complete:false` au lieu d'un calcul déterministe.
2. `hourly_rounding_unspecified` : certains frais de connexion longue durée ne peuvent être chiffrés sans règle de facturation précise; il faut extraire la source plutôt qu'inventer un arrondi.
3. Les tarifs non `rules` / `component_groups` reposent sur le simple `pricePerKwh`; auditer les offres réellement publiées pour tout autre format de grille et conserver les composants.
4. Les offres hétérogènes d'une même station doivent rester au **niveau EVSE + puissance**, même si l'interface regroupe les résultats visuellement.
5. **Qualité source CPO** : certains éléments d'archive exposent une référence tarifaire officielle sans prix matérialisé par EVSE. Ne pas considérer `hasDirectTariff` comme preuve qu'une simulation complète est calculable pour la session.

## Contrat de sortie recommandé

Un enregistrement par `evseId, powerKw, connectorKind, provider, offerId, subscriptionId, scenarioId` avec :
- `computed | incomplete | ambiguous | unavailable` et `reasonCodes[]`;
- `total`, `currency`, `componentBreakdown`, `congestionIncluded`, `tariffEffectiveAt`, `provenance/matchTier`;
- `recoveredKm`, `costPerRecoveredKm`;
- les offres ambiguës **non** incluses dans le classement de la moins chère.

## Ordre de traitement

1. Inventorier **toutes les formes de grilles** des CPO et overlays validés (nombre d'offres/EVSE et cas par type).
2. Construire les scénarios de tests déterministes par famille tarifaire (y compris cas frontières); comparer au calcul actuel.
3. Corriger les manques réellement déterminables par les données sources; garder les ambiguïtés explicites.
4. Publier le moteur de calcul et les agrégats après tests d'intégration séparés du processus de correspondance figé.

Les totaux de **couverture d'identité** issus du rapprochement IRVE ne doivent **jamais** être interprétés comme le nombre de simulations tarifaires complètes possibles.
