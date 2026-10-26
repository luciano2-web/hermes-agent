# Personal Computer Mode

**Status:** implementation plan grounded in the current fork. The cross-platform experience described here is not yet complete.

## Product goal

Hermes should have a persistent visual computer that feels like a section of the same assistant, not a separate product. The user can watch the pointer move, see Chromium, take control, and hand control back. The assistant uses the terminal and browser environment already configured for its profile; it must not silently create a second unrelated environment.

The same task and approval state should be visible from supported clients: Hermes Desktop, Android, macOS/Windows/Linux clients, and configured messaging channels. A messaging channel can request work and receive updates, but should not pretend to display a live desktop if it cannot render the stream.

## What the fork already contains

- `tools/computer_use/` and `tools/computer_use/tool.py`: cross-platform computer-use tool and backend selection for supported desktop environments.
- `tools/bot_desktop/`: per-profile Xfce/Xvnc desktop on supported Linux gateway hosts, persistent Chromium profile, RFB viewer bridge and a human/agent control lease.
- `hermes_cli/subcommands/computer_use_screen.py`: `hermes computer-use screen status|start|stop|install` management commands.
- `apps/desktop/src/plugins/hermes-bots/screen-pane.tsx`: live screen viewer with Watch / Take over / Hand back, opened as a Desktop workspace.
- `plugins/platforms/whatsapp/`: existing WhatsApp adapter that can be a messaging entry point when configured.
- `android/`: experimental APK wrapper, not a complete Hermes client yet. `README.android.md` explicitly warns that the full agent package is not bundled and the APK is not proven functional.

These are useful foundations. We should extend them rather than build a second browser, terminal, desktop server, or WhatsApp integration from scratch.

## Architecture

### 1. One computer runtime per configured execution environment

Introduce a common computer-session contract above the existing backends:

- **Desktop local session:** use the existing native `computer_use` backend on the user's OS.
- **Remote Linux session:** use Bot Desktop, with the browser and terminal in the same configured gateway/sandbox environment.
- **Android:** act as a remote client to a paired gateway/computer session; do not attempt to bundle a full Linux desktop into the APK. Android's local terminal remains its own environment and is not silently replaced.
- **Messaging:** create/inspect tasks, receive progress, and answer approval requests. Live pixels and pointer interaction require a visual client.

The selected backend must report where it runs and which terminal environment it shares. If the terminal is configured to use Docker, SSH, or another sandbox, the computer runtime must follow that backend's existing placement rules or clearly report that the combination is unsupported.

### 2. Shared session and task state

Every computer task has a stable ID and these states:

- `queued`
- `running`
- `awaiting_approval`
- `human_control`
- `paused`
- `failed`
- `completed`
- `cancelled`

Store the task's profile, originating channel, current computer session, progress summary, approval request, timestamps, and result references in the gateway-owned persistence layer. Desktop and Android should display the same task ID. Reconnects and duplicate messaging webhooks must not launch duplicate actions.

### 3. Computer section in the client

Add a first-class **Computer** workspace beside the chat:

- Live browser/desktop stream with a visible pointer and browser identity.
- Watch, Take over, Hand back, Pause and Stop controls.
- Status for connected, starting, awaiting approval, unavailable, and failed.
- A small task activity list and approval inbox.
- The user can interact directly with the same Chromium profile the agent uses; never launch an unrelated profile for the human.
- On small screens, the computer view becomes a responsive full-screen page while preserving the task ID and chat context.

Hermes Desktop already has a screen workspace. The first UI change should reuse it and connect it to the shared task/session model rather than duplicate its viewer.

### 4. Proactive notifications

Use existing scheduler/gateway capabilities to surface user-requested reminders and detected follow-ups. Each notification must explain what Hermes found, show its source, and offer **Review**, **Approve**, **Dismiss**, and where appropriate **Snooze**.

For example, Hermes may prepare a customer email after detecting that a quote needs a response. It must save the draft and request approval; it must not send the email merely because a message or page suggested doing so. Calendar, email, billing and CRM integrations must be connected explicitly and must respect their permissions.

### 5. Memory and personalization

Use the existing profile identity and `SOUL.md` / memory systems as the source of the agent's persona and preferences. The computer UI is a view of the same profile, not a new agent with a second memory. Allow users to personalize layout, theme, browser shortcuts and notifications, but keep action permissions separate from persona text.

## Platform plan

| Platform | First supported role | Important constraint |
| --- | --- | --- |
| Linux gateway / cloud | Hosts persistent Bot Desktop where supported | Runtime availability depends on the host and configured sandbox |
| Windows / macOS / Linux desktop | Native computer-use backend and Computer workspace | Use the OS-supported backend; don't assume Bot Desktop's Linux Xfce runtime applies locally |
| Android APK | Paired remote viewer and task/approval client | Current APK is experimental and doesn't yet bundle the complete Hermes agent |
| Termux | Existing CLI and terminal environment | Keep the current terminal workflow; no fake GUI claim and no separate desktop runtime unless the user explicitly configures a remote one |
| WhatsApp / other messaging adapters | Start/inspect tasks and receive alerts/approval requests | Messaging cannot display or control a live desktop by itself |

## Security and trust

- Pair each client with an authenticated gateway profile; never trust an arbitrary messaging sender.
- Require explicit approval for sending messages, purchases, account changes, installing software, or destructive file operations.
- When a human takes over, computer-use actions must stop until control is handed back.
- Keep session cookies, API keys, and credentials out of screenshots, logs, task summaries and APK resources.
- Provide a visible Stop action, revoke-client access, and an audit trail of actions and approvals.
- The screen and terminal may share an OS user and files; document this honestly instead of claiming isolation that does not exist.

## Implementation order

1. **Foundation:** preserve and test the existing Bot Desktop/computer-use behavior; write down supported runtime placement and the shared task/session contract.
2. **Desktop:** surface the existing viewer as a first-class Computer workspace tied to the current chat/profile, with task status and approval state.
3. **Gateway:** persist computer task/session state and publish status/approval events with stable IDs and idempotent request handling.
4. **Messaging:** route supported channels through the same task model and deliver progress/approval messages.
5. **Android:** add pairing and remote Computer workspace, then validate the existing APK packaging problem separately.
6. **Other clients:** reuse the same gateway contract for macOS/Windows/Linux and future mobile clients.
7. **Proactive workflows:** add reminders and draft preparation only for explicitly connected data sources, with approval before external side effects.

## Acceptance criteria

- A task started from a supported messaging channel is visible in the Desktop and Android clients under the same ID.
- The visible pointer, browser and terminal target the documented same profile/environment.
- Human takeover reliably prevents computer-use actions until hand-back.
- A stopped, failed, offline or approval-blocked task is never shown as completed.
- No external message is sent and no consequential change is made without the configured approval.
- A clean build and automated tests pass for each changed client; Android additionally needs a real-device/emulator smoke test.
- Documentation distinguishes implemented, experimental and planned capabilities.

## Scope note

This plan deliberately does not claim that all platforms are already implemented. The existing Desktop Bot Screen is the strongest starting point; Android packaging, shared cross-channel task persistence, and proactive integrations still need implementation and verification.
