# QSC EuroMillions v3.9

> ⚠️ Claude ne prédit pas les tirages. Le hasard est sans mémoire. Aucune analyse ne garantit un gain. EV nette structurellement négative (~−1,42 €/grille). Les edges backtestés et percentiles Monte-Carlo peuvent être du bruit statistique — méthodologie documentée, pas un oracle.

Pipeline d'analyse probabiliste et de backtest, exécuté automatiquement par GitHub Actions le matin de chaque tirage (mardi, vendredi — 08:10 Paris). La tâche Claude « QSC EuroMillions v3.9 — Tirage jour (mar/ven) » lit `output/latest.json` et le restitue ; si le run GitHub a été sauté, elle rejoue le pipeline versionné elle-même (sans écrire dans le dépôt).

## Contenu

| Fichier | Rôle |
|---|---|
| `euromillions_MASTER.csv` | Historique complet des tirages (`date;n1..n5;e1;e2`), mis à jour par l'Action. Source : [API pedromealha](https://euromillions.api.pedromealha.dev/). |
| `qsc_v39.py` | Module : univers impopulaire (décile le moins populaire des C(50,5) d'après `popularity_fdj.json`) dans lequel le porteur départage, 6 selectors backtestés en walk-forward step 1, IC95 % bootstrap, null hypergéométrique exacte + max-statistic, étoiles par ère de pool 9/11/12, consensus stricte, checklist. `qsc_v38.py` conservé pour référence. |
| `fit_popularity.py` | Estime la popularité relative des 50 numéros et 12 étoiles sur les gagnants par rang (ère 12 étoiles, totaux européens) → `popularity_fdj.json` ; cache `winners_MASTER.csv`. Relancé par `refit-popularity.yml` le 1er du mois. |
| `test_qsc_v39.py` | 89 tests unitaires (`python3 test_qsc_v39.py`). |
| `update_master.py` | Refresh append-only du CSV depuis l'API, refus d'écrire si l'intégrité casse, écrit `output/api_meta.json`. |
| `run_qsc.py` | Pipeline complet → `output/latest.json`, `output/latest.html`, `output/registre.csv`, `output/history/<date>.json`. |
| `.github/workflows/qsc.yml` | Trois crons mar/ven (06:10, 09:10, 12:40 UTC) avec garde d'idempotence + `workflow_dispatch` (inputs `jackpot_meur`, `n_grilles`). |
| `PROMPT_tache_cloud_v39.md` | Prompt de la tâche Claude cloud (lecteur + fallback). |
| `RAPPORT_application_v39.md` | Audit du moteur de sélection et chantier v3.9 (popularité calibrée). `RAPPORT_application_v38.md` : chantier précédent. |

## Sorties publiées

- `output/latest.json` — grilles du jour, backtests, verdicts, jackpot estimé, registre rapproché, `chat_summary` prêt à coller.
- `output/latest.html` — tableau de bord autonome (badges, backtests, cumul protocole-vs-hasard, lexique).
- `output/registre.csv` — registre append-only : chaque grille jouée, rapprochée au run suivant avec le tirage réel.

## Lancer en local

```bash
python3 test_qsc_v39.py
python3 update_master.py            # ~10 s, dépend de l'API
python3 run_qsc.py [--jackpot 95]   # ~30 s (5 000 simulations null)
python3 fit_popularity.py           # recalibre popularity_fdj.json (numpy + scipy, ~2 min avec l'API)
```
