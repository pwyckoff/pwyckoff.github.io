#!/usr/bin/env python3
"""
Build the full estimated coast path of England and Wales, once.

The result, coast-path-full.geojson, is what the coast path log loads, so no
visitor waits for anything to be fetched or guessed. Run it by hand, or let the
GitHub workflow run it monthly so formal updates are picked up.

Sources, in order of authority. Each one only adds ground the earlier ones
don't already cover:

  1. Natural England's King Charles III England Coast Path (approved stretches),
     and Defra's copy of the same dataset, which can carry newer approvals.
  2. The Wales Coast Path, as mapped in OpenStreetMap.
  3. OpenStreetMap's England Coast Path routes, including stretches mapped ahead
     of opening (Mablethorpe to Humber Bridge, Humber Bridge to Easington, ...).
  4. Existing trails along stretches not yet approved, each clipped to the stretch
     it fills (the Essex Way by the Stour, the Solent Way by the New Forest, ...).
     The list comes from research into each gap; see GAP_RESEARCH.md.
  5. Guesses for whatever is still missing: walkable ways near the shore,
     preferring walking routes; a straight link for short crossings; otherwise
     a trace of the shoreline.

Usage:
  python build_coast_path.py --out ../coast-path-full.geojson --report report.md
  python build_coast_path.py --mock tests/essex   # sample data, no network

Everything fetched is cached in .cache/ (for 25 days by default), so a rerun is
quick and kind to the free services it uses.
"""
import argparse
import hashlib
import heapq
import json
import math
import os
import sys
import time
from datetime import datetime, timezone

import requests
from pyproj import Transformer
from shapely.geometry import LineString, MultiLineString, Point
from shapely.ops import transform, unary_union
from shapely.strtree import STRtree

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

NATURAL_ENGLAND = 'https://services.arcgis.com/JJzESW51TqeY9uat/ArcGIS/rest/services/England_Coast_Path_Route/FeatureServer/0/query'
DEFRA_COPY = 'https://environment.data.gov.uk/arcgis/rest/services/NE/EnglandCoastPathRoute/FeatureServer/0/query'
OVERPASS = ['https://overpass-api.de/api/interpreter', 'https://overpass.kumi.systems/api/interpreter']
WALES_RELATION = 1820890
ENGLAND_OSM_RELATION = 3971851
# Stretches mapped in OpenStreetMap ahead of opening, from the OSM wiki's status table
ENGLAND_OSM_EXTRA = [19509918, 19514585, 16312445, 17052594, 17243288, 17243557, 17245344,
                     18268797, 17248088, 18269765, 18269898, 18271937, 18297638, 17284514, 18038767]
ENGLAND_BOX = (49.85, -6.5, 55.85, 1.85)           # south, west, north, east
EXPECTED_MI = {'E': 2689, 'W': 870}

# Existing trails for stretches not yet approved, in order of preference. Each is
# clipped to a box (south, west, north, east) around just the stretch it fills.
# `match` is a case-insensitive pattern for route or path names in OpenStreetMap.
TRAILS = [
    # The long-standing National Trails and coast paths the England Coast Path absorbs
    ('South West Coast Path', 'South West Coast Path', (49.95, -5.75, 51.25, -1.94), 'Minehead to South Haven Point'),
    ('Norfolk Coast Path', 'Norfolk Coast Path', (52.90, 0.47, 53.00, 1.16), 'Hunstanton to Weybourne'),
    ('Suffolk Coast Path', 'Suffolk Coast', (51.96, 1.30, 52.53, 1.80), 'Felixstowe to Hopton-on-Sea'),
    ('Isle of Wight Coastal Path', 'Isle of Wight Coastal Path', (50.57, -1.60, 50.78, -1.06), 'the Isle of Wight'),
    ('Lancashire Coastal Way', 'Lancashire Coastal Way', (53.62, -3.10, 54.21, -2.74), 'Silverdale to Tarleton'),
    # Regional trails along specific gaps
    ('Essex Way', 'Essex Way', (51.92, 1.03, 51.965, 1.295), 'Manningtree to Harwich (Stour)'),
    ('Stour and Orwell Walk', 'Stour and Orwell', (51.93, 1.03, 52.06, 1.40), 'Cattawade to Felixstowe'),
    ('Wivenhoe Trail', 'Wivenhoe Trail', (51.85, 0.90, 51.89, 0.98), 'Colchester to Wivenhoe (Colne)'),
    ('Colchester Orbital', 'Colchester Orbital', (51.82, 0.88, 51.90, 1.02), 'Rowhedge, Fingringhoe and Wivenhoe (Colne)'),
    ('Roach Valley Way', 'Roach Valley Way', (51.56, 0.68, 51.66, 0.86), 'Roach and Crouch sea walls'),
    ('Bournemouth Coast Path', 'Bournemouth Coast Path', (50.66, -1.98, 50.76, -1.55), 'Sandbanks to Milford on Sea'),
    ('Solent Way', 'Solent Way', (50.70, -1.72, 50.86, -0.93), 'Milford on Sea to Langstone'),
    ('Sussex Border Path', 'Sussex Border Path', (50.78, -0.95, 50.86, -0.85), 'Thorney Island (Chichester Harbour)'),
    ('Saxon Shore Way', 'Saxon Shore Way', (50.84, 0.55, 51.48, 0.95), 'Sheppey, Medway, Rye and Hastings'),
    ('Wirral Way', 'Wirral', (53.28, -3.22, 53.45, -2.95), 'Wirral coast'),
    ('Hadrian\u2019s Wall Path', 'Hadrian.s Wall Path', (54.88, -3.25, 54.96, -2.92), 'Bowness-on-Solway to Carlisle'),
    ('Hadrian\u2019s Cycleway', 'Hadrian.s Cycleway', (54.76, -3.45, 54.96, -3.22), 'Allonby to Bowness-on-Solway'),
    ('Allerdale Ramble', 'Allerdale Ramble', (54.85, -3.40, 54.92, -3.22), 'Grune Point, by Silloth'),
    ('Cistercian Way', 'Cistercian Way', (54.05, -3.25, 54.25, -2.90), 'Furness peninsula'),
    ('Headland Way', 'Headland Way', (54.05, -0.30, 54.23, -0.05), 'Flamborough Head to Filey'),
    ('Severn Way', 'Severn Way', (51.45, -2.75, 51.62, -2.55), 'Aust to Avonmouth'),
]

