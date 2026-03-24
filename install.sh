#!/data/data/com.termux/files/usr/bin/bash
# ─────────────────────────────────────────────────────────────────
#  NOVA PLAYER — Professional Termux Installer
# ─────────────────────────────────────────────────────────────────

CYAN='\033[96m'
MAG='\033[95m'
YEL='\033[93m'
GRN='\033[92m'
RED='\033[91m'
RST='\033[0m'

echo -e "${CYAN}"
echo "  ███╗  ██╗ ██████╗ ██╗   ██╗ █████╗ "
echo "  ████╗ ██║██╔═══██╗██║   ██║██╔══██╗"
echo "  ██╔██╗██║██║   ██║╚██╗ ██╔╝███████║"
echo "  ██║╚████║╚██████╔╝  ╚███╔╝ ██║  ██║"
echo "  ╚═╝ ╚═══╝ ╚═════╝    ╚══╝  ╚═╝  ╚═╝"
echo -e "${RST}"
echo -e "  ${YEL}Nova Player Installer${RST}  —  Termux Music CLI"
echo "  ──────────────────────────────────────────"

# 1. System Updates & Core Packages
echo -e "  ${CYAN}[1/5]${RST} Installing core packages (mpv, ffmpeg)..."
pkg update -y && pkg install -y python mpv ffmpeg termux-api curl ncurses-utils

# 2. Python Dependencies
# We install yt-dlp first to ensure it handles YouTube's latest patches
echo -e "  ${CYAN}[2/5]${RST} Installing Python libraries..."
pip install --upgrade pip 2>/dev/null || true
pip install mutagen requests Pillow yt-dlp spotipy indic-transliteration

# 3. Storage Setup
echo -e "  ${CYAN}[3/5]${RST} Checking storage permissions..."
if [ ! -d "$HOME/storage" ]; then
    termux-setup-storage
    sleep 2
fi

# 4. Directory & Cookie Placeholder
# Creating a placeholder for cookies to help with the "Bot" error
SONGS_DIR="$HOME/storage/downloads/songs"
mkdir -p "$SONGS_DIR"
touch "$HOME/cookies.txt"
echo -e "  ${GRN}✓${RST}  Songs folder ready: ${YEL}${SONGS_DIR}${RST}"

# 5. Download Nova Player Core
SCRIPT_DEST="$HOME/nova_player.py"
echo -e "  ${CYAN}[4/5]${RST} Fetching latest Nova Player script..."

# If running locally, copy it; if via one-liner, download it
if [ -f "./nova_player.py" ]; then
    cp ./nova_player.py "$SCRIPT_DEST"
else
    curl -sL "https://raw.githubusercontent.com/JUJUx1/Nova/main/nova_player.py" -o "$SCRIPT_DEST"
fi
chmod +x "$SCRIPT_DEST"

# 6. Command Alias Configuration
RC="$HOME/.bashrc"
if ! grep -q "alias nova=" "$RC" 2>/dev/null; then
    echo 'alias nova="python $HOME/nova_player.py"' >> "$RC"
    echo -e "  ${GRN}✓${RST}  Alias ${CYAN}nova${RST} created"
fi

echo -e "  ${CYAN}[5/5]${RST} Finalizing installation..."
echo ""
echo -e "${GRN}  Installation Complete!${RST}"
echo -e "  ──────────────────────────────────────────"
echo -e "  1. Run: ${YEL}source ~/.bashrc${RST}"
echo -e "  2. Type: ${CYAN}nova${RST} to start."
echo ""
echo -e "${MAG}  NOTE:${RST} If you get a 'Bot' error while downloading,"
echo -e "  put your YouTube cookies in ${YEL}$HOME/cookies.txt${RST}"
echo ""
