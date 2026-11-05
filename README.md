# QSC EuroMillions v4.0

> ⚠️ Claude ne prédit pas les tirages. Le hasard est sans mémoire. Aucune analyse ne garantit un gain. EV nette structurellement négative (de −1,9 € par grille à 17 M€ de jackpot à −0,5 € au plafond de 250 M€). Les écarts backtestés sont du bruit statistique, mesuré comme tel — méthodologie documentée, pas un oracle.

Pipeline de sélection de grilles parmi les moins jouées (tirage uniforme dans l'univers impopulaire, diagnostic backtest publié pour mémoire, registre en euros, mise sous budget), exécuté automatiquement par GitHub Actions le matin de chaque tirage (mardi, vendredi — 08:10 Paris). La tâche Claude « QSC EuroMillions v4.0 — Tirage jour (mar/ven) » lit `output/latest.json` et le restitue ; si le run GitHub a été sauté, elle rejoue le pipeline versionné elle-même (sans écrire dans le dépôt).

## Contenu

| Fichier | Rôle |
|---|---|
| `euromillions_MASTER.csv` | Historique complet des tirages (`date;n1..n5;e1;e2`), mis à jour par l'Action. Source : [API pedromealha](https://euromillions.api.pedromealha.dev/). |
| `euromillions_PRIZES.csv` | Gagnants par rang à chaque tirage (`date;w5_2;…;w1_2`), append-only, même source. Sert à estimer la popularité (R7). |
| `popularite.py` | R7 : popularité relative des numéros et étoiles estimée sur les gagnants par rang (ratio 3 num./2 num., 2 ét./1 ét.), stdlib. |
| `qsc_v40.py` | Module : univers impopulaire (décile le moins populaire des C(50,5) sous la table R7, repli proxy UK), **tirage uniforme par seed** dans cet univers (A1), règle de mise 1/2/3/4 grilles sous budget annuel de 520 € (A2), 6 selectors backtestés en walk-forward step 1 à titre de diagnostic (null hypergéométrique exacte + max-statistic), étoiles par ère de pool 9/11/12, checklist. Plus de porteur, de rotation ni de consensus depuis l'audit du 04/11/2026. `qsc_v39.py` conservé pour référence. |
| `test_qsc_v40.py` | 98 tests unitaires (`python3 test_qsc_v40.py`). |
| `tools/calibration_r7.py` | Hors pipeline (numpy) : calibration des pentes de `popularite.py` et contrôle croisé. |
| `update_master.py` | Refresh append-only du CSV depuis l'API, refus d'écrire si l'intégrité casse, alimente `euromillions_PRIZES.csv`, conserve les réponses annuelles dans `output/api_cache/` (montants par rang), écrit `output/api_meta.json`. |
| `run_qsc.py` | Pipeline complet : jackpot officiel lu sur fdj.fr (repli estimation API), registre rapproché en euros, tirage des grilles → `output/latest.json`, `output/latest.html`, `output/registre.csv`, `output/history/<date>.json`. |
| `.github/workflows/qsc.yml` | Trois crons mar/ven (06:10, 09:10, 12:40 UTC) avec garde d'idempotence + `workflow_dispatch` (inputs `jackpot_meur`, `n_grilles`). |
| `PROMPT_tache_cloud_v40.md` | Prompt de la tâche Claude cloud (lecteur + fallback). |
| `RAPPORT_application_v40.md` | Application de l'audit du 04/11/2026 (sélection uniforme, mise sous budget, registre en euros). `RAPPORT_application_v39.md` et antérieurs : chantiers précédents. |

## Sorties publiées

- `output/latest.json` — grilles du jour, mise et budget, jackpot officiel, popularité, diagnostic backtest, registre rapproché en euros, `chat_summary` prêt à coller.
- `output/popularite.json` — table de popularité en vigueur pour le run (source, ρ par numéro/étoile, incertitudes).
- `output/latest.html` — tableau de bord autonome (grilles, mise, popularité R7, cumul protocole-vs-hasard en euros et partage observé, diagnostic, lexique).
- `output/registre.csv` — registre append-only : chaque grille jouée, rapprochée au run suivant avec le tirage réel, le rang atteint, le gain réel et les gagnants observés vs attendus.

## Lancer en local

```bash
python3 test_qsc_v40.py
python3 update_master.py            # ~15 s, dépend de l'API
python3 run_qsc.py [--jackpot 95] [--no-fdj]   # ~30 s (5 000 simulations null)
```

## QSC Loto (dossier `loto/`) — différé

**Crons désactivés le 05/11/2026** : le Loto est reporté tant que son module n'est pas aligné sur la v4.0 (tirage uniforme, 1 grille par tirage, budget commun). Le code reste en place et `workflow_dispatch` fonctionne.

Même protocole (version v3.9) transposé au Loto FDJ (5 numéros sur 49 + numéro Chance sur 10, tirages lundi / mercredi / samedi) : six selectors backtestés, null exacte 5 parmi 49, popularité des numéros et du numéro Chance estimée sur les gagnants par rang publiés par la FDJ (2 819 tirages depuis 2008), univers impopulaire, registre append-only, 3 grilles par défaut (+1 par tranche de 10 M€ au-delà de 10 M€).

| Fichier | Rôle |
|---|---|
| `loto/loto_MASTER.csv`, `loto/loto_PRIZES.csv` | Historique officiel FDJ (tirages ; gagnants par rang, règle 6 rangs 2008-2017 puis 9 rangs). |
| `loto/qsc_loto.py`, `loto/popularite_loto.py` | Module et estimateur de popularité (stdlib). |
| `loto/update_loto.py`, `loto/run_loto.py` | Refresh depuis le zip FDJ `loto_201911` ; pipeline complet → `loto/output/`. |
| `loto/test_loto.py` | 49 tests. |
| `.github/workflows/loto.yml` | Crons lun/mer/sam (06:20, 09:20, 12:50 UTC) + garde d'idempotence. |
| `PROMPT_tache_cloud_loto.md` | Prompt de la tâche Claude cloud Loto. |

```bash
cd loto && python3 test_loto.py && python3 update_loto.py && python3 run_loto.py   # ~50 s
```
