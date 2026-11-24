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
OVERPASS = ['https://overpass-api.de/api/interpreter', 'https://overpass.private.coffee/api/interpreter',
            'https://overpass.kumi.systems/api/interpreter', 'https://maps.mail.ru/osm/tools/overpass/api/interpreter']
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
    ('Suffolk Coast Path', 'Suffolk Coast (Path|and Heaths|& Heaths)', (51.96, 1.30, 52.53, 1.80), 'Felixstowe to Hopton-on-Sea'),
    ('Isle of Wight Coastal Path', 'Isle of Wight Coastal Path', (50.57, -1.60, 50.78, -1.06), 'the Isle of Wight'),
    ('Lancashire Coastal Way', 'Lancashire Coastal Way', (53.62, -3.10, 54.21, -2.74), 'Silverdale to Tarleton'),
    # Regional trails along specific gaps
    ('Essex Way', 'Essex Way', (51.92, 1.03, 51.965, 1.295), 'Manningtree to Harwich (Stour)'),
    ('Stour and Orwell Walk', 'Stour (and|&) Orwell', (51.93, 1.03, 52.06, 1.40), 'Cattawade to Felixstowe'),
    ('Wivenhoe Trail', 'Wivenhoe Trail', (51.85, 0.90, 51.89, 0.98), 'Colchester to Wivenhoe (Colne)'),
    ('Colchester Orbital', 'Colchester Orbital', (51.82, 0.88, 51.90, 1.02), 'Rowhedge, Fingringhoe and Wivenhoe (Colne)'),
    ('Roach Valley Way', 'Roach Valley Way', (51.56, 0.68, 51.66, 0.86), 'Roach and Crouch sea walls'),
    ('Bournemouth Coast Path', 'Bournemouth Coast Path', (50.66, -1.98, 50.76, -1.55), 'Sandbanks to Milford on Sea'),
    ('Solent Way', 'Solent Way', (50.70, -1.72, 50.86, -0.93), 'Milford on Sea to Langstone'),
    ('Sussex Border Path', 'Sussex Border Path', (50.78, -0.95, 50.86, -0.85), 'Thorney Island (Chichester Harbour)'),
    ('Saxon Shore Way', 'Saxon Shore Way', (50.84, 0.55, 51.48, 0.95), 'Sheppey, Medway, Rye and Hastings'),
    ('Wirral Way', '^Wirral Way$', (53.28, -3.22, 53.45, -2.95), 'Wirral coast'),
    ('Hadrian\u2019s Wall Path', 'Hadrian.s Wall Path', (54.88, -3.25, 54.96, -2.92), 'Bowness-on-Solway to Carlisle'),
    ('Hadrian\u2019s Cycleway', 'Hadrian.s Cycleway', (54.76, -3.45, 54.96, -3.22), 'Allonby to Bowness-on-Solway'),
    ('Allerdale Ramble', 'Allerdale Ramble', (54.85, -3.40, 54.92, -3.22), 'Grune Point, by Silloth'),
    ('Cistercian Way', 'Cistercian Way', (54.05, -3.25, 54.25, -2.90), 'Furness peninsula'),
    ('Headland Way', 'Headland Way', (54.05, -0.30, 54.23, -0.05), 'Flamborough Head to Filey'),
    ('Severn Way', 'Severn Way', (51.45, -2.75, 51.62, -2.55), 'Aust to Avonmouth'),
]

# Trails recorded in OpenStreetMap as paths carrying the name, rather than as a route
NAMED_PATH_TRAILS = {'Wivenhoe Trail', 'Colchester Orbital'}
# Cycle routes used on purpose; every other trail must be a walking route
CYCLE_TRAILS = {'Hadrian\u2019s Cycleway'}
ISOLATED_MAX_M = 12000  # a stretch standing clear of the path must still be this close to it (the Colne is wide)

