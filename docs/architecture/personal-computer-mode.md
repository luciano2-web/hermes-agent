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


## Repository audit update (2026-10-24)

This section records existing building blocks found in the fork before proposing new infrastructure.

### Existing components to reuse

- The desktop application already lives in apps/desktop and uses Electron with a React renderer. Its README describes the desktop shell as connecting to a headless Hermes process through the tui_gateway JSON-RPC/WebSocket API, via apps/shared. The app is available as a target for macOS, Windows, and Linux, although the published release matrix and support differ by platform.
- The desktop app already has chat, streaming tool activity, side-by-side previews, a file browser, voice, settings, and onboarding. The new Computer view should be an additional route/pane in this application, not a separate desktop application.
- Hermes documentation already describes a computer_use toolset for desktop control on macOS, Windows, and Linux, plus browser automation options including local Chromium-family CDP and a visible/headed browser mode. Before writing a second driver, verify whether those toolsets are present, enabled, and working on the fork's current base branch.
- The root README documents a shared gateway for existing messaging channels, including WhatsApp, Telegram, Discord, Slack, and Signal. Reuse the gateway and identity/authorization model rather than creating separate channel bots.
- The Android README explicitly says the APK is experimental and does not yet bundle the complete Hermes Agent dependency set. Treat Android as a client/companion target until packaging and device tests prove otherwise. Termux remains a distinct CLI installation path.

### Gaps to solve (not claims that every item is absent from upstream)

1. A persistent task registry that survives chat changes and gateway restarts, with stable IDs, status, activity, result links, and approval state.
2. A cross-platform Computer view in the existing desktop app, with a browser/desktop session viewer and clear ownership of keyboard/mouse control.
3. A shared task/approval API that can be consumed by desktop, Android, and configured messaging channels.
4. Proactive scheduled checks and notifications that can identify pending work, but only use connected data sources the user has authorized.
5. Explicit approval gates for sending email/messages, submitting forms, spending money, changing accounts, or making consequential file changes.
6. A truthful capability matrix and automated tests for macOS, Windows, Linux, Android companion, and Termux. Do not promise parity merely because a package builds.

## Competitor landscape and product gap

This is a capability comparison, not a claim that Hermes is universally worse. The competing projects are moving quickly; recheck their official docs before publishing any comparative claims.

- OpenAI Dots: official launch materials describe an always-on agent with its own cloud computer and browser, persistent learning from feedback, connected apps, and access from ChatGPT plus selected messaging surfaces. This sets expectations around ongoing tasks, visible computer sessions, and proactive follow-through.
- OpenClaw: its official docs emphasize a self-hosted gateway, persistent memory, a broad set of messaging channels, browser/shell tools, mobile nodes, scheduled automation, and multi-agent routing. This competes on local control and cross-channel reach.
- Browser Use: it is a browser-agent/infrastructure layer rather than a full personal-assistant product. It offers a browser driver, local browser integration and optional cloud browsers; Hermes documentation already names Browser Use in its browser stack. We should integrate or reuse it rather than rebuild browser automation without evidence that it fails our requirements.
- Hermes Agent: the fork already inherits substantial agent, gateway, desktop-shell, browser, terminal-backend, and computer-use foundations. The product gap to focus on is unifying them into a visible, persistent, cross-platform task experience with reliable status, notifications, permissions, and review—not merely adding a mouse cursor.

Official references:
- OpenAI Dots: https://openai.com/index/introducing-dots/
- OpenClaw overview: https://docs.openclaw.ai/help/faq/what-is-openclaw
- Browser Use: https://browser-use.com/
- Hermes computer use: https://hermes-agent.nousresearch.com/docs/user-guide/features/computer-use
- Hermes browser automation: https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/features/browser.md

## Revised implementation roadmap

### Milestone 1 — verify and expose existing computer/browser tools
- Audit the desktop route structure, preload bridge, gateway RPC methods, toolset registration, and current fork base.
- Add a Computer entry to the existing desktop navigation that shows truthful connection/session state.
- Reuse the existing computer_use/browser tools where available; do not introduce a parallel driver until tests show a concrete gap.
- Acceptance: one desktop end-to-end test launches or attaches to a supported browser, shows its status and a screenshot/session view, and can safely perform a harmless navigation task.

