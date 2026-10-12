# Audit du moteur de sélection et rapport d'application — QSC EuroMillions v3.9

> ⚠️ Claude ne prédit pas les tirages. Le hasard est sans mémoire. Aucune analyse ne garantit un gain. EV nette structurellement négative (~−1,42 €/grille). Les edges backtestés et percentiles Monte-Carlo peuvent être du bruit statistique — méthodologie documentée, pas un oracle.

Audit du 12/10/2026, à la demande de Charles : « le moteur de génération de grilles est-il toujours optimisé, y a-t-il des choses à refaire ? ». Périmètre : `qsc_v38.py`, `run_qsc.py`, `update_master.py`, le workflow, le registre (27 grilles, 25 rapprochées) et l'historique `output/history/`.

## 1. Verdict d'ensemble

Le moteur est **sain sur ce qui peut l'être** : le backtest est correct (walk-forward step 1, null hypergéométrique exacte, max-statistic sur 6 modèles), il conclut honnêtement que les six selectors sont indiscernables du hasard (p global 0,70, stable depuis des mois), la consensus dégénère volontairement, le registre est append-only et rapproché. Le cumul protocole-vs-hasard est à 11 numéros trouvés pour 12,5 attendus sur 25 grilles : exactement ce qu'on attend d'un tirage sans mémoire.

Le seul levier qui ait une valeur dans ce jeu est le **partage** (tous les rangs sont pari-mutuel, pas seulement le jackpot) : jouer des combinaisons que les autres jouent peu. La v3.8 a eu raison de faire de ce levier le critère principal. Mais elle l'alimentait avec un modèle de popularité **jamais mesuré** : quatre bandes de prix (1,55 / 1,30 / 0,80 / 0,62) empruntées au Lotto UK des années 2000. C'était la pièce la plus fragile du protocole, et le rapport v3.8 le disait lui-même (R7, « non fait »).

**Ce que l'audit a fait : mesurer la popularité réelle, et constater que le proxy UK se trompait, en amplitude et par endroits en direction.**

## 2. Mesure : la popularité des numéros d'après les gagnants par rang (D5)

L'API fournit, pour chaque tirage, le nombre de gagnants à chaque rang (totaux européens, ce qui est la bonne population : les rangs sont partagés au niveau européen). Conditionnellement au tirage, le nombre de tickets ayant exactement *k* numéros exacts vaut

    W_k ≈ T · q_k · moyenne_{A ⊂ tirage, |A|=k} Π_{n∈A} w_n

avec *T* le nombre de tickets (nuisance, éliminée en forme close), *q_k* la probabilité hypergéométrique et *w_n* la popularité relative du numéro *n* (moyenne 1). Ajustement par moindres carrés sur *k* = 2, 3, 4, 1 046 tirages de l'ère 12 étoiles (27/09/2016 → 06/10/2026). Même logique pour les étoiles sur les fractions 0/1/2 étoiles. Script : `fit_popularity.py` (~1 s sans l'API, ~2 min avec).

Qualité : rms des log-résidus 0,049 contre 0,067 avec des popularités uniformes ; **corrélation 0,92 entre les tables ajustées sur chaque moitié de l'historique** (la table est stable, ce n'est pas du bruit). Étoiles : 0,074 contre 0,135.

| | Proxy UK (v3.8) | Mesure (v3.9) |
|---|---|---|
| Étalement numéros | ×0,54 à ×1,69 (facteur 3,1) | **×0,79 (46) à ×1,27 (7)** (facteur 1,6) |
| Bande 1-12 | ×1,39 | ×1,10 — et **le 1 est sous la moyenne (0,94)** |
| Bande 13-31 | ×1,14 | ×1,08 — mais 29, 30, 31 sous la moyenne |
| Bande 32-40 | ×0,70 | ×0,89 |
| Bande 41-50 | ×0,54 | ×0,83 |
| Top populaires | 7, 3, bande 1-12 | **7, 17, 12, 13, 11, 19, 23, 27, 5, 14** |
| Moins populaires | 41-50 hors 42/49 | **46, 49, 50, 48, 40, 36, 47, 41, 45, 34** |
| Étoiles | ≤ 7 populaires, 8-12 impopulaires | **10, 11, 12 (et 1) impopulaires ; 7, 5, 3 populaires ; 8 et 9 sont dans la moyenne** |

Conséquence directe : les « joueurs attendus ×0,06 à ×0,16 » affichés par la v3.8 étaient **5 à 10 fois trop flatteurs**. Les mêmes grilles, recalculées sur la table mesurée : ×0,47 à ×0,67. Une grille v3.7 réputée impopulaire (13-16-22-33-44 ★8-9, ×0,32 selon le proxy) était en réalité **plus jouée que la moyenne** (×1,36) : 13, 16, 22 et l'étoile 8-9 ne sont pas les numéros délaissés que le proxy supposait.

