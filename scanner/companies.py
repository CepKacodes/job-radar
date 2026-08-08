"""
Dohledani webu a kariernim stranky firmy.

Bezi jednou na firmu, ne na nabidku, a vysledek se uklada, takze pri paté
nabidce od stejne firmy uz se nic nehleda. Spousti se az po hodnoceni a jen
u nabidek nad prahem, protoze u odpadu to nema smysl.
"""

import re
from urllib.parse import urlparse

from .dedupe import klic_firmy
from .sources.base import bez_diakritiky, fetch, session

CESTY = (
    "/kariera", "/kariera/", "/kariera/volna-mista", "/kariera/volne-pozice",
    "/prace", "/prace-u-nas", "/volna-mista", "/nabidka-prace",
    "/careers", "/careers/", "/careers/jobs", "/jobs", "/join-us", "/work-with-us",
)

ZNAKY_KARIERY = (
    "volna mista", "volne pozice", "kariera", "nabidka prace", "pridej se",
    "careers", "open positions", "join our team", "we are hiring", "job openings",
)

ATS_STOPY = {
    "greenhouse": r"boards\.greenhouse\.io/([a-z0-9_-]+)",
    "lever": r"jobs\.lever\.co/([a-z0-9_-]+)",
    "recruitee": r"([a-z0-9-]+)\.recruitee\.com",
    "teamtailor": r"([a-z0-9-]+)\.teamtailor\.com",
    "workable": r"apply\.workable\.com/([a-z0-9_-]+)",
}


def _zkus(url, timeout=8):
    try:
        r = session.get(url, timeout=timeout, allow_redirects=True)
        return r if r.status_code == 200 else None
    except Exception:
        return None


def najdi_web(firma):
    """Zkusi odhadnout domenu z nazvu firmy. Overi, ze stranka opravdu existuje."""
    zaklad = re.sub(r"[^a-z0-9]", "", bez_diakritiky(firma).lower())
    if len(zaklad) < 3:
        return ""
    for koncovka in (".cz", ".com", ".eu", ".io"):
        for schema in ("https://www.", "https://"):
            odpoved = _zkus(f"{schema}{zaklad}{koncovka}")
            if odpoved:
                return f"{odpoved.url.rstrip('/')}"
    return ""


def najdi_karieru(web):
    """Projde obvykle cesty a overi, ze stranka vypada jako kariernim."""
    if not web:
        return "", ""
    korenova = _zkus(web)
    if korenova:
        z_odkazu = _kariera_z_odkazu(korenova.text, web)
        if z_odkazu:
            return z_odkazu, _ats_z_textu(korenova.text)

    for cesta in CESTY:
        odpoved = _zkus(web.rstrip("/") + cesta)
        if not odpoved:
            continue
        text = bez_diakritiky(odpoved.text[:200000]).lower()
        if any(znak in text for znak in ZNAKY_KARIERY):
            return odpoved.url, _ats_z_textu(odpoved.text)
    return "", ""


def _kariera_z_odkazu(html, web):
    domena = urlparse(web).netloc
    for cil, popisek in re.findall(r'href="([^"]+)"[^>]*>([^<]{0,60})<', html, re.I):
        stitek = bez_diakritiky(popisek).lower()
        if any(znak in stitek for znak in ZNAKY_KARIERY):
            if cil.startswith("/"):
                return f"https://{domena}{cil}"
            if domena in cil or "greenhouse" in cil or "lever" in cil or "recruitee" in cil:
                return cil
    return ""


def _ats_z_textu(html):
    """Kdyz firma jede na znamem systemu, poznáme to a jde ji pridat jako zdroj."""
    for typ, vzor in ATS_STOPY.items():
        shoda = re.search(vzor, html, re.I)
        if shoda:
            return f"{typ}:{shoda.group(1)}"
    return ""


def doplnit(nabidky, cislenik):
    """Doplni odkazy k nabidkam a rozsiri cislenik firem."""
    for n in nabidky:
        firma = n.get("firma", "")
        if not firma:
            continue
        klic = klic_firmy(firma)
        if not klic:
            continue

        if klic not in cislenik:
            web = najdi_web(firma)
            kariera, ats = najdi_karieru(web) if web else ("", "")
            cislenik[klic] = {"nazev": firma, "web": web, "kariera": kariera, "ats": ats}
            print(f"  {firma}: web {'ano' if web else 'ne'}, kariera {'ano' if kariera else 'ne'}")

        zaznam = cislenik[klic]
        n["web"] = zaznam.get("web", "")
        n["kariera"] = zaznam.get("kariera", "")
        n["ats"] = zaznam.get("ats", "")
    return cislenik
