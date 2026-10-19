#!/usr/bin/env bash
# RetroForge OS image builder.
#
#   sudo ./build.sh <profile> [--bundle] [--size 4G] [--out DIR]
#
# Profiles: see os/profiles/*.conf (pc-x86_64, pc-i686, arm64-uefi, rpi-arm64,
# rpi-armhf, riscv64). Runs on any Debian/Ubuntu host (or in the provided
# Dockerfile); foreign architectures are built through qemu-user-static/binfmt.
#
# Host packages: mmdebstrap qemu-user-static binfmt-support dosfstools exfatprogs
#                e2fsprogs fdisk grub-pc-bin grub-efi-amd64-bin curl python3 rsync
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$(cd "$HERE/.." && pwd)"
PROFILE="${1:?Profil angeben, z. B. pc-x86_64}"; shift || true
BUNDLE=0; IMG_SIZE=""; OUT="$HERE/out"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --bundle) BUNDLE=1 ;;
    --size) IMG_SIZE="$2"; shift ;;
    --out) OUT="$2"; shift ;;
    *) echo "unbekannte Option $1"; exit 2 ;;
  esac; shift
done

[[ $EUID -eq 0 ]] || { echo "Bitte als root ausführen (loop devices, chroot)."; exit 1; }
# shellcheck source=/dev/null
source "$HERE/profiles/$PROFILE.conf"
VERSION="$(python3 -c "import sys; sys.path.insert(0,'$SRC'); import retroforge; print(retroforge.__version__)")"
WORK="$HERE/build/$PROFILE"; ROOT="$WORK/rootfs"
mkdir -p "$WORK" "$OUT"
log() { printf '\033[1;35m[retroforge]\033[0m %s\n' "$*"; }
list() { for l in "$@"; do grep -vE '^\s*(#|$)' "$HERE/packages/$l.list"; done | tr '\n' ' '; }

# ---------------------------------------------------------------------------
log "1/6 Basis-System ($SUITE/$ARCH) mit mmdebstrap"
rm -rf "$ROOT"
KEYOPTS=()
if [[ -n "${EXTRA_KEY_URL:-}" ]]; then
  curl -fsSL "$EXTRA_KEY_URL" | gpg --dearmor > "$WORK/extra.gpg"
  KEYOPTS+=(--keyring="$WORK/extra.gpg")
  KEYOPTS+=(--setup-hook="mkdir -p \"\$1/usr/share/keyrings\"; cp $WORK/extra.gpg \"\$1/usr/share/keyrings/raspberrypi-archive-keyring.gpg\"")
fi
if [[ -n "${RASPBIAN_KEY_URL:-}" ]]; then
  curl -fsSL "$RASPBIAN_KEY_URL" | gpg --dearmor > "$WORK/raspbian.gpg"
  KEYOPTS+=(--keyring="$WORK/raspbian.gpg")
fi
COMPONENTS="main contrib non-free non-free-firmware"
[[ "$MIRROR" == *raspbian* ]] && COMPONENTS="main contrib non-free rpi"
mmdebstrap --architectures="$ARCH" --variant=minbase --components="$COMPONENTS" \
  --include="systemd,systemd-sysv,apt,ca-certificates,locales" "${KEYOPTS[@]}" \
  "$SUITE" "$ROOT" "deb $MIRROR $SUITE $COMPONENTS" ${EXTRA_REPO:+"$EXTRA_REPO"}

# ---------------------------------------------------------------------------
log "2/6 Pakete, Kernel & Treiber"
mount --bind /dev "$ROOT/dev"; mount -t proc proc "$ROOT/proc"; mount -t sysfs sys "$ROOT/sys"
cleanup() { umount -lf "$ROOT/dev" "$ROOT/proc" "$ROOT/sys" 2>/dev/null || true; [[ -n "${LOOP:-}" ]] && losetup -d "$LOOP" 2>/dev/null || true; }
trap cleanup EXIT
cat > "$ROOT/tmp/install.sh" <<'EOS'
#!/bin/bash
# best-effort install: whole list first, then package by package (names differ between suites)
set -u
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
inst() { apt-get install -y -q --no-install-recommends "$@" >/dev/null 2>&1 && return 0
         for p in "$@"; do apt-get install -y -q --no-install-recommends "$p" >/dev/null 2>&1 || echo "  übersprungen: $p"; done; }
