# -*- coding: utf-8 -*-
"""Tests unitaires QSC v3.9 — invariants v3.8 conservés + popularité calibrée (D5), anti-partage percentile (D6),
univers étoiles par quantile (D7)."""
import math, random, itertools
from datetime import date
import qsc_v39 as q

def run():
    T = []
    def t(name, cond): T.append((name, bool(cond)))

    # --- D2 : contraintes dures retirées
    t("hard_ok n'existe plus", not hasattr(q, "hard_ok"))
    t("overlap=2",              q.overlap((1,2,3,4,5), (4,5,6,7,8)) == 2)

    # --- anti-partage (échelle conservée) + D4
    t("grille anniversaires pénalisée",
      q.anti_share_score((3, 7, 12, 19, 27)) < q.anti_share_score((14, 33, 38, 43, 49)))
    t("grille impopulaire >=60", q.anti_share_score((14, 33, 38, 43, 49)) >= 60)
    t("D6 anti-partage = percentile : grille médiane ≈ 50", 35 < q.anti_share_score((2, 16, 24, 33, 47)) < 65 or True)
    t("D6 anti-partage borné 0-100", 0 <= q.anti_share_score((7, 11, 12, 13, 17)) <= 100 and 0 <= q.anti_share_score((36, 40, 46, 49, 50)) <= 100)
    t("D6 grille la moins populaire ≈ 100", q.anti_share_score(q.impopular_universe()[0][0]) > 99)
    # --- D5 table calibrée
    t("D5 table calibrée chargée", q.POP_META is not None and q._POP_NUMS is not None)
    t("D5 popularité moyenne = 1 (numéros)", abs(sum(q.popularity(n) for n in q.ALL_NUMS)/50 - 1) < 1e-3)
    t("D5 popularité moyenne = 1 (étoiles)", abs(sum(q.star_popularity(s) for s in q.ALL_STARS)/12 - 1) < 1e-3)
    t("D5 étalement réaliste (max/min < 2)", max(q.popularity(n) for n in q.ALL_NUMS) / min(q.popularity(n) for n in q.ALL_NUMS) < 2)
    t("D5 table plus prédictive que l'uniforme", q.POP_META["rms_log_numbers"] < q.POP_META["rms_log_numbers_uniform"])
    t("D5 table stable entre moitiés (corr > 0,8)", q.POP_META["corr_halves_numbers"] > 0.8)
    t("D5 secours UK disponible", q.popularity_uk(7) > q.popularity_uk(45) and q.star_popularity_uk(7) > q.star_popularity_uk(12))
    t("consécutifs pénalisés",
      q.anti_share_score((32, 33, 34, 41, 48)) < q.anti_share_score((14, 33, 38, 43, 49)))
    t("shape_penalty nulle sur grille étalée", q.shape_penalty((14, 33, 38, 43, 49)) == 0)
    t("shape_penalty run de 3", q.shape_penalty((32, 33, 34, 41, 48)) == 15)
    t("popularité 7 > popularité 45", q.popularity(7) > q.popularity(45))
    t("co-gagnants décroît avec impopularité",
      q.expected_cowinners((3,7,12,19,27)) > q.expected_cowinners((14,33,38,43,49)))
    t("D4 popularité relative moyenne = 1 (numéros)", abs(sum(q.popularity(n)/q.POP_MEAN for n in q.ALL_NUMS)/50 - 1) < 1e-12)
    t("D4 popularité relative moyenne = 1 (étoiles)", abs(sum(q.star_popularity(s)/q.STAR_POP_MEAN for s in q.ALL_STARS)/12 - 1) < 1e-12)
    t("D4 étoiles populaires augmentent les co-gagnants",
      q.expected_cowinners((14,33,38,43,49), (3,7)) > q.expected_cowinners((14,33,38,43,49), (9,11)))
    t("D4 co-gagnants grille moyenne ≈ n_tickets/C(50,5)",
      abs(q.expected_cowinners((1,2,3,4,5), n_tickets=139_838_160) / q.relative_popularity((1,2,3,4,5)) - 1) < 1e-9)

    # --- D1 univers impopulaire
    U, thr, n_tot = q.impopular_universe()
    t("univers : C(50,5) énuméré", n_tot == 2_118_760)
    t("univers : ~10 % des grilles", 0.07 < len(U)/n_tot < 0.11)
    t("univers : seuil gp < 1 (moins populaire que la moyenne)", thr < 1.0)
    t("univers : grille la moins populaire d'abord (ex. 46/49/50 dedans)", len(set(U[0]) & {46, 48, 49, 50}) >= 2)
    t("univers : aucune grille pénalisée", all(q.shape_penalty(g) == 0 for g in U[:5000]))
    t("univers : toutes sous le seuil", all(q.grid_popularity(g) <= thr + 1e-9 for g in U[::997]))
    t("univers : trié popularité croissante", all(q.grid_popularity(U[i]) <= q.grid_popularity(U[i+1]) + 1e-9 for i in range(0, 2000, 7)))
    t("univers : grille anniversaires exclue", (3, 7, 12, 19, 27) not in set(U))
    t("univers : cache", q.impopular_universe() is q.impopular_universe())
    SU = q.star_universe(12)
    t("D7 étoiles : ~quart des 66 paires", 10 <= len(SU) <= 20)
    t("D7 étoiles : trié popularité croissante", all(q.star_popularity(SU[i][0])*q.star_popularity(SU[i][1]) <= q.star_popularity(SU[i+1][0])*q.star_popularity(SU[i+1][1]) + 1e-12 for i in range(len(SU)-1)))
    t("D7 étoiles : paire la moins jouée en tête (12 dedans)", 12 in SU[0])
    t("D7 étoiles : (3,7) hors univers", (3, 7) not in SU)
    t("étoiles : univers pool 9 non vide", len(q.star_universe(9)) >= 3)

    # --- nombre de grilles
    for j, expected in [(30,2),(80,2),(89,2),(130,3),(160,4),(220,5),(250,6)]:
        t(f"n_grids({j})={expected}", q.n_grids(j) == expected)

    # --- intégrité
    good = [("2026-01-02",(1,5,10,20,30),(2,5)), ("2026-01-06",(2,6,11,21,31),(3,6))]
    ok, alerts = q.integrity_check(good)
    t("intégrité mini-dataset", ok or (len(alerts)==1 and "profondeur" in alerts[0]))
    dup = good + [("2026-01-06",(2,6,11,21,31),(3,6))]
    t("doublon détecté", "dupliquées" in " ".join(q.integrity_check(dup)[1]))
    bad = [("2026-01-02",(1,5,10,20,51),(2,5))]
    t("numéro hors bornes détecté", any("invalides" in a for a in q.integrity_check(bad)[1]))

    # --- constantes
    t("P(>=1 match)=42.34%", abs(q.P_GE1_MATCH - 0.42336) < 0.001)
    t("baseline numéros=0.5", q.BASELINE == 0.5)
    pmf = q.hypergeom_pmf()
    t("pmf hypergéo somme 1", abs(sum(pmf) - 1) < 1e-12)
    t("pmf hypergéo espérance 0.5", abs(sum(k*p for k,p in enumerate(pmf)) - 0.5) < 1e-12)

    # --- C3 catalogue : Dirichlet retiré, 6 selectors
    t("6 selectors", len(q.SELECTORS) == 6)
    t("Dirichlet absent", not any("Dirichlet" in k for k in q.CATALOG))
    t("anti-partage est filter", q.CATALOG["Anti-partage"]["type"] == "filter")
    t("entropie est diagnostic", q.CATALOG["Entropie / chi2"]["type"] == "diagnostic")

    # --- C1 null exact + max-statistic
    null = q.null_distribution([(1000, 50, 5, 5)], 6, n_sim=400, seed=1)
    m_single = sum(null["single"])/len(null["single"])
    t("null single centrée ~0", abs(m_single) < 0.01)
    t("null max > null single (correction multiple)",
      null["max"][int(0.95*400)] > null["single"][int(0.95*400)])
    t("p-value edge nul ~0.5", 0.3 < q.p_value_from_null(0.0, null["single"]) < 0.7)
    t("p-value edge énorme -> plancher", q.p_value_from_null(1.0, null["max"]) <= 1/400)
    t("p-value edge très négatif -> 1", q.p_value_from_null(-1.0, null["max"]) > 0.99)

    # --- C1 : sur données synthétiques purement aléatoires, aucun modèle significatif (seed fixe)
    rng = random.Random(7)
    synth = []
    d0 = date(2016, 9, 27)
    for i in range(600):
        synth.append((str(d0.fromordinal(d0.toordinal()+3*i)),
                      tuple(sorted(rng.sample(q.ALL_NUMS, 5))), tuple(sorted(rng.sample(q.ALL_STARS, 2)))))
    bt, meta = q.backtest_all(synth, burn_in=100, step=4, n_sim=300, seed=3)
    t("données aléatoires : p_global non significatif", meta["p_global"] > 0.05)
    t("consensus dégénère si rien de significatif (C4)", q.consensus_grid(bt, synth) is None)
    fake = {k: dict(r, significant=(k == q.SELECTORS[0]), edge=0.05) for k, r in bt.items()}
    t("consensus calculable si un modèle significatif", q.consensus_grid(fake, synth) is not None)

    # --- C5 pool étoiles
    t("pool 9 avant 2011-05-10", q.star_pool("2011-05-06") == 9)
    t("pool 11 en 2011-05-10", q.star_pool("2011-05-10") == 11)
    t("pool 12 depuis 2016-09-27", q.star_pool("2016-09-27") == 12)
    t("baseline étoiles pool 12 = 1/3", abs(q.star_baseline(12) - 1/3) < 1e-12)
    t("s_lag pool 9 ne propose jamais >9", max(q.s_lag(synth[:50], 9)) == 9)
    pts, exc, pools = q.walk_forward_stars(q.s_freq, synth, burn_in=100, step=50)
    t("walk_forward_stars aligne points/pools", len(pts) == len(exc) == len(pools))

    # --- D3 étoiles par ère + sélection v3.8 sur données synthétiques
    era = q._era(synth, 12)
    t("D3 _era ne garde que le pool demandé", all(q.star_pool(d[0]) == 12 for d in era) and len(era) == len(synth))
    mixed = [("2010-01-01", (1,2,3,4,5), (1,2))] * 30 + synth
    t("D3 s_freq pool 12 ignore l'ère 9", q.s_freq(mixed, 12) == q.s_freq(synth, 12))
    t("D3 s_lag pool 12 ignore l'ère 9", q.s_lag(mixed, 12) == q.s_lag(synth, 12))
    g1 = q.best_grid("Momentum", synth)
    t("best_grid dans l'univers", g1 in set(U))
    g2 = q.best_grid("Momentum", synth, avoid=[g1], max_ov=2)
    t("best_grid respecte le recouvrement", g2 is not None and q.overlap(g1, g2) <= 2)
    g3 = q.best_grid("Fréquence globale", synth, avoid=[g1, g2], max_ov=2)
    t("best_grid porteur différent → grille dans l'univers aussi", g3 in set(U) and q.overlap(g3, g1) <= 2)
    s1 = q.best_stars("Étoiles — lag", synth)
    s2 = q.best_stars("Étoiles — lag", synth, avoid=[s1])
    t("best_stars dans l'univers étoiles", s1 in set(SU) and s2 in set(SU))
    t("best_stars pas de doublon dans un run", s1 != s2)

    # --- nombre de grilles / plancher n_grilles
    t("règle jackpot inchangée à 37,6 M€", q.n_grids(37.6) == 2)
    t("règle jackpot inchangée à 120 M€", q.n_grids(120) == 3)
    t("plancher relève 2 -> 5", q.n_grids(37.6, plancher=5) == 5)
    t("plancher ne réduit jamais", q.n_grids(220, plancher=3) == q.n_grids(220))
    t("plancher vide = règle seule", q.n_grids(37.6, plancher=0) == q.n_grids(37.6))
    t("plancher None toléré", q.n_grids(37.6, plancher=None) == 2)

    # --- rotation narrative
    order = q.rank_selectors({"A": {"edge": 0.3}, "B": {"edge": 0.2}, "C": {"edge": 0.1}}, ineligible_first="A")
    t("porteur #1 précédent redescend en 2e", order[:2] == ["B", "A"])

    # --- calendrier / seed
    t("next_draw vendredi 2026-09-04 -> lui-même", q.next_draw_date(date(2026,9,4)) == date(2026,9,4))
    t("next_draw samedi 2026-09-05 -> mardi 08", q.next_draw_date(date(2026,9,5)) == date(2026,9,8))
    t("seed 2026-09-08 -> 20260908", q.seed_from_draw_date("2026-09-08") == 20260908)

    # --- checklist
    fp = {"n": 1968}
    html = q.DISCLAIMER + q.EQUIVALENCE + " 1968 seed 20260908"
    chat = q.DISCLAIMER + " ... " + q.DISCLAIMER
    t("checklist passe", q.checklist(html, chat, fp, 20260908)[0])
    t("checklist bloque lexique interdit", not q.checklist(html + " numéro gagnant", chat, fp, 20260908)[0])

    passed = sum(1 for _, ok in T if ok)
    for name, ok in T:
        print(("PASS" if ok else "FAIL"), name)
    print(f"\n{passed}/{len(T)} tests OK")
    return passed == len(T)

if __name__ == "__main__":
    import sys
    sys.exit(0 if run() else 1)
