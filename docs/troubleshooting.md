# LEDIT troubleshooting

This page collects common failures and the fastest checks to run before opening a bug report.

## First command to run

```sh
./ledit doctor
```

`doctor` checks common host tools. On macOS it checks Docker and `diskutil`; on Linux it checks base tools like `sudo`, `python3`, `dd`, `lsblk`, bootloader tools, and optional distro-specific builders.

## GUI fails with `ModuleNotFoundError: No module named 'PySide6'`

Cause: the active Python environment does not have Qt installed, or `.qtvenv` was created with old/broken dependency pins.

Fix:

```sh
git pull
rm -rf .qtvenv
python gui.py
```

`gui.py` should recreate `.qtvenv`, install `requirements.txt`, and re-run through the Qt virtualenv before importing GUI modules.

## GUI opens from terminal but not Finder

Finder-launched macOS apps often receive a reduced `PATH`. Start from Terminal while troubleshooting:

```sh
python gui.py
```

Then check whether Docker is visible:

```sh
which docker
docker info
```

## Docker is not running

macOS builds usually require Docker Desktop.

Symptoms:

- `ERROR: Docker is not running`
- Docker image pull/build errors before distro configuration starts
- build exits immediately on macOS

Fix:

1. Open Docker Desktop.
2. Wait until Docker reports it is running.
3. Run:

```sh
docker info
./ledit doctor
```

## Package search returns no results

Possible causes:

- wrong distro selected,
- wrong branch/release selected,
- package has a different name in that distro,
- package exists in a repository not enabled by the backend.

Check:

```sh
./ledit search firefox --distro alpine --branch latest-stable --limit 10
./ledit search firefox --distro ubuntu --branch 24.04 --limit 10
./ledit search firefox --distro arch --branch rolling --limit 10
```

Then add the package name exactly as the distro reports it.

## Extra packages with spaces behave incorrectly

Use quoted strings or repeat `--extra-package`:

```sh
./ledit build --distro arch \
  --extra-package neovim \
  --extra-package "tmux htop" \
  --extra-package docker \
  --ask-password
```

LEDIT splits package lists intentionally, validates names, deduplicates them, and passes them to backends through environment files or safe environment mappings.

## Dry-run fails

Dry-run is supposed to fail early when a profile is invalid.

Common reasons:

- unsupported branch,
- unsupported architecture,
- invalid package name,
- unsupported bootloader for that distro,
- desktop/session/display-manager combination not mapped by the backend.

Try the simplest dry-run first:

```sh
./ledit build --distro alpine --dry-run --ask-password -y
```

Then add your options back one by one.

## Build succeeds but image does not boot

Try a compatibility-first build:

```sh
./ledit build --distro alpine \
  --profile compatibility \
  --bootloader grub \
  --firmware full \
  --legacy-x11-drivers \
  --ask-password \
  -y
```

Also check:

- the target machine boot mode: UEFI vs legacy BIOS,
- secure boot settings,
- whether the USB drive is healthy,
- whether you flashed the whole disk path, not a partition.

## Flashing refuses the target device

LEDIT intentionally blocks suspicious targets.

Run:

```sh
./ledit devices
```

Use a whole-disk path:

| Host | Correct | Incorrect |
| --- | --- | --- |
| macOS | `/dev/disk4` | `/dev/disk4s1` |
| Linux | `/dev/sdb` | `/dev/sdb1` |

## Flashing is slow

Raw image flashing is limited by USB drive speed. Prefer good USB 3.x drives and direct ports instead of hubs.

On macOS LEDIT writes to `/dev/rdiskX` internally for better performance after validating `/dev/diskX`.

## Permission errors on Linux

Use a user with sudo access or install `pkexec`.

```sh
sudo -v
./ledit flash /tmp/ledit/ledit.img /dev/sdX
```

## Permission errors on macOS

macOS flashing uses `diskutil`, `sudo`, and `dd`.

Check:

```sh
diskutil list
sudo -v
```

## Output path errors

If Docker is involved, choose an output path under a directory Docker Desktop can access, for example:

```sh
./ledit build --distro arch \
  --output "$HOME/Downloads/ledit-arch.img" \
  --ask-password \
  -y
```

Avoid unusual paths until the default flow works.

## Backend-specific issues

Use the distro page:

- [Alpine](distros/alpine.md)
- [Arch](distros/arch.md)
- [Debian](distros/debian.md)
- [Fedora](distros/fedora.md)
- [Gentoo](distros/gentoo.md)
- [NixOS](distros/nixos.md)
- [openSUSE](distros/opensuse.md)
- [RHEL family](distros/rhel.md)
- [Slackware](distros/slackware.md)
- [Ubuntu](distros/ubuntu.md)
- [Void](distros/void.md)

## Good bug report checklist

Include:

- host OS and version,
- Python version,
- exact command,
- selected distro and branch,
- whether Docker was running,
- full error output,
- whether `--dry-run` succeeds,
- output of `./ledit doctor`.

## See also

- [Project README](../README.md)
- [Configuration reference](configuration.md)
- [Per-distro documentation](distros/README.md)
