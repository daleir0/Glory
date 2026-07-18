#!/bin/bash
# Glory Daily tmux session
# Copy this to /mnt/e/Glory/glory-daily-start.sh in WSL

SESSION="glory-daily"
GLORY_DIR="/mnt/e/Glory"
VAULT_DIR="/mnt/e/Glory/Glory's Intellect/05 - Research"

tmux new-session -d -s $SESSION -x 220 -y 50

# Pane 0: Glory (top-left) — main work pane
tmux send-keys -t $SESSION:0.0 "cd $GLORY_DIR && echo 'Glory is ready.'" Enter

# Pane 1: Hermes (top-right)
tmux split-window -h -t $SESSION:0
tmux send-keys -t $SESSION:0.1 "cd ~/hermes-agent/hermes-agent-2026.4.30 && hermes gateway status" Enter

# Pane 2: Vault (bottom-left)
tmux split-window -v -t $SESSION:0.0
tmux send-keys -t $SESSION:0.2 "watch -n 30 ls -lt \"$VAULT_DIR\" | head -10" Enter

# Pane 3: Monitor (bottom-right)
tmux split-window -v -t $SESSION:0.1
tmux send-keys -t $SESSION:0.3 "watch -n 5 nvidia-smi --query-gpu=name,temperature.gpu,utilization.gpu,memory.used,memory.total --format=csv,noheader" Enter

# Focus on Glory pane
tmux select-pane -t $SESSION:0.0

tmux attach -t $SESSION
