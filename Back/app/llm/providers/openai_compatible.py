import json
from urllib.parse import urlsplit

import httpx

from app.llm.errors import ModelError
from app.llm.observability import record_response


def complete(config, secret, system_message, user_message):
    base = config["base_url"].rstrip("/")
    parsed = urlsplit(base)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ModelError("PROVIDER_REJECTED", "模型服务地址配置无效")
    payload = {
        "model": config["model_name"], "stream": False,
        "messages": [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message},
        ],
        "response_format": {"type": "json_object"},
    }
    try:
        # An administrator supplies the endpoint. Never follow a redirect carrying the token.
        with httpx.Client(timeout=config["request_timeout_sec"], follow_redirects=False, trust_env=False) as client:
            with client.stream("POST", base + "/chat/completions", json=payload,
                               headers={"Authorization": "Bearer " + secret, "Accept": "application/json"}) as response:
                if response.status_code == 429 or response.status_code >= 500:
                    raise ModelError("PROVIDER_UNAVAILABLE", "文本模型暂时不可用，请稍后重试", retryable=True)
                if not 200 <= response.status_code < 300:
                    raise ModelError("PROVIDER_REJECTED", "文本模型拒绝了请求，请管理员检查配置或额度")
                raw = bytearray()
                for chunk in response.iter_bytes():
                    raw.extend(chunk)
                    if len(raw) > 4 * 1024 * 1024:
                        raise ModelError("AI_OUTPUT_INVALID", "模型响应超过允许大小")
        result = json.loads(raw)
        choice = result["choices"][0]
        if choice.get("finish_reason") not in (None, "stop"):
            raise ModelError("AI_OUTPUT_INVALID", "模型输出未完整结束")
        content = choice["message"]["content"]
        if not isinstance(content, str):
            raise ModelError("AI_OUTPUT_INVALID", "模型未返回文本 JSON")
        record_response(result.get("id"), result.get("usage"), content)
        return content
    except (httpx.TimeoutException, httpx.NetworkError):
        raise ModelError("PROVIDER_UNAVAILABLE", "文本模型连接超时或网络暂不可用", retryable=True) from None
    except (ValueError, KeyError, IndexError, TypeError):
        raise ModelError("AI_OUTPUT_INVALID", "模型响应无法解析") from None

