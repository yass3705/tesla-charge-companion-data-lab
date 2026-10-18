> **Rectification du 18/10/2026 :** les seuils ou non-baisses de couverture décrits pour ce run historique ne bloquent plus les lots futurs à eux seuls. Voir la [politique universelle](CPO_DYNAMIC_COVERAGE_POLICY.md). Les preuves du run original sont conservées.

# Zephyre France : collecteur ePowerDirect

Les scripts publics d'extraction et de compilation Zephyre, ainsi que le
dernier snapshot validé, proviennent de Stable au commit
`2c41dd6817b93ed1a3cabb77423b8b8716f92f2a`. La graine du 15 octobre
contient 140 EVSE directs dans 17 profils compilés. Les identités EVSE et les
règles tarifaires sont copiées sans transformation métier.

Data Lab devient propriétaire du rafraîchissement quotidien à 04:17 UTC.
Le workflow vérifie la couverture IRVE et ePowerDirect, la présence des tarifs
et du paiement direct, l'identité exacte des EVSE et la compilation avant de
commiter une nouvelle génération. Une erreur de source ou une baisse de
couverture laisse les fichiers validés en place ; le workflow peut alors
échouer sans perdre la graine. Les prix individuels ne sont pas rapprochés
pour décider du transfert.

Production doit encore lire cette offre depuis un SHA Data Lab immuable avant
le retrait du cron Zephyre Stable. Le workflow Stable et ses données restent
utilisables manuellement pour le rollback tant que ce consommateur n'est pas
validé.
