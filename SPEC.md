# SPEC — Agentic Workflow Builder (MVP)

A visual drag-and-drop builder for LLM agent workflows. Workflows persist as JSON, execute step-by-step async, each step is an `llm_call` or `tool_call`, step outputs cached by input hash.

## 1. Endpoint contract

```python
class LLMCallConfig(BaseModel):
    system: str; prompt: str; model: str = "claude-sonnet-4-6"
    max_tokens: int = 2048
class ToolCallConfig(BaseModel):
    tool_name: str; args: dict[str, str]  # values may contain {{...}} templates
class Step(BaseModel):
    id: str; type: Literal["llm_call", "tool_call"]
    config: LLMCallConfig | ToolCallConfig
    depends_on: list[str]; timeout_seconds: int = 120
class Workflow(BaseModel):
    id: UUID; name: str; steps: list[Step]
class LLMCallOutput(BaseModel):
    result: str; reasoning: str; tokens_used: int
class ToolCallOutput(BaseModel):
    result: str
StepOutput = LLMCallOutput | ToolCallOutput
class RunRequest(BaseModel):
    workflow_id: UUID; inputs: dict[str, str]
class RunStatus(BaseModel):
    run_id: UUID; status: Literal["pending","running","done","failed"]
    outputs: dict[str, StepOutput]; error: str | None
```

- `POST /workflows` → `Workflow`, 201 / 400 (cycle, duplicate id, missing `depends_on` target, unknown `tool_name`, empty workflow)
- `GET /workflows/{id}` → 200/404
- `POST /runs` body `RunRequest` → `{run_id}`, 202
- `GET /runs/{run_id}` → `RunStatus`, 200/404. `outputs` populated per completed step.

## 2. LLM contract

- Model: `claude-sonnet-4-6` (per step, overridable via `LLMCallConfig.model`).
- Structured output per `llm_call`: `LLMCallOutput` above.
- Prompt strategy: `system` and `prompt` from config, `{{var}}` substitution. Namespaces: `{{inputs.<key>}}` and `{{steps.<step_id>.result}}`. Missing or unresolved variable → run fails at start, before any step executes.

## 3. Prompt injection defense

User inputs and upstream step outputs are interpolated inside `<user_data>...</user_data>` XML tags; system prompt instructs the model to treat tag contents as data, never instructions. `tool_call` steps run only against a server-side tool registry (allowlist); each registered tool declares a Pydantic schema for its args, and rendered template args are validated against that schema before execution. Validation failure → step fails, run fails.

## 4. Testing strategy

- Engine unit tests: fake `LLMClient` + `ToolRegistry` injected via constructor; assert topological order, cycle rejection, cache hit/miss, timeout → `failed`, template resolution + missing-var failure.
- API integration tests: FastAPI + `httpx.AsyncClient` + testcontainers Postgres (session-scoped, per-test transaction rollback) + fakeredis; full `POST /workflows` → `POST /runs` → poll → `done`.
- One real-API smoke test in `tests/integration/` marked `@pytest.mark.live`, skipped by default.

## 5. Out of scope (V2)

- Auth / multi-tenancy / API keys
- Webhooks, streaming responses, SSE
- Conditional branches, loops, parallel fan-out (DAG is sequential-per-dependency only)
- Tool sandboxing beyond schema validation, SSRF protection, secret scanning
- Idempotency keys, run retries, run cancellation, dead-letter queue
- Workflow versioning, diff, rollback
- Eval suite, prompt regression tests, cost tracking dashboard
- Model router, fallback chains, rate limiting
- Observability (OTel, Sentry), structured request logging
- Admin endpoints, workflow sharing, export/import UI
- Workflow templates, node library marketplace

---

SPEC.md ready. Hand to llm-feature-architect or implement directly.
