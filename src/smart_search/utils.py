from typing import List
from .providers.base import SearchResult

def format_search_results(results: List[SearchResult]) -> str:
    if not results:
        return "No results found."

    formatted = []
    for i, result in enumerate(results, 1):
        parts = [f"## Result {i}: {result.title}"]

        if result.url:
            parts.append(f"**URL:** {result.url}")

        if result.snippet:
            parts.append(f"**Summary:** {result.snippet}")

        if result.source:
            parts.append(f"**Source:** {result.source}")

        if result.published_date:
            parts.append(f"**Published:** {result.published_date}")

        formatted.append("\n".join(parts))

    return "\n\n---\n\n".join(formatted)

search_prompt = """You are a helpful research assistant. Answer the user's question thoroughly using web search results.

Guidelines:
- Infer the user's true intent even when the question is vague. Consider multiple angles.
- Search broadly first (5+ perspectives), then go deep on the 2-3 most relevant ones.
- Prioritize authoritative sources: official docs, Wikipedia, academic papers, reputable journalism.
- Search in English first for breadth, switch to Chinese when the topic demands it.
- Every factual claim should cite its source. More credible sources strengthen the answer.
- Lead with the most likely answer, then provide supporting analysis.
- Define technical terms in plain language. Use real-world analogies for complex concepts.
- Format output in clean Markdown. Use LaTeX for formulas, code blocks for scripts.
- Be direct and concise. No filler or unnecessary follow-up questions.
"""
