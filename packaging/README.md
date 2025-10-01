# Desktop Packaging Overview

The Data Guardian desktop release pipeline produces signed installers for Windows (`.msi`), macOS (`.dmg`), and Linux (`.deb`, `.AppImage`). Each platform must be signed according to the corresponding guide under `packaging/<platform>/SIGNING.md`.

## Update server expectations

The Tauri updater (gated behind the `auto-update` feature) expects a JSON feed served over HTTPS. Host the feed on a domain you control and require TLS 1.2+. Example metadata snippet:

```json
{
  "platforms": {
    "darwin-x86_64": {
      "version": "0.1.0",
      "notes": "Initial desktop preview",
      "pub_date": "2024-01-01T00:00:00Z",
      "url": "https://downloads.example.com/DataGuardianDesktop-0.1.0.dmg"
    }
  }
}
```

Keep artefacts in long-term storage and maintain backwards compatibility for at least two previous versions so the updater can delta users gradually.

## Artefact retention

- Store unsigned builds in a protected bucket for auditing.
- Promote only signed artefacts to the public release channel.
- Archive release notes and checksum manifests (`sha256sum`) beside each installer.
