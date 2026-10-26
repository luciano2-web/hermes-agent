import { useStore } from '@nanostores/react'

import { Button } from '@/components/ui/button'
import { Codicon } from '@/components/ui/codicon'
import { $currentCwd } from '@/store/session'
import { $previewTabs, openPreview } from '@/store/preview'
import { setTerminalTakeover } from '@/app/right-sidebar/store'

/**
 * Computer workspace starter.
 *
 * This intentionally reuses the desktop app's existing Browser preview and
 * terminal pane: it must not spawn a second shell or a separate filesystem.
 * Browser input is handled by the existing Chromium webview input registry.
 * A persistent task API and mobile clients are follow-up phases.
 */
export function ComputerPane() {
  const cwd = useStore($currentCwd)
  const previewTabs = useStore($previewTabs)
  const browserTabs = previewTabs.filter(tab => tab.target.kind === 'url')
  const workspaceName = cwd.trim().split(/[\\/]+/).filter(Boolean).pop() || 'Current session'

  const openBrowser = () => {
    openPreview({
      kind: 'url',
      label: 'Computer browser',
      source: 'computer-mode',
      url: 'about:blank'
    })
  }

  const openTerminal = () => setTerminalTakeover(true)

  return (
    <section aria-label="Computer workspace" className="flex h-full min-h-0 flex-col gap-4 overflow-y-auto p-4">
      <header className="flex items-start gap-3">
        <div className="flex size-10 shrink-0 items-center justify-center rounded-xl border border-border bg-muted/50">
          <Codicon name="device-desktop" size="1.25rem" />
        </div>
        <div className="min-w-0 flex-1">
          <h2 className="text-sm font-semibold text-foreground">Computer</h2>
          <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
            A visual workspace for Hermes. It reuses this session’s existing terminal and browser instead of
            creating a separate environment.
          </p>
        </div>
      </header>

      <div className="rounded-xl border border-border p-3">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Codicon name="folder-opened" size="0.9rem" />
          <span>Shared workspace</span>
        </div>
        <p className="mt-1 break-all text-sm font-medium text-foreground">{workspaceName}</p>
        <p className="mt-1 text-xs text-muted-foreground">
          The computer’s terminal uses the same working directory as the active session.
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <div className="rounded-xl border border-border p-3">
          <div className="flex items-center gap-2">
            <Codicon name="globe" size="1rem" />
            <h3 className="text-sm font-medium text-foreground">Browser</h3>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            {browserTabs.length === 0
              ? 'No browser tab is open yet.'
              : `${browserTabs.length} browser tab${browserTabs.length === 1 ? '' : 's'} available in this session.`}
          </p>
          <Button className="mt-3 w-full" onClick={openBrowser} size="sm" variant="outline">
            <Codicon name="browser" size="0.9rem" />
            Open browser
          </Button>
        </div>

        <div className="rounded-xl border border-border p-3">
          <div className="flex items-center gap-2">
            <Codicon name="terminal" size="1rem" />
            <h3 className="text-sm font-medium text-foreground">Terminal</h3>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            Reopen the existing terminal pane; no second shell is created.
          </p>
          <Button className="mt-3 w-full" onClick={openTerminal} size="sm" variant="outline">
            <Codicon name="terminal" size="0.9rem" />
            Show terminal
          </Button>
        </div>
      </div>

      <div className="rounded-xl border border-dashed border-border p-3">
        <div className="flex items-center gap-2">
          <Codicon name="shield" size="1rem" />
          <h3 className="text-sm font-medium text-foreground">Control and approvals</h3>
        </div>
        <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
          This first desktop slice opens the real browser and terminal surfaces. Persistent computer tasks,
          cross-device task history, proactive reminders, and approval notifications are not implemented yet;
          they must be connected to Hermes’ gateway and permission system before being advertised as available.
        </p>
      </div>
    </section>
  )
}
