# Alpine USB XFCE Builder

Herramienta para construir una imagen USB booteable de Alpine Linux x86_64 con escritorio XFCE preconfigurado.

La imagen generada está pensada para grabarse directamente a una USB y arrancar como sistema Alpine instalado, no solo como instalador básico.

## Estado

Este software está en desarrollo constante. La configuración puede cambiar según nuevas versiones de Alpine, cambios en hardware, controladores, gestores de sesión y mejoras detectadas durante pruebas reales.

## Qué configura

- Alpine Linux `latest-stable`
- Boot UEFI para USB removible
- XFCE
- LightDM + `lightdm-gtk-greeter`
- Teclado español
- Usuario inicial `pablo`
- `sudo` y `doas`
- D-Bus, elogind, eudev, seatd
- NetworkManager
- PipeWire audio
- Firefox ESR
- Soporte input/video común:
  - `xf86-input-libinput`
  - AMDGPU/ATI/VESA
- Optimizaciones para uso en USB:
  - `tmpfs` para `/tmp` y `/var/tmp`
  - menor swappiness
  - menos escrituras de cache APK
  - `noatime` donde aplica

## Requisitos

Construcción recomendada en Linux o Docker Desktop con soporte NBD.

En macOS, Docker Desktop puede funcionar mejor que Colima para este flujo porque la herramienta usa `qemu-nbd`.

## GUI rápida para grabar USB

El repo incluye una utilidad gráfica simple, cross-platform, para seleccionar la imagen y grabarla a la USB.

GUI Qt:

```sh
./run_qt_gui.sh
```

Si el selector no detecta tu USB, puedes escribir manualmente el dispositivo, por ejemplo `/dev/disk7` en macOS o `/dev/sdb` en Linux.

Soporte:

- macOS: usa `diskutil`, `dd` y pide permisos de administrador.
- Linux: usa `lsblk`, `dd` y `sudo`/`pkexec` si hace falta.
- Windows: por seguridad no hace raw flashing todavía; usa Rufus/balenaEtcher con la imagen generada.

## Construir imagen

```sh
chmod +x build-alpine-usb.sh configure-alpine-usb.sh
IMAGE_SIZE=16G ./build-alpine-usb.sh
```

Resultado:

```txt
alpine-usb-xfce.img
```

## Grabar USB

⚠️ Esto borra por completo el dispositivo destino.

En macOS:

```sh
diskutil unmountDisk /dev/diskX
sudo dd if=alpine-usb-xfce.img of=/dev/rdiskX bs=4M status=progress
sync
diskutil eject /dev/diskX
```

En Linux:

```sh
lsblk
sudo dd if=alpine-usb-xfce.img of=/dev/sdX bs=4M status=progress conv=fsync
```

Usa disco completo (`/dev/sdX`, `/dev/diskX`), no partición (`/dev/sdX1`).

## Login inicial

```txt
usuario: pablo
password: pablo
root password: pablo
```

Cambia passwords después del primer arranque:

```sh
passwd
sudo passwd root
```

## Notas

- La imagen generada no se incluye en el repo.
- El repo contiene scripts para reproducir la imagen.
- Si LightDM falla, se puede iniciar XFCE manualmente con:

```sh
startx /usr/bin/startxfce4
```

## Licencia

MIT
