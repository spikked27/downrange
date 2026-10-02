import asyncio,json,time
import httpx
from test_providers import raw_launch,mock_client

def test_second_page_is_ingested(app,monkeypatch):
    calls=[]
    def handler(req):
        calls.append(req)
        page2='offset=100' in str(req.url)
        return httpx.Response(200,json={'results':[raw_launch('second' if page2 else 'first')],'count':2,
            'next':None if page2 else 'https://ll.thespacedevs.com/2.3.0/launches/upcoming/?offset=100'})
    mock_client(monkeypatch,handler)
    result=asyncio.run(app.state.providers.refresh())
    assert len(calls)==2 and len(app.state.store.launches())==2
    assert not result['truncated'] and result['pages']==2

def test_failed_tail_does_not_erase_cached_launch(app,loaded_launch,monkeypatch):
    def handler(req):
        if 'offset=100' in str(req.url):return httpx.Response(503)
        return httpx.Response(200,json={'results':[raw_launch('new')],'count':2,
            'next':'https://ll.thespacedevs.com/2.3.0/launches/upcoming/?offset=100'})
    mock_client(monkeypatch,handler)
    result=asyncio.run(app.state.providers.refresh())
    old=next(l for l in app.state.store.launches() if l['id']==loaded_launch['id'])
    assert result['truncated'] and old['feed_active']

def test_foreign_pagination_url_rejected(app,monkeypatch):
    calls=[]
    def handler(req):
        calls.append(req);return httpx.Response(200,json={'results':[raw_launch()],'next':'https://evil.test/page'})
    mock_client(monkeypatch,handler)
    result=asyncio.run(app.state.providers.refresh())
    assert len(calls)==1 and result['truncated']

def test_persistent_shared_quota(app,monkeypatch):
    app.state.store.set_meta('ll2_requests',[time.time()]*14)
    def handler(req):raise AssertionError('Quota must prevent network call')
    mock_client(monkeypatch,handler)
    assert asyncio.run(app.state.providers.refresh())['error']
