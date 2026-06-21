"""
LLM交互插件

第一性原理：大语言模型是通用推理引擎
- 推理：基于上下文进行逻辑推导
- 生成：根据提示生成文本
- 总结：将长文本压缩为关键信息
- 结构化：从非结构化文本中提取结构化数据

类比：生物的"高级认知皮层"——进行抽象思维、语言理解和创造
"""

import time
import logging
from typing import Dict, List, Any, Optional
from urllib import request, error, parse
import json

from ....platform.support.models.base.plugin import (
    PluginBase, PluginMetadata, PluginResult, PluginType, PluginCapability
)


logger = logging.getLogger(__name__)


class LLMPlugin(PluginBase):
    """
    LLM交互插件

    支持：文本生成、推理、总结、结构化提取
    默认使用OpenAI兼容API格式
    """

    def __init__(self) -> None:
        super().__init__(self._create_metadata())
        self._init_defaults()

    def _create_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="llm_plugin",
            version="1.0.0",
            plugin_type=PluginType.LLM,
            capabilities=[
                PluginCapability.EXECUTE,
                PluginCapability.TRANSFORM,
            ],
            description="大语言模型交互插件",
        )

    def _init_defaults(self) -> None:
        self.api_url: str = ""
        self.api_key: str = ""
        self.model: str = "gpt-3.5-turbo"
        self.timeout: float = 60.0
        self.max_tokens: int = 2048
        self.temperature: float = 0.7

    def initialize(self, config: Dict[str, Any]) -> bool:
        """初始化插件"""
        self._apply_config(config)
        self._initialized = bool(self.api_url)
        return self._initialized

    def _apply_config(self, config: Dict[str, Any]) -> None:
        """应用配置项"""
        self.api_url = config.get("api_url", "")
        self.api_key = config.get("api_key", "")
        self.model = config.get("model", "gpt-3.5-turbo")
        self.timeout = config.get("timeout", 60.0)
        self.max_tokens = config.get("max_tokens", 2048)
        self.temperature = config.get("temperature", 0.7)

    def health_check(self) -> bool:
        """健康检查"""
        return self._initialized and bool(self.api_url)

    def execute(self, action: str, params: Dict[str, Any]) -> PluginResult:
        """执行LLM操作"""
        start = time.time()
        try:
            result = self._dispatch(action, params)
            result.execution_time = time.time() - start
            return result
        except Exception as e:
            return PluginResult(
                success=False,
                message=str(e),
                execution_time=time.time() - start,
            )

    def _dispatch(self, action: str, params: Dict[str, Any]) -> PluginResult:
        """分发到具体动作"""
        if action == "chat":
            return self._action_chat(params)
        if action == "generate":
            return self._action_generate(params)
        if action == "summarize":
            return self._action_summarize(params)
        if action == "extract":
            return self._action_extract(params)
        if action == "reason":
            return self._action_reason(params)
        return PluginResult(success=False, message=f"Unknown action: {action}")

    def _build_headers(self) -> Dict[str, str]:
        """构建请求头"""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        return headers

    def _build_messages(self, params: Dict[str, Any]) -> List[Dict[str, str]]:
        """构建消息列表"""
        system = params.get("system", "You are a helpful assistant.")
        messages = [{"role": "system", "content": system}]
        if "messages" in params:
            messages.extend(params["messages"])
        elif "prompt" in params:
            messages.append({"role": "user", "content": params["prompt"]})
        return messages

    def _build_payload(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """构建请求体"""
        return {
            "model": params.get("model", self.model),
            "messages": self._build_messages(params),
            "max_tokens": params.get("max_tokens", self.max_tokens),
            "temperature": params.get("temperature", self.temperature),
        }

    def _call_api(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """调用LLM API"""
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            self.api_url,
            data=body,
            headers=self._build_headers(),
            method="POST",
        )
        with request.urlopen(req, timeout=self.timeout) as resp:
            response = json.loads(resp.read().decode("utf-8"))
        return response

    def _extract_content(self, response: Dict[str, Any]) -> str:
        """提取生成内容"""
        choices = response.get("choices", [])
        if not choices:
            return ""
        message = choices[0].get("message", {})
        return message.get("content", "")

    def _action_chat(self, params: Dict[str, Any]) -> PluginResult:
        """对话"""
        payload = self._build_payload(params)
        response = self._call_api(payload)
        content = self._extract_content(response)
        return PluginResult(
            success=True,
            message="Chat completed",
            data={
                "content": content,
                "usage": response.get("usage", {}),
                "model": response.get("model", ""),
            },
        )

    def _action_generate(self, params: Dict[str, Any]) -> PluginResult:
        """文本生成"""
        params["system"] = params.get("system", "You are a creative writer.")
        return self._action_chat(params)

    def _action_summarize(self, params: Dict[str, Any]) -> PluginResult:
        """文本总结"""
        text = params.get("text", "")
        max_length = params.get("max_length", 200)
        params["system"] = f"Summarize the following text in {max_length} characters or less."
        params["prompt"] = text
        return self._action_chat(params)

    def _action_extract(self, params: Dict[str, Any]) -> PluginResult:
        """结构化提取"""
        text = params.get("text", "")
        schema = params.get("schema", {})
        params = self._build_extract_prompt(params, text, schema)
        result = self._action_chat(params)
        return self._parse_extracted(result)

    def _build_extract_prompt(self, params: Dict[str, Any], text: str, schema: Dict[str, Any]) -> Dict[str, Any]:
        """构建提取提示"""
        schema_desc = json.dumps(schema, ensure_ascii=False)
        params["system"] = f"Extract structured data from the text according to this schema: {schema_desc}. Return only valid JSON."
        params["prompt"] = text
        return params

    def _parse_extracted(self, result: PluginResult) -> PluginResult:
        """解析提取结果"""
        if not result.success:
            return result
        try:
            extracted = json.loads(result.data["content"])
            result.data["extracted"] = extracted
        except json.JSONDecodeError:
            result.data["extracted"] = None
        return result

    def _action_reason(self, params: Dict[str, Any]) -> PluginResult:
        """推理分析"""
        problem = params.get("problem", "")
        params["system"] = "You are a careful reasoning engine. Think step by step and explain your reasoning clearly."
        params["prompt"] = problem
        return self._action_chat(params)
