# Computer Mode

**Status:** first desktop entry point implemented; cross-platform orchestration is planned.

## User experience

Hermes should have a dedicated **Computer** section beside the conversation. The user can watch the browser, see the pointer move, and interact with the page directly while the agent works. The computer uses the same user/workspace environment as Hermes' existing terminal; it must not silently create a separate isolated filesystem or pretend a remote desktop exists when it does not.

The desktop application already contains a Chromium-backed browser preview and an input channel that sends real mouse/keyboard input to its browser guest. This first increment adds a discoverable **Open Computer** command in the command palette that reveals that existing browser surface rather than creating a competing browser implementation.

## Cross-platform design

### Shared concepts

Use one stable computer/session identity and explicit capability status across clients:

- **Desktop (Windows, macOS, Linux):** local browser surface and the same local Hermes workspace/terminal. Reuse the existing desktop browser and terminal plumbing.
- **Android APK:** companion UI and control surface. Do not claim a full local computer until the APK can package and run the agent plus a supported browser backend. It may later connect to a user-configured desktop/remote worker.
- **Termux:** keep using the current Termux environment and terminal. A visual computer is not assumed to exist on a headless terminal; it can only be offered if a supported graphical/remote browser backend is configured.
- **Messaging channels (including configured WhatsApp gateway):** create or inspect a task using the same task/session identity. Messages should report progress and request approval, not imply that the messaging app itself contains a desktop.

### Shared state and identity

A later shared API should represent:
- computer session ID, owner/profile, workspace identifier, backend type and health;
- browser tabs, active URL, pointer/input capability, and last visible state;
- task status (queued, running, awaiting approval, paused, failed, completed, cancelled);
- approval requests and an audit trail.

The computer must use the existing Hermes profile/session identity so configured memory and SOUL.md remain the agent's normal context. The UI may be personalized from that profile, but model-authored UI content must be treated as untrusted data and rendered safely.

## Approval and transparency

- Show whether the computer is local, remote, disconnected, or unavailable.
- Ask before sending messages, submitting forms with real-world effects, deleting/modifying important files, installing software, changing account settings, or making purchases.
- Provide pause, cancel, and revoke-access controls.
- Never report a task as completed without a confirmed result.
- Do not persist passwords, session cookies, or secrets in task summaries or logs.

## Delivery plan

1. **Desktop entry point (this increment):** add an Open Computer command that reveals the existing visual browser.
2. **Desktop computer workspace:** bring the browser and existing terminal into a clearly named Computer section without duplicating the terminal backend; add visible backend status and safe interaction controls.
3. **Shared computer/session API:** define capabilities, session identity, task status, approvals and restart recovery, with tests.
4. **Messaging continuity:** route supported channels through the same task IDs and approval policy.
5. **Android companion:** build a client for the shared API and show the computer only when a real compatible backend is available.
6. **Verification:** run desktop tests on Windows/macOS/Linux where CI permits, Android build + device/emulator smoke tests, and end-to-end messaging tests before claiming cross-platform support.

## Current limitation

This PR implements only the first desktop entry point. It does not yet add a persistent worker, shared API, automated reminders, cross-channel task execution, or functional Computer Mode to the Android APK. Those require separate code and end-to-end tests.
