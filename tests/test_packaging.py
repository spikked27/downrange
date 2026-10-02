from pathlib import Path
import xml.etree.ElementTree as ET
import json
import pytest
from app import __version__
from app.config import Settings
ROOT=Path(__file__).resolve().parents[1]

def test_unraid_templates_version_port_and_permissions():
    for file in (ROOT/'templates').glob('*.xml'):
        root=ET.parse(file).getroot()
        assert root.attrib['version']=='2'
        assert root.findtext('Privileged')=='false'
        assert (root.findtext('Repository') == 'ghcr.io/spikked27/downrange:latest'
                if file.name == 'downrange.xml' else __version__ in root.findtext('Repository'))
        assert '[PORT:8097]' in root.findtext('WebUI')
        configs=root.findall('Config')
        assert any(c.attrib['Target']=='/data' for c in configs)
        assert not any('docker.sock' in str(c.attrib) for c in configs)

def test_manifest_assets_exist():
    manifest=json.loads((ROOT/'app/static/manifest.webmanifest').read_text())
    for icon in manifest['icons']:
        assert (ROOT/'app'/icon['src'].lstrip('/')).exists()

@pytest.mark.parametrize('url',['http://example.com','https://user@example.com','https://example.com/subpath','https://example.com?token=x'])
def test_public_url_validation(tmp_path,url):
    with pytest.raises(ValueError):Settings(data_dir=tmp_path,public_url=url)

def test_rate_limit_minimum_from_environment(tmp_path,monkeypatch):
    monkeypatch.setenv('POLL_SECONDS','5')
    assert Settings(data_dir=tmp_path).poll_seconds==600
