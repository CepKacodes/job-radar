"""
Hlavni beh skenu.

    python -m scanner.main               plny beh
    python -m scanner.main --test ID     zkusi jeden zdroj a vypise, co nasel
    python -m scanner.main --bez-ai      nacte nabidky, ale nehodnoti
    python -m scanner.main --bez-firem   preskoci dohledavani webu firem
"""

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import companies, dedupe, salary, score
from .sources import S_VYRAZY, nacti

DATA = Path(__file__).resolve().parent.parent / "data"


def cti(jmeno, vychozi):
    cesta = DATA / jmeno
    if not cesta.exists():
        return vychozi
    try:
        return json.loads(cesta.read_text(encoding="utf-8"))
    except Exception:
        return vychozi


def zapis(jmeno, obsah):
    (DATA / jmeno).write_text(
        json.dumps(obsah, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def vyrazy_pro(zdroj, config):
    """Zdroj si bere vyrazy z katalogu podle toho, co ma zaskrtnute."""
    if zdroj.get("typ") not in S_VYRAZY:
        return zdroj
    katalog = {p["vyraz"] for p in config.get("katalog", [])}
    vybrane = [v for v in zdroj.get("vyrazy", []) if v in katalog]
    return {**zdroj, "vyrazy": vybrane or list(katalog)}


def posbirej(config, jen_zdroj=None):
    nalezene, chyby = [], []
    for zdroj in config.get("zdroje", []):
        if jen_zdroj and zdroj.get("id") != jen_zdroj:
            continue
        if not jen_zdroj and not zdroj.get("aktivni", True):
            continue
        try:
            davka = nacti(vyrazy_pro(zdroj, config))
            print(f"  {zdroj['nazev']}: {len(davka)} nabidek")
            nalezene.extend(davka)
        except Exception as chyba:
            print(f"  {zdroj['nazev']}: selhalo ({chyba})")
            chyby.append({"zdroj": zdroj["nazev"], "chyba": str(chyba)})
    return nalezene, chyby


def vyhod_vyloucene(nabidky, config):
    slova = [s.lower() for s in config.get("vylucit_klicova_slova", [])]
    if not slova:
        return nabidky
    return [
        n for n in nabidky
        if not any(s in f"{n['nazev']} {n['popis']}".lower() for s in slova)
    ]


def hlavni():
    p = argparse.ArgumentParser()
    p.add_argument("--test", help="ID zdroje k otestovani")
    p.add_argument("--bez-ai", action="store_true")
    p.add_argument("--bez-firem", action="store_true")
    args = p.parse_args()

    config = cti("config.json", {})
    stav = cti("jobs.json", {"nabidky": []})
    hodnoceni = cti("ratings.json", {})
    cislenik = cti("companies.json", {})
    archiv = stav.get("nabidky", [])

    print("Ctu zdroje")
    nalezene, chyby = posbirej(config, jen_zdroj=args.test)

    if args.test:
        for n in nalezene[:8]:
            print(json.dumps(n, ensure_ascii=False, indent=2)[:700])
        print(f"\nCelkem {len(nalezene)} nabidek z tohoto zdroje.")
        return

    print("Slucuji duplicity")
    unikatni = dedupe.sluc(nalezene)
    print(f"  {len(nalezene)} nactenych, {len(unikatni)} po slouceni")

    znama = {n["id"] for n in archiv}
    nove = [n for n in unikatni if n["id"] not in znama]
    nove = vyhod_vyloucene(nove, config)
    print(f"Novych nabidek: {len(nove)}")

    if nove:
        kurzy = salary.nacti_kurzy()
        for n in nove:
            mzda = salary.z_nabidky(n, kurzy)
            if mzda:
                n["mzda"] = mzda

    if nove and not args.bez_ai:
        print("Hodnotim")
        vysledky = score.ohodnot(nove, config, hodnoceni, archiv)
        for n in nove:
            v = vysledky.get(n["id"], {})
            n["skore"] = v.get("skore", 0)
            n["duvod"] = v.get("duvod", "")
            n["deadline"] = v.get("deadline", "")
    else:
        for n in nove:
            n.setdefault("skore", 0)
            n.setdefault("duvod", "")
            n.setdefault("deadline", "")

    prah = config.get("prah_skore", 50)
    zajimave = [n for n in nove if n.get("skore", 0) >= prah]
    print(f"Nad prahem {prah}: {len(zajimave)}")

    if zajimave and not args.bez_firem:
        print("Dohledavam weby firem")
        cislenik = companies.doplnit(zajimave, cislenik)
        zapis("companies.json", cislenik)

    navrhy = []
    if not args.bez_ai:
        navrhy = score.navrhni_vyrazy(config, hodnoceni, archiv)
        if navrhy:
            print(f"  navrhuji {len(navrhy)} novych vyrazu do katalogu")

    hranice = datetime.now(timezone.utc) - timedelta(days=config.get("archiv_dnu", 90))
    ponechat = []
    for n in nove + archiv:
        try:
            kdy = datetime.fromisoformat(n["nalezeno"])
        except Exception:
            kdy = datetime.now(timezone.utc)
        if kdy >= hranice or n["id"] in hodnoceni:
            ponechat.append(n)
    ponechat.sort(key=lambda n: (n.get("nalezeno", ""), n.get("skore", 0)), reverse=True)

    zapis(
        "jobs.json",
        {
            "nabidky": ponechat,
            "posledni_beh": datetime.now(timezone.utc).isoformat(),
            "novych_dnes": len(nove),
            "navrhy_vyrazu": navrhy,
            "chyby": chyby,
        },
    )
    print(f"Ulozeno: {len(ponechat)} nabidek v archivu")


if __name__ == "__main__":
    sys.exit(hlavni())
