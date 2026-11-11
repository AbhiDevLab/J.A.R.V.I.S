# J.A.R.V.I.S Interaction Tracing

## Purpose

The local interaction trace store provides evidence about how J.A.R.V.I.S handled requests. It is inspired by the trace-collection and evaluation patterns documented in Stanford's OpenJarvis, but is implemented for this repository's current command pipeline.

It is an observability foundation, not an online-learning system. It does not change model weights, choose a different model, retrain anything, or automatically modify routing policy.

## What is recorded

Each interaction receives a random trace ID. Separate event rows record bounded metadata such as:

- input channel: voice or typed;
- whether contextual interpretation ran and its confidence;
- classified intent and the internal classification source;
- selected route: interpretation, automation, conversation, clarification or recovery;
- action type (for example, `open_application`), but not action parameters;
- coarse outcome and normalized provider error category;
- allowlisted provider category;
- stage latency in milliseconds.

The database has no fields for raw transcripts, prompts, model responses, document contents, paths, shell commands, tool arguments, credentials, API keys, or audio. Arbitrary metadata passed to the trace API is discarded unless it is explicitly allowlisted.

Automation traces record the action type and outcome after the existing executor returns. They do not authorize, execute, retry or approve actions. J.A.R.V.I.S's current action policy, voice confirmation, face-authentication and administrator-elevation flow remains authoritative.

## Storage and controls

Default database:

`data/interaction_traces.sqlite3`

The database is local and covered by the repository's `*.sqlite3` ignore rule. It is not uploaded to a provider or committed to Git.

Environment controls:

| Variable | Default | Purpose |
|---|---|---|
| `JARVIS_INTERACTION_TRACES_ENABLED` | `1` | Set to `0` to disable trace writes and reads |
| `JARVIS_INTERACTION_TRACE_DB` | `data/interaction_traces.sqlite3` | Override local database path |
| `JARVIS_INTERACTION_TRACE_RETENTION_DAYS` | `30` | Retain at most the configured number of days (1–365) |

The trace API is best-effort: database/path errors are swallowed and must never interrupt the current J.A.R.V.I.S request. Storage is bounded by both the configured time window and a hard cap of 50,000 events.

## Inspecting recent events

From the project root with `envjarvis` active:

```cmd
python -c "from engine.interaction_trace import list_recent_interaction_trace_events; [print(row) for row in list_recent_interaction_trace_events(30)]"
```

Treat the resulting metadata as diagnostic information. Do not add private transcripts or action arguments to traces during future extensions.

## Validation requirements

Tests cover:

- the metadata allowlist and absence of content-bearing database columns;
- opt-out without creating a database;
- rejection of unknown event types and malformed trace IDs;
- retention cleanup;
- fail-open behavior when the local store cannot be written;
- end-to-end trace events through the existing command path.

Trace evidence may later support offline analysis and evaluation-set creation. Any adaptive routing or action-policy change requires separate experiments, sample thresholds, explicit evaluation and regression tests. No automatic policy adaptation is part of this increment.
