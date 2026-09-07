#!/usr/bin/env bash
# نصب/به‌روزرسانی ابزارهای توسعه و MetaTrader 5 روی Ubuntu/Debian
# اجرا: bash install-dev-tools.sh
# نکته: رمز sudo عمداً در این فایل ذخیره نمی‌شود.

set -Eeuo pipefail
IFS=$'\n\t'

LOG_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/dev-tools-installer"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/install-$(date +%Y%m%d-%H%M%S).log"
exec > >(tee -a "$LOG_FILE") 2>&1

TMP_DIR="$(mktemp -d)"
cleanup() { rm -rf "$TMP_DIR"; }
SUDO_KEEPALIVE_PID=""
cleanup() {
    if [[ -n "$SUDO_KEEPALIVE_PID" ]]; then
        kill "$SUDO_KEEPALIVE_PID" 2>/dev/null || true
    fi
    rm -rf "$TMP_DIR"
}
trap cleanup EXIT

FAILED=()
SUDO=(sudo)

log() { printf '\n[%s] %s\n' "$(date '+%F %T')" "$*"; }
warn() { printf '[WARN] %s\n' "$*" >&2; }

on_error() {
    local rc=$? line=$1 cmd=$2
    warn "خطا در خط $line: $cmd (کد $rc)"
    return "$rc"
}
trap 'on_error "${LINENO}" "${BASH_COMMAND}"' ERR

run_step() {
    local name="$1"; shift
    log "$name"
    if "$@"; then
        log "موفق: $name"
    else
        local rc=$?
        warn "ناموفق: $name (کد $rc) — نصب بقیه ادامه پیدا می‌کند."
        FAILED+=("$name")
    fi
}

retry() {
    local attempts=4 delay=5 rc=0
    for ((i=1; i<=attempts; i++)); do
        "$@" && return 0 || rc=$?
        (( i < attempts )) && sleep "$delay"
        delay=$((delay * 2))
    done
    return "$rc"
}

apt_wait() {
    for ((i=1; i<=30; i++)); do
        if "$@"; then return 0; fi
        warn "apt در حال استفاده است؛ 10 ثانیه صبر می‌کنم..."
        sleep 10
    done
    return 1
}

require_supported_os() {
    [[ -r /etc/os-release ]] || { warn "/etc/os-release پیدا نشد."; return 1; }
    # shellcheck disable=SC1091
    source /etc/os-release
    [[ "${ID:-}" == "ubuntu" || "${ID_LIKE:-}" == *debian* ]] || {
        warn "این اسکریپت برای Ubuntu/Debian است: ${PRETTY_NAME:-ناشناخته}"; return 1;
    }
    log "سیستم: ${PRETTY_NAME:-ناشناخته} / $(uname -m)"
    [[ "$(uname -m)" == "x86_64" || "$(uname -m)" == "amd64" ]] || {
        warn "نسخه‌های دانلودی این اسکریپت برای x86_64 هستند."; return 1;
    }
}

prepare() {
    command -v sudo >/dev/null || { log "نصب sudo"; apt-get update; apt-get install -y sudo; }
    sudo -v
    # تمدید اعتبار sudo در زمان نصب‌های طولانی
    ( while true; do sudo -n -v 2>/dev/null || exit; sleep 50; done ) &
    SUDO_KEEPALIVE_PID=$!
    log "به‌روزرسانی فهرست بسته‌ها و خود سیستم"
    retry apt_wait "${SUDO[@]}" env DEBIAN_FRONTEND=noninteractive apt-get update
    retry apt_wait "${SUDO[@]}" env DEBIAN_FRONTEND=noninteractive apt-get -y upgrade
    retry apt_wait "${SUDO[@]}" env DEBIAN_FRONTEND=noninteractive apt-get install -y \
        ca-certificates curl wget gnupg lsb-release file tar xz-utils \
        unzip p7zip-full desktop-file-utils dbus-x11 software-properties-common \
        build-essential git python3 python3-pip python3-venv
}

install_chrome() {
    local deb="$TMP_DIR/google-chrome-stable.deb"
    retry curl -fL --retry 3 -o "$deb" \
        'https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb'
    "${SUDO[@]}" env DEBIAN_FRONTEND=noninteractive dpkg -i "$deb" || \
        apt_wait "${SUDO[@]}" env DEBIAN_FRONTEND=noninteractive apt-get -f install -y
    command -v google-chrome >/dev/null
}

install_vscode() {
    local deb="$TMP_DIR/code-stable-amd64.deb"
    retry curl -fL --retry 3 -o "$deb" \
        'https://code.visualstudio.com/sha/download?build=stable&os=linux-deb-x64'
    "${SUDO[@]}" env DEBIAN_FRONTEND=noninteractive dpkg -i "$deb" || \
        apt_wait "${SUDO[@]}" env DEBIAN_FRONTEND=noninteractive apt-get -f install -y
    command -v code >/dev/null
}

