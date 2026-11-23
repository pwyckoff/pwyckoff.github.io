# Gaps in the coast path, and how the build fills them

Researched November 2026. Status is from the OpenStreetMap wiki's stretch-by-stretch
table of the King Charles III England Coast Path (edited May 2026) and GOV.UK's
stretch pages. "Approved" stretches may still be missing from Natural England's
dataset, so the build treats every stretch below as a possible gap and fills in
order of authority: official data, then OpenStreetMap's England Coast Path routes,
then the existing trails listed here, then guesses.

Ranked by how much is likely missing and how little exists on the ground.

## 1. Not yet approved: certainly missing from the official data

| Stretch | Length | Status | Best source | Confidence |
|---|---:|---|---|---|
| Isle of Wight | 101 km | Proposals in development in one section, awaiting establishment in the rest | **Isle of Wight Coastal Path** (long-established, round the whole island) | High |
| Lulworth Cove to Highcliffe | 77 km | Proposals in development, part approved | **South West Coast Path** to South Haven Point; **Bournemouth Coast Path** Sandbanks to Milford on Sea. Natural England proposes the Poole Harbour chain ferry, so that crossing stays a short straight link | High |
| Highcliffe to Calshot (New Forest) | 57 km | Proposals published | **Solent Way**; it goes inland round the Beaulieu estate, so expect it to sit inland there | Medium |
| Portsmouth to South Hayling | 30 km | Proposals published | **Solent Way** (Portsmouth to Langstone) | High |
| Mersea Island | 20 km | Proposals published, not determined | No named trail; sea walls. Guessed along footpaths or traced along the shore | Medium |

## 2. Approved, being set up: often missing from the official data

| Stretch | Length | Best source | Confidence |
|---|---:|---|---|
| Salcott to Jaywick (the Colne: Mersea, Colchester, Wivenhoe, Brightlingsea, St Osyth) | 81 km | **Wivenhoe Trail** (Colchester to Wivenhoe); **Colchester Orbital** (Rowhedge, Fingringhoe, Wivenhoe); the rest guessed. Natural England's route follows the Colne up to Colchester and back | Medium |
| Jaywick to Harwich (Clacton, Frinton, Walton, Hamford Water) | 60 km | Seafront promenades and sea walls, guessed; no named trail round Hamford Water | Medium |
| Harwich to Shotley Gate (the Stour) | 39 km | **Essex Way** along the south shore (Natural England's proposal uses 4 km of it); **Stour and Orwell Walk** on the north shore | High |
| Shotley Gate to Felixstowe Ferry (the Orwell) | 44 km | **Stour and Orwell Walk** | High |
| Felixstowe Ferry to Bawdsey (the Deben) | 41 km | Partly **Suffolk Coast Path**; the rest guessed | Medium |
| Bawdsey to Aldeburgh | 62 km | **Suffolk Coast Path** (goes inland across heaths in places) | Medium |
| Aldeburgh to Hopton-on-Sea | 60 km | **Suffolk Coast Path** | High |
| Weybourne to Hunstanton | 60 km | **Norfolk Coast Path** | High |
| Wallasea Island to Burnham-on-Crouch | 58 km | **Roach Valley Way** (sea walls of the Roach and Crouch); the rest guessed | Medium |
| Mablethorpe to Humber Bridge | 81 km | **Already mapped in OpenStreetMap** (relation 19509918) | High |
| Humber Bridge to Easington | 65 km | **Already mapped in OpenStreetMap** (relation 19514585) | High |
| Easington to Filey Brigg | 95 km | OpenStreetMap relation 16312445 (partly mapped); **Headland Way** at Flamborough; the rest guessed | Medium |
| Silecroft to Silverdale (Duddon, Furness, Leven, Kent) | 112 km | **Cistercian Way** across Furness; the rest guessed. The old Cumbria Coastal Way is no longer in OpenStreetMap | Low to medium |
| Silverdale to Cleveleys (Morecambe Bay, Lune, Wyre) | 88 km | **Lancashire Coastal Way** | High |
| Cleveleys to Tarleton (the Ribble) | ~58 km | **Lancashire Coastal Way** | High |
| Gretna to Allonby (middle part) | ~47 km | **Hadrian's Wall Path** (Carlisle to Bowness); **Hadrian's Cycleway** (Bowness to Allonby); **Allerdale Ramble** at Grune Point | Medium |
| South Hayling to East Head (Chichester Harbour) | 78 km | **Solent Way** to Langstone; **Sussex Border Path** on Thorney Island; the rest guessed | Medium |
| Eastbourne to Camber | 53 km (part) | **Saxon Shore Way** from Hastings to Rye; the rest guessed | Medium |
| Isle of Sheppey | 51 km (part) | Guessed | Low to medium |
| Liverpool to the Welsh border (Wirral) | ~17 km | **Wirral Way** and Wirral coastal paths | Medium |
| Aust to Brean Down | ~23 km | **Severn Way** (Aust to Avonmouth); the rest guessed | Medium |
| Iwade to Grain (Medway) | ~18 km | **Saxon Shore Way** | High |
| Minehead to Lyme Regis (the South West peninsula) | ~900 km | **South West Coast Path**, if any of it is absent from the official data | High |

## 3. Small breaks

- **River Irt and Esk at Ravenglass** (Whitehaven to Silecroft): bridge works pending. Guessed.
- **Friskney Eaudyke to Gibraltar Point** (Sutton Bridge to Skegness): awaits a bridge over the River Steeping. Guessed.

## Adjusting this

The trails are listed in `TRAILS` in `build_coast_path.py`, each with the pattern
used to find it in OpenStreetMap and a box (south, west, north, east) around the
stretch it fills. If the build report says a trail was "not found in
OpenStreetMap", its name there probably differs: look it up on
openstreetmap.org and adjust the pattern. To add a trail, add a line in the same
form; order matters, since earlier entries take precedence where trails overlap.
