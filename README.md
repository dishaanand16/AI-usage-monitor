# AI Usage Monitoring — FLYYY.AI Take-Home

A small, working system that observes real AI activity — sanitized prompt capture, PII detection, and agent-level "declared vs. actually observed" data access tracking — and surfaces it as governance insight in a live dashboard.

## Problem understanding

Organizations increasingly deploy AI applications and agents without reliable visibility into what those systems actually do: what sensitive information users type into prompts, and whether an agent's real behavior (which tools/data sources it touches) matches what it was declared to use. This project builds a small but genuinely working monitoring layer that captures AI activity safely (redacting PII before anything is stored), and independently verifies an agent's actual data access against its declared configuration — flagging the gap when one exists.

## Architecture

![Architecture diagram](docs/architecture.png)

Two parallel pipelines converge on a shared PostgreSQL store:

- **Prompt capture lane**: a raw prompt hits `POST /prompts` → is passed through a Presidio-based PII sanitizer → only the *redacted* text and PII detection counts are persisted. Raw text is never written to disk.
- **Agent execution lane**: a user query is handed to a LangGraph agent backed by a real LLM (Groq, `openai/gpt-oss-20b`). The LLM decides which of two tools to call (FAQ Database, Orders Database). A LangChain callback (`ToolAccessLogger`) independently records every tool invocation as it happens — this callback, not the agent's own final answer, is the source of truth for what was actually accessed.

Both lanes write to Postgres. A FastAPI layer exposes read endpoints (`/prompts`, `/runs`, `/prompts/pii-summary`) that a React dashboard consumes to show three views: the sanitized prompt log, agent runs with declared-vs-observed access (with unexpected access flagged), and aggregate PII statistics per AI asset.

## Setup

**Prerequisites**: Docker, Python 3.11+, Node.js 18+.

1. Start Postgres:
docker run --name flyyy-postgres -e POSTGRES_PASSWORD=postgres -e 
POSTGRES_DB=flyyy_ai -p 5432:5432 -d postgres:16

2. Apply the schema:
docker exec -i flyyy-postgres psql -U postgres -d flyyy_ai < backend/migrations/001_init.sql

3. Backend:
cd backend
python -m venv venv
venv\Scripts\activate # or source venv/bin/activate on Mac/Linux
pip install -r requirements.txt
python -m spacy download en_core_web_lg

4. Copy `.env.example` to `.env` in the project root and fill in `DATABASE_URL` and `GROQ_API_KEY` (a free key from console.groq.com).
5. Seed one AI asset (the agent needs a row to reference):

docker exec -it flyyy-postgres psql -U postgres -d flyyy_ai -c "INSERT INTO ai_assets (name, description, declared_data_sources) VALUES ('Customer Support Agent', 'Support agent handling order and FAQ queries', ARRAY['FAQ Database']);"

6. Run the backend: `venv\Scripts\python -m uvicorn app.main:app --reload` (from `backend/`)
7. Run the frontend: `npm install && npm run dev` (from `frontend/`)
8. Visit the printed frontend URL (typically `http://localhost:5173`).

## PII protection approach

**Library**: [Microsoft Presidio](https://github.com/microsoft/presidio) (`presidio-analyzer` + `presidio-anonymizer`), backed by spaCy's `en_core_web_lg` NER model. Chosen over hand-rolled regex because named-entity recognition generalizes across name formats and phrasing far better than pattern matching, and Presidio is a maintained, widely-used library rather than a bespoke detector we'd need to validate from scratch.

**Entity types supported**: `PERSON` → `<NAME>`, `PHONE_NUMBER` → `<PHONE>`, `EMAIL_ADDRESS` → `<EMAIL>`, `LOCATION` → `<LOCATION>`. Scoped deliberately to what's relevant for a support-agent context rather than enabling Presidio's full entity list, to keep false-positive risk manageable.

**How it works**: raw prompt → `AnalyzerEngine.analyze()` detects entities → `AnonymizerEngine.anonymize()` replaces each span with its tag → only the redacted text is stored, alongside a `pii_detections` row recording entity type and count per prompt (never the entity value itself).

**Tested and passing**: correctly redacts the brief's own example, handles unusual phone formatting (dashes, country codes), lowercase/informal names, and correctly distinguishes company names (e.g. "Infosys") from person names.

**Known limitation (found through deliberate testing)**: phone numbers with **no surrounding whitespace or punctuation** (e.g. `"mynumberis9840112233callme"`) are **not detected** — the raw digits leak into storage unredacted. We isolated the root cause: Presidio's phone recognizer depends on spaCy's tokenization to find word boundaries, and a glued-together string produces a single unsegmented token the recognizer never gets a clean span to match against. Adding a single space around the same digits restores detection (verified in `tests/test_pii_sanitizer.py`). **Mitigation for production**: add a regex-based fallback pass for long digit runs (8+ consecutive digits) that runs independently of spaCy tokenization, so detection doesn't depend entirely on clean word boundaries.

## Observability approach — capability matrix

Research question from the brief: how much AI visibility can be achieved without application code changes, versus with a gateway, versus with full code instrumentation? Answered empirically (`flyyy-research/experiment.py`), not from assumption — the script simulates the same agent call three ways and records what each observer can actually see.

| Capability | No code change | Gateway (proxy) | Code instrumentation |
|---|---|---|---|
| AI provider | Inferable from destination host (TLS SNI) | Known exactly | Explicit |
| Model | Not visible (inside encrypted body) | Visible | Explicit |
| Prompt | Not visible | Visible | Explicit |
| Token usage | Not visible | Visible | Explicit |
| Tool calls | Not visible | **Not visible** — tool calls aren't LLM traffic | Explicit |
| Agent execution (multi-step reasoning) | Not visible | **Not visible** — internal to the process | Explicit |
| Data-source access | Not visible | **Not visible** — DB calls bypass the LLM gateway entirely | Explicit |

**Key finding**: a gateway gives you provider, model, prompt, and token usage "for free" without touching application code — but it is structurally blind to anything that isn't LLM network traffic. Tool calls, internal agent reasoning steps, and non-LLM data access (like our agent's Orders Database lookup) never pass through an LLM gateway at all, because they're direct function/DB calls the application makes itself. This is why our actual implementation uses code-level instrumentation (a LangChain callback recording every `on_tool_start` event) rather than relying on a gateway — it's the only approach in this matrix that can see tool-level and data-source-level activity, which is precisely the "declared vs. observed" governance insight this project is built around.

