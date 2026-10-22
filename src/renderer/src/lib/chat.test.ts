import { describe, expect, it } from 'vitest'
import fixture from './__fixtures__/report.json'
import {
  SUGGESTED_PROMPTS,
  askAbout,
  draftTitle,
  followUps,
  formatCall,
  formatMs,
  matchSeries,
  parseDraft,
  splitDrafts,
  turnsFromHistory,
  unusedPrompts
} from './chat'
import type { ChatTurn, Report, StoredMessage } from './types'

const report = fixture as unknown as Report

const DRAFT = `Subject: Refund for duplicate IronTrap Fitness charge on Jul 6, 2026

Hello IronTrap Fitness team,

I was charged $49.99 twice in July, on Jul 5 and Jul 6, 2026. Please refund the Jul 6 charge.

Thank you,
[Your name]`

function turn(over: Partial<ChatTurn>): ChatTurn {
  return { id: 't', user: 'q', tools: [], text: '', streaming: false, ...over }
}

describe('tool badges', () => {
  it('writes calls Python-style, as in the design', () => {
    expect(formatCall('get_merchant', { merchant: 'IronTrap' })).toBe('get_merchant("IronTrap")')
    expect(
      formatCall('forecast_spend', { days: 30, exclude_merchants: ['StreamFlix UHD', 'WatchNest'] })
    ).toBe('forecast_spend(days=30, exclude_merchants=["StreamFlix UHD", "WatchNest"])')
    expect(formatCall('set_renewal_reminder', { merchant: 'CloudBox Pro', days_before: 3 })).toBe(
      'set_renewal_reminder("CloudBox Pro", days_before=3)'
    )
    expect(formatCall('get_report_overview', {})).toBe('get_report_overview()')
    expect(formatCall('set_renewal_reminder', { days_before: 3, merchant: 'IronTrap' })).toBe(
      'set_renewal_reminder("IronTrap", days_before=3)'
    )
  })
  it('times', () => {
    expect(formatMs(42)).toBe('42 ms')
    expect(formatMs(1400)).toBe('1.4 s')
  })
})

describe('drafts', () => {
  it('parses subject and body', () => {
    const d = parseDraft(DRAFT)!
    expect(d.subject).toBe('Refund for duplicate IronTrap Fitness charge on Jul 6, 2026')
    expect(d.body.startsWith('Hello IronTrap Fitness team,')).toBe(true)
    expect(parseDraft('Hello there')).toBeNull()
    expect(parseDraft('Subject: Hi\n\nTwo charges of **$49.99** on **Jul 5**.')?.body).toBe(
      'Two charges of $49.99 on Jul 5.'
    )
    expect(parseDraft('**Subject:** Please cancel my membership\n\nHi')?.subject).toBe(
      'Please cancel my membership'
    )
  })
  it('titles', () => {
    expect(draftTitle('Refund for duplicate charge')).toBe('Refund request')
    expect(draftTitle('Please cancel my IronTrap Fitness membership')).toBe('Cancellation request')
    expect(draftTitle('Request for a lower rate')).toBe('Negotiation email')
  })
  it('finds fenced drafts between prose', () => {
    const segs = splitDrafts(
      `Here’s a draft you can send.\n\n\`\`\`\n${DRAFT}\n\`\`\`\n\nI won’t send it.`
    )
    expect(segs.map((s) => s.kind)).toEqual(['markdown', 'draft', 'markdown'])
    expect(segs[1].text).toBe(DRAFT)
  })
  it('keeps code blocks that are not emails as markdown', () => {
    expect(splitDrafts('```\nSELECT 1\n```').map((s) => s.kind)).toEqual(['markdown'])
  })
  it('draws an unclosed fence while streaming', () => {
    const segs = splitDrafts('Sure.\n\n```\nSubject: Please cancel my sub')
    expect(segs[1]).toEqual({ kind: 'draft', text: 'Subject: Please cancel my sub' })
  })
  it('accepts an unfenced draft up to the sign-off', () => {
    const segs = splitDrafts(`Here you go:\n\n${DRAFT}\n\nCheck the dates first.`)
    expect(segs.map((s) => s.kind)).toEqual(['markdown', 'draft', 'markdown'])
    expect(segs[1].text.endsWith('[Your name]')).toBe(true)
  })
})

