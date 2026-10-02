from datetime import datetime, timezone
import pytest
from app.geometry import predict
from app.models import Trajectory, Preferences
from app.notifications import eligible
from app.profiles import automatic_tracks, corridor, combine


def launch(**changes):
    value = dict(id='f9-example', name='Falcon 9 | Starlink example', vehicle='Falcon 9 Block 5',
                 orbit='Low Earth Orbit', mission='', net='2026-10-02T00:00:00+00:00',
                 time_precise=True, status='Go', feed_active=True, demo=False,
                 pad=dict(latitude=28.6, longitude=-80.6))
    value.update(changes)
    return value


def test_auto_tracks_are_valid_and_always_estimated():
    tracks=automatic_tracks(launch())
    assert len(tracks)>=9
    for track in tracks:
        Trajectory.model_validate(track)
        assert track['kind']=='estimated'
        assert 'NOT probabilities' in track['notes']
        assert any(not p['powered'] for p in track['points'])


@pytest.mark.parametrize('changes',[
    {'pad':dict(latitude=None,longitude=None)},
    {'demo':True},
])
def test_unsupported_stays_unknown(changes):
    assert automatic_tracks(launch(**changes))==[]


def test_iss_has_northeast_assumption_not_starlink_guess():
    headings,reason=corridor(launch(name='Crew mission',orbit='International Space Station'))
    assert all(30<h<60 for h in headings)
    assert '51.6' in reason


def test_gto_and_polar_use_distinct_scenarios():
    gto,_=corridor(launch(orbit='Geostationary Transfer Orbit'))
    polar,_=corridor(launch(orbit='Sun-Synchronous Orbit'))
    assert gto==[75,90,105]
    assert len(polar)==6 and any(h>180 for h in polar)


def test_automatic_prediction_is_explicit_and_not_probability():
    result=predict(launch(),dict(latitude=40.7,longitude=-73.35,min_elevation_deg=5),None)
    assert result['automatic'] and result['confidence']=='estimated'
    assert result['scenario_counts']['total']>=9
    assert result['best_time'] is None
    assert result['warnings'][0].startswith('AUTOMATIC ESTIMATE')
    assert 'probability' not in result


def test_imported_track_overrides_automatic_model():
    l=launch()
    track=automatic_tracks(l)[0]
    track['kind']='mission-specific'
    track['source']='Test imported trajectory, not actual flight data'
    result=predict(l,dict(latitude=40.7,longitude=-73.35,min_elevation_deg=5),track)
    assert not result.get('automatic')
    assert result['confidence']=='mission-specific'


def test_auto_alerts_require_explicit_estimate_opt_in():
    l=launch()
    pred=dict(candidate=True,mode='trajectory',confidence='estimated',
              ordinary_windows=[{'start':l['net'],'end':l['net']}],jellyfish_windows=[])
    assert not eligible(l,{'alerts':True},pred,Preferences(enabled=True))
    assert eligible(l,{'alerts':True},pred,Preferences(enabled=True,include_estimates=True))


def test_unmodeled_negative_is_not_claimed_invisible():
    pred=predict(launch(vehicle='Unknown'),dict(latitude=-60,longitude=100),None)
    assert pred['confidence']=='estimated'
    assert pred['low_information']
    assert 'invisible' not in pred['ordinary']
