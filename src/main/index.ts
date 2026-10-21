import { app, BrowserWindow, nativeTheme } from 'electron'
import path from 'node:path'
import { optimizer } from '@electron-toolkit/utils'

// M0: window only. The engine sidecar, IPC and lifecycle arrive in M1 (spec §6).

function createWindow(): void {
  const win = new BrowserWindow({
    width: 1360,
    height: 860,
    minWidth: 1100,
    minHeight: 720,
    title: 'SlothSpend',
    show: false,
    autoHideMenuBar: true,
    backgroundColor: nativeTheme.shouldUseDarkColors ? '#0B051D' : '#FFFFFF',
    webPreferences: {
      preload: path.join(__dirname, '../preload/index.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true
    }
  })
  win.once('ready-to-show', () => win.show())
  win.webContents.setWindowOpenHandler(() => ({ action: 'deny' }))
  win.webContents.on('will-navigate', (e) => e.preventDefault())

  if (process.env.ELECTRON_RENDERER_URL) win.loadURL(process.env.ELECTRON_RENDERER_URL)
  else win.loadFile(path.join(__dirname, '../renderer/index.html'))
}

app.whenReady().then(() => {
  if (process.platform === 'win32') app.setAppUserModelId('tech.slothspend.desktop')
  // F12 opens DevTools in dev; Cmd/Ctrl+R reload is disabled in production.
  app.on('browser-window-created', (_, window) => optimizer.watchWindowShortcuts(window))
  createWindow()
})

app.on('window-all-closed', () => app.quit())
