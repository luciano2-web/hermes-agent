# Personal Computer mode

**Status:** initial backend/API foundation; UI and worker integration remain in progress.

## Product goal

Hermes should expose a dedicated **Computer** section alongside the chat, not force users to leave the conversation to understand what the agent is doing. The section should show a real browser/desktop surface, a visible pointer and interactions, current task status, activity history, and approval requests. The computer is controlled by the same Hermes environment and permissions as the normal terminal; it must not silently create a second unrelated workspace.

The interface should use each person's active Hermes profile and existing SOUL.md, skills, memory, provider, and configuration. A user's theme and layout preferences should be configurable rather than imposing a fixed branded color scheme.

## Existing building blocks found in this fork

- apps/desktop/ is an existing Electron/React desktop client for macOS, Windows, and Linux.
- apps/desktop/src/app/chat/right-rail/ already contains an embedded Chromium/web preview with navigation, input, screenshots, and pop-out support.
- tools/computer_use/ and plugins/computer_use/ already provide native desktop control through the configured computer-use provider.
- hermes_cli/browser_runtime.py resolves the Chromium executable, including the Termux-specific system Chromium path when available.
- The gateway API already has authenticated task/run and approval concepts.
- android/ exists, but README.android.md explicitly says the APK is experimental and does not yet package the complete Hermes dependency set.

The goal is to connect and extend these pieces, not replace the existing terminal or invent a second desktop automation engine.

## First implementation in this branch

- agent/computer_workspace.py adds a persistent SQLite task ledger under the active HERMES_HOME, with stable task IDs, status transitions, request-key deduplication, and an append-only event log.
- The authenticated API server exposes task list/create/get/transition/event endpoints under /api/computer/tasks.
- The desktop API client exposes typed helpers for those endpoints.
- Tests cover persistence, webhook retry deduplication, valid/invalid state transitions, API authentication, and route registration.

This foundation does not yet launch a browser, drive a cursor, deliver messaging notifications, or provide the Computer pane. Those are follow-up integration steps and must not be represented as completed.

## Proposed architecture

1. **One task identity and event stream.** A task started from desktop or an authorized messaging adapter gets one ID and is visible from the other connected clients. Webhook retries must not duplicate work.
2. **Existing execution environment.** The worker uses the configured Hermes terminal backend and computer-use provider. Local execution stays on the user's machine; a remote worker is optional and must clearly show which host it controls.
3. **Visible computer surface.** The desktop client opens a dedicated Computer pane in the same chat workspace. It reuses the existing browser/preview stack where possible and adds a live computer-use view when the selected provider can provide one. The pointer and actions should be observable; a browser-only preview must not be mislabeled as full desktop control.
4. **Profile-aware personalization.** The active profile's SOUL.md, memory, skills, and configuration remain the source of agent behavior. UI preferences belong in profile-scoped settings and must not overwrite SOUL.md.
5. **Messaging adapters.** WhatsApp and other configured channels enqueue work into the same task ledger, then receive progress and approval prompts. Sender identity must be paired/authorized before a message can create or approve a task.
6. **Approval-first side effects.** Browsing and read-only inspection can follow the configured tool policy. Sending email/messages, purchases, account changes, destructive file operations, and other external side effects must pause in awaiting_approval until an authorized user approves them. Denial/cancellation must stop the pending action.
7. **Notifications.** The scheduler/monitor can surface overdue invoices, unanswered quote requests, and other user-configured follow-ups, but should prepare drafts and request approval instead of sending them automatically.
8. **Cross-platform clients.** Desktop uses the existing Electron app; Android uses a native companion only after the agent runtime/package strategy is verified. macOS/Windows/Linux share the desktop client. Termux remains a CLI/control surface and can query the same API, but it is not expected to provide a desktop-style GUI on-device.

## Implementation sequence

- [x] Add a persistent task ledger and authenticated task API.
- [x] Add typed desktop API helpers for task operations.
- [ ] Add a Computer pane in the desktop chat that lists tasks, shows status/events, and exposes pause/cancel/approval controls.
- [ ] Wire browser/computer-use progress events into the task ledger without creating a second terminal session.
- [ ] Connect configured messaging adapters to the same task IDs and enforce paired-sender permissions.
- [ ] Add configurable reminders and approval-gated email/message drafts.
- [ ] Define the remote worker protocol and optional cloud/local computer backend.
- [ ] Integrate Android after confirming a compatible Hermes runtime and testable APK build.
- [ ] Add end-to-end tests for restart recovery, duplicate webhook delivery, unauthorized sender, denied approval, pause/cancel, and desktop-to-mobile continuity.

## Security and reliability requirements

- Never store API keys, passwords, full email bodies, or other secrets in task metadata/events.
- Keep API authentication and profile/connection scoping on every client request.
- Use the existing computer-use approval gate; the task state alone is not authorization to execute an action.
- Show the controlled host and backend before the first action.
- Log redacted actions and outcomes; expose stop/cancel and access revocation.
- Do not claim a task is complete until the worker reports completion.
- Do not promise 24/7 work unless a persistent worker is actually running.
