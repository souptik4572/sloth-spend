import { describe, expect, it } from 'vitest'
import fixture from './__fixtures__/report.json'
import { followUps, reminderSetOn } from './chat'
import { relativeDay } from './format'
import { popupPlan } from './notify'
import type { ChatTurn, Notice, Phase, Reminder, Report } from './types'
import { needsYou, phaseView } from './ui-derive'

const report = fixture as unknown as Report
const TODAY = '2026-11-16'

function rem(phase: Phase, over: Partial<Reminder> = {}): Reminder {
  const group = (
    {
      REMINDED: 'needs_you',
      STILL_CHARGED: 'needs_you',
      WATCHING: 'watching',
      SNOOZED: 'watching'
    } as const
  )[phase as 'REMINDED']
  return {
    series_id: 1,
    merchant: 'TuneTide',
    amount: 11.99,
    cadence: 'monthly',
    monthly_equiv: 11.99,
    low_confidence: false,
    cancellable: true,
    next_due_date: '2026-11-19',
    days_left: 3,
    phase,
    group: group ?? (phase === 'AWAITING_STATEMENT' ? 'watching' : 'done'),
    detail: null,
    days_before: 3,
    remind_at: null,
    remind_on: null,
    reminders_sent: 0,
    max_reminders: 3,
    cancelled_on: null,
    events: [{ phase: 'WATCHING', at: '2026-10-15T12:00:00+00:00' }],
    checked: null,
    ...over
  }
}

describe('phaseView (IMPL M7.8 table)', () => {
  it('WATCHING: compact, days left in accent within a week', () => {
    const v = phaseView(
      rem('WATCHING', {
        merchant: 'WatchNest',
        amount: 9.99,
        next_due_date: '2026-11-20',
        days_left: 4
      }),
      'USD',
      TODAY
    )
    expect(v.layout).toBe('compact')
    expect(v.subline).toBe('$9.99 a month · renews Nov 20 · 4 days left')
    expect(v.badges).toEqual([{ label: '4 days left', variant: 'accent' }])
    expect(v.actions).toEqual(['keep', 'cancelled', 'stop'])
    expect(phaseView(rem('WATCHING', { days_left: 30 }), 'USD', TODAY).badges).toEqual([])
  })
  it('WATCHING, low confidence (charged once)', () => {
    const v = phaseView(
      rem('WATCHING', {
        merchant: 'CloudBox Pro',
        amount: 119.88,
        cadence: 'single',
        low_confidence: true,
        next_due_date: '2027-01-14',
        days_left: 59
      }),
      'USD',
      TODAY
    )
    expect(v.subline).toBe('$119.88 a year · likely renews Jan 14, 2027')
    expect(v.badges).toEqual([{ label: 'Low confidence', variant: 'dashed' }])
  })
  it('REMINDED: needs you, stepper on Reminded, snooze until the cap', () => {
    const r = rem('REMINDED', {
      reminders_sent: 1,
      detail: 'Renews Nov 19, 2026. Keep it, or cancel it yourself?',
      events: [
        { phase: 'WATCHING', at: '2026-10-15T12:00:00+00:00' },
        { phase: 'REMINDED', at: '2026-11-16T09:00:00+00:00' }
      ]
    })
    const v = phaseView(r, 'USD', TODAY)
    expect(v.layout).toBe('card')
    expect(v.badges.map((b) => b.label)).toEqual(['3 days left', 'Reminded · 1 of 3'])
    expect(v.steps!.map((s) => [s.label, s.sub, s.state])).toEqual([
      ['Watching', 'Oct 15', 'done'],
      ['Reminded', 'Today', 'current'],
      ['Kept / You cancelled', '', 'todo'],
      ['Verified', '', 'todo']
    ])
    expect(v.actions).toEqual(['cancelled', 'keep', 'snooze1', 'snooze3', 'howto', 'stop'])
    expect(phaseView({ ...r, reminders_sent: 3 }, 'USD', TODAY).actions).toEqual([
      'cancelled',
      'keep',
      'howto',
      'stop'
    ])
  })
  it('STILL_CHARGED: accent card, alert step, refund first (D-Reminders)', () => {
    const v = phaseView(
      rem('STILL_CHARGED', {
        merchant: 'IronTrap Fitness',
        amount: 49.99,
        next_due_date: '2026-11-05',
        cancelled_on: '2026-10-16',
        checked: { date: '2026-11-05', amount: 49.99 },
        events: [
          { phase: 'AWAITING_STATEMENT', at: '2026-10-16T12:00:00+00:00' },
          { phase: 'STILL_CHARGED', at: '2026-11-16T12:00:00+00:00' }
        ]
      }),
      'USD',
      TODAY
    )
    expect(v.tone).toBe('accent')
    expect(v.subline).toBe('$49.99 a month · renewed Nov 5')
    expect(v.badges).toEqual([{ label: 'Still charged', variant: 'solid', icon: 'alert' }])
    expect(v.steps!.map((s) => [s.label, s.sub, s.state])).toEqual([
      ['Watching', '', 'done'],
      ['Reminded', 'Skipped', 'skip'],
      ['You cancelled', 'Oct 16', 'done'],
      ['Still charged', 'Nov 5', 'alert']
    ])
    expect(v.message).toEqual({
      strong: 'Charged again on Nov 5, 2026 — $49.99',
      text: ', after you cancelled on Oct 16. Ask IronTrap Fitness for a refund; the draft is ready in Ask Sloth.'
    })
    expect(v.actions).toEqual(['refund', 'howto', 'stop'])
  })
  it('VERIFIED_STOPPED: outlined, saving in the copy', () => {
    const v = phaseView(
      rem('VERIFIED_STOPPED', {
        merchant: 'StreamFlix UHD',
        amount: 15.49,
        monthly_equiv: 15.49,
        next_due_date: '2026-11-12',
        cancelled_on: '2026-11-09',
        checked: { date: '2026-11-15', amount: null }
      }),
      'USD',
      TODAY
    )
    expect(v.tone).toBe('outlined')
    expect(v.subline).toBe('$15.49 a month · was due Nov 12')
    expect(v.steps![3]).toEqual({ label: 'Verified', sub: 'Nov 15', state: 'ok' })
    expect(v.message).toEqual({
      text: 'No StreamFlix UHD charge through Nov 15, after its Nov 12 renewal. ',
      saving: 'You’re saving $15.49 a month.'
    })
    expect(v.actions).toEqual([])
  })
  it('AWAITING_STATEMENT, SNOOZED and the ended phases', () => {
    const waiting = phaseView(
      rem('AWAITING_STATEMENT', { cancelled_on: '2026-10-16' }),
      'USD',
      TODAY
    )
    expect(waiting.badges[0].label).toBe('Waiting for your next statement')
    expect(waiting.actions).toEqual(['import', 'stop'])
    expect(phaseView(rem('SNOOZED', { reminders_sent: 2 }), 'USD', TODAY).badges[0].label).toBe(
      'Snoozed · 2 of 3'
    )
    for (const [phase, label] of [
      ['KEPT', 'Kept'],
      ['EXPIRED', 'Expired'],
      ['STOPPED', 'Stopped']
    ] as const) {
      const v = phaseView(rem(phase), 'USD', TODAY)
      expect([v.layout, v.badges[0].label, v.actions]).toEqual(['compact', label, ['again']])
    }
  })
  it('counts what needs you', () => {
    expect(needsYou([rem('REMINDED'), rem('STILL_CHARGED'), rem('WATCHING'), rem('KEPT')])).toBe(2)
  })
})

