## 14 novembre — Allego UK transmis, Source EV isolé sans inventer de prix

Run43591511750 : Allego UK réussi, reçu SHA/manifeste/fichiers vérifié ; Source EV échoué sur la ligne54 de l’audit historique (écart à la référence PAYG), pas un secret manquant. Actions refermé, zéro workflow actif, main inchangé.17handoffs prouvés,118ouverts ; G2–G8 restent FAIL. Le brut de l’échec n’était pas conservé, donc aucun nouveau montant fournisseur n’est déclaré connu/valide.

Correction commune : les offres Source EV non démontrées sont gardées brutes avec motif et références exactes ; la normalisation PCPR accepte désormais des prises non tarifables sans rejeter tout leur catalogue. Aucun tarif hors preuve n’entre dans le moteur ; audit historique conservé intact. Les sorties PCPR échouées sont mises en quarantaine hors objets/last-good.41tests ciblés PASS ; test moteur Production des offres retenues/incalculables PASS. Le nouvel essai Source EV reste à faire après expiration du quota horaire de l’exécution11:45UTC (pas avant12:46UTC), sans appeler le fournisseur pour rechercher un prix.

Allego UK réellement normalisé/importé en espace isolé : bundle b6ea9d13f160eaaf4abdd7a7ec4b151e588c5073e18ad1bc36bce3528aeced0e ; jamais encore servi dans le brouillon courant. Les variations d’identités/offres sont diagnostiques, aucun seuil de volume.

Le brouillon6af8470ab1f6ac03083a27f4 est maintenant entièrement vérifié à distance :3245fragments SHA, ressources critiques dont11.7Mo,20parcours,11recherches/neufpays etcontrôlesG9mobilePASS. Ancienbrouillonconservé/rollbackvérifié,publicinchangé. Preuves détaillées Production docs/v9-rebuild/evidence/restoration-20261114/national-renewal. Il reste partiel : pas de cadence,118transferts ouverts, latenceAmsterdam66.7s etexceptions fournisseurs.

Prochaine opération : poursuivre les familles PCPR Blink/GRIDSERVE avec secrets existants nommés, préflight sécurisé, pilote borné et fermeture Actions ; vérifier puis importer leurs artefacts. Préserver les brouillons et bundles, regrouper les prochains renouvellements avant tout nouveau déploiement. Ubitricity UK reste attente fournisseur ; REVE utilise MAPA_REVE_API_KEY ; Atlante bootstrap historique déjà prouvé, aucune nouvelle demande d’accès.


Preuves : allego-uk-handoff.json, source-ev-failure.json, uk-pcpr-control.json, uk-allego-canonical-delta.json, uk-allego-production-import.json. Les entrées synthétiques des tests ne sont pas des prix fournisseur.

Allego UK renouvelé :238offres brutes conservées,238prises sans puissance exploitable dans la réponse (max_electric_power=0), donc aucune comparaison chiffrée restaurée par ce renouvellement. Ne pas inférer une puissance depuis tension×ampérage. Le raccordement Production des éléments OCPI sans restriction/date est corrigé et testé par parité avec le convertisseur historique, mais ne résout pas cette absence fournisseur.
