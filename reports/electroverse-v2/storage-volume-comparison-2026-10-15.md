# Electroverse V2 — comparaison de volumes JSON hors ligne (15/10/2026)

## Méthode et statut
Lecture par connecteur GitHub de la fixture déjà versionnée `experiments/electroverse-v2/fixtures/archived-24.json` à la branche R&D. Calcul en mémoire, sans appel à Electroverse, sans exécuter le collecteur, sans écriture de cache. Groupement dans l'ordre de la fixture par lots de 5. Les résultats ci-dessous comptent des **caractères de chaînes JSON non indentées**, approximant des octets pour l'ASCII ; ce ne sont ni des bytes I/O effectivement écrits, ni un benchmark CPU/FS.

Fixture : 24 stations, 113 EVSE, 150 connecteurs, cinq lots [5,5,5,5,4], 176 182 caractères JSON en source.

Modèle de la V2 initiale : après chaque lot, sérialiser `{version:1,stations:state}` où `state` s'accumule, puis `{version:1,sourceHash:'placeholder',completed:[...PK]}`. Modèle journal : une seule sérialisation `{version:1,sourceHash:'placeholder',index,records:batch,hash:'placeholder'}` par lot. Les valeurs 'placeholder' sont plus courtes que les empreintes réelles ; les chiffres ne reproduisent donc pas exactement les octets de production.

| Indicateur | V2 état+checkpoint | V2 journal par lot |
|---|---:|---:|
| Nombre de lots | 5 | 5 |
| Sérialisations logiques | 10 | 5 |
| Longueur totale des JSON sérialisés | 623 765 caractères | 176 364 caractères |
| Écart de volume de sérialisation | — | −71,7 % |
| Facteur relatif | 3,54× | 1× |

**Portée du résultat :** ces volumes sont calculés effectivement sur l'archive de 24 stations, mais le fonctionnement réel de `journal_runner.mjs`, la latence I/O, les coûts fsync, les performances CPU et les ressources GitHub Actions **ne sont pas mesurés**. En particulier, les empreintes SHA-256, métadonnées et divers espaces/indentations peuvent affecter les octets réels.

## Validation et limites
- L'identité du corpus (24 stations / 113 EVSE / 150 connecteurs) a été confirmée depuis les enregistrements JSON archivés.
- Les nouvelles suites Node `generation_store.test.mjs` et `journal_runner.test.mjs` **ne sont pas vérifiées par une exécution du checkout** dans cette passe ; l'environnement local n'a pas de résolution DNS GitHub. Ne pas en déduire une CI verte ni un test complet validé.
- Aucun benchmark national ou de planification réelle. L'effet des réponses incomplètes et des reprises réelles nécessite une exécution complète des tests.
- La sécurité contre panne machine n'est pas démontrée par rename atomique seul : la durabilité et la concurrence doivent être étudiées avant toute généralisation.

**Décision :** conserver V1 intégralement. Le modèle journal est une piste prometteuse pour réduire l'amplification des écritures, à valider sur Node et corpus élargi. Aucun changement du processus existant.
