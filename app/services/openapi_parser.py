# === backend/app/services/openapi_parser.py ===
from typing import Dict, Any
import json
import yaml
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.endpoint import Endpoint
from app.services.ai_service import generate_description

def resolve_ref(ref: str, openapi_spec: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve $ref strings like '#/components/schemas/NoteRequest'"""
    if not ref.startswith("#/"):
        return {}
    
    # Remove the '#/' prefix and split the path
    parts = ref[2:].split("/")
    ref_obj = openapi_spec
    
    for part in parts:
        if isinstance(ref_obj, dict) and part in ref_obj:
            ref_obj = ref_obj[part]
        else:
            print(f"Failed to resolve ref part '{part}' in {ref}")
            return {}
    
    return ref_obj if isinstance(ref_obj, dict) else {}

def extract_schema_properties(schema: Dict[str, Any], openapi_spec: Dict[str, Any]) -> Dict[str, Any]:
    """Extract properties from schema, resolving refs """
    if "$ref" in schema:
        resolved_schema = resolve_ref(schema["$ref"], openapi_spec)
        if resolved_schema:
            schema = resolved_schema

    props = schema.get("properties", {})
    required = schema.get("required", [])
    result = {}
    
    for prop_name, prop_schema in props.items():
        # Handle nested $ref 
        if "$ref" in prop_schema:
            prop_schema = resolve_ref(prop_schema["$ref"], openapi_spec) or prop_schema
        
        result[prop_name] = {
            "type": prop_schema.get("type", "string"),
            "required": prop_name in required,
            "title": prop_schema.get("title", prop_name),
            "format": prop_schema.get("format"),
            "minLength": prop_schema.get("minLength"),
            "maxLength": prop_schema.get("maxLength"),
            "minimum": prop_schema.get("minimum"),
            "maximum": prop_schema.get("maximum"),
            "pattern": prop_schema.get("pattern"),
            "description": prop_schema.get("description")
        }
        # Remove None values
        result[prop_name] = {k: v for k, v in result[prop_name].items() if v is not None}
    
    return result

def parse_openapi_content(content: str) -> Dict[str, Any]:
    """Parse OpenAPI content from either JSON or YAML format"""
    try:
        # Try JSON first
        return json.loads(content)
    except json.JSONDecodeError:
        try:
            # Try YAML if JSON fails
            return yaml.safe_load(content)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid OpenAPI format. Must be valid JSON or YAML. Error: {e}")

async def extract_endpoints(openapi_json: Dict[str, Any], project_id: int, session: AsyncSession):
    """Extract endpoints from OpenAPI specification and save to database"""
    paths = openapi_json.get("paths", {})

    for path, methods in paths.items():
        for method, details in methods.items():
            if method.lower() in ['get', 'post', 'put', 'delete', 'patch', 'head', 'options']:
                # Generate AI summary
                summary = await generate_description(method.upper(), path)

                # Extract request body and parameters
                request_body = {}

                # === 1. Handle requestBody with content ===
                if "requestBody" in details:
                    request_body_info = details["requestBody"]
                    content = request_body_info.get("content", {})
                    
                    for content_type, media_type in content.items():
                        schema = media_type.get("schema", {})
                        fields = extract_schema_properties(schema, openapi_json)
                        
                        request_body = {
                            "content_type": content_type,
                            "required": request_body_info.get("required", False),
                            "fields": fields
                        }
                        break  

                # === 2. Handle query/path parameters ===
                if "parameters" in details:
                    if "fields" not in request_body:
                        request_body["fields"] = {}
                    
                    for param in details["parameters"]:
                        param_in = param.get("in")  # query, path, header, cookie
                        name = param.get("name")
                        schema = param.get("schema", {})
                        param_type = schema.get("type", "string")

                        if name:  
                            request_body["fields"][name] = {
                                "type": param_type,
                                "in": param_in,
                                "required": param.get("required", False),
                                "title": schema.get("title", name),
                                "description": param.get("description"),
                                "format": schema.get("format"),
                                "minimum": schema.get("minimum"),
                                "maximum": schema.get("maximum"),
                                "minLength": schema.get("minLength"),
                                "maxLength": schema.get("maxLength"),
                                "pattern": schema.get("pattern")
                            }
                            # Remove None values
                            request_body["fields"][name] = {
                                k: v for k, v in request_body["fields"][name].items() 
                                if v is not None
                            }

                # Check if requires authentication
                requires_auth = "security" in details and len(details["security"]) > 0

                # Create endpoint object
                endpoint = Endpoint(
                    project_id=project_id,
                    path=path,
                    method=method.upper(),
                    summary=summary,
                    requires_auth=requires_auth,
                    request_body=json.dumps(request_body) if request_body else None
                )
                session.add(endpoint)