BUFFER_M = 150        # a line within this of an accepted one counts as already covered
MIN_PIECE_M = 300     # shorter new pieces are dropped
JOIN_M = 300          # new pieces are extended to touch accepted ones within this
LOOSE_M = 40          # line ends further than this from any other line are loose
SUBSTANTIAL_M = 1500  # pieces of path smaller than this aren't gap ends
MAX_GAP_M = 120000

# Coastal towns in order round the coast, Berwick to Gretna, for ordering pieces
COAST_ORDER = [
    ('Berwick', 55.77, -2.00), ('Bamburgh', 55.61, -1.71), ('Amble', 55.33, -1.58), ('Tynemouth', 55.02, -1.42),
    ('Sunderland', 54.91, -1.37), ('Hartlepool', 54.69, -1.18), ('Redcar', 54.62, -1.06), ('Whitby', 54.49, -0.61),
    ('Scarborough', 54.28, -0.40), ('Flamborough', 54.12, -0.08), ('Bridlington', 54.08, -0.19), ('Hornsea', 53.91, -0.17),
    ('Spurn Head', 53.58, 0.11), ('Hull', 53.74, -0.33), ('Humber Bridge', 53.71, -0.45), ('Grimsby', 53.57, -0.08),
    ('Mablethorpe', 53.34, 0.26), ('Skegness', 53.14, 0.34), ('Boston', 52.98, -0.02), ('Sutton Bridge', 52.77, 0.19),
    ('King\u2019s Lynn', 52.75, 0.40), ('Hunstanton', 52.94, 0.49), ('Wells', 52.96, 0.85), ('Cromer', 52.93, 1.30),
    ('Great Yarmouth', 52.61, 1.73), ('Lowestoft', 52.48, 1.75), ('Southwold', 52.33, 1.68), ('Aldeburgh', 52.15, 1.60),
    ('Felixstowe', 51.96, 1.35), ('Shotley Gate', 51.95, 1.27), ('Manningtree', 51.94, 1.07), ('Harwich', 51.94, 1.28),
    ('Clacton', 51.79, 1.15), ('Mersea', 51.78, 0.92), ('Maldon', 51.73, 0.68), ('Burnham-on-Crouch', 51.63, 0.81),
    ('Southend', 51.54, 0.71), ('Tilbury', 51.46, 0.36), ('Woolwich', 51.49, 0.07), ('Gravesend', 51.44, 0.37),
    ('Sheppey', 51.40, 0.85), ('Whitstable', 51.36, 1.03), ('Margate', 51.39, 1.38), ('Ramsgate', 51.33, 1.42),
    ('Dover', 51.12, 1.31), ('Folkestone', 51.08, 1.17), ('Dungeness', 50.91, 0.98), ('Hastings', 50.85, 0.58),
    ('Eastbourne', 50.77, 0.29), ('Brighton', 50.82, -0.14), ('Worthing', 50.81, -0.37), ('Selsey', 50.73, -0.79),
    ('Portsmouth', 50.80, -1.09), ('Southampton', 50.90, -1.40), ('Lymington', 50.75, -1.55), ('Bournemouth', 50.72, -1.88),
    ('Swanage', 50.61, -1.96), ('Weymouth', 50.61, -2.45), ('Lyme Regis', 50.72, -2.94), ('Exmouth', 50.62, -3.41),
    ('Torquay', 50.46, -3.53), ('Start Point', 50.22, -3.64), ('Plymouth', 50.37, -4.14), ('Fowey', 50.33, -4.64),
    ('Falmouth', 50.15, -5.07), ('The Lizard', 49.96, -5.20), ('Penzance', 50.12, -5.54), ('Land\u2019s End', 50.07, -5.71),
    ('St Ives', 50.21, -5.48), ('Newquay', 50.41, -5.08), ('Padstow', 50.54, -4.94), ('Bude', 50.83, -4.55),
    ('Hartland', 51.02, -4.53), ('Bideford', 51.02, -4.21), ('Ilfracombe', 51.21, -4.12), ('Minehead', 51.21, -3.47),
    ('Weston-super-Mare', 51.35, -2.98), ('Portishead', 51.48, -2.77), ('Aust', 51.60, -2.63), ('Chepstow', 51.64, -2.67),
    ('Newport', 51.58, -2.99), ('Cardiff', 51.46, -3.17), ('Barry', 51.39, -3.27), ('Porthcawl', 51.48, -3.70),
    ('Swansea', 51.62, -3.94), ('Gower', 51.57, -4.29), ('Llanelli', 51.68, -4.16), ('Carmarthen', 51.86, -4.31),
    ('Tenby', 51.67, -4.70), ('Milford Haven', 51.71, -5.03), ('St Davids', 51.88, -5.27), ('Fishguard', 52.00, -4.98),
    ('Cardigan', 52.08, -4.66), ('Aberystwyth', 52.41, -4.08), ('Aberdyfi', 52.54, -4.05), ('Barmouth', 52.72, -4.05),
    ('Porthmadog', 52.93, -4.13), ('Pwllheli', 52.89, -4.42), ('Aberdaron', 52.80, -4.71), ('Caernarfon', 53.14, -4.27),
    ('Holyhead', 53.31, -4.63), ('Amlwch', 53.41, -4.34), ('Beaumaris', 53.26, -4.09), ('Bangor', 53.23, -4.13),
    ('Conwy', 53.28, -3.83), ('Rhyl', 53.32, -3.49), ('Flint', 53.25, -3.13), ('Chester', 53.19, -2.89),
    ('Birkenhead', 53.39, -3.01), ('Southport', 53.65, -3.01), ('Lytham', 53.74, -2.96), ('Blackpool', 53.82, -3.05),
    ('Fleetwood', 53.92, -3.01), ('Morecambe', 54.07, -2.86), ('Arnside', 54.20, -2.83), ('Barrow', 54.11, -3.23),
    ('Millom', 54.21, -3.27), ('Ravenglass', 54.35, -3.41), ('Whitehaven', 54.55, -3.59), ('Maryport', 54.71, -3.50),
    ('Silloth', 54.87, -3.39), ('Gretna', 54.99, -3.07),
]

