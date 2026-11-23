"""A small sample world modelled on Essex, for testing the build without the network."""
import json, os
def dens(pts, step=0.003):
    out = []
    for (a0, a1), (b0, b1) in zip(pts, pts[1:]):
        n = max(1, int(max(abs(b0 - a0), abs(b1 - a1)) / step))
        out += [(a0 + (b0 - a0) * k / n, a1 + (b1 - a1) * k / n) for k in range(n)]
    return out + [pts[-1]]
SUFFOLK = dens([(52.09, 1.32), (51.96, 1.35), (51.95, 1.27), (51.958, 1.10), (51.956, 1.05), (51.950, 1.068), (51.945, 1.085)])
HARWICH = dens([(51.945, 1.29), (51.93, 1.28)])
BLACKWATER = dens([(51.775, 0.92), (51.75, 0.80), (51.73, 0.68), (51.70, 0.80), (51.63, 0.81), (51.54, 0.71)])
BRIGHTLINGSEA = dens([(51.81, 1.02), (51.795, 1.05), (51.80, 1.08)])           # Defra's copy has this
STOUR = dens([(51.945, 1.085), (51.943, 1.15), (51.941, 1.22), (51.945, 1.29)])   # the Essex Way follows it
TENDRING = dens([(51.93, 1.28), (51.86, 1.27), (51.81, 1.20), (51.79, 1.15), (51.80, 1.08)])
COLNE_W = dens([(51.885, 0.92), (51.86, 0.93), (51.83, 0.93), (51.80, 0.92), (51.775, 0.92)])   # Colchester to West Mersea
COLNE_E = dens([(51.86, 0.96), (51.83, 0.99), (51.81, 1.02)])                                    # Wivenhoe to Brightlingsea
WIVENHOE_TRAIL = dens([(51.885, 0.92), (51.875, 0.94), (51.86, 0.96)])                          # Colchester to Wivenhoe
feat = lambda pts, name: {'attributes': {'Stretch_Name': name}, 'geometry': {'paths': [[[lo, la] for la, lo in pts]]}}
nid = [0]
def way(pts, tags, off=0.0, wid=None):
    nodes, geo = [], []
    for la, lo in pts:
        nid[0] += 1; nodes.append(nid[0]); geo.append({'lat': la + off, 'lon': lo})
    nid[0] += 1
    return {'type': 'way', 'id': wid or nid[0], 'tags': tags, 'nodes': nodes, 'geometry': geo}
coast = [way(seg, {'natural': 'coastline'}, -0.0012) for seg in (STOUR, TENDRING, COLNE_W + COLNE_E[::-1][1:], WIVENHOE_TRAIL)]
# Make the Colne coastline one continuous line round the estuary head, as OSM's is
colne = coast[2]; trail_coast = coast[3]
trail_coast['nodes'][0] = colne['nodes'][0]
world = {
    'natural_england': [feat(SUFFOLK, 'Shotley Gate to Felixstowe Ferry'), feat(HARWICH, 'Harwich to Shotley Gate'), feat(BLACKWATER, 'Maldon to Salcott')],
    'defra': [feat(BRIGHTLINGSEA, 'Salcott to Jaywick'), feat([(la + 0.0004, lo) for la, lo in SUFFOLK[:40]], 'Shotley Gate to Felixstowe Ferry')],
    'wales': [{'type': 'way', 'geometry': [{'lat': 51.60, 'lon': -4.30}, {'lat': 51.60, 'lon': -4.20}]}],
    'england_osm': [{'type': 'way', 'geometry': [{'lat': la + 0.0005, 'lon': lo} for la, lo in BLACKWATER[:60]]}],   # duplicates the official line
    'trails': {
        'Essex Way': [{'type': 'way', 'geometry': [{'lat': la + 0.0006, 'lon': lo} for la, lo in STOUR]}],
        'Wivenhoe Trail': [{'type': 'way', 'geometry': [{'lat': la, 'lon': lo} for la, lo in WIVENHOE_TRAIL]}],
    },
    'coastline': coast,
    'ways': [way(TENDRING, {'highway': 'footway'})],
    'on_walking_routes': [],
}
os.makedirs(os.path.join(os.path.dirname(__file__), 'essex'), exist_ok=True)
json.dump(world, open(os.path.join(os.path.dirname(__file__), 'essex', 'world.json'), 'w'))
print('sample world written')