describe('conversation', () => {
  it('rebuilds turns from stored messages', () => {
    const rows: StoredMessage[] = [
      { id: 1, role: 'user', content: 'Why?', tool_name: null, tool_args: null, created_at: '' },
      {
        id: 2,
        role: 'tool',
        content: '{"merchant": "IronTrap Fitness"}',
        tool_name: 'get_merchant',
        tool_args: { merchant: 'IronTrap' },
        created_at: ''
      },
      {
        id: 3,
        role: 'assistant',
        content: 'Three flags.',
        tool_name: null,
        tool_args: null,
        created_at: ''
      },
      { id: 4, role: 'user', content: 'Thanks', tool_name: null, tool_args: null, created_at: '' }
    ]
    const turns = turnsFromHistory(rows)
    expect(turns).toHaveLength(2)
    expect(turns[0].tools[0]).toMatchObject({
      name: 'get_merchant',
      args: { merchant: 'IronTrap' }
    })
    expect(turns[0].text).toBe('Three flags.')
    expect(turns[1]).toMatchObject({ user: 'Thanks', text: '', streaming: false })
  })
  it('offers the suggestions not asked yet', () => {
    expect(unusedPrompts([])).toEqual(SUGGESTED_PROMPTS.slice(0, 3))
    const asked = turn({ user: SUGGESTED_PROMPTS[0] })
    expect(unusedPrompts([asked])).toEqual(SUGGESTED_PROMPTS.slice(1, 4))
  })
})

describe('follow-ups', () => {
  it('matches tool arguments to report merchants', () => {
    expect(matchSeries('irontrap', report.series)?.merchant).toBe('IronTrap Fitness')
    expect(matchSeries('Streamflix', report.series)?.merchant).toBe('StreamFlix UHD')
    expect(matchSeries('Nope', report.series)).toBeNull()
  })
  it('refund + reminder for IronTrap (D-Main)', () => {
    const t = turn({ tools: [{ name: 'get_merchant', args: { merchant: 'IronTrap' }, ms: 42 }] })
    expect(followUps(t, report).map((f) => f.label)).toEqual([
      'Draft refund request',
      'Remind me 3 days before'
    ])
    expect(followUps(t, report)[0].prompt).toBe(
      'Draft a refund request for the duplicate IronTrap Fitness charge.'
    )
  })
  it('names the merchant when an answer covers several', () => {
    const t = turn({
      tools: [
        { name: 'get_merchant', args: { merchant: 'Streamflix' } },
        { name: 'get_merchant', args: { merchant: 'WatchNest' } }
      ]
    })
    expect(followUps(t, report).map((f) => f.label)).toEqual([
      'Remind me 3 days before · StreamFlix UHD',
      'Remind me 3 days before · WatchNest'
    ])
  })
  it('negotiation for a bill; nothing already done in the turn', () => {
    const bill = turn({ tools: [{ name: 'get_merchant', args: { merchant: 'Metro Electric' } }] })
    expect(followUps(bill, report).map((f) => f.label)).toEqual(['Draft negotiation email'])
    const drafted = turn({
      tools: [
        { name: 'find_duplicate_charges', args: { merchant: 'IronTrap' } },
        { name: 'set_renewal_reminder', args: { merchant: 'IronTrap' } }
      ],
      text: '```\n' + DRAFT + '\n```'
    })
    expect(followUps(drafted, report)).toEqual([])
  })
  it('none while streaming, after an error, or without a report', () => {
    const t = turn({ tools: [{ name: 'get_merchant', args: { merchant: 'IronTrap' } }] })
    expect(followUps({ ...t, streaming: true }, report)).toEqual([])
    expect(followUps({ ...t, error: 'x' }, report)).toEqual([])
    expect(followUps(t, null)).toEqual([])
  })
  it('pre-fills Ask Sloth from a findings row', () => {
    const iron = report.series.find((s) => s.merchant === 'IronTrap Fitness')!
    const fresh = report.series.find((s) => s.flags.length === 0)!
    expect(askAbout(iron)).toBe('Why was IronTrap Fitness flagged?')
    expect(askAbout(fresh)).toBe(`Tell me about ${fresh.merchant}.`)
  })
})
