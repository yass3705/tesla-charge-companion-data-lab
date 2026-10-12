# TCC V9 — Rebaseline tarifaire neuf pays avant audit EVSE exhaustif

Date de préparation : 12 octobre 2026. **État : audit documentaire reproductible en lecture seule, PAS inventaire actuel des EVSE et PAS publication V9.**

## Références et portée

Cette étape fige les preuves datées des rapports existants afin de ne pas confondre fichier source, connecteur, offre eMSP et scénario calculé. Commande de recalcul : `python scripts/v9_tariff_gap_baseline_20261012.py` ; contrôles : `python scripts/v9_tariff_gap_baseline_20261012.py --check` et `python -m unittest discover -s tests -p 'test_v9_tariff_gap_baseline_20261012.py'`.

- Rapports sources : `reports/tariff-scenarios/review-latest.json` (revu le 10/10, run 38047584760), `reports/netherlands/nl-cpo-unpriced-evse-inventory-2026-10-11.json` (snapshot 10/10) et `reports/tariff-scenarios/after-minutes-production-verification-2026-10-11.json`.
- Inventaire mondial daté : **1 312 fichiers recensés, 1 306 analysés, six non analysés**, et **1 179 stations Tesla déclarées dans la source utilisée par l'audit historique**. Ni le décompte de fichiers ni celui des stations Tesla ne prouve le nombre d'EVSE tarifés, actifs ou accessibles.
- Fichiers sources classés par pays dans ce rapport historique : FR **740**, IT **12**, CH **142**, DE **6**, ES **12**, NL **48**, UK **61**, MA **227**, BE **28**. La classification n'est pas un décompte de bornes et n'est pas nécessairement une partition sans recouvrement. L'audit devra ensuite couvrir les sous-répertoires non attribués et les sources non analysées.
- Les neuf pays sont présents, mais la profondeur et la fraîcheur des fichiers ne sont pas comparables. **Aucune couverture tarifaire nationale intégrale n'est déduite de ces chiffres.**

## Pays-Bas : revoir l'ancienne cible « 5 246 »

Le rapport du 11 octobre portant **exclusivement sur quatre CPO** compte :

| CPO | Connecteurs sans tarif direct | Parmi eux AVAILABLE ou CHARGING |
| --- | ---: | ---: |
| Laadnet (LNT) | 504 | 438 |
| Agri Go Charge (AGO) | 2 578 | 2 375 |
| StellaPower (SPA) | 0 | 0 |
| WattHub (WAT) | 124 | 63 |
| **Total de ce sous-ensemble** | **3 206** | **2 876** |

Ce ne sont **pas** 3 206 scénarios « incalculables » : la plupart sont **sans référence tarifaire nationale directe**, ce qui correspond à « prix non disponible ». Il reste impérativement à vérifier **sur un nouveau snapshot DOT-NL**, au niveau EVSE/connecteur : prises Type 2 et CCS seulement, statut disponible ou occupé, accès effectivement public et composants tarifaires applicables. Les 5 246 cas annoncés antérieurement concernent une autre population et doivent être **recalculés**, sans soustraire ni additionner ces chiffres entre eux.

DOT-NL prime sur les tarifs directs lorsque la référence appartient au CPO de la borne et est cohérente. Les tarifs eMSP restent dans des canaux indépendants. La règle vaut pour tous les CPO, y compris Agri Go, et ne justifie pas de vérifier chaque prix national existant dans une application tierce.

## France : frais différés

Sur les **84 offres réelles historiques** étudiées, **6** règles directes/abonnements disposent d'une preuve suffisante, et **78 offres Electra eMSP** n'ont pas de preuve sur la nature de la durée facturée (`CONNECTED_TIME`, `TIME` ou `PARKING_TIME`). Ces 78 ne doivent fournir **aucun total inventé** : « Tarif incalculable » tant que leur contrat propre n'est pas établi. Les preuves d'un tarif CPO direct ne se substituent pas aux conditions d'un eMSP tiers.

## Prochain audit calculatoire à produire (nouvelle passe, neuf pays)

