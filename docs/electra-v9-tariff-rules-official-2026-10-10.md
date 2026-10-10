# TCC V9 — règles Electra vérifiées le 10/10/2026

Périmètre : CPO Electra et ses offres dans l'application Electra. Ne **pas** appliquer automatiquement les mêmes conditions aux autres CPO accessibles avec la carte/app Electra eMSP.

## 1. Prix dynamique de l'énergie

Source officielle : https://www.go-electra.com/fr/price/ et https://www.go-electra.com/fr/electra-plus/

« Le tarif exact est toujours affiché dans l'application avant la session de charge, et reste verrouillé pendant toute la durée de la session. »

Politique : `priceSelectionBasis=session_start_local_time`, date/heure locales de la borne, **sans segmentation de l'énergie** au passage d'un créneau. Les frais de durée conservent des mécanismes indépendants ; ne pas recopier cette politique aux partenaires.

## 2. Congestion

Source officielle : https://www.go-electra.com/fr/newsroom/charging-overstay-fees-explained/

Avec l'app Electra sur le CPO Electra : frais uniquement sur DC si **SOC ≥ 80 % et station saturée**, 5 minutes de grâce à compter de la réunion de ces conditions, puis **0,40 €/minute**, **maximum 50 €** par session. La politique Electra ne s'applique pas sur les bornes partenaires.

Dans TCC : **bouton optionnel à côté des stations pertinentes**, décoché par défaut, coché = simulation « station supposée saturée ». Ne jamais inférer que la station est réellement saturée. Toute simulation qui nécessite un contexte SOC inconnu doit échouer explicitement ; pas de coût forfaitaire automatique.

Runtime : `v9-production-runtime/assets/v9/pricing-engine.js`, `session-engine.js`, `v9-production-shell/bridge.js`.
Source : `scripts/electra_france_platform_snapshot.mjs`. Tests : `tests/v9-electra-station-pricing-policy.test.cjs` dans le dépôt stable.

## 3. Frais temporels TIME / PARKING_TIME

Ne pas confondre durée de recharge et durée inactive ; les deux phases ne sont pas forcément cumulables pour les mêmes minutes. L'API Electra fournit parfois ces composants simultanément ; garder les frais contestés (Bellentre / Albi) en suspens.

## 4. Frais après une durée / plafond

Rapprocher les cas IZIVIA et SIGEIF dans le moteur. Lorsqu'une source contient `afterMinutesRate` mais ne précise pas s'il s'agit de `TIME` ou `PARKING_TIME`, retourner `after_minutes_component_unverified` (tarif **incalculable**) plutôt que d'omettre discrètement des frais.

Lorsque cette phase est prouvée, `afterMinutesComponent=TIME|PARKING_TIME` et `afterMinutesThreshold` autorisent le calcul par phase ; si plusieurs seuils, plafonds ou composants se chevauchent sans preuve, suspendre le total chiffré.

## 5. Attribution par EVSE et puissance

Une offre s'applique à une borne/EVSE et à sa puissance, pas à la station entière. Des tarifs distincts sur deux puissances différentes sont normaux. Plusieurs tarifs non équivalents possibles pour **le même EVSE à la même puissance** sans preuve de sélection → **tarif ambigu / incalculable**. Une absence de tarif source → tarif indisponible. Aucun prix inféré de la seule station, de la borne voisine ou du nom d'opérateur.

## Publication

Les tests de moteur n'impliquent pas que les snapshots Data Lab aient été republiés dans le registre V9. Vérifier séparément build Data Lab, export/synchronisation source V9 et déploiement du site. Ne jamais annoncer « V9 publié » uniquement sur la réussite des tests JavaScript.
