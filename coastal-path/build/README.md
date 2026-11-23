# Building the full coast path

`build_coast_path.py` assembles the whole estimated coast path of England and Wales
and writes `coastal-path/coast-path-full.geojson`, which the log page loads. It is
built once (and again whenever you choose, or monthly), so visitors never wait for
anything to be fetched or guessed.

## How it fills the path

In order of authority, each source only adding ground the earlier ones don't cover:

1. Natural England's approved England Coast Path, and Defra's copy of it
2. The Wales Coast Path, from OpenStreetMap
3. OpenStreetMap's England Coast Path routes, including stretches mapped before opening
4. Existing trails for stretches not yet approved (see `GAP_RESEARCH.md`)
5. Guesses for what's left: footpaths near the shore (walking routes preferred),
   short straight links for crossings, otherwise the shoreline itself

Every piece in the output says where it came from: `source` is `official`, `other`
(mapped path that isn't the official line) or `guess`, and `via` names the dataset,
trail or guessing method.

## Running it on GitHub (recommended)

The workflow in `.github/workflows/build-coast-path.yml` runs on the 3rd of each
month, or when you open the repository's **Actions** tab, choose **Build coast
path** and press **Run workflow**. It commits the new file and `report.md` only if
something changed. The first run takes longest (an hour or two, mostly polite
pauses between requests); later runs reuse cached data.

## Running it yourself

```
cd coastal-path/build
pip install -r requirements.txt
python build_coast_path.py
```

Options: `--refresh` ignores the cache; `--mock tests/essex` runs on sample data with
no network (handy for checking a change).

## Checking the result

Read `report.md`. It lists miles from each source, every guessed gap with its
method, and the places where the path still stops (Berwick and Gretna are its true
ends). The "England ... of about 2,689 miles" line is the quick completeness check.
