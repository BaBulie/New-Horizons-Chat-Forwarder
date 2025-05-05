"""
    New Horizons Chat Forwarder.
    Forwards chat messages from Conan Exiles to a Discord webhook.

    Copyright © 2025 BaBulie

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import os
import sys
import json
import ctypes
import uvicorn
import requests
import argparse
from datetime import datetime
from termcolor import colored
from fastapi import FastAPI, Query


# --- Config Constants ---
CONFIG_FILE = "config.json"
WEBHOOK_PREFIX = "https://discord.com/api/webhooks/"


# --- Termcolor Helper ---
def colored_text(text_parts, colors):
    formatted_parts = [colored(part, color) for part, color in zip(text_parts, colors)]
    return "".join(formatted_parts)


# --- Config Functions ---
def load_config() -> str:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                data = json.load(f)
            return data.get("discord_webhook_url", "")
        except (ValueError, json.JSONDecodeError):
            pass
    return ""


def save_config(url: str) -> None:
    with open(CONFIG_FILE, "w") as f:
        json.dump({"discord_webhook_url": url}, f, indent=2)


def prompt_for_webhook() -> str:
    print(colored_text(["WARNING", ":  No valid Discord webhook URL found in config."],
                       ["yellow", "light_grey"]))
    while True:
        url = input("          Enter your Discord webhook URL: ").strip()
        if url.startswith(WEBHOOK_PREFIX):
            save_config(url)
            print(colored_text(["INFO", ":     Webhook URL saved to ", CONFIG_FILE, "."],
                       ["green", "light_grey", "light_magenta", "light_grey"]))
            return url
        print(colored_text(["WARNING", ":  Invalid URL. Must start with ", WEBHOOK_PREFIX, "...", " Please try again."],
                       ["yellow", "light_grey", "light_magenta", "light_magenta", "light_grey"]))


# --- FastAPI App Setup ---
app = FastAPI()

@app.get("/webhook")
async def forwarder(sender: str = Query(...), message: str = Query(...)):
    url = load_config()
    if not url.startswith(WEBHOOK_PREFIX):
        return {"status": "error", "detail": "Discord webhook not configured correctly."}
    
    timestamp = datetime.now().strftime("%H:%M")
    content = f"{timestamp} [**{sender}**]: `{message}`"
    try:
        resp = requests.post(url, json={"content": content})
        resp.raise_for_status()
    except Exception as e:
        return {"status": "error", "detail": str(e)}
    
    return {"status": "forwarded"}


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
                        "   Conan Exiles → Discord Chat Forwarder v1.0  \n",
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
    webhook_url = load_config()
    if not webhook_url.startswith(WEBHOOK_PREFIX):
        webhook_url = prompt_for_webhook()
    
    # Start the FastAPI server
    print(colored_text(["INFO", ":     Starting chat forwarder..."],
                       ["green", "light_grey"]))
    try:
        uvicorn.run(app, host=host, port=port, log_level="info")
    except OSError as e:
        print(colored_text(["ERROR", ":    ", e],
                           ["red", "light_grey", "light_grey"]))
    finally:
        input("Press Enter to exit...")


if __name__ == "__main__":
    main()
