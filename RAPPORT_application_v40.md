# Rapport d'application — QSC EuroMillions v4.0

> ⚠️ Claude ne prédit pas les tirages. Le hasard est sans mémoire. Aucune analyse ne garantit un gain. EV nette structurellement négative (de −1,9 € par grille à 17 M€ de jackpot à −0,5 € au plafond de 250 M€). Les écarts backtestés sont du bruit statistique, mesuré comme tel — méthodologie documentée, pas un oracle.

Chantier du 05/11/2026, application de l'audit indépendant du 04/11/2026 (rapport « Audit QSC EuroMillions — novembre 2026 », Claude Docs). Décisions prises par Charles le 05/11/2026.

## Ce que l'audit a établi

- Aucun des 22 tests de base (uniformité, sommes, parité, retards, autocorrélations, runs) ne survit à la correction de Holm : les tirages se comportent comme un tirage uniforme sans mémoire.
- Aucun des 6 selectors n'est discernable du hasard (p global 0,67 sur 1 844 points, meilleur écart +0,015 pour un écart-type de 0,015). Le classement n'a aucune stabilité temporelle (Spearman 0,37 entre moitiés, 6 vainqueurs différents sur 31 fenêtres de 300 points). La rotation ne change rien (politique rejouée : −0,010 sans, +0,013 avec, ±0,015).
- Le backtest mesurait le top-5 brut, pas la grille jouée (argmax dans l'univers) : le « porteur » était classé sur une épreuve qu'il ne courait pas.
- Puissance : 4 089 grilles pour détecter +5 % avec 80 % de puissance (19,7 ans à 2 grilles par tirage) ; 41 grilles ne détectent qu'un avantage de +50 %.
- Le proxy UK (v3.8) surestimait l'amplitude des popularités d'un facteur 4 ; la table R7 (v3.9, branche non fusionnée) est juste (R² 0,57, stabilité split-half 0,94) : ρ de 0,83 à 1,18, étoiles 12, 10, 11, 1 les moins jouées.
- Le levier anti-partage vaut 1 à 11 centimes par grille selon le jackpot ; l'EV nette reste négative à tout jackpot atteignable (seuil d'EV nulle ≈ 308 M€, plafond 250 M€).
- Le jackpot utilisé était celui du tirage précédent (un palier trop bas). Deux registres coexistaient (dépôt depuis le 04/09, mémoire pour août).

## Changements

| | v3.9 (branche) | v4.0 |
|---|---|---|
| **A1 Sélection** | argmax du score du porteur dans l'univers impopulaire, classement par écart backtesté, rotation narrative, consensus | tirage **uniforme** par `random.Random(seed)` dans l'univers impopulaire (table R7), recouvrement ≤ 2, paires d'étoiles distinctes. Plus de porteur, de classement, de rotation ni de consensus (fonctions supprimées) |
| **Backtest** | pilote le classement | **diagnostic** publié pour mémoire, ne pilote rien |
| **A2 Mise** | 2 + ⌊(J−50)/50⌋ grilles, sans plafond | 1 grille, +1 à 100, 150 et 200 M€ ; borné par `BUDGET_EUR = 520` par an (0 grille et livrable publié sans grille une fois le budget atteint) |
| **A3 Jackpot** | jackpot du tirage précédent non gagné | montant officiel lu sur fdj.fr (`jackpot.source = "fdj.fr"`), repli sur l'estimation si la page est inaccessible |
| **A4 Registre** | numéros/étoiles trouvés | + `jackpot_meur`, `rang`, `gain_eur` (montant réel du rang via `output/api_cache/`), `gagnants_rang`, `gagnants_attendus_rang` (ventes estimées sur les rangs 2+0, 2+1, 1+2, 3+0). Cumul : mise, gains, solde, taux de partage observé, IC95 % de l'écart au hasard, dépense de l'année. Les 20 grilles d'août 2026 du registre hors dépôt sont réinjectées (61 grilles) |
| **A5 Livrable** | percentile Monte-Carlo sur les cartes | retiré (mesure in-sample) ; EV nette théorique par grille ; section mise/budget ; verdict reformulé |
| `update_master.py` | importait `qsc_v39` | `qsc_v40`, conserve les réponses annuelles de l'API dans `output/api_cache/`, 3 s entre appels (429 dès 3 requêtes rapprochées) |
| Workflow | `qsc.yml` v3.9 ; `loto.yml` planifié | `qsc.yml` v4.0 ; **`loto.yml` : crons désactivés** (Loto différé, `workflow_dispatch` conservé) |
| Disclaimer | « ~−1,42 €/grille », « percentiles Monte-Carlo » | fourchette d'EV réelle, plus de mention du Monte-Carlo |

Inchangés : univers impopulaire (D1), pas de contrainte dure (D2), étoiles par ère de pool (D3), co-gagnants normalisés (D4), popularité R7/R8/R9, null exacte + max-statistic, intégrité, seed, idempotence du registre.

## Effet mesuré (run à blanc du 05/11/2026 pour le tirage du 06/11, seed 20261106, 1 995 tirages)

- Jackpot officiel lu sur fdj.fr : 130 M€ (l'estimation API donnait 99 M€, soit un palier de moins) → 2 grilles.
- Grilles : 08 29 35 36 45 ★11 12 et 30 34 37 45 47 ★06 12, joueurs attendus ×0,46 chacune (table R7 ; la v3.8 aurait affiché ×0,12 avec le proxy UK), EV nette théorique −1,13 € par grille.
- Registre réconcilié : 61 grilles, 28 numéros trouvés pour 30,5 attendus (IC95 % ±9,8), mise 152,50 €, gains 20,89 € (4 rangs atteints : 13, 12, 11, 12), partage observé ×1,08 sur ces 4 rangs (trop peu pour conclure).
- Tests : 98/98 (`test_qsc_v40.py`). Pipeline complet : ~30 s (le Monte-Carlo de 50 000 grilles a disparu). Checklist verte.

## Protocole de suivi (audit §D)

Revue à n = 200 grilles (EV réalisée vs théorique, taux de partage) ; à n = 500, si l'IC de l'écart au hasard contient toujours zéro, le diagnostic backtest disparaît aussi du livrable. Toute révision de méthode passe par une PR documentée, jamais par un run.

## Fichiers du chantier

`qsc_v40.py`, `test_qsc_v40.py`, `run_qsc.py`, `update_master.py`, `.github/workflows/qsc.yml`, `.github/workflows/loto.yml`, `PROMPT_tache_cloud_v40.md`, `README.md`, `output/registre.csv`, `output/api_cache/`, ce rapport. `qsc_v39.py` et `test_qsc_v39.py` conservés pour référence.

> ⚠️ Claude ne prédit pas les tirages. Le hasard est sans mémoire. Aucune analyse ne garantit un gain. EV nette structurellement négative (de −1,9 € par grille à 17 M€ de jackpot à −0,5 € au plafond de 250 M€). Les écarts backtestés sont du bruit statistique, mesuré comme tel — méthodologie documentée, pas un oracle.
