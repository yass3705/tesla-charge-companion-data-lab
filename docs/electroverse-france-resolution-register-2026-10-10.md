# Electroverse FR — registre de résolution exhaustif (10 octobre 2026)

## Périmètre et preuve
- Inventaire source **mis en cache** : 22 818 emplacements, 96 428 EVSE sources, 117 443 connecteurs.
- Sources : cache Electroverse relevé en dernier le 6 octobre 2026, overlay TCC reconstruit le 10 octobre, IRVE statique réactualisée le 10 octobre.
- Overlay Electroverse : 89 991 offres, 104 508 connecteurs publiés ; 4 779 entrées sources EVSE non publiées (4 087 identités uniques emplacement+référence). Ne jamais assimiler ces entrées à autant d'ambiguïtés tarifaires.
- Périmètre : cache tarifaire Electroverse France déjà rapproché des emplacements IRVE. L'inventaire des identifiants bruts de tuiles nationales est distinct et n'est pas entièrement un inventaire d'offres tarifées.
- Audit / détails : [summary](../reports/electroverse/full-reconciliation/summary.json), [156 lignes prioritaires](../reports/electroverse/full-reconciliation/priority-review-evidence.json), [CSV](../reports/electroverse/full-reconciliation/top-priority-cases.csv), [archive intégrale](../reports/electroverse/full-reconciliation/all-unresolved-cases.json.gz).

## Traitement de la file
| Groupe | Quantité | Conclusion à date | Prochaine action |
| --- | ---: | --- | --- |
| Conflits historiques Electroverse confirmés par l'utilisateur | 27 identités / 54 entrées | « Tarif ambigu » conservatoire, aucune variante forcée | Contrôle tarif courant EVSE par EVSE |
| Correspondances de parent IRVE ambiguës | 90 entrées sources, vs 107 rejets du constructeur | 23 ont une **piste technique unique** après exclusion des PDC déjà publiés ; aucune ne constitue une bijection validée | Vérifier connecteur exact, disponibilité des cibles et cardinalité |
| Identifiants IRVE exacts dont la source n'est pas publiée | 4 EVSE | Identité locale unique ; aucun overlay Electroverse existant sur ces cibles ; tarif extrait mais ancien | Lire l'API courante + contrôle domaine public/CPO |
| Références physiques complètes réutilisées sur plusieurs emplacements | 8 entrées | Risque de mauvaise attribution, pas forcément prix contradictoire | Historique des identifiants/liaison opérateur |
| Autres EVSE sources sans correspondance déterministe | 4 623 entrées | Hors publication ; ne pas inventer de prix ou de borne | Regrouper par CPO et station, prioriser les preuves déterministes |
| Doublons techniquement distincts mais à **même prix** | 20 identités : LE2 (16), P01 (4) | Faux conflits retirés par normalisation des restrictions redondantes | Pas de vérification manuelle tarifaire demandée |
| Nouveaux doublons de **prix non équivalents** détectés | 4 identités S81, une seule station | Une variante contient des frais de durée après 4 h ; l'autre non. Publies comme sources, mais lecture courante non confirmée | Éviter double comptage, valider le tarif Electroverse affiché |

### Premières stations à traiter

1. **Au Bureau Soissons** — station IRVE `FRALLPGO000287` ; EVSE `FRALLEGO800088-1` et `-2` ; CCS 150 kW ; cache Electroverse : 0,59 €/kWh au 27 septembre. Identité exacte ; pas d'offre Electroverse publiée sur ces deux cibles. Ne pas confondre tarif Electroverse et tarif CPO Allego.
2. **Lidl Château-Gontier-sur-Mayenne** — station `FRLDLPLFR1132EVCP` ; EVSE `FR*LDL*E00007048` et `FR*LDL*E00007049` ; CCS 120 kW ; cache Electroverse : 0,39 €/kWh au 27 septembre. Identité exacte ; pas d'offre Electroverse publiée. Tarif eMSP à séparer du CPO direct.
3. **Le Plein Tarnais – Saint-Affrique-les-Montagnes** — station `FRS81P81235001`, EVSE `FR*S81*E81235*001*1*1`, `1*2`, `2*1`, `2*2`. Deux sources Electroverse sur chaque EVSE : 0,30 €/kWh ; l'une ajoute 0,03 €/min à partir de 4 h de connexion, l'autre n'expose pas les frais. Les deux composantes TimeRate / ParkingTimeRate ne doivent pas être additionnées arbitrairement. La grille officielle du CPO Le Plein Tarnais présente le seuil 4 h (0,028 €/min pour badge inscrit, sur une plage horaire) : corroboration **de la règle de temps**, pas preuve d'équivalence tarifaire Electroverse. Référence officielle : https://lepleintarnais.fr/.
4. **Parents SAEMES/ADP/H01/C01** — 90 entrées sur 11 stations environ, regroupées dans le rapport ; 23 pistes uniques en puissance/stock de PDC non déjà publiés, à vérifier par identité physique. Jamais de rapprochement sur proximité ou puissance seules.

