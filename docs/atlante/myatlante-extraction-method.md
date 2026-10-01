# Extraction des tarifs Atlante par station et connecteur

Méthode retrouvée dans les commandes du travail TCC V8 du 24 août 2026, relancée le 23 septembre 2026. Conserver ce dossier pour les prochaines extractions.

## Accès et périmètre

L'API utilisée par myAtlante est consultable sans compte utilisateur avec une clé technique d'abonnement API. « Sans compte » ne signifie donc pas « sans clé ». La clé fournie dans la conversation n'est pas enregistrée dans ce dossier. Elle doit être passée à l'exécution dans `ATLANTE_API_SUBSCRIPTION_KEY`.

Base : `https://pdefweushaapiam01.azure-api.net/app-backend/v1/tenants/390c3ff9-b41c-42dc-aa48-1dd51ad6ce39`

En-têtes : `Ocp-Apim-Subscription-Key`, `Accept-Language: fr`, `X-App-Version: 2.1.0`, `X-App-Platform: android`.

1. `GET /map-locations` avec `latLongBottomLeft`, `latLongTopRight`, `evseTypes=AC,DC,HPC`, `locationStatus=ALL`, `includeCpos`.
2. Pour chaque identifiant de station : `GET /locations/{id}`.
3. Pour cette même station : `GET /locations/{id}/tariffs`.
4. Relier les tarifs au détail avec `(identifiers.evseId, identifiers.connectorId)` côté tarifs et `(evses[].evseId, evses[].connectors[].evseConnectorId)` côté détail.

| Pays | countryCode | partyId | includeCpos | Rectangle sud-ouest / nord-est |
|---|---|---|---|---|
| France métropolitaine, Corse incluse | FR | ATL | FRATL | 41,-6 / 52,10 |
| Italie, Sicile et Sardaigne incluses | IT | ATE | ITATE | 35,6 / 48,19 |

Ne pas extrapoler le code `ATL` à tous les pays : l'Italie utilise `ATE`. Pour un nouveau pays, consulter une zone avec des stations Atlante sans filtre CPO, puis vérifier le pays, le partyId et operatorName dans le détail. Ajouter ensuite le code et un rectangle adapté à `COUNTRIES` dans le script.

## Lancement

Python 3, bibliothèque standard uniquement. Après avoir défini la variable d'environnement :

```sh
python3 extract_atlante.py --countries FR IT --out results --workers 8
```

Le script lit la carte nationale et quatre sous-zones, déduplique les identifiants et subdivise les sous-zones si l'API renvoie des regroupements `locationSummaries`. Il vérifie les identifiants, le pays et l'opérateur dans chaque détail. Il conserve les réponses brutes et les erreurs, sans perdre les stations dont certains prix sont inexploitables.

Si `operatorName` est vide, le rattachement repose sur le couple pays/partyId déjà validé pour Atlante, présent dans la carte filtrée et dans le détail. Le champ source reste vide et `operatorVerification` signale cette limite. Un nom d'opérateur contradictoire est rejeté.

Pour reconstruire les fichiers normalisés sans refaire les requêtes, une fois toutes les réponses brutes sauvegardées :

```sh
python3 extract_atlante.py --countries FR IT --out results --rebuild-from-raw
python3 package_results.py
```

Ce mode ne nécessite pas de clé et conserve les dates de collecte enregistrées dans les rapports. Il échoue si une carte attendue manque et signale les détails ou tarifs manquants comme erreurs.

## Interprétation

- `stations.json` : stations, adresses, coordonnées, connecteurs, puissance et tarifs associés.
- Dans ce flux, `max_electric_power` est repris comme puissance en kW (par exemple 22, 150, 300, 600) ; ne pas le diviser arbitrairement par 1 000. Le prix TTC provient de `price.incl_vat`, et non de `price.excl_vat`.
- `report.json` : dates d'extraction, couverture, volumes, prix et erreurs.
- `raw/` : cartes, détails et tarifs reçus de l'API pour audit.
- `pricePerKwhEur` est renseigné uniquement pour un tarif ENERGY en EUR TTC sans conditions ou restrictions de validité, avec une seule composante et un prix non ambigu. Sinon il reste nul ; les composantes brutes sont conservées.
- Les composantes de prix ne doivent pas être réduites à un prix au kWh si elles comprennent des frais de temps, de session, d'occupation ou des conditions. Ne pas inventer les frais absents.
- Il s'agit du flux direct myAtlante sans abonnement, distinct des prix Atlante Go et des tarifs d'itinérance chez les partenaires.
- La couverture décrit les stations publiées par cette API, pas une preuve indépendante de l'exhaustivité de toutes les stations physiques du réseau. Les statuts et tarifs constituent un instantané et peuvent changer pendant l'extraction.
- Le nom de tarif direct vient de la méthode TCC existante ; aucun test de paiement n'est effectué. Les données ne sont pas automatiquement intégrées ou publiées dans TCC.

Pour réutiliser la méthode dans une autre conversation, fournir ce dossier ou le fichier PROCEDURE.md. La conservation de ce fichier ne garantit pas le rappel automatique de la méthode dans chaque nouveau chat.
