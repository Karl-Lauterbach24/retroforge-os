# Reproducible build host:  docker build -t retroforge-builder os/
#   docker run --rm --privileged -v "$PWD":/src retroforge-builder pc-x86_64
FROM debian:trixie
RUN apt-get update && apt-get install -y --no-install-recommends \
      mmdebstrap qemu-user-static binfmt-support dosfstools exfatprogs e2fsprogs fdisk \
      grub-pc-bin grub-efi-amd64-bin curl gpg python3 rsync xz-utils ca-certificates udev \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /src/os
ENTRYPOINT ["./build.sh"]
