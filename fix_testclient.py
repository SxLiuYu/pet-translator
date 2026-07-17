from pathlib import Path

path = Path('tests/test_app_api.py')
text = path.read_text(encoding='utf-8')
old = '''def build_client(app):
    import json as _json
    from httpx import ASGITransport
    import httpx

    transport = ASGITransport(app=app)
    client = httpx.Client(transport=transport, base_url="http://testserver")

    original_request = client.request


    def _json_request(method, url, json_payload=None, **kwargs):
        if json_payload is not None:
            kwargs.setdefault("headers", {})
            if kwargs["headers"] is None:
                kwargs["headers"] = {}
            kwargs["headers"].setdefault("Content-Type", "application/json")
            return original_request(method, url, content=_json.dumps(json_payload), **kwargs)
        return original_request(method, url, **kwargs)


    client.request = _json_request
    client.post = lambda url, json=None, **kwargs: _json_request("POST", url, json_payload=json, **kwargs)
    client.put = lambda url, json=None, **kwargs: _json_request("PUT", url, json_payload=json, **kwargs)
    return client'''
new = '''def build_client(app):
    from httpx import ASGITransport
    import httpx

    transport = ASGITransport(app=app)
    client = httpx.Client(transport=transport, base_url="http://testserver")
    return client'''
if old not in text:
    raise SystemExit('target block not found')
path.write_text(text.replace(old, new), encoding='utf-8')
print('restored simple test client')
