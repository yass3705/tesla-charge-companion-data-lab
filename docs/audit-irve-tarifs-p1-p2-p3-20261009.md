# TCC France — audit P1/P2/P3 des correspondances tarifaires (9 octobre 2026)

**État : audit terminé, run [37976604619](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/37976604619), conclusion success.** Aucun overlay publié en production. Source IRVE dynamique : 2026-10-09 18:01:03 UTC; seul `en_service` explicite inclus.

## Principes

- Référence du LEFT JOIN : `EVSE_ID_NORMALISÉ`, identifiant PDC IRVE normalisé (sans séparateurs), **une ligne par EVSE**, puissance nominale maximum IRVE. Plusieurs tarifs attachés séparément à cet EVSE.
- **P1** : même identifiant normalisé dans la source eMSP d'origine et dans l'IRVE (et baseline CPO direct spécifique ou grille CPO nationale officielle déjà vérifiée).
- **P2** : P1 plus correspondances validées **déjà publiées dans les overlays Data Lab Electra eMSP/Electroverse**, y compris les identités techniques, curatées et certaines attributions homogènes. Provenance `metadata.identityMode` conservée. Priorité au P1 si un EVSE est aussi P2.
- **P3** : complément potentiel **absent des overlays P2**, à partir de l'inventaire source; une unique station IRVE à <=10m, comptage EVSE **identique** (entier station), tolérance AC `max(2kW,10%)`, DC `max(15kW,10%)`, tarifs homogènes et attribuables sans ambiguïté, preuve CPO et adresse indépendante. Le GPS seul n'autorise aucune attribution de tarif. Pour un CPO hétérogène en prix, besoin de preuve d'identité par EVSE. Aucune promotion P3 sans validation.
- Exclure EVSE `hors_service`, `inconnu`, absents de la dynamique. Les stations avec >=1 EVSE `en_service` restent actives.
- Tarifs directs CPO : référentiels conservateurs audités par EVSE ou profils réseau officiellement validés, non exhaustifs de tous les CPO français.

## Quatre combinaisons tarifaires mutuellement exclusives

| Combinaison | P1 | P1 + P2 | P1 + P2 + P3 strict |
|---|---:|---:|---:|
| CPO seul | 6 959 | 3 135 | **3 135** |
| CPO + Electra eMSP | 17 312 | 11 946 | **11 946** |
| CPO + Electroverse | 3 607 | 7 428 | **7 428** |
| CPO + Electra eMSP + Electroverse | 12 520 | 17 889 | **17 889** |
| **Total avec tarif CPO direct** | **40 398** | **40 398** | **40 398** |

## Couverture supplémentaire

| Source | P1 identités exactes | P2 supplémentaires (overlay validé) | P1+P2 | P3 nouveaux stricts |
|---|---:|---:|---:|---:|
| Electra eMSP | 51 146 | 2 522 | **53 668** | **0** |
| Electroverse | 22 406 | 29 485 | **51 891** | **0** |

- **94 586** EVSE confirmés `en_service`, **77 751** avec au moins un tarif à P1+P2+P3, **16 835** sans tarif identifié dans les sources retenues.
- Au seul P1 : **64 494** EVSE avec au moins une source tarifaire.
- P3: **11 EVSE Electra candidats** dans une passe technique préliminaire (3 lieux), mais éliminés par vérification indépendante d'adresse/code postal; **0 nouveaux P3 validés**. Il s'agit d'absence de preuve suffisante, **pas** d'une preuve que ces bornes sont hors service. Electroverse: aucun nouveau P3 techniquement admissible, et son cache ne constitue pas une preuve indépendante de CPO.
- Couverture CPO de 40 398 = sous-ensemble conservateur des prix directs effectivement identifiés par les extracteurs de cet audit, **pas** une déclaration d'exhaustivité nationale.
- Les catégories peuvent changer à mesure qu'un eMSP rejoint un EVSE déjà couvert, tandis que le total CPO direct reste stable.

## Reproductibilité

- Calcul initial CPO et overlays : `scripts/audit_fr_tariff_left_join_20261009.py`
- Sous-niveaux exact/GPS préexistants : `scripts/audit_fr_two_level_tariff_join_20261009.py`
- Audit P1/P2/P3 incrémental : `scripts/audit_fr_three_priority_match_20261009.py`
- GitHub workflow : `.github/workflows/irve-tariff-left-join-audit-20261009.yml`
- Rapport complet 167 puissances : artifact `irve-tariff-left-join-by-evse` du run 37976604619, fichier `irve-p1-p2-p3-tariff-correspondences-20261009.json`.

**Verdict :** P1 et P2 utilisables comme références d'identité pour un futur moteur unifié avec contrôle de provenance, P3 sans aucun ajout validé à cette date. Aucun déploiement V9.
