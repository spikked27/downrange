"""Observer code ships as an isolated, self-hosted UI addition."""
from pathlib import Path
import subprocess
from app import __version__
ROOT=Path(__file__).resolve().parents[1]

def test_projection_regressions():
    subprocess.run(['node',str(ROOT/'tests/test_observer.cjs')],check=True,cwd=ROOT)

def test_observer_assets_match_release_and_cache():
    loader=(ROOT/'app/static/sources-ui.js').read_text()
    worker=(ROOT/'app/static/sw.js').read_text()
    assert __version__ in loader and __version__ in worker
    for asset in ('observer.js','observer.css'):
        assert (ROOT/'app/static'/asset).exists()
        assert asset in loader and asset in worker

def test_existing_data_and_time_model_not_replaced_by_perspective():
    text=(ROOT/'app/static/observer.js').read_text()
    assert 'root.DownrangeTimeline' in text and 'api.sampleAt(points,selected,cutoff)' in text
    assert 'getUserMedia' not in text and 'geolocation' not in text
    assert 'fetch(' not in text and 'localStorage' not in text
    assert 'visibilitychange' in text and 'sliderObserver.disconnect()' in text