ROAD_FACTOR = {'footway': 1, 'path': 1, 'bridleway': 1, 'pedestrian': 1, 'steps': 1, 'cycleway': 1, 'track': 1,
               'service': 1.3, 'living_street': 1.3, 'residential': 1.5, 'unclassified': 1.5, 'tertiary': 2.2,
               'secondary': 3.5, 'primary': 6}

HERE = os.path.dirname(os.path.abspath(__file__))
TO_BNG = Transformer.from_crs(4326, 27700, always_xy=True).transform
TO_WGS = Transformer.from_crs(27700, 4326, always_xy=True).transform


def log(*a):
    print(*a, flush=True)


# --------------------------------------------------------------------------
# Fetching, with a cache and polite pacing
# --------------------------------------------------------------------------

class Fetcher:
    def __init__(self, cache_dir, ttl_days=25, refresh=False, mock_dir=None):
        self.cache_dir, self.ttl, self.refresh, self.mock = cache_dir, ttl_days * 86400, refresh, mock_dir
        self.last = 0
        os.makedirs(cache_dir, exist_ok=True)

    def _cached(self, key):
        path = os.path.join(self.cache_dir, hashlib.sha1(key.encode()).hexdigest() + '.json')
        if not self.refresh and os.path.exists(path) and time.time() - os.path.getmtime(path) < self.ttl:
            with open(path) as f:
                return path, json.load(f)
        return path, None

    def get(self, key, fn):
        """key names the request; fn makes it. Mock mode reads <mock>/<slug>.json instead."""
        if self.mock:
            return self._mock(key)
        path, data = self._cached(key)
        if data is not None:
            return data
        data = fn()
        with open(path, 'w') as f:
            json.dump(data, f)
        return data

    def _mock(self, key):
        """Answer from <mock>/world.json by kind of request, for testing without the network."""
        if not hasattr(self, '_world'):
            with open(os.path.join(self.mock, 'world.json')) as f:
                self._world = json.load(f)
        w = self._world
        self.mock_calls = getattr(self, 'mock_calls', 0) + 1
        if key == 'arcgis:natural-england':
            return {'features': w.get('natural_england', [])}
        if key == 'arcgis:defra-copy':
            return {'features': w.get('defra', [])}
        if key == 'overpass:wales':
            return {'elements': w.get('wales', [])}
        if key == 'overpass:england-osm':
            return {'elements': w.get('england_osm', [])}
        if key.startswith('overpass:trail:'):
            return {'elements': w.get('trails', {}).get(key.split(':', 2)[2], [])}
        if key.startswith('overpass:coast'):
            return {'elements': w.get('coastline', [])}
        if key.startswith('overpass:paths'):
            ids = [{'type': 'way', 'id': i} for i in w.get('on_walking_routes', [])]
            return {'elements': w.get('ways', []) + ids}
        return {'elements': [], 'features': []}

    def pause(self, gap=2.5):
        wait = self.last + gap - time.time()
        if wait > 0:
            time.sleep(wait)
        self.last = time.time()

    def overpass(self, key, query, timeout=180):
        def go():
            last_err = None
            for attempt in range(3):
                for ep in OVERPASS:
                    self.pause()
                    try:
                        r = requests.post(ep, data={'data': query}, timeout=timeout + 30,
                                          headers={'User-Agent': 'coast-path-log build (pwyckoff.github.io)'})
                        if r.status_code == 200:
                            return r.json()
                        last_err = f'{ep} answered {r.status_code}'
                    except Exception as e:      # noqa: BLE001
                        last_err = f'{ep}: {e}'
                time.sleep(20 * (attempt + 1))  # back off before trying the servers again
            raise RuntimeError(last_err)
        return self.get('overpass:' + key, go)

    def arcgis(self, key, url):
        def go():
            feats, offset = [], 0
            while True:
                self.pause(1)
                r = requests.get(url, timeout=120, params={
                    'where': '1=1', 'outFields': '*', 'returnGeometry': 'true', 'outSR': '4326',
                    'maxAllowableOffset': '0.00002', 'geometryPrecision': '6',
                    'resultOffset': offset, 'resultRecordCount': 1000, 'f': 'json'})
                r.raise_for_status()
                d = r.json()
                if 'error' in d:
                    raise RuntimeError(d['error'].get('message', 'ArcGIS error'))
                feats += d.get('features', [])
                offset += len(d.get('features', []))
                if not d.get('exceededTransferLimit') or not d.get('features'):
                    break
            return {'features': feats}
        return self.get('arcgis:' + key, go)


