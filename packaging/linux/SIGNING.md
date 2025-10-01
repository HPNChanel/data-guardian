# Linux Package Signing

## Debian packages

1. Generate or import a GPG key dedicated to package signing.
2. Update `debian/control` metadata if required.
3. Sign the `.deb` artefact:
   ```bash
   dpkg-sig --sign builder path/to/data-guardian-desktop.deb
   ```
4. Publish the public key so users can import it via `apt-key` or the modern sources list format.

## AppImage

1. Download `appimagetool` and `appimagelauncher` signing utilities.
2. Sign the `.AppImage` using `appimagelauncherfs` or `appimagetool --sign` with your GPG key.
3. Distribute the signature file alongside the AppImage.
4. Document verification instructions for end-users.
