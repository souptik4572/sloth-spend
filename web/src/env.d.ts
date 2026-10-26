/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Where the sign-up screen's "Terms" and "Privacy Policy" links go (set per deployment). */
  readonly VITE_TERMS_URL?: string
  readonly VITE_PRIVACY_URL?: string
}
