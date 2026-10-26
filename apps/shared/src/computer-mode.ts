/**
 * Cross-platform contract for Hermes Personal Computer mode.
 *
 * This module deliberately defines the shared wire model only. A desktop or
 * mobile client must not claim a computer is connected until a real worker
 * reports it, and must not execute proposed side effects merely because they
 * appear in a task payload.
 */

export const COMPUTER_TASK_STATUSES = [
  'queued',
  'running',
  'awaiting_approval',
  'paused',
  'failed',
  'completed',
  'cancelled'
] as const

export type ComputerTaskStatus = (typeof COMPUTER_TASK_STATUSES)[number]

export const COMPUTER_CONNECTION_STATUSES = [
  'disconnected',
  'connecting',
  'connected',
  'needs_approval',
  'paused',
  'error'
] as const

export type ComputerConnectionStatus = (typeof COMPUTER_CONNECTION_STATUSES)[number]

export type ComputerClientPlatform = 'desktop' | 'android' | 'ios' | 'web' | 'termux'

export type ComputerActionKind =
  | 'navigate'
  | 'click'
  | 'type'
  | 'scroll'
  | 'screenshot'
  | 'read'
  | 'write_file'
  | 'delete_file'
  | 'send_message'
  | 'send_email'
  | 'purchase'
  | 'change_account'
  | 'run_command'

export type ComputerApprovalState = 'not_required' | 'pending' | 'approved' | 'denied'

export interface ComputerWorkspace {
  /** Stable identity shared by desktop and mobile clients. */
  id: string
  name: string
  connection: ComputerConnectionStatus
  /** Describes the machine that actually runs the browser/worker. */
  hostPlatform: Exclude<ComputerClientPlatform, 'web'>
  browserName?: string
  browserUrl?: string
  lastSeenAt?: string
}

export interface ComputerTask {
  id: string
  workspaceId: string
  title: string
  status: ComputerTaskStatus
  createdAt: string
  updatedAt: string
  /** Short, user-visible progress. Do not put secrets here. */
  summary?: string
  originatingChannel?: string
  requiresApproval: boolean
}

export interface ComputerActionProposal {
  id: string
  taskId: string
  kind: ComputerActionKind
  description: string
  approval: ComputerApprovalState
  /** A UI hint only; the backend must enforce authorization independently. */
  externalSideEffect: boolean
}

const EXTERNAL_SIDE_EFFECTS = new Set<ComputerActionKind>([
  'write_file',
  'delete_file',
  'send_message',
  'send_email',
  'purchase',
  'change_account',
  'run_command'
])

/**
 * Conservative approval default for actions that can alter data, contact
 * people, affect accounts, spend money, or execute code.
 */
export function computerActionRequiresApproval(kind: ComputerActionKind): boolean {
  return EXTERNAL_SIDE_EFFECTS.has(kind)
}

export function isComputerTaskStatus(value: unknown): value is ComputerTaskStatus {
  return typeof value === 'string' && (COMPUTER_TASK_STATUSES as readonly string[]).includes(value)
}

export function isComputerConnectionStatus(value: unknown): value is ComputerConnectionStatus {
  return typeof value === 'string' && (COMPUTER_CONNECTION_STATUSES as readonly string[]).includes(value)
}

/** Fail closed on unknown states from a newer/older server. */
export function safeComputerTaskStatus(value: unknown): ComputerTaskStatus {
  return isComputerTaskStatus(value) ? value : 'failed'
}

export function safeComputerConnectionStatus(value: unknown): ComputerConnectionStatus {
  return isComputerConnectionStatus(value) ? value : 'disconnected'
}
