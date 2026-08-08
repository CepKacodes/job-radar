from . import ats, boards

REGISTR = {
    "jobscz": boards.jobscz,
    "pracecz": boards.pracecz,
    "startupjobs": boards.startupjobs,
    "hzm": boards.holkyzmarketingu,
    "euremotejobs": boards.euremotejobs,
    "tribee": boards.tribee,
    "rss": boards.rss,
    "greenhouse": ats.greenhouse,
    "lever": ats.lever,
    "recruitee": ats.recruitee,
}

# Zdroje, ktere berou hledane vyrazy z katalogu. Ostatni vraceji cely vypis.
S_VYRAZY = ("jobscz", "pracecz", "startupjobs")


def nacti(cfg):
    typ = cfg.get("typ")
    if typ not in REGISTR:
        raise ValueError(f"Nezname typ zdroje: {typ}. Dostupne: {', '.join(REGISTR)}")
    return REGISTR[typ](cfg)
