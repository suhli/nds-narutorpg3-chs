import argparse
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


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


def start_desmume(exe, rom):
    command = [str(exe), "--mcp"]
    if rom:
        command.append(str(rom))
    kwargs = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if sys.platform.startswith("win"):
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    return subprocess.Popen(command, **kwargs)


def wait_until_ready(url, timeout):
    deadline = time.monotonic() + timeout
    last_error = None
    while time.monotonic() < deadline:
        try:
            return post_jsonrpc(url, {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, timeout=2)
        except Exception as exc:
            last_error = exc
            time.sleep(0.25)
    raise TimeoutError(f"DeSmuME MCP did not respond at {url}: {last_error}")


def main():
    parser = argparse.ArgumentParser(description="List tools exposed by the DeSmuME HTTP MCP server.")
    parser.add_argument("--url", default="http://127.0.0.1:8765/", help="HTTP MCP endpoint")
    parser.add_argument("--start", action="store_true", help="Start tools/desmume.exe --mcp before querying")
    parser.add_argument("--exe", default="tools/desmume.exe", help="Path to desmume.exe")
    parser.add_argument("--rom", default=None, help="Optional ROM path passed to DeSmuME when --start is used")
    parser.add_argument("--timeout", type=float, default=10.0, help="Startup/query timeout in seconds")
    args = parser.parse_args()

    proc = None
    try:
        if args.start:
            exe = Path(args.exe)
            if not exe.exists():
                raise FileNotFoundError(exe)
            proc = start_desmume(exe, args.rom)
            result = wait_until_ready(args.url, args.timeout)
        else:
            result = post_jsonrpc(args.url, {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, args.timeout)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        if proc is not None:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    main()
