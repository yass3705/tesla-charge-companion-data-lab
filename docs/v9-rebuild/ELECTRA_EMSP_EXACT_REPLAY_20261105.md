# Reprise Electra eMSP sur preuves historiques

Extraction conservée : `v9_rebuild/electra_france.py`, méthode `FR:electra_platform`. Le nouveau constructeur `scripts/build_v9_electra_proved_canonical.py` relit exclusivement les archives locales `data/platforms/electra/france/{manifest.json,source-locations.json.gz}`, le registre `verified-app-evse-tariff-map.json` et le national canonique épinglé. Il ne fait aucune requête fournisseur.

Le collecteur historique `scripts/electra_france_platform_snapshot.mjs` utilise déjà `norm()` pour comparer les identifiants EVSE. Le dérivé V9 avait perdu cette transformation et ses cinq captures étaient considérées sans correspondance. Le replay vérifie l’unicité après cette même transformation, la localisation source, le tarif identifié et la preuve capture. L’identifiant EVSE national reste exactement celui de l’IRVE ; l’identifiant source étoilé reste séparé dans `sourceEvseId`. Aucune identité physique ni station nouvelle n’est construite.

Source canonique dérivée : `FR:electra_emsp_exact`, destination moteur Production `provedElectraOffer`, canal exclusivement Electra roaming. Cinq offres présentes dans les archives sont conservées brutes. Production ne les rend calculables que si le tarif source complet comporte ENERGY seul, sans restriction ni composante supplémentaire, avec devise EUR et montant strictement identique à la preuve historique. Les autres cas restent bruts. Le prix de Fécamp n’est pas attribué.

Contrôles : manifeste/source SHA, compte interne de localisations, preuve SHA capture, échec sur ambiguïté ou localisation différente, schéma canonique, identités/portées, mutations de frais/restriction/montant/identité. Les 31 sources du candidat précédent restent à SHA identiques ; le bundle dérivé ajoute cette seule source sans changer l’archive de référence.

Exécution reproductible depuis Data Lab :

```sh
python3 scripts/build_v9_electra_proved_canonical.py --national <bundle31>/FR__irve_static.json --archive data/platforms/electra/france --ledger data/platforms/electra/verified-app-evse-tariff-map.json --out <nouveau-dossier>/FR__electra_emsp_exact.json
python3 -m unittest discover -s tests -p 'test_v9_electra_proved_canonical.py'
```

Le fichier de sortie doit être nouveau et hors checkout. Le snapshot préparé via `v9_rebuild.snapshot.prepare` est ensuite vérifié/importé par Production, qui réutilise seulement les fragments dont le SHA canonique est inchangé (`extend_v9_prepared_candidate.py`). Les checkpoints de collecte et les artefacts GitHub restent distincts de cette preuve locale d’intégration sur archives.
