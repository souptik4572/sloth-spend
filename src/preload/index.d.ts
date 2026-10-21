import type { SlothBridge } from './index'

declare global {
  interface Window {
    sloth: SlothBridge
  }
}
