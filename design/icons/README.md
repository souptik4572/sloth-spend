# SlothSpend icons

Colours: pink `#FFA8CD`, midnight ink `#0B051D`, white `#FFFFFF`.
See `preview/icon-sheet.png` for everything at a glance, on light and dark.

This folder holds the **source artwork**. It is never packaged into the app. The files the app and
the website actually use live in the standard places for an electron-vite + electron-builder
project, listed below. Each file exists in exactly one place.

## Where everything lives

| Path | What | Used by |
|---|---|---|
| `build/icon.icns` | macOS app icon, 16–1024 px with Retina pairs, macOS icon grid | electron-builder (`buildResources: build`) for the `.app` and DMG |
| `build/icon.ico` | Windows icon, 16 / 24 / 32 / 48 / 64 / 128 / 256 px | electron-builder for the `.exe`, NSIS installer, taskbar and toast notifications |
| `build/icon.png` | 1024 px, macOS grid | electron-builder fallback |
| `resources/icon.png` | 512 px full-bleed tile (`app-icon-512.png`) | Runtime window icon on Windows and Linux (`BrowserWindow({ icon })`) |
| `resources/icon-macos.png` | 512 px on the macOS grid (`app-icon-macos-512.png`) | Dock icon during `npm run dev`, so the dev app shows the sloth instead of the Electron logo |
| `src/renderer/src/assets/brand/logo-mark.svg` | 36 px logo in every top bar | `components/brand/Logo.tsx` |
| `src/renderer/src/assets/mascot/sloth-hanging.svg` | Boot illustration, drawn for the pink hero | `components/brand/SlothHanging.tsx` |
| `src/renderer/src/assets/mascot/sloth-avatar.svg` | Ask Sloth avatar | `components/brand/Logo.tsx` → `SlothAvatar` |
| `src/renderer/src/assets/mascot/sloth-avatar-sleepy.svg` | Eyes-closed avatar for waiting / working states | `components/brand/Logo.tsx` → `SlothAvatarSleepy` |
| `site/favicon.ico`, `favicon.svg`, `apple-touch-icon.png`, `icon-192.png`, `icon-512.png` | slothspend.tech icons | `site/index.html` (M9) |
| `design/icons/` (here) | Masters, PNG exports, UI icon SVGs, preview sheet | Design tools, docs, the DEV write-up |

`resources/` only holds files the running app needs, because electron-builder packs it into the app
(`asarUnpack: resources/**`). That is why the source kit lives here instead.

## What's in this folder

```
app/
  app-icon.svg          Master app icon, full-bleed rounded tile (Windows, web, docs)
  app-icon-macos.svg    Same art on the macOS grid: 824 px tile on 1024 px + soft shadow
  app-icon-small.svg    Bolder, simpler cut for 16–32 px (no tuft, no smile, thicker ring)
  png/                  app-icon-{16…1024}.png and app-icon-macos-{16…1024}.png
brand/
  logo-mark-mono.svg    One-colour mark (currentColor) — docs, watermarks, a future tray icon
  png/                  logo-mark at 72 and 144 px
mascot/
  png/                  PNG exports of the hanging sloth and both avatars
ui/                     33 UI icons used in the screens — 24 px, 2 px stroke, currentColor
  icons.json            File → lucide-react component name → where it's used
  LICENSE-lucide.txt
preview/
  icon-sheet.png        Every icon on light and dark
```

The SVG masters for the logo mark and the mascots are the files under `src/renderer/src/assets/`.
Edit them there.

## Using them

**Rebuilding the app icons.** If the art changes, export new PNGs from `app/*.svg` into `app/png/`,
then rebuild `build/icon.icns` (`iconutil`) and `build/icon.ico` from those PNGs, and copy
`app-icon-512.png` / `app-icon-macos-512.png` to `resources/icon.png` / `resources/icon-macos.png`.

**Renderer UI icons.** Import the `lucide-react` components rather than the SVG files. `ui/icons.json`
lists the component for each icon (for example `circle-check.svg` → `<CircleCheck />`,
`ellipsis.svg` → `<Ellipsis />`, `triangle-alert.svg` → `<TriangleAlert />`). Use `size={20}`
(`16` in chips) and `strokeWidth={2}`. They inherit `currentColor`, so they follow light and dark mode.

**Landing page.**

```html
<link rel="icon" href="/favicon.ico" sizes="48x48">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
```

## Notes

- The app icon and the one-colour mark use long, slanted eye stripes so the face reads as a sloth
  rather than a panda at small sizes. The logo mark and the avatars keep the rounder eye patches
  the screens use.
- UI icons are from Lucide (ISC licence, `ui/LICENSE-lucide.txt`). Keep that file if you ship the
  SVGs. The sloth artwork is original to SlothSpend.
