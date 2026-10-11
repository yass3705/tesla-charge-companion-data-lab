# Agri Go Charge — demande de flux tarifaire direct QR et identité EVSE (TCC)

Statut 11/10/2026 : **pas d'API tarifaire QR publique démontrée**. Le site officiel publie les catégories tarifaires TTC, la plupart des bornes proposent le paiement QR et le montant réel est affiché après scan ; ces trois faits ne donnent pas le prix TTC exact pour une borne individuelle.

Sources :
- https://agrigo.nl/charge/tarieven/
- https://agrigo.nl/charge/locaties/
- https://www.lastmilesolutions.com/legal/gtcfo/ (documentation du prestataire éventuel, **l'intégration Agri Go QR avec lui n'est pas prouvée**)

## Correspondances déjà auditées

- 927 stations / 2 578 connecteurs AGO issus du DOT-NL (10/10/2026).
- Carte publique officielle : 766 marqueurs exploitables.
- 158 rapprochements de station par GPS unique (10 m) **et concordance des mots de rue** : 346 connecteurs.
- 66 rapprochements GPS à moins de 10 m mais adresse non concordante : non validés.
- 189 proches de 10 à 30 m : non validés ; 1 station multi-candidate : ambiguë.
- 513 sans marqueur à 30 m.
- **0 offre de paiement QR réel récupérée ; 0 prix direct publié dans V9**.

Fichiers :
- reports/netherlands/nl-agrigo-qr-endpoint-discovery-2026-10-11.json
- reports/netherlands/nl-agrigo-embedded-map-probe-2026-10-11.json
- reports/netherlands/nl-agrigo-official-map-match-2026-10-11.csv

## Demande technique à adresser à l'opérateur (néerlandais)

Aan: info@agrigo.nl
Onderwerp: Agri Go Charge – openbaar ad-hoc QR-laadtarief per laadpunt (EVSE-ID)

Geachte Agri Go Charge,

Wij ontwikkelen een onafhankelijke vergelijking van directe, ad-hoc laadtarieven in Nederland. Het gaat uitsluitend om het tarief dat een particuliere bestuurder via uw QR-betaalpagina betaalt, **niet** om tarieven van externe laadpasaanbieders of roamingdiensten.

In de Nederlandse openbare laadpuntgegevens hebben wij circa 927 Agri Go Charge-locaties en 2.578 connectoren geïdentificeerd. Wij willen de actuele QR-prijs betrouwbaar aan het juiste laadpunt koppelen.

Kunt u aangeven of er een openbare, uitsluitend-lezen interface of datapublicatie beschikbaar is met:

1. De vaste structuur van de QR-betaallink of een voorbeeld van een **niet-sessiegebonden** laadpuntlink, met de mapping naar EVSE-ID (bijv. NL*AGO*E...) en connectornummer.
2. Het actuele ad-hoc kWh-tarief **inclusief btw**, per EVSE/connector en eventuele startkosten.
3. De tijd- of connectiekosten, de drempelduur, de toepasselijke lokale uren en de afrondings-/facturatiestappen.
4. Of en hoe prijswijzigingen en toegankelijkheid publiek worden aangeboden (feed/API/export en toegestane updatefrequentie).

Wij zullen geen laadsessies of betalingen automatiseren. Als er geen publieke API is, volstaat een voorbeeld van één echte QR-bestemmings-URL en documentatie over de tariefweergave om de technische haalbaarheid te testen.

Alvast hartelijk dank voor uw hulp.

Met vriendelijke groet,
Tesla Charge Companion

## Quarantine policy

- Tarif direct CPO = paiement ad hoc effectivement proposé par Agri Go à l'EVSE exact ; les prix par type de lieu (0,49/0,52/0,56/0,65 € TTC) sont **non affectés**, car la catégorie du QR n'est pas vérifiée.
- Frais de connexion officiels : AC parking public >4h dans la plage 08h00–22h, 0,73 €/h ; DC >1h, 1 €/min. Règle des tranches et heure locale à vérifier avant calcul définitif.
- Préautorisation 40–60 € : jamais une composante facturée.
- Interdire la substitution d'un tarif de carte Agri Go ou d'un fournisseur eMSP.
- Correspondance carte publique uniquement = **identité de station candidate**, jamais tarif EVSE vérifié.