# Ferries the coast paths use, in path order: name, the water it crosses, the two
# landings (lat, lon), and when it runs. Timings are from the South West Coast Path
# Association's ferry list where it gives them; otherwise "check before you travel".
# The ferry's own line is taken from OpenStreetMap where it's mapped.
FERRIES = [
    ('Appledore to Instow', 'River Torridge', (51.0545, -4.1925), (51.0555, -4.1755), 'April to October'),
    ('Padstow to Rock', 'River Camel', (50.5428, -4.9365), (50.5490, -4.9230), 'all year'),
    ('Helford Passage to Helford', 'Helford River', (50.1010, -5.1275), (50.0955, -5.1355), 'seasonal; check before you travel'),
    ('Falmouth to St Mawes', 'Carrick Roads', (50.1540, -5.0675), (50.1590, -5.0150), 'all year; check before you travel'),
    ('St Mawes to Place', 'Porthcuel River', (50.1590, -5.0150), (50.1555, -5.0255), 'seasonal; check before you travel'),
    ('Fowey to Polruan', 'River Fowey', (50.3335, -4.6365), (50.3290, -4.6325), 'all year'),
    ('Cremyll to Plymouth', 'River Tamar', (50.3620, -4.1700), (50.3640, -4.1590), 'all year'),
    ('Warren Point to Noss Mayo', 'River Yealm', (50.3140, -4.0560), (50.3105, -4.0480), 'seasonal; check before you travel'),
    ('Bantham to Cockleridge', 'River Avon', (50.2795, -3.8800), (50.2775, -3.8745), 'seasonal; check before you travel'),
    ('Salcombe to East Portlemouth', 'Salcombe estuary', (50.2375, -3.7680), (50.2365, -3.7615), 'all year'),
    ('Dartmouth to Kingswear', 'River Dart', (50.3505, -3.5780), (50.3505, -3.5725), 'all year'),
    ('Teignmouth to Shaldon', 'River Teign', (50.5440, -3.5030), (50.5420, -3.5055), 'all year'),
    ('Exmouth to Starcross', 'River Exe', (50.6175, -3.4195), (50.6265, -3.4430), 'seasonal; check before you travel'),
    ('Sandbanks to Shell Bay', 'Poole Harbour', (50.6815, -1.9480), (50.6785, -1.9505), 'all year; check before you travel'),
    ('Mudeford Quay to Mudeford Sandbank', 'Christchurch Harbour', (50.7240, -1.7410), (50.7225, -1.7445), 'seasonal; check before you travel'),
    ('Cowes to East Cowes', 'River Medina', (50.7595, -1.2955), (50.7590, -1.2925), 'all year; check before you travel'),
    ('Hythe to Southampton', 'Southampton Water', (50.8705, -1.3970), (50.8960, -1.4050), 'check before you travel'),
    ('Hamble to Warsash', 'River Hamble', (50.8580, -1.3110), (50.8545, -1.3060), 'check before you travel'),
    ('Gosport to Portsmouth', 'Portsmouth Harbour', (50.7955, -1.1150), (50.7975, -1.1080), 'all year; check before you travel'),
    ('Eastney to Hayling Island', 'Langstone Harbour', (50.7900, -1.0315), (50.7915, -1.0260), 'check before you travel'),
    ('Harwich to Shotley', 'Harwich Harbour', (51.9465, 1.2885), (51.9530, 1.2700), 'seasonal; check before you travel'),
    ('Harwich to Felixstowe', 'Harwich Harbour', (51.9465, 1.2885), (51.9445, 1.3175), 'seasonal; check before you travel'),
    ('Felixstowe Ferry to Bawdsey', 'River Deben', (51.9875, 1.3915), (51.9905, 1.3965), 'seasonal; check before you travel'),
    ('Butley Ferry', 'Butley River', (52.0935, 1.4885), (52.0925, 1.4935), 'seasonal; check before you travel'),
    ('Walberswick to Southwold', 'River Blyth', (52.3170, 1.6710), (52.3185, 1.6690), 'seasonal; check before you travel'),
    ('Barmouth to Penrhyn Point', 'Afon Mawddach', (52.7200, -4.0525), (52.7185, -4.0625), 'seasonal; check before you travel'),
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
    def __init__(self, cache_dir, ttl_days=25, refresh=False, mock_dir=None, budget_min=None):
        self.cache_dir, self.ttl, self.refresh, self.mock = cache_dir, ttl_days * 86400, refresh, mock_dir
        self.last = 0
        # After this, no new requests: the build finishes with what it has, writes its
        # results, and lists what's left for the next run (cached data still loads)
        self.deadline = time.time() + budget_min * 60 if budget_min else None

    def out_of_time(self):
        return self.deadline is not None and time.time() > self.deadline
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
        if key.startswith('overpass:trail:') or key.startswith('overpass:trail-v2:'):
            return {'elements': w.get('trails', {}).get(key.split(':', 2)[2], [])}
        if key.startswith('overpass:ferry:'):
            return {'elements': w.get('ferries', {}).get(key.split(':', 2)[2], [])}
        if key.startswith('overpass:area-coast'):
            # Clip to the area, as the real service does with out geom(box)
            s0, w0, n0, e0 = map(float, key[key.index('(') + 1:key.index(')')].split(','))
            clip = lambda g: g if (s0 <= g['lat'] <= n0 and w0 <= g['lon'] <= e0) else None
            return {'elements': [dict(e, geometry=[clip(g) for g in e['geometry']]) for e in w.get('coastline', [])]}
        if key.startswith('overpass:area-paths'):
            if not key.endswith(':0'):
                return {'elements': []}
            ids = [{'type': 'way', 'id': i} for i in w.get('on_walking_routes', [])]
            return {'elements': w.get('ways', []) + ids}
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

    def overpass(self, key, query, timeout=180, attempts=3):
        def go():
            if self.out_of_time():
                raise RuntimeError('out of time for this run')
            last_err = None
            for attempt in range(attempts):
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
                if attempt + 1 < attempts and not self.out_of_time():
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

    def loose_ends(self):
        """End points of pieces that touch no other piece."""
        geoms = [p['geom'] for p in self.pieces]
        if not geoms:
            return []
        tree, out = STRtree(geoms), []
        for j, g in enumerate(geoms):
            for xy in (g.coords[0], g.coords[-1]):
                p = Point(xy)
                if not any(k != j and geoms[k].distance(p) <= LOOSE_M for k in tree.query(p.buffer(LOOSE_M))):
                    out.append(xy)
        return out

    def add_all(self, lines, source, via, country='E', stretches=None, clip=True, gaps_only=False, min_len=MIN_PIECE_M, box=None,
                clip_m=None):
        """Add lines, keeping only ground not already covered. Returns miles added.

        gaps_only: keep a piece only if it carries on from a loose end of the path
        (directly, or through other kept pieces), or stands clear of the path altogether,
        as a stretch in the middle of a gap does. A trail running parallel to the path,
        meeting it only partway along, fills no gap and is left out."""
        tree = STRtree([p['geom'] for p in self.pieces]) if self.pieces else None
        btree = STRtree(self.buffers) if self.buffers else None
        cands = []
        for i, line in enumerate(lines):
            if line.length < 1:
                continue
            if clip and btree is not None and clip_m is not None:
                # A tighter clip: only what lies more than clip_m from existing path
                near = [self.pieces[k]['geom'].buffer(clip_m, resolution=2) for k in btree.query(line)]
                parts = lines_of(line.difference(unary_union(near))) if near else [line]
                parts = [p for p in parts if p.length >= min_len]
            elif clip and btree is not None:
                # Only the covered ground near this line matters
                near = [self.buffers[k] for k in btree.query(line)]
                parts = lines_of(line.difference(unary_union(near))) if near else [line]
                parts = [p for p in parts if p.length >= min_len]
            else:
                parts = [line]
            cands += [(i, part) for part in parts]
        if gaps_only and self.pieces:
            frontier = self.loose_ends()
            geoms = [p['geom'] for p in self.pieces]
            gtree = STRtree(geoms)

            def meets_path(xy):
                p = Point(xy)
                return any(geoms[k].distance(p) <= JOIN_M for k in gtree.query(p.buffer(JOIN_M)))
            # Pieces clear of the path at both ends are in a gap: keep them, and carry on from
            # them, provided they stay near the path and don't run off the edge of the box
            # (a piece leaving the box is heading inland, not along the coast)
            def on_box_edge(xy):
                if box is None:
                    return False
                lat, lon = wgs(xy)
                s0, w0, n0, e0 = box
                return min(lat - s0, n0 - lat) < 0.002 or min(lon - w0, e0 - lon) < 0.003

            def near_path(part):
                return any(geoms[k].distance(part) <= ISOLATED_MAX_M for k in gtree.query(part.buffer(ISOLATED_MAX_M)))
            keep = [not meets_path(part.coords[0]) and not meets_path(part.coords[-1])
                    and not on_box_edge(part.coords[0]) and not on_box_edge(part.coords[-1]) and near_path(part)
                    for _, part in cands]
            for (_, part), k in zip(cands, keep):
                if k:
                    frontier += [part.coords[0], part.coords[-1]]
            changed = True
            while changed:
                changed = False
                fpts = [Point(xy) for xy in frontier]
                ftree = STRtree(fpts) if fpts else None
                for n, (i, part) in enumerate(cands):
                    if keep[n] or ftree is None:
                        continue
                    for xy in (part.coords[0], part.coords[-1]):
                        p = Point(xy)
                        if any(fpts[k].distance(p) <= JOIN_M for k in ftree.query(p.buffer(JOIN_M))):
                            keep[n] = changed = True
                            frontier += [part.coords[0], part.coords[-1]]
                            break
            cands = [c for c, k in zip(cands, keep) if k]
        added = []
        for i, part in cands:
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
        """Walking miles: ferries aren't counted unless asked for by name."""
        return sum(p['geom'].length for p in self.pieces
                   if (p['source'] == source if source else p['source'] != 'ferry')
                   and (country is None or p['country'] == country)) / 1609.344


# --------------------------------------------------------------------------
# Gaps: loose ends on separate pieces that sit near each other along the coast
# --------------------------------------------------------------------------

def components(path):
    """Which pieces connect (ends within LOOSE_M of another piece), and the loose ends."""
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
                k = int(k)
                if k != j and geoms[k].distance(p) <= LOOSE_M:
                    hit = True
                    a, b = find(j), find(k)
                    if a != b:
                        parent[a] = b
            if not hit:
                loose.append((j, end, xy))
    return geoms, tree, find, parent, loose


def coast_near(fetch, pts):
    """The coastline around some points, as (STRtree, lines), or None if it can't be fetched."""
    box = area_box(pts, pad=2000)
    bb = '({},{},{},{})'.format(*box)
    try:
        d = fetch.overpass('area-coast' + bb, f'[out:json][timeout:120];way["natural"="coastline"]{bb};out body geom{bb};',
                           timeout=150, attempts=2)
    except Exception:                   # noqa: BLE001
        return None
    lines = []
    for w in d.get('elements', []):
        run = []
        for g in (w.get('geometry') or []):
            if g and isinstance(g.get('lat'), (int, float)):
                run.append(TO_BNG(g['lon'], g['lat']))
            else:
                if len(run) > 1:
                    lines.append(LineString(run))
                run = []
        if len(run) > 1:
            lines.append(LineString(run))
    return (STRtree(lines), lines) if lines else (None, [])


def stitch(path, max_m, report, fetch=None):
    """Join each loose end to the nearest piece of path it isn't already connected to,
    if one is within max_m: pieces that don't quite meet, trails stopping just short,
    connections lost to trimming. Nearest first; a few rounds."""
    made, skipped = 0, []
    for _ in range(4):
        geoms, tree, find, parent, loose = components(path)
        joins = []
        loose_at = [(find(j), xy) for j, e, xy in loose]
        for j, end, xy in loose:
            p = Point(xy)
            # Another piece's loose end nearby is the natural partner: end to end
            best_end = min(((Point(o).distance(p), o) for c, o in loose_at if c != find(j) and Point(o).distance(p) <= max_m),
                           default=None)
            if best_end:
                k = next(int(k) for k in tree.query(Point(best_end[1]).buffer(1)) if find(int(k)) != find(j))
                joins.append((best_end[0], j, xy, best_end[1], k))
                continue
            # Otherwise the nearest point on another piece (never partway along a ferry,
            # which is out on the water: ferries join only at their landings)
            best, bq, bk = max_m, None, None
            for k in tree.query(p.buffer(max_m)):
                k = int(k)
                if find(k) == find(j) or path.pieces[k]['source'] == 'ferry':
                    continue
                d = geoms[k].distance(p)
                if d < best:
                    q = geoms[k].interpolate(geoms[k].project(p))
                    best, bq, bk = d, (q.x, q.y), k
            if bq is not None:
                joins.append((best, j, xy, bq, bk))
        joins.sort(key=lambda t: t[0])
        # The coastline around the candidate links, fetched by area, to keep links off the water
        coast_of = {}
        if fetch is not None and joins:
            cells = {}
            for t in joins:
                cells.setdefault((int(t[2][0] // 30000), int(t[2][1] // 30000)), []).append(t)
            for cell, ts in cells.items():
                c = coast_near(fetch, [t[2] for t in ts] + [t[3] for t in ts])
                for t in ts:
                    coast_of[id(t)] = c
        n = 0
        for t in joins:
            d, j, xy, q, k = t
            a, b = find(j), find(k)
            if a == b:
                continue
            if fetch is not None:
                c = coast_of.get(id(t))
                if c is None and d > 100:
                    continue                    # no coastline to check against: only the shortest links
                if c and c[0] is not None and crosses(LineString([xy, q]), c):
                    skipped.append(xy)          # it would cross water: leave it to the guessing
                    continue
            parent[a] = b
            line = LineString([xy, q]) if d > 0.5 else None
            if line is not None:
                path.pieces.append({'geom': line, 'source': 'guess', 'via': 'joined to the nearest path',
                                    'country': path.pieces[j]['country'], 'stretch': None})
                path.buffers.append(line.buffer(BUFFER_M, resolution=2))
            n += 1
        made += n
        if not n:
            break
    report['stitched'] = report.get('stitched', 0) + made
    log(f'   joined {made} near-misses within {max_m:.0f} m; {len(set(skipped))} left alone because the link would cross water')


def find_gaps(path):
    geoms, tree, find, parent, loose = components(path)
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
# Filling the gaps, area by area. Neighbouring gaps are grouped into areas up to
# about 60 km across; each area's coastline and footpaths are fetched once, and
# every gap in it is then worked out locally, with no more requests.
# --------------------------------------------------------------------------

AREA_MAX_M = 60000     # the widest area fetched in one go
CELL_M = 2000          # footpaths are fetched in squares this size along the coastline
CELLS_PER_QUERY = 250


def area_box(points, pad=4000):
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    corners = [wgs((x, y)) for x in (min(xs) - pad, max(xs) + pad) for y in (min(ys) - pad, max(ys) + pad)]
    return (round(min(c[0] for c in corners), 4), round(min(c[1] for c in corners), 4),
            round(max(c[0] for c in corners), 4), round(max(c[1] for c in corners), 4))


def cell_box(i, j):
    corners = [wgs((x, y)) for x in (i * CELL_M, (i + 1) * CELL_M) for y in (j * CELL_M, (j + 1) * CELL_M)]
    return (round(min(c[0] for c in corners), 4), round(min(c[1] for c in corners), 4),
            round(max(c[0] for c in corners), 4), round(max(c[1] for c in corners), 4))


def crosses(line, coast):
    """Does a straight link cross the coastline (and so water) away from its own ends?
    coast is (STRtree, lines) or None."""
    if not coast:
        return False
    tree, lines = coast
    a, b = Point(line.coords[0]), Point(line.coords[-1])
    for k in tree.query(line):
        x = line.intersection(lines[int(k)])
        for pt in ([x] if x.geom_type == 'Point' else getattr(x, 'geoms', [])):
            if pt.geom_type == 'Point' and pt.distance(a) > 5 and pt.distance(b) > 5:
                return True
    return False


class Network:
    """A routing network: points, neighbours, and a grid for finding the nearest point."""
    def __init__(self):
        self.pts, self.adj, self.index, self.grid = [], [], {}, {}
        self.coast = None

    def node(self, nid, xy):
        i = self.index.get(nid)
        if i is None:
            i = self.index[nid] = len(self.pts)
            self.pts.append(xy)
            self.adj.append([])
            self.grid.setdefault((int(xy[0] // 250), int(xy[1] // 250)), []).append(i)
        return i

    def edge(self, u, v, w):
        self.adj[u].append((v, w))
        self.adj[v].append((u, w))

    def nearest(self, p, snap):
        best, bi = snap, -1
        r = int(snap // 250) + 1
        ci, cj = int(p[0] // 250), int(p[1] // 250)
        for di in range(-r, r + 1):
            for dj in range(-r, r + 1):
                for i in self.grid.get((ci + di, cj + dj), ()):
                    d = math.dist(p, self.pts[i])
                    if d < best:
                        best, bi = d, i
        return bi

    def route(self, a, b, snap, ratio):
        sa, sb = self.nearest(a, snap), self.nearest(b, snap)
        if sa < 0 or sb < 0:
            return None
        k, extra = ratio
        limit = (k * math.dist(a, b) + extra) * 8      # weights run above lengths; don't search forever
        dist, prev, heap = {sa: 0.0}, {}, [(0.0, sa)]
        while heap:
            d, v = heapq.heappop(heap)
            if d > dist.get(v, 1e18):
                continue
            if v == sb or d > limit:
                break
            for w, wgt in self.adj[v]:
                nd = d + wgt
                if nd < dist.get(w, 1e18):
                    dist[w], prev[w] = nd, v
                    heapq.heappush(heap, (nd, w))
        if sb not in prev and sb != sa:
            return None
        chain, v = [], sb
        while v != sa:
            chain.append(self.pts[v])
            v = prev[v]
        chain.append(self.pts[sa])
        line = LineString([a] + chain[::-1] + [b])
        if line.length > k * math.dist(a, b) + extra:
            return None
        return line.simplify(8)


def fetch_area(fetch, gaps, attempts=1):
    """Coastline and walkable ways for an area of gaps. Returns (footpath network, shoreline network)."""
    pts = [g['a']['xy'] for g in gaps] + [g['b']['xy'] for g in gaps]
    box = area_box(pts)
    bb = '({},{},{},{})'.format(*box)
    cdata = fetch.overpass('area-coast' + bb, f'[out:json][timeout:120];way["natural"="coastline"]{bb};out body geom{bb};',
                           timeout=150, attempts=attempts)
    shore = Network()
    coast_lines = []
    for w in cdata.get('elements', []):
        if w.get('type') != 'way' or 'nodes' not in w:
            continue
        geo, run = w.get('geometry') or [], []
        for k in range(min(len(w['nodes']), len(geo))):
            g = geo[k]
            if not g or not isinstance(g.get('lat'), (int, float)):
                if len(run) > 1:
                    coast_lines.append(LineString(run))
                run = []
                continue
            xy = TO_BNG(g['lon'], g['lat'])
            run.append(xy)
            u = shore.node(w['nodes'][k], xy)
            if k and geo[k - 1] and isinstance(geo[k - 1].get('lat'), (int, float)):
                v = shore.index[w['nodes'][k - 1]]
                shore.edge(u, v, math.dist(xy, shore.pts[v]))
        if len(run) > 1:
            coast_lines.append(LineString(run))
    # Squares along the coastline (and round every gap end), then the ways in them
    cells = set()
    for l in coast_lines:
        n = max(2, int(l.length / (CELL_M / 2)))
        for k in range(n + 1):
            p = l.interpolate(k / n, normalized=True)
            i, j = int(p.x // CELL_M), int(p.y // CELL_M)
            cells |= {(i + di, j + dj) for di in (-1, 0, 1) for dj in (-1, 0, 1)}
    for x, y in pts:
        i, j = int(x // CELL_M), int(y // CELL_M)
        cells |= {(i + di, j + dj) for di in (-1, 0, 1) for dj in (-1, 0, 1)}
    cells = sorted(cells)
    hw = '|'.join(ROAD_FACTOR)
    ways, on_trail = {}, set()

    def get(chunk, key, depth=0):
        boxes = ''.join('way["highway"~"^({})$"]({},{},{},{});'.format(hw, *cell_box(i, j)) for i, j in chunk)
        q = (f'[out:json][timeout:180];({boxes})->.w;.w out body geom;'
             f'rel(bw.w)["route"~"^(hiking|foot|walking)$"]->.r;way.w(r.r);out ids;')
        try:
            return fetch.overpass(key, q, timeout=210, attempts=attempts if depth == 0 else 1)
        except Exception:
            # Usually too big to finish in time: split it in half and fetch each
            if depth >= 4 or len(chunk) < 8:
                raise
            mid = len(chunk) // 2
            log(f'   splitting a request of {len(chunk)} squares in two')
            a = get(chunk[:mid], key + 'a', depth + 1)
            b = get(chunk[mid:], key + 'b', depth + 1)
            return {'elements': a.get('elements', []) + b.get('elements', [])}

    for c0 in range(0, len(cells), CELLS_PER_QUERY):
        d = get(cells[c0:c0 + CELLS_PER_QUERY], f'area-paths{bb}:{c0}')
        for e in d.get('elements', []):
            if e.get('type') != 'way':
                continue
            if 'geometry' in e and 'nodes' in e:
                ways[e['id']] = e
            else:
                on_trail.add(e.get('id'))
    ctree = STRtree(coast_lines) if coast_lines else None

    def shore_dist(w):
        if ctree is None:
            return 2000
        g, best = w['geometry'], 2000
        for q_ in (g[0], g[len(g) // 2], g[-1]):
            if q_:
                p = Point(TO_BNG(q_['lon'], q_['lat']))
                best = min(best, coast_lines[ctree.nearest(p)].distance(p))
        return best

    shore.coast = (STRtree(coast_lines), coast_lines) if coast_lines else None
    net = Network()
    for w in ways.values():
        t = w.get('tags') or {}
        if t.get('highway') not in ROAD_FACTOR or t.get('foot') in ('no', 'private'):
            continue
        if t.get('access') in ('no', 'private') and t.get('foot') not in ('yes', 'designated', 'permissive'):
            continue
        f = ROAD_FACTOR[t['highway']] * (0.55 if w['id'] in on_trail else 1) * (1 + shore_dist(w) / 400)
        prev = None
        for k in range(min(len(w['nodes']), len(w['geometry']))):
            g = w['geometry'][k]
            if not g:
                prev = None
                continue
            u = net.node(w['nodes'][k], TO_BNG(g['lon'], g['lat']))
            if prev is not None:
                net.edge(u, prev, math.dist(net.pts[u], net.pts[prev]) * f)
            prev = u
    return net, shore


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
    # Group neighbouring gaps into areas
    areas, cur = [], []
    for g in gaps:
        pts = [p for c in cur + [g] for p in (c['a']['xy'], c['b']['xy'])]
        span = max(max(p[0] for p in pts) - min(p[0] for p in pts), max(p[1] for p in pts) - min(p[1] for p in pts))
        if cur and span > AREA_MAX_M:
            areas.append(cur)
            cur = []
        cur.append(g)
    if cur:
        areas.append(cur)
    log(f'{len(gaps)} gaps to fill, in {len(areas)} areas')

    def fill(c, net, shore):
        a, b, d = c['a']['xy'], c['b']['xy'], c['d']
        if d < 150 and (shore is None or not crosses(LineString([a, b]), shore.coast)):
            return LineString([a, b]), 'joined straight'
        if net is not None:
            g = net.route(a, b, 600, (8, 10000) if d < 25000 else (3, 15000))
            if g is not None:
                return g, 'guessed along footpaths near the shore'
        if d < 2000:
            return LineString([a, b]), 'a short crossing, joined straight'
        if shore is not None:
            g = shore.route(a, b, 3000, (6, 30000))
            if g is not None:
                return g, 'roughly along the shoreline'
        return None, None

    done = set()

    def add_guess(c, g, how):
        """Add a guessed route, keeping only what isn't already covered, but never losing
        the connection: a short gap goes in whole, and a guess trimmed to nothing becomes
        a straight link between the two ends."""
        country = c['a']['country']
        if how == 'joined straight':
            return path.add_all([g], 'guess', how, country=country, clip=False)
        mi = path.add_all([g], 'guess', how, country=country, min_len=30)
        if mi < 0.01:
            # The route runs alongside existing path almost all the way; keep just the part
            # more than 40 m from it, which is the missing link itself, along real ways
            mi = path.add_all([g], 'guess', how, country=country, min_len=10, clip_m=LOOSE_M)
        return mi

    def process(area, net, shore):
        for c in area:
            g, how = fill(c, net, shore)
            if g is None:
                continue
            done.add(id(c))
            mi = add_guess(c, g, how)
            report['gaps'].append((where(c['a']['xy']), where(c['b']['xy']), how, mi))
            report.setdefault('gap_pts', []).append({'a': wgs(c['a']['xy']), 'b': wgs(c['b']['xy']), 'how': how, 'mi': round(mi, 2)})
        # Ends of unfilled gaps here try their next-best partners, within this area's data
        unfilled = [c for c in area if id(c) not in done]
        if not unfilled or net is None:
            return
        for c in unfilled:
            used_end.difference_update({c['a']['id'], c['b']['id']})
            used_pair.discard(c['pair'])
        free_ends = {e for c in unfilled for e in (c['a']['id'], c['b']['id'])}
        tries = {}
        for c in sorted((c for c in cands if c not in area and (c['a']['id'] in free_ends or c['b']['id'] in free_ends)), key=score):
            ia, ib = c['a']['id'], c['b']['id']
            if ia in used_end or ib in used_end or c['pair'] in used_pair or tries.get(ia, 0) >= 2 or tries.get(ib, 0) >= 2:
                continue
            tries[ia] = tries.get(ia, 0) + 1
            tries[ib] = tries.get(ib, 0) + 1
            g, how = fill(c, net, shore)
            if g is not None:
                used_end.update({ia, ib})
                used_pair.add(c['pair'])
                mi = add_guess(c, g, how)
                report['gaps'].append((where(c['a']['xy']), where(c['b']['xy']), how, mi))
                report.setdefault('gap_pts', []).append({'a': wgs(c['a']['xy']), 'b': wgs(c['b']['xy']), 'how': how, 'mi': round(mi, 2)})

    deferred = []
    for ai, area in enumerate(areas):
        log(f'[area {ai + 1}/{len(areas)}] {len(area)} gaps near {place_name(area[0]["a"]["xy"])}')
        net = shore = None
        if any(c['d'] >= 150 for c in area):
            try:
                net, shore = fetch_area(fetch, area)
            except Exception as e:           # noqa: BLE001
                log('   couldn\u2019t fetch this area for now, will retry at the end:', e)
                deferred.append(area)
                continue
        process(area, net, shore)
    # Areas that failed get another go after a cool-down; only if that fails too do
    # their gaps fall back to straight links for short breaks
    if deferred:
        log(f'Retrying {len(deferred)} area(s) after a pause...')
        if not fetch.out_of_time():
            time.sleep(0 if fetch.mock else 180)
    def retry(area, depth=0):
        try:
            net, shore = fetch_area(fetch, area, attempts=2)
        except Exception as e:               # noqa: BLE001
            if len(area) > 1 and depth < 3 and not fetch.out_of_time():
                log(f'   splitting the area near {place_name(area[0]["a"]["xy"])} ({len(area)} gaps) in two')
                mid = len(area) // 2
                retry(area[:mid], depth + 1)
                retry(area[mid:], depth + 1)
                return
            log(f'   still unavailable near {place_name(area[0]["a"]["xy"])}:', e)
            report.setdefault('unfetched', []).append(where(area[0]['a']['xy']))
            net = shore = None
        process(area, net, shore)

    for area in deferred:
        retry(area)
    report['loose'] = [where(e['xy']) for e in ends if e['id'] not in used_end]
    report['loose_pts'] = [[round(v, 5) for v in wgs(e['xy'])] for e in ends if e['id'] not in used_end]


# --------------------------------------------------------------------------
# The build
# --------------------------------------------------------------------------

def add_ferries(fetch, path, report):
    """Each ferry the route uses, as its own kind of line: from OpenStreetMap where the
    ferry is mapped, otherwise straight between the landings. A ferry links the path on
    either side, so the gap there isn't guessed as a long walk round."""
    report['ferries'] = []
    for name, water, a, b, note in FERRIES:
        A, B = TO_BNG(a[1], a[0]), TO_BNG(b[1], b[0])
        box = area_box([A, B], pad=1500)
        bb = '({},{},{},{})'.format(*box)
        line, mapped = None, False
        try:
            d = fetch.overpass('ferry:' + name, f'[out:json][timeout:60];way["route"="ferry"]{bb};out geom;', timeout=90, attempts=2)
            best = 1500.0
            for w in osm_lines(d):
                s0, s1 = w.coords[0], w.coords[-1]
                fit = min(math.dist(s0, A) + math.dist(s1, B), math.dist(s1, A) + math.dist(s0, B))
                if fit < best and w.length < 8000:
                    best, line = fit, (w if math.dist(s0, A) + math.dist(s1, B) <= math.dist(s1, A) + math.dist(s0, B)
                                       else LineString(list(w.coords)[::-1]))
            mapped = line is not None
        except Exception as e:           # noqa: BLE001
            log(f'   {name}: ferry line unavailable ({e}); drawing it straight')
        if line is None:
            line = LineString([A, B])
        label = name if name.lower().endswith('ferry') else f'{name} ferry'
        path.pieces.append({'geom': line, 'source': 'ferry', 'via': label, 'country': 'W' if a[1] < -3.9 and a[0] > 52.5 else 'E',
                            'stretch': None, 'water': water, 'note': note})
        path.buffers.append(line.buffer(10, resolution=2))
        report['ferries'].append((name, water, note, 'mapped in OpenStreetMap' if mapped else 'drawn straight'))


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
    mi = path.add_all(osm_lines(fetch.overpass('england-osm', q)), 'other', 'England Coast Path in OpenStreetMap', gaps_only=True)
    report['sources'].append(('OpenStreetMap\u2019s England Coast Path routes (incl. stretches mapped before opening)', mi))

    def trail(name, match, box, fills):
        # Routes whose name contains the trail's (stage routes too, and the members of any
        # parent route), plus, for trails recorded only as named paths, those paths.
        # Scanning every road in the box instead would be far too heavy in big boxes.
        bb = '({},{},{},{})'.format(*box)
        named_paths = f'way["name"~"{match}",i]{bb};' if name in NAMED_PATH_TRAILS else ''
        kinds = 'hiking|foot|walking|bicycle' if name in CYCLE_TRAILS else 'hiking|foot|walking'
        q = (f'[out:json][timeout:180];relation["route"~"^({kinds})$"]["name"~"{match}",i]{bb}->.r;(.r;>>;)->.m;'
             f'(way.m["highway"]{bb};{named_paths});out geom{bb};')
        lines = osm_lines(fetch.overpass('trail-v2:' + name, q))
        mi = path.add_all(lines, 'other', name, gaps_only=True, box=box)
        report['sources'].append((f'{name} ({fills})' + ('' if lines else ': not found in OpenStreetMap'), mi))

    failed = []
    for t in TRAILS:
        log(f'Trail: {t[0]}...')
        try:
            trail(*t)
        except Exception as e:           # noqa: BLE001
            log('   unavailable for now, will retry:', e)
            failed.append(t)
    # Server trouble is usually brief: retry after a cool-down, before guessing starts,
    # so a trail that loads second time is used rather than guessed over
    for round_ in (1, 2):
        if not failed:
            break
        log(f'Retrying {len(failed)} trail(s) after a pause...')
        if fetch.out_of_time():
            break
        time.sleep(0 if fetch.mock else 120 * round_)
        still = []
        for t in failed:
            try:
                trail(*t)
            except Exception as e:       # noqa: BLE001
                log(f'   {t[0]} still unavailable:', e)
                still.append(t)
        failed = still
    for name, match, box, fills in failed:
        report['sources'].append((f'{name} ({fills}): couldn\u2019t load', 0))

    log('Ferries...')
    add_ferries(fetch, path, report)
    log('Joining pieces that nearly meet...')
    stitch(path, 300, report, fetch)
    log('Guessing the remaining gaps...')
    fill_gaps(fetch, path, report)
    log('Joining anything still just short...')
    stitch(path, 300, report, fetch)
    # How continuous the finished path is, and where it still stops
    geoms, tree, find, parent, loose = components(path)
    sizes = {}
    for j, g in enumerate(geoms):
        walk = 0 if path.pieces[j]['source'] == 'ferry' else g.length     # a ferry alone isn't a piece of path
        sizes[find(j)] = sizes.get(find(j), 0) + walk
    big = {c for c, m in sizes.items() if m >= SUBSTANTIAL_M}
    report['pieces'] = (len(big), max(sizes.values()) / 1609.344 if sizes else 0)
    final_loose = [xy for j, e, xy in loose if find(j) in big and path.pieces[j]['source'] != 'ferry']
    # A ferry landing that meets no path probably has its coordinates slightly off
    report['ferry_unlinked'] = sorted({path.pieces[j]['via'] for j, e, xy in loose if path.pieces[j]['source'] == 'ferry'})
    report['loose'] = [where(xy) for xy in final_loose]
    report['loose_pts'] = [[round(v, 5) for v in wgs(xy)] for xy in final_loose]
    return path, report


def write_geojson(path, out, report=None):
    feats = []
    for p in path.pieces:
        coords = [list(map(lambda v: round(v, 5), TO_WGS(x, y))) for x, y in p['geom'].coords]
        feats.append({'type': 'Feature',
                      'properties': dict({'source': p['source'], 'via': p['via'], 'country': p['country'], 'stretch': p['stretch']},
                                         **({'water': p['water'], 'note': p['note']} if p['source'] == 'ferry' else {})),
                      'geometry': {'type': 'LineString', 'coordinates': coords}})
    fc = {'type': 'FeatureCollection',
          'properties': {'created': datetime.now(timezone.utc).isoformat(timespec='seconds'),
                         'note': 'King Charles III England Coast Path and Wales Coast Path, with unofficial stretches '
                                 '(source "other": existing trails and OpenStreetMap; source "guess": estimated). '
                                 'Built by build_coast_path.py.',
                         'attribution': 'Contains Natural England data (OS data \u00a9 Crown copyright and database right); '
                                        '\u00a9 OpenStreetMap contributors (ODbL)',
                         # For review.html: where the path still stops, and the guessed gaps
                         'review': {
                             'loose': (report or {}).get('loose_pts', []),
                             'gaps': [{'a': [round(v, 5) for v in g['a']], 'b': [round(v, 5) for v in g['b']], 'how': g['how'], 'mi': g['mi']}
                                      for g in (report or {}).get('gap_pts', [])],
                             'sources': [[name, round(mi, 1)] for name, mi in (report or {}).get('sources', [])],
                         }},
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
             f'- **Wales:** {W:,.0f} of about {EXPECTED_MI["W"]:,} miles',
             f'- **Continuity:** {report.get("pieces", (0, 0))[0]} separate pieces of path over a mile long; the longest is '
             f'{report.get("pieces", (0, 0))[1]:,.0f} miles. One piece would mean it runs unbroken all the way round '
             f'(islands aside). {report.get("stitched", 0)} near-misses were joined.', '',
             '## Sources', '', '| Source | Miles added |', '|---|---:|']
    lines += [f'| {s} | {m:,.1f} |' for s, m in report['sources']]
    if report.get('ferries'):
        lines += ['', '## Ferries', '', '| Ferry | Crosses | Runs | Line |', '|---|---|---|---|']
        lines += [f'| {n} | {w} | {t} | {how} |' for n, w, t, how in report['ferries']]
        if report.get('ferry_unlinked'):
            lines += ['', 'These ferries have a landing that meets no path, so their landing points may need adjusting: '
                      + ', '.join(report['ferry_unlinked']) + '.']
    lines += ['', '## Gaps filled by guessing', '']
    if report['gaps']:
        lines += ['| From | To | How | Miles |', '|---|---|---|---:|']
        lines += [f'| {a} | {b} | {how} | {m:,.1f} |' for a, b, how, m in report['gaps']]
    else:
        lines.append('None.')
    if report.get('unfetched'):
        lines += ['', '## Areas that couldn\u2019t be fetched', '',
                  'The servers didn\u2019t answer for these even after a retry, or the run reached its time limit first; '
                  'short breaks there are joined straight for now. Run the build again to fetch them: everything '
                  'already fetched is reused.', '']
        lines += [f'- near {n}' for n in report['unfetched']]
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
    ap.add_argument('--budget', type=float, default=255,
                    help='minutes of fetching before finishing with what it has (default 255, inside GitHub\u2019s 5 hours)')
    args = ap.parse_args()
    fetch = Fetcher(args.cache, refresh=args.refresh, mock_dir=args.mock, budget_min=args.budget)
    t0 = time.time()
    path, report = build(fetch)
    write_geojson(path, args.out, report)
    write_report(path, report, args.report)
    log(f'Done in {time.time() - t0:.0f} s: England {path.miles(country="E"):,.0f} mi, Wales {path.miles(country="W"):,.0f} mi, '
        f'{len(path.pieces)} pieces -> {args.out}')


if __name__ == '__main__':
    sys.exit(main())
