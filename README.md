# QSC EuroMillions v3.7

> ⚠️ Claude ne prédit pas les tirages. Le hasard est sans mémoire. Aucune analyse ne garantit un gain. EV nette structurellement négative (~−1,42 €/grille). Les edges backtestés et percentiles Monte-Carlo peuvent être du bruit statistique — méthodologie documentée, pas un oracle.

Pipeline d'analyse probabiliste et de backtest, exécuté automatiquement par GitHub Actions le matin de chaque tirage (mardi, vendredi — 08:10 Paris). La tâche Claude « QSC EuroMillions v3.7 - Tirage jour (mar/ven) » ne calcule rien : elle lit `output/latest.json` et le restitue.

## Content

| Fichier | Rôle |
|---|---|
| `euromillions_MASTER.csv` | Historique complet des tirages (`date;n1..n5;e1;e2`), mis à jour par l'Action. Source : [API pedromealha](https://euromillions.api.pedromealha.dev/). |
| `qsc_v37.py` | Module : catalogue typé (6 selectors, 1 diagnostic, 1 filter), backtest walk-forward step 1, IC95 % bootstrap, null hypergéométrique exact + max-statistic, backtest étoiles conscient du pool 9/11/12, anti-partage, consensus stricte, checklist. |
| `test_qsc_v37.py` | 54 tests unitaires (`python3 test_qsc_v37.py`). |
| `update_master.py` | Refresh append-only du CSV depuis l'API, refus d'écrire si l'intégrité casse, écrit `output/api_meta.json`. |
| `run_qsc.py` | Pipeline complet → `output/latest.json`, `output/latest.html`, `output/registre.csv`, `output/history/<date>.json`. |
| `.github/workflows/qsc.yml` | Cron mar/ven + `workflow_dispatch` (input `jackpot_meur` pour forcer le montant officiel). |
| `PROMPT_tache_cloud_v37.md` | Prompt de la tâche Claude cloud (lecteur). |
| `RAPPORT_application_v37.md` | Rapport du chantier v3.7. |

## Sorties publiées

- `output/latest.json` — grilles du jour, backtests, verdicts, jackpot estimé, registre rapproché, `chat_summary` prêt à coller.
- `output/latest.html` — tableau de bord autonome (badges, histogramme Monte-Carlo, cumul protocole-vs-hasard, lexique).
- `output/registre.csv` — registre append-only : chaque grille jouée, rapprochée au run suivant avec le tirage réel.

## Lancer en local

```bash
python3 test_qsc_v37.py
python3 update_master.py            # ~10 s, dépend de l'API
python3 run_qsc.py [--jackpot 95]   # ~50 s (5 000 simulations null, 50 000 grilles Monte-Carlo)
```
# QSC EuroMillions v3.6

> ⚠️ Analyse probabiliste et backtest, pas un système de prédiction. Le hasard est sans mémoire. Aucune analyse ne garantit un gain. EV nette structurellement négative (~−1,42 €/grille).

## Contenu du dépôt

- `euromillions_MASTER.csv` — historique complet des tirages EuroMillions (2004-02-13 → 2026-07-31, 1968 tirages), format `date;n1;n2;n3;n4;n5;e1;e2`. Source : [API pedromealha](https://euromillions.api.pedromealha.dev/).
- `qsc_v36.py` — module d'analyse (selectors, diagnostics, filtres, backtest walk-forward, bootstrap IC95%, test de permutation).
- `test_qsc_v36.py` — tests unitaires (34/34 verts).
- `RAPPORT_application_v36.md` — rapport d'application du chantier v3.6.

## Usage

Ce dépôt sert de source de données primaire pour la session QSC EuroMillions (Claude). L'URL raw du CSV est fournie au prompt QSC pour charger l'historique complet sans dépendre de l'API à chaque run.
