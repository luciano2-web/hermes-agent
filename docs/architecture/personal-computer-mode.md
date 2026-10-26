# Personal Computer Mode

**Status:** desktop MVP in progress; cross-platform automation is not complete.

## Product goal

Hermes should have a named **Computer** section available alongside a conversation. It should feel like a personal computer belonging to that assistant/profile, with a visible browser, pointer and keyboard interaction, and a terminal. The user and Hermes share the same configured workspace and filesystem; this is not a second isolated shell.

The section should eventually be reachable from desktop, Android, macOS, Windows, Linux, and configured messaging channels. A message from WhatsApp or another gateway should be able to create a task that is visible in the same Computer section. Platform clients are different views of the same task/session service, not separate agents with divergent memories.

This is inspired by the broad product idea of a persistent personal agent, not a claim of feature parity with any proprietary service.

## Existing building blocks found in this fork

- The desktop app already uses Electron and an embedded Chromium webview for browser previews.
- `apps/desktop/src/app/chat/right-rail/preview-input.ts` exposes a per-tab input registry and uses Chromium's native input pipeline (`sendInputEvent`) so the real pointer can move and hover states can work. This is preferable to synthetic DOM clicks.
- `apps/desktop/src/store/preview.ts` already owns preview tabs and can open a browser target in the active session.
- The desktop terminal is a persistent pane connected to the active Hermes backend. Computer mode must reveal/reuse this terminal, not launch another shell.
- The agent already has browser provider and browser registry abstractions in `agent/browser_provider.py` and `agent/browser_registry.py`.
- `SOUL.md`, profiles, skills, and memory already belong to Hermes. Computer mode should read the active profile/session context rather than inventing a parallel personality store.

## First desktop slice

The desktop MVP adds a **Computer workspace** pane which:
- can be opened from the command palette as “Computer workspace”;
- displays the active workspace name;
- opens a blank tab in the existing browser preview;
- reveals the existing terminal pane;
- explicitly identifies the limits of this initial slice instead of pretending persistent tasks or notifications already exist.

This is a bridge to existing functionality, not yet a complete always-on computer agent. The browser and terminal remain the existing app surfaces and configured backend.

## Architecture to build next

### 1. One shared computer/task model

Add a versioned backend contract, ideally served through the existing Hermes gateway:

- task id, profile/session owner, origin channel, status, timestamps and progress;
- states: queued, running, awaiting approval, paused, failed, completed, cancelled;
- browser session/tab identifier and active workspace reference;
- task actions: create, inspect, pause, resume, cancel, approve/reject;
- idempotency keys for message/webhook retries and recovery after restarts.

Keep the source of truth on the Hermes backend. Desktop and mobile clients subscribe to the same state. Avoid a second competing memory or SOUL.md.

### 2. Visual browser and pointer

- Reuse the current Electron Chromium webview and `registerPreviewInput` for real pointer/keyboard events.
- Expose agent actions only through a narrow, typed interface bound to the active preview tab; do not let arbitrary web content call privileged Electron APIs.
- Show the cursor and current action to the user where feasible; show URL, loading state, screenshot/preview, and an event/activity list.
- Provide a manual takeover mode so the user can click/type directly. When a user takes over, pause agent input until control is handed back.
- Keep browser credentials/profile selection explicit. Do not silently reuse personal logged-in sessions without consent.

### 3. Same terminal and filesystem

- Reuse the active Hermes terminal/backend and its working directory.
- The Computer panel must never create a second shell or copy the workspace to an unrelated container by default.
- Remote execution, if added later, must be explicitly selected and visibly identified because its filesystem is not the local one.
- In Termux, a desktop Chromium process is not a portable assumption. The Android client needs an Android-compatible WebView or remote display adapter while preserving the same selected Hermes backend and workspace semantics.

### 4. Persistent personal assistant and proactive notices

- Use the existing profile, SOUL.md, skills and memory systems as context.
- Add scheduled/condition-based task sources through existing cron/gateway mechanisms where appropriate.
- Notifications should explain the evidence and proposed action (e.g. a draft email). Drafting is allowed; sending, spending, deleting, changing account state, or contacting another person requires explicit permission/approval.
- Provide audit history, pause/stop, revoke access, quiet hours and notification preferences.

### 5. Messaging and cross-platform clients

- Reuse configured gateway adapters (WhatsApp or other supported channels) rather than building a duplicate WhatsApp integration.
- Bind inbound requests to an authorized sender/profile and task ID.
- Send progress and approval requests back through the same channel; the desktop/mobile Computer section shows the same task.
- Build the shared API and task semantics first, then add client surfaces: desktop Electron, Android, and later other supported platforms. Do not claim “all platforms” until each build and end-to-end path is tested.

## Security and privacy requirements

- Pair devices and verify the sender before allowing task control.
- Separate read-only observation from input and external side effects.
- Require approval for sends, purchases, account changes, destructive file operations and installs.
- Keep tokens out of renderer/webview code and logs; use the existing secure IPC boundary.
- Record tool actions, approvals, task status changes and failures in an inspectable log.
- Provide immediate stop/cancel and credential revocation.
- Do not run browser actions from untrusted page scripts with Electron privileges.

## Acceptance criteria

1. The desktop Computer pane opens the existing browser and reveals the existing terminal without starting a second environment.
2. Hermes can move the real Chromium pointer, type and click through the supported browser-input path, with the user able to take over.
3. The active profile, SOUL.md, skills and memory remain the ones already used by the chat/session.
4. A task started through a configured messaging channel appears in desktop and Android with the same task ID and status.
5. Tasks recover after a gateway restart when persistent storage and a persistent worker are configured.
6. The UI distinguishes awaiting approval from running and never claims completion without backend confirmation.
7. CI, tests and platform-specific end-to-end checks pass before a platform is described as supported.

## Current limitations

- The initial Computer pane does not yet implement a persistent task API, a remote desktop protocol, proactive reminders, mobile client UI, or end-to-end WhatsApp-to-computer continuity.
- Android APK support remains experimental. A successful APK compile alone does not prove that the complete Hermes agent is packaged or functional.
- Always-on execution requires a live backend/worker; neither a free host nor a phone background process can be assumed to run continuously.
