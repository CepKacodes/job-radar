# Job Radar

Každé ráno projde vybrané job boardy a kariérní stránky, sloučí duplicity,
nechá Claude ohodnotit každou novou nabídku proti tvému zadání a výsledek
uloží do dashboardu. Co ohodnotíš hvězdičkami, to se příští ráno použije
jako kalibrace, takže doporučování se postupně zpřesňuje.

Nic z toho neběží na tvém počítači. GitHub Actions to spustí samo.

---

## Nastavení

1. Založ si na GitHubu repozitář `job-radar` a nahraj do něj obsah tohohle balíčku.
2. Vygeneruj si API klíč na `console.anthropic.com`.
3. V repozitáři: **Settings, Secrets and variables, Actions, New repository secret**.
   Jméno přesně `ANTHROPIC_API_KEY`, hodnota tvůj klíč.
4. **Settings, Pages**, zdroj Deploy from a branch, větev `main`, složka `/ (root)`.
5. Vytvoř si fine-grained token s právem **Contents: Read and write** jen pro tenhle
   repozitář. V dashboardu ho vlož do Nastavení spolu s `tvojejmeno/job-radar`.
6. **Actions, Ranní sken nabídek, Run workflow** a podívej se do logu.

Privátní repozitář s Pages vyžaduje placený plán. S free účtem buď nech repozitář
veřejný (klíč je v secrets, ne v souborech), nebo si dashboard otevírej lokálně
příkazem `python -m http.server` ve složce projektu.

---

## Jak se to používá

Ráno otevřeš dashboard. Záložky odpovídají tomu, v jaké fázi nabídka je.

**Nové** jsou nabídky nad prahem skóre, které jsi ještě neřešila. U každé je
název, firma, místo, mzda a jedna věta, proč to sedí. Vlevo je tenký proužek,
jehož výška odpovídá skóre. Číslo se ukáže po najetí myší, protože skóre je
odhad, ne známka, a nemá tě ukotvit dřív, než si přečteš, o co jde.

**Hvězdičky 1 až 5** jsou tvoje hodnocení kvality nabídky. **Stav** vedle nich
říká, co s ní děláš. Jsou to dvě různé věci schválně: trojka není rozhodnutí.
Z Nové zmizí až to, čemu dáš nějaký stav.

**Zajímavé** drží nabídky, které řešíš. Tady je pořadí tvoje. Podrž prst nebo
myš na kartě, karta se zvedne, a přetáhni ji, kam patří. Pořadí je další signál
pro hodnocení, ne jen vizuální pomůcka.

**Přihlášky** se otevřou samy, jakmile přepneš stav na přihlášena. Datum odeslání
se předvyplní. Doplň si verzi CV, dopis, kontakt a poznámky. Doba odezvy se počítá
sama a po deseti dnech bez odpovědi se to zvýrazní.

**Katalog** je seznam hledaných výrazů. U každého vidíš, kolik nabídek přinesl
a kolik z nich jsi ohodnotila čtyřkou nebo pětkou. Po pár týdnech je černé na bílém,
který výraz tahá jen balast. Model navrhuje nové výrazy podle toho, co tě zaujalo,
ale nikdy si nic nepřidá sám.

Po každé změně klikni **Uložit změny**. Bez toho se nic nezapíše.

---

## Zdroje

**Job boardy** (Jobs.cz, Prace.cz, StartupJobs) berou výrazy z katalogu. Nabírej
široce, klidně jen "marketing", a přísnost nech na modelu. Ten umí posoudit celý
popis, kdežto vyhledávání na boardu hledá jen text, takže "Vedoucí značky" ti pod
výrazem "brand manager" nikdy nepropadne.

**Komunitní a oborové výpisy** (Holky z marketingu, EU Remote Jobs, Tribee) vracejí
celý svůj výpis, výrazy nepotřebují.

**Kariérní stránky firem** přes Greenhouse, Lever a Recruitee jsou nejspolehlivější,
protože mají veřejné API. Název boardu poznáš z URL kariérní stránky firmy: když
tam vidíš `boards.greenhouse.io/rohlik`, přidej zdroj typu Greenhouse s boardem
`rohlik`. Když sken u firmy sám zjistí, že takový systém používá, uloží si to
do `data/companies.json`.

LinkedIn a Glassdoor tam schválně nejsou. Oba scraping zakazují a brání se mu,
LinkedIn za něj ruší účty. Nastav si na nich radši upozornění a používej je ručně.

---

## Mzdy a měny

Mzda se čte z inzerátu, když ji uvádí. Cizí měny se přepočítávají kurzem ČNB,
který se stahuje při každém skenu zdarma a bez klíče. Ukládá se originál i přepočet
na hrubou měsíční mzdu v korunách, aby šly nabídky z různých zemí vůbec srovnat.
Roční mzdy se dělí dvanácti, hodinové sazby se násobí 160 hodinami.

Filtr na minimální mzdu tam schválně není. Vyhazoval by přesně ty nabídky, kde se
o mzdě jedná, a těch je zhruba polovina.

---

## Deduplikace

Stejná pozice se často najde na víc místech. Slučuje se podle firmy a názvu, ne
podle URL, protože kariérní stránka má jinou adresu než Jobs.cz. Sjednocuje se
přechylování a lomítkové tvary, takže "Marketing manažer/manažerka" a "Marketing
manager" u téže firmy splynou. U nabídky pak vidíš odkazy na všechna nalezená místa.

Nastaveno je to konzervativně: raději zůstanou dvě karty, než aby zmizela pozice,
která byla ve skutečnosti jiná.

---

## Když něco přestane fungovat

```bash
pip install -r requirements.txt
python -m scanner.main --test jobscz     # zkusí jeden zdroj a vypíše, co našel
python -m scanner.main --bez-ai          # načte nabídky, ale nehodnotí
python -m scanner.main --bez-firem       # přeskočí dohledávání webů firem
```

Když zdroj vrátí nula nabídek, změnil se web. Parser výpisů je v
`scanner/sources/boards.py` ve funkci `_karty`. Pošli mi výpis z testu a upravím to.

Sken běží v pracovní dny v 5:10 UTC. Čas změníš v `.github/workflows/scan.yml`.

---

## Kolik to stojí

GitHub Actions je pro tenhle objem zdarma. Platí se jen API. Při dvaceti nových
nabídkách denně vychází Haiku řádově na deset korun měsíčně, Sonnet na trojnásobek.
Vyloučená slova to sráží dál, protože filtrují ještě před voláním API.

---

## Co je kde

```
index.html                  dashboard
data/config.json            zadání, parametry, katalog výrazů, zdroje
data/jobs.json              nalezené nabídky se skóre
data/ratings.json           hvězdičky, stavy, pořadí a spisy přihlášek
data/companies.json         weby a kariérní stránky firem
data/kurzy.json             poslední kurzy ČNB
scanner/main.py             hlavní běh
scanner/score.py            hodnocení a návrhy výrazů
scanner/salary.py           čtení mzdy a přepočet měn
scanner/dedupe.py           slučování duplicit
scanner/companies.py        dohledávání webů firem
scanner/sources/            adaptéry jednotlivých zdrojů
```

V `data/jobs.json` jsou tři ukázkové nabídky, aby sis mohla dashboard prohlédnout
ještě před prvním skenem. Zmizí samy.
