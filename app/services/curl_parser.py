# backend/app/services/curl_parser.py
import re
import json
import ast
from urllib.parse import urlparse, parse_qs, unquote_plus

def parse_curl(curl: str):
    method_match = re.search(r"curl -X ['\"]?(\w+)['\"]?", curl)
    method = method_match.group(1).upper() if method_match else "GET"

    url_match = re.search(r"['\"](https?://[^'\"]+)['\"]", curl)
    full_url = url_match.group(1) if url_match else ""

    parsed_url = urlparse(full_url)
    path_parts = parsed_url.path.strip("/").split("/")
    version_prefix = path_parts[0] if path_parts and re.match(r"v\d+", path_parts[0]) else ""
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}" + (f"/{version_prefix}" if version_prefix else "")
    path = "/" + "/".join(path_parts[1:] if version_prefix else path_parts)

    headers = dict(re.findall(r"-H ['\"]([^:]+):\s?([^'\"]+)['\"]", curl))
    auth_required = "Authorization" in headers

    data_match = re.search(r"-d\s+'((?:\\'|[^'])*)'", curl, re.DOTALL)
    raw_body = data_match.group(1).strip() if data_match else None

    if raw_body:
        try:
            raw_body = ast.literal_eval(f"'{raw_body}'")
        except Exception as e:
            print("Failed to unescape raw_body:", e)

    request_body = None
    content_type = headers.get("Content-Type", "")

    if raw_body and content_type == "application/x-www-form-urlencoded":
        parsed = parse_qs(raw_body)
        request_body = {
            "type": "object",
            "properties": {},
            "required": list(parsed.keys())
        }
        for key, value in parsed.items():
            request_body["properties"][key] = {
                "type": "string",
                "title": key.capitalize(),
                "example": unquote_plus(value[0]) if value else ""
            }

    elif raw_body and content_type == "application/json":
        try:
            json_obj = json.loads(raw_body)
            request_body = {
                "type": "object",
                "properties": {},
                "required": list(json_obj.keys())
            }
            for key, value in json_obj.items():
                py_type = type(value).__name__
                json_type = {
                    "str": "string",
                    "int": "integer",
                    "float": "number",
                    "bool": "boolean",
                    "list": "array",
                    "dict": "object"
                }.get(py_type, "string")

                request_body["properties"][key] = {
                    "type": json_type,
                    "title": key.capitalize(),
                    "example": value
                }
        except json.JSONDecodeError as e:
            print("JSON decode error:", e)
            request_body = None

    print("RAW BODY:", raw_body)
    print("REQUEST BODY SCHEMA:", json.dumps(request_body, indent=2) if request_body else "None")

    return {
        "method": method,
        "base_url": base_url,
        "path": path,
        "headers": headers,
        "body": raw_body,
        "requires_auth": auth_required,
        "request_body": json.dumps(request_body) if request_body else None
    }
