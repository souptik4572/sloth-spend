Local-first subscription audit: finds recurring charges, price creep and double charges in a bank CSV,
entirely on your computer, with Gemma and TabPFN running locally.

## Download

| Platform                  | File                             |
| ------------------------- | -------------------------------- |
| macOS 13+ (Apple Silicon) | `SlothSpend-0.1.0-mac-arm64.dmg` |
| Windows 10/11 (x64)       | `SlothSpend-0.1.0-win-x64.exe`   |

`SHA256SUMS.txt` lists the checksum of each file.

## Before you start

1. Install [Ollama](https://ollama.com/download) **0.20 or newer** and open it.
2. Any Gemma model works. If you have none, SlothSpend offers to download `gemma4:e4b` (about 5 GB).
3. TabPFN v2 downloads automatically on first launch (about 70 MB, no account).

No data? **Demo data → Sample statement** loads 12 months of fictional charges.

## This is an unsigned build

- **macOS:** open the dmg and drag SlothSpend to Applications, then right-click it → **Open** the first time.
  If macOS says the app is damaged or can't be opened, run `xattr -cr /Applications/SlothSpend.app` once.
- **Windows:** SmartScreen may warn about an unknown publisher. Choose **More info → Run anyway**.

Full instructions and troubleshooting: [README](https://github.com/souptik4572/sloth-spend#install).
