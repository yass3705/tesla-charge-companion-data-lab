# G5 — Revue documentaire préfixes et références physiques (2026-11-25)

## Conclusion
Structure eMI3 nationale documentée ; l'association du champ Electroverse physicalReference avec la partie locale d'un EVSE-ID n'est pas garantie par le standard OCPI. Aucun code numérique Electroverse n'est approuvé. Aucun nouveau match/prix, v5 14968 inchangée. G5 PARTIAL. Ne pas transformer l'absence de preuve en rejet définitif.

## Audit amont
Run https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45616209607 ; job 139212144845 ; code d4ccf9e3078a62b7b93d50589836d46fd99dbe54 ; completed/success 12:44:04Z le 25/11. 12 tests et public safety PASS. Artefact 15020954425 (1494094 octets, expiration 25/12 12:43:58Z), SHA256 c1d37171dc2a78f38332a2a5c4c20243fb9ae0d6a73367eb4e340afa9a5311c9 ; CRC et trois exports vérifiés indépendamment :
- global-references.csv.gz : 4caa061d754de52aceb050dc3512263da12235f8650c032ac736412da8b19bfb
- global-unique-pairs.csv.gz : 5893f160e3cc8da9e0774a0e0dca89aed07f578dce5f4bf33adbae84bb8adf20
- prior-392.csv.gz : 0b721e41b38989c52ccf56ca3f11d640f68285dff7dd120f33372a8a174e383e

181456 lignes IRVE brutes, 181412 propriétaires, 174948 propriétaires statiques, 101856 actifs ; 22818 locations/93510 groupes/113383 connecteurs source. 72269 références distinctes utilisables : 19545 structurellement uniques, 356 plusieurs propriétaires nationaux, 6 plusieurs propriétaires source (433 groupes), 52362 aucune cible structurée ; 2259 groupes sans référence alphanumérique. 392 historiques : 374 uniques, 2 collisions, 16 suffixes arbitraires. 28432 couples actifs, 28390 libres, 10318 plug/courant/puissance PASS (toutes allocations), 9983 présélection (aucun diagnostic hors PREFIX_RULE_NOT_INDEPENDENTLY_DOCUMENTED, CPO_PROOF_NOT_ESTABLISHED, TARIFF_SCOPE_NOT_VALIDATED), 9959 PDC, 3439 stations, 4579 <=5m, 7916 cible archive. Aucun hit même-record source/référence et cible. Potentiel théorique 24951 avec v5, non validé. Prefixes: FRFR1E 4548, FRLE2E 1994, FRWIZE 647 (libellé IRVE EVZEN), FRFASE 461, FRS10E 387, FRS56E 377, FRBMPE 356, FRPLNE 356, FRS80E 278, autres 579.

## Sources publiques consultées le 25/11/2026
- Transport.data.gouv.fr : https://doc.transport.data.gouv.fr/type-donnees/infrastructures-de-recharge-de-vehicules-electriques-irve/donnees-statiques/produire-ses-donnees — format FR + 3 caractères + E ; P pour station, unicité du PDC. Confirme la syntaxe, pas la transformation Electroverse.
- Avere-France/Afirev : https://afirev.fr/prefixes/obtenir-un-prefixe/ et https://afirev.fr/prefixes/consulter-l-annuaire/ — attribution eMI3, annuaire distinguant aménageur, opérateur et état administratif. Interface https://app.afirev.fr/embed/annuaire ne rend que « Chargement... » dans la consultation textuelle ; lignes FR1/LE2 non vérifiées directement. Le lien data.gouv https://www.data.gouv.fr/api/1/datasets/r/3a7284cc-d108-403a-85c2-77214a56fa45 redirige vers l'annuaire, pas un CSV accessible.
- OCPI 2.2.1 : https://ocpi.github.io/openapi-specification/ocpi/2.2.1/roles/cpo-interface.html — evse_id et physical_reference sont deux champs distincts, ce dernier est un repère visuel. Exemple officiel https://github.com/ocpi/ocpi/blob/2.3.0/release/core/examples/location_example.json (EVSE complet BE*BEC*E041503001, physical_reference 1). Ne présume aucune transformation générale ni que GraphQL Electroverse suit exactement OCPI.
- Freshmile : https://www.freshmile.com/aide-contact/ et https://www.freshmile.com/articles/recharger-son-vehicule-electrique-freshmile/ — QR et lien XFM sur le point physique ; pas de règle publiée affirmant que le code XFM est systématiquement le suffixe eMI3.
- Electroverse : https://intercom.help/electroverse/en/articles/9534055-how-do-i-select-the-correct-charging-point-and-charger-for-my-charge — l'identifiant affiché dans l'application doit correspondre à celui du point physique ; aucune définition publique trouvée pour operatorId numérique ni règle universelle du champ physicalReference.
- E.Leclerc : https://www.mouvement.leclerc/espace-presse/le-mouvement-eleclerc-lance-charge-e-lec-sa-nouvelle-offre-de-recharge-electrique — Freshmile supervise les bornes de l'offre Charge E-Lec ; relation commerciale explicite, pas preuve d'équivalence de tous FR1/LE2 ni de codes numériques.
- Gireve : https://www.gireve.com/fr/freshmile-renforce-son-partenariat-strategique-avec-gireve-pour-deployer-le-plug-charge-en-france/ — relation d'itinérance confirmée ; pas de crosswalk numérique.
- Pages dérivées IRVE, exemples https://adhoccharging.eu/fr/city/mondeville/freshmile-fr-fr1-rue-charles-coulomb-mondeville-14120-france/ (FRFR1EAABM1) et https://adhoccharging.eu/city/chalons-en-champagne/eleclerc-frle2-42-rue-du-moulin-saint-martin-sur-le-pre-51520-france/ (FRLE2EAACF1) : corroboration du libellé/ID national seulement, pas indépendantes si même source IRVE. Aucun appel aux endpoints fournisseurs ni contournement.

