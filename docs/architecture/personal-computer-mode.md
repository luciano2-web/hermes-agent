# Personal Computer Mode

**Status:** implementation plan; the end-to-end feature is not implemented yet.  
**Goal:** one persistent Hermes assistant with a dedicated, visible computer/browser workspace, accessible from Desktop, Android, and configured messaging channels.

## What already exists in this fork

This feature should extend existing systems, not create a second agent or terminal:

- **Desktop app:** `apps/desktop/` is an Electron/React app for macOS, Windows, and Linux. It already has a browser preview/pop-out (`apps/desktop/src/app/chat/browser-popout-shell.tsx`), a Computer Use settings panel (`apps/desktop/src/app/settings/computer-use-panel.tsx`), a canonical gateway connection, session history, and profile-aware configuration.
- **Browser automation:** `tools/browser_session.py`, `tools/browser_session_cdp.py`, and the browser toolset already manage Chromium/CDP sessions. Browser tasks can use the existing browser session instead of starting a second unrelated browser.
- **Visible desktop interaction:** `tools/computer_use/` and `plugins/computer_use/` use the CUA driver on supported macOS, Windows, and Linux hosts. The existing backend has approval gates and hard-blocked dangerous key combinations.
- **Memory and identity:** existing Hermes profiles, skills, session history, and `SOUL.md` should remain the source of identity and preferences. Personal Computer Mode must not create a parallel memory system.
- **Automation and messaging:** existing gateway adapters and cron scheduler can deliver reminders. Cross-channel task identity and approval state still need to be defined.

## Important platform truth

- **Desktop:** the existing browser and Computer Use primitives make this the best first integration target. The new section should be a workspace in the existing desktop app and use the canonical gateway/profile/session.
- **Android APK:** the current APK is explicitly experimental and does not bundle the full Hermes dependency set. The CUA driver currently targets desktop OSes, not Android. The APK must not claim it can control an Android desktop or run the full agent until packaging, API, UI, and device tests prove it. For a first Android client, connect securely to a paired Hermes gateway/worker; do not attempt to bundle the whole desktop runtime blindly.
- **Termux:** keep the existing CLI and terminal environment. Do not build a fake graphical desktop inside the terminal. Termux can control/inspect the same task service through CLI commands and browser/CDP when configured.
- **macOS, Windows, Linux:** reuse the existing desktop app and Computer Use implementation.
- **Messaging (WhatsApp, Telegram, Discord, etc.):** messages should create, inspect, or approve tasks via the same task IDs. A messaging adapter is a control surface, not a separate agent.

## Product behavior

1. Add a first-class **Computer** section in the existing Desktop app, next to the chat/workspace surfaces. It contains:
   - a visible Chromium/browser viewport with address bar, tab title, loading state, and a visible pointer/action indicator;
   - task list and progress, including the last action and current URL;
   - a clear **Take control / Return control** switch so the human and agent do not unknowingly type over each other;
   - approvals, stop/pause/resume, error details, and a small audit trail;
   - links to the existing chat/session and the selected Hermes profile.
2. The computer workspace uses the same configured terminal/backend and workspace as the selected Hermes profile. It is not silently a second isolated computer. If a user explicitly chooses a sandbox/remote worker, label the location and permissions clearly.
3. Preserve user customization through the existing profile, `SOUL.md`, config, skills, and memory. Store UI preferences separately from agent identity.
4. Support persistent tasks with stable IDs. A task started in WhatsApp can be inspected in Desktop or Android, provided those clients are paired to the same gateway and profile.
5. Proactive reminders (for example, a due invoice or unanswered quote) must be opt-in, show their evidence/source, and offer a prepared draft. Sending an email/message, changing records, making purchases, deleting files, or submitting forms requires explicit approval.
6. The interface must report queued/running/awaiting-approval/paused/failed/completed accurately. It must never claim completion before the worker confirms it.

## Architecture

### Reuse, do not fork the agent

- **Orchestration:** canonical Hermes gateway and existing session/profile model.
- **Browser:** existing browser session/CDP supervisor and local Chromium where available.
- **Desktop input:** existing `computer_use` backend and its approval/permission rules.
- **Terminal:** the configured Hermes terminal backend, respecting its existing local/Docker/SSH/plugin selection.
- **Identity and memory:** existing profile + `SOUL.md` + memory/skills.
- **Notifications:** existing gateway messaging adapters and cron scheduler.

