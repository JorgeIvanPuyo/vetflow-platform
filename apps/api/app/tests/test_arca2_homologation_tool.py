"""Tool guards only; no live homologation is performed by these tests."""
import json
import uuid

import httpx
import pytest

from app.tools.arca_homologation import run


def _args(sale, emission):
    return ['--sale-id', str(sale), '--emission-id', str(emission)]


def test_live_tool_is_off_without_both_explicit_switches(monkeypatch):
    sale, emission = uuid.uuid4(), uuid.uuid4()
    calls = []
    transport = httpx.MockTransport(lambda request: calls.append(request))
    monkeypatch.delenv('ARCA_HOMOLOGATION_SMOKE_ENABLED', raising=False)
    with pytest.raises(ValueError):
        run(_args(sale, emission), transport=transport)
    monkeypatch.setenv('ARCA_HOMOLOGATION_SMOKE_ENABLED', 'true')
    with pytest.raises(ValueError):
        run(_args(sale, emission) + ['--execute-homologation'], transport=transport)
    assert calls == []


@pytest.mark.parametrize('origin', ['https://remote.invalid', 'http://127.0.0.1@remote.invalid', 'http://localhost/private', 'file:///etc/passwd'])
def test_live_tool_rejects_external_api_origins_before_transport(monkeypatch, origin):
    monkeypatch.setenv('ARCA_HOMOLOGATION_SMOKE_ENABLED', 'true')
    monkeypatch.setenv('ARCA_HOMOLOGATION_API_TOKEN', 'synthetic-token')
    with pytest.raises(ValueError):
        run(_args(uuid.uuid4(), uuid.uuid4()) + ['--execute-homologation', '--confirm-synthetic-data', '--api-origin', origin],
            transport=httpx.MockTransport(lambda request: pytest.fail('Transport must not run')))


@pytest.mark.parametrize('status', ['prepared', 'unknown', 'authorized'])
def test_tool_uses_persisted_identity_and_never_resends_unknown(monkeypatch, status):
    sale, emission = uuid.uuid4(), uuid.uuid4()
    monkeypatch.setenv('ARCA_HOMOLOGATION_SMOKE_ENABLED', 'true')
    monkeypatch.setenv('ARCA_HOMOLOGATION_API_TOKEN', 'synthetic-token')
    calls = []
    operation = {'id': str(emission), 'environment': 'homologation', 'status': status, 'file_status': 'ready',
                 'allowed_actions': {'issue': True, 'reconcile': True}}
    def handle(request):
        calls.append(request)
        if request.url.path.endswith('/file'):
            return httpx.Response(200, content=b'%PDF-synthetic')
        if request.method == 'POST':
            if status == 'unknown':
                assert json.loads(request.read()) == {"retry_same_request": False}
            operation['status'] = 'authorized'
            return httpx.Response(200, json={'data': operation})
        return httpx.Response(200, json={'data': {'operations': [operation]}})
    result = run(_args(sale, emission) + ['--execute-homologation', '--confirm-synthetic-data'],
                 transport=httpx.MockTransport(handle))
    assert result['result'] == 'PASS'
    posts = [request.url.path for request in calls if request.method == 'POST']
    assert posts == ([f'/api/v1/sales/{sale}/fiscal-emissions/{emission}/issue'] if status == 'prepared' else
                     [f'/api/v1/sales/{sale}/fiscal-emissions/{emission}/reconcile'] if status == 'unknown' else [])
