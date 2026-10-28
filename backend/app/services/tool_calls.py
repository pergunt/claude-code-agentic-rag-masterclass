from dataclasses import dataclass, field


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: str  # raw JSON string, parsed and validated by the tool executor


@dataclass
class _Partial:
    id: str = ""
    name: str = ""
    arguments: list[str] = field(default_factory=list)


class ToolCallAccumulator:
    """Rebuild tool calls from streamed Chat Completions deltas (pure, no I/O).

    Providers differ: some stream the arguments piecemeal, some send a whole call in one chunk,
    and some omit `index` or `id`. Calls are keyed by `index`.
    """

    def __init__(self) -> None:
        self._calls: dict[int, _Partial] = {}
        self._last_index = 0

    def add(self, deltas: list | None) -> None:
        for delta in deltas or []:
            index = delta.index if delta.index is not None else self._last_index
            self._last_index = index
            call = self._calls.setdefault(index, _Partial())
            if delta.id and not call.id:
                call.id = delta.id
            if delta.function:
                if delta.function.name and not call.name:
                    call.name = delta.function.name
                if delta.function.arguments:
                    call.arguments.append(delta.function.arguments)

    def calls(self) -> list[ToolCall]:
        return [
            ToolCall(id=c.id or f"call_{i}", name=c.name, arguments="".join(c.arguments))
            for i, c in sorted(self._calls.items())
        ]

    def __bool__(self) -> bool:
        return bool(self._calls)
