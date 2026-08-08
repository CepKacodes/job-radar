"""Zdroje: job boardy a komunitni vypisy."""

import re
from urllib.parse import quote_plus, urljoin

from .base import fetch, job, json_ld_jobs, soup_of


def _vyrazy(cfg):
    """Zdroj muze mit vic hledanych vyrazu z katalogu."""
    seznam = cfg.get("vyrazy") or ([cfg["dotaz"]] if cfg.get("dotaz") else [])
    return [v.strip() for v in seznam if v and v.strip()] or [""]


def _karty(soup, base_url, zdroj, href_filtr=None):
    """
    Univerzalni cteni vypisu.

    Boardy meni tridy v HTML kazdych par mesicu, takze se drzime struktury:
    nabidka je article nebo polozka seznamu s odkazem a nadpisem.
    Kdyz prestane vracet vysledky, spust `--test <id-zdroje>`.
    """
    out, videne = [], set()
    for karta in soup.select("article, li[class*='earch'], div[class*='earch'], div[class*='job'], li[class*='job']"):
        odkaz = karta.find("a", href=True)
        if not odkaz:
            continue
        url = urljoin(base_url, odkaz["href"])
        if href_filtr and href_filtr not in url:
            continue
        if url in videne:
            continue
        videne.add(url)

        nadpis = karta.find(["h2", "h3"]) or odkaz
        firma = karta.select_one("[class*='ompany'], [data-test*='company'], [class*='employer']")
        misto = karta.select_one("[class*='ocation'], [class*='ocalit'], [data-test*='location']")
        mzda = karta.select_one("[class*='alar'], [class*='mzd'], [class*='wage']")

        out.append(
            job(
                url=url,
                title=nadpis.get_text(" ", strip=True),
                company=firma.get_text(" ", strip=True) if firma else "",
                location=misto.get_text(" ", strip=True) if misto else "",
                snippet=karta.get_text(" ", strip=True),
                mzda_text=mzda.get_text(" ", strip=True) if mzda else "",
                source=zdroj,
            )
        )

    return out or json_ld_jobs(soup, base_url, zdroj)


def _pro_kazdy_vyraz(cfg, sestav_url, href_filtr=None):
    out = []
    for vyraz in _vyrazy(cfg):
        url = sestav_url(vyraz)
        try:
            out.extend(_karty(soup_of(url), url, cfg["nazev"], href_filtr))
        except Exception as chyba:
            print(f"    vyraz '{vyraz}' selhal: {chyba}")
    return out


def jobscz(cfg):
    lokalita = (cfg.get("lokalita") or "").strip("/")
    cesta = f"/prace/{lokalita}/" if lokalita else "/prace/"
    return _pro_kazdy_vyraz(
        cfg, lambda v: f"https://www.jobs.cz{cesta}?q%5B%5D={quote_plus(v)}"
    )


def pracecz(cfg):
    lokalita = (cfg.get("lokalita") or "").strip("/")
    cesta = f"/nabidky/{lokalita}/" if lokalita else "/nabidky/"
    return _pro_kazdy_vyraz(
        cfg, lambda v: f"https://www.prace.cz{cesta}?q%5B%5D={quote_plus(v)}"
    )


def startupjobs(cfg):
    return _pro_kazdy_vyraz(
        cfg,
        lambda v: f"https://www.startupjobs.cz/nabidky?hledani={quote_plus(v)}",
        href_filtr="/nabidka/",
    )


def holkyzmarketingu(cfg):
    """
    Rucne vybirane marketingove pozice. Vypis nacita dalsi davky tlacitkem,
    takze prochazime i strankovani.
    """
    zaklad = "https://www.holkyzmarketingu.cz/hzmjobs-nabidky/"
    out, videne = [], set()

    for stranka in range(1, int(cfg.get("stranek", 3)) + 1):
        url = zaklad if stranka == 1 else f"{zaklad}page/{stranka}/"
        try:
            soup = soup_of(url)
        except Exception:
            break

        nalezeno = 0
        for odkaz in soup.select("a[href*='/volne-misto/']"):
            cil = urljoin(url, odkaz["href"]).split("?")[0]
            if cil in videne:
                continue
            videne.add(cil)
            nalezeno += 1

            blok = odkaz.find_parent(["article", "div", "li"]) or odkaz
            text = blok.get_text(" ", strip=True)
            out.append(
                job(
                    url=cil,
                    title=odkaz.get_text(" ", strip=True) or _z_slugu(cil),
                    location=_najdi(text, ["Praha", "Brno", "Ostrava", "home office", "remote"]),
                    snippet=text,
                    source=cfg["nazev"],
                )
            )
        if not nalezeno:
            break

    return out


