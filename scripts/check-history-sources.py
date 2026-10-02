"""Bounded live compatibility audit of named historical analogue inputs.

Reads public archive JSON only. Does not send a location, credentials, or user
appdata, and does not assert that another mission follows the archived flight.
"""
import asyncio
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.source_inputs import CachedReader
from app.trajectory_sources import HISTORY_INDEX, history_candidates, historical_profile
from app.store import Store


async def main():
    report = {'schema':1,'scope':'Live archive compatibility, NOT forecast or sighting validation','classes':[]}
    with tempfile.TemporaryDirectory(prefix='downrange-source-audit-') as directory:
        reader = CachedReader(Store(Path(directory)/'audit.sqlite3'))
        catalog = json.loads(await reader.get(HISTORY_INDEX,86400,robots=False))
        for vehicle,orbit in [('Falcon 9','International Space Station'),
                              ('Falcon 9','Geostationary Transfer Orbit'),
                              ('Falcon 9','Low Earth Orbit'),('Falcon Heavy','Low Earth Orbit')]:
            launch={'vehicle':vehicle,'orbit':orbit,'mission':'','mission_name':''}
            selected=history_candidates(catalog,launch)
            assert selected, f'No archive analogue matched {vehicle}/{orbit}'
            group={'vehicle':vehicle,'orbit_class':orbit,'profiles':[]}
            for entry in selected:
                urls=entry['JSON']
                try:
                    data=json.loads(await reader.get(urls['analysed'],86400,robots=False))
                    events=json.loads(await reader.get(urls['events'],86400,robots=False))
                    profile=historical_profile(data,events,entry['mission_name'],urls['analysed'])
                    group['profiles'].append({'name':profile['name'],'status':'parsed',
                        'samples':len(profile['samples']),'start_t_s':profile['samples'][0][0],
                        'end_t_s':profile['samples'][-1][0], 'source_url':profile['url']})
                except Exception as exc:
                    group['profiles'].append({'name':entry['mission_name'],'status':'unusable',
                                             'reason':type(exc).__name__+': '+str(exc)[:200]})
            report['classes'].append(group)
    output=Path('browser-artifacts');output.mkdir(exist_ok=True)
    (output/'historical-source-audit.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2),flush=True)
    assert all(any(p['status']=='parsed' for p in row['profiles']) for row in report['classes']), 'A mission class has no usable analogue'
    print('PASS: each configured Falcon mission class has at least one live parsed historical analogue.')

if __name__=='__main__':asyncio.run(main())
