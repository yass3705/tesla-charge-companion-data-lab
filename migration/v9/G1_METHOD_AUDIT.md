# G1 — audit technique des méthodes existantes

État au 20 octobre 2026. Cet audit lit uniquement le dépôt et ses données historiques. Il ne vérifie aucun nouveau prix ni endpoint fournisseur.

## Inventaire reproductible

`python3 scripts/v9_rebuild_inventory.py --output migration/v9/legacy-inventory.json` produit un registre statique de 1 207 workflows et 756 fichiers historiques dans `scripts/` ; les outils créés pour cette reconstruction sont exclus du décompte. Il conserve, pour chaque YAML, les scripts nommés, les noms de secrets, les chemins de données explicites et les événements déclencheurs. Les valeurs de secrets ne sont jamais extraites. Parmi les 756 scripts, 43 ne sont pas cités littéralement par un YAML ; cela n'établit pas qu'ils sont inutiles. Plusieurs portent des méthodes ou contrôles directs, notamment GeniePoint UK, Lidl UK, Ze-Watt et Zephyre. Ils restent dans la revue G1.

`python3 scripts/v9_scheduled_methods.py --output migration/v9/scheduled-methods.json` produit la matrice des 117 workflows planifiés. Chaque ligne garde les commandes exactes détectées, les scripts, les secrets nommés, les chemins de fichiers et la portée. Le contrôle exige 117/117 lignes avec au moins une commande. Les 117 méthodes ont une **destination proposée** répartie sur 76 modules logiciels candidats, en regroupant les workflows d'un même fournisseur. `destination_module` reste vide tant que la méthode et ses sorties n'ont pas été qualifiées ; ces chemins proposés ne prouvent pas la migration. Trois YAML n'ont aucun chemin de fichier littéral détecté ; l'un est le collecteur REVE, dont le répertoire est défini par `REVE_DATA_DIR=data/spain_reve/full_20261018` et `scripts/reve_es_stream_collect.py`. Les deux autres sont une maintenance Actions et une validation historique.

| Catégorie observable | Nombre | Conséquence pour la migration |
| --- | ---: | --- |
| Workflows planifiés | 117 | Revoir les commandes et sorties comme méthodes de collecte candidates. |
| Planifiés avec permission ou commande d'écriture | 115 | Aucun ne peut être réactivé tel quel pour la nouvelle architecture. |
| Déclenchés par `workflow_run` | 16 | Éliminer les chaînes indirectes de la nouvelle architecture. |
| Workflows sans pays unique déductible | 367 | Résoudre par les sources et sorties ; ne pas déduire un pays d'un seul nom de script partagé. |
| Planifiés sans pays unique déductible | 26 | Portée et rôle relus dans `scheduled-scope-review.json` ; certains sont transversaux ou multi-pays. |
| Planifiés sans référence `scripts/` ou `src/` détectée | 13 | Lire le YAML complet : commande inline ou binaire externe possible. |

Le champ `country_hint` est un indice, pas une provenance validée. Le champ `contains_write_command_or_permission` est conservateur : il détecte aussi une permission d'écriture sans commande de push. Le registre ne classe pas encore les méthodes comme utiles ou obsolètes et ne certifie pas G1.

Les 26 cas planifiés sans pays unique ont une portée documentée dans `scheduled-scope-review.json`. Le contrôle automatique exige l'égalité exacte entre cette liste et les 26 cas du registre. Les outils transversaux ont une portée vide plutôt qu'une attribution fictive aux neuf pays. `validate-v9-country-progress.yml` reste une **ancienne validation** comportant des constantes de volume ; elle ne doit pas être reprise dans les nouvelles portes.

Une branche Production locale distincte `rebuild/v9-20261020` a été créée au SHA distant `fba450da9092450fa7315d4c5b44e7e80394c8b4`, sans modifier la branche historique ni le site. `scripts/v9_production_consumers.py` a comparé les 1 469 chemins de fichiers détectés dans les YAML Data Lab à 176 fichiers de code/configuration Production : 80 chemins ont une référence littérale, et les 80 fichiers existent dans le `main` Data Lab examiné. La liste exacte est dans `production-consumers.json`. Les références dynamiques et les pins historiques ne sont pas prouvés par ce test ; un chemin cité dans un test n'est pas forcément chargé par le runtime. La revue des méthodes doit donc suivre la chaîne de build réelle avant de classer une source comme non utilisée.

