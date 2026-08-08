"""Spolecne pomucky pro vsechny zdroje."""

import hashlib
import json
import re
import time
import unicodedata
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0 Safari/537.36"
)

session = requests.Session()
session.headers.update({"User-Agent": UA, "Accept-Language": "cs,en;q=0.8"})


def fetch(url, **kwargs):
    time.sleep(1.0)
    r = session.get(url, timeout=30, **kwargs)
    r.raise_for_status()
    return r


def soup_of(url):
    return BeautifulSoup(fetch(url).text, "lxml")


def bez_diakritiky(text):
    rozlozene = unicodedata.normalize("NFKD", text or "")
    return "".join(z for z in rozlozene if not unicodedata.combining(z))


def clean_text(value, limit=2500):
    if not value:
        return ""
    text = BeautifulSoup(str(value), "lxml").get_text(" ")
    return re.sub(r"\s+", " ", text).strip()[:limit]


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def job(url, title, company="", location="", snippet="", posted="", source="", mzda_text=""):
    """
    Jednotny tvar nabidky.

    Odkazy jsou seznam, protoze tatáz pozice se casto najde na vic mistech
    a po deduplikaci si drzime vsechny.
    """
    cista = (url or "").split("?")[0]
    return {
        "id": hashlib.sha1(cista.rstrip("/").encode("utf-8")).hexdigest()[:16],
        "odkazy": [{"zdroj": source, "url": cista}] if cista else [],
        "nazev": clean_text(title, 200),
        "firma": clean_text(company, 120),
        "lokalita": clean_text(location, 120),
        "popis": clean_text(snippet),
        "mzda_text": clean_text(mzda_text, 120),
        "zverejneno": posted or "",
        "nalezeno": now_iso(),
    }


def json_ld_jobs(soup, base_url, source):
    """Zaloha pro weby, ktere maji strukturovana data JobPosting."""
    nalezene = []

    def projdi(uzel):
        if isinstance(uzel, dict):
            if uzel.get("@type") == "JobPosting":
                nalezene.append(uzel)
            for hodnota in uzel.values():
                projdi(hodnota)
        elif isinstance(uzel, list):
            for polozka in uzel:
                projdi(polozka)

    for tag in soup.find_all("script", type="application/ld+json"):
        raw = tag.string or tag.get_text()
        if not raw:
            continue
        try:
            projdi(json.loads(raw))
        except Exception:
            continue

    out = []
    for post in nalezene:
        org = post.get("hiringOrganization") or {}
        misto = post.get("jobLocation")
        if isinstance(misto, list) and misto:
            misto = misto[0]
        lokalita = ""
        if isinstance(misto, dict):
            adresa = misto.get("address", {})
            if isinstance(adresa, dict):
                lokalita = adresa.get("addressLocality") or adresa.get("addressRegion") or ""
        out.append(
            job(
                url=post.get("url") or base_url,
                title=post.get("title", ""),
                company=org.get("name", "") if isinstance(org, dict) else str(org),
                location=lokalita,
                snippet=post.get("description", ""),
                posted=post.get("datePosted", ""),
                source=source,
            )
        )
    return out
