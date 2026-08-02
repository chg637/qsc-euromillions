# QSC EuroMillions v3.6

> ⚠️ Analyse probabiliste et backtest, pas un système de prédiction. Le hasard est sans mémoire. Aucune analyse ne garantit un gain. EV nette structurellement négative (~−1,42 €/grille).

## Contenu du dépôt

- `euromillions_MASTER.csv` — historique complet des tirages EuroMillions (2004-02-13 → 2026-07-31, 1968 tirages), format `date;n1;n2;n3;n4;n5;e1;e2`. Source : [API pedromealha](https://euromillions.api.pedromealha.dev/).
- `qsc_v36.py` — module d'analyse (selectors, diagnostics, filtres, backtest walk-forward, bootstrap IC95%, test de permutation).
- `test_qsc_v36.py` — tests unitaires (34/34 verts).
- `RAPPORT_application_v36.md` — rapport d'application du chantier v3.6.

## Usage

Ce dépôt sert de source de données primaire pour la session QSC EuroMillions (Claude). L'URL raw du CSV est fournie au prompt QSC pour charger l'historique complet sans dépendre de l'API à chaque run.
