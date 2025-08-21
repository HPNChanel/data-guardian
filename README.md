# Data Guardian

Data Guardian is a comprehensive tool for managing encryption, signing, and hashing operations. It provides a secure and user-friendly interface for protecting sensitive data.

## Features

- **Key Management**: Generate, list, and load cryptographic keys.
- **Encryption/Decryption**: Perform hybrid encryption using AES-256-GCM and RSA-OAEP.
- **Signing/Verification**: Create and verify digital signatures using Ed25519.
- **Hashing**: Generate SHA-256 hashes for data integrity verification.
- **Command-Line Interface (CLI)**: Easy-to-use commands for all operations.

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/HPNChanel/python-base-projects.git
   cd data-guardian
   ```

2. Install dependencies:
   ```bash
   pip install poetry
   poetry install
   ```

## Usage

Run the CLI to access the available commands:
```bash
poetry run python -m data_guardian.cli --help
```

### Example Commands

- Generate a new key:
  ```bash
  poetry run python -m data_guardian.cli keygen
  ```

- Encrypt a file:
  ```bash
  poetry run python -m data_guardian.cli encrypt --input file.txt --output file.enc
  ```

- Decrypt a file:
  ```bash
  poetry run python -m data_guardian.cli decrypt --input file.enc --output file.txt
  ```

- Sign a file:
  ```bash
  poetry run python -m data_guardian.cli sign --input file.txt --output file.sig
  ```

- Verify a signature:
  ```bash
  poetry run python -m data_guardian.cli verify --input file.txt --signature file.sig
  ```

## Testing

Run the test suite to ensure everything works as expected:
```bash
poetry run pytest
```

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.
