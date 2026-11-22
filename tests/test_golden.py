# -*- coding: utf-8 -*-
"""
test_golden.py : filet de non-régression du protocole QSC (EuroMillions et Loto).

Rejoue un run complet de chaque jeu sur des données FIGÉES (tests/golden/data/), à une date
fixe, sans réseau (--no-fdj), avec un jackpot imposé, et compare la sortie octet pour octet
aux références stockées dans tests/golden/expected_*. Le tirage étant semé par la date, une
différence signifie que la méthode, les nombres ou le rendu ont changé.

Ce test sert à refactorer sans changer le comportement. Si un changement de méthode est voulu
(nouvelle version du protocole), regénérer les références, relire le diff, puis le committer :

    python3 tests/test_golden.py --update

Usage : python3 tests/test_golden.py        (pur stdlib, code retour 0 si tout est identique)
"""
import difflib, os, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOLD = os.path.join(ROOT, "tests", "golden")
DATA = os.path.join(GOLD, "data")
TODAY = "2026-11-20"
N_SIM = "300"

GAMES = {
    "euromillions": dict(script=os.path.join(ROOT, "run_qsc.py"), jackpot="95",
                         csv="euromillions_MASTER.csv", prizes="euromillions_PRIZES.csv"),
    "loto": dict(script=os.path.join(ROOT, "loto", "run_loto.py"), jackpot="5",
                 csv="loto_MASTER.csv", prizes="loto_PRIZES.csv"),
}
COMPARED = ["latest.json", "registre.csv"]


def run_game(name, out):
    g = GAMES[name]
    cmd = [sys.executable, g["script"],
           "--csv", os.path.join(DATA, g["csv"]), "--prizes", os.path.join(DATA, g["prizes"]),
           "--out", out, "--today", TODAY, "--jackpot", g["jackpot"],
           "--no-fdj", "--n-sim", N_SIM, "--autre-registre", os.path.join(out, "_aucun.csv")]
    env = dict(os.environ, JACKPOT_MEUR="", N_GRILLES="")
    p = subprocess.run(cmd, cwd=out, env=env, capture_output=True, text=True)
    return p


def main():
    update = "--update" in sys.argv
    ok = fail = 0
    for name in GAMES:
        tmp = tempfile.mkdtemp(prefix=f"golden_{name}_")
        try:
            p = run_game(name, tmp)
            if p.returncode != 0:
                fail += 1
                print(f"[{name}] run en échec (code {p.returncode})\n{p.stdout[-1500:]}\n{p.stderr[-1500:]}")
                continue
            for fn in COMPARED:
                got = open(os.path.join(tmp, fn), encoding="utf-8").read()
                ref_path = os.path.join(GOLD, f"expected_{name}_{fn}")
                if update:
                    open(ref_path, "w", encoding="utf-8", newline="\n").write(got)
                    print(f"[{name}] référence mise à jour : {os.path.relpath(ref_path, ROOT)}")
                    ok += 1
                    continue
                if not os.path.exists(ref_path):
                    fail += 1
                    print(f"[{name}] référence absente : {os.path.relpath(ref_path, ROOT)} (lancer --update)")
                    continue
                exp = open(ref_path, encoding="utf-8").read()
                if got == exp:
                    ok += 1
                else:
                    fail += 1
                    d = difflib.unified_diff(exp.splitlines(), got.splitlines(), "attendu", "obtenu", lineterm="", n=1)
                    print(f"[{name}] {fn} DIFFÉRENT :\n" + "\n".join(list(d)[:40]))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    total = ok + fail
    print(f"\n{ok}/{total} comparaisons golden OK" if not update else f"\n{ok} références écrites")
    sys.exit(0 if fail == 0 else 1)


if __name__ == "__main__":
    main()
