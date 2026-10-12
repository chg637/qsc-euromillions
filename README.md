# QSC EuroMillions v3.9

> ⚠️ Claude ne prédit pas les tirages. Le hasard est sans mémoire. Aucune analyse ne garantit un gain. EV nette structurellement négative (~−1,42 €/grille). Les edges backtestés et percentiles Monte-Carlo peuvent être du bruit statistique — méthodologie documentée, pas un oracle.

Pipeline d'analyse probabiliste et de backtest, exécuté automatiquement par GitHub Actions le matin de chaque tirage (mardi, vendredi — 08:10 Paris). La tâche Claude « QSC EuroMillions v3.9 — Tirage jour (mar/ven) » lit `output/latest.json` et le restitue ; si le run GitHub a été sauté, elle rejoue le pipeline versionné elle-même (sans écrire dans le dépôt).

## Contenu

| Fichier | Rôle |
|---|---|
| `euromillions_MASTER.csv` | Historique complet des tirages (`date;n1..n5;e1;e2`), mis à jour par l'Action. Source : [API pedromealha](https://euromillions.api.pedromealha.dev/). |
| `euromillions_PRIZES.csv` | Gagnants par rang à chaque tirage (`date;w5_2;…;w1_2`), append-only, même source. Sert à estimer la popularité (R7). |
| `popularite.py` | R7 : popularité relative des numéros et étoiles estimée sur les gagnants par rang (ratio 3 num./2 num., 2 ét./1 ét.), stdlib. |
| `qsc_v39.py` | Module : univers impopulaire (décile le moins populaire des C(50,5) sous la table estimée, repli proxy UK) dans lequel le porteur départage, 6 selectors backtestés en walk-forward step 1, IC95 % bootstrap, null hypergéométrique exacte + max-statistic, étoiles par ère de pool 9/11/12, consensus stricte, checklist. `qsc_v38.py` conservé pour référence. |
| `test_qsc_v39.py` | 93 tests unitaires (`python3 test_qsc_v39.py`). |
| `tools/calibration_r7.py` | Hors pipeline (numpy) : calibration des pentes de `popularite.py` et contrôle croisé. |
| `update_master.py` | Refresh append-only du CSV depuis l'API, refus d'écrire si l'intégrité casse, alimente `euromillions_PRIZES.csv`, écrit `output/api_meta.json`. |
| `run_qsc.py` | Pipeline complet → `output/latest.json`, `output/latest.html`, `output/registre.csv`, `output/history/<date>.json`. |
| `.github/workflows/qsc.yml` | Trois crons mar/ven (06:10, 09:10, 12:40 UTC) avec garde d'idempotence + `workflow_dispatch` (inputs `jackpot_meur`, `n_grilles`). |
| `PROMPT_tache_cloud_v39.md` | Prompt de la tâche Claude cloud (lecteur + fallback). |
| `RAPPORT_application_v39.md` | Audit du moteur et chantier v3.9 (popularité estimée). `RAPPORT_application_v38.md` : chantier précédent. |

## Sorties publiées

- `output/latest.json` — grilles du jour, backtests, verdicts, jackpot estimé, registre rapproché, `chat_summary` prêt à coller.
- `output/popularite.json` — table de popularité en vigueur pour le run (source, ρ par numéro/étoile, incertitudes).
- `output/latest.html` — tableau de bord autonome (badges, histogramme Monte-Carlo, cumul protocole-vs-hasard, lexique).
- `output/registre.csv` — registre append-only : chaque grille jouée, rapprochée au run suivant avec le tirage réel.

## Lancer en local

```bash
python3 test_qsc_v39.py
python3 update_master.py            # ~10 s, dépend de l'API
python3 run_qsc.py [--jackpot 95]   # ~90 s (5 000 simulations null, 50 000 grilles Monte-Carlo)
```
