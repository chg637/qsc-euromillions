# QSC v3.7 — Rapport d'application (04/09/2026)

> ⚠️ **Claude ne prédit pas les tirages. Le hasard est sans mémoire. Aucune analyse ne garantit un gain. EV nette structurellement négative (~−1,42 €/grille). Les edges backtestés et percentiles Monte-Carlo peuvent être du bruit statistique — méthodologie documentée, pas un oracle.**

## Ce qui change vs v3.6

| # | Changement | Pourquoi | Preuve |
|---|---|---|---|
| C1 | **Test de significativité corrigé** : null hypergéométrique exact + max-statistic (correction des 6 tests multiples) | Le "test de permutation" v3.6 ré-échantillonnait chaque modèle avec remise et comparait l'observé à lui-même (la permutation `sh` n'était même pas utilisée) : p ≈ 0,9 par construction | p global numéros = 0,75 ; seuil de significativité du meilleur modèle = écart ≥ +0,036 |
| C2 | **Walk-forward step 1** (1 827 points au lieu de 228) | Step 8 jetait 87 % des points de test | IC95 % divisés par ~3 : Co-occurrence passe de +0,066 [−0,02 ; +0,16] à **+0,004 [−0,03 ; +0,03]** |
| C3 | **Dirichlet-multinomial retiré** | Classement strictement identique à Fréquence globale (mêmes grilles, même IC) : un selector fantôme qui gonflait la correction multiple | 6 selectors |
| C4 | **Consensus stricte** | v3.6 ne dégénérait que si tous les écarts ≤ 0 : avec 7 modèles non significatifs elle pondérait du bruit | Dégénère dès qu'aucun p corrigé < 0,05 — c'est le cas aujourd'hui |
| C5 | **Étoiles backtestées, pool 9/11/12 respecté** | Premier backtest étoiles : "fenêtres" sortait **significatif (p = 0,002)**. Artefact : le pool est passé de 9 à 11 étoiles le 10/05/2011 puis 12 le 27/09/2016 ; une baseline 1/3 sur 2004-2011 donne un faux edge à tout modèle fréquence. Baseline, candidats et null sont désormais indexés sur le pool en vigueur à chaque tirage | Après correction : fenêtres +0,018, p = 0,20 ; lag +0,011, p = 0,45 ; fréquence −0,002, p = 0,90. Rien ne survit |
| C6 | **Pipeline GitHub Actions** (`update_master.py`, `run_qsc.py`, `.github/workflows/qsc.yml`) | Le CSV était figé au 31/07 ; la tâche cloud recalculait tout à chaque run | Cron mar/ven 08:10 Paris : refresh API → tests → rapport → commit. Le CSV est passé à 1 977 tirages (→ 01/09/2026) |
| C7 | **Registre append-only + rapprochement automatique + tableau de bord cumulatif** (`output/registre.csv`) | Spec #12-#14 v3.6 vivaient en mémoire Cowork, hors dépôt | Run 31/07 rapproché : 0 numéro sur 2 grilles (attendu 1,0). Les grilles du jour sont inscrites, rapprochées au run suivant |
| C8 | **Rotation narrative portée dans le code** | Spec #15 | `rank_selectors(ineligible_first=…)` lit le dernier `history/<date>.json` antérieur au tirage |
| C9 | **Badges, histogramme Monte-Carlo SVG, responsive** (`output/latest.html`) | Spec #16-#17 | Page autonome, sans JS, aucune balise orpheline |
| C10 | **Tâche cloud = lecteur** (`PROMPT_tache_cloud_v37.md`) | Plus aucun calcul côté Claude : lecture de `latest.json`, contrôles fraîcheur / checklist / intégrité / jackpot, restitution de `chat_summary` | À coller dans la tâche « QSC EuroMillions v3.7 - Tirage jour (mar/ven) » |

Tests : **54/54 verts** (`test_qsc_v37.py`), dont : null centrée en 0, null max > null single, données synthétiques aléatoires → p global non significatif et consensus dégénérée, pool étoiles par date, rotation, calendrier.

## Résultat central du chantier

Sur 1 977 tirages, step 1, correction des tests multiples :

| Modèle | Écart | IC95 % | p corrigé |
|---|---|---|---|
| Momentum | +0,012 | [−0,016 ; +0,041] | 0,75 |
| Co-occurrence / graphe | +0,004 | [−0,027 ; +0,033] | 0,96 |
| Fréquence globale | −0,000 | [−0,029 ; +0,029] | 0,99 |
| Chaînes de Markov | −0,002 | [−0,032 ; +0,028] | 0,99 |
| Fenêtres glissantes | −0,012 | [−0,041 ; +0,018] | 1,00 |
| Lag / retard normalisé | −0,018 | [−0,047 ; +0,011] | 1,00 |

χ² d'uniformité : 53,4 (ddl 49), p ≈ 0,31. Le classement v3.6 (Co-occurrence +0,066 en tête) était un artefact du sous-échantillonnage : à pleine résolution tout se resserre autour de zéro, comme attendu pour un tirage sans mémoire. La v3.7 le mesure proprement au lieu de le constater par accident.

## Reste à faire (Charles)

1. Pousser le dépôt (fichiers livrés) et vérifier que l'Action tourne (onglet Actions → "QSC EuroMillions — tirage du jour" → Run workflow pour un premier test).
2. Remplacer le prompt de la tâche cloud par `PROMPT_tache_cloud_v37.md` et la renommer v3.7. Décaler son heure si besoin : l'Action publie vers 08:15 Paris, la tâche doit passer après.
3. Optionnel : renseigner le jackpot officiel via `Run workflow` → `jackpot_meur` quand l'estimation API (report du dernier jackpot) est trop basse pour déclencher la 3e grille (seuil 100 M€).

---

> ⚠️ **Claude ne prédit pas les tirages. Le hasard est sans mémoire. Aucune analyse ne garantit un gain. EV nette structurellement négative (~−1,42 €/grille). Les edges backtestés et percentiles Monte-Carlo peuvent être du bruit statistique — méthodologie documentée, pas un oracle.**
