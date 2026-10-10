# Electroverse FR — vérification de la reconstruction nationale du 10 octobre 2026

## Verdict
**ÉCHEC / NON DÉPLOYÉ.** La validation ciblée de 28 stations / 133 références a réussi, mais la collecte des statuts à l'échelle nationale a échoué à deux reprises. Le dernier overlay Electroverse publié n'inclut pas le champ `statusGate` et conserve **89 991 offres**, générées le `2026-10-10T11:42:23.873Z`, **avant** application du filtre.

## Pièces
- Exécution collecte `38052991505` : échec. 22 818 stations demandées, **88 réussies**, **6 541 unités d'erreur** dans les logs et arrêt sans registre. Les erreurs majoritaires sont GraphQL `An error occurred.`, souvent sur des requêtes multi-emplacements.
- Exécution collecte `38053204710` : échec. **174 stations réussies**, **6 347 unités d'erreur** ; aucun `data/electroverse/live_statuses/manifest.json` publié.
- Exécution de l'overlay `38053326406` : workflow **success** sans construction ; log : `Status census not yet available — preserve current V9 overlay`, puis `No overlay changes`. Ne pas interpréter cette sortie comme une publication.
- `reports/electroverse/status-gate-postbuild.json` **absent** ; donc aucun test national final de l'éligibilité des sources EVSE.
- La nature des erreurs GraphQL est générique ; **surcharge / protection de débit possible mais non prouvée**. Le préflight de 16 emplacements seul ne suffit pas à valider un run national.

## Corrections introduites lors de la vérification
1. Le workflow de construction retourne désormais un **échec explicite** lorsqu'aucun registre national validé de statuts n'est disponible (au lieu de succès trompeur).
2. Le collecteur plafonne le budget d'erreurs, espace les requêtes et distingue **échoués / non interrogés**, afin de ne plus lancer des milliers d'appels voués à l'échec.
3. Les règles métier et le constructeur appliquent toujours le filtre strict `AVAILABLE` / `CHARGING` au PK source ; les autres statuts sont exclus **uniquement quand un inventaire complet, récent et vérifié est disponible**.

## Dossiers déjà vérifiés via l'API en direct
- Contrôle ciblé du 10 octobre : 31 conflits → 23 après retrait de 8 variantes sources non admissibles.
- 4 références à Saint-Affrique-les-Montagnes sont levées par le statut : offres `UNKNOWN` écartées et offre `AVAILABLE` avec frais après 4 h retenue pour analyse.
- Les **23 conflits résiduels** sont Métropolis (13), Chargezy (8), Beauvais (2) et restent `Tarif ambigu` tant qu'une preuve ne permet pas de départager les sources.
- Les **4 offres exactes Allego/Lidl**, les **60 correspondances parentes actives** et les **3 réutilisations actives** sont à poursuivre séparément.
- Ces chiffres ne constituent **pas** un résultat de déploiement national.

## Prochaine résolution technique
Tester les limitations réelles du backend Electroverse sur une petite plage (requêtes paginées / un emplacement à la fois, débit contraint, gestion des erreurs GraphQL), puis collecter les 22 818 stations de manière incrémentale et vérifiable avant toute nouvelle reconstruction. Tant qu'aucun registre national complet et fraîchement horodaté n'est disponible, **ne pas publier de nouveau tarif issu d'une source à statut indéterminé** et conserver l'overlay historique sans prétendre qu'il satisfait la nouvelle règle.

Liens vers les exécutions :
- https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/38052991505
- https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/38053204710
- https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/38053326406
