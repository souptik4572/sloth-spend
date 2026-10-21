import { app } from 'electron'
import { spawn, execFileSync, type ChildProcess } from 'node:child_process'
import fs from 'node:fs'
import net from 'node:net'
import path from 'node:path'
import type { LogBuffer } from './logbuffer'

const isWin = process.platform === 'win32'
const isDev = !app.isPackaged

export interface RuntimeConfig {
  enginePort: number
  token: string
  dataDir: string
}

export function freePort(): Promise<number> {
  return new Promise((resolve, reject) => {
    const srv = net.createServer()
    srv.unref()
    srv.on('error', reject)
    srv.listen(0, '127.0.0.1', () => {
      const { port } = srv.address() as net.AddressInfo
      srv.close(() => resolve(port))
    })
  })
}

/** Dev: SLOTH_PYTHON, else engine/.venv if it exists, else the system interpreter. */
function devPython(engineDir: string): string {
  if (process.env.SLOTH_PYTHON) return process.env.SLOTH_PYTHON
  const venv = path.join(engineDir, '.venv', isWin ? 'Scripts/python.exe' : 'bin/python')
  if (fs.existsSync(venv)) return venv
  return isWin ? 'python' : 'python3'
}

function engineCommand(): { cmd: string; args: string[]; cwd?: string } {
  if (isDev) {
    const engineDir = path.join(app.getAppPath(), 'engine')
    return { cmd: devPython(engineDir), args: ['-m', 'app.main'], cwd: engineDir }
  }
  const exe = isWin ? 'slothspend-engine.exe' : 'slothspend-engine'
  return { cmd: path.join(process.resourcesPath, 'engine', exe), args: [] }
}

export function killTree(pid: number | undefined): void {
  if (!pid) return
  try {
    if (isWin) execFileSync('taskkill', ['/pid', String(pid), '/T', '/F'], { stdio: 'ignore' })
    else process.kill(pid, 'SIGTERM')
  } catch {
    /* already gone */
  }
}

export function startEngine(
  cfg: RuntimeConfig,
  secretsEnv: Record<string, string>,
  logs: LogBuffer
): ChildProcess {
  const { cmd, args, cwd } = engineCommand()
  logs.push(`[main] starting engine: ${cmd} ${args.join(' ')}\n`)
  const proc = spawn(cmd, args, {
    cwd,
    env: {
      ...process.env,
      ...secretsEnv,
      SLOTH_PORT: String(cfg.enginePort),
      SLOTH_TOKEN: cfg.token,
      SLOTH_DATA_DIR: cfg.dataDir,
      SLOTH_VERSION: app.getVersion(),
      TABPFN_MODEL_CACHE_DIR: path.join(cfg.dataDir, 'tabpfn-weights'),
      PYTHONUNBUFFERED: '1'
    },
    stdio: ['pipe', 'pipe', 'pipe'], // stdin stays open: EOF tells the engine its parent is gone
    windowsHide: true
  })
  const relay = (d: Buffer): void => {
    const text = d.toString()
    logs.push(text)
    process.stdout.write(`[engine] ${text}`)
  }
  proc.stdout?.on('data', relay)
  proc.stderr?.on('data', relay)
  proc.on('error', (err) => logs.push(`[main] could not start the engine: ${err.message}\n`))
  return proc
}

export async function stopEngine(proc: ChildProcess | null, cfg: RuntimeConfig): Promise<void> {
  if (!proc || proc.exitCode !== null) return
  try {
    await fetch(`http://127.0.0.1:${cfg.enginePort}/shutdown`, {
      method: 'POST',
      headers: { 'X-Sloth-Token': cfg.token },
      signal: AbortSignal.timeout(2000)
    })
  } catch {
    /* engine may already be down */
  }
  proc.stdin?.end()
  await new Promise<void>((resolve) => {
    if (proc.exitCode !== null) return resolve()
    const timer = setTimeout(resolve, 1500)
    proc.once('exit', () => {
      clearTimeout(timer)
      resolve()
    })
  })
  if (proc.exitCode === null) killTree(proc.pid)
}
