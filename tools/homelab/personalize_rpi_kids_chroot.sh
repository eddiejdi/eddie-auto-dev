#!/usr/bin/env bash
set -euo pipefail

CHROOT_DIR="${1:-${CHROOT_DIR:-/var/tmp/rpi-kids-build/chroot}}"
PROFILE_USER="${PROFILE_USER:-pi}"
WALLPAPER="${KIDS_WALLPAPER:-/usr/share/rpd-wallpaper/balloon.jpg}"
USER_HOME="$CHROOT_DIR/home/$PROFILE_USER"
APPS_DIR="$CHROOT_DIR/usr/share/applications"
LOCAL_APPS_DIR="$USER_HOME/.local/share/applications"
DESKTOP_DIR="$USER_HOME/Desktop"
PANEL_DIR="$USER_HOME/.config/lxpanel/LXDE-pi/panels"
PCMANFM_DIR="$USER_HOME/.config/pcmanfm/LXDE-pi"
CHROMIUM_DIR="$USER_HOME/.config/chromium/Default"

log() {
  printf '[kids-ux] %s\n' "$*"
}

require_path() {
  if [ ! -e "$1" ]; then
    printf 'Missing required path: %s\n' "$1" >&2
    exit 1
  fi
}

copy_app_to_desktop() {
  local app_id="$1"
  local src="$APPS_DIR/$app_id"
  local dest="$DESKTOP_DIR/$app_id"

  if [ -f "$src" ]; then
    cp -f "$src" "$dest"
    chmod +x "$dest"
  else
    log "launcher not found, skipping: $app_id"
  fi
}

require_path "$CHROOT_DIR"
require_path "$USER_HOME"
require_path "$APPS_DIR"

log "Applying child-friendly desktop defaults in $CHROOT_DIR"

mkdir -p "$LOCAL_APPS_DIR" "$DESKTOP_DIR" "$PANEL_DIR" "$PCMANFM_DIR" "$CHROMIUM_DIR"

rm -f \
  "$DESKTOP_DIR/install-standard.desktop" \
  "$DESKTOP_DIR/install-express.desktop" \
  "$DESKTOP_DIR/pcmanfm.desktop" \
  "$DESKTOP_DIR/lxterminal.desktop"

cat > "$LOCAL_APPS_DIR/kids-videos.desktop" <<'EOF'
[Desktop Entry]
Version=1.0
Type=Application
Name=Videos para Criancas
Comment=Abrir videos infantis em tela cheia
Exec=chromium --no-first-run --start-maximized https://www.youtube.com/kids/
Icon=chromium
Terminal=false
Categories=Education;AudioVideo;
EOF

cat > "$LOCAL_APPS_DIR/kids-sites.desktop" <<'EOF'
[Desktop Entry]
Version=1.0
Type=Application
Name=Sites Educativos
Comment=Abrir atividades e jogos infantis no navegador
Exec=chromium --no-first-run --start-maximized https://www.pbskids.org/
Icon=applications-games
Terminal=false
Categories=Education;Game;
EOF

chmod +x "$LOCAL_APPS_DIR/"*.desktop

copy_app_to_desktop "org.kde.gcompris.desktop"
copy_app_to_desktop "org.kde.klettres.desktop"
copy_app_to_desktop "tuxpaint.desktop"
copy_app_to_desktop "tuxmath.desktop"
cp -f "$LOCAL_APPS_DIR/kids-videos.desktop" "$DESKTOP_DIR/"
cp -f "$LOCAL_APPS_DIR/kids-sites.desktop" "$DESKTOP_DIR/"

cat > "$PCMANFM_DIR/desktop-items-0.conf" <<EOF
[*]
wallpaper_mode=fit
wallpaper_common=1
wallpaper=$WALLPAPER
desktop_bg=#fff5cfd8a8b0
desktop_fg=#1f1f1f1f1f1f
desktop_shadow=#ffffffffffff
desktop_font=PibotoLt 16
show_wm_menu=0
sort=name;ascending;
show_documents=0
show_trash=0
show_mounts=0
EOF

cat > "$PANEL_DIR/panel" <<'EOF'
Global {
  edge=top
  align=left
  margin=0
  widthtype=percent
  width=100
  height=52
  transparent=0
  tintcolor=#ffffff
  alpha=0
  autohide=0
  setdocktype=1
  setpartialstrut=1
  usefontcolor=0
  fontsize=16
  usefontsize=1
  iconsize=44
  background=0
  point_at_menu=0
}
Plugin {
  type=menu
  Config {
    padding=8
    image=start-here
    system {
    }
    separator {
    }
    item {
      image=system-shutdown
      command=logout
    }
  }
}
Plugin {
  type=space
  Config {
    Size=8
  }
}
Plugin {
  type=launchbar
  Config {
    Button {
      id=org.kde.gcompris.desktop
    }
    Button {
      id=tuxpaint.desktop
    }
    Button {
      id=tuxmath.desktop
    }
    Button {
      id=org.kde.klettres.desktop
    }
    Button {
      id=chromium.desktop
    }
  }
}
Plugin {
  type=taskbar
  expand=1
  Config {
    tooltips=1
    IconsOnly=1
    ShowAllDesks=0
    UseMouseWheel=0
    FlatButton=1
    MaxTaskWidth=180
    spacing=2
    GroupedTasks=1
  }
}
Plugin {
  type=space
  Config {
    Size=6
  }
}
Plugin {
  type=volumepulse
  Config {
  }
}
Plugin {
  type=dclock
  Config {
    ClockFmt=%R
    TooltipFmt=%A %x
    BoldFont=1
    CenterText=1
  }
}
Plugin {
  type=ptbatt
  Config {
  }
}
EOF

touch "$USER_HOME/.config/chromium/First Run"
cat > "$CHROMIUM_DIR/Bookmarks" <<'EOF'
{
  "checksum": "",
  "roots": {
    "bookmark_bar": {
      "children": [
        {
          "date_added": "13350000000000000",
          "guid": "kids-videos",
          "id": "1",
          "name": "Videos para Criancas",
          "type": "url",
          "url": "https://www.youtube.com/kids/"
        },
        {
          "date_added": "13350000000000001",
          "guid": "gcompris-site",
          "id": "2",
          "name": "Atividades Educativas",
          "type": "url",
          "url": "https://gcompris.net/index-en.html"
        },
        {
          "date_added": "13350000000000002",
          "guid": "pbs-kids",
          "id": "3",
          "name": "Jogos Infantis",
          "type": "url",
          "url": "https://pbskids.org/"
        }
      ],
      "date_added": "13350000000000003",
      "date_modified": "13350000000000004",
      "guid": "bookmark_bar_root",
      "id": "4",
      "name": "Barra de favoritos",
      "type": "folder"
    },
    "other": {
      "children": [],
      "date_added": "13350000000000005",
      "date_modified": "0",
      "guid": "other_root",
      "id": "5",
      "name": "Outros favoritos",
      "type": "folder"
    },
    "synced": {
      "children": [],
      "date_added": "13350000000000006",
      "date_modified": "0",
      "guid": "synced_root",
      "id": "6",
      "name": "Favoritos do celular",
      "type": "folder"
    }
  },
  "version": 1
}
EOF

if chroot "$CHROOT_DIR" id "$PROFILE_USER" >/dev/null 2>&1; then
  chroot "$CHROOT_DIR" chown -R "$PROFILE_USER:$PROFILE_USER" "/home/$PROFILE_USER/.config" "/home/$PROFILE_USER/.local" "/home/$PROFILE_USER/Desktop"
fi

log "Child-friendly desktop customization complete for user '$PROFILE_USER'"
