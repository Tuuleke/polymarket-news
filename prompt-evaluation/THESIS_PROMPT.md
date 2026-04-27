# Juhised lõputöö peatüki kirjutamiseks

Sa oled akadeemiline kirjutamisassistent. Kirjuta alloleva konteksti põhjal **bakalaureusetöö peatükk eesti keeles**.

**Nõuded:**
- Keel: eesti keel, akadeemiline toon
- Maht: 1200–1800 sõna
- Tase: bakalaureusetöö (ei eelda lugejalt sügavaid tehnilisi eelteadmisi, kuid tehnilisi mõisteid selgitada lühidalt)
- Koodinäiteid kasutatakse illustratsioonina — integreeri need teksti loomulikult, kommenteeri nende eesmärki
- Peatüki nimi: **"Artiklite kvaliteedi hindamissüsteem"** (või sobilik alternatiiv)
- Struktuur: sissejuhatus → süsteemi arhitektuur → veebiandmetega põhjendamine → LLM-as-a-judge metoodika → hindamiskriteeriumid → põhjendatud hindamispass → kokkuvõte

---

# Kontekst: Polymarket News projekt

## Mis on Polymarket News?

Polymarket News on veebirakendus, mis tõmbab automaatselt ennustusmängude andmeid Polymarket platvormilt ja genereerib nende põhjal lühikesi uudisartikleid suurkeelemudelite (LLM) abil. Rakenduse backend on kirjutatud FastAPI raamistikuga (Python), kasutab PostgreSQL andmebaasi ning suhtleb LLM-idega OpenRouter API kaudu — see on ühtne OpenAI-ühilduv liides, mis võimaldab lülituda erinevate mudelite vahel ilma koodimuutusteta.

### Kaks artikli tüüpi

**1. Explanation (selgitus)** — igapäevaülevaade, mis selgitab, mida konkreetne ennustusmäng prognoosib ja kuidas hetketõenäosust tõlgendada.

**2. Update (uuendus)** — uudisteartikkel, mis kirjeldab olulist tõenäosuse muutust. Näiteks: OKC Thunder'i NBA play-off tõenäosus tõusis 35%-lt 52%-le pärast 119–84 võitu Phoenixi üle.

---

# Hindamissüsteem: `prompt-evaluation/`

Hindamissüsteem on eraldi moodul, mis ei sõltu rakenduse backendist. Selle eesmärk on mõõta ja võrrelda erinevate LLM-mudelite poolt genereeritud artiklite kvaliteeti automaatselt — ilma inimhindajateta.

## Failistruktuur

```
prompt-evaluation/
├── config.py         — WRITER_MODELS, JUDGE_MODEL, EvalConfig
├── web_writer.py     — WebSearchWriter: genereerib artikleid veebi otsinguga
├── evaluator.py      — ArticleEvaluator: hindab artikleid LLM-as-a-judge meetodiga
├── web_evaluate.py   — Peamine jooksutaja: paralleelne genereerimine + hindamine
├── sample_data.py    — 5 selgituse + 5 uuenduse testsisend (aprill 2026 reaalturud)
├── grounded_eval.py  — Põhjendatud hindamispass: allikadokumendid → täpsem skoor
└── results/          — JSON, CSV ja Markdown väljundid
```

## Andmevoog

```
Põhipass:
  sample_data
    → 3 × WebSearchWriter paralleelselt
        (igaüks otsib veebi ja kirjutab artikli koos allikaviitega)
      → artiklid + tsiteeritud URL-id
        → ArticleEvaluator (kasutab ka veebiotsingut)
          → JSON skoorid (5 kriteeriumi × 0–10 = kokku 0–50)
            → salvestatakse JSON/CSV/Markdown pärast iga näidet

Põhjendatud hindamispass (valikuline):
  web_eval_*.json
    → eelkureeritud referents-URL-id iga turu jaoks + artikli enda allikad
      → HTTP GET, HTML striipimine, kärpimine ~800 tokenini
        → DOC[1]..DOC[n] koos artikliga → deepseek hindab uuesti factual_consistency
          → grounded_eval_results.json (originaal vs põhjendatud skoor, delta)
```

