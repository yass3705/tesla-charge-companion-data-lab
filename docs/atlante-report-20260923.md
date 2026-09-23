# Atlante — extraction France et Italie

Instantané du flux myAtlante. Prix TTC directs sans abonnement, par connecteur. Aucun changement dans TCC.

| Pays | Stations | Connecteurs | Prix simple exploitable | Sans prix simple | Tarifs bruts |
|---|---:|---:|---:|---:|---:|
| FR | 162 | 1416 | 1416 | 0 | 1416 |
| IT | 472 | 1842 | 1842 | 0 | 1842 |

## Contrôles et limites

### FR

Extraction : 2026-09-23T12:24:17.632015+00:00 → 2026-09-23T12:30:03.915348+00:00.
CPO : FRATL. 5 requêtes de carte contrôlées. 0 stations ajoutées par le découpage par rapport à la liste nationale directe.
Dimensions tarifaires : {"ENERGY": 1416}. Tarifs sans connecteur correspondant : 0. Erreurs de récupération : 0.

Prix simples par connecteur (EUR TTC/kWh) :

| Prix | Connecteurs |
|---:|---:|
| 0.01 | 22 |
| 0.3 | 10 |
| 0.36 | 230 |
| 0.41 | 20 |
| 0.44 | 46 |
| 0.54 | 985 |
| 0.59 | 103 |

**À confirmer : 22 connecteurs sous 0,10 €/kWh** sur Atlante - Confrançon - Netto Confrançon, Atlante - Mably - Del Arte, Atlante - Warmeriville - Intermarché SUPER Warmeriville. Valeurs conservées telles que renvoyées par l’API, sans confirmation du prix facturé. Voir low-price-review.json avant toute intégration dans un classement.

### IT

Extraction : 2026-09-23T12:30:03.990329+00:00 → 2026-09-23T12:47:09.741492+00:00.
CPO : ITATE. 13 requêtes de carte contrôlées. 472 stations ajoutées par le découpage par rapport à la liste nationale directe.
Dimensions tarifaires : {"ENERGY": 1842}. Tarifs sans connecteur correspondant : 0. Erreurs de récupération : 0.

Prix simples par connecteur (EUR TTC/kWh) :

| Prix | Connecteurs |
|---:|---:|
| 0.45 | 4 |
| 0.47 | 4 |
| 0.55 | 662 |
| 0.57 | 2 |
| 0.61 | 4 |
| 0.69 | 760 |
| 0.75 | 406 |

5 stations ont operatorName vide dans la source. Elles sont rattachées au code CPO vérifié grâce au pays et au partyId, cohérents entre carte et détail ; cette limite est marquée dans operatorVerification.

## Évolution de l’inventaire France

Par rapport au 2026-08-24T09:41:02.949633Z : 12 identifiants ne figurent plus sur la carte et 4 apparaissent. Ce constat ne démontre pas des fermetures ou ouvertures physiques. Le fichier de comparaison contient les identifiants concernés.

6 changements de prix observés sur les connecteurs identifiés dans les deux extractions. Détail dans price-changes-20260824.json.

La couverture porte sur les stations publiées par l’API dans les rectangles documentés. France : métropole et Corse, pas les territoires ultramarins. Les coordonnées, horaires et composantes détaillées restent disponibles dans les réponses brutes. Les prix peuvent évoluer ; aucune session de recharge ou validation de paiement n’a été réalisée.

La procédure et le script réutilisable sont inclus. La clé technique doit être fournie séparément par variable d’environnement.
