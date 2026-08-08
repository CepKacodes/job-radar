"""
Cteni mzdy z textu inzeratu a prepocet na koruny.

Kurzy tahame z CNB, ktera je zverejnuje volne a bez klice. Kdyz stazeni
selze, pouzijou se posledni ulozene, at kvuli tomu nespadne cely sken.
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .sources.base import fetch

CNB_URL = (
    "https://www.cnb.cz/cs/financni-trhy/devizovy-trh/"
    "kurzy-devizoveho-trhu/kurzy-devizoveho-trhu/denni_kurz.txt"
)
KURZY_SOUBOR = Path(__file__).resolve().parent.parent / "data" / "kurzy.json"

MESICU_V_ROCE = 12
HODIN_V_MESICI = 160

MENY = {
    "kč": "CZK", "kc": "CZK", "czk": "CZK", "korun": "CZK",
    "€": "EUR", "eur": "EUR",
    "$": "USD", "usd": "USD",
    "£": "GBP", "gbp": "GBP",
    "pln": "PLN", "zł": "PLN",
}

ROK = ("rok", "ročně", "rocne", "year", "annum", "annually", "p.a.", "yearly")
HODINA = ("hodin", "hour", "hourly", "/hr", "per hour")
MESIC = ("měsíc", "mesic", "měsíčně", "mesicne", "month", "monthly")


def nacti_kurzy():
    """Vrati slovnik kod meny -> kurz ke koruně, plus datum kurzu."""
    try:
        text = fetch(CNB_URL).text
        radky = text.strip().split("\n")
        datum = radky[0].split(" ")[0]
        kurzy = {"CZK": 1.0}
        for radek in radky[2:]:
            casti = radek.split("|")
            if len(casti) < 5:
                continue
            mnozstvi = float(casti[2].replace(",", "."))
            kurz = float(casti[4].replace(",", "."))
            kurzy[casti[3]] = kurz / mnozstvi
        ulozeny = {"datum": datum, "kurzy": kurzy}
        KURZY_SOUBOR.write_text(json.dumps(ulozeny, ensure_ascii=False, indent=2), encoding="utf-8")
        return ulozeny
    except Exception as chyba:
        print(f"  Kurzy CNB se nepodarilo stahnout ({chyba}), beru ulozene")
        if KURZY_SOUBOR.exists():
            return json.loads(KURZY_SOUBOR.read_text(encoding="utf-8"))
        return {"datum": "", "kurzy": {"CZK": 1.0}}


def _mena(text):
    nizky = text.lower()
    for znak, kod in MENY.items():
        if znak in nizky:
            return kod
    return None


def _obdobi(text, mena):
    nizky = text.lower()
    if any(s in nizky for s in HODINA):
        return "hodina"
    if any(s in nizky for s in ROK):
        return "rok"
    if any(s in nizky for s in MESIC):
        return "mesic"
    # Ceske inzeraty uvadeji mesicni mzdu, zahranicni rocni.
    return "mesic" if mena == "CZK" else "rok"


def _cisla(text, minimum=100):
    """Vytahne castky vcetne zkratek typu 110K nebo 50 tis."""
    out = []
    for surove, nasobic in re.findall(r"(\d[\d\s.,]*)\s*(k\b|tis\.?|000)?", text, re.I):
        cistka = surove.strip().replace(" ", "").replace("\u00a0", "")
        if not cistka or not cistka[0].isdigit():
            continue
        # Tecka i carka muzou byt oddelovac tisicu i desetin, rozhodne posledni skupina.
        if re.search(r"[.,]\d{3}\b", cistka):
            cistka = re.sub(r"[.,](?=\d{3}\b)", "", cistka)
        cistka = cistka.replace(",", ".")
        try:
            hodnota = float(cistka)
        except ValueError:
            continue
        if nasobic and nasobic.lower().startswith(("k", "tis")):
            hodnota *= 1000
        if hodnota >= minimum:
            out.append(hodnota)
    return out


def precti(text, kurzy):
    """
    Vrati strukturu mzdy, nebo None kdyz v textu zadna neni.

    Ulozi original i prepocet na mesicni hrubou mzdu v korunach, aby sly
    nabidky z ruznych zemi vubec porovnat.
    """
    if not text:
        return None
    mena = _mena(text)
    if not mena:
        return None

    obdobi = _obdobi(text, mena)
    # Hodinove sazby jsou mala cisla, mesicni a rocni velka. Prah proto
    # zalezi na obdobi, jinak by se sazba 40 dolaru za hodinu zahodila.
    castky = _cisla(text, minimum=5 if obdobi == "hodina" else 100)
    if not castky:
        return None

    kurz = kurzy.get("kurzy", {}).get(mena)
    nizka, vysoka = min(castky), max(castky)

    def na_mesic_czk(hodnota):
        if not kurz:
            return None
        v_czk = hodnota * kurz
        if obdobi == "rok":
            v_czk /= MESICU_V_ROCE
        elif obdobi == "hodina":
            v_czk *= HODIN_V_MESICI
        return int(round(v_czk / 100.0) * 100)

    return {
        "text": text.strip()[:120],
        "mena": mena,
        "obdobi": obdobi,
        "min": nizka,
        "max": vysoka if vysoka != nizka else None,
        "czk_mesic_min": na_mesic_czk(nizka),
        "czk_mesic_max": na_mesic_czk(vysoka) if vysoka != nizka else None,
        "kurz_datum": kurzy.get("datum", ""),
        "prepocteno": mena != "CZK",
    }


def z_nabidky(nabidka, kurzy):
    """Zkusi mzdu nejdriv z vyhrazeneho pole, pak z popisu."""
    mzda = precti(nabidka.get("mzda_text", ""), kurzy)
    if mzda:
        return mzda
    popis = nabidka.get("popis", "")
    for veta in re.split(r"(?<=[.!?;])\s+|\n", popis):
        if _mena(veta) and _cisla(veta):
            mzda = precti(veta, kurzy)
            if mzda:
                return mzda
    return None
