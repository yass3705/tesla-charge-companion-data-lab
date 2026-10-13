# EnergyVision Belgique — supplément CPO indépendant, phase diagnostique

## Objectif et origine

Le flux DATEX authentifié EnergyVision du 13/10/2026 expose 1 236 stations / 3 791 PDC et 1 226 grilles ad-hoc au niveau station ; l'audit NAP épinglé [#38431651109](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/38431651109) ne trouve aucun rapprochement exact des 3 791 IDs `BE*NRG` au NAP de 71 opérateurs sélectionnés. EnergyVision n'apparaît pas dans la liste nominative `docs/belgium-cpo-progress-2026-09.json` ; ce n'est pas une preuve de non-publicité des stations.

Un supplément **autonome en diagnostic seulement** est créé à partir de l'inventaire EnergyVision lui-même, sans l'inventer via les rapprochements GPS. Le supplément ne remplace ni ne modifie la base NAP, le registre V9, ses offres ni la publication Pages.

## Contrôles techniques

- 1 236 IDs de sites distincts, 3 791 IDs de PDC et IDs externes uniques ; identités statiques recoupées avec les statuts dynamiques exacts.
- Connecteurs autorisés : Type 2 et CCS ; puissances en watts conservées ; coordonnées vérifiées ; aucune duplication de l'identifiant source.
- Les références dynamiques supplémentaires sans point dans le flux statique ne deviennent pas des PDC.
- Seuls les statuts `available` ou `charging` sont signalés comme positifs ; tous les autres sont conservés dans l'inventaire de preuve mais non éligibles à l'affichage d'une recharge en service.
- Les 1 226 ID de grilles sont conservés au niveau station, **jamais copiés automatiquement sur tous les PDC**. Les règles comportant fenêtres, seuils et frais restent non interprétées.
- `typeOfSite` et méthodes d'authentification DATEX sont collectés en métadonnées pour examen. Cela **ne prouve pas l'accès public** ; `publicAccessVerified=false` tant qu'une source claire ne le confirme pas.
- `v9PublicationReady=false` et `v9PricedPDC=0` sont des garde-fous bloquants. Le supplément se trouve uniquement dans un artefact Actions de sept jours, et n'est pas une source tarifaire V9.

## Décisions restantes

1. Confirmer l'accès réellement public et la déclaration `typeOfSite` pour chaque site ou catégorie grâce au CPO / à la documentation officielle. Les tags AFIR et `onStreet` ne sont pas à eux seuls suffisants pour garantir un accès public.
2. Confirmer auprès du CPO la portée `energyRate` station → PDC, notamment lorsque le site associe Type 2 et CCS, ainsi que les groupes `priceGroupIndex`.
3. Confirmer la signification des composantes `pricePerMinute`, `timeBasedApplicability/fromMinute,toMinute`, leurs bornes temporelles, fuseau Europe/Brussels et arrondis. Ne pas facturer par hypothèse.
4. Obtenir une preuve de fraîcheur tarifaire : un flux collecté aujourd'hui conserve des `lastUpdated` remontant à 2025/2026, ce qui n'est pas en soi une garantie de validité au 13/10.
5. Tester par oracle indépendant des scénarios kWh/minutes/taxes et frontières horaires sur un échantillon stratifié.
6. Une fois les garde-fous prouvés : ouvrir **une autre PR Production** pour intégration des seuls PDC publics et offres calculables, avec nouveau snapshot candidat et aucun déploiement sans autorisation.

## Flux GitHub

`.github/workflows/energyvision-datex-stage.yml` continue à n'utiliser `ENERGYVISION_API_KEY` que dans GitHub Actions sur `main` ; les PR exécutent les tests sans clé, sans collecte externe. L'artefact étendu contient `energyvision-independent-cpo-supplement.json.gz` et un rapport agrégé anonymisé des comptes.

## Electric 55, Place Lully (preuve distincte)

L'utilisateur a transcrit depuis le portail E55C un tarif consommateur au 13/10 : frais de session 0,60 €, 07h–23h charge 0,08 €/min et parking 0,08 €/min ; 23h–07h charge 0,06 €/min et parking 0,06 €/min. La preuve est conservée dans `data/station_verifications/electric55_place_lully_direct_portal_user_2026_10_13.json`. Numéro exact de PDC, déclenchement des frais de parking, règles d'arrondi et TVA restent non prouvés. **Aucun prix direct attribué aux PDC de la station ni au réseau entier.**

