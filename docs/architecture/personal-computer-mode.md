# Personal Computer mode

**Status:** foundational contracts implemented; browser control and UI are not yet implemented.

Personal Computer is a cross-platform workspace for Hermes. It should appear as a dedicated section inside the existing conversation UI on desktop and mobile, rather than a separate branded app. The worker should reuse the user's existing Hermes profile, terminal/backend and memory identity. A browser window is a visual surface for that same worker, not a second unrelated computer.

## Shared contract added

`apps/shared/src/personal-computer.ts` defines:
- Cross-platform task and worker states.
- Stable task/profile identifiers, including references to the existing SOUL.md and memory profile.
- Approval requests for actions with external side effects.
- Events for task changes, approvals, worker availability, browser availability and proactive notices.
- Task transition validation and a fail-closed approval check.

The module is platform-neutral so desktop, Android, macOS, Windows, Linux, web and configured messaging adapters can use the same vocabulary.

## Intended architecture

1. **Existing Hermes runtime remains the execution authority.** Do not create a second terminal or silently move tasks to a separate filesystem. A remote worker is an optional backend only when the user explicitly configures one.
2. **Browser adapter:** expose Chromium/Playwright or the supported existing browser tool through a small interface for navigate, screenshot, click, type, scroll and wait. The UI should show the real browser state and a visible cursor/action indicator. Human interaction and agent actions must not race; offer pause/take-control.
3. **Task coordinator:** persist task IDs, state, progress, profile reference and approval state so the same task can be opened from desktop, Android or a messaging channel.
4. **Conversation integration:** add a Computer section/panel beside the current chat, with task list, live browser surface, terminal output, notifications, approvals, and pause/cancel controls.
5. **Proactive notices:** reminders and detected follow-ups create draft suggestions (for example, a reply to a customer); they never send externally without explicit approval.
6. **Platform adapters:** desktop first because the existing Electron application and shared TypeScript package are already present; Android next; then macOS/Windows/Linux packaging and messaging connectors using the same contracts. Termux continues to use its existing terminal, without pretending to have a desktop window manager.

## Required safeguards

- Read-only navigation can run without approval; sending messages, purchases, account changes, software installation, important file writes/deletes and similar external side effects require an explicit approval tied to the task and action.
- Verify the requesting user/channel before allowing control.
- Show clear offline, awaiting-approval, paused, failed and completed states. Never mark work complete merely because a command was submitted.
- Provide stop/cancel and audit history.
- Do not store API keys in profile metadata, UI state, screenshots, or logs.
- SOUL.md and memory are references to the user's existing profile, not copies to drift out of sync.

## Milestones

- [x] Define shared cross-platform task, profile, event and approval contracts.
- [ ] Add unit tests for state transitions and approval decisions.
- [ ] Connect contracts to the desktop Electron main process and existing gateway.
- [ ] Add Computer section to the existing desktop chat UI.
- [ ] Implement a real browser adapter and live browser display using existing supported tooling.
- [ ] Persist task state and approvals with restart recovery.
- [ ] Add proactive reminder/draft workflow with explicit approval.
- [ ] Build Android UI and decide the supported Android browser/runtime strategy.
- [ ] Add platform-specific packaging and end-to-end tests.
- [ ] Demonstrate one task started in a messaging channel and continued in desktop/Android.

## Current limitation

This milestone only adds shared contracts and safety primitives. It does not yet launch Chromium, move a real mouse, render a remote desktop, connect WhatsApp, send notifications, or add the UI. Those features must be wired to existing runtime capabilities and tested before they are advertised as available.
