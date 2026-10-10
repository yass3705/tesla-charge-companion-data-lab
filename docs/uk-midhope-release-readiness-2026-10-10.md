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

## Blocages de déploiement global non liés à Midhope

- Run preview global **38058077511 : échec** — source **Ubitricity UK** dépassant le seuil strict de 48 heures. **Ne pas contourner** sans réactualiser ou mettre la source non vérifiée en quarantaine.
- Run paquet V9 isolé **38058093523 : échec** — source **Blink UK** non conforme au croisement horodatage/source rapport de validation. **Ne pas forcer la publication** d'un snapshot dont les autres tarifs sont en écart.
- ChargePoint UK : `readyForTariffRanking=false`; la nouvelle construction le conserve inactif plutôt que de publier des tarifs ad hoc non confirmés.

## Statut

`ENGINE_AND_EXACT_CPO_SOURCE_VERIFIED__V9_UI_NOT_DEPLOYED`

La réussite des tests Midhope et la présence du code sur `main` ne prouvent **pas** la publication effective du snapshot V9 en production. Reprendre par la réconciliation des collectes Ubitricity/Blink, reconstruire le snapshot complet, vérifier la présence des quatre EVSE dans le registre/runtime navigateur, puis déployer.
