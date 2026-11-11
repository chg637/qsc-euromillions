# -*- coding: utf-8 -*-
"""Tests unitaires QSC Loto v2.0 — invariants v1.0 conservés + tirage uniforme dans l'univers (A1), règle de mise
1/2/3/4 sous budget commun (A2), jackpot fdj.fr (A3), rangs et registre en euros (A4), EV (A5)."""
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

    # nombre de grilles (A2) : 1 / 2 / 3 / 4 aux paliers 100, 150, 200 M€, borné par le budget commun
    t("n_grids_regle(13) = 1", q.n_grids_regle(13) == 1)
    t("n_grids_regle(30) = 1 (maximum historique)", q.n_grids_regle(30) == 1)
    t("n_grids_regle(100) = 2", q.n_grids_regle(100) == 2)
    t("n_grids_regle(150) = 3", q.n_grids_regle(150) == 3)
    t("n_grids_regle(200) = 4", q.n_grids_regle(200) == 4)
    t("plancher relève", q.n_grids(13, plancher=3) == 3)
    t("plancher ne réduit pas", q.n_grids(150, plancher=1) == 3)
    t("budget : reste 2 grilles", q.n_grids(200, depense_annee=515.6) == 2)
    t("budget : atteint → 0 grille", q.n_grids(13, depense_annee=519.0) == 0)
    t("budget : exactement 1 grille de reste", q.n_grids(13, depense_annee=517.8) == 1)
    t("budget par défaut = 520 €", q.BUDGET_EUR == 520.0 and q.PRIX_GRILLE == 2.20)
    t("plancher borné par le budget", q.n_grids(13, plancher=5, depense_annee=515.6) == 2)

    # rangs, ventes, EV (A4, A5)
    t("rang_of : 5+C = 1", q.rang_of(5, 1) == 1)
    t("rang_of : 5 = 2", q.rang_of(5, 0) == 2)
    t("rang_of : 4+C = 3, 4 = 4", q.rang_of(4, 1) == 3 and q.rang_of(4, 0) == 4)
    t("rang_of : 3+C = 5, 3 = 6", q.rang_of(3, 1) == 5 and q.rang_of(3, 0) == 6)
    t("rang_of : 2+C = 7, 2 = 8", q.rang_of(2, 1) == 7 and q.rang_of(2, 0) == 8)
    t("rang_of : Chance avec 0 ou 1 numéro = 9", q.rang_of(0, 1) == 9 and q.rang_of(1, 1) == 9)
    t("rang_of : rien = 0", q.rang_of(0, 0) == 0 and q.rang_of(1, 0) == 0)
    pr = q.p_of_rank()
    t("p rang 1 = P_RANG1", abs(pr[1] - q.P_RANG1) < 1e-15)
    t("p rangs 1-9 = 1 - P(aucun gain)", abs(sum(pr.values()) - (1 - 0.9 * (q._PK[0] + q._PK[1]))) < 1e-12)
    t("p rang 2 = 9 × p rang 1", abs(pr[2] - 9 * pr[1]) < 1e-15)
    W = {5: int(3.9e6 * pr[5]), 6: int(3.9e6 * pr[6]), 7: int(3.9e6 * pr[7]), 8: int(3.9e6 * pr[8]), 9: int(3.9e6 * pr[9])}
    t("ventes estimées à 1 % près", abs(q.ventes_estimees(W) / 3.9e6 - 1) < 0.01)
    t("ventes : données insuffisantes → None", q.ventes_estimees({8: 1000}) is None)
    amts = {2: 178163.8, 3: 1672.5, 4: 494.7, 5: 50.0, 6: 24.4, 7: 9.0, 8: 4.6, 9: 2.2}
    t("EV rangs bas ≈ 0,84 € (montants du 04/11/2026)", abs(q.ev_rangs_bas(amts) - 0.842) < 0.01)
    t("EV croît avec le jackpot", q.ev_grille(13, 1.0) < q.ev_grille(20, 1.0) < q.ev_grille(30, 1.0))
    t("EV nette négative à 2 M€ et 13 M€", q.ev_grille(2, 1.0) < -1.2 and q.ev_grille(13, 1.0) < -0.6)
    t("EV nette proche de zéro à 30 M€ (|EV| < 0,3)", abs(q.ev_grille(30, 1.0)) < 0.3)
    t("EV : grille moins jouée > grille moyenne", q.ev_grille(20, 0.5) > q.ev_grille(20, 1.0))
    t("EV : plus de ventes → moins de gain", q.ev_grille(30, 1.0, ventes=9e6) < q.ev_grille(30, 1.0, ventes=3.9e6))

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

    # données synthétiques : backtest non significatif ; sélection uniforme dans l'univers (A1)
    rng = random.Random(7); synth = []; d0 = date(2017, 3, 6)
    for i in range(600):
        synth.append((str(d0.fromordinal(d0.toordinal()+2*i)), tuple(sorted(rng.sample(q.ALL_NUMS, 5))), rng.choice(q.ALL_CHANCE)))
    bt, meta = q.backtest_all(synth, burn_in=100, step=4, n_sim=300, seed=3)
    t("aléatoire : p_global non significatif", meta["p_global"] > 0.05)
    t("verdict : plus de porteur", "porteur" not in q.verdict(bt, meta))
    sb, sm = q.backtest_chance(synth, burn_in=100, step=4, n_sim=300, seed=3)
    t("backtest Chance : 3 modèles", len(sb) == 3 and all(r["n"] > 0 for r in sb.values()))
    for gone in ("best_grid", "best_chance", "consensus_grid", "rank_selectors", "n_grids_v1"):
        t(f"{gone} n'existe plus", not hasattr(q, gone))
    U = q.impopular_universe()[0]; CU = q.chance_universe()
    G = q.draw_grids(20261107, 3)
    t("draw_grids : 3 grilles", len(G) == 3)
    t("draw_grids : dans l'univers", all(g in set(U) for g, _ in G))
    t("draw_grids : Chance dans l'univers Chance", all(c in CU for _, c in G))
    t("draw_grids : recouvrement ≤ 2", all(q.overlap(G[i][0], G[j][0]) <= 2 for i in range(3) for j in range(i+1, 3)))
    t("draw_grids : Chance distinctes (3 grilles, univers de 3)", len({c for _, c in G}) == 3)
    t("draw_grids : déterministe pour une seed", G == q.draw_grids(20261107, 3))
    t("draw_grids : la seed change les grilles", G != q.draw_grids(20261110, 3))
    t("draw_grids : 4 grilles malgré 3 Chance", len(q.draw_grids(1, 4)) == 4)
    t("draw_grids : n=0 → vide", q.draw_grids(1, 0) == [])
    firsts = [q.draw_grids(s, 1)[0][0] for s in range(2000)]
    t("draw_grids : tirage varié (≥ 1 900 grilles distinctes sur 2 000 seeds)", len(set(firsts)) > 1900)
    t("draw_grids : accepte univers et Chance injectés", q.draw_grids(5, 1, universe=U[:50], chance_univ=[4])[0][1] == 4)

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

    # --- runner : registre en euros, jackpot fdj.fr, budget commun
    import run_loto as R
    rows = [{"run_date": "2026-11-04", "draw_date": "2026-11-04", "grid": "1", "model": "x", "nums": "2-7-11-30-41",
             "chance": "7", "seed": "20261104", "jackpot_meur": "12", "real_nums": "", "real_chance": "", "match_nums": "",
             "match_chance": "", "rang": "", "gain_eur": "", "gagnants_rang": "", "gagnants_attendus_rang": ""}]
    draws_r = [("2026-11-04", (2, 7, 11, 19, 33), 7)]
    pz = {"2026-11-04": {"era": 9, "rapport1": 12e6, "w": {1: 0, 2: 1, 3: 26, 4: 317, 5: 1873, 6: 13805, 7: 28941, 8: 225683, 9: 420509}}}
    rec = R.reconcile(rows, draws_r, pz, {})
    t("reconcile : numéros/Chance trouvés sans montants", rows[0]["match_nums"] == "3" and rows[0]["match_chance"] == "1" and len(rec) == 1)
    t("reconcile : rang laissé ouvert sans montants", rows[0]["rang"] == "")
    R.reconcile(rows, draws_r, pz, {"2026-11-04": {5: 50.0, 6: 24.4}})
    t("reconcile : rang 5 (3+C)", rows[0]["rang"] == "5")
    t("reconcile : gain réel du rang", rows[0]["gain_eur"] == 50.0)
    t("reconcile : gagnants observés", rows[0]["gagnants_rang"] == 1873)
    t("reconcile : gagnants attendus > 0", float(rows[0]["gagnants_attendus_rang"]) > 0)
    t("reconcile : idempotent", R.reconcile(rows, draws_r, pz, {"2026-11-04": {5: 99.0}}) == [] and rows[0]["gain_eur"] == 50.0)
    pz6 = {"2026-11-04": {"era": 6, "rapport1": 1e6, "w": {}}}
    rows2 = [dict(rows[0], match_nums="", rang="", gain_eur="")]
    R.reconcile(rows2, draws_r, pz6, {"2026-11-04": {5: 50.0}})
    t("reconcile : règle 6 rangs → rang laissé vide", rows2[0]["rang"] == "")
    cum = R.cumul(rows, 2026, autre_depense=100.0)
    t("cumul : mise 2,20 €", cum["mise_eur"] == 2.2 and cum["gains_eur"] == 50.0)
    t("cumul : budget commun (Loto + EuroMillions)", cum["depense_annee_eur"] == 102.2 and cum["depense_autres_jeux_eur"] == 100.0)
    t("cumul : partage observé", cum["taux_partage"] is not None and cum["rangs_atteints"] == 1)
    t("depense_registre : un re-run ne compte pas deux fois", R.depense_registre(rows, 2026, 2.2, hors_tirage="2026-11-04") == 0.0
      and R.depense_registre(rows, 2026, 2.2) == 2.2)
    t("depense_registre : autre année ignorée", R.depense_registre(rows, 2025, 2.2) == 0.0)
    page = "<html><head><title>LOTO® : 13\u202fM€ ce samedi 7 novembre 2026</title></head><body>Jackpot LOTO® de 13 M€</body></html>"
    t("jackpot fdj.fr : lu", R.parse_jackpot_page(page, date(2026, 11, 7)) == 13.0)
    t("jackpot fdj.fr : mauvaise date → None", R.parse_jackpot_page(page, date(2026, 11, 9)) is None)
    t("jackpot fdj.fr : hors plage → None", R.parse_jackpot_page(page.replace("13", "999"), date(2026, 11, 7)) is None)
    t("jackpot fdj.fr : décimale", R.parse_jackpot_page(page.replace("13", "7,5"), date(2026, 11, 7)) == 7.5)
    t("jackpot fdj.fr : page illisible → None", R.parse_jackpot_page("<title>Erreur</title>", date(2026, 11, 7)) is None)
    t("jackpot : override gagne", R.estimate_jackpot(None, 25, date(2026, 11, 7), use_fdj=False)["source"] == "fourni")
    t("jackpot : repli estimation", R.estimate_jackpot({"last_draw": {"date": "2026-11-04", "jackpot_eur": 12e6, "has_winner": False}}, None, date(2026, 11, 7), use_fdj=False)["meur"] == 13.0)
    t("jackpot : remis après un gagnant", R.estimate_jackpot({"last_draw": {"date": "2026-11-04", "jackpot_eur": 12e6, "has_winner": True}}, None, date(2026, 11, 7), use_fdj=False)["meur"] == 2.0)
    evb, mesure = R.ev_bas_recent({"2026-11-02": amts, "2026-11-04": amts})
    t("ev_bas_recent : médiane des montants", mesure and abs(evb - q.ev_rangs_bas(amts)) < 1e-9)
    t("ev_bas_recent : cache vide → défaut", R.ev_bas_recent({}) == (q.EV_RANGS_BAS_DEFAUT, False))
    t("registre v1.0 : colonnes absentes complétées", all(k in R.load_registre("output/registre.csv")[0] for k in R.REG_FIELDS) if __import__("os").path.exists("output/registre.csv") else True)


    # ---- v2.1 : fiabilité du run (alignement sur EuroMillions v4.1, 11/11/2026)
    t("fraîcheur : dataset à jour = 0 tirage de retard", R.retard_dataset("2026-11-09", date(2026, 11, 11)) == 0)
    t("fraîcheur : un tirage de retard", R.retard_dataset("2026-11-07", date(2026, 11, 11)) == 1)
    t("fraîcheur : trois tirages de retard", R.retard_dataset("2026-11-04", date(2026, 11, 14)) == 3)
    t("tirage précédent : samedi → mercredi", R.previous_draw_date(date(2026, 11, 14)) == date(2026, 11, 11))
    fm = {"last_draw": {"date": "2026-11-07", "has_winner": False, "jackpot_eur": 13000000.0}}
    jp1 = R.estimate_jackpot(fm, None, date(2026, 11, 11), use_fdj=False, retard=1)
    t("jackpot : estimation sur dataset en retard marquée périmée", jp1["source"] == "estimation périmée" and jp1["fiable"] is False)
    t("jackpot : estimation sur dataset à jour inchangée", R.estimate_jackpot(fm, None, date(2026, 11, 9), use_fdj=False)["source"] == "estimation")
    ligne = {"run_date": "2026-11-09", "draw_date": "2026-11-09", "grid": 1, "nums": "4-5-14-35-46", "chance": 8,
             "real_nums": "", "real_chance": "", "match_nums": "", "match_chance": "", "rang": "", "gain_eur": "",
             "gagnants_rang": "", "gagnants_attendus_rang": ""}
    tir = [("2026-11-09", (4, 5, 14, 37, 41), 8)]
    pzs = {"2026-11-09": {"era": 9, "w": {k: 1000 * k for k in range(1, 10)}, "rapport1": None}}
    rg_att = q.rang_of(3, 1)
    l1 = [dict(ligne)]
    d1 = R.reconcile(l1, tir, {}, {})
    t("rapprochement : numéros connus, rapports pas encore → rang en attente", l1[0]["match_nums"] == "3" and l1[0]["rang"] == "" and len(d1) == 1)
    d2 = R.reconcile(l1, tir, pzs, {"2026-11-09": {rg_att: 20.0}})
    t("rapprochement : gain soldé après coup annoncé au run suivant", len(d2) == 1 and d2[0]["rang"] == str(rg_att) and d2[0]["gain_eur"] == 20.0)
    l2 = [dict(ligne)]
    d3 = R.reconcile(l2, tir, pzs, {"2026-11-09": {rg_att: 20.0}})
    t("rapprochement : tout connu d'un coup → une seule ligne annoncée", len(d3) == 1)

    passed = sum(1 for _, ok in T if ok)
    for name, ok in T: print(("PASS" if ok else "FAIL"), name)
    print(f"\n{passed}/{len(T)} tests OK")
    return passed == len(T)

if __name__ == "__main__":
    import sys; sys.exit(0 if run() else 1)
