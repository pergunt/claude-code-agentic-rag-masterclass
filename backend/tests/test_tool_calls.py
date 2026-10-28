import json
from types import SimpleNamespace

from openai.types.chat.chat_completion_chunk import ChoiceDeltaToolCall, ChoiceDeltaToolCallFunction

from app.services.tool_calls import ToolCallAccumulator


def delta(index=0, id=None, name=None, arguments=None) -> ChoiceDeltaToolCall:
    return ChoiceDeltaToolCall(
        index=index, id=id, function=ChoiceDeltaToolCallFunction(name=name, arguments=arguments)
    )


def test_arguments_split_across_chunks():
    acc = ToolCallAccumulator()
    acc.add([delta(id="c1", name="search_documents", arguments='{"qu')])
    for frag in ('ery": "re', "fund po", 'licy"}'):
        acc.add([delta(arguments=frag)])
    (call,) = acc.calls()
    assert call.name == "search_documents"
    assert json.loads(call.arguments) == {"query": "refund policy"}


def test_interleaved_parallel_calls():
    acc = ToolCallAccumulator()
    acc.add([delta(0, "a", "search_documents", '{"query":'), delta(1, "b", "search_documents", '{"query":')])
    acc.add([delta(1, arguments='"two"}')])
    acc.add([delta(0, arguments='"one"}')])
    first, second = acc.calls()
    assert (first.id, json.loads(first.arguments)) == ("a", {"query": "one"})
    assert (second.id, json.loads(second.arguments)) == ("b", {"query": "two"})


def test_complete_call_in_one_chunk():
    acc = ToolCallAccumulator()
    acc.add([delta(0, "x", "search_documents", '{"query": "hi there"}')])
    (call,) = acc.calls()
    assert call.id == "x"
    assert json.loads(call.arguments) == {"query": "hi there"}


def test_id_and_name_only_on_first_chunk():
    acc = ToolCallAccumulator()
    acc.add([delta(0, "x", "search_documents", "{")])
    acc.add([delta(0, None, None, "}")])
    (call,) = acc.calls()
    assert (call.id, call.name, call.arguments) == ("x", "search_documents", "{}")


def test_missing_id_is_synthesized():
    acc = ToolCallAccumulator()
    acc.add([delta(0, None, "search_documents", "{}")])
    assert acc.calls()[0].id == "call_0"


def test_missing_index_continues_last_call():
    acc = ToolCallAccumulator()
    acc.add([delta(1, "b", "search_documents", "{")])
    # Some providers omit `index`; the OpenAI model requires it, so use a plain namespace.
    acc.add([SimpleNamespace(index=None, id=None, function=SimpleNamespace(name=None, arguments="}"))])
    (call,) = acc.calls()
    assert call.arguments == "{}"


def test_none_is_falsy():
    acc = ToolCallAccumulator()
    acc.add(None)
    assert not acc
    assert acc.calls() == []
