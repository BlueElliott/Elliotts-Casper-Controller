"""Read/write app config and regenerate casparcg.config."""
import json
import os
from typing import List

DEFAULT_CONFIG = {
    "caspar_exe_path": "casparcg.exe",
    "amcp_port": 5250,
    "web_port": 5280,
    "startup_delay": 8,
    "video_mode": "1080p2500",
    "channels": [
        {"number": 1, "name": "GFXPVW", "ndi_name": "PCR3 GFXPVW", "url": "https://app.singular.live/output/66B4M4gG2cjcbEEP51ORwU/Output?aspect=16:9&g_custom1=GFXPVW"},
        {"number": 2, "name": "GFX1",   "ndi_name": "PCR3 GFX1",   "url": "https://app.singular.live/output/66B4M4gG2cjcbEEP51ORwU/Output?aspect=16:9&g_custom1=GFX1"},
        {"number": 3, "name": "GFX2",   "ndi_name": "PCR3 GFX2",   "url": "https://app.singular.live/output/66B4M4gG2cjcbEEP51ORwU/Output?aspect=16:9&g_custom1=GFX2"},
        {"number": 4, "name": "GFX3",   "ndi_name": "PCR3 GFX3",   "url": "https://app.singular.live/output/66B4M4gG2cjcbEEP51ORwU/Output?aspect=16:9&g_custom1=GFX3"},
        {"number": 5, "name": "GFX4",   "ndi_name": "PCR3 GFX4",   "url": "https://app.singular.live/output/66B4M4gG2cjcbEEP51ORwU/Output?aspect=16:9&g_custom1=GFX4"},
    ],
}

CONFIG_FILE = "elliotts_casper_config.json"
CASPAR_CONFIG_FILE = "casparcg.config"


def load() -> dict:
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            stored = json.load(f)
        config = dict(DEFAULT_CONFIG)
        config.update(stored)
        return config
    return dict(DEFAULT_CONFIG)


def save(config: dict) -> None:
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def regenerate_caspar_config(config: dict) -> None:
    channels_xml = ""
    for ch in config["channels"]:
        channels_xml += f"""
    <!-- Channel {ch['number']}: {ch['name']} -->
    <channel>
      <video-mode>{config['video_mode']}</video-mode>
      <consumers>
        <ndi>
          <name>{ch['ndi_name']}</name>
          <allow-fields>false</allow-fields>
        </ndi>
      </consumers>
    </channel>
"""
    xml = f"""<?xml version="1.0" encoding="utf-8"?>
<configuration>
  <log-level>info</log-level>

  <channels>
{channels_xml.rstrip()}
  </channels>

  <paths>
    <media-path>media\\</media-path>
    <log-path>log\\</log-path>
    <data-path>data\\</data-path>
    <template-path>template\\</template-path>
  </paths>

  <controllers>
    <tcp>
      <port>{config['amcp_port']}</port>
      <protocol>AMCP</protocol>
    </tcp>
  </controllers>

</configuration>
"""
    with open(CASPAR_CONFIG_FILE, "w", encoding="utf-8") as f:
        f.write(xml)
