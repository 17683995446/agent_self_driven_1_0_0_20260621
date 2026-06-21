"""
LLM插件测试

覆盖：正常值、空入参、边界极值、非法格式
"""

import pytest
from unittest.mock import patch, MagicMock
import json

from src.left.action.execution.llm_plugin import LLMPlugin


class TestLLMPlugin:
    """LLM插件测试类"""

    @pytest.fixture
    def plugin(self):
        p = LLMPlugin()
        p.initialize({"api_url": "https://api.example.com/v1/chat/completions", "api_key": "test-key"})
        return p

    def test_initialize(self):
        """测试初始化"""
        p = LLMPlugin()
        assert p.initialize({"api_url": "https://api.example.com", "api_key": "key"}) is True
        assert p.api_url == "https://api.example.com"

    def test_initialize_no_url(self):
        """测试无URL初始化"""
        p = LLMPlugin()
        assert p.initialize({"api_key": "key"}) is False

    def test_health_check(self, plugin):
        """测试健康检查"""
        assert plugin.health_check() is True

    def test_health_check_no_url(self):
        """测试无URL健康检查"""
        p = LLMPlugin()
        p.initialize({"api_url": ""})
        assert p.health_check() is False

    def test_build_messages_with_prompt(self, plugin):
        """测试带prompt构建消息"""
        messages = plugin._build_messages({"prompt": "Hello"})
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "Hello"

    def test_build_messages_with_messages(self, plugin):
        """测试带messages构建"""
        messages = plugin._build_messages({"messages": [{"role": "user", "content": "Hi"}]})
        assert len(messages) == 2

    def test_build_payload(self, plugin):
        """测试构建请求体"""
        payload = plugin._build_payload({"prompt": "test"})
        assert "model" in payload
        assert "messages" in payload
        assert "max_tokens" in payload

    def test_extract_content(self, plugin):
        """测试提取内容"""
        response = {"choices": [{"message": {"content": "Hello"}}]}
        content = plugin._extract_content(response)
        assert content == "Hello"

    def test_extract_content_empty(self, plugin):
        """测试空内容提取"""
        response = {"choices": []}
        content = plugin._extract_content(response)
        assert content == ""

    @patch("src.left.action.execution.llm_plugin.request.urlopen")
    def test_chat_success(self, mock_urlopen, plugin):
        """测试对话成功"""
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "choices": [{"message": {"content": "Hi there"}}],
            "usage": {"total_tokens": 10},
            "model": "gpt-3.5"
        }).encode()
        mock_urlopen.return_value.__enter__.return_value = mock_resp
        result = plugin.execute("chat", {"prompt": "Hello"})
        assert result.success is True
        assert result.data["content"] == "Hi there"

    @patch("src.left.action.execution.llm_plugin.request.urlopen")
    def test_generate_success(self, mock_urlopen, plugin):
        """测试生成成功"""
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "choices": [{"message": {"content": "Generated text"}}],
            "usage": {},
            "model": ""
        }).encode()
        mock_urlopen.return_value.__enter__.return_value = mock_resp
        result = plugin.execute("generate", {"prompt": "Write a story"})
        assert result.success is True

    @patch("src.left.action.execution.llm_plugin.request.urlopen")
    def test_summarize_success(self, mock_urlopen, plugin):
        """测试总结成功"""
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "choices": [{"message": {"content": "Summary"}}],
            "usage": {},
            "model": ""
        }).encode()
        mock_urlopen.return_value.__enter__.return_value = mock_resp
        result = plugin.execute("summarize", {"text": "Long text here", "max_length": 100})
        assert result.success is True

    @patch("src.left.action.execution.llm_plugin.request.urlopen")
    def test_extract_success(self, mock_urlopen, plugin):
        """测试提取成功"""
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "choices": [{"message": {"content": '{"name": "John", "age": 30}'}}],
            "usage": {},
            "model": ""
        }).encode()
        mock_urlopen.return_value.__enter__.return_value = mock_resp
        result = plugin.execute("extract", {"text": "John is 30", "schema": {"name": "str", "age": "int"}})
        assert result.success is True
        assert result.data["extracted"]["name"] == "John"

    @patch("src.left.action.execution.llm_plugin.request.urlopen")
    def test_extract_invalid_json(self, mock_urlopen, plugin):
        """测试提取非法JSON"""
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "choices": [{"message": {"content": "not json"}}],
            "usage": {},
            "model": ""
        }).encode()
        mock_urlopen.return_value.__enter__.return_value = mock_resp
        result = plugin.execute("extract", {"text": "test", "schema": {}})
        assert result.success is True
        assert result.data["extracted"] is None

    @patch("src.left.action.execution.llm_plugin.request.urlopen")
    def test_reason_success(self, mock_urlopen, plugin):
        """测试推理成功"""
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "choices": [{"message": {"content": "Step 1: ..."}}],
            "usage": {},
            "model": ""
        }).encode()
        mock_urlopen.return_value.__enter__.return_value = mock_resp
        result = plugin.execute("reason", {"problem": "What is 2+2?"})
        assert result.success is True

    def test_unknown_action(self, plugin):
        """测试未知动作"""
        result = plugin.execute("unknown", {})
        assert result.success is False
        assert "Unknown action" in result.message
