# Windows Code Signing

1. Obtain an EV code-signing certificate from a trusted CA.
2. Install the certificate into the local machine store on the build agent.
3. Use `signtool.exe` to sign the MSI installer:
   ```powershell
   signtool sign /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 /n "Your Company Name" path\to\installer.msi
   ```
4. Verify the signature:
   ```powershell
   signtool verify /pa path\to\installer.msi
   ```
5. Document the certificate thumbprint and renewal schedule.
