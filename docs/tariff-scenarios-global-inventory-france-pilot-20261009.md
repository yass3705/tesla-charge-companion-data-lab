# TCC V9 — Inventaire tarifaire mondial et pilote de calcul France — 9 octobre 2026

**État : premier passage COMPLET, analyse non invasive.**
GitHub Actions : [run 37985452927](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/37985452927) **success**.
Branche d'audit : `audit/global-tariff-scenarios-20261009`. Les exports chiffrés détaillés sont dans l'artifact GitHub Actions `global-tariff-inventory-france-pilot`.

## 1. Inventaire transversal des 9 pays TCC

Périmètre : FR, IT, CH, DE, ES, NL, UK, MA, BE; CPO directs, eMSP, abonnements, référentiels nationaux, sources candidates, raw et certains snapshots runtime.

- **1 308 fichiers** JSON / JSON.gz identifiés; **1 302 analysés**; **6 ignorés** pour JSON invalide ou taille excessive, explicitement recensés.
- Regroupement indicatif par pays selon chemin/metadata (les fichiers peuvent contenir plusieurs pays, la somme ne représente ni EVSE ni tarifs validés) : FR 740; MA 227; CH 142; UK 61; NL 48; BE 28; ES 12; IT 12; DE 6; UNSPECIFIED 28.
- **Familles détectées à partir des noms de champs** : énergie 511 fichiers, durée de connexion 260, stationnement/idle 365, congestion 124, frais fixes/session 221, paliers/arrondis 232, conditions horaires 86, abonnements 135, puissance/connecteur 289, taxes/devises 431, minima 6, structures complexes 326.
- **Attention** : présence d'un champ != offre tarifaire valide ni quantité de bornes couvertes. Certaines données DE sont `stagedOnly`; ES REVE inclut un `PRE_INTEGRATION_ONLY`; la disponibilité des prix et la prise en charge V9 doivent être vérifiées pays par pays.
- FR eMSP publiés parcourus : Electra **98 752 lignes d'offres**, Electroverse **89 990 lignes d'offres** (nombre de lignes, **pas** EVSE uniques).

## 2. Pilote France — moteur V9 existant, inchangé

Version testée du moteur : `yass3705/tesla-charge-companion-stable` commit `38ac26e029ba1c4779d4d8fa43e7d5d300858624`, `v9-production-runtime/assets/v9/pricing-engine.js`.

**17 / 17 scénarios synthétiques déterministes réussis**, notamment énergie, minutes connectées / de charge, parking, frais fixes, minima, franchises, arrondis énergie, paliers OCPI, congestion 80 % et exclusion, minima globaux, condition de session, post-charge et traversée de plage simple. Ce sont des tests ciblés; aucun de ces 17 tests ne constitue une certification d'exhaustivité.

**933 offres réelles échantillonnées** sur les références FR : 441 offres eMSP (240 Electra, 201 Electroverse) + 492 offres compilées V9 CPO et abonnements. La même simulation illustrative a été appliquée partout; ces résultats ne préjugent pas de tous les horaires, SOC ou profils véhicules.

| Classification échantillon France | Nombre |
|---|---:|
| Calcul `complete`, sans champ ignoré détecté | **837** |
| Calcul `complete`, mais avec champs tarifaires sources **ignorés** | **84** |
| Calcul `incomplete` | **12** |
| Exception JS | **0** |
| **Total** | **933** |

### P0 : coût calculé mais frais invisibles / inexploités — 84 cas

- Champs **`afterMinutesRate` et `afterMinutesThreshold`** non utilisés par le moteur actuel dans **84 échantillons**, dont **78 Electra eMSP**.
- Informations de plafonnement complémentaire présentes dans certains tarifs : `afterMinutesCapStart` (**6**) ; `afterMinutesCapEnd` (**6**) ; `afterMinutesCap` (**1**).
- Les 6 autres cas se répartissent entre CPO Plug Inn (**1**), SIGEIF (**3**), et deux abonnements Charge Pass (**2**).
- **Risque métier** : un nombre est rendu même si une dimension de la facture est ignorée. **Ne pas classer ces 84 échantillons comme calculs fiables.** Avant correction définitive, blocage de comparabilité/affichage explicite `incomplet_champ_tarif_non_modélisé`.

### P1 : calcul incomplet mais pas forcément moteur erroné — 12 cas

- **10 YES55 direct** : `post_charge_exemption_requires_start_time`. La simulation manque du début réel de la phase post-charge exigé par la plage d'exonération.
- **2 Révéo direct 11** : `no_matching_time_rule`. Aucune plage tarifaire applicable à l'heure illustrative; examiner calendrier officiel et politique de résultat `non applicable`, sans prix fictif.

### Limites du test

- L'analyse est **un inventaire de schémas et un test sur des échantillons**, non le calcul exhaustif de toutes les bornes, puissances, fenêtres horaires et conditions de chaque pays.
- 6 sources non analysées; remédier à leur taille/format avec lecture incrémentale si elles contiennent des prix.
- Les nouveaux correctifs du moteur doivent conserver la parité avec les 17 scénarios existants, ajouter des tests d'horaire / seuil / plafond / puissance / souscription, puis faire une seconde passe sur des données françaises représentatives et complètes.
- **Aucune modification du moteur V9 en production**.

## 3. Plan d'extension après pilote FR

1. **FR** : protéger le classement contre les 84 `complete` trompeurs, modéliser les champs `afterMinutes*` depuis preuves tarifaires CPO/eMSP, fournir le contexte nécessaire aux 10 cas YES55, interpréter correctement les 2 plages Révéo. Repasser une matrice de tests sur toutes familles et puissances.
2. **CH + IT** : réutiliser les bases nationales/directes et vérifier multi-tarifs, CHF/EUR, CPO par EVSE, abonnements, prix par minute, horaires, stationnements.
3. **UK + DE** : OCPI/PCPR, frais fixes/durée, règles de puissance/temps, staging AFIR vs CPO direct, vérification public/ad-hoc.
4. **NL + ES + BE** : prix par EVSE, sources nationales et roaming/candidats, séparation des tarifs publiables, statut REVE, arrondis/TVA.
5. **MA** : tarification par minute, statut de source nationale absent, correspondance CPO exact, devise MAD et conversion contextualisée.
6. Chaque extension doit livrer `scenario_id`, preuve source, test déterministe, état `computed | incomplete | ambiguous | unavailable`, composants détaillés, et un run daté.

**Décision recommandée :** conserver et renforcer le calcul actuel, ne pas le réécrire; corriger le P0 des champs ignorés, puis seulement après validation de parité France étendre les pays. Pas de prix inventés pour combler les sources manquantes.