# --------------------------------------------------------------------------
# Geometry helpers
# --------------------------------------------------------------------------

def bng(coords_latlon):
    """[(lat, lon), ...] -> LineString in British National Grid metres."""
    return LineString([TO_BNG(lon, lat) for lat, lon in coords_latlon])


def lines_of(geom):
    if geom is None or geom.is_empty:
        return []
    if geom.geom_type == 'LineString':
        return [geom]
    if hasattr(geom, 'geoms'):
        return [g for part in geom.geoms for g in lines_of(part)]
    return []


def osm_lines(data):
    """Ways with geometry from an Overpass response, split where clipping left gaps."""
    out = []
    for e in data.get('elements', []):
        if e.get('type') != 'way' or not isinstance(e.get('geometry'), list):
            continue
        run = []
        for g in e['geometry']:
            if g and isinstance(g.get('lat'), (int, float)):
                run.append((g['lat'], g['lon']))
            else:
                if len(run) > 1:
                    out.append(bng(run))
                run = []
        if len(run) > 1:
            out.append(bng(run))
    return out


def arcgis_lines(data):
    lines, names = [], []
    for f in data.get('features', []):
        a = f.get('attributes') or {}
        key = next((k for k in a if 'stretch' in k.lower() and isinstance(a[k], str)), None)
        name = a[key].strip() if key and a[key] else None
        for p in (f.get('geometry') or {}).get('paths', []):
            if len(p) > 1:
                lines.append(LineString([TO_BNG(x, y) for x, y in p]))
                names.append(name)
    return lines, names


def ref_t(lat, lon):
    """Position along the coast (Berwick to Gretna) of the point nearest (lat, lon)."""
    best, bt, cum = 1e18, 0.0, 0.0
    kx = math.cos(math.radians(lat))
    for i in range(1, len(COAST_ORDER)):
        _, a0, a1 = COAST_ORDER[i - 1]
        _, b0, b1 = COAST_ORDER[i]
        ax, ay = (a1 - lon) * kx, a0 - lat
        dx, dy = (b1 - a1) * kx, b0 - a0
        l2 = dx * dx + dy * dy
        t = max(0.0, min(1.0, -(ax * dx + ay * dy) / l2)) if l2 else 0.0
        px, py = ax + t * dx, ay + t * dy
        seg = math.hypot(dx, dy)
        if px * px + py * py < best:
            best, bt = px * px + py * py, cum + t * seg
        cum += seg
    return bt


def wgs(pt_xy):
    lon, lat = TO_WGS(pt_xy[0], pt_xy[1])
    return lat, lon


def where(xy):
    """'Mersea (51.860, 0.960)': a name to recognise and coordinates to find it by."""
    lat, lon = wgs(xy)
    return f'{place_name(xy)} ({lat:.3f}, {lon:.3f})'


