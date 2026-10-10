# TCC V9 — Extension ultérieure des overlays eMSP Electroverse et Electra (11/10/2026)

**Décision de périmètre utilisateur :** étendre les données tarifaires eMSP Electroverse et Electra aux pays de TCC, en les conservant séparées des tarifs directs CPO. Ce chantier **n'est pas une autorisation de substituer une offre eMSP à un tarif CPO direct non vérifié**.

- Pays de base de l'audit : FR, IT, CH, DE, ES, NL, UK, MA, BE ; prendre uniquement les pays effectivement couverts par chaque application au moment de la collecte (aucun tarif ni couverture présumés).
- Affichage cible dans V9 pour chaque combinaison EVSE + puissance : **Direct/CPO**, **Electra eMSP**, **Electroverse eMSP** ; valeurs absentes « prix non disponible », ambiguïtés vérifiées « tarif incalculable », pas de prix inventé.
- Tarif eMSP lié au connecteur/EVSE exact, sinon rapprochement GPS 5–10 m + puissance + opérateur lorsque univoque ; interdire tout prix moyen de station. Audit exact/synthétique par CPO, puissance, pays.
- Conditions tarifaires prises en compte : énergie, frais de session, temps, stationnement après charge, seuils, plage locale, TVA, plafonds, abonnement activé et préautorisation non comptée comme frais.
- Vérifier la prise en charge des pays, la monnaie locale et la contre-valeur € ; distinguer tarif eMSP courant, abonnement et tarifs CPO.
- Cycle d'intégration indépendant du CPO direct : collecte, statut de disponibilité exploitable (available/occupied), preuve tarifaire, identité EVSE, simulation déterministe, snapshot par pays et publication.
- Déploiement progressif après validation des sources : commencer par un inventaire du support pays des deux eMSP et de leurs méthodes existantes en FR et NL, puis étendre en gardant les pays non supportés vides.

**État au 11/10/2026 :** cible enregistrée, **aucune publication internationale supplémentaire prétendue**. L'analyse du direct CPO NL (Laadnet / Agri Go / StellaPower / WattHub) demeure prioritaire.
