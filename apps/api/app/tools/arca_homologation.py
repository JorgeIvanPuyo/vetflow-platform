"""Explicit live homologation smoke tool, never imported or run by pytest.

Uses the authenticated local API and an already prepared, reviewed synthetic
intent. It cannot choose credential resources, create sample customer records,
send production documents, retry issuance, or resend an uncertain request.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from urllib.parse import urlsplit

import httpx


def _arguments(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute-homologation', action='store_true')
    parser.add_argument('--confirm-synthetic-data', action='store_true')
    parser.add_argument('--api-origin', default='http://127.0.0.1:8000')
    parser.add_argument('--sale-id', type=uuid.UUID, required=True)
    parser.add_argument('--emission-id', type=uuid.UUID, required=True)
    return parser.parse_args(argv)


def run(argv=None, *, transport=None):
    args = _arguments(argv)
    # Two independent, explicit switches. Merely provisioning a certificate or
    # enabling normal server homologation cannot launch this tool.
    if not args.execute_homologation or not args.confirm_synthetic_data or os.getenv('ARCA_HOMOLOGATION_SMOKE_ENABLED') != 'true':
        raise ValueError('Prueba externa desactivada: exige ambos flags explícitos y ARCA_HOMOLOGATION_SMOKE_ENABLED=true')
    origin = urlsplit(args.api_origin)
    if origin.scheme not in {'http', 'https'} or origin.hostname not in {'127.0.0.1', 'localhost', '::1'} or origin.username or origin.password or origin.path not in {'', '/'} or origin.query or origin.fragment:
        raise ValueError('La herramienta sólo admite el origen de la API local autenticada')
    token = os.getenv('ARCA_HOMOLOGATION_API_TOKEN', '')
    if not token or any(character.isspace() for character in token):
        raise ValueError('Falta el token de API del actor fiscal; provisionarlo fuera de argumentos y archivos del repositorio')
    path = f'/api/v1/sales/{args.sale_id}/fiscal-emissions'
    with httpx.Client(base_url=args.api_origin, transport=transport or httpx.HTTPTransport(retries=0, trust_env=False),
                      headers={'Authorization': 'Bearer ' + token}, timeout=httpx.Timeout(120, connect=10),
                      follow_redirects=False, verify=True, trust_env=False) as client:
        response = client.get(path)
        response.raise_for_status()
        operations = response.json()['data']['operations']
        operation = next((row for row in operations if row['id'] == str(args.emission_id)), None)
        if operation is None or operation['environment'] != 'homologation':
            raise ValueError('No existe esa intención de homologación para el actor y la venta autenticados')
        status = operation['status']
        if status == 'prepared':
            if not operation['allowed_actions']['issue']:
                raise ValueError('La API informa un bloqueo de emisión; revisar Ajustes y permisos')
            response = client.post(f'{path}/{args.emission_id}/issue', json={'confirm': True})
            response.raise_for_status()
            operation = response.json()['data']
        elif status in {'processing', 'unknown', 'conflict'}:
            if not operation['allowed_actions']['reconcile']:
                raise ValueError('El claim vigente impide conciliar; recuperar después de su vencimiento')
            response = client.post(f'{path}/{args.emission_id}/reconcile', json={'retry_same_request': False})
            response.raise_for_status()
            operation = response.json()['data']
        if operation['status'] != 'authorized':
            return {'result': 'PENDING' if operation['status'] in {'processing', 'unknown', 'conflict'} else 'FAIL',
                    'status': operation['status'], 'environment': 'homologation', 'automatic_resend': False}
        if operation['file_status'] != 'ready':
            return {'result': 'PENDING', 'status': 'authorized_file_pending', 'environment': 'homologation', 'automatic_resend': False}
        response = client.get(f'{path}/{args.emission_id}/file')
        response.raise_for_status()
        if not response.content.startswith(b'%PDF-'):
            raise ValueError('La API no devolvió el PDF autorizado')
        return {'result': 'PASS', 'status': 'authorized', 'environment': 'homologation', 'pdf_bytes': len(response.content), 'automatic_resend': False}


def main():
    try:
        result = run()
    except Exception:
        # HTTP exceptions may contain request metadata. Never echo credentials,
        # response XML, receiver data, or unrestricted exception representations.
        print('FAIL: prueba externa no completada. Consultar el estado durable en la API; no reenviar emisión.', file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0 if result['result'] == 'PASS' else 2


if __name__ == '__main__':
    raise SystemExit(main())
