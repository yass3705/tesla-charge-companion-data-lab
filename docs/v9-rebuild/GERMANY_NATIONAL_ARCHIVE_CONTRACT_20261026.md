# Contrat G3 — archive nationale allemande

Source canonique `DE:bnetza_afir_archive`, depuis `data/national/germany_non_tesla_catalog_staging_direct_cpo.json.gz` (schéma historique 0.6.0). La route conserve les sites BNetzA et leurs identifiants EVSE publiés, les coordonnées, l’opérateur exact, l’adresse et tous les champs bruts. L’enveloppe source, ses décisions d’exclusion historiques et les références AFIR sont préservées. Aucun nouveau filtre de performance n’est appliqué.

La clé technique d’EVSE inclut le site source : un identifiant répété sur deux sites ne fusionne pas implicitement leurs stations. Les références nationales et AFIR non rapprochées restent dans le brut ; aucun rapprochement GPS ni transfert de tarif n’est autorisé par ce normaliseur.

`maxConnectionPowerKw` et `declaredChargePoints` sont des agrégats de site. Ils ne créent ni prises, ni puissances EVSE, ni faux identifiants physiques. Les identifiants EVSE présents sont conservés sans les modifier. Les détails AFIR et CPO, les tarifs et les statuts historiques sont conservés dans `rawSourceFields`, sans inventer un statut live. Cette première route n’émet aucun connecteur ni offre tarifaire canonique : leur portée exacte reste un travail G3/G5 distinct, et aucun tarif de staging n’est promu. Une absence de topologie ou de tarif ne supprime aucune station.

Cinq tests passent, dont le rejeu de l’archive complète : identité stable, entrée non mutée, mêmes IDs de sites, tous champs bruts conservés, zéro prix/puissance inféré. Les comptes internes sont comparés au contenu de cette archive, jamais à un seuil de volume historique. Cette preuve ne vaut ni recette de transfert GitHub, ni couverture complète G3/G5/G6. Aucun workflow, main ou site public modifié.
