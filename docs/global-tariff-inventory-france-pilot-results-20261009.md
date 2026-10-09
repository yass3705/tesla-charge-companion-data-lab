# TCC — premiers résultats vérifiés de l'inventaire tarifaire global et du pilote France

**Date : 2026-10-09.** Pipeline d'audit : [GitHub Actions 37984721285](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/37984721285), terminé avec succès. **Aucune modification du moteur V9 production.**

## Inventaire des sources (première passe)

- **1 571 fichiers de données parcourus**, dont **1 566 analysés**; 3 fichiers non interprétables et 2 sources trop volumineuses. Les fichiers échantillonnés sont signalés et ne sont pas considérés comme exhaustifs.
- Détection de familles énergie (kWh), temps, parking/idle, congestion, frais fixes, paliers/durée, heure/jours, puissance, abonnement et devise/TVA.
- **Attention :** les « occurrences de familles » comptabilisent des fichiers contenant des champs compatibles, pas des EVSE ni des tarifs CPO vérifiés; les duplications de sources et versions sont possibles.
- Les premiers résultats de l'inventaire incluent des sources FR/IT/CH/DE/ES/NL/UK/BE; les fichiers de vérification marocains ont été ajoutés explicitement au scan suivant sous le statut `recherche_observation_non_validée`.
- Les fichiers candidats/staging, les sources brutes et les overlays d'itinérance ne sont **pas assimilés à des prix directs CPO publiables**.

## Inventaire des vrais tarifs eMSP France

- Electra eMSP : **98 752 lignes d'offres** (pas 98 752 EVSE actifs distincts).
- Electroverse eMSP : **89 990 lignes d'offres**.
- Total : **188 742 lignes**, toutes au format `pricing.type=rules` dans cette passe.
- Échantillons réels structurels analysés par le moteur V9 : **240 Electra + 201 Electroverse**, tous calculés pour un profil de session illustratif.

## Banc d'essai France élargi

- **17/17** tests déterministes de calcul réussis : kWh, temps, parking, session/connexion, minimum, paliers, arrondi, SOC 80/congestion, options utilisateur, changement horaire, et cas de calcul incomplet attendus.
- **933 offres réelles échantillonnées** (eMSP + catalogues CPO directs V9 + abonnements).
- **921 simulations complètes** selon le retour du moteur, **12 incomplètes** (10 fois heure de début de frais post-charge absente; 2 fois absence de règle horaire applicable); **0 exception**.
- Certains catalogues V9 portent des champs `afterMinutesRate`/`afterMinutesThreshold` qui ne sont pas lus directement par le moteur `pricing-engine.js` du commit épinglé `38ac26e029ba1c4779d4d8fa43e7d5d300858624`. **Risque de surcoût omis quand le seuil de temps est dépassé** : cas spécifique à isoler avant de déclarer la simulation complète.
- **Important :** le résultat « calculé » ne vaut pas validation exhaustive : un seul profil test et source V9 épinglée, cas réels particuliers (SOC, longues sessions, heures et puissance) encore à traiter.

## Mise à disposition permanente

Voir [reports/tariff-scenarios/](../reports/tariff-scenarios/) : inventaire fichier par fichier, familles tarifaires, exemples source et rapports de calcul. La sauvegarde automatique sur `main` est assurée par `.github/workflows/global-tariff-scenario-review.yml`. Les rapports datés sont versionnés sous `snapshots/` et l'historique Git.

## Ordre de validation

1. France : vérifier toutes les familles complexes et les champs non modélisés (notamment après-durée), sans remplacer ce qui marche.
2. Suisse + Italie : tests CHF / EUR, abonnements et puissances.
3. Royaume-Uni + Pays-Bas + Espagne : PCPR, PAYG, REVE/DOTNL et monnaie GBP.
4. Allemagne + Maroc + Belgique : grilles AFIR/OCPI composites, tarif par minute, sources partielles et restrictions d'accès.

**Critère avant publication :** montant chiffré seulement si toutes les composantes tarifaires qui s'appliquent sont modélisées et l'attribution EVSE+puissance est validée. Sinon `incomplete` ou `ambiguous`, jamais 0 par défaut.
