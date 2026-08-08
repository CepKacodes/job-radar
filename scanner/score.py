"""
Hodnoceni nabidek pomoci Claude API.

Model nedostava klicova slova, ale tvoje zadani napsane beznou cestinou
a tvoje predchozi hodnoceni na skale 1 az 5. Cim vic hodnoceni, tim spis
kopiruje tvoje rozhodovani misto toho, aby hadal z popisu.
"""

import json
import os

import anthropic

DAVKA = 6
PRIKLADU_NA_STUPEN = 4

SYSTEM = """Jsi asistent, ktery tridi pracovni nabidky pro jednu konkretni uzivatelku.

Dostanes jeji zadani, jeji predchozi hodnoceni na skale 1 az 5 (5 nejlepsi)
a seznam novych nabidek. U kazde nabidky vrat:

- skore 0 az 100, jak moc odpovida zadani
- jednu vetu cesky, proc ano nebo proc ne, konkretne a bez frazi
- deadline ve tvaru RRRR-MM-DD, POUZE kdyz je v textu vyslovne uveden
  termin pro podani prihlasky. Kdyz tam neni, vrat prazdny retezec.
  Nikdy datum nehadej a nepouzivej datum zverejneni.

Bud prisny. Skore nad 70 dej jen nabidkam, ktere by opravdu stalo za to otevrit.

Predchozi hodnoceni maji prednost pred zadanim. Kdyz uzivatelka opakovane
odmita urcity typ role, i kdyz zadani rika neco jineho, ridi se hodnocenim.
Pouzij i strednich stupnu: nabidka podobna tem, kterym dala 3, ma dostat
skore kolem padesati, ne osmdesat.

Odpovez vyhradne polem JSON, bez uvodu a bez markdown znacek:
[{"id": "...", "skore": 0, "duvod": "...", "deadline": ""}]"""

SYSTEM_VYRAZY = """Navrhni hledane vyrazy pro job boardy.

Dostanes zadani uzivatelky, vyrazy, ktere uz pouziva, a nazvy pozic, ktere
ohodnotila 4 nebo 5. Navrhni az osm NOVYCH vyrazu, ktere v katalogu jeste
nejsou a ktere by pomohly najit podobne role. Mysli na ceske i anglicke
varianty a na to, ze tataz role se jmenuje ruzne.

Vyrazy maji byt kratke, jedno az tri slova, tak jak by je clovek napsal
do vyhledavaciho pole.

Odpovez vyhradne polem JSON:
[{"vyraz": "...", "jazyk": "cs"}]"""


def _klient():
    klic = os.environ.get("ANTHROPIC_API_KEY")
    if not klic:
        raise RuntimeError(
            "Chybi ANTHROPIC_API_KEY. V GitHubu ho pridej do Settings, "
            "Secrets and variables, Actions."
        )
    return anthropic.Anthropic(api_key=klic)


def _text(odpoved):
    surovy = "".join(b.text for b in odpoved.content if b.type == "text")
    return surovy.replace("```json", "").replace("```", "").strip()


def _priklady(hodnoceni, archiv):
    """Kalibracni priklady rozdelene podle stupnu, vcetne stredu."""
    podle_id = {n["id"]: n for n in archiv}
    podle_stupne = {1: [], 2: [], 3: [], 4: [], 5: []}

    polozky = sorted(hodnoceni.items(), key=lambda kv: kv[1].get("kdy", ""), reverse=True)
    for job_id, zaznam in polozky:
        hvezdy = zaznam.get("hvezdy")
        nabidka = podle_id.get(job_id)
        if not hvezdy or not nabidka or hvezdy not in podle_stupne:
            continue
        if len(podle_stupne[hvezdy]) >= PRIKLADU_NA_STUPEN:
            continue
        podle_stupne[hvezdy].append(
            {
                "nazev": nabidka.get("nazev", ""),
                "firma": nabidka.get("firma", ""),
                "lokalita": nabidka.get("lokalita", ""),
                "poznamka": zaznam.get("poznamka", ""),
            }
        )
    return {str(k): v for k, v in podle_stupne.items() if v}


def ohodnot(nabidky, config, hodnoceni, archiv):
    """Vrati slovnik id -> {"skore", "duvod", "deadline"}."""
    if not nabidky:
        return {}

    client = _klient()
    model = config.get("model", "claude-sonnet-5")
    priklady = _priklady(hodnoceni, archiv)
    vysledky = {}

    for i in range(0, len(nabidky), DAVKA):
        davka = nabidky[i : i + DAVKA]
        obsah = {
            "zadani": config.get("zadani", ""),
            "moje_hodnoceni_podle_stupne": priklady,
            "nabidky": [
                {
                    "id": n["id"],
                    "nazev": n["nazev"],
                    "firma": n["firma"],
                    "lokalita": n["lokalita"],
                    "mzda": (n.get("mzda") or {}).get("text", ""),
                    "popis": n["popis"][:1500],
                }
                for n in davka
            ],
        }

        try:
            odpoved = client.messages.create(
                model=model,
                max_tokens=2000,
                system=SYSTEM,
                messages=[{"role": "user", "content": json.dumps(obsah, ensure_ascii=False)}],
            )
            for polozka in json.loads(_text(odpoved)):
                vysledky[polozka["id"]] = {
                    "skore": max(0, min(100, int(polozka.get("skore", 0)))),
                    "duvod": polozka.get("duvod", ""),
                    "deadline": (polozka.get("deadline") or "").strip(),
                }
        except Exception as chyba:
            print(f"  Davku se nepodarilo ohodnotit: {chyba}")

    return vysledky


def navrhni_vyrazy(config, hodnoceni, archiv):
    """Navrhne nove vyrazy do katalogu podle toho, co uzivatelku zaujalo."""
    podle_id = {n["id"]: n for n in archiv}
    oblibene = [
        podle_id[i]["nazev"]
        for i, z in hodnoceni.items()
        if z.get("hvezdy", 0) >= 4 and i in podle_id
    ][:25]
    if len(oblibene) < 3:
        return []

    stavajici = [p["vyraz"] for p in config.get("katalog", [])]
    obsah = {
        "zadani": config.get("zadani", ""),
        "uz_mam": stavajici,
        "pozice_ktere_me_zaujaly": oblibene,
    }

    try:
        odpoved = _klient().messages.create(
            model=config.get("model", "claude-sonnet-5"),
            max_tokens=700,
            system=SYSTEM_VYRAZY,
            messages=[{"role": "user", "content": json.dumps(obsah, ensure_ascii=False)}],
        )
        znama = {v.lower() for v in stavajici}
        return [
            {"vyraz": p["vyraz"], "jazyk": p.get("jazyk", "cs")}
            for p in json.loads(_text(odpoved))
            if p.get("vyraz") and p["vyraz"].lower() not in znama
        ][:8]
    except Exception as chyba:
        print(f"  Navrhy vyrazu selhaly: {chyba}")
        return []
