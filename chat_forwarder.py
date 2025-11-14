# !/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
#
# New Horizons Chat Forwarder.
# Forwards chat messages from Conan Exiles to a Discord webhook.
#
# Copyright © 2025 BaBulie
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/gpl-3.0.txt>.

import os
import sys
import json
import time
import queue
import ctypes
import uvicorn
import requests
import argparse
import threading
from pathlib import Path
from datetime import datetime
from termcolor import colored
from fastapi import FastAPI, Query
from typing import Iterable, Optional


# --- Version ---
__version__ = "1.2"


# --- Config Constants ---
CONFIG_FILE = "config.json"
WEBHOOK_PREFIXES = (
    "https://discord.com/api/webhooks/",
    "https://discordapp.com/api/webhooks/",
)
USER_AGENT = f"NH-Chat-Forwader/{__version__} (+https://github.com/BaBulie/New-Horizons-Chat-Forwarder)"


# --- Cached runtime webhook URL ---
WEBHOOK_URL_CACHE: Optional[str] = None


# --- Termcolor Helper ---
def colored_text(text_parts, colors):
    formatted_parts = [colored(part, color) for part, color in zip(text_parts, colors)]
    return "".join(formatted_parts)


# --- Config Functions ---
def is_valid_webhook_prefix(url: str) -> bool:
    return any(url.startswith(prefix) for prefix in WEBHOOK_PREFIXES)


def get_webhook_url() -> str:
    global WEBHOOK_URL_CACHE
    if WEBHOOK_URL_CACHE is None:
        WEBHOOK_URL_CACHE = load_config()
    return WEBHOOK_URL_CACHE


def _config_candidates() -> Iterable[Path]:
    # Same folder as the executable
    try:
        if getattr(sys, "frozen", False):
            exe_dir = Path(sys.executable).resolve().parent
            yield exe_dir / CONFIG_FILE
    except Exception:
        pass
    yield Path(__file__).resolve().parent / CONFIG_FILE

    # %APPDATA%\New-Horizons-Chat-Forwarder\config.json
    appdata = os.getenv("APPDATA")
    if appdata:
        yield Path(appdata) / "New-Horizons-Chat-Forwarder" / CONFIG_FILE

    # User's home config
    yield Path.home() / ".config" / "new-horizons-chat-forwarder" / CONFIG_FILE