## 3. Changements appliqués (v3.9)

| | v3.8 | v3.9 |
|---|---|---|
| **D5 Popularité** | proxy UK, bandes fixes | `popularity_fdj.json`, table calibrée sur les gagnants par rang ; recalibrage le 1er du mois (`refit-popularity.yml`) ; proxy UK en secours si le fichier manque (`POP_SOURCE` l'affiche) |
| **D6 Score anti-partage** | échelle affine attachée au proxy | percentile : « plus impopulaire que X % des 2 118 760 grilles », moins pénalités de forme — lisible, comparable d'un run à l'autre |
| **D7 Univers étoiles** | paires dans 8-12 (artefact du proxy) | le quart le moins joué des 66 paires (16 paires), d'après la table |
| **R4 Monte-Carlo** | percentile sur chaque carte + histogramme | retiré (mesure in-sample, flatteuse par construction) ; pipeline 75 s → 30 s |
| Univers numéros (D1), pénalités de forme (D2), étoiles par ère (D3), co-gagnants normalisés (D4) | — | inchangés, mais calculés sur la table mesurée |
| Backtest, null, max-stat, consensus, rotation, règle jackpot, registre | — | **inchangés** |

Univers v3.9 : 188 245 grilles (décile le moins joué, popularité géométrique ≤ 0,921), tête de liste 36-40-46-49-50. Tests : 89/89 (`test_qsc_v39.py`). Run à blanc du 13/10/2026 : checklist verte, G1 01-29-37-42-44 ★02-12 (×0,50), G2 22-35-41-44-49 ★10-12 (×0,36).

## 4. Ce que ça vaut, en euros — pour ne pas se raconter d'histoires

Le levier anti-partage est réel mais **petit**. Espérance de la part jackpot d'une grille, à 25 M de tickets :

| Jackpot | grille moyenne | grille v3.9 (×0,5) | grille la moins jouée (×0,33) |
|---|---|---|---|
| 17 M€ | 0,103 € | 0,111 € | 0,115 € |
| 100 M€ | 0,539 € | 0,606 € | 0,645 € |
| 200 M€ | 0,950 € | 1,119 € | 1,226 € |

Soit **+1 à +17 centimes par grille** selon le jackpot, pour un ticket à 2,50 €. Les rangs inférieurs, pari-mutuel aussi, ajoutent un gain du même ordre. Le protocole fait donc ce qu'il peut faire, et rien de plus : l'espérance reste négative à tout jackpot réaliste.

## 5. Ce que l'audit n'a pas changé, et pourquoi

- **Les six selectors** (fréquence, lag, fenêtres, momentum, co-occurrence, Markov). Ils ne prédisent rien et le backtest le prouve ; les garder comme départage est inoffensif, et la rotation narrative aussi. Les supprimer ne gagnerait que du temps de calcul. Effet visible : le 44 est dans 15 des 27 grilles du registre (12 des 14 dernières), parce qu'il est sorti souvent récemment et que co-occurrence/momentum le favorisent. Ni bon ni mauvais : il n'est pas plus probable qu'un autre, et il est peu joué (×0,88).
- **La règle jackpot du nombre de grilles** (2 + ⌊(J−50)/50⌋). Charles s'interroge sur passer à 1 grille par défaut. L'audit va dans ce sens : l'espérance par grille étant négative à tout jackpot, chaque grille supplémentaire coûte en moyenne ~1,25 € ; le jackpot est une raison de jouer *ou pas*, pas de jouer *plus*. Non modifié, décision de Charles (le plancher `n_grilles` reste disponible).
- **Le cumul protocole-vs-hasard en numéros trouvés.** Il mesure la bonne chose (rien à voir, et rien n'est vu). Le passer en euros (R5) resterait utile pour mesurer le partage réel, mais avec 2 grilles par tirage il faudra des années pour que ce soit lisible.

## 6. Limites de la table calibrée

- Le modèle multiplicatif suppose que les joueurs choisissent leurs numéros indépendamment les uns des autres ; les motifs (dates, colonnes, suites) ne sont capturés que par les pénalités de forme, pas par la table.
- La table est européenne, pas française. C'est la bonne population pour le partage, mais une spécificité FDJ (numéros Flash, jeux multiples) n'y est pas isolée.
- 46 et 50 à ×0,79-0,81 : des numéros « impopulaires » peuvent redevenir populaires si beaucoup de joueurs suivent le même conseil. Le recalibrage mensuel sert à ça.

> ⚠️ Claude ne prédit pas les tirages. Le hasard est sans mémoire. Aucune analyse ne garantit un gain. EV nette structurellement négative (~−1,42 €/grille). Les edges backtestés et percentiles Monte-Carlo peuvent être du bruit statistique — méthodologie documentée, pas un oracle.
