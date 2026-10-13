# V9 — pilotes bornés Electra NL et Electroverse GB (13/10/2026)

Statut : **diagnostic**, aucun prix eMSP international épinglé en Production. Maroc hors périmètre.

## Electra eMSP ↔ DOT-NL : collecte réelle et jointure

Le script [pilote](../scripts/pilot_electra_nl_emsp.py) interroge quatre pages fixes de 100 lieux à offsets 0, 50 000, 250 000 et 300 000, et les compare au [DOT-NL normalisé](../data/national/netherlands_dotnl/normalized.json.gz). [Rapport JSON](../reports/emsp-pilots/electra-nl-dotnl.json) : SHA-256 de la base inclus ; quatre réponses complètes sans erreur, `totalCount=322939` constant pendant l'essai. Échantillon déterministe et **non représentatif du pays entier**.

| Niveau mesuré | Décompte |
| --- | ---: |
| Lieux Electra NL sur les quatre pages | 257 |
| Grilles `chargeTariffs` source sur ces lieux | 268 |
| EVSE Electra dans ces lieux | 597 |
| EVSE sans ID correspondant dans DOT-NL | 230 |
| EVSE avec ID normalisé unique et GPS concordant à ≤120 m | 367 |
| Parmi ces 367, statut positif dans les deux sources | 356 |
| Parmi ces 367, lieu à une seule grille Electra | 351 |
| Parmi ces 367, lieu à plusieurs grilles Electra | 16 |
| Parmi ces 367, référence tarifaire Direct DOT-NL présente | 360 |

Ces catégories se chevauchent ; **351 n'est pas un nombre d'offres eMSP publiables**. L'ID EVSE/GPS prouve une identité candidate, mais il faut encore vérifier connecteur, puissance, opérateur et périmètre de la grille. Les 16 EVSE multigrilles restent sans affectation automatique. Les 230 EVSE non joints ne prouvent pas une absence de borne, seulement l'absence de ce même ID dans ce pin DOT-NL.

Exemple source exact : `NLLMSE1000055828*1`, statut `AVAILABLE` des deux côtés et GPS identique. Electra eMSP expose une grille `ENERGY` à 0,61 €/kWh ; DOT-NL référence séparément le tarif Direct `NL:505:364295044`, dont l'énergie est 0,50 € HT/0,605 € TTC par kWh. Les deux montants proches ne sont **pas** interchangeables. Le rapport conserve les composants source de chaque voie. Le cas `NL*EFL*EV9580442*C1` illustre l'inverse : même ID/GPS, mais statut `UNKNOWN` des deux côtés, deux IDs de grille Electra et aucune référence tarifaire directe ; aucune offre calculée n'en résulte.

## Electroverse GB ↔ CPO UK : test authentifié limité

Le [workflow manuel](../.github/workflows/electroverse-uk-cpo-pilot.yml) exécute le [script](../scripts/electroverse_uk_cpo_pilot.mjs) dans GitHub Actions avec le secret déjà configuré, sans l'afficher. Il vise trois lieux CPO publics et actifs issus des sources épinglées : Source EV Milton Gate, Allego Liddington Road et MFG St Albans. Pour chacun : neuf tuiles zoom 18 autour du CPO, puis interrogation des seuls PK proches et de leurs EVSE/tarifs. Limites strictes : 80 PK/témoin, 12 lieux détaillés/témoin et 100 requêtes au total. Une erreur ou un dépassement arrête le témoin ; aucun prix n'est deviné. Rapport JSON en artefact Actions conservé sept jours, aucune écriture dans les données canoniques.

La comparaison porte sur l'ID EVSE normalisé exact et le GPS proche. Les composants Electroverse ne sont consignés comme **preuve de collecte** que pour ces correspondances ; le script ne produit aucun overlay V9. Les IDs tarifaires PCPR des CPO demeurent dans la voie Direct. Résultat du run authentifié à compléter après exécution.
