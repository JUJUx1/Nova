#!/data/data/com.termux/files/usr/bin/bash
# ─────────────────────────────────────────────────────────────────
#  NOVA PLAYER — Enhanced Termux Installer
# ─────────────────────────────────────────────────────────────────

CYAN='\033[96m'
MAG='\033[95m'
YEL='\033[93m'
GRN='\033[92m'
RED='\033[91m'
RST='\033[0m'

echo -e "${CYAN}Starting Nova Player Installation...${RST}"

# 1. Update Packages
echo -e "  ${CYAN}[1/6]${RST} Updating system packages..."
pkg update -y && pkg upgrade -y

# 2. Install System Dependencies
# mpv is required for playback, ffmpeg for recording
echo -e "  ${CYAN}[2/6]${RST} Installing mpv and ffmpeg..."
pkg install -y python mpv ffmpeg termux-api

# 3. Install Python Libraries
# Installing core and optional dependencies found in nova_player.py
echo -e "  ${CYAN}[3/6]${RST} Installing Python libraries (this may take a minute)..."
pip install --upgrade pip
pip install mutagen requests Pillow yt-dlp spotipy indic-transliteration

# 4. Setup Storage
# Required so the player can access your Music and Downloads folders
echo -e "  ${CYAN}[4/6]${RST} Setting up storage access..."
termux-setup-storage
sleep 2

# 5. Create Songs Directory
SONGS_DIR="$HOME/storage/downloads/songs"
mkdir -p "$SONGS_DIR"
echo -e "  ${GRN}✓${RST} Songs directory ready: ${YEL}$SONGS_DIR${RST}"

# 6. Install Script and Create Alias
# Moves the player to home and creates the 'nova' command
if [ -f "./nova_player.py" ]; then
    cp ./nova_player.py "$HOME/nova_player.py"
    chmod +x "$HOME/nova_player.py"
    
    # Add alias to .bashrc if it doesn't exist
    if ! grep -q "alias nova=" "$HOME/.bashrc"; then
        echo 'alias nova="python $HOME/nova_player.py"' >> "$HOME/.bashrc"
    fi
    echo -e "  ${GRN}✓${RST} Player installed. Use ${CYAN}nova${RST} to start."
else
    echo -e "  ${RED}✗ Error: nova_player.py not found in current directory.${RST}"
fi

echo -e "\n${GRN}Installation Complete!${RST}"
echo -e "Restart Termux or run ${YEL}source ~/.bashrc${RST} to use the ${CYAN}nova${RST} command."
