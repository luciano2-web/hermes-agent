# Personal Computer Mode

**Status:** task-state foundation implemented on a feature branch; UI, execution worker, and cross-channel API remain future phases.

## Product goal

Give Hermes a dedicated **Computer** section inside its existing chat experience. It should be available across the desktop app, Android, macOS, and supported messaging clients. A user can inspect a persistent task, watch the computer/browser, see the pointer move and pages change, and take over control when desired.

The computer is an interaction surface for the existing Hermes runtime, not a second agent with a separate terminal. The normal terminal environment and its configured workspace remain authoritative. Browser interaction should reuse Hermes' existing browser capabilities where possible and add a visible/headed browser backend for the Computer view.

## Product behavior

- A persistent **Computer** section can be opened beside or within the current conversation without replacing the chat.
- The browser has a recognizable browser tab/address bar and visible pointer, with live state and screenshots or a remote view supplied by the actual backend.
- The user can take over with keyboard and mouse/touch. Agent and human control must be clearly indicated.
- Tasks started from the desktop, Android, or an authorized messaging adapter share one task ID and state.
- Existing profile configuration, memory, and SOUL.md stay owned by the current Hermes profile. Computer mode reads the active profile context; it must not create a disconnected personality or duplicate the memory store.
- The assistant can proactively surface useful reminders and draft follow-ups, but external actions such as sending an email, submitting a form, making a purchase, deleting data, or changing account settings require explicit approval.
- Notifications should explain what was detected, what the assistant proposes, and what permission is needed. No fake "completed" states.

## Existing seams to reuse

- apps/desktop is already an Electron desktop app with a native chat surface and an in-app browser window implementation (apps/desktop/electron/browser-windows.ts).
- agent/browser_provider.py and agent/browser_registry.py already provide pluggable cloud-browser backends.
- The existing terminal and tool approval path remains responsible for terminal commands; this feature must not invent a parallel shell or silently switch workspaces.
- The gateway and profile/session model are the shared coordination points for other clients.

The existing browser window is not by itself proof that Hermes can drive a full interactive desktop, and the cloud browser provider interface is not a live computer-use API. The worker and visual-control bridge must be implemented and tested separately.

## Task-state foundation

agent/personal_computer/tasks.py provides a small SQLite-backed task ledger for the first implementation step:

- Stable UUID task IDs and idempotency keys for duplicate webhook/message delivery.
- Profile-scoped task listing.
- Explicit lifecycle states: queued, running, awaiting approval, paused, failed, completed, cancelled.
- Atomic state transitions and expected-state checks to reject stale updates.
- An explicit approval decision record. Approving changes task state only; it does not itself execute an external action.
- Persistence across process restarts.

The store is deliberately not wired to execute commands, drive a browser, or expose an unauthenticated API yet.

## Implementation phases

### Phase 1 — persistent task core
- [x] Define shared task states and durable task records.
- [x] Add idempotent task creation, profile scoping, restart persistence, and approval-state primitives.
- [x] Add focused unit tests.
- [ ] Run the test suite and static checks in CI.

### Phase 2 — connect the existing runtime
- Add a task coordinator that invokes the existing Hermes session/tool system.
- Preserve the selected profile, workspace, and terminal backend; never create a surprise second terminal.
- Emit task progress and approval-required events to the existing gateway.
- Test cancellation, worker restart, stale events, and tool failures.

### Phase 3 — visual computer backend
- Define a capability-based interface for screenshot, navigation, pointer move/click, keyboard input, and visible browser state.
- Reuse the existing browser provider registry where it fits; implement a headed browser/remote-view adapter for the desktop.
- Add explicit human takeover, pause/stop, URL allow/deny policy, and approval gates for consequential actions.
- Keep browser cookies and credentials out of task metadata and logs.

### Phase 4 — desktop Computer section
- Add a separate Computer pane in the existing desktop chat, with browser controls, live status, task activity, approvals, and a clear human/agent control indicator.
- Follow apps/desktop/DESIGN.md and existing Electron/renderer/backend boundaries.
- The renderer must not execute shell commands or use broad Node/Electron access.

### Phase 5 — Android and other clients
- Android becomes a remote control/view for the same task and worker, rather than duplicating a full desktop runtime inside the APK.
- Add responsive web/API access and client adapters for macOS/Windows/Linux and configured messaging channels.
- On Android, provide touch controls and a low-bandwidth view; do not promise a continuously running worker when only the tablet is available.
- A task started in WhatsApp should appear in the desktop and Android views under the same task ID.

### Phase 6 — proactive personal assistant
- Add opt-in reminders and monitored events (for example, overdue invoices or unanswered quote requests) only through explicitly connected data sources.
- Show the evidence/source and why the reminder was raised.
- Prepare email/message drafts for review; sending always waits for user approval.
- Add per-source permissions, quiet hours, rate limits, audit history, and an easy disable/revoke control.

## Acceptance criteria

- A task survives gateway restart and duplicate channel delivery without being duplicated.
- The same authorized task can be inspected from desktop and Android.
- The visible computer accurately reflects the real browser state; no fake pointer movement or simulated success.
- The agent and human can take turns controlling the browser without hidden input capture.
- The existing terminal/workspace is reused as configured and remains subject to existing Hermes approval policies.
- Cross-channel identity and profile permissions are checked server-side.
- External side effects require explicit approval, and every action has an inspectable audit entry.
- Desktop, Android, and gateway CI pass; then perform a real desktop end-to-end test and Android smoke test before claiming support.

## Current limitations

This first code change implements only the task-state foundation. It does not yet create a visual computer, drive Chromium, send WhatsApp messages, monitor invoices, or provide an Android UI. Those capabilities depend on the subsequent phases above.
