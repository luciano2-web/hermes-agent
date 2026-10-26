import { connectionScoped, hermesApi, profileScoped } from './client'

export type ComputerTaskStatus =
  | 'queued'
  | 'running'
  | 'awaiting_approval'
  | 'paused'
  | 'failed'
  | 'completed'
  | 'cancelled'

export interface ComputerTask {
  id: string
  request_key: null | string
  channel: string
  requester_id: string
  title: string
  summary: string
  status: ComputerTaskStatus
  created_at: string
  updated_at: string
  metadata: Record<string, unknown>
}

export interface ComputerTaskEvent {
  kind: string
  message: string
  data: Record<string, unknown>
  created_at: string
}

export interface CreateComputerTask {
  channel: string
  requester_id: string
  title: string
  summary?: string
  request_key?: string
  metadata?: Record<string, unknown>
}

type ComputerScope = { profile?: string }

export async function getComputerTasks(
  options: ComputerScope & { status?: ComputerTaskStatus; limit?: number } = {}
): Promise<ComputerTask[]> {
  const query = new URLSearchParams()
  if (options.status) query.set('status', options.status)
  if (options.limit !== undefined) query.set('limit', String(options.limit))
  const suffix = query.size ? `?${query.toString()}` : ''
  const result = await hermesApi<{ tasks: ComputerTask[] }>({
    ...profileScoped(options.profile),
    ...connectionScoped(),
    path: `/api/computer/tasks${suffix}`
  })
  return result.tasks ?? []
}

export async function createComputerTask(
  task: CreateComputerTask,
  options: ComputerScope = {}
): Promise<ComputerTask> {
  const result = await hermesApi<{ task: ComputerTask }>({
    ...profileScoped(options.profile),
    ...connectionScoped(),
    path: '/api/computer/tasks',
    method: 'POST',
    body: task
  })
  return result.task
}

export async function getComputerTask(
  taskId: string,
  options: ComputerScope = {}
): Promise<ComputerTask> {
  const result = await hermesApi<{ task: ComputerTask }>({
    ...profileScoped(options.profile),
    ...connectionScoped(),
    path: `/api/computer/tasks/${encodeURIComponent(taskId)}`
  })
  return result.task
}

export async function transitionComputerTask(
  taskId: string,
  status: ComputerTaskStatus,
  options: ComputerScope & { message?: string; event_data?: Record<string, unknown> } = {}
): Promise<ComputerTask> {
  const result = await hermesApi<{ task: ComputerTask }>({
    ...profileScoped(options.profile),
    ...connectionScoped(),
    path: `/api/computer/tasks/${encodeURIComponent(taskId)}/transition`,
    method: 'POST',
    body: { status, message: options.message, event_data: options.event_data }
  })
  return result.task
}

export async function appendComputerTaskEvent(
  taskId: string,
  event: { kind: string; message?: string; data?: Record<string, unknown> },
  options: ComputerScope = {}
): Promise<ComputerTaskEvent[]> {
  const result = await hermesApi<{ events: ComputerTaskEvent[] }>({
    ...profileScoped(options.profile),
    ...connectionScoped(),
    path: `/api/computer/tasks/${encodeURIComponent(taskId)}/events`,
    method: 'POST',
    body: event
  })
  return result.events ?? []
}