## Résultat du run sur main, après correction de la dérive du flux

- [PR #262](https://github.com/yass3705/tesla-charge-companion-data-lab/pull/262) fusionnée `2ff9e647` : normalisation inventaire CPO autonome et conservation de la preuve Place Lully dans `data/station_verifications/electric55_place_lully_direct_portal_user_2026_10_13.json`. Tests PR `38434146825` réussis.
- Le premier run `38434297043` a révélé une croissance légitime : **1 238 stations / 3 795 PDC**, contre 1 236/3 791 quelques heures auparavant. Le contrôle conservait l'ancienne égalité stricte et a bloqué l'archive, **sans publier de tarif**.
- [PR #263](https://github.com/yass3705/tesla-charge-companion-data-lab/pull/263) fusionnée `3635cef7` : garde identité univoque + variation bornée ±10 % autour du repère de 3 791, avec différentiel journalisé. Le [run main #38435009280](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/38435009280) est **success** (tests + collecte + supplément + artefact). C'est le **dernier état vérifié**.
- **1 238 sites / 3 795 PDC uniques**, dont 3 671 Type 2 et 124 CCS ; statuts exacts : 2 513 `available`, 1 120 `charging`, 131 `unknown`, 23 `inoperative`, 8 `faulted`. **3 633 PDC** en état positif, mais non déclarés tarifés ou accessibles site par site.
- **3 795/3 795** identités statiques couplées à un statut dynamique unique ; aucune référence dynamique orpheline sur cette collecte. 3 795 identifiants externes distincts ; **0/3 795 correspondances ID exactes ou normalisées avec les 17 pages NAP**. Le NAP sélectionné conserve ses autres CPO, aucune substitution ni rapprochement GPS seul.
- **1 228** grilles `adHoc` station, 10 sites sans grille. Les PDC du supplément gardent `priceable=false`, et la source ne prétend pas qu'un tarif de station est un tarif individuel validé ; `v9PricedPDC=0`, `v9PublicationReady=false`.
- Le DATEX transmis signale `typeOfSite=openSpace` et `authenticationMethods=rfid,apps,website` pour les 1 238 sites. Le [catalogue officiel transportdata.be](https://transportdata.be/en/dataset/energyvision-public-charging-network-afir-datex) qualifie bien la source comme **EnergyVision Public Charging Network**, destinée aux données d'infrastructures accessibles au public. C'est une preuve du **périmètre public de la source**, pas un audit des obstacles d'accès à chaque parking individuel : l'état `publicAccessVerified=false` est conservé par précaution dans le supplément.
- La [documentation technique DATEX II](https://docs.datex2.eu/v3.3/energy/) confirme que les prix peuvent figurer au niveau site, station ou PDC. Le [schéma AFIR de référence](https://github.com/MobilithekDE/AFIR-DATEX-II-Recharging-Profil/blob/main/Releases/Version%2001-00-00/Schema%20und%20Beispiele/EnergyInfrastructureStatusPublication/DATEXII_3_AfirEnergyInfrastructure.json) indique que les composantes d'une grille s'additionnent **lorsqu'elles sont applicables (AND, non OR)** ; `timeBasedApplicability` borne les minutes de charge. Les règles de seuil, les grilles à horaires et les arrondis doivent néanmoins passer des oracles avant un prix TCC calculable ; ne pas confondre un prix `pricePerMinute` avec du stationnement post-charge sans preuve.
- L'artefact `energyvision-datex-staging-38435009280` (sept jours) contient les trois fichiers de staging et le rapport JSON `reports/belgium/energyvision-cpo-supplement-audit.json`. Valeur de référence : SHA-256 du flux statique `a412de196e0f92b71d2a5a0892b75fc9fbdb40cd9a06af917b86af5ac2a8423d`.

**Suite :** obtenir les conditions d'accès exactes lorsque nécessaires, la preuve d'application `energyRate` aux PDC et la sémantique minute/seuil. Ensuite seulement préparer un adaptateur Production avec prix par PDC réellement applicables. Aucun déploiement V9/PAGES/Cloudflare n'a été effectué.
