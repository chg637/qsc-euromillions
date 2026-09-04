# -*- coding: utf-8 -*-
"""
run_qsc.py — Pipeline QSC v3.7 complet, exécuté par GitHub Actions les jours de tirage.

Étapes : chargement + intégrité → rapprochement du run précédent (registre append-only)
→ backtest numéros/étoiles (step 1, null exact, max-stat) → diagnostics (chi², Monte-Carlo)
→ estimation jackpot → rotation narrative → génération des grilles → consensus (stricte)
→ latest.json / latest.html / history/<date>.json → checklist.

Usage : python3 run_qsc.py [--csv ...] [--out output] [--jackpot 95] [--today 2026-09-08]
Sortie : code 0 si checklist verte, 4 sinon (le livrable est quand même écrit, marqué KO).
"""
import argparse, csv, json, os, sys, html as H
from datetime import date
import qsc_v37 as q

# ------------------------------------------------------------------ registre

REG_FIELDS = ["run_date", "draw_date", "grid", "model", "nums", "stars", "seed",
              "real_nums", "real_stars", "match_nums", "match_stars"]

def load_registre(path):
    if not os.path.exists(path): return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter=";"))

def save_registre(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=REG_FIELDS, delimiter=";", lineterminator="\n")
        w.writeheader()
        for r in rows: w.writerow(r)

def reconcile(rows, draws):
    """Remplit les résultats des grilles dont le tirage est connu. Retourne les lignes rapprochées ce run."""
    by_date = {d: (n, s) for d, n, s in draws}
    done = []
    for r in rows:
        if r["match_nums"] == "" and r["draw_date"] in by_date:
            rn, rs = by_date[r["draw_date"]]
            gn = {int(x) for x in r["nums"].split("-")}
            gs = {int(x) for x in r["stars"].split("-")}
            r["real_nums"] = "-".join(map(str, rn)); r["real_stars"] = "-".join(map(str, rs))
            r["match_nums"] = str(len(gn & set(rn))); r["match_stars"] = str(len(gs & set(rs)))
            done.append(r)
    return done

def cumul(rows):
    played = [r for r in rows if r["match_nums"] != ""]
    n = len(played)
    mn = sum(int(r["match_nums"]) for r in played)
    ms = sum(int(r["match_stars"]) for r in played)
    return {"grilles": n, "match_nums": mn, "attendu_nums": round(q.BASELINE * n, 2),
            "ecart_nums": round(mn - q.BASELINE * n, 2),
            "match_stars": ms, "attendu_stars": round(q.star_baseline(12) * n, 2),
            "ecart_stars": round(ms - q.star_baseline(12) * n, 2),
            "meilleur": max((int(r["match_nums"]) for r in played), default=0)}

# ------------------------------------------------------------------ jackpot

def estimate_jackpot(api_meta, override):
    if override is not None:
        return {"meur": float(override), "source": "fourni", "note": "montant officiel fourni au run"}
    last = (api_meta or {}).get("last_draw") or {}
    jp = last.get("jackpot_eur")
    if jp and not last.get("has_winner"):
        return {"meur": round(jp / 1e6, 1), "source": "estimation",
                "note": f"report du jackpot du {last['date']} sans gagnant : le montant réel du prochain tirage est ≥ à cette valeur"}
    return {"meur": 17.0, "source": "estimation", "note": "jackpot remis à ~17 M€ après un gagnant (ou API muette)"}

# ------------------------------------------------------------------ HTML

