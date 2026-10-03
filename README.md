# QSC EuroMillions v3.8

> ⚠️ Claude ne prédit pas les tirages. Le hasard est sans mémoire. Aucune analyse ne garantit un gain. EV nette structurellement négative (~−1,42 €/grille). Les edges backtestés et percentiles Monte-Carlo peuvent être du bruit statistique — méthodologie documentée, pas un oracle.

Pipeline d'analyse probabiliste et de backtest, exécuté automatiquement par GitHub Actions le matin de chaque tirage (mardi, vendredi — 08:10 Paris). La tâche Claude « QSC EuroMillions v3.8 — Tirage jour (mar/ven) » lit `output/latest.json` et le restitue ; si le run GitHub a été sauté, elle rejoue le pipeline versionné elle-même (sans écrire dans le dépôt).

## Contenu

| Fichier | Rôle |
|---|---|
| `euromillions_MASTER.csv` | Historique complet des tirages (`date;n1..n5;e1;e2`), mis à jour par l'Action. Source : [API pedromealha](https://euromillions.api.pedromealha.dev/). |
| `qsc_v38.py` | Module : univers impopulaire (décile le moins populaire des C(50,5), proxy UK) dans lequel le porteur départage, 6 selectors backtestés en walk-forward step 1, IC95 % bootstrap, null hypergéométrique exacte + max-statistic, étoiles par ère de pool 9/11/12, consensus stricte, checklist. `qsc_v37.py` conservé pour référence. |
| `test_qsc_v38.py` | 75 tests unitaires (`python3 test_qsc_v38.py`). |
| `update_master.py` | Refresh append-only du CSV depuis l'API, refus d'écrire si l'intégrité casse, écrit `output/api_meta.json`. |
| `run_qsc.py` | Pipeline complet → `output/latest.json`, `output/latest.html`, `output/registre.csv`, `output/history/<date>.json`. |
| `.github/workflows/qsc.yml` | Trois crons mar/ven (06:10, 09:10, 12:40 UTC) avec garde d'idempotence + `workflow_dispatch` (inputs `jackpot_meur`, `n_grilles`). |
| `PROMPT_tache_cloud_v38.md` | Prompt de la tâche Claude cloud (lecteur + fallback). |
| `RAPPORT_application_v38.md` | Rapport du chantier v3.8 (sélection inversée). `RAPPORT_application_v37.md` : chantier précédent. |

## Sorties publiées

- `output/latest.json` — grilles du jour, backtests, verdicts, jackpot estimé, registre rapproché, `chat_summary` prêt à coller.
- `output/latest.html` — tableau de bord autonome (badges, histogramme Monte-Carlo, cumul protocole-vs-hasard, lexique).
- `output/registre.csv` — registre append-only : chaque grille jouée, rapprochée au run suivant avec le tirage réel.

## Lancer en local

```bash
python3 test_qsc_v38.py
python3 update_master.py            # ~10 s, dépend de l'API
python3 run_qsc.py [--jackpot 95]   # ~50 s (5 000 simulations null, 50 000 grilles Monte-Carlo)
```
