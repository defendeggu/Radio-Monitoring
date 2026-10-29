"""
OpenAPI 3.1 document generated from the routes and pydantic schemas (N11).

Usage in a blueprint:

    @bp.post('/stream-decode')
    @api('Start a streaming session', tags=['Streaming'], body=StreamRequest)
    def start():
        req = parse_body(StreamRequest)

The document is served at /openapi.json; the web UI renders it on its API page.
"""

import re
from typing import Any, Callable, Optional, TypeVar

from flask import Flask, request
from pydantic import BaseModel

from radiomoni.errors import ApiError
from radiomoni.version import __version__

F = TypeVar('F', bound=Callable[..., Any])
M = TypeVar('M', bound=BaseModel)


def api(summary: str, tags: Optional[list[str]] = None, body: Optional[type[BaseModel]] = None,
        query: Optional[type[BaseModel]] = None, description: Optional[str] = None,
        responses: Optional[dict[int, str]] = None, deprecated: bool = False) -> Callable[[F], F]:
    """Attach OpenAPI metadata to a view function."""
    def decorator(fn: F) -> F:
        fn._api_meta = {  # type: ignore[attr-defined]
            'summary': summary,
            'tags': tags or [],
            'body': body,
            'query': query,
            'description': description or (fn.__doc__ or '').strip() or None,
            'responses': responses or {},
            'deprecated': deprecated}
        return fn
    return decorator


def parse_body(model: type[M]) -> M:
    """Validate the JSON body against `model` (raises ApiError/ValidationError)."""
    data = request.get_json(silent=True)
    if data is None:
        if request.data:
            raise ApiError('Invalid JSON body', 400)
        data = {}
    if not isinstance(data, dict):
        raise ApiError('JSON body must be an object', 400)
    return model.model_validate(data)


def parse_query(model: type[M]) -> M:
    """Validate query-string parameters against `model`."""
    return model.model_validate({k: v for k, v in request.args.items()})


_PATH_PARAM = re.compile(r'<(?:(\w+):)?(\w+)>')


def build_openapi(app: Flask) -> dict[str, Any]:
    components: dict[str, Any] = {}
    paths: dict[str, Any] = {}

    def schema_ref(model: type[BaseModel]) -> dict[str, Any]:
        schema = model.model_json_schema(ref_template='#/components/schemas/{model}')
        for name, sub in schema.pop('$defs', {}).items():
            components[name] = sub
        components[model.__name__] = schema
        return {'$ref': f'#/components/schemas/{model.__name__}'}

    for rule in sorted(app.url_map.iter_rules(), key=lambda r: r.rule):
        view = app.view_functions.get(rule.endpoint)
        meta = getattr(view, '_api_meta', None)
        if meta is None:
            continue
        path = _PATH_PARAM.sub(lambda m: '{' + m.group(2) + '}', rule.rule)
        params = [{'name': m.group(2), 'in': 'path', 'required': True,
                   'schema': {'type': 'integer' if m.group(1) == 'int' else 'string'}}
                  for m in _PATH_PARAM.finditer(rule.rule)]
        if meta['query'] is not None:
            qschema = meta['query'].model_json_schema()
            for name, prop in qschema.get('properties', {}).items():
                params.append({'name': name, 'in': 'query', 'required': name in qschema.get('required', []),
                               'schema': prop})
        for method in sorted((rule.methods or set()) - {'HEAD', 'OPTIONS'}):
            op: dict[str, Any] = {
                'summary': meta['summary'], 'tags': meta['tags'], 'operationId': f"{rule.endpoint}_{method.lower()}",
                'responses': {str(code): {'description': text} for code, text in
                              ({200: 'OK', 400: 'Validation error', 401: 'Missing API key',
                                403: 'Invalid API key'} | meta['responses']).items()},
            }
            if meta['description']:
                op['description'] = meta['description']
            if meta['deprecated']:
                op['deprecated'] = True
            if params:
                op['parameters'] = params
            if meta['body'] is not None and method in ('POST', 'PUT', 'PATCH'):
                op['requestBody'] = {'required': True,
                                     'content': {'application/json': {'schema': schema_ref(meta['body'])}}}
            paths.setdefault(path, {})[method.lower()] = op

    return {
        'openapi': '3.1.0',
        'info': {'title': 'RadioMoni API', 'version': __version__,
                 'description': 'REST API of the RadioMoni SDR monitoring system. '
                                'Authenticate with the X-API-Key header.'},
        'servers': [{'url': '/api'}],
        'components': {'schemas': components,
                       'securitySchemes': {'ApiKey': {'type': 'apiKey', 'in': 'header', 'name': 'X-API-Key'}}},
        'security': [{'ApiKey': []}],
        'paths': paths,
    }
