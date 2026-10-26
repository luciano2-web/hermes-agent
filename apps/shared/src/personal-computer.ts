/**
 * Cross-platform contracts for Hermes Personal Computer.
 *
 * This module intentionally contains no platform-specific I/O. Desktop,
 * Android, macOS, and messaging adapters can share the same task and approval
 * vocabulary without pretending that a browser/worker exists when it is offline.
 */

export type PersonalComputerPlatform =
  | 'desktop'
  | 'android'
  | 'macos'
  | 'windows'
  | 'linux'
  | 'web'
  | 'messaging';

export type ComputerTaskStatus =
  | 'queued'
  | 'running'
  | 'awaiting_approval'
  | 'paused'
  | 'failed'
  | 'completed'
  | 'cancelled';

export type ComputerActionRisk =
  | 'read_only'
  | 'write_local'
  | 'send_message'
  | 'account_change'
  | 'purchase'
  | 'delete_data'
  | 'install_software';

export type ComputerApprovalStatus = 'pending' | 'approved' | 'denied' | 'expired';

export interface ComputerTask {
  id: string;
  title: string;
  prompt: string;
  status: ComputerTaskStatus;
  createdAt: string;
  updatedAt: string;
  requesterId: string;
  sourcePlatform: PersonalComputerPlatform;
  /** Stable reference to the user's existing Hermes profile/session. */
  profileId: string;
  /** Human-readable progress, never a substitute for verified task output. */
  progress?: string;
  resultSummary?: string;
  errorCode?: string;
}

export interface ComputerWorkspaceProfile {
  id: string;
  displayName: string;
  /** Reference to the existing profile's SOUL.md; never duplicate secrets here. */
  soulFile?: string;
  /** Reference to existing Hermes memory/session store. */
  memoryProfileId: string;
  theme?: 'system' | 'light' | 'dark' | 'custom';
  accentColor?: string;
  preferredBrowser?: 'chromium' | 'system';
  createdAt: string;
  updatedAt: string;
}

export interface ComputerApprovalRequest {
  id: string;
  taskId: string;
  requesterId: string;
  action: ComputerActionRisk;
  summary: string;
  target?: string;
  status: ComputerApprovalStatus;
  createdAt: string;
  expiresAt?: string;
  decidedAt?: string;
  decidedBy?: string;
}

export type ComputerEvent =
  | { type: 'task.created'; task: ComputerTask }
  | { type: 'task.updated'; task: ComputerTask }
  | { type: 'approval.requested'; approval: ComputerApprovalRequest }
  | { type: 'approval.decided'; approval: ComputerApprovalRequest }
  | { type: 'worker.status'; online: boolean; platform: PersonalComputerPlatform; checkedAt: string }
  | { type: 'browser.status'; connected: boolean; url?: string; title?: string }
  | { type: 'computer.notice'; id: string; title: string; message: string; createdAt: string; taskId?: string };

const ALLOWED_TRANSITIONS: Record<ComputerTaskStatus, readonly ComputerTaskStatus[]> = {
  queued: ['running', 'cancelled', 'failed'],
  running: ['awaiting_approval', 'paused', 'failed', 'completed', 'cancelled'],
  awaiting_approval: ['running', 'paused', 'failed', 'cancelled'],
  paused: ['queued', 'running', 'cancelled', 'failed'],
  failed: ['queued'],
  completed: [],
  cancelled: []
};

export function canTransitionComputerTask(
  from: ComputerTaskStatus,
  to: ComputerTaskStatus
): boolean {
  return ALLOWED_TRANSITIONS[from].includes(to);
}

export function transitionComputerTask(
  task: ComputerTask,
  status: ComputerTaskStatus,
  updatedAt: string,
  details: Pick<ComputerTask, 'progress' | 'resultSummary' | 'errorCode'> = {}
): ComputerTask {
  if (!canTransitionComputerTask(task.status, status)) {
    throw new Error(`Invalid computer task transition: ${task.status} -> ${status}`);
  }
  return { ...task, ...details, status, updatedAt };
}

/** Actions that change the outside world must never be implicitly approved. */
export function requiresComputerApproval(action: ComputerActionRisk): boolean {
  return action !== 'read_only';
}

export function canExecuteComputerAction(
  action: ComputerActionRisk,
  approval?: Pick<ComputerApprovalRequest, 'status' | 'action' | 'taskId'>,
  taskId?: string
): boolean {
  if (!requiresComputerApproval(action)) return true;
  return Boolean(
    approval &&
      approval.status === 'approved' &&
      approval.action === action &&
      (!taskId || approval.taskId === taskId)
  );
}

export function isComputerTaskTerminal(status: ComputerTaskStatus): boolean {
  return status === 'completed' || status === 'cancelled';
}
