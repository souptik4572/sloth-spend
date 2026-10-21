/** Keeps the last N engine log lines so the Boot screen can show them when the engine stops. */
export class LogBuffer {
  private lines: string[] = []
  private partial = ''

  constructor(private readonly max = 200) {}

  push(chunk: string): void {
    const parts = (this.partial + chunk).split(/\r?\n/)
    this.partial = parts.pop() ?? ''
    for (const line of parts) if (line.trim()) this.lines.push(line)
    if (this.lines.length > this.max) this.lines.splice(0, this.lines.length - this.max)
  }

  tail(n = 20): string[] {
    const all = this.partial.trim() ? [...this.lines, this.partial] : this.lines
    return all.slice(-n)
  }
}