def euremotejobs(cfg):
    """
    Remote nabidky pro evropske casove zony. Mzdy uvadi casto, ale v cizich
    menach, takze se tady uplatni prepocet.
    """
    kategorie = cfg.get("kategorie", "remote-marketing-jobs")
    url = f"https://euremotejobs.com/jobs/{kategorie}/"
    soup = soup_of(url)

    out, videne = [], set()
    for odkaz in soup.select("a[href*='/job/']"):
        cil = urljoin(url, odkaz["href"]).split("?")[0]
        if cil in videne:
            continue
        videne.add(cil)

        text = odkaz.get_text(" ", strip=True)
        out.append(
            job(
                url=cil,
                title=_orizni_firmu(text),
                company=_prvni_slova(text),
                location=_mezi(text, "Location", "Job Type"),
                snippet=text,
                mzda_text=_mzda_z_textu(text),
                source=cfg["nazev"],
            )
        )
    return out


def tribee(cfg):
    url = "https://www.tribee.cz/cs/prace"
    soup = soup_of(url)
    out = _karty(soup, url, cfg["nazev"], href_filtr="/prace/")
    if out:
        return out

    videne = []
    for odkaz in soup.select("a[href*='/prace/'], a[href*='/nabidka/']"):
        cil = urljoin(url, odkaz["href"]).split("?")[0]
        if cil == url or cil in [n["odkazy"][0]["url"] for n in videne if n["odkazy"]]:
            continue
        videne.append(
            job(url=cil, title=odkaz.get_text(" ", strip=True),
                snippet=odkaz.get_text(" ", strip=True), source=cfg["nazev"])
        )
    return videne


def rss(cfg):
    from bs4 import BeautifulSoup

    xml = BeautifulSoup(fetch(cfg["url"]).text, "xml")
    out = []
    for polozka in xml.find_all(["item", "entry"]):
        odkaz = polozka.find("link")
        href = odkaz.get("href") if odkaz and odkaz.get("href") else (odkaz.text if odkaz else "")
        if not href:
            continue
        titulek = polozka.find("title")
        popis = polozka.find(["description", "summary", "content"])
        datum = polozka.find(["pubDate", "published", "updated"])
        out.append(
            job(
                url=href,
                title=titulek.get_text(strip=True) if titulek else "",
                snippet=popis.get_text(" ", strip=True) if popis else "",
                posted=datum.get_text(strip=True) if datum else "",
                source=cfg["nazev"],
            )
        )
    return out


def _z_slugu(url):
    return url.rstrip("/").split("/")[-1].replace("-", " ").capitalize()


def _najdi(text, moznosti):
    for m in moznosti:
        if m.lower() in text.lower():
            return m
    return ""


def _mezi(text, od, do):
    shoda = re.search(re.escape(od) + r"(.*?)" + re.escape(do), text, re.S)
    return shoda.group(1).strip()[:120] if shoda else ""


def _prvni_slova(text, kolik=3):
    return " ".join(text.split()[:kolik])


def _orizni_firmu(text):
    return re.sub(r"\s*(Location|Job Type|Posted)\b.*$", "", text).strip()[:200]


def _mzda_z_textu(text):
    shoda = re.search(
        r"[€$£]?\s?[\d][\d\s.,]*\s*(?:K|k)?\s*(?:-|–|to)?\s*[€$£]?\s?[\d\s.,]*\s*"
        r"(?:USD|EUR|GBP|PLN|CZK|Kč)[^.]{0,30}",
        text,
    )
    return shoda.group(0).strip() if shoda else ""
