# Rapport d'application — QSC EuroMillions v3.9 (audit du moteur)

> ⚠️ Claude ne prédit pas les tirages. Le hasard est sans mémoire. Aucune analyse ne garantit un gain. EV nette structurellement négative (~−1,42 €/grille). Les edges backtestés et percentiles Monte-Carlo peuvent être du bruit statistique — méthodologie documentée, pas un oracle.

Chantier du 12/10/2026. Objet : audit du moteur de génération de grilles v3.8 et correction du seul levier qui compte, le modèle de popularité.

## Ce que l'audit confirme

- **La mesure est juste.** Six selectors, walk-forward step 1, null hypergéométrique exacte, max-statistic : p global 0,70, stable depuis des mois. Le cumul du registre (11 numéros trouvés sur 25 grilles, attendu 12,5) est dans l'intervalle du hasard. Rien à changer côté backtest.
- **La v3.8 a eu raison** de retirer les modèles du pilotage de la sélection et de les reléguer au départage.
- **Le code est propre** : déterministe (seed = date du tirage), idempotent (garde du workflow, registre append-only), testé (75 tests), checklist anti-lexique.

## Ce que l'audit invalide

Le levier anti-partage reposait sur un proxy UK Lotto (Baker & McHale) jamais confronté à EuroMillions. Or l'API fournit, pour chaque tirage, le nombre de gagnants par rang sur le pool européen — exactement la population avec laquelle un gain est partagé. Le ratio (gagnants à 3 numéros) / (gagnants à 2 numéros) élimine le volume de ventes inconnu et ne dépend que de la popularité des cinq numéros tirés. Régression sur 1 608 tirages (2011→2026), même construction pour les étoiles (2 étoiles / 1 étoile, 1 046 tirages depuis le pool 12) :

| | Proxy UK (v3.6-v3.8) | Estimé sur les gagnants (v3.9) |
|---|---|---|
| Sens | 1-31 populaires, 32-50 impopulaires | **confirmé**, corr. 0,88 ; stable dans le temps (corr. 0,94 entre 2011-18 et 2019-26) |
| Amplitude numéros (ρ min → max) | 0,54 → 1,68 | **0,83 → 1,18** |
| Tranche 41-50 | ×0,54 | ×0,87 |
| Tranche 1-12 | ×1,39 | ×1,09 |
| Étoiles les moins jouées | 8-12 (toutes à ×0,77) | **12 (×0,73), 10 (×0,84), 11 (×0,86), 1 (×0,95)** — 8 et 9 sont en fait parmi les plus jouées (×1,10, ×1,07) |
| Incertitude | — | ±0,014 par numéro, ±0,015 par étoile (effets à 5-10 σ) |

Conséquences concrètes sur les grilles v3.8 déjà jouées, réévaluées sous la table estimée :

- « joueurs attendus ×0,12 » affiché le 02/10 valait en réalité **×0,53 à ×0,80** ;
- deux grilles sur les huit dernières (étoiles 8-9 et 5-9) étaient **plus jouées que la moyenne** (×1,30 et ×1,37) tout en affichant un anti-partage « conforme » ;
- la grille la moins jouée possible vaut ×0,42 : le gain réel du levier est un facteur ~2 sur le partage, pas 8.

Troisième constat : **le départage par « porteur » recentre sur les numéros historiquement fréquents** (44 dans 15 des 25 dernières grilles, puis 50, 23, 29, 39). Co-occurrence et Momentum, les deux porteurs en rotation, sont des fonctions de la fréquence ; dans un univers dominé par 32-50 ils renvoient toujours la même famille de grilles. Ce n'est pas un biais de probabilité, mais les « numéros chauds » sont aussi ceux que jouent les suiveurs de statistiques — et la table estimée le voit : 44 (×0,93) et 50 (×0,89) sont plus joués que leurs voisins 46 et 48 (×0,83).

## Changements v3.9

| | v3.8 | v3.9 |
|---|---|---|
| **R7 Popularité** | proxy UK figé dans le code | estimée à chaque run sur `euromillions_PRIZES.csv` (`popularite.py`, stdlib, 0,1 s), repli proxy UK affiché si le fichier manque |
| **R8 Univers étoiles** | paires dans 8-12 codées en dur | quart le moins joué des 66 paires sous la table estimée (17 paires : 10-12, 11-12, 1-12, 10-11, 4-12…) |
| **R9 Anti-partage** | fonction affine du proxy, 0-100 | percentile d'impopularité parmi les C(50,5) grilles (100 = la moins jouée de toutes), moins pénalités de forme |
| Cartes de grille | percentile Monte-Carlo in-sample | retiré de la carte (R4 du rapport v3.8) ; reste dans le JSON et l'histogramme |
| `update_master.py` | importait `qsc_v37` | importe `qsc_v39`, alimente `euromillions_PRIZES.csv` (append-only) |
| Univers numéros, D1-D4, backtest, null, consensus, rotation, règle jackpot, registre | — | **inchangés** |

Effet sur le run du 13/10/2026 (seed 20261013, 1 987 tirages) : univers 188 228 grilles (seuil gp 0,941 vs 1,00) ; G1 01 29 36 37 44 ★02 12 (×0,56), G2 22 35 39 41 44 ★10 12 (×0,45). Tests : 93/93. Pipeline ~95 s. Checklist verte.

## Limites de l'estimation (à afficher, pas à cacher)

- Modèle au premier ordre : un effet par numéro, additif en log. Il ne voit pas les motifs (dates, suites, colonnes), d'où le maintien des pénalités de forme.
- La pente b → ρ est calibrée par simulation (tools/calibration_r7.py) ; l'ordre des numéros est exact, l'échelle à ±10 %.
- Pool européen, pas FDJ seule — mais c'est le pool européen qui partage les gains.

## Recommandations non appliquées (à décider)

1. **Départage aléatoire seedé dans l'univers** à la place des porteurs. Les porteurs n'ont pas de valeur mesurée et concentrent sur les numéros chauds. Un tirage uniforme dans l'univers (seed = date) garde la reproductibilité, diversifie les grilles et supprime la rotation narrative, le classement et la consensus (qui dégénère depuis sa création). Le backtest resterait un diagnostic affiché.
2. **Registre en euros (R5)** : les gagnants et gains par rang sont maintenant dans le dépôt ; coût réel du protocole = mises − gains, plutôt que numéros trouvés.
3. **Une grille par défaut** : la règle `2 + ⌊(jackpot − 50)/50⌋` double la mise sans changer l'espérance par grille ; l'EV ne devient positive qu'au-delà de ~200 M€ et encore, hors partage.

> ⚠️ Claude ne prédit pas les tirages. Le hasard est sans mémoire. Aucune analyse ne garantit un gain. EV nette structurellement négative (~−1,42 €/grille). Les edges backtestés et percentiles Monte-Carlo peuvent être du bruit statistique — méthodologie documentée, pas un oracle.
