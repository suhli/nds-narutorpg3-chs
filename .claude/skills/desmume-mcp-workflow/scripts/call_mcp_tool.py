import argparse
import json
import urllib.request


def post_jsonrpc(url, payload, timeout):
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "Content-Length": str(len(body))},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def main():
    parser = argparse.ArgumentParser(description="Call one tool on the DeSmuME HTTP MCP server.")
    parser.add_argument("--url", default="http://127.0.0.1:8765/", help="HTTP MCP endpoint")
    parser.add_argument("--tool", required=True, help="MCP tool name, such as nds_get_state")
    parser.add_argument("--arguments", default="{}", help="JSON object passed as tool arguments")
    parser.add_argument("--timeout", type=float, default=10.0, help="Request timeout in seconds")
    args = parser.parse_args()

    tool_args = json.loads(args.arguments)
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": args.tool, "arguments": tool_args},
    }
    print(json.dumps(post_jsonrpc(args.url, payload, args.timeout), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
