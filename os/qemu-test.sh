#!/usr/bin/env bash
# Boot a built x86_64 image in QEMU (UEFI + virtio-gpu with 3D):
#   ./qemu-test.sh out/retroforge-0.1.0-pc-x86_64.img [--bios]
set -euo pipefail
IMG="${1:?Image angeben}"
FW=(-bios /usr/share/ovmf/OVMF.fd)
[[ "${2:-}" == --bios ]] && FW=()
exec qemu-system-x86_64 -enable-kvm -m 4G -smp 4 -cpu host "${FW[@]}" \
  -drive file="$IMG",format=raw,if=virtio \
  -device virtio-vga-gl -display gtk,gl=on \
  -audiodev pa,id=snd -device intel-hda -device hda-duplex,audiodev=snd \
  -device qemu-xhci -device usb-tablet \
  -nic user,model=virtio-net-pci,hostfwd=tcp::8080-:8080,hostfwd=tcp::2222-:22
