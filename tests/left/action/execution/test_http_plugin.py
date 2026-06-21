"""
HTTP插件测试

覆盖：正常值、空入参、边界极值、非法格式
"""

import pytest
from unittest.mock import patch, MagicMock
from urllib import error

from src.left.action.execution.http_plugin import HttpPlugin


class TestHttpPlugin:
    """HTTP插件测试类"""

    @pytest.fixture
    def plugin(self):
        p = HttpPlugin()
        p.initialize({})
        return p

    def test_initialize(self):
        """测试初始化"""
        p = HttpPlugin()
        assert p.initialize({"timeout": 10.0, "max_retries": 5}) is True
        assert p.default_timeout == 10.0
        assert p.max_retries == 5

    def test_initialize_default(self):
        """测试默认初始化"""
        p = HttpPlugin()
        assert p.initialize({}) is True
        assert p.default_timeout == 30.0
        assert p.max_retries == 3

    def test_health_check(self, plugin):
        """测试健康检查"""
        assert plugin.health_check() is True

    def test_build_url(self, plugin):
        """测试URL构建"""
        url = plugin._build_url({"url": "https://example.com", "query": {"a": "1"}})
        assert url == "https://example.com?a=1"

    def test_build_url_no_query(self, plugin):
        """测试无查询参数"""
        url = plugin._build_url({"url": "https://example.com"})
        assert url == "https://example.com"

    def test_build_url_empty(self, plugin):
        """测试空URL"""
        with pytest.raises(ValueError):
            plugin._build_url({"url": ""})

    def test_build_headers(self, plugin):
        """测试请求头构建"""
        headers = plugin._build_headers({"headers": {"X-Custom": "value"}})
        assert headers["X-Custom"] == "value"
        assert "User-Agent" in headers

    def test_encode_body(self, plugin):
        """测试请求体编码"""
        body = plugin._encode_body({"body": {"key": "value"}})
        assert b"key" in body

    def test_encode_body_string(self, plugin):
        """测试字符串请求体"""
        body = plugin._encode_body({"body": "plain text"})
        assert body == b"plain text"

    @patch("src.left.action.execution.http_plugin.request.urlopen")
    def test_get_success(self, mock_urlopen, plugin):
        """测试GET成功"""
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b'{"data": "test"}'
        mock_resp.headers = {}
        mock_urlopen.return_value.__enter__.return_value = mock_resp
        result = plugin.execute("get", {"url": "https://example.com"})
        assert result.success is True
        assert result.data["status"] == 200

    @patch("src.left.action.execution.http_plugin.request.urlopen")
    def test_post_success(self, mock_urlopen, plugin):
        """测试POST成功"""
        mock_resp = MagicMock()
        mock_resp.status = 201
        mock_resp.read.return_value = b'{"id": 1}'
        mock_resp.headers = {}
        mock_urlopen.return_value.__enter__.return_value = mock_resp
        result = plugin.execute("post", {"url": "https://example.com", "body": {"name": "test"}})
        assert result.success is True
        assert result.data["status"] == 201

    @patch("src.left.action.execution.http_plugin.request.urlopen")
    def test_put_success(self, mock_urlopen, plugin):
        """测试PUT成功"""
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b'{}'
        mock_resp.headers = {}
        mock_urlopen.return_value.__enter__.return_value = mock_resp
        result = plugin.execute("put", {"url": "https://example.com", "body": {"update": True}})
        assert result.success is True

    @patch("src.left.action.execution.http_plugin.request.urlopen")
    def test_delete_success(self, mock_urlopen, plugin):
        """测试DELETE成功"""
        mock_resp = MagicMock()
        mock_resp.status = 204
        mock_resp.read.return_value = b''
        mock_resp.headers = {}
        mock_urlopen.return_value.__enter__.return_value = mock_resp
        result = plugin.execute("delete", {"url": "https://example.com/1"})
        assert result.success is True

    @patch("src.left.action.execution.http_plugin.request.urlopen")
    def test_retry_on_500(self, mock_urlopen, plugin):
        """测试500错误重试"""
        mock_urlopen.side_effect = [
            error.HTTPError("", 500, "Error", {}, None),
            error.HTTPError("", 500, "Error", {}, None),
            error.HTTPError("", 500, "Error", {}, None),
        ]
        result = plugin.execute("get", {"url": "https://example.com"})
        assert result.success is False
        assert mock_urlopen.call_count == 3

    @patch("src.left.action.execution.http_plugin.request.urlopen")
    def test_no_retry_on_400(self, mock_urlopen, plugin):
        """测试400错误不重试"""
        mock_urlopen.side_effect = error.HTTPError("", 400, "Bad Request", {}, None)
        result = plugin.execute("get", {"url": "https://example.com"})
        assert result.success is False
        assert mock_urlopen.call_count == 1

    def test_unknown_action(self, plugin):
        """测试未知动作"""
        result = plugin.execute("unknown", {})
        assert result.success is False
        assert "Unknown action" in result.message

    def test_parse_json_body(self, plugin):
        """测试JSON解析"""
        response = {"body": '{"key": "value"}'}
        result = plugin._parse_json_body(response)
        assert result["json"]["key"] == "value"

    def test_parse_json_body_invalid(self, plugin):
        """测试非法JSON解析"""
        response = {"body": "not json"}
        result = plugin._parse_json_body(response)
        assert result["json"] is None
