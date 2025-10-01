# macOS Signing & Notarization

1. Acquire an Apple Developer ID Application certificate and install it in your keychain.
2. Codesign the `.app` bundle before packaging:
   ```bash
   codesign --deep --force --options runtime --sign "Developer ID Application: Your Company" path/to/Data\ Guardian.app
   ```
3. Notarize the signed app with Apple:
   ```bash
   xcrun notarytool submit path/to/Data\ Guardian.app --apple-id "apple-id" --team-id TEAMID --password "app-specific-password" --wait
   ```
4. Staple the notarization ticket:
   ```bash
   xcrun stapler staple path/to/Data\ Guardian.app
   ```
5. Repeat the process for the `.dmg` installer and verify with `spctl -a -vv` on a clean macOS system.