## Contrôle local reproductible sur sources épinglées
Téléchargements GitHub ZIP et CRC vérifiés : 14937133575 SHA256 b538f0b420e046dcd597f5c3b32fd5a2ff76451a9ad6ff97f2ea66892a9f3719 ; raw static.csv SHA256 6556dea1a9237640fca0c9c50ca380ea46f8044031a13d2c684f53b9837d094f ; v5 14966840567 SHA256 c5ae905e217c47d410ff36d167ea0169acb515def4a2fc4e1244e69c3d927a04 ; SQLite SHA256 65d1f4ed8cd81fec38ef5fa045bbec74db70490803a761832708a8b9b17ff744, lecture immutable. Filtre 9983 indiqué ci-dessus. Jointure raw par (station_id, evse_id) ; id_pdc_local normalisé comme ident() ; zéro égalité exacte avec physicalReference, 8481 autres valeurs, 817 identiques à l'ID itinérance complet, 685 manquantes. Les 6542 FR1/LE2 proviennent du Fichier IRVE Gireve, id_pdc_local différent ; exemples AABM1 / FRFR1EAABM1 / 1302002 et AACF1 / FRLE2EAACF1 / 1805334. Le champ id_pdc_local ne peut servir de pont. Les 22818 source_location du ledger ne comportent aucun operator_name renseigné. Parmi les 6542, zéro ancre v5 même station/préfixe ; 2 candidats FR1 sur locations avec une autre ancre, pas preuve d'identité. Sur toutes les 14968 v5, code 21133 avec 383 FR1 exacts et code 3353 avec 606 LE2 exacts ; ce sont indices, pas preuve indépendante CPO. Ne pas extrapoler ni fusionner FR1 et LE2.

| Préfixe | operatorId | Candidats | Ancre v5 code/préfixe |
|---|---|---:|---:|
| FR1 | 21133 | 4176 | 383 |
| FR1 | 64694 | 221 | 0 |
| FR1 | 727 | 87 | 0 |
| FR1 | 3326 | 52 | 0 |
| FR1 | 3527 | 8 | 0 |
| FR1 | 3468 | 4 | 0 |
| LE2 | 3353 | 1990 | 606 |
| LE2 | 98468 | 4 | 0 |

## Proposition de pilote (non exécuté)
Échantillon de départ, un cas par code, choisi sur distance minimale et référence lexicographique, uniquement pour recherche de preuve, pas extrapolation :
| Code | Référence | EVSE national | LocationPk | Station IRVE | Distance m |
|---|---|---|---|---|---:|
| 21133 | JCFV1 | FRFR1EJCFV1 | 652329 | FRFR1P8289342808958091411 | 0.382 |
| 64694 | NBKJ1 | FRFR1ENBKJ1 | 943602 | FRFR1P3954308727827316770 | 0.869 |
| 727 | WAYZ1 | FRFR1EWAYZ1 | 617076 | FRFR1P2365459661242012003 | 1.271 |
| 3326 | MYKC1 | FRFR1EMYKC1 | 581442 | FRFR1PVFKUJC | 1.793 |
| 3527 | RRHD1 | FRFR1ERRHD1 | 1004083 | FRFR1P5316535057035692011 | 4.806 |
| 3468 | ATEN1 | FRFR1EATEN1 | 574865 | FRFR1P8704164420360895621 | 2.060 |
| 3353 | DEGM1 | FRLE2EDEGM1 | 592630 | FRLE2P855251647589442442 | 0.334 |
| 98468 | ADFM1 | FRLE2EADFM1 | 617325 | FRLE2P6018472125822626667 | 0.823 |

Prochaine décision utilisateur : soit collecte ciblée autorisée de champs explicites evseId/partyId/operator name via source existante, sans secrets, sans modifier collector ni augmenter le volume avant vérification de disponibilité des champs ; soit validation manuelle documentaire/app des références et des codes. Tester 8 cas et contre-exemples (collision BCRU1/EFWZ1) ; une preuve par cas ne suffit pas à généraliser le code ; exiger contrat de données/équivalence documentée ou preuve par EVSE. En cas d'absence, classer NON_VERIFIABLE et conserver la cohorte à part ; ne pas refaire audit statistique identique. Une nouvelle politique de confiance probabiliste nécessiterait accord explicite et statut séparé des validés. G6 DATE_BASED reste à traiter. Pas de nouveau workflow car audit documentaire et contrôle local achevés. Aucun changement règle, prix, main/Production, registry, publication ; sauvegarde durable des décisions et lien génération restent ouverts. Mac local inaccessible. Rollback : revert commit documentaire, aucun effet sur catalogue.
