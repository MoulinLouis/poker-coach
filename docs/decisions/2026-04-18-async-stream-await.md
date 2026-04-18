# Async SDK stream final-message methods must be `await`ed

## Context

Both provider SDKs expose a `.get_final_*()` method on their streaming objects to retrieve the accumulated response after iteration:

- Anthropic: `stream.get_final_message()`
- OpenAI Responses: `stream.get_final_response()`

The **sync** client's version is a regular method. The **async** client's version is a **coroutine**. Both look identical at the call site.

Calling it without `await` from the async client returns a coroutine object. `getattr(coroutine, "content", [])` silently defaults to `[]`, `_find_tool_use` finds nothing, and every call fails with:

> `OracleError(kind="invalid_schema", message="no tool_use block in response")`

This persisted across multiple fixes (system prompts, thinking modes, tool_choice variants) because the oracle literally never saw the real response.

## Decision

Always `await` the final-message getter when using the async client:

```python
message = await stream.get_final_message()      # Anthropic
response = await stream.get_final_response()    # OpenAI
```

Test fixtures (`FakeStream.get_final_message`, `FakeStream.get_final_response`) must be `async def` so the `await` path is exercised. Sync fakes mask this bug completely.

## Rationale

This is the single most expensive bug of the project's development so far. It survived every layer of unit testing because the fakes had the wrong shape. Making fakes mirror the real SDK's async-ness is the structural fix.

## Canary

- Repeated `invalid_schema: no tool_use block in response` errors with every model and config → this bug has returned.
- `inspect.iscoroutinefunction(AsyncMessageStream.get_final_message)` should return `True`. If a future SDK version changes this, the oracle code should be re-checked.
- Any new SDK integration must verify whether its accessors are coroutines on the async path before copying the pattern.

## Implementing commits

- `fe5ab4f` — await the async get_final_message / get_final_response
