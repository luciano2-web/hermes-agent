import { describe, expect, it } from 'vitest'

import {
  computerActionRequiresApproval,
  safeComputerConnectionStatus,
  safeComputerTaskStatus
} from './computer-mode.js'

describe('computer mode shared contract', () => {
  it('requires approval for consequential external actions', () => {
    expect(computerActionRequiresApproval('send_email')).toBe(true)
    expect(computerActionRequiresApproval('delete_file')).toBe(true)
    expect(computerActionRequiresApproval('purchase')).toBe(true)
    expect(computerActionRequiresApproval('run_command')).toBe(true)
  })

  it('allows non-mutating browser observation without an approval requirement', () => {
    expect(computerActionRequiresApproval('screenshot')).toBe(false)
    expect(computerActionRequiresApproval('read')).toBe(false)
    expect(computerActionRequiresApproval('navigate')).toBe(false)
  })

  it('fails closed when a server sends an unknown task state', () => {
    expect(safeComputerTaskStatus('finished-ish')).toBe('failed')
  })

  it('treats an unknown connection state as disconnected', () => {
    expect(safeComputerConnectionStatus('connected-maybe')).toBe('disconnected')
  })
})