---

## Konfiguratsioon (`config.py`)

Kirjutajad ja hindaja on täielikult sõltumatud — kummalegi saab määrata erineva mudeli:

```python
WRITER_MODELS = [
    "deepseek/deepseek-v3.2",
    "google/gemini-3-flash-preview",
    "minimax/minimax-m2.7",
]
JUDGE_MODEL = "deepseek/deepseek-v3.2"
```

Kolm kirjutajamudelit kirjutavad sama näite põhjal artikleid paralleelselt — see võimaldab otsest võrdlust samade sisendandmete korral. Hindaja on fikseeritud, et tagada hindamiste järjepidevus.

---

## Testsisendid (`sample_data.py`)

Süsteem kasutab 10 reaalset Polymarketi turgu aprillist 2026 — viit selgituse ja viit uuenduse näidet. Uuenduste tõenäosusmuutused on seotud konkreetsete ajalooliste sündmustega:

```python
SampleUpdate(
    # OKC võitis Phoenixi 119–84 (19. aprill 2026) → tõenäosus hüppas 35%-lt 52%-le
    market=SampleMarket(
        question="Will the Oklahoma City Thunder win the 2026 NBA Championship?",
        category="Sports",
        probability=0.52,
        volume=317_000_000,
    ),
    prev=SampleSnapshot(date=date(2026, 2, 19), probability=0.35),
    curr=SampleSnapshot(date=date(2026, 4, 19), probability=0.52),
),
```

Testsisendite realism on oluline: mudel, mis genereerib artikleid fiktiivsete sündmuste kohta, saab veebiotsingul madalama faktitäpsuse skoori kui see, kes leiab tegelikud uudisvood.

---

## Veebiandmetega põhjendatud artiklite genereerimine (`web_writer.py`)

### Kirjutaja süsteemiprompt

Iga kirjutaja saab järgmise süsteemiprompti:

```
You are a financial journalist. Today's date is April 2026.

Before writing any article you MUST use the web_search tool at least twice to
find recent news (March–April 2026) relevant to the topic. Search for specific
events, announcements, or data that explain the current situation.

Rules:
- Every factual claim must be grounded in search results.
- Cite sources inline with numbered references: [1], [2], etc.
- End with a SOURCES section listing the full URLs.
- Body must be under 80 words (not counting the SOURCES section).
- If your searches return no relevant results, state this explicitly
  rather than speculating.
```

### Tööriistaloop (`_call` meetod)

OpenRouter pakub serveripoolset veebiotsingutööriista `openrouter:web_search`. Mudel käivitab otsingu, OpenRouter täidab tulemuse ja mudel saab jätkata — arendaja poolelt piisab tühja vastuse tagastamisest:

```python
_WEB_SEARCH_TOOL = {"type": "openrouter:web_search"}

async def _call(self, messages: list[dict]) -> str:
    for _ in range(8):  # maksimaalselt 8 ringi
        resp = await self._client.chat.completions.create(
            model=self._model,
            max_tokens=2048,
            messages=messages,
            tools=[_WEB_SEARCH_TOOL],
            tool_choice="auto",
        )
        msg = resp.choices[0].message
        # lisa assistendi vastus sõnumite ahelasse
        messages.append({"role": "assistant", "content": msg.content or "",
                         "tool_calls": [...]})

        if not msg.tool_calls:
            return msg.content or ""  # mudel on lõpetanud

        # tagasta tühi platseerija — OpenRouter lahendab veebiotsingu serveripoolselt
        for tc in msg.tool_calls:
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": ""})
```

Tsükkel kordub, kuni mudel ei kutsu enam tööriista. Tavaliselt teeb kirjutaja 1–3 otsingut enne lõplikku artikli kirjutamist. Artikkel parsitakse sektsioonidesse `TITLE / BODY / SOURCES` — `_normalise()` funktsioon eemaldab eelnevalt DeepSeeki poolt toodetud Markdowni rasvased markerid (`**TITLE:**` → `TITLE:`), et parsimine toimiks ühtmoodi kõigi mudelite puhul.