def place_name(xy):
    lat, lon = wgs(xy)
    best, name = 15000, None
    for n, la, lo in COAST_ORDER:
        d = math.dist(TO_BNG(lo, la), xy)
        if d < best:
            best, name = d, n
    return name or f'{lat:.3f}, {lon:.3f}'


# --------------------------------------------------------------------------
# The path, assembled piece by piece
# --------------------------------------------------------------------------

class Path:
    def __init__(self):
        self.pieces = []          # dicts: geom (BNG LineString), source, via, stretch, country
        self.buffers = []         # one buffer per piece, for "is this ground already covered?"

    def add_all(self, lines, source, via, country='E', stretches=None, clip=True):
        """Add lines, keeping only ground not already covered. Returns miles added."""
        added = []
        tree = STRtree([p['geom'] for p in self.pieces]) if self.pieces else None
        btree = STRtree(self.buffers) if self.buffers else None
        for i, line in enumerate(lines):
            if line.length < 1:
                continue
            if clip and btree is not None:
                # Only the covered ground near this line matters
                near = [self.buffers[k] for k in btree.query(line)]
                parts = lines_of(line.difference(unary_union(near))) if near else [line]
                parts = [p for p in parts if p.length >= MIN_PIECE_M]
            else:
                parts = [line]
            for part in parts:
                part = self._join(part, tree)
                added.append({'geom': part, 'source': source, 'via': via, 'country': country,
                              'stretch': stretches[i] if stretches else None})
        self.pieces += added
        self.buffers += [a['geom'].buffer(BUFFER_M, resolution=2) for a in added]
        return sum(a['geom'].length for a in added) / 1609.344

    def _join(self, part, tree):
        """Extend a new piece's ends to touch the nearest accepted line within JOIN_M."""
        if tree is None:
            return part
        coords = list(part.coords)
        for end in (0, -1):
            p = Point(coords[end])
            near = tree.query(p.buffer(JOIN_M))
            best, bq = JOIN_M, None
            for idx in near:
                g = self.pieces[idx]['geom']
                d = g.distance(p)
                if 1 < d < best:
                    best, bq = d, g.interpolate(g.project(p))
            if bq is not None:
                if end == 0:
                    coords.insert(0, (bq.x, bq.y))
                else:
                    coords.append((bq.x, bq.y))
        return LineString(coords)

    def miles(self, source=None, country=None):
        return sum(p['geom'].length for p in self.pieces
                   if (source is None or p['source'] == source) and (country is None or p['country'] == country)) / 1609.344


# --------------------------------------------------------------------------
# Gaps: loose ends on separate pieces that sit near each other along the coast
# --------------------------------------------------------------------------

