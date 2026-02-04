# Front Desk Setup Notes

## Environment Setup Complete ✓

Your Front Desk AI receptionist is now set up and ready to run!

### What Was Installed

1. **Miniconda** - Python environment manager (already installed)
2. **Conda Environment** - `frontdesk` environment with Python 3.11
3. **Python Dependencies** - All packages from requirements.txt
4. **Supabase CLI** - Installed to `~/.local/bin/supabase`
5. **ngrok** - Installed to `~/.local/bin/ngrok`

### Quick Start

#### Terminal 1: Start the Server

```bash
./start_server.sh
```

Or manually:

```bash
eval "$(~/miniconda3/bin/conda shell.bash hook)"
conda activate frontdesk
export PATH="$HOME/.local/bin:$PATH"
python main.py
```

The server will start on http://localhost:8000

#### Terminal 2: Start ngrok (for Twilio webhooks)

**First time setup:**
```bash
ngrok config add-authtoken <YOUR_NGROK_AUTHTOKEN>
```

**Then run:**
```bash
./start_ngrok.sh
```

Or manually:

```bash
export PATH="$HOME/.local/bin:$PATH"
ngrok http 8000
```

### Access the Web UI

Open your browser to: http://localhost:8000/static/index.html

### Important Notes

1. **Stripe Configuration** - You mentioned you still need to set up Stripe. The app will work without it, but billing features will be unavailable.

2. **Network/DNS Issues** - The app tried to sync pricing data from OpenRouter but couldn't reach it (likely network/DNS issue). The server starts anyway with a warning.

3. **Deprecated Warning** - There's a deprecation warning about `gotrue` package. This doesn't affect functionality but you may want to update to `supabase_auth` in the future.

4. **Code Fixes Applied**:
   - Removed deprecated `FrameSerializerType` import to work with pipecat 0.0.101
   - Added error handling for pricing sync to allow offline startup
   - Installed missing `gotrue` package

### Next Steps

1. **Configure ngrok authtoken** (if you haven't already)
2. **Set up Stripe** (when ready)
3. **Configure Twilio webhook** to point to your ngrok URL + `/voice`
4. **Test the simulator** at the web UI

### Useful Commands

**Check server is running:**
```bash
curl http://localhost:8000/static/index.html
```

**Activate conda environment manually:**
```bash
eval "$(~/miniconda3/bin/conda shell.bash hook)"
conda activate frontdesk
```

**Add tools to PATH:**
```bash
export PATH="$HOME/.local/bin:$PATH"
```

### Troubleshooting

If you get "command not found" errors for supabase or ngrok, make sure to run:
```bash
export PATH="$HOME/.local/bin:$PATH"
```

Or add this line to your `~/.bashrc` file to make it permanent.
