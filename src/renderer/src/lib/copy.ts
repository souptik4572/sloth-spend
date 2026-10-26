// Sentences that differ between the desktop app and SlothSpend Web (WEB-IMPL W-D11: on the web, statements live
// in the person's private workspace on SlothSpend's server, and Gemma may be the Gemini API).
import { byPlatform } from './platform'

export const statementPrivacy = (): string =>
  byPlatform(
    'Your statement never leaves this computer.',
    'Your statement stays in your private workspace.'
  )
