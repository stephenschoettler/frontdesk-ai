#!/bin/bash
# Start the Front Desk server with conda environment

# Initialize conda
eval "$($HOME/miniconda3/bin/conda shell.bash hook)"

# Activate the frontdesk environment
conda activate frontdesk

# Add local bin to PATH for supabase and ngrok
export PATH="$HOME/.local/bin:$PATH"

# Start the server
cd /home/w0lf/dev/frontdesk
python main.py
