#!/usr/bin/env python3
"""
API 客户端封装
支持 OpenAI SDK 和 Anthropic SDK 两种风格
"""

from typing import Iterator, Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class ChatResponse:
    """统一的响应格式"""
    content: str
    tokens: int
    latency_ms: float
    ttft_ms: Optional[float]
    success: bool
    error: Optional[str] = None


@dataclass
class StreamChunk:
    """统一的流式响应块"""
    content: str
    is_first: bool = False
    is_last: bool = False


class APIClient:
    """统一封装的 API 客户端"""

    def __init__(self, api_key: str, base_url: str, style: str = "openai", model: str = ""):
        self.api_key = api_key
        self.base_url = base_url
        self.style = style.lower()
        self.model = model
        self._client = None

        if self.style == "anthropic":
            try:
                from anthropic import Anthropic
                self._client = Anthropic(api_key=api_key, base_url=base_url)
            except ImportError:
                raise ImportError("请先安装 anthropic SDK: pip install anthropic")
        else:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=api_key, base_url=base_url)
            except ImportError:
                raise ImportError("请先安装 openai SDK: pip install openai")

    def chat_stream(self, prompt: str, max_tokens: Optional[int] = None) -> Iterator[StreamChunk]:
        """
        流式对话
        返回统一的 StreamChunk 格式
        """
        if self.style == "anthropic":
            return self._anthropic_stream(prompt, max_tokens)
        else:
            return self._openai_stream(prompt, max_tokens)

    def _openai_stream(self, prompt: str, max_tokens: Optional[int] = None) -> Iterator[StreamChunk]:
        """OpenAI 风格的流式调用"""
        from openai import OpenAI

        messages = [{"role": "user", "content": prompt}]
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.7,
            "stream": True,
        }
        if max_tokens:
            kwargs["max_tokens"] = max_tokens

        response = self._client.chat.completions.create(**kwargs)

        is_first = True
        for chunk in response:
            content = ""
            if chunk.choices and chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content

            yield StreamChunk(
                content=content,
                is_first=is_first,
                is_last=False
            )
            is_first = False

        # 发送结束标记
        yield StreamChunk(content="", is_first=False, is_last=True)

    def _anthropic_stream(self, prompt: str, max_tokens: Optional[int] = None) -> Iterator[StreamChunk]:
        """Anthropic 风格的流式调用"""
        from anthropic import Anthropic

        # Anthropic 必须指定 max_tokens
        if not max_tokens:
            max_tokens = 4096

        response = self._client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=0.7,
            messages=[{"role": "user", "content": prompt}],
            stream=True
        )

        is_first = True
        for chunk in response:
            content = ""
            # Anthropic SDK 流式事件类型: content_block_delta, message_delta, etc.
            if hasattr(chunk, 'type'):
                if chunk.type == 'content_block_delta' and hasattr(chunk, 'delta'):
                    content = getattr(chunk.delta, 'text', '')
                elif chunk.type == 'content_block_start' and hasattr(chunk, 'content_block'):
                    content = getattr(chunk.content_block, 'text', '')
            elif hasattr(chunk, 'delta') and hasattr(chunk.delta, 'text'):
                content = chunk.delta.text

            if content:
                yield StreamChunk(
                    content=content,
                    is_first=is_first,
                    is_last=False
                )
                is_first = False

        # 发送结束标记
        yield StreamChunk(content="", is_first=False, is_last=True)
