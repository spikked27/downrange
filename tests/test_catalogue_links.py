from app.trajectory_sources import history_candidates


def test_known_crs8_catalogue_typo_corrected_without_mutation():
    broken='https://raw.githubusercontent.com/shahar603/Telemetry-Data/master/SpaceX%20CRS-8/JSON/analysed2.json'
    catalog=[{'mission_name':'SpaceX CRS-8','analysed_stage':2,'JSON':{'analysed':broken}}]
    rows=history_candidates(catalog,{'vehicle':'Falcon 9','orbit':'International Space Station'})
    assert rows[0]['JSON']['analysed'].endswith('/analysed.json')
    assert catalog[0]['JSON']['analysed']==broken
    assert 'catalog_note' in rows[0]


def test_unrecognized_catalogue_url_not_rewritten():
    value='https://example.test/not-the-reviewed-file/analysed2.json'
    catalog=[{'mission_name':'SpaceX CRS-8','analysed_stage':2,'JSON':{'analysed':value}}]
    assert history_candidates(catalog,{'vehicle':'Falcon 9','orbit':'International Space Station'})[0]['JSON']['analysed']==value


def test_bad_catalogue_items_are_skipped():
    assert history_candidates([None,'bad',{}],{'vehicle':'Falcon 9'})==[]