inst $1
EOS
chmod +x "$ROOT/tmp/install.sh"
BOOTPKGS=""
case "$BOOT" in
  grub-hybrid)    BOOTPKGS="grub-pc-bin grub-efi-amd64-bin grub-efi-ia32-bin grub2-common initramfs-tools" ;;
  grub-hybrid32)  BOOTPKGS="grub-pc-bin grub-efi-ia32-bin grub2-common initramfs-tools" ;;
  grub-efi-arm64) BOOTPKGS="grub-efi-arm64-bin grub2-common initramfs-tools" ;;
  grub-efi-riscv64) BOOTPKGS="grub-efi-riscv64-bin grub2-common initramfs-tools" ;;
  rpi)            BOOTPKGS="initramfs-tools" ;;
esac
NVPKGS=""
[[ "${NVIDIA:-0}" == 1 ]] && NVPKGS="nvidia-open-kernel-dkms nvidia-driver firmware-nvidia-gsp linux-headers-amd64"
for group in "$KERNEL $BOOTPKGS" "$(list $PACKAGE_LISTS)" "$NVPKGS" "$(list ${OPTIONAL_LISTS:-})"; do
  [[ -n "${group// }" ]] && chroot "$ROOT" /tmp/install.sh "$group"
done

# ---------------------------------------------------------------------------
log "3/6 RetroForge installieren & System konfigurieren"
rsync -a "$HERE/rootfs/" "$ROOT/"
mkdir -p "$ROOT/opt/retroforge"
rsync -a --delete --exclude '__pycache__' --exclude userdata \
  "$SRC/retroforge" "$SRC/themes" "$SRC/plugins" "$SRC/pyproject.toml" "$ROOT/opt/retroforge/"
echo "RETROFORGE_VERSION=$VERSION PROFILE=$PROFILE BUILD=$(date -u +%Y%m%d)" > "$ROOT/etc/retroforge-release"
chroot "$ROOT" /bin/bash -e <<EOS
echo retroforge > /etc/hostname
printf '127.0.1.1\tretroforge retroforge.local\n' >> /etc/hosts
sed -i 's/^# *de_DE.UTF-8/de_DE.UTF-8/; s/^# *en_US.UTF-8/en_US.UTF-8/' /etc/locale.gen && locale-gen >/dev/null
echo 'LANG=de_DE.UTF-8' > /etc/default/locale
id rf >/dev/null 2>&1 || useradd -m -u 1000 -s /bin/bash -G input,video,render,audio,plugdev,bluetooth rf || \
  useradd -m -u 1000 -s /bin/bash -G input,video,audio rf
