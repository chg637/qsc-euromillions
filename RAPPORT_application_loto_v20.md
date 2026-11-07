# Rapport d'application — QSC Loto v2.0

> ⚠️ Claude ne prédit pas les tirages. Le hasard est sans mémoire. Aucune analyse ne garantit un gain. EV nette négative à presque tous les jackpots (environ −1,3 € par grille à 2 M€, −0,7 € à 13 M€), proche de zéro seulement au maximum historique de 30 M€. Les écarts backtestés sont du bruit statistique, mesuré comme tel — méthodologie documentée, pas un oracle.

Chantier du 07/11/2026 : transposition au Loto de la v4.0 EuroMillions (audit indépendant du 04/11/2026, décisions de Charles du 05/11/2026). Le Loto était différé depuis le 05/11 ; il repart avec ce module.

## Changements

| | Loto v1.0 | Loto v2.0 |
|---|---|---|
| **A1 Sélection** | argmax du score du porteur dans l'univers impopulaire, rotation narrative, consensus | tirage **uniforme** par `random.Random(seed)` dans l'univers impopulaire (décile le moins joué des C(49,5), hors motifs sur-joués), recouvrement ≤ 2, numéro Chance tiré dans les 3 les moins joués, distincts tant que possible. `best_grid`, `best_chance`, `rank_selectors`, `consensus_grid` supprimées |
| **Backtest** | pilote le classement des porteurs | **diagnostic** publié pour mémoire, ne pilote rien |
| **A2 Mise** | 3 grilles, +1 par tranche de 10 M€ | 1 grille, +1 à 100, 150 et 200 M€, borné par `BUDGET_EUR = 520` par an **tous jeux confondus** : le runner lit aussi `output/registre.csv` (EuroMillions) |
| **A3 Jackpot** | estimation (dernier jackpot non gagné + 1 M€) | montant officiel lu sur la page Loto de fdj.fr (titre « LOTO® : 13 M€ ce samedi 7 novembre 2026 »), accepté seulement s'il porte la date du tirage visé et tient dans 2-200 M€ ; repli sur l'estimation sinon |
| **A4 Registre** | numéros et Chance trouvés | + `jackpot_meur`, `rang` (règle 2017+), `gain_eur` (montant réel du rang, conservé dans `loto/output/api_cache/`), `gagnants_rang`, `gagnants_attendus_rang` (ventes estimées sur les rangs 5 à 9). Une ligne reste ouverte tant que les gagnants ou les montants du tirage manquent. Cumul : mise, gains, solde, partage observé, IC95 %, dépense de l'année |
| **A5 Livrable** | consensus, porteurs, rotation | EV nette théorique par grille, section mise et budget commun, verdict reformulé |
| `update_loto.py` | tirages et gagnants par rang | + montants par rang de l'année en cours et de la précédente (`output/api_cache/<année>.json`) |
| Workflow `loto.yml` | crons désactivés | crons réactivés lun/mer/sam sur le modèle de `qsc.yml` : veille au soir (22:29 UTC), nuit (02:43), 06:20, 09:20, 12:50 UTC, garde d'idempotence conservée |
| `run_qsc.py` (EuroMillions) | budget limité à son propre registre | + dépense Loto de l'année (`loto/output/registre.csv`, 2,20 € la grille) dans le budget de 520 € ; 5 tests ajoutés |

Inchangés : univers impopulaire, popularité estimée sur les gagnants par rang FDJ, null exacte + max-statistic, intégrité, seed, idempotence du registre.

## Ce que les données ont montré en route

- **Rang 9** : Chance avec 0 **ou 1** numéro (rapport rang 9 / rang 8 observé 1,44 pour 1,48 attendu ; l'hypothèse « 0 numéro seulement » donnait 0,91).
- **Ventes** : environ 3,9 millions de grilles par tirage en 2026 (rangs 5 à 9), et non les 6 millions que supposait la v1.0 pour les co-gagnants attendus.
- **EV** : avec 0,84 € d'espérance sur les rangs 2 à 9 (montants du 04/11/2026), l'EV nette d'une grille est d'environ −1,26 € à 2 M€, −0,74 € à 13 M€, −0,41 € à 20 M€ et **+0,06 à +0,14 € à 30 M€** (maximum historique sur 1 502 tirages), avant tout effet des ventes plus fortes quand le jackpot monte. L'avertissement « structurellement négative » de la v1.0 était donc faux au plafond : il est corrigé dans `DISCLAIMER`.
- **Paliers de mise** : le Loto n'a jamais atteint 100 M€ ; la règle 1/2/3/4 donne toujours 1 grille. Décision laissée à Charles s'il veut un palier propre au Loto (constante `PALIERS_MEUR`).
- **Budget** : 1 grille Loto par tirage (156 par an, 343 €) plus 1 grille EuroMillions (104 par an, 260 €) dépassent 520 € sur une année pleine : le pipeline s'arrêtera de lui-même en fin d'année 2027. Sur 2026, la dépense inscrite aux registres reste très en dessous.

## Run à blanc du 07/11/2026 (tirage du samedi 07/11, seed 20261107, 2 830 tirages)

- Jackpot officiel lu sur fdj.fr : 13 M€ → 1 grille : 08 24 39 45 46, Chance 2, joueurs attendus ×0,52, EV nette −0,75 €.
- Registre : les 3 grilles du 14/10 sont rapprochées (2 numéros pour la meilleure, rang 8, gain réel 5,30 €, partage ×0,92 sur ce seul rang).
- Budget : 166,30 € dépensés en 2026 sur 520 € (dont 157,50 € en EuroMillions).
- Tests : 110/110 (`loto/test_loto.py`), 104/104 (`test_qsc_v40.py`). Pipeline complet ~45 s. Checklist verte.

## Limite connue

Le registre du Loto ne contient que les 3 grilles du 14/10 : les runs de la tâche Claude entre le 17/10 et le 04/11 ont été rejoués en local (fallback, sans écriture dans le dépôt) et ne sont pas inscrits. Si Charles a joué ces grilles, elles sont à réinjecter à la main, comme l'ont été celles d'août pour l'EuroMillions.

## Fichiers du chantier

`loto/qsc_loto.py`, `loto/run_loto.py`, `loto/update_loto.py`, `loto/test_loto.py`, `run_qsc.py`, `test_qsc_v40.py`, `.github/workflows/loto.yml`, `PROMPT_tache_cloud_loto.md`, `README.md`, ce rapport.

> ⚠️ Claude ne prédit pas les tirages. Le hasard est sans mémoire. Aucune analyse ne garantit un gain. EV nette négative à presque tous les jackpots (environ −1,3 € par grille à 2 M€, −0,7 € à 13 M€), proche de zéro seulement au maximum historique de 30 M€. Les écarts backtestés sont du bruit statistique, mesuré comme tel — méthodologie documentée, pas un oracle.