---

## LLM-as-a-judge metoodika (`evaluator.py`)

### Mis see on?

LLM-as-a-judge on lähenemine, kus üht suurkeelemudelit kasutatakse teise mudeli väljundi hindamiseks. Selle asemel et palgata inimhindajaid või kirjutada kitsaid reeglipõhiseid kontrollimehhanisme, palutakse hindajamudelil anda struktureeritud skoor koos põhjendusega.

### Hindaja süsteemiprompt (kriteeriumide osa)

```
CRITERIA
--------
1. grammar (0–10)
   - Zero tolerance for grammatical errors, misspellings, or incorrect punctuation.

2. factual_consistency (0–10)
   - Use web_search to verify key factual claims in the article.
   - Penalise invented or hallucinated facts that search results contradict.
   - The article must also not contradict figures given in the prompt
     (probabilities, dates, direction of movement).

3. clarity (0–10)
   - A general-audience reader should understand without prior knowledge
     of prediction markets.

4. relevance (0–10)
   - EXPLANATION: must cover (a) what the market predicts, (b) what drives
     the probability, and (c) how to interpret the figure.
   - UPDATE: must cover (a) what happened, (b) plausible reasons, (c) outlook.

5. format (0–10)
   - Title present and concise. Body ≤ ~80 words. Correct TITLE/BODY structure.
```

Hindaja saab kolm sisendit: originaalprompti (sisaldab numbrilisi fakte), genereeritud artikli ja turukonteksti. See "ground truth" osa on oluline — ilma selleta ei suudaks hindaja kontrollida, kas artiklis esitatud tõenäosused ja kuupäevad vastavad tegelikkusele.

### Hindamise JSON väljund

```json
{
  "scores": {
    "grammar": 8,
    "factual_consistency": 7,
    "clarity": 9,
    "relevance": 8,
    "format": 9
  },
  "total": 41,
  "rationale": {
    "factual_consistency": "Article correctly states the 52% probability and
      mentions the Game 1 blowout win, verified via web search."
  },
  "overall_verdict": "Well-grounded article with accurate facts and clear structure."
}
```

### Eelised ja piirangud

**Eelised:** skaleeruv (saab hinnata sadu artikleid automaatselt), järjepidev (sama hindaja kasutab alati sama kriteeriumi), odav võrreldes inimhindajatega, suudab hinnata semantilist kvaliteeti (mida reegelpõhised meetodid ei suuda).

**Piirangud:** hindaja mudeli kallutatavus (võib eelistada oma stiili), ei suuda kontrollida fakte, mida veebiotsing ei leia, vajab täpset süsteemiprompti — ebamäärasete juhiste korral on tulemused ebausaldusväärsed.

---

## Hindamiskriteeriumite valik

Viis kriteeriumi katavad artikli kvaliteedi eri tahud:

| Kriteerium | Mida mõõdab | Miks oluline |
|---|---|---|
| **grammar** | Grammatika, õigekiri, kirjavahemärgid | Avalikud artiklid peavad olema keeleliselt korrektsed |
| **factual_consistency** | Faktide vastavus veebiallika ja prompti andmetega | LLM-id võivad hallutsineerida valesid numbreid või sündmusi |
| **clarity** | Arusaadavus üldpublikule | Ennustusmängud on mittetuttavale lugejale keeruline teema |
| **relevance** | Kas kõik nõutud punktid on kaetud | Prompt nõuab spetsiifilisi elemente, nende puudumine on viga |
| **format** | Pealkiri + keha ≤80 sõna + SOURCES sektsioon | Rakendus eeldab kindlat vormingut parsimiseks |

Igaüks skalal 0–10, kokku maksimaalselt 50 punkti.

---

## Põhjendatud hindamispass (`grounded_eval.py`)