CSS = """
:root{--bg:#0b0f14;--pan:#121821;--line:#1f2a36;--tx:#d7dee7;--mut:#8593a3;--acc:#5aa9ff;--ok:#31c48d;--warn:#f5a524;--bad:#ef5350}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--tx);font:14px/1.45 -apple-system,Segoe UI,Roboto,sans-serif;padding:16px}
h1{font-size:18px;margin:0 0 4px}h2{font-size:14px;color:var(--mut);text-transform:uppercase;letter-spacing:.08em;margin:22px 0 8px}
.warn{background:#2a1d0a;border:1px solid #5a3d0f;color:#ffd58a;padding:10px 12px;border-radius:6px;font-size:13px;margin:10px 0}
.grid{display:grid;gap:10px;grid-template-columns:repeat(auto-fit,minmax(260px,1fr))}
.card{background:var(--pan);border:1px solid var(--line);border-radius:8px;padding:12px}
.nums{font:600 22px/1 ui-monospace,Menlo,monospace;letter-spacing:.04em;margin:6px 0}.nums b{color:var(--warn)}
table{width:100%;border-collapse:collapse;font-size:13px}th,td{padding:5px 6px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap}
th{color:var(--mut);font-weight:500}.r{text-align:right}.wrap{overflow-x:auto}
.b{display:inline-block;padding:1px 7px;border-radius:10px;font-size:11px;font-weight:600}
.b.ns{background:#1c2733;color:var(--mut)}.b.sig{background:#0f3d2b;color:var(--ok)}.b.ok{background:#0f3d2b;color:var(--ok)}.b.ko{background:#4a1616;color:var(--bad)}
.k{color:var(--mut);font-size:12px}.mono{font-family:ui-monospace,Menlo,monospace}
svg{max-width:100%;height:auto}.foot{color:var(--mut);font-size:12px;margin-top:20px}
"""

def svg_hist(hist, marks):
    W, Hh, pad = 640, 160, 28
    counts = hist["counts"]; mx = max(counts) or 1; n = len(counts)
    bw = (W - 2*pad) / n
    bars = "".join(
        f'<rect x="{pad + i*bw:.1f}" y="{Hh - pad - (c/mx)*(Hh-2*pad):.1f}" width="{bw-1:.1f}" height="{(c/mx)*(Hh-2*pad):.1f}" fill="#2b3f57"/>'
        for i, c in enumerate(counts))
    def x_of(v): return pad + (v - hist["lo"]) / (hist["hi"] - hist["lo"] or 1) * (W - 2*pad)
    lines = "".join(
        f'<line x1="{x_of(v):.1f}" x2="{x_of(v):.1f}" y1="{pad-8}" y2="{Hh-pad}" stroke="{c}" stroke-width="2"/>'
        f'<text x="{x_of(v):.1f}" y="{pad-12}" fill="{c}" font-size="11" text-anchor="middle">{lab}</text>'
        for lab, v, c in marks)
    axis = (f'<text x="{pad}" y="{Hh-8}" fill="#8593a3" font-size="11">{hist["lo"]:.3f}</text>'
            f'<text x="{W-pad}" y="{Hh-8}" fill="#8593a3" font-size="11" text-anchor="end">{hist["hi"]:.3f}</text>'
            f'<text x="{W/2:.0f}" y="{Hh-8}" fill="#8593a3" font-size="11" text-anchor="middle">matches moyens / tirage (50 000 grilles aléatoires)</text>')
    return f'<svg viewBox="0 0 {W} {Hh}" xmlns="http://www.w3.org/2000/svg">{bars}{lines}{axis}</svg>'

def fmt_nums(nums): return " ".join(f"{n:02d}" for n in nums)