def load_config() -> str:
    for cfg_path in _config_candidates():
        try:
            print(colored_text(["INFO", ":     Checking config at ", str(cfg_path)],
                               ["green", "light_grey", "light_magenta"]))
            if cfg_path.exists():
                with open(cfg_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                url = data.get("discord_webhook_url", "")
                print(colored_text(["INFO", ":     Loaded config from ", str(cfg_path)],
                                   ["green", "light_grey", "light_magenta"]))
                return url
        except Exception as e:
            print(colored_text(["ERROR", ":    Failed to read ", str(cfg_path), " -> ", str(e)],
                               ["red", "light_grey", "light_grey", "light_grey", "light_grey"]))
    return ""


def save_config(url: str) -> None:
    last_exc = None
    for cfg_path in _config_candidates():
        try:
            parent = cfg_path.parent
            if not parent.exists():
                parent.mkdir(parents=True, exist_ok=True)
            with open(cfg_path, "w", encoding="utf-8") as f:
                json.dump({"discord_webhook_url": url}, f, ensure_ascii=False, indent=2)
            global WEBHOOK_URL_CACHE
            WEBHOOK_URL_CACHE = url
            print(colored_text(["INFO", ":     Webhook URL saved to ", str(cfg_path)],
                               ["green", "light_grey", "light_magenta"]))
            return
        except Exception as e:
            last_exc = e
            print(colored_text(["WARNING", ":  Could not write to ", str(cfg_path), " -> ", str(e)],
                               ["yellow", "light_grey", "light_magenta", "light_grey", "light_grey"]))
            continue

    # If nothing was writeable
    print(colored_text(["ERROR", ":    Failed to save config anywhere."],
                       ["red", "light_grey"]))
    if last_exc:
        print(colored_text(["ERROR", ":    Last error: ", str(last_exc)],
                           ["red", "light_grey", "light_grey"]))


def prompt_for_webhook() -> str:
    print(colored_text(["WARNING", ":  No valid Discord webhook URL found in config."],
                       ["yellow", "light_grey"]))
    while True:
        url = input("          Enter your Discord webhook URL: ").strip()
        if is_valid_webhook_prefix(url):
            save_config(url)
            return url
        print(colored_text(["WARNING", ":  Invalid URL. Must start with one of: ", "... ".join(WEBHOOK_PREFIXES), "...", " Please try again."],
                       ["yellow", "light_grey", "light_magenta", "light_magenta", "light_grey", "light_grey"]))


# --- Rate Limiting / Queueing ---
SEND_QUEUE: "queue.Queue[str]" = queue.Queue(maxsize=500)
WORKER_RUNNING = False
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": USER_AGENT})


def send_to_discord(url: str, content: str):
    try:
        resp = SESSION.post(url, json={"content": content}, timeout=10)
    except Exception as e:
        raise RuntimeError(f"request error: {e}")
    
    if resp.status_code == 429:
        retry_after = None
        header = resp.headers.get("Retry-After") or resp.headers.get("retry-after")

        if header is not None:
            try:
                retry_after = float(header)
            except Exception:
                retry_after = None
        if retry_after is None:
            try:
                retry_after = float(resp.json().get("retry_after", 1.0))
            except Exception:
                retry_after = 1.0
        
        time.sleep(max(retry_after, 0.5))
        resp = SESSION.post(url, json={"content": content}, timeout=10)

    resp.raise_for_status()

    reset_after = resp.headers.get("X-RateLimit-Reset-After")

    if reset_after is not None:
        try:
            return float(reset_after)
        except Exception:
            pass

    return None


def worker_loop():
    global WORKER_RUNNING
    WORKER_RUNNING = True
    base_spacing = 0.45     # ~5 req / 2s
    backoff = 0.0

    while WORKER_RUNNING:
        try:
            content = SEND_QUEUE.get(timeout=0.5)
        except queue.Empty:
            continue
        try:
            url = get_webhook_url()
            reset_after = send_to_discord(url, content)
            spacing = base_spacing
            if reset_after:
                spacing = max(spacing, reset_after)
            time.sleep(spacing)
            backoff = 0.0
        except Exception:
            backoff = min((backoff * 2) if backoff else 1.0, 30.0)
            time.sleep(backoff)
        finally:
            SEND_QUEUE.task_done()


# --- FastAPI App Setup ---
app = FastAPI()

@app.get("/webhook")
async def forwarder(sender: str = Query(...), message: str = Query(...)):
    url = get_webhook_url()
    if not is_valid_webhook_prefix(url):
        print(colored_text(["ERROR", ":    Discord webhook not configured correctly."],
                           ["red", "light_grey"]))
        return {"status": "error", "detail": "Discord webhook not configured correctly."}
    
    timestamp = datetime.now().strftime("%H:%M")
    clean_sender = str(sender).replace('`', "'")
    clean_message = str(message).replace('`', "'")
    max_message_length = 1800
    if len(clean_message) > max_message_length:
        clean_message = clean_message[:max_message_length - 1] + '...'

    content = f"{timestamp} [**{clean_sender}**]: `{clean_message}`"

    try:
        SEND_QUEUE.put_nowait(content)
    except queue.Full:
        print(colored_text(["ERROR", ":    Queue full! Message discarded."],
                           ["red", "light_grey"]))
        return {"status": "error", "detail": "Queue full! Message discarded."}
    
    return {"status": "queued"}


# --- Run minimized ---
def minimize_console():
    if sys.platform == "win32":
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            SW_MINIMIZE = 6
            ctypes.windll.user32.ShowWindow(hwnd, SW_MINIMIZE)


# --- Main Entrypoint ---
def main():
    # Welcome message
    print("""
                    #                    
                  ---+-                  
            -####-----+-####-            
         .##-###############-##+         
       .##+#########.#########.##-       
      ##.##########--.##########.##      
     #+###########-#...#############     
    #+###########+++....#############    
   ###########+-#+++...--.#########+#+   
   #+########+++-#+#-------###########   
 ##-#####-#-##-######-##+###-####-##-### 
 +#-+-###--#-+#####+#+#############--##+ 
   #+#####+#######++-#++++-##++--###+#   
   #######++##########++####+++++--+#+   
    ####.#####+##+++##++#++++#####+##    
     ###########-###################     
      ##++#+####+##+++#++###-###+##      
       +##+#-#####+++#+#####-++##        
          ###-#+###+++#++##-###          
             #####+++++#####             
                  +####                  
                    #                    
""")
    print(colored_text(["================================================\n",
                        f"   Conan Exiles → Discord Chat Forwarder v{__version__}  \n",
                        "================================================\n",
                        "Copyright © 2025 BaBulie - ABSOLUTELY NO WARRANTY. See LICENSE for details.\n"],
                       ["magenta", "cyan", "magenta", "light_grey"]))
    
    # Parse arguments
    parser = argparse.ArgumentParser(description="Forwards chat messages from Conan Exiles to a Discord webhook.")
    parser.add_argument("--host", default="127.0.0.1", help="Listen address")
    parser.add_argument("--port", type=int, default=8000, help="HTTP port")
    parser.add_argument("--minimized", action="store_true", help="Start the console minimized")
    args = parser.parse_args()

    host = args.host
    port = args.port
    if args.minimized:
        minimize_console()

    # Ensure webhook URL is set
    webhook_url = get_webhook_url()
    if not is_valid_webhook_prefix(webhook_url):
        webhook_url = prompt_for_webhook()
    
    # Start the background sender worker
    threading.Thread(target=worker_loop, daemon=True).start()

    # Start the FastAPI server
    print(colored_text(["INFO", ":     Starting chat forwarder..."],
                       ["green", "light_grey"]))
    
    try:
        uvicorn.run(app, host=host, port=port, log_level="info")
    except OSError as e:
        print(colored_text(["ERROR", ":    ", str(e)],
                           ["red", "light_grey", "light_grey"]))
    finally:
        input("Press Enter to exit...")


if __name__ == "__main__":
    main()