## End-to-end example (verified working)

Matches the brief's own example almost exactly:

1. A user query mentioning an order ("Where is my order ORD-4471 and what are your support hours?") is sent to the LangGraph agent.
2. The agent (declared to use only `FAQ Database`) is given two real tools. The LLM independently decides to call both `FAQ Database` and `Orders Database`.
3. The `ToolAccessLogger` callback records both calls as they happen.
4. The API computes `observed_data_sources − declared_data_sources` and returns `has_unexpected_access: true`.
5. The React dashboard renders this run with a red "Unexpected access" badge, distinct from a clean run that only touches FAQ Database.

Because tool selection is made by a real LLM rather than a scripted heuristic, this is not deterministic — an interesting finding in itself, discussed below.

## Key technical decisions

- **Real LLM tool-calling over a keyword heuristic.** An earlier version of the agent decided which tools to call using a hardcoded `if "order" in query` check. This worked but wasn't actually testing "AI usage" — it was testing an if-statement. We replaced it with a LangGraph `create_agent` wired to a live LLM (Groq's `openai/gpt-oss-20b`, chosen for its free tier and speed) making real tool-calling decisions. This is closer to what the brief is actually asking to be monitored, and it surfaced a genuine finding: the LLM's tool selection is **not fully deterministic** — the same-ish query can sometimes trigger only FAQ Database (the agent asking for an order number first) and sometimes both tools, depending on phrasing. This matters for governance: you cannot assume a single test run tells you an agent's behavior is stable. Continuous observation, not one-time declaration review, is what this project's monitoring approach is built to support.
- **Monitoring, not the agent, is the source of truth.** The `ToolAccessLogger` callback records tool access independently of the agent's own final answer. An agent's self-reported behavior should not be trusted as an audit record — this is a deliberate design choice, not an oversight.
- **No agent framework overhead where it doesn't help.** The PII pipeline is plain FastAPI + Presidio; LangGraph is used only where it adds real value (the agent itself), per the brief's own guidance that a framework should only be used if it "adds clear value."
- **Mocked LLM available as a fallback.** The agent can run against Groq's live API (default) or the earlier keyword-based version can be reintroduced for demo situations needing zero external dependency — documented as a deliberate reliability trade-off, not an accident.

## Assumptions

- A single seeded `ai_assets` row ("Customer Support Agent") stands in for a real asset registry; a production system would have a management UI for registering/declaring assets.
- Groq's free tier is used for the live LLM rather than a paid provider, given project scope and cost constraints; the architecture is provider-agnostic (swapping `ChatGroq` for `ChatAnthropic` requires no other changes).
- The two "databases" (FAQ, Orders) are mocked Python functions rather than real database-backed services — sufficient to demonstrate the declared-vs-observed monitoring mechanism, which is the actual subject under test.

## Out of scope (deliberate cuts)

- Multi-tenant auth / user accounts
- Real-time streaming updates to the dashboard (currently polls on tab switch)
- Production-grade PII detection beyond Presidio's NER (e.g. a fine-tuned model)
- Multi-agent orchestration
- Deployment (the brief lists this as optional; prioritized a solid, fully-verified local setup over a rushed deployed link)

## Limitations & what we'd add with more time

- **Glued-digit phone numbers bypass PII detection** — documented above, with a proposed regex-fallback mitigation not yet implemented.
- **Retention (`retention_days`) exists as a schema column but has no automated cleanup job yet** — the toggle for *whether* to monitor an asset (`monitoring_enabled`) is implemented and verified (returns 403 when disabled), but scheduled deletion of prompts older than `retention_days` is not yet built.
- **No OpenTelemetry spans wired into the live agent run** — OTel was used during Day 1 research to validate the capability matrix, but the production logging path currently uses a LangChain callback directly rather than emitting OTel spans. A production version would likely use both: OTel for cross-service tracing, the callback for domain-specific tool-access semantics.
- **Dashboard polls rather than streams** — acceptable at this scale, would need WebSockets or SSE for a live-updating governance view at production scale.

