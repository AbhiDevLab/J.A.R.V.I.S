# Phase 7.4.1 — Central Permission Architecture

## Selected policy

- Ordinary operations: automatic.
- Sensitive operations: one-time voice confirmation.
- Critical operations: one-time voice confirmation followed by face authentication.
- Administrator access: on demand only. The main JARVIS process remains un-elevated.

Windows UAC is part of the critical path only when a typed action explicitly declares that it requires administrator privileges.

## Enforcement model

Every supported action enters `execute_action()`. The executor resolves its handler before approval, classifies the semantic action, records the request, obtains the required approval, verifies that the action fingerprint is unchanged, and only then executes it.

Unknown action types classify as critical. Unsupported handlers are rejected before prompting. `RiskLevel.HIGH` and `requires_admin=True` always force the critical tier.

## Action tiers

### Ordinary
Read-only and low-impact operations such as opening/reading applications, opening files/folders, listing directories, and finding files. These execute automatically.

### Sensitive
Operations that change user data or close active work: typing into applications, compound open-and-type, creating, renaming, moving, copying, and closing applications. These require explicit voice confirmation but not face authentication.

### Critical
Shell/PowerShell/Python execution, deletes, process termination, system power, software installation/removal, registry/service/firewall changes, system-wide tasks, and all administrator-required operations. These require voice confirmation and face authentication.

## Operation-bound approval

The approval fingerprint is SHA-256 over the action type, exact parameters, risk level, and administrator requirement. It is held only in memory, checked after approval, and never reused for another operation. Any mutation invalidates approval.

Confirmation is parsed from the raw recognition result using a small exact allowlist; it is not paraphrased by the LLM/context interpreter.

## Audit trail

SQLite stores UTC timestamps, action type, tier, fingerprint, event, and reason code. It never stores raw paths, shell command contents, credentials, document text, or voice recordings. Sensitive and critical actions fail closed if the request/approval audit record cannot be persisted.

Default database: `data/automation_audit.sqlite3` (ignored by Git). Override with `JARVIS_AUTOMATION_AUDIT_DB`.

## Administrator boundary

The ordinary JARVIS process is never relaunched as Administrator. `AutomationAction.requires_admin` is trusted typed metadata. Such actions are routed to the privileged-broker interface only after critical approval. This commit deliberately fails closed because the one-shot UAC broker is Phase 7.4.4; it does not run the action in the normal process as a fallback.

## Not included yet

- One-shot elevated Windows broker and UAC transport (Phase 7.4.4).
- System discovery and capability adapters (Phases 7.4.2–7.4.5).
- Security settings UI and audit viewer.
- Broad autonomous workflow planning.

## Validation expectations

Policy classification, downgrade resistance, one-time fingerprint binding, audit privacy, audit failure behavior, approval requirements, and privileged-broker fail-closed behavior are covered by automated tests. Live Windows UAC broker validation is deferred until the broker exists.