Põhipassis hindab hindaja faktitäpsust samuti veebiotsingu abil, kuid otsingutulemused võivad sõltuda päringutest ning mõned väited jäävad kontrollimata. Seetõttu on loodud eraldiseisev põhjendatud hindamispass, mis kasutab dedikeeritud otsingumudeli `openai/gpt-4o-search-preview`.

### Põhimõte

Põhipassi kirjutajamudelid genereerivad artikleid ja esmane hindaja (deepseek) annab neile skoorid. Põhjendatud hindamispass loeb salvestatud artiklid uuesti sisse ja laseb `gpt-4o-search-preview`-l iga artikli faktitäpsuse iseseisvalt üle kontrollida — täiesti eraldi otsinguprotsessina:

```python
JUDGE_MODEL = "openai/gpt-4o-search-preview"

async def judge_article(client: AsyncOpenAI, article: dict) -> dict:
    resp = await client.chat.completions.create(
        model=JUDGE_MODEL,
        max_tokens=1024,
        messages=[
            {"role": "system", "content": _JUDGE_SYSTEM_PROMPT},
            {"role": "user",   "content": _build_judge_prompt(article)},
        ],
    )
    return _parse_judge(resp.choices[0].message.content or "")
```

Mudel saab turukonteksti (tõenäosus, kuupäev, suund) kui "ground truth" ning artikli teksti — seejärel otsib ta ise veebi, et kontrollida konkreetseid faktilisi väiteid (mängu tulemused, majandusandmed, uudissündmused), ja tagastab JSON-i:

```json
{
  "factual_consistency_grounded": 9,
  "supported_claims": ["France maintains 17% probability", "Ekitike ruled out with injury"],
  "unsupported_claims": [],
  "reasoning": "All key claims verified via web search."
}
```

### Delta analüüs

Põhjendatud hindamispass salvestab nii originaal- kui ka põhjendatud skoori koos deltaga:

```json
{
  "writer_model": "google/gemini-3-flash-preview",
  "original_factual_consistency": 5,
  "grounded_factual_consistency": 9,
  "delta": 4
}
```

Delta positiivne väärtus tähendab, et esmane hindaja alahindas artiklit — kirjutajamudelil oli õigus, kuid esmane hindaja ei suutnud seda ilma kontekstirikka otsingu toeta kinnitada. Negatiivne delta tähendab vastupidist: väited, mis kõlasid usutavalt, on tegelikult veebiallikatega vastuolus.

Mõlema hindamispassi kombinatsioon annab täpsema pildi mudeli faktitäpsusest: põhipass hindab kiirelt ja odavalt kõiki kriteeriumeid, põhjendatud pass kontrollib ainult faktitäpsust, kuid teeb seda põhjalikumalt.

---

## Tulemuste salvestamine

Süsteem salvestab tulemused inkrementaalselt pärast iga näidet (mitte ainult lõpus), mis tähendab, et töö katkestamisel ei lähe eelnevad tulemused kaduma. Kolm väljundiformaati tekivad automaatselt:

- **JSON** (`web_eval_<timestamp>.json`) — täielik masinavormingus andmestik koos toorväljundite ja hindamisratsioonaalidega
- **CSV** (`web_eval_<timestamp>.csv`) — Excel-ühilduv tabel, üks rida artikli kohta
- **Markdown** (`web_eval_<timestamp>.md`) — kaks tabelit: artiklikaupa skoorid ja mudeli koondkokkuvõte

```
OVERALL MODEL RANKING  (judge: deepseek/deepseek-v3.2)
────────────────────────────────────────────────────────────────────────────
  MODEL                               AVG/50   Gra  Fac  Cla  Rel  Fmt
────────────────────────────────────────────────────────────────────────────
  #1 gemini-3-flash-preview             38.2     8    6    8    8    8
  #2 deepseek-v3.2                      35.7     8    4    8    7    8
  #3 minimax-m2.7                       31.4     7    3    7    7    7
```