def find_gaps(path):
    geoms = [p['geom'] for p in path.pieces]
    tree = STRtree(geoms)
    parent = list(range(len(geoms)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    loose = []
    for j, g in enumerate(geoms):
        for end, xy in ((0, g.coords[0]), (1, g.coords[-1])):
            p = Point(xy)
            hit = False
            for k in tree.query(p.buffer(LOOSE_M)):
                if k != j and geoms[k].distance(p) <= LOOSE_M:
                    hit = True
                    a, b = find(j), find(int(k))
                    if a != b:
                        parent[a] = b
            if not hit:
                loose.append((j, end, xy))
    comp_len = {}
    for j, g in enumerate(geoms):
        comp_len[find(j)] = comp_len.get(find(j), 0) + g.length
    # Every piece's place along the coast; an end's rank is its piece's, so "how far
    # apart along the coast" counts pieces of path, not just the loose ends
    t_of = []
    for g in geoms:
        mid = g.interpolate(0.5, normalized=True)
        t_of.append(ref_t(*wgs((mid.x, mid.y))))
    rank_of = {j: r for r, j in enumerate(sorted(range(len(geoms)), key=lambda j: t_of[j]))}
    ends = []
    for j, end, xy in loose:
        if comp_len[find(j)] < SUBSTANTIAL_M:
            continue
        ends.append({'id': f'{j}:{end}', 'xy': xy, 'comp': find(j), 't': t_of[j], 'rank': rank_of[j],
                     'country': path.pieces[j]['country']})
    ends.sort(key=lambda e: e['rank'])
    cands = []
    for x in range(len(ends)):
        for y in range(x + 1, len(ends)):
            A, B = ends[x], ends[y]
            if B['rank'] - A['rank'] > 60:
                break
            if A['comp'] == B['comp']:
                continue
            d = math.dist(A['xy'], B['xy'])
            if d > MAX_GAP_M:
                continue
            cands.append({'a': A, 'b': B, 'd': d, 'apart': B['rank'] - A['rank'],
                          'pair': tuple(sorted((A['comp'], B['comp'])))})
    return cands, ends


# --------------------------------------------------------------------------
# Filling a gap: footpaths near the shore, a short crossing, or the shoreline
# --------------------------------------------------------------------------

def box_around(a, b, pad_frac=0.35, min_pad=3000):
    pad = max(min_pad, math.dist(a, b) * pad_frac)
    xs, ys = (a[0], b[0]), (a[1], b[1])
    sw = wgs((min(xs) - pad, min(ys) - pad))
    ne = wgs((max(xs) + pad, max(ys) + pad))
    return (round(sw[0], 4), round(sw[1], 4), round(ne[0], 4), round(ne[1], 4))


def coastline(fetch, box):
    bb = '({},{},{},{})'.format(*box)
    d = fetch.overpass('coast' + bb, f'[out:json][timeout:120];way["natural"="coastline"]{bb};out body geom{bb};')
    return d


def route_footpaths(fetch, a, b, corridor):
    box = box_around(a, b)
    bb = '({},{},{},{})'.format(*box)
    cdata = coastline(fetch, box)
    coast = osm_lines(cdata)
    hw = '|'.join(ROAD_FACTOR)
    # Walkable ways within the corridor of the coastline, and which of them are on walking routes
    q = (f'[out:json][timeout:180];way["natural"="coastline"]{bb}->.c;'
         f'way(around.c:{corridor})["highway"~"^({hw})$"]{bb}->.w;.w out body geom;'
         f'rel(bw.w)["route"~"^(hiking|foot|walking)$"]->.r;way.w(r.r);out ids;')
    data = fetch.overpass(f'paths{bb}:{corridor}', q)
    on_trail = {e['id'] for e in data.get('elements', []) if e.get('type') == 'way' and 'geometry' not in e}
    ways = [e for e in data.get('elements', []) if e.get('type') == 'way' and 'geometry' in e and 'nodes' in e
            and (e.get('tags') or {}).get('highway') in ROAD_FACTOR
            and (e.get('tags') or {}).get('foot') not in ('no', 'private')
            and not ((e.get('tags') or {}).get('access') in ('no', 'private')
                     and (e.get('tags') or {}).get('foot') not in ('yes', 'designated', 'permissive'))]
    if not ways:
        return None
    ctree = STRtree(coast) if coast else None

    def shore_dist(w):
        if ctree is None:
            return 2000
        g = w['geometry']
        best = 2000
        for q_ in (g[0], g[len(g) // 2], g[-1]):
            if q_:
                p = Point(TO_BNG(q_['lon'], q_['lat']))
                idx = ctree.nearest(p)
                best = min(best, coast[idx].distance(p))
        return best

    pts, adj, index = [], [], {}

    def node(nid, g):
        if nid not in index:
            index[nid] = len(pts)
            pts.append(TO_BNG(g['lon'], g['lat']))
            adj.append([])
        return index[nid]

    for w in ways:
        f = ROAD_FACTOR[w['tags']['highway']] * (0.55 if w['id'] in on_trail else 1) * (1 + shore_dist(w) / 400)
        for k in range(1, min(len(w['nodes']), len(w['geometry']))):
            g0, g1 = w['geometry'][k - 1], w['geometry'][k]
            if not g0 or not g1:
                continue
            u, v = node(w['nodes'][k - 1], g0), node(w['nodes'][k], g1)
            wgt = math.dist(pts[u], pts[v]) * f
            adj[u].append((v, wgt))
            adj[v].append((u, wgt))
    return shortest(pts, adj, a, b, snap=600, ratio=(8, 10000) if math.dist(a, b) < 25000 else (3, 15000))


def route_shoreline(fetch, a, b):
    box = box_around(a, b, pad_frac=0.6, min_pad=5000)
    data = coastline(fetch, box)
    pts, adj, index = [], [], {}
    for w in data.get('elements', []):
        if w.get('type') != 'way' or 'nodes' not in w:
            continue
        geo = w.get('geometry') or []
        for k in range(1, min(len(w['nodes']), len(geo))):
            g0, g1 = geo[k - 1], geo[k]
            if not g0 or not g1:
                continue
            for nid, g in ((w['nodes'][k - 1], g0), (w['nodes'][k], g1)):
                if nid not in index:
                    index[nid] = len(pts)
                    pts.append(TO_BNG(g['lon'], g['lat']))
                    adj.append([])
            u, v = index[w['nodes'][k - 1]], index[w['nodes'][k]]
            d = math.dist(pts[u], pts[v])
            adj[u].append((v, d))
            adj[v].append((u, d))
    return shortest(pts, adj, a, b, snap=3000, ratio=(6, 30000))


def shortest(pts, adj, a, b, snap, ratio):
    if not pts:
        return None

    def nearest(p):
        best, bi = snap, -1
        for i, q in enumerate(pts):
            if abs(q[0] - p[0]) < snap and abs(q[1] - p[1]) < snap:
                d = math.dist(p, q)
                if d < best:
                    best, bi = d, i
        return bi
    sa, sb = nearest(a), nearest(b)
    if sa < 0 or sb < 0:
        return None
    dist = {sa: 0.0}
    prev = {}
    heap = [(0.0, sa)]
    while heap:
        d, v = heapq.heappop(heap)
        if d > dist.get(v, 1e18):
            continue
        if v == sb:
            break
        for w, wgt in adj[v]:
            nd = d + wgt
            if nd < dist.get(w, 1e18):
                dist[w], prev[w] = nd, v
                heapq.heappush(heap, (nd, w))
    if sb not in dist:
        return None
    chain, v = [], sb
    while v != sa:
        chain.append(pts[v])
        v = prev[v]
    chain.append(pts[sa])
    line = LineString([a] + chain[::-1] + [b])
    k, extra = ratio
    if line.length > k * math.dist(a, b) + extra:
        return None
    return line.simplify(8)


def fill_gaps(fetch, path, report):
    cands, ends = find_gaps(path)
    score = lambda c: c['d'] * (1 + c['apart'] / 4)
    used_end, used_pair, gaps = set(), set(), []
    for c in sorted(cands, key=score):
        if c['a']['id'] in used_end or c['b']['id'] in used_end or c['pair'] in used_pair:
            continue
        used_end |= {c['a']['id'], c['b']['id']}
        used_pair.add(c['pair'])
        gaps.append(c)
    gaps.sort(key=lambda c: c['a']['t'])
    log(f'{len(gaps)} gaps to fill')

    def fill(c):
        a, b, d = c['a']['xy'], c['b']['xy'], c['d']
        if d < 150:
            return LineString([a, b]), 'joined straight'
        for corridor in (1500, 4000):
            try:
                g = route_footpaths(fetch, a, b, corridor)
            except Exception as e:       # noqa: BLE001
                log('   footpath search failed:', e)
                g = None
                break
            if g is not None:
                return g, 'guessed along footpaths near the shore'
        if d < 2000:
            return LineString([a, b]), 'a short crossing, joined straight'
        try:
            g = route_shoreline(fetch, a, b)
        except Exception as e:           # noqa: BLE001
            log('   shoreline trace failed:', e)
            g = None
        return (g, 'roughly along the shoreline') if g is not None else (None, None)

    unfilled = []
    for i, c in enumerate(gaps):
        log(f'[{i + 1}/{len(gaps)}] {place_name(c["a"]["xy"])} to {place_name(c["b"]["xy"])}, {c["d"] / 1000:.1f} km apart')
        g, how = fill(c)
        if g is None:
            unfilled.append(c)
            continue
        mi = path.add_all([g], 'guess', how, country=c['a']['country'])
        report['gaps'].append((where(c['a']['xy']), where(c['b']['xy']), how, mi))
    # A gap that couldn't be filled frees its ends to try their next-best partners
    for c in unfilled:
        used_end -= {c['a']['id'], c['b']['id']}
        used_pair.discard(c['pair'])
    retry_ends = {e for c in unfilled for e in (c['a']['id'], c['b']['id'])}
    tries = {}
    for c in sorted((c for c in cands if c not in unfilled and (c['a']['id'] in retry_ends or c['b']['id'] in retry_ends)), key=score):
        ia, ib = c['a']['id'], c['b']['id']
        if ia in used_end or ib in used_end or c['pair'] in used_pair:
            continue
        if tries.get(ia, 0) >= 2 or tries.get(ib, 0) >= 2:
            continue
        tries[ia] = tries.get(ia, 0) + 1
        tries[ib] = tries.get(ib, 0) + 1
        g, how = fill(c)
        if g is not None:
            used_end |= {ia, ib}
            used_pair.add(c['pair'])
            mi = path.add_all([g], 'guess', how, country=c['a']['country'])
            report['gaps'].append((where(c['a']['xy']), where(c['b']['xy']), how, mi))
    report['loose'] = [where(e['xy']) for e in ends if e['id'] not in used_end]


# --------------------------------------------------------------------------
# The build
# --------------------------------------------------------------------------

def build(fetch):
    report = {'sources': [], 'gaps': [], 'loose': []}
    path = Path()

    log('Natural England England Coast Path...')
    ne_lines, ne_names = arcgis_lines(fetch.arcgis('natural-england', NATURAL_ENGLAND))
    mi = path.add_all(ne_lines, 'official', 'Natural England', stretches=ne_names, clip=False)
    report['sources'].append(('Natural England, approved England Coast Path', mi))

    try:
        df_lines, df_names = arcgis_lines(fetch.arcgis('defra-copy', DEFRA_COPY))
        mi = path.add_all(df_lines, 'official', 'Natural England (Defra copy)', stretches=df_names)
        report['sources'].append(('Defra\u2019s copy of the same dataset (newer approvals)', mi))
    except Exception as e:               # noqa: BLE001
        log('   Defra copy unavailable:', e)
        report['sources'].append(('Defra\u2019s copy of the same dataset: unavailable', 0))

    log('Wales Coast Path...')
    w = fetch.overpass('wales', f'[out:json][timeout:180];relation({WALES_RELATION});>>;way._;out geom;')
    mi = path.add_all(osm_lines(w), 'official', 'Wales Coast Path (OpenStreetMap)', country='W')
    report['sources'].append(('Wales Coast Path, from OpenStreetMap', mi))

    log('OpenStreetMap England Coast Path routes...')
    ids = ','.join(str(i) for i in [ENGLAND_OSM_RELATION] + ENGLAND_OSM_EXTRA)
    bb = '({},{},{},{})'.format(*ENGLAND_BOX)
    q = (f'[out:json][timeout:240];(relation(id:{ids});'
         f'relation["route"~"^(hiking|foot|walking)$"]["name"~"England Coast Path",i]{bb};)->.r;'
         f'(.r;>>;)->.m;way.m;out geom;')
    mi = path.add_all(osm_lines(fetch.overpass('england-osm', q)), 'other', 'England Coast Path in OpenStreetMap')
    report['sources'].append(('OpenStreetMap\u2019s England Coast Path routes (incl. stretches mapped before opening)', mi))

    for name, match, box, fills in TRAILS:
        log(f'Trail: {name}...')
        bb = '({},{},{},{})'.format(*box)
        q = (f'[out:json][timeout:120];way["highway"]{bb}->.w;rel(bw.w)["name"~"{match}",i]->.r;'
             f'(way(r.r){bb};way["name"~"{match}",i]{bb};);out geom{bb};')
        try:
            lines = osm_lines(fetch.overpass('trail:' + name, q))
        except Exception as e:           # noqa: BLE001
            log('   unavailable:', e)
            report['sources'].append((f'{name} ({fills}): couldn\u2019t load', 0))
            continue
        mi = path.add_all(lines, 'other', name)
        note = '' if lines else ': not found in OpenStreetMap'
        report['sources'].append((f'{name} ({fills}){note}', mi))

    log('Guessing the remaining gaps...')
    fill_gaps(fetch, path, report)
    return path, report


def write_geojson(path, out):
    feats = []
    for p in path.pieces:
        coords = [list(map(lambda v: round(v, 5), TO_WGS(x, y))) for x, y in p['geom'].coords]
        feats.append({'type': 'Feature',
                      'properties': {'source': p['source'], 'via': p['via'], 'country': p['country'], 'stretch': p['stretch']},
                      'geometry': {'type': 'LineString', 'coordinates': coords}})
    fc = {'type': 'FeatureCollection',
          'properties': {'created': datetime.now(timezone.utc).isoformat(timespec='seconds'),
                         'note': 'King Charles III England Coast Path and Wales Coast Path, with unofficial stretches '
                                 '(source "other": existing trails and OpenStreetMap; source "guess": estimated). '
                                 'Built by build_coast_path.py.',
                         'attribution': 'Contains Natural England data (OS data \u00a9 Crown copyright and database right); '
                                        '\u00a9 OpenStreetMap contributors (ODbL)'},
          'features': feats}
    with open(out, 'w') as f:
        json.dump(fc, f, separators=(',', ':'))


def write_report(path, report, out):
    E = path.miles(country='E')
    W = path.miles(country='W')
    lines = ['# Coast path build report', '',
             f'Built {datetime.now(timezone.utc).strftime("%d %B %Y, %H:%M UTC")}.', '',
             f'- **England:** {E:,.0f} of about {EXPECTED_MI["E"]:,} miles '
             f'({path.miles("official", "E"):,.0f} official, {path.miles("other", "E"):,.0f} from other mapped paths, '
             f'{path.miles("guess", "E"):,.0f} guessed)',
             f'- **Wales:** {W:,.0f} of about {EXPECTED_MI["W"]:,} miles', '',
             '## Sources', '', '| Source | Miles added |', '|---|---:|']
    lines += [f'| {s} | {m:,.1f} |' for s, m in report['sources']]
    lines += ['', '## Gaps filled by guessing', '']
    if report['gaps']:
        lines += ['| From | To | How | Miles |', '|---|---|---|---:|']
        lines += [f'| {a} | {b} | {how} | {m:,.1f} |' for a, b, how, m in report['gaps']]
    else:
        lines.append('None.')
    lines += ['', '## Places where the path still stops', '',
              'Berwick and Gretna are its true ends; anything else is worth a look.', '']
    lines += [f'- near {n}' for n in report['loose']] or ['None.']
    with open(out, 'w') as f:
        f.write('\n'.join(lines) + '\n')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', default=os.path.join(HERE, '..', 'coast-path-full.geojson'))
    ap.add_argument('--report', default=os.path.join(HERE, 'report.md'))
    ap.add_argument('--cache', default=os.path.join(HERE, '.cache'))
    ap.add_argument('--refresh', action='store_true', help='ignore the cache and fetch everything again')
    ap.add_argument('--mock', help='read sample responses from this folder instead of the network')
    args = ap.parse_args()
    fetch = Fetcher(args.cache, refresh=args.refresh, mock_dir=args.mock)
    t0 = time.time()
    path, report = build(fetch)
    write_geojson(path, args.out)
    write_report(path, report, args.report)
    log(f'Done in {time.time() - t0:.0f} s: England {path.miles(country="E"):,.0f} mi, Wales {path.miles(country="W"):,.0f} mi, '
        f'{len(path.pieces)} pieces -> {args.out}')


if __name__ == '__main__':
    sys.exit(main())