def build_html(R):
    fp, bt, sb = R["dataset"], R["backtest"]["numeros"], R["backtest"]["etoiles"]
    badge = lambda r: '<span class="b sig">sig.</span>' if r["significant"] else '<span class="b ns">ns</span>'
    rows_bt = "".join(
        f'<tr><td>{i+1}</td><td>{H.escape(k)}</td><td class="r mono">{r["edge"]:+.3f}</td>'
        f'<td class="r mono">[{r["ci"][0]:+.3f} ; {r["ci"][1]:+.3f}]</td><td class="r mono">{r["p_raw"]:.2f}</td>'
        f'<td class="r mono">{r["p_adj"]:.2f}</td><td>{badge(r)}</td></tr>'
        for i, (k, r) in enumerate(sorted(bt.items(), key=lambda x: -x[1]["edge"])))
    rows_sb = "".join(
        f'<tr><td>{H.escape(k)}</td><td class="r mono">{r["edge"]:+.3f}</td>'
        f'<td class="r mono">[{r["ci"][0]:+.3f} ; {r["ci"][1]:+.3f}]</td><td class="r mono">{r["p_adj"]:.2f}</td><td>{badge(r)}</td></tr>'
        for k, r in sorted(sb.items(), key=lambda x: -x[1]["edge"]))
    cards = "".join(
        f'<div class="card"><div class="k">G{g["id"]} · porteur : {H.escape(g["model"])} · étoiles : {H.escape(g["star_model"])}</div>'
        f'<div class="nums">{fmt_nums(g["nums"])} <b>★ {g["stars"][0]:02d} {g["stars"][1]:02d}</b></div>'
        f'<div class="k">somme {g["sum"]} · pairs {g["even"]}/5 · bas {g["low"]}/5 · anti-partage {g["anti_share"]:.0f}/100 · '
        f'co-gagnants attendus {g["cowinners"]:.2f} · percentile MC {g["mc_pct"]:.0f}e <span class="k">(descriptif rétrospectif, sans valeur prédictive)</span></div></div>'
        for g in R["grilles"])
    marks = [(f'G{g["id"]}', g["mc_avg"], "#f5a524") for g in R["grilles"]]
    marks.append(("médiane", R["monte_carlo"]["median"], "#5aa9ff"))
    c = R["registre"]["cumul"]
    rec = R["registre"]["rapproche"]
    rec_html = ("".join(f'<tr><td>{r["draw_date"]}</td><td>G{r["grid"]} · {H.escape(r["model"])}</td><td class="mono">{r["nums"]} ★ {r["stars"]}</td>'
                        f'<td class="mono">{r["real_nums"]} ★ {r["real_stars"]}</td><td class="r"><b>{r["match_nums"]}</b> num · {r["match_stars"]} ét.</td></tr>' for r in rec)
                or '<tr><td colspan="5" class="k">aucune grille à rapprocher ce run</td></tr>')
    chk = R["checklist"]
    jp = R["jackpot"]
    alerts = "".join(f"<li>{H.escape(a)}</li>" for a in R["dataset"]["alertes"]) or "<li>aucune alerte</li>"
    return f"""<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>QSC EuroMillions v{q.VERSION} — tirage du {R['draw_date']}</title><style>{CSS}</style></head><body>
<h1>QSC EuroMillions v{q.VERSION} — tirage du {R['draw_date_fr']}</h1>
<div class="k">run {R['run_date']} · seed <span class="mono">{R['seed']}</span> · dataset {fp['n']} tirages ({fp['premier']} → {fp['dernier']}) · hash <span class="mono">{fp['hash']}</span> · checklist {'<span class="b ok">verte</span>' if chk['ok'] else '<span class="b ko">KO</span>'}</div>
<div class="warn">⚠️ {q.DISCLAIMER}</div>

<h2>Grilles proposées — {len(R['grilles'])} (jackpot {jp['meur']:.0f} M€, {jp['source']} : {H.escape(jp['note'])})</h2>
<div class="grid">{cards}</div>
<p class="k">{q.EQUIVALENCE}</p>
<p class="k">Consensus pondérée : {H.escape(R['consensus']['message'])}</p>

<h2>Backtest numéros — walk-forward burn-in {R['backtest']['meta']['burn_in']}, step {R['backtest']['meta']['step']}, {R['backtest']['meta']['n_points']} points</h2>
<div class="wrap"><table><tr><th>#</th><th>Modèle</th><th class="r">Écart vs 0,50</th><th class="r">IC95% bootstrap</th><th class="r">p brut</th><th class="r">p corrigé*</th><th></th></tr>{rows_bt}</table></div>
<p class="k">* p corrigé = max-statistic sur {R['backtest']['meta']['n_models']} modèles ({R['backtest']['meta']['n_sim']} simulations sous H0 hypergéométrique exact). Seuil de significativité du meilleur modèle : écart ≥ {R['backtest']['meta']['null_max_q95']:+.3f}. <b>Verdict :</b> {H.escape(R['backtest']['verdict'])}</p>

<h2>Backtest étoiles — pool historique 9/11/12 respecté</h2>
<div class="wrap"><table><tr><th>Modèle</th><th class="r">Écart vs baseline pool</th><th class="r">IC95%</th><th class="r">p corrigé</th><th></th></tr>{rows_sb}</table></div>
<p class="k">p global étoiles = {R['backtest']['etoiles_meta']['p_global']:.2f}. {H.escape(R['backtest']['etoiles_verdict'])}</p>

<h2>Diagnostics</h2>
<div class="grid">
<div class="card"><div class="k">χ² d'uniformité (50 numéros, ddl 49)</div><div class="nums">{R['chi2']['stat']:.1f}</div><div class="k">p ≈ {R['chi2']['p']:.2f} — {'aucun biais matériel' if R['chi2']['p'] > 0.05 else 'écart à l uniforme : vérifier le dataset'}</div></div>
<div class="card"><div class="k">P(≥1 numéro) pour toute grille</div><div class="nums">{100*q.P_GE1_MATCH:.1f} %</div><div class="k">1 − C(45,5)/C(50,5) — identique pour toutes les grilles</div></div>
<div class="card"><div class="k">Intégrité dataset</div><ul class="k" style="margin:6px 0 0 16px;padding:0">{alerts}</ul></div>
</div>
<div class="card" style="margin-top:10px"><div class="k">Histogramme Monte-Carlo — position rétrospective des grilles (une grille au 90e percentile a fait 0 numéro le 31/07 : ce panneau décrit le passé, il ne prédit rien)</div>{svg_hist(R['monte_carlo']['hist'], marks)}</div>

<h2>Tableau de bord cumulatif — protocole vs hasard</h2>
<div class="grid">
<div class="card"><div class="k">Grilles jouées (registre)</div><div class="nums">{c['grilles']}</div></div>
<div class="card"><div class="k">Numéros trouvés / attendus</div><div class="nums">{c['match_nums']} / {c['attendu_nums']}</div><div class="k">écart {c['ecart_nums']:+}</div></div>
<div class="card"><div class="k">Étoiles trouvées / attendues</div><div class="nums">{c['match_stars']} / {c['attendu_stars']}</div><div class="k">écart {c['ecart_stars']:+}</div></div>
<div class="card"><div class="k">Meilleure grille</div><div class="nums">{c['meilleur']} num.</div></div>
</div>
<h2>Rapprochement du run précédent</h2>
<div class="wrap"><table><tr><th>Tirage</th><th>Grille</th><th>Jouée</th><th>Réel</th><th class="r">Résultat</th></tr>{rec_html}</table></div>

<h2>Lexique</h2>
<p class="k"><b>Écart backtesté</b> : matches moyens du top-5 du modèle moins 0,50 (espérance d'une grille aléatoire). <b>IC95%</b> : bootstrap 10 000 tirages des points de test. <b>p corrigé</b> : probabilité, sous pur hasard, qu'au moins un des modèles atteigne cet écart (max-statistic). <b>Porteur</b> : modèle qui a fourni la grille — un choix de méthode, pas un signal. <b>Anti-partage</b> : impopularité estimée de la grille (proxy UK, distribution FDJ non publiée) — réduit le partage en cas de gain, ne change pas la probabilité de gain. <b>Rotation narrative</b> : le porteur #1 d'un run est inéligible comme #1 au run suivant.</p>
<div class="warn">⚠️ {q.DISCLAIMER}</div>
<div class="foot">QSC v{q.VERSION} · généré par GitHub Actions · source données : API pedromealha + CSV maître · checklist : {'OK' if chk['ok'] else 'KO — ' + '; '.join(chk['fails'])}</div>
</body></html>"""

