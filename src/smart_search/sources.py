import re
import uuid
from collections import OrderedDict
from typing import Any

import asyncio

from .config import config


_THINK_BLOCK_PATTERN = re.compile(r"<think>[\s\S]*?</think>", re.IGNORECASE)

_LEADING_POLICY_PATTERNS = [
    re.compile(r"^I\s+cannot\s+(comply|assist|help|provide|fulfill)", re.IGNORECASE),
    re.compile(r"^I\s+(can't|won't|will\s+not|am\s+unable\s+to)\s+(comply|assist|help|provide|fulfill)", re.IGNORECASE),
    re.compile(r"^I('m|\s+am)\s+not\s+able\s+to", re.IGNORECASE),
    re.compile(r"^(Sorry|Apologies|I\s+apologize),?\s+(but\s+)?I\s+(cannot|can't|won't)", re.IGNORECASE),
    re.compile(r"^As\s+an?\s+AI(\s+language\s+model)?", re.IGNORECASE),
    re.compile(r"^我(无法|不能|没有办法)(遵从|遵守|协助|帮助|提供|满足)", re.IGNORECASE),
    re.compile(r"^(抱歉|对不起|很遗憾)[，,]?\s*我(无法|不能)", re.IGNORECASE),
]

_POLICY_META_KEYWORDS = {
    "policy", "policies", "guideline", "guidelines", "content policy",
    "usage policy", "terms of service", "acceptable use",
    "策略", "政策", "准则", "使用条款", "服务条款",
}

_POLICY_CONTEXT_KEYWORDS = {
    "prompt injection", "jailbreak", "system prompt", "hidden instruction",
    "bypass", "override", "ignore previous",
    "提示注入", "越狱", "系统提示", "隐藏指令",
}


def _normalize_policy_text(text: str) -> str:
    text = re.sub(r"[*_`#~\[\](){}]", "", text)
    return text.lower().strip()


def _split_paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def _looks_like_policy_block(text: str) -> bool:
    normalized = _normalize_policy_text(text)
    if not normalized:
        return False

    for pattern in _LEADING_POLICY_PATTERNS:
        if pattern.search(normalized):
            return True

    meta_count = sum(1 for kw in _POLICY_META_KEYWORDS if kw in normalized)
    ctx_count = sum(1 for kw in _POLICY_CONTEXT_KEYWORDS if kw in normalized)
    if meta_count >= 2 or ctx_count >= 2 or (meta_count >= 1 and ctx_count >= 1):
        return True

    return False


def sanitize_answer_text(text: str) -> str:
    text = _THINK_BLOCK_PATTERN.sub("", text or "").strip()
    if not text:
        return ""

    paragraphs = _split_paragraphs(text)
    cleaned: list[str] = []
    leading = True
    for para in paragraphs:
        if leading and _looks_like_policy_block(para):
            continue
        leading = False
        cleaned.append(para)

    return "\n\n".join(cleaned).strip()


def new_session_id() -> str:
    return uuid.uuid4().hex[:12]


class SourcesCache:
    def __init__(self, max_size: int = 256):
        self._max_size = max_size
        self._lock = asyncio.Lock()
        self._cache: OrderedDict[str, list[dict]] = OrderedDict()

    async def set(self, session_id: str, sources: list[dict]) -> None:
        async with self._lock:
            self._cache[session_id] = sources
            self._cache.move_to_end(session_id)
            while len(self._cache) > self._max_size:
                self._cache.popitem(last=False)

    async def get(self, session_id: str) -> list[dict] | None:
        async with self._lock:
            sources = self._cache.get(session_id)
            if sources is None:
                return None
            self._cache.move_to_end(session_id)
            return sources


def merge_sources(*source_lists: list[dict]) -> list[dict]:
    seen: set[str] = set()
    merged: list[dict] = []
    for sources in source_lists:
        for item in sources or []:
            url = (item or {}).get("url")
            if not isinstance(url, str) or not url.strip():
                continue
            url = url.strip()
            if url in seen:
                continue
            seen.add(url)
            merged.append(item)
    return merged
