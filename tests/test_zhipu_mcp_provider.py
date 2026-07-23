import json

import httpx
import pytest

from smart_search.providers.zhipu_mcp import ZhipuMCPProvider, _content_error


class FakeZReadClient:
    calls = []
    response: httpx.Response | None = None

    def __init__(self, timeout, follow_redirects=True):
        self.timeout = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def post(self, url, headers, json):
        self.__class__.calls.append({"url": url, "headers": headers, "json": json})
        if self.__class__.response is not None:
            return self.__class__.response
        request = httpx.Request("POST", url)
        if json["method"] == "initialize":
            return httpx.Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "id": json["id"],
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "serverInfo": {"name": "zread-server", "version": "0.0.1"},
                        "capabilities": {},
                    },
                },
                headers={"mcp-session-id": "session-123", "content-type": "application/json"},
                request=request,
            )
        if json["method"] == "notifications/initialized":
            return httpx.Response(200, json={}, request=request)
        return httpx.Response(
            200,
            json={"jsonrpc": "2.0", "id": json["id"], "result": {"content": [{"type": "text", "text": "### Result\nhttps://example.com"}]}},
            request=request,
        )


@pytest.fixture(autouse=True)
def reset_client(monkeypatch):
    FakeZReadClient.calls = []
    FakeZReadClient.response = None
    monkeypatch.setattr("smart_search.providers.zhipu_mcp.httpx.AsyncClient", FakeZReadClient)


@pytest.mark.asyncio
async def test_zread_tools_use_current_mcp_schema():
    provider = ZhipuMCPProvider("https://open.bigmodel.cn/api/mcp/zread/mcp", "secret", provider_id="zhipu-mcp-zread")
    await provider.search_doc("owner/repo", "安装", language="zh")
    await provider.get_repo_structure("owner/repo", path="src")
    await provider.read_file("owner/repo", "README.md")

    calls = FakeZReadClient.calls
    assert [call["json"]["method"] for call in calls] == [
        "initialize",
        "notifications/initialized",
        "tools/call",
        "initialize",
        "notifications/initialized",
        "tools/call",
        "initialize",
        "notifications/initialized",
        "tools/call",
    ]
    tool_calls = [call for call in calls if call["json"]["method"] == "tools/call"]
    assert [call["json"]["params"]["name"] for call in tool_calls] == ["search_doc", "get_repo_structure", "read_file"]
    assert tool_calls[0]["json"]["params"]["arguments"] == {"repo_name": "owner/repo", "query": "安装", "language": "zh"}
    assert tool_calls[1]["json"]["params"]["arguments"] == {"repo_name": "owner/repo", "dir_path": "src"}
    assert tool_calls[2]["json"]["params"]["arguments"] == {"repo_name": "owner/repo", "file_path": "README.md"}
    assert all(call["headers"]["Mcp-Session-Id"] == "session-123" for call in tool_calls)
    assert all(call["headers"]["MCP-Protocol-Version"] == "2024-11-05" for call in tool_calls)


@pytest.mark.asyncio
async def test_zread_redacts_token_from_http_error():
    FakeZReadClient.response = httpx.Response(401, text="secret invalid", request=httpx.Request("POST", "https://open.bigmodel.cn/api/mcp/zread/mcp"))
    provider = ZhipuMCPProvider("https://open.bigmodel.cn/api/mcp/zread/mcp", "secret", provider_id="zhipu-mcp-zread")
    data = json.loads(await provider.read_file("owner/repo", "README.md"))
    assert data["error_type"] == "auth_error"
    assert "secret" not in data["error"]


def test_zread_classifies_mcp_rate_limit_content():
    message = 'MCP error -429: {"error":{"code":"1302","message":"您的账户已达到速率限制"}}'

    assert _content_error(message) == ("rate_limited", message)


def test_zread_classifies_jsonrpc_rate_limit_error():
    provider = ZhipuMCPProvider(
        "https://open.bigmodel.cn/api/mcp/zread/mcp",
        "secret",
        provider_id="zhipu-mcp-zread",
    )

    output = provider._normalize_response(
        "get_repo_structure",
        {"repo_name": "owner/repo"},
        {"jsonrpc": "2.0", "id": 2, "error": {"code": -429, "message": "Too many requests"}},
        0,
    )

    assert output["error_type"] == "rate_limited"