Parmi les 1 090 workflows sans `schedule`, 61 citent un de ces chemins référencés par Production. `scripts/v9_manual_consumer_priority.py` les extrait dans `production-linked-manual-workflows.json` pour une revue prioritaire ; aucun de ces 61 ne référence un script manquant. Les 1 029 autres ne sont **pas** classés inutiles : une sortie peut être résolue dynamiquement ou conservée dans un snapshot historique. Aucune suppression ne résulte de ce tri.

Le [registre central provisoire](source-registry.json), généré par `scripts/v9_source_registry.py`, associe les 117 planifiés, 61 manuels liés littéralement à Production et 43 scripts sans référence YAML, soit 221 méthodes prioritaires, à 108 modules candidats. Le contrôle exige une destination proposée pour chacun des 43 scripts isolés. Il regroupe les portées, noms de secrets et chemins connus. Les chemins de module sont des destinations **proposées** ; aucun module n'est encore déclaré migré. Les 1 029 autres workflows restent explicitement répertoriés dans `legacy-inventory.json` et attendent la revue de leur utilité. Le registre est un outil de conservation et de tri, pas une preuve de collecte ou de consommation Production.

## Contrat Ubitricity NL incomplet dans `main`

Le workflow planifié `ubitricity-nl-payg-refresh.yml` invoque deux fichiers absents : `scripts/audit_nl_ubitricity_payg_portal.py` et `scripts/reconcile_nl_ubitricity_payg_overlay.py`. `git log --all --full-history` et les autres arbres locaux consultés ne fournissent pas ces fichiers. Le commit de création `2930717c8` n'a ajouté que le YAML ; le commit `e166b409d` a ajouté le candidat et `scripts/integrate_ubitricity_nl_payg.py`, sans les deux extracteurs. Ainsi, le workflow hebdomadaire ne peut pas réussir depuis le `main` actuel. Il reste désactivé avec l'ensemble des Actions.

La méthode et la donnée validées ne sont pas perdues : le YAML conserve les commandes et paramètres, `dotnl_netherlands_build.py` et `integrate_ubitricity_nl_payg.py` compilent, et `data/operator_direct/ubitricity_nl_payg_exact_overlay_candidate.json.gz.b64` se décompresse et contient 3 tarifs et 3 670 correspondances exactes. Sa politique exige la source portail officiel, le canal Direct, les identités EVSE/connecteur exactes et exclut la préautorisation du prix. Cela prouve l'existence de l'artefact historique, **pas** la récupérabilité des deux extracteurs manquants ni la fraîcheur de ses montants.

Test technique lecture seule : `python3 scripts/integrate_ubitricity_nl_payg.py --no-write` sur le `normalized.json.gz` et le candidat du `main` actuel a réussi (`status=validated_no_write`, 3 670 correspondances exactes promues en mémoire, 0 rejet, 4 lignes source ambiguës exclues, 3 grilles). Ce test confirme le fonctionnement de l'intégrateur sur ces **entrées identiques** ; il n'établit ni un nouveau prix ni l'exécution du collecteur manquant. Aucun fichier de données n'a été modifié.

Destination proposée : conserver le candidat et l'intégrateur dans le futur module `cpo/ubitricity`, méthode `nl_payg` ; laisser l'étape d'acquisition désactivée jusqu'à récupération du code exact depuis une source historique approuvée ou reconstruction technique à partir des preuves déjà validées. Ne pas lancer de nouvelle investigation tarifaire.

## Étape suivante

Compléter les lignes des 117 workflows planifiés en reliant commande exacte, dépendances, secret nommé, sortie et source métier. Puis examiner les workflows manuels par familles pour préserver les méthodes utiles, affecter un module ou classer explicitement la référence comme expérimentale, redondante ou obsolète. G1 ne passe qu'après ce contrôle et la résolution des scripts manquants essentiels.
