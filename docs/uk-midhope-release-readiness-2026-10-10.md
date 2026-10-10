# TCC V9 — Midhope Road UK, état de publication au 10/10/2026

## Confirmé et prêt dans le code (ne pas confondre avec déploiement public)

- Source: quatre connecteurs exacts Connected Kerb, station `cd20ba89-4241-4b39-b738-514f49093e8d`.
- EVSE: `GB*CK0*E19825`, `GB*CK0*E19865`, `GB*CK0*E19716`, `GB*CK0*E19707`.
- Preuve client: captures app guest Connected Kerb IMG_8107 et IMG_8108, audit `reports/uk/connected-kerb-midhope-verified-2026-10-10.json`.
- Énergie: £0.39996/kWh source brut TTC, affichage £0.40/kWh.
- Stationnement: £0.80004 par tranche de 30 minutes entamée, = £1.60008/h TTC (affiché £1.60/h), du lundi au samedi 08:30–18:00 heure locale Europe/London. Le dimanche, stationnement gratuit.
- Inactivité séparée: £0.01/min pendant les minutes sans charge, y compris le dimanche. Stationnement continu sur le temps occupé, sans addition simultanée des composantes charging/idle de parking.
- Préautorisation: £25, n'entre pas dans le coût de charge.
- Toutes les règles EVSE exactes et TTC.
- Validité conservatrice: du 10/10/2026 au 24/10/2026 inclus. L'horaire d'hiver et la tarification ultérieure restent bloqués tant qu'ils ne sont pas observés directement.

## Tests

GitHub production: workflow `UK Midhope verified pricing and legacy regression`, run **38058077538: success**.

Vérifie quatre identifiants, tarif énergie, pas de facturation, préautorisation, 08:30/18:00, une seule occupation stationnement à la transition charging->idle, dimanche, garde hiver et non-régression OCPI. Source générée via Data Lab run **38057293313: success**.

Les offres sont désormais prévues dans le moteur et la source V9 construite, mais restent dépendantes d'un snapshot global validé avant visibilité dans l'interface publique.

## Validation et publication effective

- **Blink UK** : collecte PCPR du **2026-10-10T14:10:35Z**, audit indépendant `38058579417` réussi ; 869 stations / 3 599 connecteurs tarifés / 55 tarifs / 0 non tarifé.
- **Ubitricity UK** : exclu de la V9 tant que le support CPO n'a pas renvoyé un accès de collecte fonctionnel ; les anciennes données sont archivées mais la source runtime `uk-ubitricity-pcpr-payg` reste `active:false`.
- **ChargePoint UK** : `readyForTariffRanking:false`, tarifs encore hors classement faute de preuve directe PAYG/TVA.
- **Midhope Road** : quatre EVSE source `uk-connected-kerb-midhope-guest-verified` intégrés au snapshot V9 avec bornage temporel été validé (du 10 au 24 octobre inclus) ; période hivernale `tarif indisponible` jusqu'à nouvelle preuve.
- **Allemagne IONITY** : quatre sites isolés sans prix, contrôle de proximité et huit cas tiers exclus ; aucun tarif extrapolé.
- **Tests finaux** : snapshot construit, tests OCPI, tests UK, smoke multi-pays et scénario navigateur réussis.
- **GitHub Pages** : publication vérifiée par exécution `38059294144` (`build-deploy: success`, `deploy: success`), le 10/10/2026 à **14:23:35 UTC**.
- URL de la prévisualisation : https://yass3705.github.io/tesla-charge-companion-production/
- URL du run de publication : https://github.com/yass3705/tesla-charge-companion-production/actions/runs/38059294144

## Statut

`MIDHOPE_4_EVSE_BLINK_3599_PUBLISHED_TO_V9_PAGES__UBITRICITY_SUPPORT_HOLD`

Le workflow GitHub Pages confirme le déploiement. L'URL publique n'a pas été relue depuis cet environnement réseau après déploiement ; tests de navigateur sur artefact du workflow réussis. La réactivation Ubitricity nécessite des données fraîches et une validation explicite. L'heure d'hiver Midhope nécessite une nouvelle observation tarifaire client.


## 10 octobre 2026 — publication V9 finalement validée

- Production GitHub Pages **déployée** : [run 38059294144](https://github.com/yass3705/tesla-charge-companion-production/actions/runs/38059294144), étapes de build et de déploiement `success`.
- URL publique : https://yass3705.github.io/tesla-charge-companion-production/v9-production-shell/
- `shell-config.json` servi sur Pages : `snapshotId = 2026-10-10-r38059294144`.
- Registre `source-registry.json` relu directement depuis Pages après déploiement :
  - `uk-connected-kerb-midhope-guest-verified` **active=true, optional=false** : uniquement 4 EVSE/sockets exacts, tarifs invités validés en été ; garde hiver.
  - `uk-blink-pcpr-direct` **active=true, optional=false** : nouvelle collecte PCPR 2026-10-10T14:10:35Z, audit indépendant réussi, 869 stations publiques et 3 599 connecteurs tarifés / 55 tarifs.
  - `uk-ubitricity-pcpr-payg` **active=false, optional=true** : exclu provisoirement à la demande utilisateur en attendant la réponse du support (ancien fichier conservé à titre de preuve uniquement).
  - `uk-eco-movement-pcpr-cpo-direct` **active=false, optional=true** : attribution PAYG et TVA non encore prouvées.
- Toute mention plus haut d'une « V9 non déployée » ou de « blocages Ubitricity/Blink empêchant le déploiement » décrit l'état intermédiaire **avant** le run réussi 38059294144. Ce statut est remplacé par la présente vérification.
- L'interface GitHub Pages a été chargée et identifiée comme `Tesla Charge Companion V9`, avec le même ID de snapshot en ligne.
- La validité limitée au 24 octobre 2026 de Midhope n'est **pas** une validation hivernale. Les périodes ultérieures doivent rester non calculables tant que le CPO n'a pas fourni les horaires d'hiver.

## Rectification horaire — 10 octobre 2026

La capture fournie par l’utilisateur affiche les heures en **Europe/Paris** : **09:30–19:00** ; cela correspond à **08:30–18:00 Europe/London**, en été comme en hiver puisque France et Royaume-Uni passent aux mêmes dates à l’heure d’hiver. La date de fin `2026-10-24` était une précaution saisonnière injustifiée par la seule conversion horaire et doit être retirée du contrat de l'offre source et du moteur V9. Le moteur utilise les heures locales `Europe/London` (IANA) plutôt qu’une plage UTC figée. Maintenir la provenance du prix au 10/10/2026 ; vérifier les changements de conditions à la source indépendamment du changement d’heure. Ne jamais supposer de nouvelles composantes, ni doubler des frais de stationnement. Cette correction supplante les références ci-dessus à une garde hiver automatique.
