# Personal Computer Mode — Architecture Proposal

**Status:** proposal / not implemented  
**Target:** Hermes Agent fork, Android companion, existing messaging gateway  
**Goal:** one persistent personal agent that can be directed from Android or a supported messaging channel and work inside a dedicated computer environment.

## Product concept

The user can send a task from WhatsApp (when the existing gateway is configured), the Android companion, or another supported channel. The request creates or resumes a persistent task. The agent works in a dedicated worker environment with its own workspace and browser, then reports progress and results through the originating channel. The same task can be inspected from Android.

This is inspired by the *general workflow* of always-on agents; it is not a claim of feature parity with OpenAI Dots.

## Proposed components

1. **Task Control API**
   - Create, list, inspect, pause, resume, cancel, and approve tasks.
   - Use stable task IDs across messaging and Android.
   - Return explicit states: queued, running, awaiting approval, paused, failed, completed, cancelled.

2. **Persistent task store**
   - Store task ID, requester identity, channel, status, timestamps, concise progress, result references, and approval state.
   - Recover safely after gateway or worker restarts.
   - Make message handling idempotent to avoid duplicate work from webhook retries.

3. **Worker / computer backend**
   - Define an interface rather than coupling task orchestration to one cloud vendor.
   - Start with a local or SSH-backed worker that can be tested; consider cloud backends later.
   - Isolate each task's workspace and browser profile where practical.
   - Report health and availability accurately. A persistent worker is required for work to continue while Android is offline; free hosting is not guaranteed to be continuously available.

4. **Android companion**
   - Show task list, progress, recent output, approvals, worker connectivity, and errors.
   - Provide pause, cancel, revoke-access, and open-computer/browser controls.
   - Clearly distinguish a real remote desktop/browser session from a simple status screen.

5. **Messaging adapter**
   - Reuse Hermes gateway adapters instead of creating a parallel WhatsApp integration.
   - Map each authorized sender to a user/profile and task permissions.
   - Send task updates and approval requests back through the configured channel.
   - Never treat a message from an unpaired sender as authorization.

6. **Permission and audit layer**
   - Require explicit approval for external side effects such as sending messages, changing accounts, modifying/deleting important files, installing software, or making purchases.
   - Separate read permissions from write/send permissions.
   - Log approvals, tool actions, errors, and cancellations in a user-inspectable audit trail.
   - Support an immediate stop control and revocation of worker access.

## Implementation plan

### Phase 0 — repository audit
- Inspect the Android APK source and current build workflow.
- Determine whether the current APK is a real agent client or an experimental shell.
- Map gateway, session, terminal-backend, approval, and persistence APIs already available.
- Document platform limitations and known failing CI checks.

### Phase 1 — task model and API
- Define task states and a versioned API.
- Add persistent storage and restart recovery.
- Add tests for duplicate requests, cancellation, authorization, and failure recovery.

### Phase 2 — worker interface
- Implement one backend using existing Hermes terminal capabilities where feasible.
- Keep credentials out of task logs and Android builds.
- Expose worker health, workspace metadata, and supported operations.

### Phase 3 — Android controls
- Add task list/details, approval inbox, progress, logs, and stop/pause controls.
- Add remote computer/browser viewing only after an actual backend supports it.
- Handle offline and reconnect states explicitly.

### Phase 4 — cross-channel continuity
- Connect WhatsApp and other configured gateway channels to the same task IDs.
- Verify that a task started in one channel can be inspected in Android and that authorization follows the requester, not merely the channel.

### Phase 5 — end-to-end verification
- Demonstrate a task from WhatsApp to worker to Android and back.
- Test gateway restart, worker outage, duplicate message delivery, revoked access, unauthorized sender, approval denial, and emergency stop.
- Publish a setup guide that explains hosting, model/API costs, privacy, and limitations.

## Acceptance criteria

- A task started through a configured messaging channel appears in Android with the same task ID.
- Tasks can recover after a gateway restart when persistent storage and a persistent worker are configured.
- The interface never labels a task complete unless the worker confirms completion.
- Sensitive external actions follow explicit permissions and approval policy.
- The user can inspect logs, pause/cancel work, and revoke access.
- Tests and an end-to-end demo pass before describing the feature as implemented.

## Non-goals for the first version

- Guaranteeing 24/7 operation on a free host.
- Claiming support for every platform before each adapter is tested.
- Building a full virtual-computer system from scratch if an existing terminal/browser backend can be reused.
- Automatically sending messages or making consequential changes without the configured authorization.

## Current status

This document is a design proposal only. No Android UI, task API, cloud computer, or end-to-end WhatsApp workflow is implemented by this document.