## Règle d'affichage et priorité
- **Tarif ambigu** : sources contradictoires pour le même EVSE et la même offre sans preuve pour départager ; pas de coût forcé.
- **Tarif incalculable** : source univoque mais contexte de calcul absent.
- **Tarif indisponible** : aucune offre exploitable identifiée pour la borne.
- La tarification reste **par connecteur et puissance**, l'eMSP Electroverse est distinct du tarif direct CPO.
- Toutes les décisions ci-dessus sont **des audits / preuves**, pas des changements de prix publiés dans V9.

## Collecte GraphQL ciblée
La requête de contrôle direct via l'API de l'application Electroverse est implémentée par `scripts/electroverse_live_priority_price_probe.mjs`, exécutée via `audit-electroverse-live-priority-prices.yml`. Rapport attendu : `reports/electroverse/live-priority-price-probe-2026-10-10.json`. Les cas en échec ou non retournés par l'API restent à vérifier dans l'application ; aucun écran de l'application n'a été simulé.

## Contrôle en direct de l'application Electroverse — terminé le 10 octobre 2026
L'appel GraphQL `chargingLocation` paginé, avec la version Android `2026.09.08`, s'est exécuté **avec succès** : **28 stations** examinées, **133 identifiants physiques sur 133** récupérés, **aucun échec**.

Les 133 identifiants ont été classés dans [le registre individuel des décisions](../reports/electroverse/live-priority-decisions-2026-10-10.json) :

| Classe et décision | EVSE distincts | Preuve / suite |
|---|---:|---|
| **Tarif ambigu — deux signatures tarifaires présentes simultanément dans l'API en direct** | **31** | Les 27 EVSE précédents + 4 à Saint-Affrique-les-Montagnes : ne sélectionner aucun tarif |
| **Correspondance parente ↔ PDC indéterminée** | **90** | Les tarifs sources sont univoques ; relier physiquement et sans réutilisation les connecteurs aux PDC IRVE, avec validation des 23 pistes techniques |
| **Identité exacte IRVE, offre source univoque, non publiée** | **4** | Deux Allego Au Bureau Soissons : 150 kW, **0,59 €/kWh Electroverse** ; deux Lidl Château-Gontier-sur-Mayenne : 120 kW, **0,39 €/kWh Electroverse** ; confirmer le périmètre public/éligibilité avant de publier |
| **Référence source complète réutilisée sur plusieurs sites** | **8** | Tarif source univoque mais attribution station ↔ EVSE à confirmer |

La preuve GraphQL complète : [live-priority-price-probe-2026-10-10.json](../reports/electroverse/live-priority-price-probe-2026-10-10.json). Les 31 signatures multiples sont **présentes dans une même réponse actuelle de l'API**, elles ne sont pas seulement un écart entre les vieux snapshots. Bry-sur-Marne Pasteur P1 conserve par exemple deux PK sources : `951893` = 0,53 €/kWh et 0,08 €/min inactivité non conditionné dans la réponse ; `3568499` = 0,53 €/kWh et 0,10 €/min après **600 s**, comme les deux captures utilisateur. S81 renvoie également les versions **avec et sans 0,03 €/min à partir de quatre heures** pour chacune des quatre références.

Les **20 anciens faux conflits** LE2/P01 correspondent à des composantes tarifaires identiques représentées par une règle simple et/ou une règle globale redondante ; après normalisation des règles, **ils ne sont pas comptés comme conflits de prix**.

**Attention :** une fiche source univoque dans l'API ne suffit pas à autoriser la publication, surtout si elle est mal appariée à l'IRVE. Les eMSP Electroverse restent distincts des tarifs CPO directs.

**Statut de publication :** constat et décision en lecture seule, aucune modification de tarif, de correspondance ou d'affichage V9 au titre de cette vérification.

## Procédure de clôture
Chaque cas clôturé doit conserver : station IRVE, EVSE IRVE normalisé, Electroverse Location PK et Source EVSE PK, opérateur, connecteur/puissance, intégralité des composantes et restrictions, horodatage source, origine de la preuve, décision `validated` / `ambiguous` / `incalculable` / `unavailable`, et références d'éventuels tests de non-régression avant publication.