Pour chaque pays, mesurer séparément, **sur les versions exactes courantes des sources et du moteur** : (a) EVSE accessibles au public et en service (disponibles ou occupés), (b) connecteurs Type 2 / CCS, (c) présence de tarif direct CPO, abonnement, Electra eMSP ou Electroverse eMSP, (d) motifs de prix indisponible, tarif ambigu ou tarif incalculable, (e) taux de scénarios effectivement calculables par famille énergie/minute/frais/horaires/paliers/plafonds/SOC80 et devise. Conserver la puissance et l'identité EVSE ; **ne jamais agréger les prix d'une station**.

Priorité : **NL** pour le recensement exhaustif et les 5 246 cas à requalifier ; puis **France Electra/Electroverse** (dont Lidl/Allego et 78 frais différés) ; enfin balayage neuf pays en conservant les sources Tesla, OCPI/PCPR, les fuseaux horaires et les spécificités MA. Utiliser les collectes courantes seulement après validation du statut de publication et de provenance.

**Aucun tarif, snapshot ou moteur n'est changé par ce dossier.** Les limites des anciennes mesures sont affichées, sans présenter ce pré-audit comme une solution exhaustive.

## Extension read-only DOT-NL Type 2 / CCS (PR)

Le workflow de cette PR produit également un **artefact de contrôle** `v9-nl-type2-ccs-scope-audit` depuis `data/national/netherlands_dotnl/normalized.json.gz` du commit analysé. Script : `scripts/v9_nl_type2_ccs_scope_audit_20261012.py`. Il filtre les connecteurs Type 2/CCS et conserve séparément la disponibilité (AVAILABLE/CHARGING), les références tarifaires nationales présentes et les références absentes, par CPO et avec SHA-256 de la source.

**Important :** ce deuxième résultat est un décompte de connecteurs candidats, **pas** une preuve d'accès public ni une simulation de prix ; il n'attribue pas « calculable » à une référence tarifaire qui n'a pas encore été simulée. Les autres prises et statuts non actifs sont exclus de la sélection active et reportés dans les diagnostics. L'artefact n'est pas publié dans TCC.

## Résultat du contrôle DOT-NL réel — run 38187419104

Audit de `data/national/netherlands_dotnl/normalized.json.gz` sur le commit Data Lab `3c9588b49ab16efdce4a8a20fcd21d9564cc9856`. Source générée le **11/10/2026 à 10:32:38 UTC**, empreinte SHA-256 `651d3723e67250ff9e5dfe0644a4b7973a8609ff08e3021b3f253cc5ef85ee93`.

- **175 437** occurrences de connecteurs Type 2/CCS (170 305 Type 2 ; 5 132 CCS).
- **165 418** de ces connecteurs indiquaient AVAILABLE ou CHARGING ; **10 019** n'étaient pas dans ces statuts ou avaient un statut inconnu.
- **5 431** occurrences n'avaient aucune référence tarifaire nationale DOT-NL ; **3 908** étaient disponibles ou occupées. **161 510** connexions actives avaient une référence nationale, à vérifier ensuite pour la calculabilité réelle.
- CPO prioritaires parmi les **3 908 actifs sans référence nationale** : **Agri Go 2 374**, **GFX 738**, **Laadnet 432**, **EFL 111**, **NUO 84**, **WattHub 74**, **UB2 36**, **QPA 32**, **SGM 25**, **LMS 2**. Ces codes opérateurs sont ceux de DOT-NL et doivent être réconciliés avec leur nom réel avant les démarches CPO.
- Le fichier persistant `reports/netherlands/v9-nl-type2-ccs-scope-20261012.json` conserve les détails agrégés par CPO et l'identifiant du run de preuve. [Validation GitHub](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/38187419104).

**Ce résultat n'est pas le nombre de tarifs « incalculables ».** Il compte les références nationales manquantes. L'étape suivante doit vérifier l'accès public et calculer réellement les offres associées aux **161 510 connecteurs actifs avec référence** : composantes, conflits, restrictions temporelles, seuils, plafonds, parking et devise. Le statut n'est qu'une photographie du 11 octobre. Aucune attribution tarifaire par station ou par simple proximité.

## Deuxième audit NL — compilabilité contractuelle du tarif CPO

