# QSC v3.6 — Rapport d'application (01/08/2026)

> ⚠️ **Claude ne prédit pas les tirages. Le hasard est sans mémoire. Aucune analyse ne garantit un gain. EV nette structurellement négative (~−1,42 €/grille). Les edges backtestés et percentiles Monte-Carlo peuvent être du bruit statistique — méthodologie documentée, pas un oracle.**

## Ce qui a été appliqué (état réel, vérifié)

| Spec | Statut | Preuve |
|---|---|---|
| #1 Chaîne de données (source 2 : API) | ✅ Fait | 1 968 tirages chargés (13/02/2004 → 31/07/2026), 1 seul retry 429 |
| #2 Validation d'intégrité (5 contrôles) | ✅ Fait | Intégrité OK, zéro alerte ; hash cf6f7f8716da |
| #3 IC95% bootstrap sur chaque écart | ✅ Fait | 10 000 itérations, colonne IC dans le dry-run |
| #4 Verdict "aucun modèle ne se distingue" | ✅ Fait — et déclenché | Voir dry-run ci-dessous |
| #5 Test de permutation global | ✅ Fait | p = 0,89 |
| #6 Catalogue typé selector/diagnostic/filter | ✅ Fait | 7 selectors, 1 diagnostic, 1 filter |
| #7 Consensus corrigée (max(écart,0)+ε, dégénérescence) | ✅ Fait | Testé (dégénère bien si tous écarts ≤0) |
| #8 P(≥1 match) exacte + relabel MC | ✅ Fait | **Correction : 42,3 %** (1−C(45,5)/C(50,5)=0,4234), pas 42,6 % comme écrit dans la spec |
| #9 Anti-partage sourcé (score continu, étoiles, co-gagnants) | ✅ Fait | Table de popularité Baker & McHale / McHale (proxy UK) |
| #10 Module + tests unitaires | ✅ Fait | `qsc_v36.py` + `test_qsc_v36.py` : **34/34 tests verts** |
| #11 Seed = date du tirage | ✅ Fait | `seed_from_draw_date("2026-08-04") = 20260804` |
| #12 Registre append-only | ✅ Fait | `/areas/qsc-registre.md` créé en mémoire Cowork, run du 31/07 loggé |
| #13 Rapprochement du run précédent | ✅ Fait — premier rapprochement réel | Voir ci-dessous |
| #15 Rotation narrative | ✅ Amorcé | Lag/retard inéligible comme porteur #1 au prochain run (dans le registre) |
| #18 Lexique + checklist automatisée | ✅ Fait | Fonction `checklist()` dans le module + §LEXIQUE dans le prompt |
| **Tâche planifiée mise à jour** | ✅ Fait | "QSC EuroMillions v3.6 - Tirage jour (mar/ven)", prochain run mardi 04/08 12h05 Paris |
| #14 Tableau de bord cumulatif | ⏳ Prochains runs | Se nourrit du registre (2 grilles au compteur) |
| #16/#17 Badges + histogramme MC + responsive | ⏳ Prochain run | Spécifiés dans le prompt v3.6, seront produits au run du 04/08 |
| #1 complet (dépôt Git) | ⏳ Session locale requise | Seul item nécessitant Charles : créer le dépôt et y pousser CSV + module |

## Premier rapprochement réel (spec #13) — run du 31/07/2026

Tirage réel du 31/07 : **10 - 24 - 25 - 31 - 45, étoiles 4 - 5** (l'API l'avait déjà intégré).

| Grille jouée | Numéros | Étoiles | Résultat |
|---|---|---|---|
| G1 (Lag/retard) | 11-15-27-32-50 | 3-7 | **0 numéro, 0 étoile** |
| G2 (Markov) | 7-14-19-37-46 | 5-6 | **0 numéro, 1 étoile** (aucun gain) |

Cumul protocole-vs-hasard : 0 match numéros sur 2 grilles, espérance théorique 1,0 — écart −1,0, n=2, aucune conclusion possible (et il n'y en aura jamais d'autre attendue que la convergence vers zéro écart).

Illustration involontaire mais parfaite : la G2 était au "90e percentile Monte-Carlo" du run v3.5 et a fait zéro numéro — le fit rétrospectif ne prédit rien, comme la v3.6 l'affiche désormais explicitement.

## Dry-run pleine puissance — le résultat central du chantier

Backtest walk-forward **burn-in 150 / step 8 sur 1 968 tirages** (228 points de test, la config spec enfin exécutable) :

| Modèle | Écart backtesté | IC95% | Verdict |
|---|---|---|---|
| Co-occurrence / graphe | +0,066 | [−0,022 ; +0,162] | ns |
| Chaînes de Markov | +0,048 | [−0,044 ; +0,145] | ns |
| Momentum | +0,044 | [−0,040 ; +0,123] | ns |
| Fréquence globale | +0,026 | [−0,057 ; +0,114] | ns |
| Dirichlet-multinomial | +0,026 | [−0,057 ; +0,114] | ns |
| Fenêtres glissantes | +0,018 | [−0,070 ; +0,105] | ns |
| Lag / retard normalisé | −0,031 | [−0,110 ; +0,053] | ns |

p-value de permutation globale : **0,89**. Verdict automatique déclenché : *"Aucun modèle ne se distingue du hasard sur cet échantillon — le choix des porteurs est méthodologique, pas inférentiel."* χ² d'uniformité sur 1 968 tirages : 52,3 (ddl 49), p≈0,35 — aucun biais matériel.

À noter, la démonstration la plus parlante du chantier : le classement sur historique complet est **presque l'inverse** du classement du 31/07 sur 50 tirages (Lag/retard, "mieux classé" vendredi, est dernier sur 1 968 tirages ; Co-occurrence, écarté vendredi, est premier). Deux classements opposés selon la fenêtre = la preuve concrète que ces classements sont du bruit — exactement ce que les IC affichent désormais.

## Ce qu'il reste à faire (toi, Charles — 10 minutes en session locale)

Créer un dépôt Git (ou Gist) `qsc-euromillions` et y pousser `euromillions_MASTER.csv`, `qsc_v36.py`, `test_qsc_v36.py` (livrés avec ce rapport). Puis me donner l'URL raw dans une session : je mettrai à jour le §DONNÉES du prompt pour activer la source primaire. En attendant, la source 2 (API) suffit — le run de mardi fonctionnera en historique complet sans toi.

---

> ⚠️ **Claude ne prédit pas les tirages. Le hasard est sans mémoire. Aucune analyse ne garantit un gain. EV nette structurellement négative (~−1,42 €/grille). Les edges backtestés et percentiles Monte-Carlo peuvent être du bruit statistique — méthodologie documentée, pas un oracle.**
