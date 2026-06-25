FROM alpine:3.22@sha256:310c62b5e7ca5b08167e4384c68db0fd2905dd9c7493756d356e893909057601

RUN apk add --no-cache \
    bash \
    curl \
    sudo \
    python3 \
    e2fsprogs \
    dosfstools \
    util-linux \
    sfdisk \
    multipath-tools \
    qemu-img \
    qemu-system-x86_64 \
    parted \
    grub \
    grub-efi \
    mtools \
    xorriso \
    rsync \
    kmod

WORKDIR /work
