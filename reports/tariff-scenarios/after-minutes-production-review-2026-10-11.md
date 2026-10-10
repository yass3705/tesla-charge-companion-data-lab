# TCC V9 — frais différés, seuils et plafonds (revue du 11/10/2026)

## Résultats vérifiés

- [Audit de la version actuelle du moteur (27/27)](after-minutes-production-verification-2026-10-11.json) ; [workflow](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/workflows/tcc-v9-after-minutes-production-verification.yml).
- Périmètre : **84 offres** signalées par l'audit France initial du 10/10 ; **6** tarifées suivant un contrat officiel documenté (CPO Plug Inn direct : 1 ; abonnements Charge Pass : 2 ; CPO SIGEIF direct : 3), **78** offres eMSP Electra non justifiées quant à la nature du frais.
- La version actuelle du [moteur production V9](https://github.com/yass3705/tesla-charge-companion-stable/blob/ae2dd2537737a2d0d73d7893214bedcb873746d2/v9-production-runtime/assets/v9/pricing-engine.js) supporte déjà `afterMinutesRate`, `afterMinutesThreshold`, `afterMinutesCap` et `afterMinutesCapMode` si le composant et les paramètres de plafonnement sont attestés. Le rapport du 10/10 utilisait un **moteur antérieur épinglé** pour comparaison ; ne pas reprendre son chiffre de 84 tarifs « calculés mais incomplets » comme l'état du moteur actuel.
- **6 offres directes / abonnements vérifiées :**
  - `pluginn-direct`, `pluginn-chargepass-basic`, `pluginn-chargepass-intense` : +0,30 €/min après **60 minutes branchées** ; contrats vérifiés dans `data/operator_direct/pluginn_fastcharge_official_france.json`.
  - `sigeif-24` : +0,20 €/min après **120 minutes branchées** ;
  - `sigeif-50-100` : +0,30 €/min après **60 minutes branchées** ;
  - `sigeif-7-22` : +0,05 €/min après **180 minutes branchées**, frais de nuit **20h–8h plafonnés à 4 € par nuit** ; contrats vérifiés dans `data/operator_direct/sigeif_official_ile_de_france.json`.
- **78 offres Electra eMSP** : la donnée `afterMinutesRate` n'indique pas si le montant vise le temps connecté, le temps de charge ou le temps de stationnement post-charge. **Ne pas** forcer `afterMinutesComponent` ni un montant, même par analogie avec les règles CPO Electra. Le moteur actuel retourne `complete:false` dans l'échantillon vérifié, ce qui impose **« Tarif incalculable »** au calcul, pas un prix amputé d'une composante.
- Attention : les offres eMSP Electra peuvent concerner des CPO tiers. La [documentation Electra](https://intercom.help/go-electra/fr/articles/13673440-les-frais-d-occupation) précise que les conditions varient selon le mode de paiement et l'opérateur ; les règles des stations CPO Electra ne valent pas preuve pour la couche eMSP.

## Contrôles de sécurité

- Comparaison des formules avec les [grilles officielles SIGEIF](https://www.sigeif.fr/sites/default/files/2025-10/GUIDE%20D%27UTILISATION%20IRVE%202025%20OCTOBRE.pdf).
- Contrôle des seuils stricts, des frais après 60/120/180 minutes, des frais de nuit, du plafond, et des tarifs Plug Inn direct/Charge Pass sans confusion entre les offres.
- Simulation négative : suppression de la nature du frais ou de la preuve du mode de plafonnement → `complete:false`.
- Vérification des 84 anciennes offres par rapport au **moteur stable actuel** ; aucune des 78 offres non justifiées ne doit obtenir un montant définitif.

## Suite

1. Construire une matrice par contrat des 78 offres eMSP (CPO physique, ID EVSE, `afterMinutesRate`, `afterMinutesThreshold`, texte contractuel/source).
2. N'activer le calcul par offre qu'avec une preuve `CONNECTED_TIME` / `TIME` / `PARKING_TIME`, et, si nécessaire, les seuils/caps explicites.
3. Sur la V9, distinguer `Tarif incalculable` (composante connue mais non modélisable) et `Prix non disponible` (aucune offre).
4. Aucun déploiement du moteur ou changement des sources n'est nécessaire pour les 6 tarifs déjà documentés : le code de production testé fonctionne. Pas de publication de valeurs pour les 78 eMSP non justifiés.
