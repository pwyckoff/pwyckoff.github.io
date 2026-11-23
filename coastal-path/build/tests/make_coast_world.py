"""The whole coast as a sample world: town-to-town lines with two gaps and decoy fragments."""
import json, os, random, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from build_coast_path import COAST_ORDER
random.seed(7)
def dens(a, b, step=0.004):
    n = max(1, int(max(abs(b[1] - a[1]), abs(b[2] - a[2])) / step))
    return [(a[1] + (b[1] - a[1]) * k / n, a[2] + (b[2] - a[2]) * k / n) for k in range(n + 1)]
names = [t[0] for t in COAST_ORDER]
ci, ce = names.index('Chepstow'), names.index('Chester')
GAPS = {('Manningtree', 'Harwich'), ('Lymington', 'Bournemouth')}
ne, wal, gap_legs = [], [], []
for i in range(1, len(COAST_ORDER)):
    a, b = COAST_ORDER[i - 1], COAST_ORDER[i]
    seg = dens(a, b)
    if (a[0], b[0]) in GAPS:
        gap_legs.append(seg); continue
    cut = len(seg) // 2
    for part in (seg[:cut + 1], seg[cut:]):
        if random.random() < 0.4: part = part[::-1]
        if ci <= i - 1 < ce:
            wal.append({'type': 'way', 'geometry': [{'lat': la, 'lon': lo} for la, lo in part]})
        else:
            ne.append({'attributes': {}, 'geometry': {'paths': [[[lo, la] for la, lo in part]]}})
for t in ['Manningtree', 'Harwich', 'Bournemouth', 'Lymington']:
    _, la0, lo0 = COAST_ORDER[names.index(t)]
    for k in range(10):
        la, lo = la0 + random.uniform(-0.03, 0.03), lo0 + random.uniform(-0.05, 0.05)
        ne.append({'attributes': {}, 'geometry': {'paths': [[[lo, la], [lo + 0.002, la + 0.001]]]}})
nid = [0]; coast = []; ways = []
for seg in gap_legs:
    nodes = []
    for _ in seg: nid[0] += 1; nodes.append(nid[0])
    coast.append({'type': 'way', 'tags': {'natural': 'coastline'}, 'nodes': nodes, 'geometry': [{'lat': la - 0.0012, 'lon': lo} for la, lo in seg]})
    nodes = []
    for _ in seg: nid[0] += 1; nodes.append(nid[0])
    nid[0] += 1
    ways.append({'type': 'way', 'id': nid[0], 'tags': {'highway': 'footway'}, 'nodes': nodes, 'geometry': [{'lat': la, 'lon': lo} for la, lo in seg]})
os.makedirs(os.path.join(os.path.dirname(__file__), 'coast'), exist_ok=True)
json.dump({'natural_england': ne, 'wales': wal, 'coastline': coast, 'ways': ways},
          open(os.path.join(os.path.dirname(__file__), 'coast', 'world.json'), 'w'))
print(f'{len(ne)} official pieces, {len(wal)} Welsh pieces')