Le workflow PR exécute `scripts/v9_nl_direct_tariff_compiler_audit_20261012.py` en **lecture seule** sur le DOT-NL épinglé au commit du run, et compare son périmètre à l'audit Type 2/CCS : nombre de connecteurs actifs et nombre exact de références manquantes. Il classe chaque occurrence active en : sans référence nationale, compilée mais **non simulée**, contradictoire, référence pointant sur un tarif absent, tarif hors période, tarif non-direct, ou règle incomplète/non prise en charge.

Ce diagnostic utilise **le compilateur DOT-NL déjà en place**, sans le modifier. Il ne fournit **pas** de simulation complète : les profils horaires, durée connectée, énergie, stationnement et frais SOC80 devront être validés indépendamment avant d'annoncer un prix réel. Le rapport de détail est conservé comme artefact CI, puis ses agrégats seront archivés dans la PR après validation. Aucun nouveau prix, abonnement ou eMSP n'est injecté en Direct.

## Contrôle de compilation DOT-NL — run 38189617121

Sur les **165 418 occurrences de connecteurs Type 2/CCS disponibles ou occupés** dans le snapshot du 11/10, le compilateur direct DOT-NL a accepté **161 509 références tarifaires** (sous réserve des simulations de charge), identifié **3 908 absences de référence tarifaire**, et rejeté **1 référence hors période**. Aucun conflit ni autre code de rejet détecté dans ce périmètre, à cette date. Le bilan par CPO avec son empreinte source est archivé dans [le rapport JSON](../reports/netherlands/v9-nl-direct-compiler-reconciliation-20261012.json). [Run GitHub Actions validé](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/38189617121).

Le seul rejet tarifaire concerne l'EVSE `NL*NUO*EALF*0072880*1` (connecteur Type 2, 22,08 kW, référence `NL:NUO:2000025714-2000013230`) : `no_current_element` au 11/10. Vérifier si la source a omis la grille en vigueur ; **ne pas** remplacer par un tarif d'une autre borne. Parmi les références absentes, AGO : 2 374, GFX : 738, LNT : 432, EFL : 111 (les autres CPO figurent dans le rapport).

**Étape obligatoire suivante :** tester des scénarios réels (kWh, temps de charge et de connexion, stationnement, changements de créneau, min/max durée, TVA/arrondis) avec la version actuelle du moteur, puis contrôler les entrées tarifaires. Ces **161 509** tarifs sont *compilés*, **pas** démontrés comme correctement calculables dans tous les cas. Les sites à accès non public restent à exclure de la publication après vérification, sans les présumer publics sur le seul statut OCPI.

## Simulation prospective de six profils de recharge (en cours de validation CI)

Le script `scripts/v9_nl_direct_tariff_simulation_fixtures_20261012.py` conserve l'opérateur, le type de prise, la puissance et le tarif retenu du connecteur, ainsi que sa multiplicité. Un candidat tarifaire partagé est simulé une fois par classe (tarif, opérateur, prise, puissance) puis pondéré par le nombre de connecteurs actifs représentés. L'objectif est de couvrir les **161 509** connecteurs dont le compilateur DOT-NL a accepté une référence, sans fusionner les prix par station. Les **3 908** sans référence et le cas unique hors période restent exclus du calcul chiffré.

Les six hypothèses sont : charge un jour ouvré, charge en soirée suivie d'une occupation, traversée de minuit, dimanche avec occupation, session de quatre heures, traversée du changement d'heure automnal. Ces dates/énergies/durées sont des **profils hypothétiques**, pas des factures ni une preuve que le tarif sera encore applicable à ces dates.

La CI épingle le runtime **Production V9** sur `84e86c317af2f4d2380f2fd1543dd4befafc10fe`, importe l'adaptateur réel DOT-NL et son moteur tarifaire, exécute les régressions contractuelles, contrôle les totaux d'EVSE pondérés et publie un **artefact de résultats non déployé**. Seuls les tarifs simples ENERGIE sont comparés à une formule indépendante ; tous les autres succès sont déclarés **moteur a retourné un montant**, et non **prix commercial indépendant validé**. Les éventuels refus exacts sont conservés par profil, CPO, offre et raison.

Aucune correction automatique de prix ou déploiement n'est autorisé par ce workflow.
