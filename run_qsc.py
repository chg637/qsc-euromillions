# -*- coding: utf-8 -*-
"""
run_qsc.py — Pipeline QSC v4.0 complet, exécuté par GitHub Actions les jours de tirage.

Étapes : chargement + intégrité → rapprochement du run précédent (registre append-only, en euros)
→ popularité estimée sur les gagnants par rang (R7, repli proxy UK) → backtest numéros/étoiles
(DIAGNOSTIC : step 1, null exact, max-stat) → chi² → jackpot officiel (fdj.fr, repli estimation API)
→ nombre de grilles (1/2/3/4 selon paliers, borné par le budget annuel) → tirage uniforme dans
l'univers impopulaire (A1) → latest.json / latest.html / history/<date>.json → checklist.

Usage : python3 run_qsc.py [--csv ...] [--out output] [--jackpot 95] [--today 2026-09-08] [--no-fdj]
Sortie : code 0 si checklist verte, 4 sinon (le livrable est quand même écrit, marqué KO).
"""
import argparse, csv, json, os, re, sys, math, html as H, urllib.request, urllib.error
from datetime import date, timedelta
import qsc_v40 as q
import popularite as P

# ------------------------------------------------------------------ registre (A4 : en euros)

REG_FIELDS = ["run_date", "draw_date", "grid", "model", "nums", "stars", "seed", "jackpot_meur",
              "real_nums", "real_stars", "match_nums", "match_stars",
              "rang", "gain_eur", "gagnants_rang", "gagnants_attendus_rang"]
RANG = {(5, 2): 1, (5, 1): 2, (5, 0): 3, (4, 2): 4, (4, 1): 5, (3, 2): 6, (4, 0): 7,
        (2, 2): 8, (3, 1): 9, (3, 0): 10, (1, 2): 11, (2, 1): 12, (2, 0): 13}
P_RANG1 = 1 / 139_838_160

def p_rank(k, s, pool=12):
    """Probabilité exacte d'une grille d'avoir k numéros et s étoiles."""
    return (math.comb(5, k) * math.comb(45, 5 - k) / math.comb(50, 5)) * \
           (math.comb(2, s) * math.comb(pool - 2, 2 - s) / math.comb(pool, 2))

def load_registre(path):
    if not os.path.exists(path): return []
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f, delimiter=";"))
    for r in rows:                       # lignes des versions antérieures : colonnes absentes → vides
        for k in REG_FIELDS: r.setdefault(k, "")
    return rows

