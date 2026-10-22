import { create } from 'zustand'
import type { ChatTurn, ToolCall } from './lib/types'

const CID_KEY = 'sloth.cid'

function newId(): string {
  return crypto.randomUUID()
}

/** The conversation id survives restarts (IMPL M6.4); storage can be unavailable, so never rely on it. */
function storedCid(): string {
  try {
    const saved = localStorage.getItem(CID_KEY)
    if (saved) return saved
    const fresh = newId()
    localStorage.setItem(CID_KEY, fresh)
    return fresh
  } catch {
    return newId()
  }
}

interface ChatState {
  cid: string
  turns: ChatTurn[]
  /** What the input holds; the findings table can pre-fill it. */
  input: string
  /** Bumped to move focus to the input. */
  focusNonce: number
  setInput: (text: string) => void
  prefill: (text: string) => void
  setTurns: (turns: ChatTurn[]) => void
  startTurn: (user: string) => string
  patchTurn: (id: string, patch: (t: ChatTurn) => Partial<ChatTurn>) => void
  addTool: (id: string, call: ToolCall) => void
  endTool: (
    id: string,
    end: Required<Pick<ToolCall, 'name' | 'ms' | 'preview'>> & { live?: string }
  ) => void
  reset: () => void
}

export const useChat = create<ChatState>((set) => ({
  cid: storedCid(),
  turns: [],
  input: '',
  focusNonce: 0,
  setInput: (input) => set({ input }),
  prefill: (input) => set((s) => ({ input, focusNonce: s.focusNonce + 1 })),
  setTurns: (turns) => set({ turns }),
  startTurn: (user) => {
    const id = newId()
    set((s) => ({ turns: [...s.turns, { id, user, tools: [], text: '', streaming: true }] }))
    return id
  },
  patchTurn: (id, patch) =>
    set((s) => ({ turns: s.turns.map((t) => (t.id === id ? { ...t, ...patch(t) } : t)) })),
  addTool: (id, call) =>
    set((s) => ({
      turns: s.turns.map((t) => (t.id === id ? { ...t, tools: [...t.tools, call] } : t))
    })),
  endTool: (id, end) =>
    set((s) => ({
      turns: s.turns.map((t) => {
        if (t.id !== id) return t
        // The oldest unfinished call with this name is the one that just ended.
        const i = t.tools.findIndex((c) => c.name === end.name && c.ms === undefined)
        if (i < 0) return t
        const tools = t.tools.slice()
        tools[i] = { ...tools[i], ...end }
        return { ...t, tools }
      })
    })),
  reset: () => {
    const cid = newId()
    try {
      localStorage.setItem(CID_KEY, cid)
    } catch {
      /* storage unavailable: this session still gets a fresh conversation */
    }
    set({ cid, turns: [], input: '' })
  }
}))

export const isStreaming = (s: { turns: ChatTurn[] }): boolean => s.turns.some((t) => t.streaming)
