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

echo ""
echo -e "${CYAN}  ███╗  ██╗ ██████╗ ██╗   ██╗ █████╗ ${RST}"
echo -e "${MAG}  ████╗ ██║██╔═══██╗██║   ██║██╔══██╗${RST}"
echo -e "${CYAN}  ██╔██╗██║██║   ██║╚██╗ ██╔╝███████║${RST}"
echo -e "${MAG}  ██║╚████║╚██████╔╝  ╚███╔╝ ██║  ██║${RST}"
echo -e "${YEL}  ╚═╝ ╚═══╝ ╚═════╝    ╚══╝  ╚═╝  ╚═╝${RST}"
echo ""
echo -e "  ${YEL}Nova Player Installer${RST}  —  Termux Music CLI"
echo ""

# 1. Update and Install System Dependencies
# Added ffmpeg for video recording and termux-api for system integration
echo -e "  ${CYAN}[1/5]${RST} Installing system packages (mpv, ffmpeg)..."
pkg update -y && pkg install -y python mpv ffmpeg termux-api curl

# 2. Install Python Libraries
# Includes yt-dlp for downloading and Pillow for the visualizer
echo -e "  ${CYAN}[2/5]${RST} Installing Python libraries..."
pip install --upgrade pip
pip install mutagen requests Pillow yt-dlp spotipy indic-transliteration

# 3. Setup Storage
# Ensures the player can access the phone's storage
echo -e "  ${CYAN}[3/5]${RST} Requesting storage access..."
termux-setup-storage
sleep 2

# 4. Create Songs Directory
# Matches the paths expected by the player
SONGS_DIR="$HOME/storage/downloads/songs"
mkdir -p "$SONGS_DIR"
echo -e "  ${GRN}✓${RST}  Songs folder ready: ${YEL}${SONGS_DIR}${RST}"

# 5. Download & Install Player Script
# If the user is using the one-liner, we fetch the script from your repo
SCRIPT_DEST="$HOME/nova_player.py"
echo -e "  ${CYAN}[4/5]${RST} Downloading Nova Player..."

if [ -f "./nova_player.py" ]; then
    cp ./nova_player.py "$SCRIPT_DEST"
else
    curl -sL "https://raw.githubusercontent.com/JUJUx1/Nova/main/nova_player.py" -o "$SCRIPT_DEST"
fi
chmod +x "$SCRIPT_DEST"

# 6. Add Command Alias
RC="$HOME/.bashrc"
if ! grep -q "alias nova=" "$RC" 2>/dev/null; then
  echo 'alias nova="python $HOME/nova_player.py"' >> "$RC"
  echo -e "  ${GRN}✓${RST}  Alias ${CYAN}nova${RST} added"
fi

echo ""
echo -e "${GRN}Installation Complete!${RST}"
echo -e "Restart Termux or run: ${YEL}source ~/.bashrc${RST}"
echo -e "Then type ${CYAN}nova${RST} to start playing."
