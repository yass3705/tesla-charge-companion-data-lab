# France IRVE: comparaison du pin V9 et de la collecte du 13 octobre

## Références et méthode

- Pin **public et candidat de développement actuel** : Stable `0a6d2c3415504397310d3dc92fae40be843b2435`, `v9-production-runtime/data/v9/france-static/all.json.gz` ; 48 058 stations, 165 792 identifiants EVSE normalisés.
- Base Data Lab collectée le **2026-10-13 09:26 UTC** : `data/national/france-irve-static-v9/all.json.gz`, SHA-256 `7113daf751ff34922474d8c9ead10c8e998ca651400d56a08f4964d3e66cf94f` ; 49 185 stations, 165 129 EVSE.
- Statut dynamique Data Lab généré le **2026-10-13 10:39 UTC**. Les overlays Electra FR (97 371 offres) et Electroverse FR (89 991) n'ont pas changé depuis le pin Data Lab `047e1911` ; seules les deux bases IRVE sont comparées ici.
- [Résultat machine](../reports/france/irve/pinned-transition-2026-10-13.json) ; [script](../scripts/france/audit_pinned_irve_transition.py). Les jointures ne reposent que sur l'identifiant EVSE normalisé ; aucun rapprochement GPS ou opérateur ne transfère un prix.

## Différence d'identité

| Mesure | Nombre |
|---|---:|
| Stations retenues sous le même ID | 40 031 |
| Stations propres à l'ancien / nouveau référentiel | 8 027 / 9 154 |
| EVSE retenus sous le même ID | 157 949 |
| EVSE propres à l'ancien / nouveau référentiel | 7 843 / 7 180 |
| Même EVSE mais ID de station modifié | 23 978 |
| Parmi ces derniers, même nom, adresse et coordonnées | 22 950 |
| EVSE associés à plusieurs stations dans la nouvelle base | 0 |

La forte rotation des IDs de station semble en partie provenir d'identifiants synthétiques régénérés : les exemples examinés gardent l'EVSE, le nom, l'adresse et les coordonnées. C'est une **inférence** à vérifier pour les 1 028 cas restants et pour les offres directement limitées par station. Même lorsqu'un EVSE est identique, son changement d'emplacement ou d'opérateur exige une vérification avant une nouvelle publication.

| Plateforme | Ancien unique → nouveau unique | Ancien absent → nouveau unique | Ancien unique → nouveau absent | Absent dans les deux | Offres toujours uniques mais ID station changé |
|---|---:|---:|---:|---:|---:|
| Electra eMSP | 92 816 | 4 514 | 34 | 7 | 17 877 |
| Electroverse eMSP | 82 827 | 2 173 | 3 955 | 1 036 | 17 109 |

**Décision : aucun remplacement direct du pin IRVE.** Il ferait perdre 3 955 liens Electroverse auparavant uniques, en plus de 34 liens Electra. Ces offres restent liées au pin actuellement publié ; leur état réel (borne supprimée, renommée, hors service ou simplement absente de la nouvelle source) doit être déterminé avec le statut dynamique et une preuve de provenance. Les offres nouvellement jointes sont des candidates, pas des prix publiés. Le script mesure la jointure source → EVSE ; il ne démontre ni la calculabilité ni la visibilité dans l'interface.

## Sept configurations Belib absentes du pin

Le catalogue Belib officiel a sept configurations tarifaires à EVSE explicite sans jointure dans l'ancien IRVE :

| Station | EVSE exacts dans le nouvel IRVE | EVSE explicitement actifs le 13/10 | Suite |
|---|---:|---:|---|
| Avenue Émile Deschanel 15 | 5/5 | 5/5 | Candidate à un ajout exact contrôlé |
| Rue Cortambert 55 | 4/4 | 4/4 | Candidate à un ajout exact contrôlé |
| Avenue Paul Doumer 39 | 5/5 | 5/5 | Candidate à un ajout exact contrôlé |
| Rue Pierre Mauroy 15 | 3/3 | 3/3 | Candidate à un ajout exact contrôlé |
| SAEMES Porte d'Auteuil | 0/5 | 0/5 | Vérifier accès public et statut auprès de Belib |
| SAGS Parking Lobau | 0/7 | 0/7 | Vérifier accès public et statut auprès de Belib |
| SAEMES Parking Saint-Augustin | 0/5 | 0/5 | Vérifier accès public et statut auprès de Belib |

Les quatre candidates présentent 17 EVSE exacts et positivement `en_service` dans le flux du jour. L'ajout reste soumis à une comparaison des connecteurs, puissances, CPO et conditions d'accès ; les trois parkings sans preuve dynamique ne doivent pas être ajoutés par proximité. Aucun tarif Belib n'a été modifié pendant cet audit.

## Prochaine intégration sûre

1. Comparer les 7 843 anciens EVSE absents et les 7 180 nouveaux avec le flux dynamique et les archives de changement d'ID ; classer les pertes de jointure par CPO et statut.
2. Vérifier la provenance des quatre stations Belib candidates et construire un **complément exact** au pin existant, puis mesurer les deltas Direct, Electra et Electroverse. Ne promouvoir que si les liens tarifaires actuellement valides sont préservés et si les bornes supprimées ne survivent pas artificiellement.
3. Réexécuter le contrôle de jointure, les tests tarifaires, le smoke neuf pays et le navigateur sur un candidat explicitement épinglé. Le pin public demeure `2026-10-13-nine-country-be-belib-exact-candidate` ; aucun déploiement n'est déclenché.
