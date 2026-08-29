# Docker Image Changelog

All notable changes to the `ghcr.io/tongyi-mai/mobile_world` Docker image.

## v1.2 (2026-04-12)

Built on top of `ghcr.io/tongyi-mai/mobile_world:latest` via `Dockerfile.update`.

### Fixed
- **iptables NAT failure on newer kernels (6.x+)**: Host kernels that have dropped the
  legacy `iptable_nat` module caused dockerd inside the container to fail silently, leading
  to deadlocked container launches and silent eval failures. The image now defaults to the
  `iptables-nft` backend, with runtime auto-detection that falls back to `iptables-legacy`
  on older kernels.
- **dockerd startup deadlock**: The entrypoint now verifies dockerd is actually functional
  (via `docker info`) after launch, with a 30s timeout. On failure, it exits with a clear
  error message and the last 20 lines of `dockerd.err.log`, instead of hanging indefinitely.

### Added
- `mw env check` now includes an iptables NAT prerequisite check that detects whether the
  host kernel supports iptables NAT (legacy or nftables) and provides actionable guidance.

### Changed
- Entrypoint auto-detects the correct iptables backend at container startup based on
  host kernel capabilities (tries `iptables-nft` first, falls back to `iptables-legacy`).

---

## v1.1

Built on top of `ghcr.io/tongyi-mai/mobile_world:latest` via `Dockerfile.update`.

### Added
- `socat` package for ADB port relay (`0.0.0.0:5556 -> 127.0.0.1:5555`).
- Updated entrypoint with ADB relay support.

### Changed
- CMD now tails `dockerd.err.log` in addition to `emulator.log` and `server.log`.

---

## v1.0 (2025-12-24)

Initial release. Base image: `cruizba/ubuntu-dind:latest`.

- Android SDK 34 with `google_apis;x86_64` system image
- Pre-configured AVD: `Pixel_8_API_34_x86_64`
- Embedded emulator (build 14214601)
- MobileWorld server + viewer
- Docker-in-Docker support (Mattermost, Mastodon containers)
- noVNC for optional GUI access
