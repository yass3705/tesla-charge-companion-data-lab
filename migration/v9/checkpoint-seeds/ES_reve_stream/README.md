# REVE : checkpoint partiel, jamais un snapshot publiable

Acquisition réelle bornée42123311317, branche rebuild/v9-20261020, HEADbf958eecbfa3e86caed42e55d39362f401e05dcb. Artefact13459572404 ; ZIP SHA f45d3beb868c50bf1fd8f58e81d0e04f4679aa941400a37dcb733be3513d858f. Vérification complète : docs/v9-rebuild/evidence/emsp-restoration-20261105/reve-partial-resume.json.

Les cinq réponsesHTTP200 ajoutent les pages tarifs37–39 et statuts25–26, sans perdre les lignes antérieures. Le checkpoint conserve quotaUntil/Retry-After ; ne pas le réinitialiser pour consommer davantage de quota. Les pages anciennes restent anciennes : ce fichier n’est pas une acquisition complète fraîche.

Seed utilisé uniquement lorsqu’aucun checkpoint d’exécution restauré n’existe. Le manifeste SHA est contrôlé ; toute corruption bloque, aucun retour silencieux àpage1. Les archives du20octobre restent intactes. Aucune donnée de ce checkpoint ne doit être normalisée/publiée tant que les deux flux ne sont pas techniquement complets. Aucun secret ni paquet d’application n’est inclus.
