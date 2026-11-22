# -*- coding: utf-8 -*-
"""
qsc_games.py : configuration des jeux du protocole QSC, en un seul endroit.

Deux niveaux :
  - constantes COMMUNES aux jeux, décidées une fois (budget annuel de mise, paliers de jackpot) :
    les changer ici les change pour l'EuroMillions et le Loto ;
  - une fiche GameSpec par jeu (taille de la grille, bonus, prix, jours de tirage, quantiles
    de l'univers impopulaire, valeurs par défaut d'EV).

Les modules qsc_v40.py (EuroMillions) et loto/qsc_loto.py lisent leurs constantes ici et gardent
leurs noms habituels (PRIX_GRILLE, ALL_NUMS, ...), donc le reste du code ne change pas.
Ajouter un jeu commence par ajouter une fiche ici.

Pur stdlib, aucune dépendance aux autres modules du dépôt.
"""
from dataclasses import dataclass
from typing import Optional, Tuple

# ---------------------------------------------------------------- communes aux jeux

BUDGET_ANNUEL_EUR = 520.0          # plafond annuel de mise, tous jeux confondus (décision du 05/11/2026)
PALIERS_MEUR = (100, 150, 200)     # 1 grille, +1 à chaque palier de jackpot franchi (en M€), mêmes paliers


# ---------------------------------------------------------------- fiche par jeu

@dataclass(frozen=True)
class GameSpec:
    cle: str                        # identifiant court
    nom: str                        # nom affiché
    n_pool: int                     # numéros de 1 à n_pool
    k_pick: int                     # numéros par grille
    bonus: str                      # "etoiles" ou "chance"
    bonus_pool: int                 # taille du pool du bonus (en vigueur)
    prix_grille: float              # € par grille
    draw_weekdays: Tuple[int, ...]  # jours de tirage, lundi = 0
    impop_quantile: float           # part des grilles les moins jouées qui forme l'univers
    bonus_quantile: float           # idem pour le bonus
    ventes_defaut: Optional[int] = None         # grilles vendues par tirage, si non estimées
    ev_rangs_bas_defaut: Optional[float] = None  # EV des rangs bas par grille, si cache de montants absent


EUROMILLIONS = GameSpec(
    cle="euromillions", nom="EuroMillions",
    n_pool=50, k_pick=5, bonus="etoiles", bonus_pool=12,
    prix_grille=2.50, draw_weekdays=(1, 4),          # mardi, vendredi
    impop_quantile=0.10, bonus_quantile=0.25,
)

LOTO = GameSpec(
    cle="loto", nom="Loto",
    n_pool=49, k_pick=5, bonus="chance", bonus_pool=10,
    prix_grille=2.20, draw_weekdays=(0, 2, 5),       # lundi, mercredi, samedi
    impop_quantile=0.10, bonus_quantile=0.30,
    ventes_defaut=3_900_000,          # médiane 2026 estimée sur les rangs 6 à 9
    ev_rangs_bas_defaut=0.84,         # EV des rangs 2 à 9 par grille (montants du 04/11/2026)
)

JEUX = {g.cle: g for g in (EUROMILLIONS, LOTO)}