### Milestone 2 — task registry and approval inbox
- Add a versioned task model and persistent store behind the existing gateway/backend.
- Expose list/get/pause/resume/cancel/approve operations through the shared API.
- Add desktop task list, live progress, activity log, and approval inbox.
- Acceptance: a task remains inspectable after a renderer restart; denied approval prevents the external action.

### Milestone 3 — channel continuity and proactive notices
- Map authorized channel identities to the same task IDs.
- Add scheduled checks only for user-authorized sources and provide a way to disable each check.
- Deliver progress, overdue-work alerts, and approval requests through configured channels.
- Acceptance: a task started in one channel can be inspected from desktop and a second configured channel without duplicating execution.

### Milestone 4 — Android companion and platform matrix
- Add the same task list, approvals, notifications, and remote Computer view to Android only after defining a supported API/transport.
- Keep the Termux CLI working as-is; it does not need to host a full graphical desktop locally.
- Test macOS, Windows, Linux, Android, and Termux separately and document unsupported combinations.

### Milestone 5 — upstream contribution strategy
- Split the work into small PRs: (1) audited/reusable computer-use integration, (2) desktop Computer view, (3) task/approval API, (4) messaging continuity, (5) Android companion.
- Each PR should include focused tests, screenshots or a short demo, a clear problem statement, and explicit limitations.
- Keep the feature branch current with upstream main; request review from the relevant maintainers only after the checks pass. Do not claim that maintainers have noticed or approved a PR until GitHub confirms it.

## Safety and reliability requirements

- The user can always see whether the computer is connected, which environment it controls, and what task is running.
- Browser actions and local-computer actions must have clear, separate permissions; a cloud computer must not silently gain access to the user's real device.
- Read-only research may proceed within granted access. Sending, submitting, purchasing, deleting, installing, or changing important data requires explicit approval by default.
- Credentials, cookies, private messages, and full page contents must not be copied into task logs unnecessarily.
- Provide pause, cancel, revoke-access, and audit-history controls.
- Never send a drafted email or message merely because the agent prepared it.


## Mobile use is a first-class requirement

Mobile is not a later afterthought and does not mean trying to run a full Linux graphical desktop inside Android. The Android app (or a responsive mobile client where that is more practical) must be able to:

- Open the same **Computer** section and same persistent task IDs as Desktop.
- See the remote desktop/browser live, including visible cursor movement, and send touch gestures as pointer/keyboard input when connected.
- Read task progress and audit events; approve or reject an action; pause/cancel work; disconnect the viewer without killing the task.
- Receive opt-in notifications for attention needed, task completion, and approval requests.
- Reconnect after network loss without creating a duplicate task or launching a second computer session.

### Runtime model

The computer runs on the configured Hermes execution host/terminal backend; the phone is a viewer/controller. The client must not silently create a second terminal environment. In particular, the existing `tools.bot_desktop.placement` policy resolves whether the desktop belongs on the gateway host or a supported terminal backend. Preserve that policy and report `refused` clearly for backends that cannot host a graphical stream; do not quietly escape the selected execution boundary.

The existing `tools.bot_desktop` code already implements a Linux Xfce desktop per Hermes profile, an RFB Unix socket, profile-specific state, and a Chromium profile shared between the dock's Browser icon and the agent. That is a useful starting point for the visible computer, but the code audit alone does not prove that an authenticated mobile RFB/WebSocket viewer or a complete Computer UI exists. Build that transport deliberately; never expose the raw RFB socket or unauthenticated remote-debugging port to the public internet.

### Mobile acceptance tests

- A phone/tablet can connect to a paired gateway over an authenticated transport and see the same running desktop as Desktop.
- Tap, drag, scroll, and on-screen keyboard input reach the intended remote screen, with visible feedback and no accidental host-device input.
- Disconnecting the phone only disconnects the viewer; it does not kill the agent task or its shared terminal environment.
- Reconnection resumes the same task/session IDs.
- Unauthorized clients cannot view the screen, read session state, or send input.
- A task awaiting approval remains blocked until an authorized user approves it.
- The feature degrades honestly when the chosen backend cannot provide a graphical stream.

## Status

The repository audit confirms reusable architecture and existing browser/computer-use documentation. It does not prove the fork's GUI currently exposes every computer-use feature, and it does not mean the new Computer view, persistent task registry, or proactive workflow has been implemented. Those require code changes and end-to-end tests.
