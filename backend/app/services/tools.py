import json
from dataclasses import dataclass

from langsmith import traceable
from pydantic import BaseModel, Field, ValidationError
from supabase import Client

from app.config import get_settings
from app.services.retrieval import search_chunks


class SearchDocumentsArgs(BaseModel):
    query: str = Field(
        min_length=2,
        max_length=500,
        description=(
            "A self-contained search query. Rewrite follow-ups into standalone form, "
            "e.g. 'refund policy for annual plans' rather than 'what about that?'"
        ),
    )


@dataclass
class ToolContext:
    db: Client  # the per-request user-JWT client, so searches run under RLS
    user_id: str


class ToolResult(BaseModel):
    content: str  # text sent back to the model
    sources: list[dict] = []  # {document_id, filename, chunk_index, similarity}, for display
    error: bool = False


def _tool_schema() -> dict:
    parameters = SearchDocumentsArgs.model_json_schema()
    parameters.pop("title", None)
    for prop in parameters.get("properties", {}).values():
        prop.pop("title", None)
    return {
        "type": "function",
        "function": {
            "name": "search_documents",
            "description": (
                "Semantic search over the documents the user has uploaded. Returns the most "
                "relevant passages with filename and chunk number. Use for any question that "
                "might be answered by the user's documents."
            ),
            "parameters": parameters,
        },
    }


TOOL_SCHEMAS = [_tool_schema()]


@traceable(run_type="tool", name="search_documents")
async def search_documents(args: SearchDocumentsArgs, ctx: ToolContext) -> ToolResult:
    settings = get_settings()
    hits = await search_chunks(
        ctx.db,
        args.query,
        top_k=settings.retrieval_top_k,
        min_similarity=settings.retrieval_min_similarity,
    )
    if not hits:
        return ToolResult(
            content=(
                "No passages in the user's documents matched this query "
                f"(minimum similarity {settings.retrieval_min_similarity:.2f}). Do not invent an "
                "answer from the documents; tell the user their documents don't appear to cover this."
            )
        )
    lines = [
        f"Found {len(hits)} passages from the user's documents (most relevant first).",
        "Cite as (filename, chunk N).",
    ]
    for i, hit in enumerate(hits, 1):
        lines.append(
            f"\n[{i}] {hit.filename}, chunk {hit.chunk_index} (similarity {hit.similarity:.2f})\n{hit.content}"
        )
    sources = [
        {
            "document_id": h.document_id,
            "filename": h.filename,
            "chunk_index": h.chunk_index,
            "similarity": h.similarity,
        }
        for h in hits
    ]
    return ToolResult(content="\n".join(lines), sources=sources)


async def execute_tool(name: str, raw_args: str, ctx: ToolContext) -> ToolResult:
    """Run a tool call from the model. Never raises: problems go back to the model as the result."""
    if name != "search_documents":
        return ToolResult(content=f"Unknown tool: {name}", error=True)
    try:
        args = SearchDocumentsArgs.model_validate(json.loads(raw_args or "{}"))
    except (json.JSONDecodeError, ValidationError) as exc:
        short = str(exc).splitlines()[0] if isinstance(exc, json.JSONDecodeError) else exc.errors()[0]["msg"]
        return ToolResult(
            content=f'Invalid arguments: {short}. Call again with {{"query": "..."}}', error=True
        )
    try:
        return await search_documents(args, ctx)
    except Exception as exc:  # e.g. embedding API down
        return ToolResult(content=f"Search failed: {exc}", error=True)