describe('chat and reminders', () => {
  const turn = (over: Partial<ChatTurn>): ChatTurn => ({
    id: 't',
    user: 'q',
    tools: [],
    text: '',
    streaming: false,
    ...over
  })
  it('the reminder chip shows only for a reminder that was set', () => {
    const ok =
      '{"merchant": "IronTrap Fitness", "reminder_set": true, "days_before": 3, "remind_on": "Nov 2, 2026"}'
    expect(reminderSetOn({ name: 'set_renewal_reminder', args: {}, preview: ok })).toBe(
      'Nov 2, 2026'
    )
    const no = '{"reminder_set": false, "error": "No new reminder was set"}'
    expect(reminderSetOn({ name: 'set_renewal_reminder', args: {}, preview: no })).toBeNull()
    expect(reminderSetOn({ name: 'get_merchant', args: {}, preview: ok })).toBeNull()
  })
  it('no "Remind me" follow-up when a reminder is already running', () => {
    const iron = report.series.find((s) => s.merchant === 'IronTrap Fitness')!
    const t = turn({ tools: [{ name: 'get_merchant', args: { merchant: 'IronTrap' } }] })
    expect(
      followUps(t, report, [rem('WATCHING', { series_id: iron.id })]).map((f) => f.label)
    ).toEqual(['Draft refund request'])
    expect(
      followUps(t, report, [rem('KEPT', { series_id: iron.id })]).map((f) => f.label)
    ).toContain('Remind me 3 days before')
  })
  it('imported today / yesterday / a date', () => {
    const now = new Date('2026-11-16T15:00:00')
    expect(relativeDay('2026-11-16T09:00:00', now)).toBe('today')
    expect(relativeDay('2026-11-15T23:00:00', now)).toBe('yesterday')
    expect(relativeDay('2026-11-09T10:00:00', now)).toBe('Nov 9')
  })
})

describe('pop-ups after an absence (WEB-IMPL W6)', () => {
  const notice = (id: number): Notice => ({
    id,
    series_id: 1,
    kind: 'reminder',
    title: `n${id}`,
    body: '',
    created_at: '2026-10-26T09:00:00Z',
    read_at: null
  })

  it('shows the newest three and counts the rest into one summary', () => {
    const plan = popupPlan([5, 1, 4, 2, 3].map(notice))
    expect(plan.show.map((n) => n.id)).toEqual([3, 4, 5])
    expect(plan.more).toBe(2)
  })

  it('shows a short burst as it is', () => {
    expect(popupPlan([notice(7)])).toEqual({ show: [notice(7)], more: 0 })
    expect(popupPlan([])).toEqual({ show: [], more: 0 })
  })
})
