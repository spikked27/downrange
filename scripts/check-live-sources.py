"""Bounded live compatibility check. No credentials or observer data sent out.

This checks acquisition, not whether a rocket was actually seen. Run manually
or in CI with network access; ordinary unit tests do not depend on the Internet.
"""
import asyncio,json,tempfile,time,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.store import Store
from app.source_inputs import CachedReader,nextspaceflight_facts,jellyfish_facts
from app.trajectory_sources import HISTORY_INDEX,history_candidates,historical_profile
from app.profiles import automatic_tracks
from app.geometry import predict

async def main():
    mission={'id':'4651fd8a-43de-4166-bf8f-c168b3bd1d2c','name':'Falcon Heavy | NROL-97','mission_name':'NROL-97',
             'vehicle':'Falcon Heavy','net':'2026-10-02T03:54:00+00:00','time_precise':True,
             'pad':{'latitude':28.60822681,'longitude':-80.60428186},'orbit':'Unknown','mission':'Classified payload'}
    with tempfile.TemporaryDirectory() as directory:
        store=Store(Path(directory)/'check.sqlite3');reader=CachedReader(store)
        url='https://nextspaceflight.com/launches/details/7826/'
        facts=nextspaceflight_facts(await reader.get(url),mission,url)
        assert 20<=facts['heading_deg']<=70
        print('LIVE NSF MATCH',json.dumps({k:v for k,v in facts.items() if k!='links'}),flush=True)
        jelly=json.loads(await reader.get('https://jellyfish.johnkrausphotos.com/api/v2/upcoming'))
        other=jellyfish_facts(jelly,mission)
        print('LIVE JELLYFISH HEADING',json.dumps(other),flush=True)
        catalog=json.loads(await reader.get(HISTORY_INDEX,robots=False))
        candidates=history_candidates(catalog,mission)
        assert candidates,'Historical Falcon Heavy catalogue match missing'
        chosen=candidates[0];urls=chosen['JSON']
        profile=historical_profile(json.loads(await reader.get(urls['analysed'],robots=False)),
                                   json.loads(await reader.get(urls['events'],robots=False)),chosen['mission_name'],urls['analysed'])
        print('LIVE HISTORICAL PROFILE',profile['name'],'samples',len(profile['samples']),'last sample',profile['samples'][-1],flush=True)
        mission['acquisition']={'directions':[facts],'profiles':[profile],'evidence':[facts],'checked':time.time()}
        tracks=automatic_tracks(mission);assert tracks
        result=predict(mission,{'latitude':40.7,'longitude':-73.35,'min_elevation_deg':5},None)
        assert result['evidence_level']=='published-direction/history'
        print('END-TO-END GEOMETRY',json.dumps({k:result[k] for k in ('evidence_level','scenario_counts','max_elevation_deg','direction','first_visible')}),flush=True)
        print('PASS: live public direction + historical profile -> modeled geometry. NOT sighting validation.',flush=True)

if __name__=='__main__':asyncio.run(main())
