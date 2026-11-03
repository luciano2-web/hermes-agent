# Personal Computer task registry

## Purpose

The task registry is the durable source of task state for future desktop, Android, and messaging clients. Clients should display the same task ID and status rather than independently inventing their own state.

## Current implementation

`hermes_cli.personal_computer.tasks.TaskRegistry` stores task metadata, state transitions, approvals, and an append-only event history in SQLite. It supports:

- Stable task IDs across clients connected to the same backend database.
- Idempotency keys to prevent duplicated tasks when a messaging provider retries delivery.
- Explicit task states and validated transitions.
- Approval requests that remain pending until a human resolves them.
- An audit event for creation, status changes, and approval decisions.
- Restart recovery by reopening the same file-backed database.

The module is a backend building block. It does not run tasks, execute approvals, operate Chromium, expose a network API, send WhatsApp messages, or create Android UI by itself. Those integrations must be implemented separately.

## Integration requirements

1. Instantiate the registry under the active Hermes profile's data directory, not in the repository checkout.
2. Expose task operations only through the authenticated gateway/API; never expose the SQLite file directly to remote clients.
3. Authorize the requester for every list/get/transition/approval operation. Filtering by requester ID is not a substitute for gateway authentication.
4. Make browser/terminal workers update status and append events through the backend.
5. Require the approval layer to check the recorded decision immediately before the external side effect. Recording an approval does not itself execute the action.
6. Add migrations/versioning before changing the schema in a released build.
7. Test concurrent requests and process restart against the same database.

## Next implementation slice

Wire the registry into the existing gateway's authenticated RPC protocol, then replace the Computer view's placeholder Tasks and Approvals panels with live registry data. After that, add a real browser session viewer backed by the existing browser/CDP tooling. Cross-channel adapters and Android should consume the same API rather than keep their own task databases.
