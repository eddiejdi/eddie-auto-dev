Next steps to migrate from Vaultwarden to SOPS/GPG

1. Export items you want to keep (Open WebUI API key) into plaintext file `secrets/openwebui_api.key`.
2. Create a passphrase file readable only by root/your user and store it securely (e.g. `/root/.vault_pass` or inside your password manager locally).
3. Run `./encrypt_secret.sh secrets/openwebui_api.key secrets/openwebui_api.key.gpg /path/to/passphrase`.
4. Remove plaintext `secrets/openwebui_api.key` after verifying the encrypted file.
5. Update services to decrypt at startup or read decrypted content from a secure mount.

If you'd prefer SOPS (recommended for Git-managed secrets), install `sops` and create an age or GPG key for encryption.
