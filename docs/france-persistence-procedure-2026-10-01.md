# France V9 — procédure de persistance GitHub

Date de validation : 2026-10-01
Repo canonique : `yass3705/tesla-charge-companion-data-lab`
Branche canonique : `main`

## Règle
Aucun run France n'est terminé tant que toute décision sûre n'est pas persistée et relue depuis `main`.

## Chemin normal
1. Relire `main` et récupérer les SHA courants.
2. Tenter l'écriture directe seulement si elle est simple et sûre.
3. Relire `main` après écriture et vérifier le canonique.

## Fallback obligatoire si l'écriture directe échoue
1. Créer les blobs/trees/commit nécessaires.
2. Créer ou mettre à jour une branche temporaire dédiée au batch depuis le dernier `main`.
3. Ouvrir un pull request de cette branche vers `main`.
4. Relire le PR jusqu'à obtenir `mergeable=true`.
5. Fusionner avec `expected_head_sha` pour empêcher une fusion d'un head différent.
6. Relire depuis `main` tous les fichiers concernés et vérifier le commit de merge.
7. Vérifier le canonique : `treated + setAside + active = 291`, longueurs cohérentes, aucun overlap exact, `pendingDedupe=0` sauf preuve contraire.
8. Seulement ensuite reprendre une nouvelle investigation CPO.

## Cas de référence
- batch491 : PR #98, merge `0ac156a0b20991db17176c07de59affa20e23b8c`
- batch492 : PR #101, merge `044ed738ec6030b3195f4e3d30ccdc32607554b0`

## Interdictions
- Ne jamais annoncer une mutation comme acquise tant qu'elle n'est pas visible sur `main`.
- Ne jamais continuer sur un autre CPO lorsqu'une décision sûre du run courant reste non persistée.
- Ne jamais utiliser `tesla-stations-updater-test` comme destination d'écriture France.
- Ne jamais forcer `main` si une fusion PR propre est disponible.

Cette procédure est la voie de secours standard pour les futurs blocages du connecteur GitHub.
