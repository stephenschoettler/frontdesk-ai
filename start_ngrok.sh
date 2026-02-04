#!/bin/bash
# Start ngrok tunnel for development
# Make sure to configure ngrok with your authtoken first:
# ngrok config add-authtoken <YOUR_NGROK_AUTHTOKEN>

export PATH="$HOME/.local/bin:$PATH"
ngrok http 8000
