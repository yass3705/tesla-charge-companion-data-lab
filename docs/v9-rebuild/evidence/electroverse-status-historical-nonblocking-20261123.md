# Electroverse V9 — observation historique non bloquante, fin du veto 16 h (23/11/2026)

## Décision produit et périmètre

Confirmation explicite utilisateur du 23 novembre 2026 : **TCC reste exclusivement un comparateur de tarifs**. La disponibilité réelle est toujours vérifiée dans l'application de recharge avant utilisation. La disponibilité live Electroverse est FACULTATIVE ; aucun statut de disponibilité, même récent, ne conditionne les stations, les offres Direct/Electra/Electroverse, les jointures EVSE/prises ou le calcul des prix. Ne jamais publier une disponibilité ancienne comme instantanée.

La règle antérieure `FRESH_SECONDS=16*3600` était un contrôle local et n'est **pas** un quota fournisseur. Elle ne bloque plus les acquisitions, les reprises et la clôture d'un inventaire **historique**, même si plusieurs jobs dépassent ensemble 16 h. Pour les observations nouvelles, l'horodatage `observedAtByLocation` est conservé par ChargingLocation PK. Les observations héritées sans horodatage individuel gardent exclusivement les bornes authentiques `startedAt`/`updatedAt` de leur partition ; aucune date précise n'est fabriquée. Un diagnostic d'âge `allPartitionsFresh` peut rester faux, mais n'est pas une condition de complétude historique.

## Source immuable et sauvegarde

- Data Lab : `yass3705/tesla-charge-companion-data-lab`, branche `rebuild/v9-20261020`. Départ audité avant intervention : `6fe136575af3d5060f6f935a693010dc7528fd46`.
- Run source interrompu : [45086131828](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45086131828), conclusion `cancelled` après le plafond configuré de 300 minutes, aucun statut national complet.
- **Dernier checkpoint durable** : artifact `14790727210`, `tcc-v9-electroverse-status-stage-sweep-10`, ZIP SHA256 `13df5d3920803d3f56e8cbc71cd5068f3a6709b84f54e8d2f2c77c78e9c17b5e`, fileset complet SHA256 `28fb15b237f7868a294703ef27cdd0ee7f83303879e28cf83a8ba55133ef43b7`, sourceFingerprint `3365025ffc1f0f57ac4b48101e4e78517797a8cbb5a8b2a72fea60bce1cd12b4`.
- Inventaire audit : **14 091 succès** sur **22 818 stations**, 11 partitions 00–10 enregistrées, **393 erreurs différées**, 1 204 PK non visités dans les partitions déjà entamées et 7 130 PK dans les cinq partitions encore absentes (total 8 727 non vérifiées). 14 091/22 818 = 61,75 % ; ni succès national ni tarification nouvelle n'en découlent.
- 23/11 : copie ZIP téléchargée indépendamment du run GitHub et contrôlée localement : 316 179 octets, SHA256 exacte, CRC ZIP PASS, 15 membres inventoriés et SHA256 de chaque membre PASS. L'artefact GitHub annonce expiration le 30/11/2026 04:48:26Z ; conserver une copie autonome si une reprise au-delà est nécessaire. Aucun octet tarifaire/provenance parent réécrit.

## Changements réalisés et sécurité

Fichiers V9 modifiés : `scripts/electroverse_status_incremental.mjs`, `v9_rebuild/electroverse_status.py`, `scripts/pilot_v9_electroverse_status.py`, `scripts/resilient_v9_electroverse_status.py`, les tests associés et `docs/v9-rebuild/PROJECT_SPEC_G0_G9.md`. Contrôles conservés : fingerprint tarifaire, manifeste et SHA du checkpoint, identités, erreurs différées, compteurs HTTP 429 **par station** (60/120/300 s, quatrième 429 arrête), attente de cooldown, aucun tarif inventé et aucune publication automatique. Le job GitHub reste limité à 300 min mais un garde à environ 216 min depuis la préparation interdit de commencer une nouvelle unité de durée potentielle 60 min ; l'unité sauvegardée est persistée avant la fin du job et peut être reprise depuis une archive SHA-pinnée. Les acquisitions peuvent nécessiter plusieurs runs successifs, chaque nouveau run devant pointer explicitement le dernier artefact vérifié.

## Vérification hors fournisseur

- Requête `mode=verify`, `explicitProviderAuthorization=false` commit `ced0d80bff1f91d5eb5a94fdc3be3dd574812339` (23/11/2026).
- [Run #45153951292](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/45153951292), job **137622050675**, `completed/success`, SHA exécuté `ced0d80bff1f91d5eb5a94fdc3be3dd574812339`.
- **39 tests Python PASS, 25 tests Node PASS, scan `public_safety_check.py` OK** ; zip source tarif et checkpoint récupérés et empreintes validées ; reconstructeur du delta restitue le fileset SHA256 `28fb15b2...` ; contrôleur `verified_only` confirme `verifiedLocations=14091`, `errors=393`, `resumeEligible=true`, `supplierCalls=0`.
- Le test de reprise après 17/25 heures et le test de limite préventive du runner sont inclus. **Aucune collecte fournisseur, ni publication, ni changement de main/Production/Updater Test** dans ce run.

## Suites autorisées / risques résiduels

La vérification prouve la possibilité de reprendre le checkpoint, **pas** la complétude du recensement live ni l'actualisation des prix dans TCC. Toute collecte ultérieure doit rester un unique run borné avec `automaticPublication=false`, puis faire l'objet d'un nouvel audit d'artefact et d'une éventuelle demande de reprise à partir de ce nouveau digest. La présence d'un champ `allPartitionsFresh=false` signifie seulement que l'historique n'est pas instantané : **ne jamais l'utiliser pour afficher une disponibilité courante**. Les axes tarifaires, les jointures IRVE et l'interface doivent pouvoir progresser indépendamment.
