# Rapport d'application — QSC EuroMillions v3.8

> ⚠️ Claude ne prédit pas les tirages. Le hasard est sans mémoire. Aucune analyse ne garantit un gain. EV nette structurellement négative (~−1,42 €/grille). Les edges backtestés et percentiles Monte-Carlo peuvent être du bruit statistique — méthodologie documentée, pas un oracle.

Chantier du 02/10/2026. Un seul objet : **mettre la sélection des grilles en accord avec le verdict du backtest.**

## Constat de départ

La v3.7 mesure correctement que ses six selectors sont indiscernables du hasard (p global ≈ 0,70, max-statistic sur null hypergéométrique exacte). Elle choisissait pourtant les numéros en **maximisant le score du porteur**, l'anti-partage n'intervenant qu'en départage et via un seuil bas (≥ 60/100). Autrement dit : critère principal = le levier dont la nullité est démontrée ; critère secondaire = le seul levier qui ait une valeur, le partage conditionnel au gain.

Trois défauts annexes relevés à la relecture :

- des contraintes dures (somme 95-155, 2-3 pairs, 2-3 bas, écart ≥ 3) héritées du folklore de la « grille équilibrée », qui poussent vers des formes ressemblant à ce que les joueurs choisissent ;
- à la génération, les modèles étoiles comptaient tout l'historique avec un pool de 12, pénalisant structurellement 10-12 (absentes avant 2016) — le backtest, lui, était correct ; deux grilles d'un même run pouvaient partager la même paire (4-12 dans 7 lignes sur 23 du registre) ;
- co-gagnants attendus calculés sans normalisation (table UK de moyenne 1,15, soit un facteur ~1,9) et sans les étoiles.

## Changements

| | v3.7 | v3.8 |
|---|---|---|
| **D1 Univers** | top-16 numéros du porteur, puis filtres | décile le moins populaire des C(50,5) = 2 118 760 grilles (seuil de popularité moyenne 0,886 vs 1,15 pour la grille moyenne), hors motifs pénalisés → 194 616 grilles |
| **D1 Critère** | (score porteur, anti-partage) | score porteur **à l'intérieur de l'univers** ; égalité → la moins populaire |
| **D2 Contraintes dures** | `hard_ok` | supprimées ; seules les pénalités de forme du modèle de popularité restent |
| **D3 Étoiles** | top-2 brut du modèle, tout l'historique | modèle calculé sur l'ère du pool uniquement ; univers = paires dans 8-12 ; pas de paire répétée dans un run |
| **D4 Co-gagnants** | `gp^5 × 25 M / C(50,5)` | popularités relatives normalisées (moyenne 1), étoiles incluses ; nouveau champ `rel_popularity` (« joueurs attendus ×k ») |
| Recouvrement entre grilles | ≤ 2, puis 3 si épuisé | identique |
| Backtest, null, max-stat, consensus, rotation, registre | — | **inchangés** |

Rien n'est ajouté côté modèles : la mesure dit que c'est du bruit, on n'en rajoute pas.

## Effet mesuré sur le run du 02/10/2026 (seed 20261002, 1 985 tirages)

| | Grilles | Anti-partage | Joueurs attendus (× grille moyenne) | Co-gagnants attendus rang 1 |
|---|---|---|---|---|
| v3.7 | 13 16 23 28 44 ★10 12 · 10 19 23 39 50 ★05 09 | 70,7 · 70,3 | ×0,55 · ×0,57 | 0,099 · 0,101 |
| v3.8 | 12 33 37 42 44 ★09 12 · 19 23 39 43 50 ★10 12 | 91,2 · 88,1 | ×0,12 · ×0,15 | 0,021 · 0,028 |

Sur les 23 grilles du registre (v3.6/v3.7), le facteur « joueurs attendus » moyen était ×0,53. Le gain est donc d'un facteur 3 à 5 sur le partage attendu **si** le proxy UK décrit correctement les joueurs FDJ — ce qui reste l'hypothèse la plus fragile du protocole (voir suite).

Backtest numéros : strictement identique (D1-D4 ne touchent pas à l'évaluation). Backtest étoiles : la correction d'ère fait passer « fréquence » de −0,002 à +0,021 (p corrigé 0,12) — toujours non significatif, c'est le biais structurel qui disparaît, pas un signal qui apparaît.

Tests : 75/75 (`test_qsc_v38.py`). Pipeline complet : ~75 s. Checklist verte.

## Ce que ça change pour le joueur, et ce que ça ne change pas

- Probabilité de gagner : **inchangée**, 1/139 838 160 au rang 1 pour toute grille.
- Partage attendu en cas de gain : réduit, d'après le proxy.
- Allure des grilles : systématiquement chargée en 32-50, étoiles 8-12. C'est la conséquence directe du modèle de popularité ; une grille « déséquilibrée » n'est ni plus ni moins probable qu'une autre.

## Suite logique (non faite)

- **R5** — registre en euros : mapping matches → rang → gain réel du tirage (l'API fournit `prizes`), pour mesurer le coût réel du protocole plutôt que des numéros trouvés.
- **R7** — remplacer le proxy UK par une estimation FDJ : le nombre de gagnants par rang à chaque tirage, comparé à l'attendu sous jeu uniforme, mesure la popularité de la combinaison tirée. C'est le seul apprentissage qui ait un sens dans ce jeu : il porte sur les autres joueurs, pas sur les boules.
- **R4** — retirer le percentile Monte-Carlo des cartes de grille (mesure in-sample, systématiquement flatteuse pour les grilles issues de la fréquence).

## Fichiers du chantier

`qsc_v38.py`, `test_qsc_v38.py`, `run_qsc.py`, `.github/workflows/qsc.yml` (trois crons + garde d'idempotence, voir incident du 02/10), `PROMPT_tache_cloud_v38.md`, `README.md`, ce rapport. `qsc_v37.py` et `test_qsc_v37.py` sont conservés pour référence.

> ⚠️ Claude ne prédit pas les tirages. Le hasard est sans mémoire. Aucune analyse ne garantit un gain. EV nette structurellement négative (~−1,42 €/grille). Les edges backtestés et percentiles Monte-Carlo peuvent être du bruit statistique — méthodologie documentée, pas un oracle.
