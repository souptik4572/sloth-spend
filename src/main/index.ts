import { app, BrowserWindow, ipcMain, nativeTheme, shell } from 'electron'
import { randomBytes } from 'node:crypto'
import path from 'node:path'
import type { ChildProcess } from 'node:child_process'
import { optimizer } from '@electron-toolkit/utils'
import { freePort, startEngine, stopEngine, type RuntimeConfig } from './sidecars'
import { KeyError, clearPriorKey, hasPriorKey, secretsEnv, setPriorKey } from './secrets'
import { LogBuffer } from './logbuffer'
// Runtime icons (resources/ is shipped and asar-unpacked). Packaged builds take the app icon from
// build/icon.icns / build/icon.ico instead — see design/icons/README.md.
import windowIcon from '../../resources/icon.png?asset'
import devDockIcon from '../../resources/icon-macos.png?asset'

let cfg: RuntimeConfig
let engine: ChildProcess | null = null
let win: BrowserWindow | null = null
let quitting = false
const logs = new LogBuffer(200)

const OPEN_ALLOW = [
  /^https:\/\/slothspend\.tech/,
  /^https:\/\/ollama\.com/,
  /^https:\/\/platform\.priorlabs\.ai/,
  /^https:\/\/github\.com/
]

/** Spawns the engine and reports its exit to the renderer — unless it was replaced or we are quitting. */
function launchEngine(): void {
  const proc = startEngine(cfg, secretsEnv(), logs)
  engine = proc
  proc.on('exit', (code) => {
    logs.push(`[main] engine exited with code ${code}\n`)
    if (engine === proc && !quitting) win?.webContents.send('engine:exit', code)
  })
  // Spawn failures (missing interpreter or binary) emit 'error' and no 'exit'.
  proc.on('error', () => {
    if (engine === proc && !quitting) win?.webContents.send('engine:exit', null)
  })
}

async function boot(): Promise<void> {
  cfg = {
    enginePort: await freePort(),
    token: randomBytes(32).toString('hex'),
    dataDir: app.getPath('userData')
  }
  launchEngine()
}

function createWindow(): BrowserWindow {
  const w = new BrowserWindow({
    width: 1360,
    height: 860,
    minWidth: 1100,
    minHeight: 720,
    title: 'SlothSpend',
    show: false,
    autoHideMenuBar: true,
    // Windows and Linux show this in the title bar and taskbar; macOS uses the bundle icon.
    ...(process.platform === 'darwin' ? {} : { icon: windowIcon }),
    backgroundColor: nativeTheme.shouldUseDarkColors ? '#0B051D' : '#FFFFFF',
    webPreferences: {
      preload: path.join(__dirname, '../preload/index.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true
    }
  })
  w.once('ready-to-show', () => w.show())
  w.webContents.setWindowOpenHandler(() => ({ action: 'deny' }))
  w.webContents.on('will-navigate', (e) => e.preventDefault())
  if (process.env.ELECTRON_RENDERER_URL) w.loadURL(process.env.ELECTRON_RENDERER_URL)
  else w.loadFile(path.join(__dirname, '../renderer/index.html'))
  return w
}

app.whenReady().then(() => {
  if (process.platform === 'win32') app.setAppUserModelId('tech.slothspend.desktop') // Windows toasts
  // `npm run dev` runs the stock Electron.app; show the sloth in the Dock instead of the Electron logo.
  if (process.platform === 'darwin' && !app.isPackaged) app.dock?.setIcon(devDockIcon)
  // F12 opens DevTools in dev; Cmd/Ctrl+R reload is disabled in production.
  app.on('browser-window-created', (_, window) => optimizer.watchWindowShortcuts(window))
  const booting = boot()

  ipcMain.handle('config:get', async () => {
    await booting
    return {
      apiBase: `http://127.0.0.1:${cfg.enginePort}`,
      token: cfg.token,
      version: app.getVersion(),
      platform: process.platform
    }
  })
  ipcMain.handle('shell:open', (_e, url: string) => {
    if (typeof url === 'string' && OPEN_ALLOW.some((re) => re.test(url)))
      return shell.openExternal(url)
    return undefined
  })
  const restartEngine = async (): Promise<void> => {
    await booting
    const old = engine
    engine = null // its exit must not reach the renderer as a crash
    await stopEngine(old, cfg)
    launchEngine()
  }
  ipcMain.handle('engine:restart', restartEngine)

  // Prior Labs key (IMPL M4.12). The renderer can save, replace or remove it, and ask whether one is
  // saved — never read it back. Each change restarts the engine so TabPFN picks it up.
  ipcMain.handle('secrets:has', () => hasPriorKey())
  ipcMain.handle('secrets:set', async (_e, key: unknown) => {
    try {
      setPriorKey(key)
    } catch (err) {
      return {
        ok: false,
        error: err instanceof KeyError ? err.message : 'The key couldn’t be saved.'
      }
    }
    await restartEngine()
    return { ok: true }
  })
  ipcMain.handle('secrets:clear', async () => {
    clearPriorKey()
    await restartEngine()
    return { ok: true }
  })
  ipcMain.handle('engine:logs', () => logs.tail(20))
  ipcMain.handle('window:focus', () => {
    if (!win) return
    if (win.isMinimized()) win.restore()
    win.show()
    win.focus()
  })
  ipcMain.handle('window:bg', (_e, hex: string) => {
    if (typeof hex === 'string' && /^#[0-9a-f]{6}$/i.test(hex)) win?.setBackgroundColor(hex)
  })

  // Window first, so the Boot screen shows while the engine starts (spec §6.1).
  win = createWindow()
})

app.on('before-quit', (e) => {
  if (quitting) return
  e.preventDefault()
  quitting = true
  stopEngine(engine, cfg).finally(() => app.quit())
})

app.on('window-all-closed', () => app.quit())
