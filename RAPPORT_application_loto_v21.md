# QSC Loto v2.1 — fiabilité du run (11/11/2026)

Alignement du Loto sur l'EuroMillions v4.1 (PR #7). La méthode ne change pas : tirage uniforme dans l'univers impopulaire, 1 grille, budget commun de 520 €.

Le Loto partait de plus haut que l'EuroMillions : ses données viennent de l'historique officiel FDJ, la lecture du jackpot vérifiait déjà la date du tirage, et un rang n'était déjà soldé qu'une fois son montant connu. Restaient les défauts de mécanique communs.

| # | Problème | Correctif |
|---|---|---|
| 1 | Dataset en retard jamais signalé | `dataset.retard_tirages` + alerte dans `dataset.alertes` |
| 2 | Jackpot estimé sur un tirage ancien | source « estimation périmée », `jackpot.fiable` |
| 3 | Premier run dégradé figé pour la journée | la garde laisse rejouer un run dégradé jusqu'à 10:00 UTC |
| 4 | Même seed, grille différente si les données bougent | les grilles déjà inscrites au registre pour le tirage sont figées |
| 5 | FDJ injoignable ou tirage manquant = aucune grille | la mise à jour du CSV n'est plus bloquante ; alerte dans le livrable |
| 6 | Gain soldé à un run ultérieur jamais annoncé | la ligne entre dans `registre.rapproche` au run où le rang est soldé |

Tests : 119 (110 existants + 9). Scénarios rejoués sur le tirage du 11/11/2026 : re-run à données identiques, re-run avec gagnants modifiés (grille conservée alors qu'un run neuf en aurait tiré une autre), run neuf (grille identique à la v2.0), samedi 14/11 avec FDJ en panne (grille livrée, retard signalé).
