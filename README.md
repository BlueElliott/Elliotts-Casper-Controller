# Elliott's Casper Controller

> Desktop application and web UI for managing CasparCG with NDI outputs and Singular.live graphics

[![Build Status](https://github.com/BlueElliott/Elliotts-Casper-Controller/actions/workflows/build.yml/badge.svg)](https://github.com/BlueElliott/Elliotts-Casper-Controller/actions)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A desktop application and web UI for launching CasparCG, managing 5 NDI output channels loaded with Singular.live HTML graphics, and monitoring everything from a browser-based multiviewer.

## Features

- **Desktop GUI** — Native Windows app with system tray support
- **One-click CasparCG launch** — Starts the server and loads all channels automatically
- **Per-channel restart buttons** — Recover a stuck NDI output without touching the others
- **Web-based Dashboard** — Live channel status, server controls, event log
- **Multiviewer** — All 5 Singular.live outputs in one browser window
- **Settings page** — Edit NDI names, URLs, video mode, ports — auto-regenerates `casparcg.config`

## Quick Start

### Windows Executable (Recommended)

1. Download `ElliotsCasperController.exe` from [Releases](https://github.com/BlueElliott/Elliotts-Casper-Controller/releases)
2. Double-click to run — no installation needed
3. Click **Start CasparCG** in the desktop window
4. Click **Open Web UI** or visit `http://localhost:5280`

### Python (pip)

```bash
pip install elliotts-casper-controller
python -m elliotts_casper_controller
```

### From Source

```bash
git clone https://github.com/BlueElliott/Elliotts-Casper-Controller.git
cd Elliotts-Casper-Controller
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m elliotts_casper_controller
```

## NDI Outputs

| Channel | NDI Name     | Source              |
|---------|-------------|---------------------|
| 1       | PCR3 GFXPVW | Singular.live GFXPVW |
| 2       | PCR3 GFX1   | Singular.live GFX1  |
| 3       | PCR3 GFX2   | Singular.live GFX2  |
| 4       | PCR3 GFX3   | Singular.live GFX3  |
| 5       | PCR3 GFX4   | Singular.live GFX4  |

All outputs are 1080p 25fps by default. Change via Settings → Video Mode.

## Configuration

Settings are stored in `elliotts_casper_config.json` and editable from the web Settings page.
`casparcg.config` is auto-generated — do not edit it manually.

## Building the Executable

```bash
pip install pyinstaller
pyinstaller ElliotsCasperController.spec
```

The `.exe` will be in `dist/`.

## Issues

Report bugs at: https://github.com/BlueElliott/Elliotts-Casper-Controller/issues
