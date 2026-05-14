import { describe, expect, it } from 'vitest'
import { applyStreamEventToMessage, serverMsgToLocal } from './useChat'
import type { Message } from '../types/chat'

describe('chat stream helpers', () => {
  it('keeps partial streaming messages visible instead of showing thinking dots', () => {
    const message = serverMsgToLocal({
      id: 'm1',
      role: 'assistant',
      content: 'partial answer',
      metadata: {
        status: 'streaming',
        run_id: 'r1',
        last_event_id: '4-0',
      },
      created_at: '2026-05-12T00:00:00Z',
    })

    expect(message.status).toBe('streaming')
    expect(message.thinking).toBe(false)
    expect(message.runId).toBe('r1')
    expect(message.lastEventId).toBe('4-0')
  })

  it('tracks event ids while applying stream chunks', () => {
    const base: Message = {
      id: 'm1',
      role: 'ai',
      content: 'hello',
      status: 'streaming',
      runId: 'r1',
      createdAt: 1,
    }

    const next = applyStreamEventToMessage(base, { type: 'answer_chunk', content: ' world' }, '2-0')

    expect(next.content).toBe('hello world')
    expect(next.thinking).toBe(false)
    expect(next.status).toBe('streaming')
    expect(next.lastEventId).toBe('2-0')
  })

  it('uses server partial content and event id as the resume checkpoint', () => {
    const restored = serverMsgToLocal({
      id: 'm1',
      role: 'assistant',
      content: 'hello world',
      metadata: {
        status: 'streaming',
        run_id: 'r1',
        last_event_id: '2-0',
      },
      created_at: '2026-05-12T00:00:00Z',
    })

    const resumed = applyStreamEventToMessage(restored, { type: 'answer_chunk', content: '!' }, '3-0')

    expect(restored.content).toBe('hello world')
    expect(restored.lastEventId).toBe('2-0')
    expect(resumed.content).toBe('hello world!')
    expect(resumed.lastEventId).toBe('3-0')
  })

  it('clears streaming state on terminal events', () => {
    const base: Message = {
      id: 'm1',
      role: 'ai',
      content: 'done',
      status: 'streaming',
      runId: 'r1',
      thinking: false,
      createdAt: 1,
    }

    const completed = applyStreamEventToMessage(base, { type: 'done', state: { generated_sql: 'select 1' } }, '3-0')
    const failed = applyStreamEventToMessage(base, { type: 'error', content: 'bad' }, '4-0')

    expect(completed.status).toBe('completed')
    expect(completed.sql).toBe('select 1')
    expect(completed.lastEventId).toBe('3-0')
    expect(failed.status).toBe('failed')
    expect(failed.error).toBe('bad')
    expect(failed.thinking).toBe(false)
  })
})