def build_chat(R):
    g = "\n".join(f"G{x['id']} ({x['model']}) : {fmt_nums(x['nums'])} ★ {x['stars'][0]:02d} {x['stars'][1]:02d}" for x in R["grilles"])
    c = R["registre"]["cumul"]
    return (f"⚠️ {q.DISCLAIMER}\n\n"
            f"QSC EuroMillions v{q.VERSION} — tirage du {R['draw_date_fr']} · {R['dataset']['n']} tirages · seed {R['seed']}\n"
            f"Jackpot {R['jackpot']['meur']:.0f} M€ ({R['jackpot']['source']}) → {len(R['grilles'])} grilles\n\n{g}\n\n"
            f"{q.EQUIVALENCE}\n"
            f"Backtest : {R['backtest']['verdict']}\n"
            f"Cumul protocole vs hasard : {c['match_nums']} numéros trouvés sur {c['grilles']} grilles (attendu {c['attendu_nums']}, écart {c['ecart_nums']:+}).\n\n"
            f"⚠️ {q.DISCLAIMER}")

# ------------------------------------------------------------------ main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="euromillions_MASTER.csv")
    ap.add_argument("--out", default="output")
    ap.add_argument("--jackpot", type=float, default=os.environ.get("JACKPOT_MEUR") or None)
    ap.add_argument("--today", default=None)
    ap.add_argument("--n-sim", type=int, default=5000)
    ap.add_argument("--mc", type=int, default=50_000)
    a = ap.parse_args()
    os.makedirs(os.path.join(a.out, "history"), exist_ok=True)

    today = date.fromisoformat(a.today) if a.today else date.today()
    draw_date = q.next_draw_date(today)
    draw_iso = draw_date.isoformat()
    seed = q.seed_from_draw_date(draw_iso)
    jours = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
    draw_fr = f"{jours[draw_date.weekday()]} {draw_date.day:02d}/{draw_date.month:02d}/{draw_date.year}"

    draws = q.load_master(a.csv)
    ok, alerts = q.integrity_check(draws)
    fp = q.dataset_fingerprint(draws, "csv"); fp["integrite"] = ok; fp["alertes"] = alerts
    if draws[-1][0] >= draw_iso:
        print(f"Le tirage {draw_iso} est déjà dans le dataset : rien à générer.", file=sys.stderr); sys.exit(0)

    api_meta = None
    p = os.path.join(a.out, "api_meta.json")
    if os.path.exists(p):
        api_meta = json.load(open(p, encoding="utf-8"))

    # registre : rapprochement + cumul
    reg_path = os.path.join(a.out, "registre.csv")
    rows = load_registre(reg_path)
    rapproche = reconcile(rows, draws)
    cum = cumul(rows)

    # rotation narrative : porteur #1 du dernier run
    prev_first = None
    hist_files = sorted(f for f in os.listdir(os.path.join(a.out, "history")) if f < f"{draw_iso}.json")
    if hist_files:  # dernier run d'un tirage antérieur (un re-run du même jour ne se voit pas lui-même)
        prev = json.load(open(os.path.join(a.out, "history", hist_files[-1]), encoding="utf-8"))
        prev_first = prev.get("porteurs", [None])[0]

    # backtests
    bt, meta = q.backtest_all(draws, n_sim=a.n_sim, seed=seed)
    sb, smeta = q.backtest_stars(draws, n_sim=a.n_sim, seed=seed)
    chi2, pchi = q.chi2_uniformity(draws)
    mc = q.monte_carlo(draws, n=a.mc, seed=seed)
    hist = q.mc_histogram(mc)

    # jackpot / nombre de grilles
    jp = estimate_jackpot(api_meta, a.jackpot)
    n = q.n_grids(jp["meur"])

    # grilles
    order = q.rank_selectors(bt, ineligible_first=prev_first)
    star_order = sorted(sb, key=lambda k: -sb[k]["edge"])
    grids, avoid = [], []
    for i in range(n):
        model = order[i % len(order)]
        g = q.best_grid(model, draws, avoid=avoid, max_ov=2, min_as=60)
        if g is None:
            g = q.best_grid(model, draws, pool=22, avoid=avoid, max_ov=2, min_as=50)
        avoid.append(g)
        sm = star_order[i % len(star_order)]
        stars = q.stars_for(draws, sm, pool=12)
        avg, pct = q.mc_percentile(g, draws, mc)
        grids.append({"id": i+1, "model": model, "nums": list(g), "star_model": sm, "stars": list(stars),
                      "sum": sum(g), "even": sum(1 for x in g if x % 2 == 0), "low": sum(1 for x in g if x <= 25),
                      "anti_share": round(q.anti_share_score(g, stars), 1),
                      "cowinners": round(q.expected_cowinners(g), 3),
                      "mc_avg": round(avg, 4), "mc_pct": round(pct, 1)})
    cons = q.consensus_grid(bt, draws)
    consensus = {"grid": list(cons) if cons else None,
                 "message": (f"{fmt_nums(cons)} (pondérée sur les seuls modèles significatifs)" if cons else
                             "non calculable ce jour : aucun modèle ne surperforme le hasard après correction — la consensus dégénère volontairement.")}

    # registre : ajout des grilles du jour (idempotent)
    if not any(r["draw_date"] == draw_iso for r in rows):
        for g in grids:
            rows.append({"run_date": today.isoformat(), "draw_date": draw_iso, "grid": g["id"], "model": g["model"],
                         "nums": "-".join(map(str, g["nums"])), "stars": "-".join(map(str, g["stars"])), "seed": seed,
                         "real_nums": "", "real_stars": "", "match_nums": "", "match_stars": ""})
    save_registre(reg_path, rows)

    slim = lambda d: {k: {kk: vv for kk, vv in v.items() if kk != "points"} for k, v in d.items()}
    R = {"version": q.VERSION, "run_date": today.isoformat(), "draw_date": draw_iso, "draw_date_fr": draw_fr, "seed": seed,
         "dataset": fp, "jackpot": jp, "n_grilles": n, "porteurs": order, "porteur_precedent_inéligible": prev_first,
         "grilles": grids, "consensus": consensus,
         "backtest": {"meta": meta, "numeros": slim(bt), "verdict": q.verdict(bt, meta),
                      "etoiles": slim(sb), "etoiles_meta": smeta,
                      "etoiles_verdict": ("Au moins un modèle étoiles significatif après correction — prudence." if any(r["significant"] for r in sb.values())
                                          else "Aucun modèle étoiles ne se distingue du hasard : choix méthodologique par rotation.")},
         "chi2": {"stat": round(chi2, 2), "p": round(pchi, 3)},
         "monte_carlo": {"n": a.mc, "median": mc[len(mc)//2], "hist": hist},
         "registre": {"rapproche": rapproche, "cumul": cum},
         "disclaimer": q.DISCLAIMER, "equivalence": q.EQUIVALENCE}
    R["checklist"] = {"ok": True, "fails": []}
    html_text = build_html(R); chat = build_chat(R)
    okc, fails = q.checklist(html_text, chat, fp, seed)
    R["checklist"] = {"ok": okc, "fails": fails}
    html_text = build_html(R)
    R["chat_summary"] = chat

    with open(os.path.join(a.out, "latest.html"), "w", encoding="utf-8") as f: f.write(html_text)
    with open(os.path.join(a.out, "latest.json"), "w", encoding="utf-8") as f: json.dump(R, f, ensure_ascii=False, indent=1)
    with open(os.path.join(a.out, "history", f"{draw_iso}.json"), "w", encoding="utf-8") as f: json.dump(R, f, ensure_ascii=False, indent=1)
    print(chat)
    print(f"\nchecklist : {'OK' if okc else 'KO ' + str(fails)}")
    sys.exit(0 if okc else 4)

if __name__ == "__main__":
    main()
