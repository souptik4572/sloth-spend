// Ask Sloth actions (IMPL M6.4–M6.5): load a conversation, send a message, start a new one.
import { useChat, isStreaming } from '../chatStore'
import { errorMessage, getChat, stream } from './api'
import { turnsFromHistory } from './chat'
import type { ToolArgs } from './types'

const chat = useChat.getState
let current: AbortController | null = null

/** Redraw the saved conversation (after a restart the pane looks as it did). */
export async function loadConversation(): Promise<void> {
  const { cid } = chat()
  try {
    const { messages } = await getChat(cid)
    if (chat().cid === cid && !isStreaming(chat())) chat().setTurns(turnsFromHistory(messages))
  } catch {
    /* nothing saved, or the engine is restarting: start empty */
  }
}

export async function send(text: string): Promise<void> {
  const message = text.trim()
  if (!message || isStreaming(chat())) return
  chat().setInput('')
  const id = chat().startTurn(message)
  current = new AbortController()
  let finished = false
  try {
    await stream(
      '/chat',
      { conversation_id: chat().cid, message },
      {
        token: (d) =>
          chat().patchTurn(id, (t) => ({ text: t.text + (d as { text: string }).text })),
        tool_start: (d) => {
          const { name, args } = d as { name: string; args: ToolArgs }
          chat().addTool(id, { name, args })
        },
        tool_end: (d) =>
          chat().endTool(id, d as { name: string; ms: number; preview: string; live?: string }),
        replace: (d) => chat().patchTurn(id, () => ({ text: (d as { text: string }).text })),
        done: () => {
          finished = true
          chat().patchTurn(id, () => ({ streaming: false }))
        },
        error: (d) => {
          finished = true
          chat().patchTurn(id, () => ({
            streaming: false,
            error: (d as { message: string }).message
          }))
        }
      },
      current.signal
    )
    if (!finished) {
      chat().patchTurn(id, () => ({
        streaming: false,
        error: 'The answer stopped before it finished.'
      }))
    }
  } catch (err) {
    chat().patchTurn(id, () => ({
      streaming: false,
      error: errorMessage(err, 'Ask Sloth couldn’t reach the engine. Please try again.')
    }))
  } finally {
    current = null
  }
}

export function newConversation(): void {
  current?.abort()
  current = null
  chat().reset()
}
