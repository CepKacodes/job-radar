"""
Zdroje: kariernim stranky firem.

Tyhle systemy maji verejne JSON API, takze jsou nejspolehlivejsi ze vsech
zdroju. Nazev boardu poznas z URL kariernim stranky firmy.
"""

from .base import fetch, job


def greenhouse(cfg):
    board = cfg["board"]
    data = fetch(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true").json()
    return [
        job(
            url=i.get("absolute_url", ""),
            title=i.get("title", ""),
            company=cfg.get("firma", board),
            location=(i.get("location") or {}).get("name", ""),
            snippet=i.get("content", ""),
            posted=i.get("updated_at", ""),
            source=cfg["nazev"],
        )
        for i in data.get("jobs", [])
        if i.get("absolute_url")
    ]


def lever(cfg):
    board = cfg["board"]
    data = fetch(f"https://api.lever.co/v0/postings/{board}?mode=json").json()
    return [
        job(
            url=i.get("hostedUrl", ""),
            title=i.get("text", ""),
            company=cfg.get("firma", board),
            location=(i.get("categories") or {}).get("location", ""),
            snippet=i.get("descriptionPlain") or i.get("description", ""),
            posted=i.get("createdAt", ""),
            mzda_text=(i.get("salaryRange") or {}).get("text", ""),
            source=cfg["nazev"],
        )
        for i in data
        if i.get("hostedUrl")
    ]


def recruitee(cfg):
    board = cfg["board"]
    data = fetch(f"https://{board}.recruitee.com/api/offers/").json()
    return [
        job(
            url=i.get("careers_url") or i.get("careers_apply_url", ""),
            title=i.get("title", ""),
            company=cfg.get("firma", board),
            location=i.get("location", ""),
            snippet=i.get("description", ""),
            posted=i.get("published_at", ""),
            mzda_text=i.get("salary_text", "") or "",
            source=cfg["nazev"],
        )
        for i in data.get("offers", [])
        if i.get("careers_url") or i.get("careers_apply_url")
    ]