install_antigravity() {
    local page="$TMP_DIR/antigravity-download.html"
    local archive="$TMP_DIR/antigravity-ide.tar.gz"
    local url
    retry curl -fsSL 'https://antigravity.google/download' -o "$page"
    url="$(grep -oE 'https?[^" ]+linux-x64/Antigravity(%20| )IDE\.tar\.gz' "$page" | head -1)"
    [[ -n "$url" ]] || { warn "لینک x64 Antigravity از صفحه رسمی پیدا نشد."; return 1; }
    url="${url//&amp;/&}"
    retry curl -fL --retry 3 -o "$archive" "$url"
    gzip -t "$archive"
    "${SUDO[@]}" mkdir -p /opt/antigravity-ide
    "${SUDO[@]}" tar -xzf "$archive" --strip-components=1 -C /opt/antigravity-ide
    "${SUDO[@]}" chown -R root:root /opt/antigravity-ide
    "${SUDO[@]}" chmod 4755 /opt/antigravity-ide/chrome-sandbox
    "${SUDO[@]}" ln -sf /opt/antigravity-ide/antigravity-ide /usr/local/bin/antigravity
    cat >"$TMP_DIR/antigravity.desktop" <<'EOF'
[Desktop Entry]
Name=Google Antigravity
Comment=Agentic development environment
Exec=/usr/local/bin/antigravity %F
Icon=/opt/antigravity-ide/resources/app/resources/linux/code.png
Type=Application
Terminal=false
Categories=Development;IDE;
MimeType=text/plain;inode/directory;
EOF
    "${SUDO[@]}" install -m 644 "$TMP_DIR/antigravity.desktop" /usr/share/applications/antigravity.desktop
    command -v antigravity >/dev/null
}

install_mt5() {
    local setup="$TMP_DIR/mt5setup.exe"
    export WINEPREFIX="$HOME/.mt5"
    export WINEDEBUG=-all
    retry apt_wait "${SUDO[@]}" dpkg --add-architecture i386
    retry apt_wait "${SUDO[@]}" env DEBIAN_FRONTEND=noninteractive apt-get update
    retry apt_wait "${SUDO[@]}" env DEBIAN_FRONTEND=noninteractive apt-get install -y \
        --install-recommends wine wine32:i386 winetricks
    retry curl -fL --retry 3 -o "$setup" \
        'https://download.mql5.com/cdn/web/metaquotes.software.corp/mt5/mt5setup.exe'
    mkdir -p "$WINEPREFIX/drive_c"
    cp "$setup" "$WINEPREFIX/drive_c/mt5setup.exe"
    # این دو دستور روی دسکتاپ واقعی اجرا می‌شوند؛ در sandbox ممکن است محدود شوند.
    wineboot -u
    winecfg -v win11 || true
    wine "$WINEPREFIX/drive_c/mt5setup.exe" /auto
    local terminal="$WINEPREFIX/drive_c/Program Files/MetaTrader 5/terminal64.exe"
    [[ -f "$terminal" ]] || { warn "ترمینال MT5 هنوز در مسیر استاندارد پیدا نشد."; return 1; }
    cat >"$TMP_DIR/metatrader5" <<'EOF'
#!/bin/sh
set -eu
export WINEPREFIX="$HOME/.mt5"
export WINEDEBUG=-all
exec wine "$WINEPREFIX/drive_c/Program Files/MetaTrader 5/terminal64.exe" "$@"
EOF
    cat >"$TMP_DIR/metatrader5.desktop" <<'EOF'
[Desktop Entry]
Name=MetaTrader 5
Comment=MetaTrader 5 trading platform
Exec=/usr/local/bin/metatrader5 %F
Icon=wine
Type=Application
Terminal=false
Categories=Finance;Office;
EOF
    "${SUDO[@]}" install -m 755 "$TMP_DIR/metatrader5" /usr/local/bin/metatrader5
    "${SUDO[@]}" install -m 644 "$TMP_DIR/metatrader5.desktop" /usr/share/applications/metatrader5.desktop
}

finish() {
    "${SUDO[@]}" update-desktop-database /usr/share/applications 2>/dev/null || true
    printf '\n===== نتیجه =====\n'
    command -v google-chrome >/dev/null && echo 'OK  Chrome' || echo 'FAIL Chrome'
    command -v code >/dev/null && echo "OK  VS Code: $(code --version 2>/dev/null | head -1)" || echo 'FAIL VS Code'
    test -x /opt/antigravity-ide/antigravity-ide && echo 'OK  Antigravity' || echo 'FAIL Antigravity'
    test -x /usr/local/bin/metatrader5 && echo 'OK  MetaTrader launcher' || echo 'FAIL MetaTrader'
    if ((${#FAILED[@]})); then
        printf 'مراحل ناموفق: %s\n' "${FAILED[*]}"
        printf 'لاگ کامل: %s\n' "$LOG_FILE"
        return 1
    fi
    printf 'همه مراحل با موفقیت انجام شد. لاگ: %s\n' "$LOG_FILE"
}

main() {
    require_supported_os
    prepare
    run_step 'نصب/به‌روزرسانی Google Chrome' install_chrome
    run_step 'نصب/به‌روزرسانی Visual Studio Code' install_vscode
    run_step 'نصب/به‌روزرسانی Google Antigravity' install_antigravity
    run_step 'نصب Wine و MetaTrader 5' install_mt5
    finish
}

main "$@"
