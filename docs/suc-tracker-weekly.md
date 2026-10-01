# SuC Tracker : collecte GitHub et comparaison Mac

## Collecte autonome

Le workflow **Weekly SuC Tracker Tesla snapshot** tourne chaque dimanche à **04:17 UTC**, sur un runner GitHub Linux. Le Mac peut être éteint. Une première collecte est également déclenchée lorsque le workflow ou ses scripts sont intégrés dans `main`.

Il télécharge une seule réponse de `https://suc-tracker.eu/data/europe.json`, valide le schéma, les identifiants, les dates et la couverture, puis enregistre ensemble :

- `data/suc-tracker/europe.json` : source complète SuC (34 pays dans le relevé initial) ;
- `data/suc-tracker/tesla_stations.json` : JSON au format TCC, sur les pays activés dans `config/countries.json` (11 pays / 1 182 stations initialement) ;
- `data/suc-tracker/metadata.json` : date du contrôle, dates réelles de source, compteurs et empreintes.

Ce catalogue est indépendant de `tesla-charge-companion-stable/data/tesla_stations.json`. Il ne remplace pas la production. Aucun secret supplémentaire ni compte Tesla n'est nécessaire. Le workflow utilise le jeton GitHub intégré uniquement pour enregistrer ses trois fichiers dans ce dépôt.

En cas d'échec de téléchargement, de schéma invalide, de recul de date ou de baisse supérieure à 10 % du nombre de stations d'un pays, la version précédente reste sur GitHub. Les tarifs restent datés du relevé SuC : une collecte hebdomadaire ne rend pas la source temps réel. Les horaires d'accès provenant du précédent relevé Mac restent identifiés comme tels ; un accès inconnu reste inconnu.

Les exécutions programmées dépendent de la disponibilité et du quota GitHub Actions du compte. Un éventuel échec est visible dans Actions. Les artefacts temporaires ne sont pas la source canonique : les JSON sont conservés dans Git.

## Comparaison après le passage Mac

La comparaison fait un `git fetch` en lecture avec les identifiants déjà utilisés par le checkout Mac. Elle épingle un seul commit GitHub pour lire les trois fichiers cohérents et vérifie leurs empreintes. Elle ne fait ni checkout, ni reset et ne modifie pas les résultats du collecteur.

Les workflows Mac existants appellent automatiquement la comparaison :

- **Export to Charge Companion** : seulement le pays du rapport d'export, ou les pays du rapport global validé ;
- **Update Tesla stations by lot** : seulement les pays terminés du lot (`published` ou `validated_not_published`). Les pays bloqués/incomplets sont exclus. Chaque pays est extrait de son propre `publish-candidate.json`, pour éviter d'utiliser la copie ancienne des autres pays présente dans un export global.

Les rapports `comparaison_mac_suc.html` et `comparaison_mac_suc.json` sont joints à l'artefact habituel du passage Mac. Ils restent aussi sur le Mac dans `export/suc-comparison/` pour l'export simple ou `runtime/suc-comparison/` pour un lot. Une indisponibilité SuC produit un avertissement et ne supprime ni ne bloque le résultat Mac.

Le workflow simple **Test Tesla station updater** conserve son fonctionnement actuel : après le scan, lancer l'export comme d'habitude ; c'est cet export qui déclenche la comparaison.

## Comparaison manuelle d'un fichier final Mac

Depuis le dépôt updater actualisé :

```bash
python3 scripts/suc_tracker/compare_mac.py \
  --mac-json export/tesla_stations.json \
  --countries france \
  --out runtime/suc-comparison
```

Pour Belgique + Pays-Bas + Luxembourg : `--countries BE,NL,LU`.

On peut remplacer `--countries` par `--mac-report export/france-report.json`. Le périmètre est alors lu dans le rapport validé. Sans sélection explicite ni rapport de pays terminés, la commande refuse de comparer : elle ne déduit jamais les pays mis à jour de l'ensemble des pays présents dans le JSON Mac.

Pour un lot terminé :

```bash
python3 scripts/suc_tracker/compare_mac.py \
  --lot-summary runtime/lot/lot-summary.json \
  --out runtime/suc-comparison
```

Les tarifs sont comparés sur toutes les minutes de la journée, en devise native et avec les tranches de puissance. Les découpages horaires équivalents ne sont pas signalés comme différents. Les frais annexes et la disponibilité en direct, absents de SuC, ne sont pas comparés. Un écart entre des relevés de dates différentes ne prouve pas une erreur.

## Validation

```bash
python3 -m unittest discover -s tests/suc_tracker -p 'test_*.py' -v
```

Tests : conversion tarifaire, tranches de puissance, rejet des plages ambiguës, préservation du dernier fichier valide, intégrité des fichiers GitHub et filtrage des seuls pays terminés sur Mac.
