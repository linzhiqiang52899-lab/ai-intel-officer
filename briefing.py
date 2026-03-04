"""
DeepSeek API integration for generating intelligence briefings.
Uses OpenAI-compatible interface.
"""
from typing import Generator

from openai import OpenAI

from config import DEEPSEEK_API_KEY

_BASE_URL = "https://api.deepseek.com"
_MODEL = "deepseek-chat"

_SYSTEM_PROMPT = """\
你是一位专业情报分析官。根据提供的多个RSS信源文章，生成一份结构清晰、重点突出的情报简报。

输出格式（严格使用Markdown）：
1. **执行摘要**：3-5句话总结当前最重要的信息与趋势
2. **关键情报**：按重要性列出5-10条值得关注的新闻/事件，每条包含标题和简短分析
3. **技术动态**（如有）：技术领域的重要进展
4. **趋势研判**：基于所有信源的综合趋势判断
5. **值得关注**：需要持续跟踪的话题或事件

语言：中文输出（专有名词可保留英文）
风格：专业、简洁、客观，避免冗余
"""


def _client() -> OpenAI:
    return OpenAI(api_key=DEEPSEEK_API_KEY, base_url=_BASE_URL)


def build_user_prompt(articles_data: dict) -> str:
    """Format fetch_all result into a prompt string."""
    results = articles_data.get("results", [])
    if not results:
        return "当前没有任何订阅文章，请先添加RSS订阅源。"

    lines = ["以下是各信源的最新文章，请生成情报简报：\n"]
    for feed in results:
        if not feed.get("success"):
            continue
        name = feed.get("configured_name") or feed.get("feed_title") or feed.get("url", "")
        articles = feed.get("articles", [])[:20]
        if not articles:
            continue
        lines.append(f"\n## 信源：{name}\n")
        for a in articles:
            title = a.get("title", "(no title)")
            summary = (a.get("summary", "") or "")[:200]
            pub = a.get("published", "")
            line = f"- [{pub}] **{title}**"
            if summary:
                line += f"\n  {summary}"
            lines.append(line)

    return "\n".join(lines)


def generate_briefing_stream(articles_data: dict) -> Generator[str, None, None]:
    """Yield SSE-formatted text chunks: 'data: <chunk>\\n\\n'"""
    prompt = build_user_prompt(articles_data)
    client = _client()

    stream = client.chat.completions.create(
        model=_MODEL,
        max_tokens=4096,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        stream=True,
    )

    for chunk in stream:
        text = chunk.choices[0].delta.content
        if text:
            escaped = text.replace("\n", "\\n")
            yield f"data: {escaped}\n\n"

    yield "data: [DONE]\n\n"


def generate_briefing_sync(articles_data: dict) -> str:
    """Non-streaming version for background scheduler tasks."""
    prompt = build_user_prompt(articles_data)
    client = _client()

    response = client.chat.completions.create(
        model=_MODEL,
        max_tokens=4096,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    )
    return response.choices[0].message.content
