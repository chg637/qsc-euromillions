# -*- coding: utf-8 -*-
"""Tests unitaires QSC Loto v1.0."""
import math, random, itertools
from datetime import date
import qsc_loto as q
import popularite_loto as P

def run():
    T = []
    def t(name, cond): T.append((name, bool(cond)))

    # constantes
    t("C(49,5) = 1 906 884", q.N_COMBOS == 1_906_884)
    t("P rang 1 = 1/19 068 840", abs(q.P_RANG1 * 19_068_840 - 1) < 1e-12)
    t("baseline numéros = 25/49", abs(q.BASELINE - 25/49) < 1e-12)
    pmf = q.hypergeom_pmf()
    t("pmf somme 1", abs(sum(pmf) - 1) < 1e-12)
    t("pmf espérance = baseline", abs(sum(k*p for k, p in enumerate(pmf)) - q.BASELINE) < 1e-12)
    t("6 selectors", len(q.SELECTORS) == 6)
    t("3 modèles Chance", len(q.CHANCE_CATALOG) == 3)

    # calendrier
    t("lundi 2026-10-12 → lui-même", q.next_draw_date(date(2026, 10, 12)) == date(2026, 10, 12))
    t("mardi 2026-10-13 → mercredi 14", q.next_draw_date(date(2026, 10, 13)) == date(2026, 10, 14))
    t("jeudi 2026-10-15 → samedi 17", q.next_draw_date(date(2026, 10, 15)) == date(2026, 10, 17))
    t("dimanche 2026-10-18 → lundi 19", q.next_draw_date(date(2026, 10, 18)) == date(2026, 10, 19))
    t("seed", q.seed_from_draw_date("2026-10-14") == 20261014)

    # nombre de grilles
    t("n_grids(2) = 3", q.n_grids(2) == 3)
    t("n_grids(19) = 3", q.n_grids(19) == 3)
    t("n_grids(20) = 4", q.n_grids(20) == 4)
    t("plancher relève", q.n_grids(2, plancher=5) == 5)
    t("plancher ne réduit pas", q.n_grids(30, plancher=1) == q.n_grids(30))

    # popularité : proxy, table, univers
    t("source par défaut = proxy", "proxy" in q.POP["source"])
    t("moyenne 1 (numéros)", abs(sum(q.popularity(n) for n in q.ALL_NUMS)/49 - 1) < 1e-12)
    t("moyenne 1 (Chance)", abs(sum(q.chance_popularity(c) for c in q.ALL_CHANCE)/10 - 1) < 1e-12)
    U, thr, n_tot = q.impopular_universe()
    t("univers énuméré", n_tot == q.N_COMBOS)
    t("univers ~10 %", 0.06 < len(U)/n_tot < 0.11)
    t("univers trié", all(q.relative_popularity(U[i]) <= q.relative_popularity(U[i+1]) + 1e-9 for i in range(0, 3000, 11)))
    t("univers sans motif pénalisé", all(q.shape_penalty(g) == 0 for g in U[:5000]))
    t("grille anniversaires exclue", (3, 7, 12, 19, 27) not in set(U))
    t("Chance univers = 3 moins joués", len(q.chance_universe()) == 3)
    t("percentile dans [0,100]", 0 <= q.anti_share_score((1, 2, 3, 4, 5)) <= 100)
    t("percentile grille 41-49 > 97", q.anti_share_score((41, 43, 44, 46, 48)) > 97)
    flat = {"source": "plat", "nums": {n: 1.0 for n in q.ALL_NUMS}, "chance": {c: 1.0 for c in q.ALL_CHANCE}}
    q.set_popularity(flat)
    t("table plate : cache invalidé", q.impopular_universe()[0] is not U)
    t("table plate : relative_popularity = 1", abs(q.relative_popularity((1, 2, 3, 4, 5), 7) - 1) < 1e-12)
    inv = {"source": "inv", "nums": {n: (2.0 if n > 40 else 1.0) for n in q.ALL_NUMS}, "chance": {c: (2.0 if c >= 8 else 1.0) for c in q.ALL_CHANCE}}
    q.set_popularity(inv)
    t("table inversée : 41-49 hors univers", all(not any(n > 40 for n in g) for g in q.impopular_universe()[0][:3000]))
    t("table inversée : Chance 8-10 hors univers", all(c < 8 for c in q.chance_universe()))
    try:
        q.set_popularity({"source": "x", "nums": {1: 1.0}, "chance": {}}); bad = False
    except ValueError:
        bad = True
    t("table incomplète refusée", bad)
    q.set_popularity(None)

    # données synthétiques : backtest non significatif, consensus dégénère, sélection dans l'univers
    rng = random.Random(7); synth = []; d0 = date(2017, 3, 6)
    for i in range(600):
        synth.append((str(d0.fromordinal(d0.toordinal()+2*i)), tuple(sorted(rng.sample(q.ALL_NUMS, 5))), rng.choice(q.ALL_CHANCE)))
    bt, meta = q.backtest_all(synth, burn_in=100, step=4, n_sim=300, seed=3)
    t("aléatoire : p_global non significatif", meta["p_global"] > 0.05)
    t("consensus dégénère", q.consensus_grid(bt, synth) is None)
    sb, sm = q.backtest_chance(synth, burn_in=100, step=4, n_sim=300, seed=3)
    t("backtest Chance : 3 modèles", len(sb) == 3 and all(r["n"] > 0 for r in sb.values()))
    U = q.impopular_universe()[0]
    g1 = q.best_grid("Momentum", synth); g2 = q.best_grid("Momentum", synth, avoid=[g1])
    t("best_grid dans l'univers", g1 in set(U) and g2 in set(U))
    t("recouvrement ≤ 2", q.overlap(g1, g2) <= 2)
    c1 = q.best_chance("Chance — lag", synth); c2 = q.best_chance("Chance — lag", synth, avoid=[c1])
    t("Chance dans l'univers, pas de doublon", c1 in q.chance_universe() and c2 in q.chance_universe() and c1 != c2)
    order = q.rank_selectors({"A": {"edge": .3}, "B": {"edge": .2}, "C": {"edge": .1}}, ineligible_first="A")
    t("rotation", order[:2] == ["B", "A"])

    # intégrité
    t("intégrité synthétique", q.integrity_check(synth)[1] == ["profondeur faible: 600 tirages"])
    t("Chance hors bornes détectée", any("Chance" in a for a in q.integrity_check([("2026-01-05", (1, 2, 3, 4, 5), 11)])[1]))

    # estimateur : recouvre des effets connus (règle 2017+, 9 rangs)
    rho = {n: 1 + 0.2 * math.sin(n) for n in q.ALL_NUMS}; rhoc = {c: 1 + 0.2 * math.cos(c) for c in q.ALL_CHANCE}
    prizes = {}
    for d, nums, ch in synth:
        bn = sum(P.SLOPE_NUMS * (rho[n] - 1) for n in nums); bc = P.SLOPE_CHANCE * (rhoc[ch] - 1)
        w2 = 500_000; w3 = w2 * math.exp(math.log(10*math.comb(44, 2)/(10*math.comb(44, 3))) + bn + rng.gauss(0, .01))
        r = math.exp(math.log(1/9) + bc + rng.gauss(0, .01))   # (k+C)/(k)
        prizes[d] = {"era": 9, "rapport1": 2e6, "w": {1: 0, 2: 1, 3: int(600*r), 4: 600, 5: int(w3*r), 6: int(w3), 7: int(w2*r), 8: int(w2), 9: 50_000}}
    fn = P.fit_numbers(prizes, synth); fc = P.fit_chance(prizes, synth)
    t("fit numéros : 600 points", fn is not None and fn["n_draws"] == 600)
    t("fit numéros : ρ à ±0,06", max(abs(fn["rho"][n] - rho[n]) for n in q.ALL_NUMS) < 0.06)
    t("fit Chance : 600 points", fc is not None and fc["n_draws"] == 600)
    t("fit Chance : ρ à ±0,05", max(abs(fc["rho"][c] - rhoc[c]) for c in q.ALL_CHANCE) < 0.05)
    t("fichier absent → None", P.estimate("/nonexistent.csv", synth) is None)

    # checklist
    fp = {"n": 2819}; html = q.DISCLAIMER + q.EQUIVALENCE + " 2819 seed 20261014"; chat = q.DISCLAIMER + " .. " + q.DISCLAIMER
    t("checklist passe", q.checklist(html, chat, fp, 20261014)[0])
    t("checklist bloque lexique", not q.checklist(html + " numéro gagnant", chat, fp, 20261014)[0])

    passed = sum(1 for _, ok in T if ok)
    for name, ok in T: print(("PASS" if ok else "FAIL"), name)
    print(f"\n{passed}/{len(T)} tests OK")
    return passed == len(T)

if __name__ == "__main__":
    import sys; sys.exit(0 if run() else 1)
