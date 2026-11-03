import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { ComputerUseStatus } from '@/types/hermes'

import { PersonalComputerView } from './view'

const getComputerUseStatus = vi.fn()
const navigate = vi.fn()

vi.mock('@/hermes', () => ({ getComputerUseStatus: () => getComputerUseStatus() }))
vi.mock('@hermes/plugin-sdk', () => ({ host: { navigate } }))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

function readyStatus(): ComputerUseStatus {
  return {
    platform: 'linux',
    platform_supported: true,
    installed: true,
    ready: true,
    can_grant: false,
    accessibility: null,
    screen_recording: null,
    version: 'test driver',
    checks: []
  } as unknown as ComputerUseStatus
}

describe('PersonalComputerView', () => {
  it('reports the actual computer-use readiness from the backend', async () => {
    getComputerUseStatus.mockResolvedValue(readyStatus())

    render(<PersonalComputerView />)

    await waitFor(() => expect(screen.getByText('Ready')).toBeTruthy())
    expect(screen.getByText('Not connected yet')).toBeTruthy()
    expect(screen.getByText(/does not pretend that a live session is already running/i)).toBeTruthy()
  })

  it('offers a route to computer tool configuration', async () => {
    getComputerUseStatus.mockResolvedValue(readyStatus())

    render(<PersonalComputerView />)
    fireEvent.click(await screen.findByRole('button', { name: /configure computer tools/i }))

    expect(navigate).toHaveBeenCalledWith('/capabilities?tab=toolsets')
  })

  it('keeps the browser, tasks, and approvals sections explicit about their current status', async () => {
    getComputerUseStatus.mockResolvedValue(readyStatus())

    render(<PersonalComputerView />)

    fireEvent.click(screen.getByRole('button', { name: 'Browser' }))
    expect(screen.getByText(/live Chromium view is not wired/i)).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: 'Tasks' }))
    expect(screen.getByText(/shared task registry is the next backend milestone/i)).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: 'Approvals' }))
    expect(screen.getByText(/explicit user decision/i)).toBeTruthy()
  })
})
