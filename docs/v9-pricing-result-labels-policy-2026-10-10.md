# TCC V9 — libellés des résultats tarifaires (décision du 10 octobre 2026)

## Règle de présentation

- **Tarif ambigu** : au moins deux offres pour le même EVSE / connecteur, le même usage et le même instant, avec composantes incompatibles et aucune preuve suffisante pour départager. Ne sélectionner aucun montant arbitraire et ne pas afficher de coût numérique calculé à partir d'un des candidats.
- **Tarif incalculable** : une offre déterminée existe, mais les variables ou règles nécessaires à son calcul sont inconnues ou non prises en charge. Aucune estimation prétendument précise.
- **Tarif indisponible** : aucune offre tarifaire exploitable n'est identifiée pour cette borne (l'absence de couverture n'est pas une ambiguïté).
- **Tarif calculé** : toutes les composantes applicables et leur fenêtre d'application sont déterminées pour le scénario, sans conflit non résolu.

La classification est **par EVSE/prise et par offre**, non par station entière : ne pas masquer les prises ou offres sans conflit.
Ne pas qualifier « tarif ambigu » un frais d'inactivité simplement parce que sa règle de déclenchement est inconnue pour une offre univoque : dans ce cas il est « incalculable ».
Ne pas publier le prix d'un enregistrement alternatif d'un même EVSE pour contourner une ambiguïté.

## Cas à reproduire

**Métropolis, Bry-sur-Marne Pasteur, borne P1** `FR*MGP*E94015*A*B1*P1` Type 2, 22 kW, offre Electroverse :
- Capture application à 12:57 : énergie 0,53 €/kWh + « frais d'inactivité de l'opérateur » 0,08 €/min, condition temporelle non visible.
- Capture application à 12:58 : énergie 0,53 €/kWh et, après 10 min, « frais d'inactivité de l'opérateur » 0,10 €/min.
- Audit source : `reports/electroverse/irve-tariff-conflicts-triage-2026-10-10.json` identifie déjà deux entrées contradictoires (0,53 €/kWh seul / 0,53 €/kWh + 0,08 €/min).

**Statut de l'offre Electroverse P1 : « Tarif ambigu »** tant que l'identification de la fiche source courante, le contexte d'affichage et la règle d'inactivité ne sont pas établis. Le montant total de cette offre ne doit pas être calculé à partir d'une des fiches seulement.

Preuve : `reports/electroverse/manual-evidence-bry-sur-marne-pasteur-p1-2026-10-10.md`.

## Acceptation

1. Cas ci-dessus : libellé exact « Tarif ambigu » (pas « indisponible » ni prix inventé).
2. Offre unique à durée manquante : « Tarif incalculable ».
3. Aucune offre : « Tarif indisponible ».
4. Une autre offre indépendante, validée et exploitable pour la même borne continue à être calculée/affichée.
5. Les filtres, classements et comparaisons n'utilisent pas un montant des offres « ambigu » ou « incalculable ».

**État :** règle de produit documentée. Le déploiement dans le moteur / UI V9 nécessite un changement testé dans le code et la publication de l'artefact de production ; cette fiche ne constitue pas une preuve de déploiement.

## Extension à tous les cas Electroverse identifiés — confirmation utilisateur du 10 octobre 2026

L'utilisateur signale **le même constat d'affichages contradictoires dans Electroverse pour tous les autres cas précédemment cités**. En conséquence, les **27 identifiants signalés** dans l'audit Electroverse passent, à titre conservatoire, sous le libellé **« Tarif ambigu »** tant que la fiche tarifaire applicable ne peut être départagée.

- **Ne pas calculer ni afficher un prix dérivé d'une variante choisie arbitrairement**, et **ne pas remplacer par « Tarif indisponible »**.
- Garder le diagnostic source initial : 14 conflits de composants à puissance identique, 8 candidats à correspondance unique en puissance mais prix divergents, 5 cas sans puissance exacte ; **parmi ces 5, quatre ont des prix identiques dans le snapshot brut et constituent d'abord un défaut de correspondance**, malgré le signalement utilisateur. Ne pas écrire dans l'audit de provenance que ces quatre divergences chiffrées ont été observées.
- Le seul dossier documenté avec deux captures et conditions précises reste **Bry-sur-Marne Pasteur P1** ; les autres sont des signalements utilisateur sans justificatif individuel, à examiner avant levée du gel.
- Cette règle affecte uniquement **l'offre Electroverse de l'EVSE concerné**, et non une offre CPO directe indépendante et validée.

Table exhaustive machine-readable : `reports/electroverse/ambiguity-disposition-user-confirmed-2026-10-10.json`.

**Attention :** cette extension documente la décision métier, sans garantir son application immédiate dans le rendu de la V9 déployée.
