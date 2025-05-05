# New Horizons Local Chat Logger

This program will automatically save your local Conan Exiles chat logs by sending them to a discord channel that you designate for it.
Follow these steps for first-time setup:

## Step 1: Set up a Discord Server

Create a private discord server or use one you already have for personal use. Create a channel for your chat logs. You can choose to create multiple channels for multiple servers or characters.

Press the server name in the top left corner of the screen, and go to 'Server Settings'. Then go to 'integrations', click 'webhooks', and create a new webhook. Here you can choose which channel the messages are sent to; if you want to switch destinations for different characters in the future, do it here.

## Step 2: Set up the Chat Forwarder

Download the chat forwarder.

Move the chat forwarder to a folder where you won't lose it, and start it.

From the Discord Integrations window, copy the link of the Discord webhook and paste it into the chat forwarder. Press Enter.

### Step 2.1: Start with Windows (Optional)

Go to `C:\Users\USERNAME\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup`, right click, 'New', 'Shortcut', and create a shortcut that points to the chat forwarder. This makes sure that the chat forwarder launches with windows.

*You can also get to the startup folder by pressing WindowsKey+R and typing `shell:startup`.*

*It's also possible to right click-drag the chat forwarder to the Startup folder and choosing 'Create shortcuts here'.*

### Step 2.2: Start Minimized (Optional)

Right click the shortcut you just created, and go to 'Properties'. In 'Target:', add ` --minimized` after the string of text. The chat forwarder will now start minimized.

## Step 3: Set up Conan Exiles
In Conan Exiles, press ESC to bring up the pause menu. Go to the Sudo Player Panel on the right side of the screen.

Go to **Chat & UI Settings**.

On the right side of the screen, where it says 'Webhook', check 'Enable Webhook', and paste this URL:
`http://localhost:8000/webhook`

Press **Save Changes**.

You must keep the chat forwarder running for chat messages to be logged to discord.
If you want you can drag it to a different Windows Desktop with WindowsKey+Tab to keep it hidden from your taskbar if it bothers you.
