import { describe, expect, it } from 'vitest'
import { isEmail, passwordRules, strength } from './password'
import { initials } from './session'

const ok = (pw: string, email = 'asha@example.com'): boolean[] =>
  passwordRules(pw, email).map((r) => r.ok)

describe('password rules (same as engine/app/web/passwords.py)', () => {
  it('checks length, a number or symbol, and the email', () => {
    expect(ok('slow&steady2026')).toEqual([true, true, true])
    expect(ok('short1!')).toEqual([false, true, true])
    expect(ok('slowandsteadyforever')).toEqual([true, false, true])
    expect(ok('asha-likes-sloths-2026')).toEqual([true, true, false])
    expect(ok('al-likes-sloths-2026', 'al@example.com')).toEqual([true, true, true]) // < 3 letters: not checked
  })

  it('names the strength like the design', () => {
    expect(strength(passwordRules('slothsteadyy', 'asha@example.com')).label).toBe('Almost there')
    expect(strength(passwordRules('slow&steady2026', 'asha@example.com')).label).toBe('Strong')
    expect(strength(passwordRules('', 'asha@example.com')).label).toBe('Too weak')
  })
})

describe('small helpers', () => {
  it('accepts plausible emails only', () => {
    expect(isEmail(' asha@example.com ')).toBe(true)
    expect(isEmail('asha@example')).toBe(false)
    expect(isEmail('asha example.com')).toBe(false)
  })

  it('makes initials for the account button', () => {
    expect(initials('Asha Rao')).toBe('AR')
    expect(initials('  asha  ')).toBe('A')
    expect(initials('Mary Anne de la Cruz')).toBe('MC')
    expect(initials('')).toBe('?')
  })
})