### Add a cross-channel task contract

A future implementation should expose a versioned task API through the authenticated gateway. Each task record should include:

- opaque stable `task_id`, profile ID, requesting identity/channel, and timestamps;
- state: `queued | running | awaiting_approval | paused | failed | completed | cancelled`;
- a short progress summary, current activity, optional browser URL, and result reference;
- required permission, approval decision, approver identity, and audit events;
- worker identity and a truthful worker availability/heartbeat state.

Writes must be authorized per paired user/profile. Message delivery retries must be idempotent. Secrets, cookies, full message contents, and credentials must never be copied into task summaries or logs. Task APIs must use the gateway's existing authenticated control channel rather than exposing an unauthenticated public port.

### Browser and pointer

- Reuse CDP for navigation, page structure, screenshots, and DOM-backed actions.
- Use the existing CUA backend only when actual desktop pointer/keyboard interaction is needed and supported.
- A visible cursor overlay inside the Computer view can show agent pointer actions; it must not pretend to be the operating-system cursor when actions are CDP-only.
- Before human takeover, pause agent input and fence any in-flight action. Resume only after the user explicitly hands control back.
- For a logged-in browser profile, disclose that cookies/session data are sensitive and do not capture or report secrets.

## Implementation phases and gates

### Phase 1 — Desktop Computer workspace (first code milestone)
- Audit the existing browser preview, Computer Use panel, route/contribution registry, and gateway RPC before wiring new UI.
- Add the Computer workspace using existing contribution/navigation conventions.
- Display existing browser tabs/session status and make task status visible; do not add a pretend task API.
- Reuse the current browser and CUA drivers. Add tests for view opening, unsupported backends, browser disconnects, and human takeover.
- Gate: desktop typecheck/tests pass and a manual demo proves visible browser interaction.

### Phase 2 — task API and persistence
- Implement the task contract in the canonical gateway with persistent storage, authorization, idempotency, and audit records.
- Add lifecycle tests including gateway restart, duplicate request, stop/cancel, and denied approval.
- Gate: tasks survive restart without falsely becoming completed.

### Phase 3 — cross-channel control
- Map configured messaging adapters to the same authenticated task service and task IDs.
- Add commands/buttons to inspect status, request approval, pause, and cancel.
- Gate: a task started in a messaging channel can be inspected from Desktop; unauthorized senders cannot control it.

### Phase 4 — Android client
- Build a native Android client that pairs with the existing gateway and shows Computer, tasks, approvals, and notifications.
- First version can remotely view/control a desktop worker; it must not claim the Android device itself has desktop CUA support.
- Add secure pairing, token revocation, reconnect handling, background notification behavior, and Android device tests.
- Gate: install/startup smoke tests and an end-to-end remote task test on a real Android device.

### Phase 5 — proactive reminders
- Add opt-in reminder sources and scheduled checks using existing cron/gateway capabilities.
- Require source connectors and user-selected schedules; never infer invoices or customer promises from inaccessible accounts.
- Draft emails/messages for review, but never send without explicit approval.
- Gate: reminder tests, duplicate-notification prevention, and approval-denial tests.

### Phase 6 — releases and upstream
- CI for desktop (macOS/Windows/Linux) and Android builds, automated tests, permissions review, accessibility, and documented support matrix.
- Keep Android support marked experimental until dependency packaging and on-device verification pass.
- Split upstream contributions into small, reviewable PRs (task API, desktop workspace, Android client, integrations) rather than one enormous PR.

## Definition of done

- One Hermes identity/profile and shared memory across clients.
- Browser view visibly updates and agent actions can be observed.
- Human can take over safely; agent input pauses during takeover.
- Same task ID and truthful status from Desktop and configured messaging channels, later Android.
- Explicit approvals for external side effects; pause/stop/revoke always available.
- Secrets and authenticated browser data are protected.
- CI and end-to-end tests pass for every platform claimed as supported.

## Current status

This document is a plan and architecture contract, not a claim that the feature has been implemented. The fork already has several foundations listed above; the missing work is the unified Computer workspace, durable cross-channel task service, and a properly packaged/verified Android client.
