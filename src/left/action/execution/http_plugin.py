"""
HTTP客户端插件

第一性原理：网络是系统与外部世界交互的桥梁
- 请求：向外部服务获取信息或发送指令
- 重试：网络不稳定时自动重试
- 限流：防止对外部服务造成压力
- 超时：防止请求无限挂起

类比：生物的"神经系统"——通过神经信号与外部环境交互
"""

import time
import logging
from typing import Dict, List, Any, Optional, Tuple
from urllib import request, error, parse
import json

from ....platform.support.models.base.plugin import (
    PluginBase, PluginMetadata, PluginResult, PluginType, PluginCapability
)


logger = logging.getLogger(__name__)


class HttpPlugin(PluginBase):
    """
    HTTP客户端插件

    支持：GET、POST、PUT、DELETE，自动重试、超时控制
    """

    def __init__(self) -> None:
        meta = PluginMetadata(
            name="http_plugin",
            version="1.0.0",
            plugin_type=PluginType.HTTP,
            capabilities=[
                PluginCapability.READ,
                PluginCapability.WRITE,
                PluginCapability.CONNECT,
            ],
            description="HTTP请求插件，支持重试和超时",
        )
        super().__init__(meta)
        self.default_timeout: float = 30.0
        self.max_retries: int = 3
        self.retry_delay: float = 1.0
        self.base_headers: Dict[str, str] = {}

    def initialize(self, config: Dict[str, Any]) -> bool:
        """初始化插件"""
        self.default_timeout = config.get("timeout", 30.0)
        self.max_retries = config.get("max_retries", 3)
        self.retry_delay = config.get("retry_delay", 1.0)
        self.base_headers = config.get("headers", {
            "User-Agent": "SelfDrivenAgent/1.0",
            "Accept": "application/json",
        })
        self._initialized = True
        return True

    def health_check(self) -> bool:
        """健康检查"""
        return self._initialized

    def execute(self, action: str, params: Dict[str, Any]) -> PluginResult:
        """执行HTTP请求"""
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
        if action == "get":
            return self._action_get(params)
        if action == "post":
            return self._action_post(params)
        if action == "put":
            return self._action_put(params)
        if action == "delete":
            return self._action_delete(params)
        return PluginResult(success=False, message=f"Unknown action: {action}")

    def _build_url(self, params: Dict[str, Any]) -> str:
        """构建URL"""
        url = params.get("url", "")
        if not url:
            raise ValueError("url is required")
        query = params.get("query", {})
        if query:
            url = url + "?" + parse.urlencode(query)
        return url

    def _build_headers(self, params: Dict[str, Any]) -> Dict[str, str]:
        """构建请求头"""
        headers = dict(self.base_headers)
        headers.update(params.get("headers", {}))
        return headers

    def _build_request(self, url: str, method: str, headers: Dict[str, str], body: Optional[bytes] = None) -> request.Request:
        """构建请求对象"""
        req = request.Request(url, method=method)
        for key, value in headers.items():
            req.add_header(key, value)
        if body:
            req.data = body
        return req

    def _do_request(self, req: request.Request, timeout: float) -> Dict[str, Any]:
        """执行单次请求"""
        with request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            return {
                "status": resp.status,
                "headers": dict(resp.headers),
                "body": body,
            }

    def _parse_json_body(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """尝试解析JSON响应体"""
        try:
            response["json"] = json.loads(response["body"])
        except json.JSONDecodeError:
            response["json"] = None
        return response

    def _request_with_retry(self, req: request.Request, timeout: float) -> Dict[str, Any]:
        """带重试的请求"""
        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = self._do_request(req, timeout)
                return self._parse_json_body(response)
            except error.HTTPError as e:
                last_error = e
                if e.code < 500:
                    raise
            except error.URLError as e:
                last_error = e
            if attempt < self.max_retries - 1:
                time.sleep(self.retry_delay * (attempt + 1))
        raise last_error if last_error else Exception("Request failed")

    def _action_get(self, params: Dict[str, Any]) -> PluginResult:
        """GET请求"""
        url = self._build_url(params)
        headers = self._build_headers(params)
        timeout = params.get("timeout", self.default_timeout)
        req = self._build_request(url, "GET", headers)
        response = self._request_with_retry(req, timeout)
        return PluginResult(
            success=True,
            message=f"GET {url} -> {response['status']}",
            data=response,
        )

    def _encode_body(self, params: Dict[str, Any]) -> bytes:
        """编码请求体"""
        body = params.get("body", {})
        if isinstance(body, dict):
            return json.dumps(body).encode("utf-8")
        return str(body).encode("utf-8")

    def _action_post(self, params: Dict[str, Any]) -> PluginResult:
        """POST请求"""
        return self._send_json_request(params, "POST")

    def _action_put(self, params: Dict[str, Any]) -> PluginResult:
        """PUT请求"""
        return self._send_json_request(params, "PUT")

    def _send_json_request(self, params: Dict[str, Any], method: str) -> PluginResult:
        """发送JSON请求"""
        url, headers, timeout, body = self._prepare_json_request(params)
        req = self._build_request(url, method, headers, body)
        response = self._request_with_retry(req, timeout)
        return self._build_method_result(method, url, response)

    def _prepare_json_request(self, params: Dict[str, Any]) -> Tuple[str, Dict[str, str], float, bytes]:
        """准备JSON请求参数"""
        url = self._build_url(params)
        headers = self._build_headers(params)
        headers["Content-Type"] = "application/json"
        timeout = params.get("timeout", self.default_timeout)
        body = self._encode_body(params)
        return url, headers, timeout, body

    def _build_method_result(self, method: str, url: str, response: Dict[str, Any]) -> PluginResult:
        """构建方法结果"""
        return PluginResult(
            success=True,
            message=f"{method} {url} -> {response['status']}",
            data=response,
        )

    def _action_delete(self, params: Dict[str, Any]) -> PluginResult:
        """DELETE请求"""
        url = self._build_url(params)
        headers = self._build_headers(params)
        timeout = params.get("timeout", self.default_timeout)
        req = self._build_request(url, "DELETE", headers)
        response = self._request_with_retry(req, timeout)
        return PluginResult(
            success=True,
            message=f"DELETE {url} -> {response['status']}",
            data=response,
        )
