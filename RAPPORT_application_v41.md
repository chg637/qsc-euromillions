# QSC EuroMillions v4.1 — fiabilité du run (revue du 11/11/2026)

La méthode ne change pas : tirage uniforme dans l'univers impopulaire, 1 grille puis +1 à 100, 150 et 200 M€, budget de 520 €. Cette version corrige la mécanique autour.

## Ce qui s'est passé le 10/11/2026

Le run de 04:11 UTC a publié 1 grille sur un jackpot « estimé » à 98,8 M€. Le jackpot officiel était de 141 M€ : la règle donnait 2 grilles. Trois causes empilées :

1. L'API n'avait pas encore le tirage du 06/11 ; l'estimation reprenait donc le jackpot du 03/11, deux tirages en arrière, sans le dire.
2. La lecture de fdj.fr reposait sur un texte (« NNN Millions d'euros à gagner ») que la page n'affiche plus pour l'EuroMillions.
3. La garde d'idempotence a arrêté les quatre créneaux suivants, puisque `latest.json` portait déjà la bonne date.

## Correctifs

| # | Problème | Correctif |
|---|---|---|
| 1 | Dataset en retard jamais signalé | `dataset.retard_tirages` + alerte dans `dataset.alertes` |
| 2 | Jackpot estimé sur un tirage ancien | source « estimation périmée », note explicite, `jackpot.fiable` |
| 3 | Lecture fdj.fr cassée | lecture du bloc de données EuroMillions (clé `megaJackpot`), date du tirage vérifiée, raison de l'échec écrite dans la note |
| 4 | Premier run dégradé figé pour la journée | la garde laisse rejouer un run dégradé jusqu'à 10:00 UTC |
| 5 | Même seed, grilles différentes si les données bougent | les grilles déjà inscrites au registre pour le tirage sont figées ; un re-run n'ajoute que le complément |
| 6 | API injoignable ou tirage sauté = aucune grille | la mise à jour du CSV n'est plus bloquante ; le run tourne sur le CSV existant et l'écrit en alerte |
| 7 | Gain dont le montant arrive après coup jamais annoncé | la ligne entre dans `registre.rapproche` au run où le rang est soldé ; un rang atteint sans montant n'est plus soldé à 0 € |
| 8 | Push en échec si le Loto a commité entre-temps | `git pull --rebase` avant le push |

## Non traité, à décider

- Le registre compte les grilles générées, pas les grilles réellement jouées (budget et cumul compris).
- Un créneau parti après 20h15 (fermeture des prises de jeu) génère encore la grille du jour.
- Le workflow Loto a la même garde et la même lecture fdj.fr : à aligner.

## Tests

118 tests (104 existants + 14). Scénarios rejoués : re-run du 10/11 avec 141 M€ et table de popularité modifiée (G1 conservée, G2 ajoutée) ; vendredi 13/11 avec API figée (alerte, estimation périmée, grille livrée) ; vendredi 13/11 avec CSV rattrapé (3 grilles rapprochées) ; run neuf du 10/11 (grille identique à la v4.0).
