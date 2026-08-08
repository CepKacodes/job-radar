"""
Slucovani stejne nabidky nalezene na vic mistech.

Deduplikace podle URL nestaci, protoze tataz pozice ma na Jobs.cz a na
kariernim webu firmy jinou adresu. Poustime se proto do porovnavani firmy
a nazvu, ale zamerne opatrne: radeji necham dve karty, nez abych smazal
pozici, ktera byla ve skutecnosti jina.
"""

import re
from difflib import SequenceMatcher

from .sources.base import bez_diakritiky

PRAH_PODOBNOSTI = 0.87

PRAVNI_FORMY = (
    "s.r.o.", "s. r. o.", "a.s.", "a. s.", "spol.", "k.s.", "v.o.s.",
    "sro", "as", "ltd", "gmbh", "b.v.", "inc.", "plc", "se",
)

SUM = (
    "m/f/d", "m/w/d", "f/m/x", "praha", "brno", "remote", "hybrid",
    "full time", "part time", "fulltime", "hpp", "zkraceny uvazek",
)


def _norm(text):
    text = bez_diakritiky(text or "").lower()
    text = re.sub(r"[\(\[].*?[\)\]]", " ", text)
    for kus in SUM:
        text = text.replace(kus, " ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def klic_firmy(firma):
    zaklad = _norm(firma)
    for forma in PRAVNI_FORMY:
        zaklad = zaklad.replace(_norm(forma), " ")
    zaklad = re.sub(r"\b(cz|czech|republic|cesko|ceska)\b", " ", zaklad)
    return re.sub(r"\s+", " ", zaklad).strip()


def klic_pozice(nazev):
    """
    Sjednoti prechylovani a lomitkove varianty, kterych je v ceskych
    inzeratech plno: manazer/manazerka, specialist(k)a a podobne.
    """
    zaklad = _norm(nazev)
    zaklad = re.sub(r"\b(\w+?)(ka|ky|kou)\b", r"\1", zaklad)
    zaklad = re.sub(r"\b(manazer|manager)\w*", "manager", zaklad)
    zaklad = re.sub(r"\b(specialist)\w*", "specialist", zaklad)
    zaklad = re.sub(r"\b(koordinator)\w*", "koordinator", zaklad)
    # Jednopismenne zbytky vznikaji po odstraneni zavorek ve tvarech jako
    # "specialist(k)a" a jinak by ta stejna pozice vysla jako dve ruzne.
    slova = sorted({s for s in zaklad.split() if len(s) > 1})
    return " ".join(slova)


def _shoduje_se(a, b):
    fa, fb = klic_firmy(a["firma"]), klic_firmy(b["firma"])
    if not fa or not fb or fa != fb:
        return False
    pa, pb = klic_pozice(a["nazev"]), klic_pozice(b["nazev"])
    if not pa or not pb:
        return False
    if pa == pb:
        return True
    return SequenceMatcher(None, pa, pb).ratio() >= PRAH_PODOBNOSTI


def sluc(nabidky):
    """Vrati seznam bez duplicit, s odkazy na vsechna nalezena mista."""
    vysledek = []
    podle_id = {}

    for n in nabidky:
        if n["id"] in podle_id:
            _pridej_odkazy(podle_id[n["id"]], n)
            continue

        shoda = None
        if n.get("firma"):
            for stavajici in vysledek:
                if _shoduje_se(stavajici, n):
                    shoda = stavajici
                    break

        if shoda:
            _pridej_odkazy(shoda, n)
            _doplnit_prazdna(shoda, n)
        else:
            vysledek.append(n)
            podle_id[n["id"]] = n

    return vysledek


def _pridej_odkazy(cil, zdroj):
    existujici = {o["url"] for o in cil.get("odkazy", [])}
    for odkaz in zdroj.get("odkazy", []):
        if odkaz["url"] not in existujici:
            cil.setdefault("odkazy", []).append(odkaz)
            existujici.add(odkaz["url"])


def _doplnit_prazdna(cil, zdroj):
    """Kdyz jeden zdroj uvadi mzdu nebo lokalitu a druhy ne, vezmi tu vyplnenou."""
    for pole in ("lokalita", "mzda_text", "zverejneno"):
        if not cil.get(pole) and zdroj.get(pole):
            cil[pole] = zdroj[pole]
    if len(zdroj.get("popis", "")) > len(cil.get("popis", "")):
        cil["popis"] = zdroj["popis"]