passwd -d rf >/dev/null
echo 'rf ALL=(root) NOPASSWD: /usr/local/sbin/retroforge-*' > /etc/sudoers.d/retroforge
chmod 440 /etc/sudoers.d/retroforge
chmod +x /usr/local/bin/* /usr/local/sbin/*
systemctl enable retroforge.service retroforge-firstboot.service retroforge-gpu.service >/dev/null
systemctl disable getty@tty1.service ssh.service >/dev/null 2>&1 || true
systemctl mask systemd-networkd-wait-online.service NetworkManager-wait-online.service >/dev/null 2>&1 || true
python3 -m compileall -q /opt/retroforge/retroforge
apt-get clean
rm -rf /var/lib/apt/lists/* /usr/share/doc/* /usr/share/man/* /tmp/install.sh
EOS
# trim locales to de/en (saves ~100 MB)
find "$ROOT/usr/share/locale" -mindepth 1 -maxdepth 1 ! -name 'de*' ! -name 'en*' ! -name 'locale.alias' -exec rm -rf {} + || true

# ---------------------------------------------------------------------------
log "4/6 userdata-Vorlage$([[ $BUNDLE == 1 ]] && echo " + gebündelte Emulatoren")"
SKEL="$ROOT/usr/share/retroforge/userdata-skel"
mkdir -p "$SKEL"/{roms,bios,saves,states,screenshots,music,themes,plugins,emulators,import,bezels,shaders}
python3 - "$SRC" "$SKEL" <<'EOP'
import sys; sys.path.insert(0, sys.argv[1])
from retroforge.builtin.systems import SYSTEMS
from pathlib import Path
for s in SYSTEMS:
    d = Path(sys.argv[2], "roms", s.id); d.mkdir(parents=True, exist_ok=True)
    (d / "_info.txt").write_text(f"{s.name} ({s.maker}, {s.year})\nDateitypen: {' '.join(s.exts)}\n"
                                 + (f"BIOS: {', '.join(s.bios)}\n" if s.bios else ""), encoding="utf-8")
EOP
if [[ $BUNDLE == 1 ]]; then
  RETROFORGE_HOME="$SKEL" python3 - "$SRC" "$FAMILY" <<'EOP'
import sys; sys.path.insert(0, sys.argv[1])
from retroforge.core import Core
c = Core().boot(do_probe=False, scan=False)
c.hw.family = sys.argv[2]
for e in c.registry.all("emulator"):
    if c.emus.can_install(e) and not c.emus.installed(e):
        try:
            print("  bündle", e.name); c.emus.install(e)
        except Exception as ex:
            print("  übersprungen", e.name, ex)
EOP
  rm -rf "$SKEL/system"
fi

# ---------------------------------------------------------------------------
log "5/6 Image erzeugen"
ROOT_MB=$(( $(du -sm "$ROOT" | cut -f1) * 115 / 100 + 200 ))
DATA_MB=512                                 # grows to the whole disk on first boot
BOOT_MB=256
TOTAL_MB=$(( 2 + BOOT_MB + ROOT_MB + DATA_MB + 2 ))
[[ -n "$IMG_SIZE" ]] && TOTAL_MB=$(( $(numfmt --from=iec "$IMG_SIZE") / 1048576 ))
IMG="$OUT/retroforge-$VERSION-$PROFILE.img"
rm -f "$IMG"; truncate -s "${TOTAL_MB}M" "$IMG"
if [[ "$BOOT" == rpi ]]; then
  # MBR: the Raspberry Pi boot ROM only reads FAT on an MBR disk
  sfdisk -q "$IMG" <<EOF
label: dos
start=8MiB, size=${BOOT_MB}MiB, type=c, bootable
size=${ROOT_MB}MiB, type=83
type=7
EOF
else
  sfdisk -q "$IMG" <<EOF
label: gpt
start=1MiB, size=1MiB, type=21686148-6449-6E6F-744E-656564454649, name=bios
size=${BOOT_MB}MiB, type=C12A7328-F81F-11D2-BA4B-00A0C93EC93B, name=RF-BOOT
size=${ROOT_MB}MiB, type=0FC63DAF-8483-4772-8E79-3D69D8477DE4, name=RF-ROOT
type=EBD0A0A2-B9E5-4433-87C0-68B6B72699C7, name=RETROFORGE
EOF
fi
LOOP=$(losetup --show -fP "$IMG")
if [[ "$BOOT" == rpi ]]; then P_BOOT=${LOOP}p1; P_ROOT=${LOOP}p2; P_DATA=${LOOP}p3
else P_BOOT=${LOOP}p2; P_ROOT=${LOOP}p3; P_DATA=${LOOP}p4; fi
mkfs.vfat -F 32 -n RF-BOOT "$P_BOOT" >/dev/null
mkfs.ext4 -q -L RF-ROOT -O ^has_journal -m 0 "$P_ROOT"   # no journal: fewer writes on SD cards
mkfs.exfat -L RETROFORGE "$P_DATA" >/dev/null
MNT="$WORK/mnt"; mkdir -p "$MNT"
mount "$P_ROOT" "$MNT"
rsync -aHAX "$ROOT/" "$MNT/"
mkdir -p "$MNT/boot/efi" "$MNT/userdata"
mount "$P_DATA" "$MNT/userdata"; rsync -rt "$SKEL/" "$MNT/userdata/"; touch "$MNT/userdata/.rf-fresh"; umount "$MNT/userdata"
cat > "$MNT/etc/fstab" <<EOF
LABEL=RF-ROOT    /          ext4   defaults,noatime,commit=60      0 1
LABEL=RF-BOOT    /boot/efi  vfat   defaults,noatime,umask=0077     0 2
LABEL=RETROFORGE /userdata  exfat  defaults,noatime,uid=1000,gid=1000,umask=0022,nofail 0 0
tmpfs            /tmp       tmpfs  defaults,nosuid,size=25%        0 0
EOF

# ---------------------------------------------------------------------------
log "6/6 Bootloader ($BOOT)"
mount "$P_BOOT" "$MNT/boot/efi"
for d in dev proc sys; do mount --bind "/$d" "$MNT/$d"; done
CMDLINE="root=LABEL=RF-ROOT rw quiet splash loglevel=3 vt.global_cursor_default=0 consoleblank=0 nowatchdog"
case "$BOOT" in
  grub-hybrid|grub-hybrid32|grub-efi-arm64|grub-efi-riscv64)
    chroot "$MNT" update-initramfs -c -k all >/dev/null
    KVER=$(ls "$MNT/lib/modules" | sort -V | tail -1)
    mkdir -p "$MNT/boot/grub"
    sed -e "s|@KVER@|$KVER|g" -e "s|@CMDLINE@|$CMDLINE|g" "$HERE/boot/grub.cfg" > "$MNT/boot/grub/grub.cfg"
    case "$BOOT" in
      grub-hybrid)
        chroot "$MNT" grub-install --target=i386-pc --boot-directory=/boot "$LOOP"
        chroot "$MNT" grub-install --target=x86_64-efi --efi-directory=/boot/efi --boot-directory=/boot --removable --no-nvram
        chroot "$MNT" grub-install --target=i386-efi --efi-directory=/boot/efi --boot-directory=/boot --removable --no-nvram || true ;;
      grub-hybrid32)
        chroot "$MNT" grub-install --target=i386-pc --boot-directory=/boot "$LOOP"
        chroot "$MNT" grub-install --target=i386-efi --efi-directory=/boot/efi --boot-directory=/boot --removable --no-nvram ;;
      grub-efi-arm64)
        chroot "$MNT" grub-install --target=arm64-efi --efi-directory=/boot/efi --boot-directory=/boot --removable --no-nvram ;;
      grub-efi-riscv64)
        chroot "$MNT" grub-install --target=riscv64-efi --efi-directory=/boot/efi --boot-directory=/boot --removable --no-nvram ;;
    esac ;;
  rpi)
    # raspi-firmware installs firmware, DTBs and kernels into /boot/firmware
    rsync -rt "$MNT/boot/firmware/" "$MNT/boot/efi/"
    cp "$HERE/boot/rpi/config.txt" "$MNT/boot/efi/config.txt"
    echo "console=tty3 $CMDLINE rootwait fsck.repair=yes" > "$MNT/boot/efi/cmdline.txt"
    sed -i 's|/boot/efi|/boot/firmware|' "$MNT/etc/fstab" ;;
esac
for d in dev proc sys; do umount -l "$MNT/$d"; done
umount "$MNT/boot/efi"; umount "$MNT"
losetup -d "$LOOP"; LOOP=""
log "Komprimiere …"
xz -T0 -6 -f -k "$IMG"
log "Fertig: $IMG.xz  ($(du -h "$IMG.xz" | cut -f1))"
log "Flashen z. B. mit:  xzcat $IMG.xz | sudo dd of=/dev/sdX bs=4M status=progress"
