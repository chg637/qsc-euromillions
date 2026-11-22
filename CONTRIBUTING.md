# Contribuer au protocole QSC

Le dépôt porte deux jeux (EuroMillions et Loto) sur une même méthode : tirer uniformément dans l'univers des grilles les moins jouées, pour ne pas partager un jackpot. Le protocole ne prédit rien et ne promet aucun gain. Toute restitution garde le rappel (`DISCLAIMER` dans les modules de jeu).

## Où est quoi

| Fichier | Rôle | Qui touche |
|---|---|---|
| `qsc_core.py` | Briques communes aux deux jeux (modèles, bootstrap, p-values, règle de mise) | Les deux relecteurs |
| `qsc_games.py` | Une fiche par jeu, plus budget annuel et paliers communs | Les deux relecteurs |
| `qsc_v40.py`, `run_qsc.py`, `update_master.py`, `popularite.py` | EuroMillions | Libre, une PR par changement |
| `loto/` | Loto (`qsc_loto.py`, `run_loto.py`, `update_loto.py`, `popularite_loto.py`) | Libre, une PR par changement |
| `qsc.py` | Point d'entrée : `python3 qsc.py run\|update\|test <jeu>` | Libre |
| `tests/` | Test golden et ses données figées | Les deux relecteurs |
| `output/`, `loto/output/`, `*_MASTER.csv`, `*_PRIZES.csv` | Écrits par les Actions les jours de tirage | Ne pas éditer à la main |

## Avant d'ouvrir une PR

1. `python3 qsc.py test` : tests EuroMillions, tests Loto et golden doivent passer. La CI les rejoue sur chaque PR vers `main`.
2. Une PR = un changement. Une PR de nettoyage ne change pas la méthode, une PR de méthode ne nettoie pas en passant.
3. Python 3.12, bibliothèque standard seulement dans le pipeline (numpy n'est toléré que dans `tools/`).

## Le test golden, mode d'emploi

`tests/test_golden.py` rejoue un run complet de chaque jeu sur des données figées et compare la sortie octet pour octet aux références `tests/golden/expected_*`.

- Il échoue : quelque chose a changé dans la grille, la mise, la popularité, le backtest ou le registre. Si ce n'était pas voulu, c'est une régression.
- Le changement est voulu (nouvelle version de la méthode) : `python3 tests/test_golden.py --update`, relire le diff des références, le committer dans la même PR en expliquant pourquoi.
- Ne jamais mettre à jour les références pour « faire passer » un test sans avoir lu le diff.

## Ce qui demande une décision à deux

- Tout changement dans `qsc_core.py` ou `qsc_games.py` (il touche les deux jeux).
- Le budget annuel (`BUDGET_ANNUEL_EUR`) et les paliers de jackpot : ils sont communs.
- Un changement de méthode de sélection (univers, quantiles, anti-partage).

## Divergences connues entre les deux jeux, à trancher

Ces fonctions se ressemblent dans les deux jeux mais ne sont pas identiques. Elles n'ont pas été fusionnées dans `qsc_core.py` pour ne pas changer un comportement sans décision.

- `n_grids` : le Loto ajoute une tolérance flottante (`+ 1e-9`) que l'EuroMillions n'a pas.
- `null_distribution`, `backtest_all`, `walk_forward` : loi du tirage propre à chaque jeu.
- `anti_share_score`, `shape_penalty`, `impopular_universe` : cœur de la méthode, écritures différentes.
- `checklist` : textes `EQUIVALENCE` et `FORBIDDEN` propres à chaque jeu.

## Ajouter un jeu

Commencer par une fiche dans `qsc_games.py`, puis un module de jeu et ses scripts `run` et `update`, puis une route dans `qsc.py` et une entrée dans le test golden (données figées et références).