def save_registre(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=REG_FIELDS, delimiter=";", lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        for r in rows: w.writerow(r)

def ventes_estimees(W):
    """Grilles vendues sur le pool, estimées par les gagnants des rangs bas (moyenne de W_k / p_k
       sur les rangs 2+0, 2+1, 1+2, 3+0 : chacun compte des centaines de milliers de gagnants)."""
    est = [W[k] / p_rank(*k) for k in [(2, 0), (2, 1), (1, 2), (3, 0)] if W.get(k, 0) > 0]
    return sum(est) / len(est) if est else None

def reconcile(rows, draws, prizes, prize_amounts):
    """Remplit numéros/étoiles trouvés, rang, gain réel et gagnants observés/attendus pour les grilles
       dont le tirage est connu. prizes = {date: {(k,s): winners}}, prize_amounts = {date: {(k,s): eur}}.
       Retourne les lignes rapprochées ce run."""
    by_date = {d: (n, s) for d, n, s in draws}
    done = []
    for r in rows:
        if r["match_nums"] == "" and r["draw_date"] in by_date:
            rn, rs = by_date[r["draw_date"]]
            gn = {int(x) for x in r["nums"].split("-")}; gs = {int(x) for x in r["stars"].split("-")}
            r["real_nums"] = "-".join(map(str, rn)); r["real_stars"] = "-".join(map(str, rs))
            k, s = len(gn & set(rn)), len(gs & set(rs))
            r["match_nums"] = str(k); r["match_stars"] = str(s)
            done.append(r)
        if r["match_nums"] != "" and r["rang"] == "" and r["draw_date"] in prizes:
            k, s = int(r["match_nums"]), int(r["match_stars"])
            W = prizes[r["draw_date"]]; rg = RANG.get((k, s))
            # v4.1 : un rang atteint sans montant connu n'est pas soldé à 0 € ; on attend le montant.
            if rg and (k, s) not in prize_amounts.get(r["draw_date"], {}):
                continue
            r["rang"] = rg or 0
            r["gain_eur"] = prize_amounts[r["draw_date"]][(k, s)] if rg else 0.0
            if not any(r is d for d in done):   # v4.1 : rang rempli après coup → annoncé quand même
                done.append(r)
            if rg:
                N = ventes_estimees(W)
                r["gagnants_rang"] = W.get((k, s), "")
                r["gagnants_attendus_rang"] = round(N * p_rank(k, s), 1) if N else ""
    return done

LOTO_PRIX = 2.20           # prix d'une grille Loto (budget commun, décision du 05/11/2026)

def depense_autre_jeu(path, annee, prix):
    """Dépense de l'année dans l'autre jeu (registre Loto) : une grille inscrite = une grille jouée.
       Fichier absent = 0 €. Le budget de 520 € est annuel et tous jeux confondus."""
    if not os.path.exists(path): return 0.0
    with open(path, newline="", encoding="utf-8") as f:
        return prix * sum(1 for r in csv.DictReader(f, delimiter=";") if r["draw_date"][:4] == str(annee))

def cumul(rows, annee, autre_depense=0.0):
    played = [r for r in rows if r["match_nums"] != ""]
    n = len(played)
    mn = sum(int(r["match_nums"]) for r in played); ms = sum(int(r["match_stars"]) for r in played)
    ic_n = 1.96 * math.sqrt(0.41327 * n) if n else 0.0
    ic_s = 1.96 * math.sqrt(0.25253 * n) if n else 0.0
    gains = sum(float(r["gain_eur"] or 0) for r in played)
    mise = q.PRIX_GRILLE * n
    en_euros = [r for r in played if r["rang"] != ""]
    obs = sum(float(r["gagnants_rang"]) for r in en_euros if r["gagnants_rang"] not in ("", None))
    att = sum(float(r["gagnants_attendus_rang"]) for r in en_euros if r["gagnants_attendus_rang"] not in ("", None))
    depense_annee = q.PRIX_GRILLE * sum(1 for r in rows if r["draw_date"][:4] == str(annee))
    return {"grilles": n, "match_nums": mn, "attendu_nums": round(q.BASELINE * n, 2),
            "ecart_nums": round(mn - q.BASELINE * n, 2), "ic95_nums": round(ic_n, 2),
            "match_stars": ms, "attendu_stars": round(q.star_baseline(12) * n, 2),
            "ecart_stars": round(ms - q.star_baseline(12) * n, 2), "ic95_stars": round(ic_s, 2),
            "meilleur": max((int(r["match_nums"]) for r in played), default=0),
            "mise_eur": round(mise, 2), "gains_eur": round(gains, 2), "solde_eur": round(gains - mise, 2),
            "grilles_en_euros": len(en_euros), "rangs_atteints": sum(1 for r in en_euros if int(r["rang"] or 0) > 0),
            "gagnants_observes": round(obs, 1), "gagnants_attendus": round(att, 1),
            "taux_partage": round(obs / att, 3) if att else None,
            "depense_euromillions_annee_eur": round(depense_annee, 2), "depense_autres_jeux_eur": round(autre_depense, 2),
            "depense_annee_eur": round(depense_annee + autre_depense, 2), "budget_eur": q.BUDGET_EUR, "annee": annee}

def load_prize_amounts(prizes_path, api_dir):
    """Montants par rang (euros) — pas dans euromillions_PRIZES.csv (gagnants seulement) :
       lus dans output/api_cache/<année>.json quand update_master les a conservés."""
    out = {}
    if not os.path.isdir(api_dir): return out
    for fn in sorted(os.listdir(api_dir)):
        if not fn.endswith(".json"): continue
        try:
            for it in json.load(open(os.path.join(api_dir, fn), encoding="utf-8")):
                out[it["date"]] = {(p["matched_numbers"], p["matched_stars"]): float(p["prize"]) for p in it.get("prizes", [])}
        except Exception as e:
            print(f"api_cache {fn} illisible : {e}", file=sys.stderr)
    return out

# ------------------------------------------------------------------ popularité (R7)

def popularity_report(table):
    """Résumé de la table en vigueur (après set_popularity) pour le JSON/HTML."""
    nums = {n: round(q.popularity(n), 4) for n in q.ALL_NUMS}
    stars = {s: round(q.star_popularity(s), 4) for s in q.ALL_STARS}
    meta = (table or {}).get("meta", {})
    r = {"source": q.POP["source"], "estimee": table is not None,
         "nums": nums, "stars": stars,
         "nums_min": min(nums, key=nums.get), "nums_max": max(nums, key=nums.get),
         "stars_tries": sorted(stars, key=stars.get),
         "tranches": {f"{lo}-{hi}": round(sum(nums[n] for n in range(lo, hi+1)) / (hi-lo+1), 3)
                      for lo, hi in [(1, 12), (13, 31), (32, 40), (41, 50)]}}
    if table is not None:
        mn, me = meta.get("numeros", {}), meta.get("etoiles", {})
        r.update({"n_tirages_nums": mn.get("n_draws"), "n_tirages_stars": me.get("n_draws"),
                  "periode": mn.get("periode"), "r2_nums": round(mn.get("r2", 0), 3),
                  "se_moyen_nums": round(sum(mn.get("se", {}).values()) / 50, 4) if mn.get("se") else None,
                  "se_moyen_stars": round(sum(me.get("se", {}).values()) / 12, 4) if me.get("se") else None,
                  "intercept": round(mn.get("intercept", 0), 4), "intercept_uniforme": round(mn.get("intercept_uniforme", 0), 4)})
    return r

# ------------------------------------------------------------------ jackpot (A3)

FDJ_URL = "https://www.fdj.fr/jeux-de-tirage/euromillions-my-million"

def parse_jackpot_fdj(page, draw_iso=None):
    """Extrait le jackpot EuroMillions (M€) de la page fdj.fr. Retourne (montant|None, raison).
       v4.1 : la page porte l'annonce du prochain tirage dans un bloc de données
       ("amount":"17 millions €" … "megaJackpot" … "date":"2026-11-13T21:45…"). On lit CE bloc,
       reconnu par la clé megaJackpot (propre à l'EuroMillions : la page affiche aussi le Loto,
       le Super Loto, le Keno), et on exige que sa date soit celle du tirage visé. L'ancien motif
       « NNN Millions d'euros à gagner » ne sert plus que de secours."""
    txt = page.replace('\\"', '"')
    blocs = re.findall(r'"amount":"(\d{1,3})\s*millions?\s*€"[^{}]{0,400}?"megaJackpot"[^{}]{0,600}?"date":"(\d{4}-\d{2}-\d{2})T', txt)
    if blocs:
        for montant, d in blocs:
            if draw_iso is None or d == draw_iso:
                v = float(montant)
                return (v, "ok") if 17 <= v <= 250 else (None, f"montant hors bornes ({montant} M€)")
        return None, f"page lue, mais annonce pour le {blocs[0][1]} et non le {draw_iso}"
    m = re.search(r"(\d{2,3})\s*Millions\s*d(?:&#x27;|'|’)euros\s*à\s*gagner", page, flags=re.I)
    if m and 17 <= float(m.group(1)) <= 250:
        return float(m.group(1)), "ok (ancien motif)"
    return None, "page lue, montant introuvable (mise en page changée ?)"

def jackpot_fdj(draw_iso=None, timeout=20):
    """Montant officiel du prochain tirage lu sur fdj.fr. Retourne (montant|None, raison) :
       la raison distingue une page inaccessible d'une page lue mais non comprise."""
    try:
        req = urllib.request.Request(FDJ_URL, headers={"User-Agent": "Mozilla/5.0 (qsc-euromillions/4.1)"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            page = r.read().decode("utf-8", "replace")
    except Exception as e:
        print(f"fdj.fr inaccessible : {e}", file=sys.stderr); return None, f"page inaccessible ({type(e).__name__})"
    return parse_jackpot_fdj(page, draw_iso)

def previous_draw_date(draw_date):
    """Tirage précédant draw_date (mardi/vendredi)."""
    d = draw_date - timedelta(days=1)
    while d.weekday() not in (1, 4):
        d -= timedelta(days=1)
    return d

def retard_dataset(dernier_iso, draw_date):
    """Nombre de tirages déjà joués qui manquent au dataset (0 = à jour)."""
    n, d = 0, previous_draw_date(draw_date)
    while d.isoformat() > dernier_iso:
        n += 1; d = previous_draw_date(d)
    return n

def estimate_jackpot(api_meta, override, use_fdj=True, draw_iso=None, retard=0):
    """Jackpot du run. Ordre : montant fourni, fdj.fr, estimation API. v4.1 : l'estimation n'est
       fiable que si le dernier tirage connu est bien le précédent (retard = 0) ; sinon elle est
       marquée « estimation périmée » et le nombre de grilles est à confirmer à la main."""
    if override is not None:
        return {"meur": float(override), "source": "fourni", "note": "montant officiel fourni au run", "fiable": True}
    last = (api_meta or {}).get("last_draw") or {}
    jp = last.get("jackpot_eur")
    est = round(jp / 1e6, 1) if (jp and not last.get("has_winner")) else 17.0
    raison = "fdj.fr non interrogé"
    if use_fdj:
        off, raison = jackpot_fdj(draw_iso)
        if off is not None and (retard > 0 or off >= est - 1):
            return {"meur": off, "source": "fdj.fr", "fiable": True,
                    "note": f"montant officiel lu sur fdj.fr (estimation API : {est:.0f} M€)"}
        if off is not None:
            raison = f"fdj.fr donne {off:.0f} M€, sous l'estimation API ({est:.0f} M€) : écarté"
    if retard > 0:
        return {"meur": est, "source": "estimation périmée", "fiable": False,
                "note": f"fdj.fr : {raison}. Le dataset a {retard} tirage(s) de retard (dernier connu : {last.get('date', '?')}) : "
                        f"ce montant n'est PAS celui du prochain tirage. Nombre de grilles à confirmer avec le jackpot officiel."}
    if jp and not last.get("has_winner"):
        return {"meur": est, "source": "estimation", "fiable": False,
                "note": f"fdj.fr : {raison}. Report du jackpot du {last['date']} sans gagnant : le montant réel du prochain tirage est ≥ à cette valeur"}
    return {"meur": 17.0, "source": "estimation", "fiable": False,
            "note": f"fdj.fr : {raison}. Jackpot remis à ~17 M€ après un gagnant (ou API muette)"}

def ev_grille(jackpot_meur, rel_pop, ventes=23_000_000, ev_rangs_bas=0.47):
    """EV nette théorique d'une grille : rang 1 avec partage Poisson (λ = N·p₁·ρ) + rangs 2-13 (≈0,47 €)."""
    lam = ventes * P_RANG1 * rel_pop
    share = (1 - math.exp(-lam)) / lam if lam > 1e-12 else 1.0
    return jackpot_meur * 1e6 * P_RANG1 * share + ev_rangs_bas - q.PRIX_GRILLE

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

def popularity_html(p):
    """Section R7 : barres de popularité relative par numéro et par étoile."""
    def bars(table, keys, w=12):
        mx = max(table[k] for k in keys); mn = min(table[k] for k in keys)
        out = []
        for k in keys:
            v = table[k]; h = 46 * (v - mn) / (mx - mn or 1) + 4
            col = "#ef5350" if v > 1.05 else ("#31c48d" if v < 0.95 else "#8593a3")
            out.append(f'<div title="{k} : ×{v:.2f}" style="display:inline-block;width:{w}px;margin:0 1px;text-align:center;font-size:9px;color:#8593a3;vertical-align:bottom">'
                       f'<div style="height:50px;display:flex;align-items:flex-end"><div style="width:100%;height:{h:.0f}px;background:{col};border-radius:2px 2px 0 0"></div></div>{k}</div>')
        return "".join(out)
    nums = {int(k): v for k, v in p["nums"].items()}; stars = {int(k): v for k, v in p["stars"].items()}
    if p["estimee"]:
        src = (f'{H.escape(p["source"])} — {p["n_tirages_nums"]} tirages ({p["periode"][0]} → {p["periode"][1]}), '
               f'R² {p["r2_nums"]:.2f}, incertitude moyenne ±{p["se_moyen_nums"]:.3f} par numéro, ±{p["se_moyen_stars"]:.3f} par étoile. '
               f'Tranches : 1-12 ×{p["tranches"]["1-12"]:.2f} · 13-31 ×{p["tranches"]["13-31"]:.2f} · 32-40 ×{p["tranches"]["32-40"]:.2f} · 41-50 ×{p["tranches"]["41-50"]:.2f}. '
               f'Numéro le plus joué : {p["nums_max"]} (×{nums[p["nums_max"]]:.2f}), le moins joué : {p["nums_min"]} (×{nums[p["nums_min"]]:.2f}). '
               f'Étoiles de la moins à la plus jouée : {" ".join(str(s) for s in p["stars_tries"])}.')
    else:
        src = f'{H.escape(p["source"])} — table estimée indisponible ce run (fichier de gagnants absent ou trop court) : proxy UK Lotto normalisé.'
    return (f'<div class="card" style="margin-top:10px"><div class="k"><b>Popularité des numéros et des étoiles</b> (×1,00 = moyenne ; rouge = plus joué, vert = moins joué). {src}</div>'
            f'<div style="margin-top:8px;white-space:nowrap;overflow-x:auto">{bars(nums, q.ALL_NUMS)}</div>'
            f'<div style="margin-top:6px;white-space:nowrap">{bars(stars, q.ALL_STARS, w=18)}</div></div>')

def fmt_nums(nums): return " ".join(f"{n:02d}" for n in nums)
def fmt_int(n): return f"{n:,}".replace(",", "\u202f")
def fmt_eur(x): return f"{x:,.2f} €".replace(",", "\u202f").replace(".", ",")

def build_html(R):
    fp, bt, sb = R["dataset"], R["backtest"]["numeros"], R["backtest"]["etoiles"]
    badge = lambda r: '<span class="b sig">sig.</span>' if r["significant"] else '<span class="b ns">ns</span>'
    rows_bt = "".join(
        f'<tr><td>{H.escape(k)}</td><td class="r mono">{r["edge"]:+.3f}</td>'
        f'<td class="r mono">[{r["ci"][0]:+.3f} ; {r["ci"][1]:+.3f}]</td><td class="r mono">{r["p_raw"]:.2f}</td>'
        f'<td class="r mono">{r["p_adj"]:.2f}</td><td>{badge(r)}</td></tr>'
        for k, r in sorted(bt.items(), key=lambda x: -x[1]["edge"]))
    rows_sb = "".join(
        f'<tr><td>{H.escape(k)}</td><td class="r mono">{r["edge"]:+.3f}</td>'
        f'<td class="r mono">[{r["ci"][0]:+.3f} ; {r["ci"][1]:+.3f}]</td><td class="r mono">{r["p_adj"]:.2f}</td><td>{badge(r)}</td></tr>'
        for k, r in sorted(sb.items(), key=lambda x: -x[1]["edge"]))
    cards = "".join(
        f'<div class="card"><div class="k">G{g["id"]} · tirage uniforme dans l&rsquo;univers impopulaire</div>'
        f'<div class="nums">{fmt_nums(g["nums"])} <b>★ {g["stars"][0]:02d} {g["stars"][1]:02d}</b></div>'
        f'<div class="k">somme {g["sum"]} · pairs {g["even"]}/5 · bas {g["low"]}/5 · impopularité {g["anti_share"]:.0f}e percentile · '
        f'joueurs attendus ×{g["rel_popularity"]:.2f} vs grille moyenne · co-gagnants attendus au rang 1 : {g["cowinners"]:.3f} · '
        f'EV nette théorique {fmt_eur(g["ev_nette"])}</div></div>'
        for g in R["grilles"]) or '<div class="card"><div class="k">Aucune grille ce run : budget annuel atteint.</div></div>'
    c = R["registre"]["cumul"]
    rec = R["registre"]["rapproche"]
    rec_html = ("".join(f'<tr><td>{r["draw_date"]}</td><td>G{r["grid"]}</td><td class="mono">{r["nums"]} ★ {r["stars"]}</td>'
                        f'<td class="mono">{r["real_nums"]} ★ {r["real_stars"]}</td><td class="r"><b>{r["match_nums"]}</b> num · {r["match_stars"]} ét.</td>'
                        f'<td class="r">{("rang " + str(r["rang"]) + " · " + fmt_eur(float(r["gain_eur"] or 0))) if r.get("rang") not in ("", 0, "0", None) else "—"}</td></tr>' for r in rec)
                or '<tr><td colspan="6" class="k">aucune grille à rapprocher ce run</td></tr>')
    chk = R["checklist"]; jp = R["jackpot"]
    plancher_html = ""
    if R.get("n_grilles_plancher"):
        plancher_html = ('<p class="k">Nombre de grilles relevé par l&rsquo;input <span class="mono">n_grilles</span> = '
                         f'{R["n_grilles_plancher"]} ; la règle jackpot seule en donnait {R["n_grilles_regle_jackpot"]}. '
                         'Le plancher change combien on joue, jamais la probabilité de gain de chaque grille.</p>')
    alerts = "".join(f"<li>{H.escape(a)}</li>" for a in R["dataset"]["alertes"]) or "<li>aucune alerte</li>"
    tp = c["taux_partage"]
    return f"""<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>QSC EuroMillions v{q.VERSION} — tirage du {R['draw_date']}</title><style>{CSS}</style></head><body>
<h1>QSC EuroMillions v{q.VERSION} — tirage du {R['draw_date_fr']}</h1>
<div class="k">run {R['run_date']} · seed <span class="mono">{R['seed']}</span> · dataset {fp['n']} tirages ({fp['premier']} → {fp['dernier']}) · hash <span class="mono">{fp['hash']}</span> · checklist {'<span class="b ok">verte</span>' if chk['ok'] else '<span class="b ko">KO</span>'}</div>
<div class="warn">⚠️ {q.DISCLAIMER}</div>

<h2>Grilles — {len(R['grilles'])} (jackpot {jp['meur']:.0f} M€, {jp['source']} : {H.escape(jp['note'])})</h2>
{plancher_html}
<div class="grid">{cards}</div>
<p class="k">{q.EQUIVALENCE}</p>
<p class="k"><b>Sélection v4.0</b> : univers = les {100*R['selection']['quantile']:.0f} % de grilles les moins jouées ({fmt_int(R['selection']['univers_grilles'])} sur {fmt_int(R['selection']['total_grilles'])}, popularité moyenne ≤ {R['selection']['seuil_gp']:.3f} vs 1,00 pour la grille moyenne), hors motifs sur-joués ; étoiles = {len(R['selection']['etoiles_univers'])} paires du quart le moins joué. Les grilles sont tirées <b>uniformément</b> dans cet univers (seed {R['seed']}) : aucun modèle ne les choisit, parce qu'aucun modèle ne fait mieux que le hasard (voir diagnostic). Cela ne change pas la probabilité de gagner, seulement le partage attendu si la grille gagne.</p>
<p class="k"><b>Mise</b> : règle {R['mise']['regle']} ; budget {fmt_eur(c['budget_eur'])} par an tous jeux confondus, dépensé {fmt_eur(c['depense_annee_eur'])} en {c['annee']} (dont {fmt_eur(c['depense_autres_jeux_eur'])} au Loto, grilles de ce run comprises), reste {fmt_eur(max(0, c['budget_eur'] - c['depense_annee_eur']))}.</p>
{popularity_html(R['popularite'])}

<h2>Tableau de bord cumulatif — protocole vs hasard</h2>
<div class="grid">
<div class="card"><div class="k">Grilles jouées (registre)</div><div class="nums">{c['grilles']}</div></div>
<div class="card"><div class="k">Numéros trouvés / attendus</div><div class="nums">{c['match_nums']} / {c['attendu_nums']}</div><div class="k">écart {c['ecart_nums']:+} · IC95 % ±{c['ic95_nums']}</div></div>
<div class="card"><div class="k">Étoiles trouvées / attendues</div><div class="nums">{c['match_stars']} / {c['attendu_stars']}</div><div class="k">écart {c['ecart_stars']:+} · IC95 % ±{c['ic95_stars']}</div></div>
<div class="card"><div class="k">Mise / gains</div><div class="nums">{fmt_eur(c['mise_eur'])} / {fmt_eur(c['gains_eur'])}</div><div class="k">solde {fmt_eur(c['solde_eur'])} · {c['rangs_atteints']} rang(s) atteint(s) sur {c['grilles_en_euros']} grilles en euros</div></div>
<div class="card"><div class="k">Partage observé (rangs atteints)</div><div class="nums">{('×' + format(tp, '.2f')) if tp is not None else '—'}</div><div class="k">gagnants observés {fmt_int(round(c['gagnants_observes']))} / attendus sous jeu uniforme {fmt_int(round(c['gagnants_attendus']))} — &lt; 1 = les grilles jouées sont moins partagées que la moyenne</div></div>
</div>
<h2>Rapprochement du run précédent</h2>
<div class="wrap"><table><tr><th>Tirage</th><th>Grille</th><th>Jouée</th><th>Réel</th><th class="r">Résultat</th><th class="r">Rang · gain</th></tr>{rec_html}</table></div>

<h2>Diagnostic — les modèles ne font pas mieux que le hasard (walk-forward burn-in {R['backtest']['meta']['burn_in']}, step {R['backtest']['meta']['step']}, {R['backtest']['meta']['n_points']} points)</h2>
<div class="wrap"><table><tr><th>Modèle</th><th class="r">Écart vs 0,50</th><th class="r">IC95% bootstrap</th><th class="r">p brut</th><th class="r">p corrigé*</th><th></th></tr>{rows_bt}</table></div>
<p class="k">* p corrigé = max-statistic sur {R['backtest']['meta']['n_models']} modèles ({R['backtest']['meta']['n_sim']} simulations sous H0 hypergéométrique exact). Seuil de significativité du meilleur modèle : écart ≥ {R['backtest']['meta']['null_max_q95']:+.3f}. <b>Verdict :</b> {H.escape(R['backtest']['verdict'])} Ce tableau est publié pour mémoire : il ne pilote plus la sélection depuis la v4.0.</p>
<div class="wrap"><table><tr><th>Modèle étoiles</th><th class="r">Écart vs baseline pool</th><th class="r">IC95%</th><th class="r">p corrigé</th><th></th></tr>{rows_sb}</table></div>
<p class="k">p global étoiles = {R['backtest']['etoiles_meta']['p_global']:.2f}.</p>
<div class="grid">
<div class="card"><div class="k">χ² d'uniformité (50 numéros, ddl 49)</div><div class="nums">{R['chi2']['stat']:.1f}</div><div class="k">p ≈ {R['chi2']['p']:.2f} — {'aucun biais matériel' if R['chi2']['p'] > 0.05 else 'écart à l uniforme : vérifier le dataset'}</div></div>
<div class="card"><div class="k">P(≥1 numéro) pour toute grille</div><div class="nums">{100*q.P_GE1_MATCH:.1f} %</div><div class="k">1 − C(45,5)/C(50,5) — identique pour toutes les grilles</div></div>
<div class="card"><div class="k">Intégrité dataset</div><ul class="k" style="margin:6px 0 0 16px;padding:0">{alerts}</ul></div>
</div>

<h2>Lexique</h2>
<p class="k"><b>Univers impopulaire</b> : les 10 % de grilles les moins jouées d'après la table de popularité estimée sur les gagnants par rang (R7). <b>Impopularité (percentile)</b> : part des 2 118 760 grilles plus jouées que celle-ci, moins les pénalités de forme. <b>Joueurs attendus ×k</b> : facteur multiplicatif du nombre de joueurs sur cette grille par rapport à un joueur uniforme (étoiles incluses). <b>EV nette théorique</b> : espérance de gain d'une grille (rang 1 avec partage Poisson aux ventes médianes, rangs 2-13 aux montants moyens) moins son prix ; toujours négative. <b>Partage observé</b> : sur les rangs atteints par les grilles jouées, gagnants réels divisés par les gagnants attendus si tout le monde jouait au hasard ; c'est la seule mesure du levier anti-partage. <b>Écart backtesté</b> : matches moyens du top-5 d'un modèle moins 0,50 ; <b>p corrigé</b> : probabilité, sous pur hasard, qu'au moins un des modèles atteigne cet écart (max-statistic).</p>
<div class="warn">⚠️ {q.DISCLAIMER}</div>
<div class="foot">QSC v{q.VERSION} · généré par GitHub Actions · source données : API pedromealha + CSV maître · jackpot : {jp['source']} · checklist : {'OK' if chk['ok'] else 'KO — ' + '; '.join(chk['fails'])}</div>
</body></html>"""

def build_chat(R):
    g = "\n".join(f"G{x['id']} : {fmt_nums(x['nums'])} ★ {x['stars'][0]:02d} {x['stars'][1]:02d}  (joueurs attendus ×{x['rel_popularity']:.2f}, EV nette {x['ev_nette']:+.2f} €)" for x in R["grilles"]) \
        or "Aucune grille ce run : budget annuel atteint."
    c = R["registre"]["cumul"]
    tp = c["taux_partage"]
    return (f"⚠️ {q.DISCLAIMER}\n\n"
            f"QSC EuroMillions v{q.VERSION} — tirage du {R['draw_date_fr']} · {R['dataset']['n']} tirages · seed {R['seed']}\n"
            f"Jackpot {R['jackpot']['meur']:.0f} M€ ({R['jackpot']['source']}) → {len(R['grilles'])} grille(s) ({R['mise']['regle']})"
            + (f" (plancher n_grilles = {R['n_grilles_plancher']})" if R.get("n_grilles_plancher") else "") + f"\n\n{g}\n\n"
            f"{q.EQUIVALENCE}\n"
            f"Sélection : tirage uniforme (seed) parmi les {100*R['selection']['quantile']:.0f} % de grilles les moins jouées, étoiles du quart le moins joué. Aucun modèle ne choisit les numéros : le diagnostic dit qu'aucun ne bat le hasard ({R['backtest']['verdict']})\n"
            f"Popularité : {R['popularite']['source']}"
            + (f" — {R['popularite']['n_tirages_nums']} tirages ; étoiles les moins jouées : {', '.join(str(s) for s in R['popularite']['stars_tries'][:4])}.\n" if R['popularite']['estimee'] else " (repli : table estimée indisponible ce run).\n")
            + f"Budget : {c['depense_annee_eur']:.2f} € dépensés en {c['annee']} sur {c['budget_eur']:.0f} € (dont {c['depense_autres_jeux_eur']:.2f} € au Loto).\n"
            f"Cumul : {c['match_nums']} numéros trouvés sur {c['grilles']} grilles (attendu {c['attendu_nums']}, écart {c['ecart_nums']:+} ± {c['ic95_nums']}) · mise {c['mise_eur']:.2f} €, gains {c['gains_eur']:.2f} €"
            + (f" · partage observé ×{tp:.2f} sur {c['rangs_atteints']} rang(s)" if tp is not None else "") + f".\n\n"
            f"⚠️ {q.DISCLAIMER}")

# ------------------------------------------------------------------ main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="euromillions_MASTER.csv")
    ap.add_argument("--prizes", default="euromillions_PRIZES.csv")
    ap.add_argument("--out", default="output")
    ap.add_argument("--jackpot", type=float, default=os.environ.get("JACKPOT_MEUR") or None)
    ap.add_argument("--today", default=None)
    ap.add_argument("--n-grilles", type=int, default=int(os.environ.get("N_GRILLES") or 0),
                    help="plancher du nombre de grilles ; ne peut que relever la règle jackpot (le budget borne toujours)")
    ap.add_argument("--autre-registre", default=os.path.join("loto", "output", "registre.csv"),
                    help="registre Loto, pour le budget annuel commun (absent = 0 €)")
    ap.add_argument("--no-fdj", action="store_true", help="ne pas interroger fdj.fr (tests, rejeu)")
    ap.add_argument("--n-sim", type=int, default=5000)
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
        msg = f"Le tirage {draw_iso} est déjà dans le dataset : rien à générer."
        print(msg, file=sys.stderr)
        if os.environ.get("GITHUB_STEP_SUMMARY"):
            with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f: f.write(f"## Run QSC sans objet\n\n{msg}\n")
        sys.exit(0)

    # v4.1 : fraîcheur. Le contrôle d'intégrité ne voit que les trous à l'intérieur du dataset ;
    # ici on compare le dernier tirage connu au tirage précédant celui du run.
    retard = retard_dataset(draws[-1][0], draw_date)
    fp["retard_tirages"] = retard
    if retard:
        fp["alertes"].append(f"dataset en retard de {retard} tirage(s) : dernier connu {draws[-1][0]}, "
                             f"attendu {previous_draw_date(draw_date).isoformat()} (rapprochement et jackpot estimé incomplets)")
    maj = os.environ.get("UPDATE_STATUS", "")
    if maj and maj != "success":
        fp["alertes"].append("mise à jour du CSV en échec ce run (API injoignable ou tirage manquant) : calcul sur le CSV existant")

    api_meta = None
    p = os.path.join(a.out, "api_meta.json")
    if os.path.exists(p):
        api_meta = json.load(open(p, encoding="utf-8"))

    # registre : rapprochement (en euros) + cumul
    prizes = P.load_prizes(a.prizes)
    amounts = load_prize_amounts(a.prizes, os.path.join(a.out, "api_cache"))
    reg_path = os.path.join(a.out, "registre.csv")
    rows = load_registre(reg_path)
    rapproche = reconcile(rows, draws, prizes, amounts)
    autre_depense = depense_autre_jeu(a.autre_registre, draw_date.year, LOTO_PRIX)
    cum_avant = cumul(rows, draw_date.year, autre_depense=autre_depense)

    # R7 : popularité estimée sur les gagnants par rang (repli proxy UK si impossible)
    pop_table = P.estimate(a.prizes, draws, q.star_pool)
    q.set_popularity(pop_table)
    pop_info = popularity_report(pop_table)
    with open(os.path.join(a.out, "popularite.json"), "w", encoding="utf-8") as f:
        json.dump(pop_info, f, ensure_ascii=False, indent=1)

    # diagnostic (ne pilote rien)
    bt, meta = q.backtest_all(draws, n_sim=a.n_sim, seed=seed)
    sb, smeta = q.backtest_stars(draws, n_sim=a.n_sim, seed=seed)
    chi2, pchi = q.chi2_uniformity(draws)

    # jackpot officiel / nombre de grilles sous budget
    jp = estimate_jackpot(api_meta, a.jackpot, use_fdj=not a.no_fdj, draw_iso=draw_iso, retard=retard)
    deja_ce_tirage = sum(1 for r in rows if r["draw_date"] == draw_iso)
    depense = cum_avant["depense_annee_eur"] - q.PRIX_GRILLE * deja_ce_tirage   # un re-run ne compte pas deux fois ses grilles
    n = q.n_grids(jp["meur"], plancher=a.n_grilles, depense_annee=depense)
    regle_txt = f"1 grille, +1 à 100, 150 et 200 M€ ({q.n_grids_regle(jp['meur'])} pour {jp['meur']:.0f} M€)"

    # grilles : tirage uniforme dans l'univers impopulaire (A1)
    universe, gp_thr, n_total = q.impopular_universe()
    star_univ = q.star_universe(12)
    ventes = ventes_estimees(prizes[max(prizes)]) if prizes else None
    # v4.1 : les grilles déjà inscrites au registre pour ce tirage sont FIGÉES. Un re-run (jackpot
    # officiel, créneau de rattrapage) recalcule leurs indicateurs mais ne les retire jamais, même
    # si la table de popularité a bougé entre-temps ; il ne tire que les grilles supplémentaires.
    figees = sorted((r for r in rows if r["draw_date"] == draw_iso), key=lambda r: int(r["grid"]))
    paires = [(tuple(int(x) for x in r["nums"].split("-")), tuple(int(x) for x in r["stars"].split("-"))) for r in figees]
    if len(paires) < n:
        for g, stars in q.draw_grids(seed, n + len(paires) + 5, universe=universe, star_univ=star_univ):
            if len(paires) >= n: break
            if any(q.overlap(g, h) > 2 or stars == st for h, st in paires): continue
            paires.append((g, stars))
    grids = []
    for i, (g, stars) in enumerate(paires):
        rp = q.relative_popularity(g, stars)
        grids.append({"id": i+1, "nums": list(g), "stars": list(stars),
                      "sum": sum(g), "even": sum(1 for x in g if x % 2 == 0), "low": sum(1 for x in g if x <= 25),
                      "anti_share": round(q.anti_share_score(g, stars), 1),
                      "rel_popularity": round(rp, 3),
                      "cowinners": round(q.expected_cowinners(g, stars, n_tickets=ventes or 25_000_000), 3),
                      "ev_nette": round(ev_grille(jp["meur"], rp, ventes=ventes or 23_000_000), 3)})
    selection = {"regle": "univers = décile le moins populaire des C(50,5) (table R7) hors motifs pénalisés ; "
                          "tirage uniforme par seed à l'intérieur, recouvrement ≤ 2 numéros, paires d'étoiles distinctes",
                 "quantile": q.IMPOP_QUANTILE, "univers_grilles": len(universe), "total_grilles": n_total,
                 "seuil_gp": round(gp_thr, 4), "etoiles_univers": [list(p) for p in star_univ],
                 "max_recouvrement": 2, "etoiles_quantile": q.STAR_QUANTILE, "popularite_source": q.POP["source"],
                 "ventes_estimees": ventes}

    # registre : ajout des grilles du jour (idempotent, par (tirage, n° de grille))
    deja = {(r["draw_date"], str(r["grid"])) for r in rows}
    for g in grids:
        if (draw_iso, str(g["id"])) in deja: continue
        rows.append({"run_date": today.isoformat(), "draw_date": draw_iso, "grid": g["id"], "model": "uniforme-univers-R7",
                     "nums": "-".join(map(str, g["nums"])), "stars": "-".join(map(str, g["stars"])), "seed": seed,
                     "jackpot_meur": jp["meur"], "real_nums": "", "real_stars": "", "match_nums": "", "match_stars": "",
                     "rang": "", "gain_eur": "", "gagnants_rang": "", "gagnants_attendus_rang": ""})
    save_registre(reg_path, rows)
    cum = cumul(rows, draw_date.year, autre_depense=autre_depense)

    slim = lambda d: {k: {kk: vv for kk, vv in v.items() if kk != "points"} for k, v in d.items()}
    R = {"version": q.VERSION, "run_date": today.isoformat(), "draw_date": draw_iso, "draw_date_fr": draw_fr, "seed": seed,
         "dataset": fp, "jackpot": jp, "n_grilles": len(grids), "grilles_figees": len(figees),
         "n_grilles_regle_jackpot": q.n_grids_regle(jp["meur"]), "n_grilles_plancher": a.n_grilles or None,
         "mise": {"regle": regle_txt, "budget_eur": q.BUDGET_EUR, "prix_grille": q.PRIX_GRILLE, "depense_annee_avant_run": round(depense, 2),
                  "dont_autres_jeux": round(autre_depense, 2)},
         "selection": selection, "popularite": pop_info, "grilles": grids,
         "backtest": {"role": "diagnostic — ne pilote pas la sélection", "meta": meta, "numeros": slim(bt), "verdict": q.verdict(bt, meta),
                      "etoiles": slim(sb), "etoiles_meta": smeta},
         "chi2": {"stat": round(chi2, 2), "p": round(pchi, 3)},
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
