# Juhised lõputöö UI/UX peatüki kirjutamiseks

Sa oled akadeemiline kirjutamisassistent. Kirjuta alloleva konteksti põhjal **bakalaureusetöö peatükk eesti keeles**.

**Nõuded:**
- Keel: eesti keel, akadeemiline toon
- Maht: 1000–1500 sõna
- Tase: bakalaureusetöö — tehniline detail on teine plaan, fookus on kasutajakogemusel ja disainiotsustel
- Ära seleta koodi ega implementatsiooni detaile — räägi sellest, mida kasutaja näeb ja tunneb
- Peatüki nimi: **"Kasutajaliidese disain"** (või sobilik alternatiiv)
- Struktuur: sissejuhatus → üldine paigutus ja navigatsioon → turukaardi komponent → interaktsioon ja tagasiside → visuaalne disainisüsteem → kokkuvõte

---

# Kontekst: Polymarket News rakendus

## Mis on rakendus?

Polymarket News on veebirakendus, mis kuvab ennustusmängude andmeid Polymarket platvormilt ning võimaldab kasutajal genereerida nende kohta tehisintellekti abil kirjutatud uudisartikleid. Ennustusmäng on turg, kus inimesed panevad raha mängule selle peale, kas mingi sündmus toimub või mitte. Tõenäosus kajastab kollektiivset hinnangut.

Rakenduse kasutajaks on tavainimene, kes soovib ennustusmängude seisust kiiresti ülevaadet saada ilma, et peaks ise andmeid tõlgendama.

## Tehniline alus (vaid kontekstiks — ära kirjelda peatükis detailselt)

- Frontend: Next.js 15 (React, TypeScript)
- Stiilid: inline CSS koos CSS-muutujatega (disainimärgid)
- Andmed uuenevad automaatselt iga 30 minuti järel

---

# Kasutajaliidese kirjeldus

## Üldine lehekülg

Rakendus koosneb ühest põhilehest. Leht on üles ehitatud järgmiselt (ülalt alla):

1. **Kleepuv päiseriba** — jääb kerimise ajal ekraani ülaossa
2. **Kategooriavalik (tabid)** — filtreerimiseks
3. **Pealkirja plokk** — aktiivse kategooria nimi ja info uuendussageduse kohta
4. **Turukaarditide loend** — üks kaart iga turu kohta

Lehekülje maksimaalne laius on 860 pikslit, mis on keskel joondatud — see hoiab sisu loetavana ka laiadel ekraanidel.

---

## Päiseriba

Päiseriba on "frosted glass" efektiga — taust on poolläbipaistev ja udune, mis annab visuaalse sügavustunde ning eristab päist lehekülje sisust. Päises on:

- **Pealkiri** "Polymarket News" — suur, paks kiri
- **Alapealkiri** "AI-generated market analysis" — väiksem, hallikas

Päis on kleepuv (`position: sticky`), mis tähendab, et kasutajal on alati teada, millises rakenduses ta on, ka pikka loendit alla kerides.

---

## Kategooriavalik

Kategooriad on kuvatud pillide kujul ühes reas: **Geopolitics · Finance · Culture · Tech**

Navigatsiooniblokk ise on ka ümar pill-kujuline konteiner helehalli taustaga. Aktiivne kategooria eristub:
- valge taust (kaardi värv)
- paksem kiri (font-weight 600 vs 450)
- kerge vari alla

Klikk kategooriale laadib uue lehekülje selle kategooria andmetega (URL-i parameeter `?tag=finance` jne). Üleminek toimub ilma kogu lehe laadimiseta (Next.js client-side navigation).

---

## Turukaart

Turukaart on rakenduse põhikomponent. Iga ennustusmängu kohta kuvatakse üks kaart.

### Kaardi päis

Kaardi ülaosas on kaks elementi kõrvuti:

**Vasakul:**
- Küsimus (nt "Will Bitcoin reach $150,000 before the end of 2025?") — bold, 15px
- Maht dollarites — väike, hallikas (nt "Vol $9.8M")

**Paremal:**
- Tõenäosuse protsent — suur (22px), rasvane, värvikoodiga:
  - **Roheline** (≥60%) — sündmus on tõenäoline
  - **Oranž** (40–60%) — ebaselge
  - **Punane** (≤40%) — sündmus on ebatõenäoline
- Allpool väike tekst "probability"

Tõenäosuse värv on semantiline — kasutaja saab hetkega aru, kas turg on "jahtade" või "karude" poolel, ilma protsenti lugemata.

### Tõenäosusriba

Pealkirja all on õhuke horisontaalne riba (3px kõrge), mis näitab tõenäosust visuaalselt. Riba täitumus vastab protsendile ja on sama värviga kui numbriline näit.

### Kaardi hover-efekt

Hiire liigutamisel kaardile:
- Vari muutub tugevamaks
- Kaart nihkub 1 piksli üles

See annab kasutajale tagasiside, et kaart on klikitav/interaktiivne, ja loob visuaalse sügavustunde.

---

## Tegevusnupud

Iga kaardi all on kaks nuppu:

