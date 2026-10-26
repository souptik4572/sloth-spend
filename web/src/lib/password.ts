// The password rules from the sign-up and reset designs — the same three, in the same words, as the server
// (engine/app/web/passwords.py), which checks them again.

export interface Rule {
  label: string
  ok: boolean
}

export const MIN_LENGTH = 12

export function passwordRules(password: string, email: string): Rule[] {
  const local = (email.split('@')[0] ?? '').toLowerCase()
  return [
    { label: 'At least 12 characters', ok: password.length >= MIN_LENGTH },
    { label: 'A number or symbol', ok: /[0-9\W_]/.test(password) },
    {
      label: 'Doesn’t contain your email',
      ok: !(local.length >= 3 && password.toLowerCase().includes(local))
    }
  ]
}

export function strength(rules: Rule[]): { met: number; label: string } {
  const met = rules.filter((r) => r.ok).length
  return {
    met,
    label: met === rules.length ? 'Strong' : met === rules.length - 1 ? 'Almost there' : 'Too weak'
  }
}

export const isEmail = (value: string): boolean => /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(value.trim())
