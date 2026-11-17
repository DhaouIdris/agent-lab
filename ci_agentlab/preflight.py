"""Two actual inference calls when explicitly run; no Azure resource creation."""
import json
from .contracts import tool_specs
from .tools import Engine
from .providers import ProviderError

def check_endpoint(client):
    engine=Engine()
    tools=[t for t in tool_specs() if t["function"]["name"]=="get_entity_details"]
    messages=[{"role":"system","content":"This is a protocol test. Use the provided tool. After the tool result return only JSON with keys ok (true), entity_id and name taken from tool data. Do not add other claims."},
              {"role":"user","content":"Read entity P1 with get_entity_details."}]
    first=client.chat(messages,tools_override=tools,tool_choice={"type":"function","function":{"name":"get_entity_details"}})
    calls=first.get("tool_calls") or []
    if len(calls)!=1:raise ProviderError("Preflight: expected exactly one function call")
    c=calls[0]
    try:
        if c["function"]["name"]!="get_entity_details" or json.loads(c["function"]["arguments"])!={"entity_id":"P1"}:
            raise ProviderError("Preflight: wrong tool or arguments")
        cid=c["id"]
    except (KeyError,TypeError,ValueError):raise ProviderError("Preflight: invalid tool call structure") from None
    result=engine.call("get_entity_details",{"entity_id":"P1"})
    messages.extend([{"role":"assistant","content":first.get("content"),"tool_calls":calls},
                     {"role":"tool","tool_call_id":cid,"content":json.dumps(result,ensure_ascii=False)}])
    second=client.chat(messages,tools_override=tools,tool_choice="none",response_format={"type":"json_object"})
    try:data=json.loads(second.get("content") or "")
    except (TypeError,ValueError):raise ProviderError("Preflight: final response is not JSON") from None
    if not isinstance(data,dict) or data.get("ok") is not True or data.get("entity_id")!="P1" or data.get("name")!="Nuit de Saïgon":
        raise ProviderError("Preflight: JSON does not faithfully reflect the tool result")
    return {"passed":True,"checks":["authentication_and_endpoint","forced_function_call","exact_arguments", "tool_result_roundtrip","json_object_output"],
            "provider_calls":client.calls,"cost":client.cost(),
            "limitation":"Protocol smoke test only. Does not prove all 9 tools, strict JSON Schema decoding or agent robustness."}