### "Explain" nupp (sinine)
Genereerib selgitusartikli — igapäevaülevaate, mis seletab, mida see turg prognoosib ja kuidas hetketõenäosust tõlgendada.

- Genereerimise ajal: nupp muutub hallikas, kuvatakse pöörlevat laadimisikoon ja tekst "Explaining…"
- Pärast genereerimist: nupp läheb halliks ja tekstiks muutub "Explained" — näitab, et see toiming on juba tehtud ja pole vaja uuesti vajutada
- Kui selgitus juba eksisteerib: nupp on algselt keelatud (disabled)

### "Generate updates" nupp (lilla)
Otsib ajaloolistest andmetest üles suured tõenäosusmuutused (üle 10 protsendipunkti) ja genereerib iga sellise liikumise kohta uudisteartikli.

- Genereerimise ajal: sama laadimiskäitumine nagu "Explain" nupul
- Pärast genereerimist: rohelise taustaga teade (nt "3 update articles generated")
- Kui suuri liikumisi ei leita: teade "No significant moves found (>10pp)"

Mõlemad nupud on pill-kujulised ja reageerivad hover-olukorrale kerge suurendusega (`scale(1.02)`).

---

## Tagasiside ja olekuhaldus

Rakendus annab kasutajale pidevalt teada, mis toimub:

| Olukord | Tagasiside |
|---|---|
| Genereerimine käib | Pöörlevad spinner + tekst muutub (nt "Explaining…") |
| Genereerimine õnnestus | Roheline teade kaardi sees |
| Viga | Punane teavitus kaardi sees |
| Selgitus juba olemas | Nupp on hall ja keelatud (nt "Explained") |
| Turud laadimata | Tühi olek teksti selgitusega |
| API viga | Punane teavitusblokk lehekülje ülaosas |

Tagasiside on alati kaardi tasandil — kui ühe kaardi genereerimine ebaõnnestub, ei mõjuta see teiste kaartide olekut.

---

## Artiklite kuvamine

### Selgitusartikkel

Kui selgitus on genereeritud, ilmub kaardi alla sinise vasakäärjoonega blokk:

- Väike silt "EXPLANATION" (suurtähed, sinine)
- Artikli pealkiri
- Artikli sisu
- Metainfo all: tõenäosus genereerimise hetkel + kasutatud mudeli nimi (nt "At 52.0% · qwen/qwen3-235b-a22b")

### Uuendusartiklid

Uuendused kuvatakse "Moves · N" pealkirjaga sektsioonis. Iga uuendus on eraldi kaart lehehallikas taustal:

- Vasakul: artikli pealkiri
- Paremal ülal: kuupäev
- Paremal all: muutuse suurus värvikoodiga — **roheline** tõusu korral (nt "+16.0pp"), **punane** languse korral (nt "−19.0pp")
- All: artikli tekst

Uuendused on järjestatud uuemast vanema suunas.

---

## Visuaalne disainisüsteem

Rakendus kasutab ühtset disainimärgisüsteemi (CSS-muutujad), mis tagab kogu liideses järjepideva väljanägemise.

### Värvid

| Tähendus | Kasutus |
|---|---|
| `--color-surface` (#f5f5f7) | Lehekülje taust — hele hallikas |
| `--color-card` (#ffffff) | Kaartide ja aktiivsete elementide taust |
| `--color-accent` (#0071e3) | Interaktiivsed elemendid, "Explain" nupp |
| `--color-text-primary` (#1d1d1f) | Pealkirjad, olulised andmed |
| `--color-text-secondary` (#6e6e73) | Artikli sisu, kirjeldused |
| `--color-text-tertiary` (#aeaeb2) | Metainfo, sildid |
| `--color-up` | Tõusvad tõenäosused (roheline) |
| `--color-down` | Langevad tõenäosused (punane) |

### Kujud ja varjud

- Nupud on pill-kujulised (`border-radius: 9999px`)
- Kaartidel on keskmise suurusega vari (`box-shadow`), mis suureneb hover-olukorras
- Ümarad nurgad kõikjal (8–16px), teravaid nurki ei esine

### Animatsioonid

- Üleminekud on kiired (150–300ms) ja kasutavad `cubic-bezier` kõverat, mis annab loomulikuma liikumise
- Laadimis-spinner pöörleb 0,7 sekundi tsükliga
- Tõenäosusriba laius animeerub aeglasemalt (`transition-slow: 400ms`)

---

## Disainipõhimõtted kokkuvõtlikult

1. **Visuaalne hierarhia** — kõige olulisem info (tõenäosus, küsimus) on suurim ja kontrastseim; metainfo on väiksem ja hallim
2. **Semantilised värvid** — punane/oranž/roheline tõenäosusel ja muutusel annavad tähendust ilma tekstita
3. **Tagasiside kõikjal** — kasutaja ei pea kunagi arvama, kas midagi toimub
4. **Progressiivne avalikustamine** — artiklid ilmuvad kaardi alla alles pärast genereerimist, mis hoiab algvaate puhtana
5. **Apple-inspireeritud minimalism** — valge, hall ja aktsendisinine; ümarad kujud; frosted glass päis
