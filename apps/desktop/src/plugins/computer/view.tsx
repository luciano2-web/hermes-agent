import { useCallback, useEffect, useState } from 'react'
import { host } from '@hermes/plugin-sdk'
import { getComputerUseStatus } from '@/hermes'
import type { ComputerUseStatus } from '@/types/hermes'
import { AlertTriangle, CheckCircle2, CircleDashed, ExternalLink, Globe, Monitor, MousePointer2, RefreshCw, ShieldCheck, TerminalSquare } from 'lucide-react'

type ComputerSection = 'computer' | 'browser' | 'tasks' | 'approvals'

const SECTIONS: Array<{ id: ComputerSection; label: string; icon: typeof Monitor }> = [
  { id: 'computer', label: 'Computer', icon: Monitor },
  { id: 'browser', label: 'Browser', icon: Globe },
  { id: 'tasks', label: 'Tasks', icon: TerminalSquare },
  { id: 'approvals', label: 'Approvals', icon: ShieldCheck }
]

function StatusMark({ ready }: { ready: boolean | null | undefined }) {
  if (ready === true) return <CheckCircle2 className="size-4 text-emerald-500" />
  if (ready === false) return <AlertTriangle className="size-4 text-amber-500" />
  return <CircleDashed className="size-4 text-muted-foreground" />
}

function StatusCard({ label, value, detail, ready }: { label: string; value: string; detail: string; ready?: boolean | null }) {
  return (
    <div className="rounded-xl border border-border/70 bg-card p-4">
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        {ready === undefined ? <CircleDashed className="size-4" /> : <StatusMark ready={ready} />}
        <span>{label}</span>
      </div>
      <p className="mt-3 text-lg font-semibold">{value}</p>
      <p className="mt-1 text-sm leading-5 text-muted-foreground">{detail}</p>
    </div>
  )
}

/**
 * First slice of the shared Personal Computer workspace. This deliberately
 * reports the real existing computer-use preflight state and labels browser
 * streaming/task orchestration as not yet connected; it never fabricates a
 * screenshot, cursor position, or running task.
 */
export function PersonalComputerView() {
  const [section, setSection] = useState<ComputerSection>('computer')
  const [status, setStatus] = useState<ComputerUseStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setStatus(await getComputerUseStatus())
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
      setStatus(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void refresh() }, [refresh])

  const computerReady = status?.platform_supported && status.installed && status.ready === true

  return (
    <main className="flex h-full min-h-0 flex-col overflow-auto bg-background">
      <header className="border-b border-border/70 px-6 py-5 md:px-8">
        <div className="mx-auto flex max-w-6xl flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Monitor className="size-4" /> Hermes workspace
            </div>
            <h1 className="mt-2 text-2xl font-semibold tracking-tight">Personal Computer</h1>
            <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
              A dedicated place to see the computer environment, browser activity, background tasks, and requests waiting for your approval.
            </p>
          </div>
          <button
            className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm hover:bg-muted disabled:opacity-50"
            disabled={loading}
            onClick={() => void refresh()}
            type="button"
          >
            <RefreshCw className={`size-4 ${loading ? 'animate-spin' : ''}`} /> Refresh status
          </button>
        </div>
      </header>

      <div className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-5 px-6 py-5 md:px-8">
        <nav aria-label="Computer sections" className="flex flex-wrap gap-2">
          {SECTIONS.map(item => {
            const Icon = item.icon
            const active = section === item.id
            return (
              <button
                aria-current={active ? 'page' : undefined}
                className={`inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors ${active ? 'bg-primary text-primary-foreground' : 'border border-border hover:bg-muted'}`}
                key={item.id}
                onClick={() => setSection(item.id)}
                type="button"
              >
                <Icon className="size-4" /> {item.label}
              </button>
            )
          })}
        </nav>

        {section === 'computer' && (
          <>
            <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              <StatusCard
                detail={status ? `Detected platform: ${status.platform}` : 'Checking the active Hermes backend.'}
                label="Computer-use driver"
                ready={computerReady}
                value={loading ? 'Checking…' : error ? 'Status unavailable' : !status?.platform_supported ? 'Unsupported here' : !status.installed ? 'Not installed' : status.ready ? 'Ready' : 'Needs attention'}
              />
              <StatusCard
                detail="The future live view must show the actual session output, not a simulated desktop."
                label="Live screen and mouse"
                value="Not connected yet"
              />
              <StatusCard
                detail="The goal is to reuse Hermes’ existing computer-use and terminal backends on the machine that owns the session."
                label="Execution environment"
                value="Existing backend"
              />
            </section>

            {error && (
              <div role="alert" className="rounded-lg border border-destructive/40 bg-destructive/5 p-3 text-sm">
                Could not read Computer Use status: {error}
              </div>
            )}

            {status?.checks?.length ? (
              <section className="rounded-xl border border-border/70 p-4">
                <h2 className="font-medium">Readiness checks</h2>
                <ul className="mt-3 grid gap-2">
                  {status.checks.map(check => (
                    <li className="flex items-start gap-2 text-sm" key={check.label}>
                      <StatusMark ready={check.status === 'ok'} />
                      <span className="min-w-0 flex-1">{check.label}</span>
                      <span className="text-muted-foreground">{check.status}</span>
                    </li>
                  ))}
                </ul>
              </section>
            ) : null}

            <section className="rounded-xl border border-dashed border-border p-5">
              <div className="flex items-start gap-3">
                <MousePointer2 className="mt-0.5 size-5 text-muted-foreground" />
                <div className="min-w-0 flex-1">
                  <h2 className="font-medium">A real, visible computer session</h2>
                  <p className="mt-1 text-sm leading-6 text-muted-foreground">
                    The next integration connects this view to an actual browser or desktop session so you can watch the cursor move, inspect the screen, and take over input. This first version only checks the existing driver; it does not pretend that a live session is already running.
                  </p>
                  <button
                    className="mt-3 inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm hover:bg-muted"
                    onClick={() => host.navigate('/capabilities?tab=toolsets')}
                    type="button"
                  >
                    Configure computer tools <ExternalLink className="size-3.5" />
                  </button>
                </div>
              </div>
            </section>
          </>
        )}

        {section === 'browser' && (
          <section className="rounded-xl border border-border/70 p-5">
            <div className="flex items-center gap-2 font-medium"><Globe className="size-5" /> Browser session</div>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              The live Chromium view is not wired to this page yet. The implementation should reuse Hermes’ existing browser/CDP session and display its real tabs, address, screenshot stream, and cursor/input state.
            </p>
          </section>
        )}

        {section === 'tasks' && (
          <section className="rounded-xl border border-border/70 p-5">
            <div className="flex items-center gap-2 font-medium"><TerminalSquare className="size-5" /> Persistent tasks</div>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              A shared task registry is the next backend milestone. It must keep stable task IDs, status, progress, results, and pause/resume/cancel state across app and gateway restarts.
            </p>
          </section>
        )}

        {section === 'approvals' && (
          <section className="rounded-xl border border-border/70 p-5">
            <div className="flex items-center gap-2 font-medium"><ShieldCheck className="size-5" /> Approval inbox</div>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              The approval inbox will surface pending actions such as sending messages, submitting forms, changing important files, or making purchases. These actions must wait for an explicit user decision.
            </p>
          </section>
        )}
      </div>
    </main>
  )
}
