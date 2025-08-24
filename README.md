# Data Guardian 🛡️

[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-passing-brightgreen.svg)](tests/)

Data Guardian is a comprehensive cryptographic toolkit designed for secure data management. It provides enterprise-grade encryption, digital signing, and hashing capabilities through an intuitive command-line interface, making data protection accessible for both developers and security professionals.

## ✨ Features

- 🔐 **Advanced Key Management**: Generate, store, and manage RSA and Ed25519 cryptographic keys
- 🔒 **Hybrid Encryption**: Military-grade AES-256-GCM with RSA-OAEP key exchange
- ✍️ **Digital Signatures**: Create and verify signatures using Ed25519 elliptic curve cryptography  
- 🔍 **Data Integrity**: SHA-256 hashing for file verification and integrity checking
- 💻 **CLI Interface**: Streamlined command-line tools for all cryptographic operations
- 🛡️ **Security First**: Built with industry best practices and secure defaults

## 🚀 Quick Start

### Prerequisites

- Python 3.8 or higher
- Poetry (recommended) or pip

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/HPNChanel/data-guardian.git
   cd data_guardian
   ```

2. **Install with Poetry (Recommended):**
   ```bash
   pip install poetry
   poetry install
   ```

   **Or install with pip:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Verify installation:**
   ```bash
   poetry run python -m data_guardian.cli --version
   ```

## 📖 Usage Guide

### Getting Started

Run the CLI to see all available commands:
```bash
poetry run python -m data_guardian.cli --help
```

### Key Management

**Generate a new RSA key pair:**
```bash
poetry run python -m data_guardian.cli keygen --type rsa --bits 4096 --name mykey
```

**Generate an Ed25519 signing key:**
```bash
poetry run python -m data_guardian.cli keygen --type ed25519 --name signing_key
```

**List all available keys:**
```bash
poetry run python -m data_guardian.cli keys list
```

### Encryption & Decryption

**Encrypt sensitive files:**
```bash
poetry run python -m data_guardian.cli encrypt \
  --input confidential.pdf \
  --output confidential.pdf.enc \
  --key mykey
```

**Decrypt files:**
```bash
poetry run python -m data_guardian.cli decrypt \
  --input confidential.pdf.enc \
  --output confidential.pdf \
  --key mykey
```

### Digital Signatures

**Sign a document:**
```bash
poetry run python -m data_guardian.cli sign \
  --input contract.pdf \
  --output contract.pdf.sig \
  --key signing_key
```

**Verify signature authenticity:**
```bash
poetry run python -m data_guardian.cli verify \
  --input contract.pdf \
  --signature contract.pdf.sig \
  --key signing_key
```

### Data Integrity

**Generate file hash:**
```bash
poetry run python -m data_guardian.cli hash --input important_data.zip
```

## 🏗️ Project Structure

```
data_guardian/
├── data_guardian/
│   ├── __init__.py
│   ├── cli.py              # Command-line interface
│   ├── crypto/
│   │   ├── encryption.py   # Encryption/decryption logic
│   │   ├── signing.py      # Digital signature operations
│   │   └── hashing.py      # Hash generation utilities
│   ├── keys/
│   │   └── manager.py      # Key management system
│   └── utils/
│       └── helpers.py      # Utility functions
├── tests/                  # Test suite
├── docs/                   # Documentation
├── pyproject.toml         # Poetry configuration
└── README.md
```

## 🧪 Testing

Run the complete test suite:
```bash
poetry run pytest
```

**Run tests with coverage:**
```bash
poetry run pytest --cov=data_guardian --cov-report=html
```

**Run specific test categories:**
```bash
poetry run pytest tests/test_encryption.py -v
```

## 🔧 Configuration

Data Guardian stores keys and configuration in:
- **Windows:** `%APPDATA%/data_guardian/`
- **macOS/Linux:** `~/.config/data_guardian/`

You can customize the configuration directory using the `DATA_GUARDIAN_CONFIG` environment variable.

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

- 📖 **Documentation:** [docs/](docs/)
- 🐛 **Bug Reports:** [GitHub Issues](https://github.com/yourusername/data_guardian/issues)
- 💬 **Discussions:** [GitHub Discussions](https://github.com/yourusername/data_guardian/discussions)

## ⚠️ Security Notice

Data Guardian is designed for educational and professional use. Always follow security best practices:
- Keep your private keys secure and never share them
- Use strong, unique passwords for key protection
- Regularly update dependencies for security patches
- Test thoroughly before using in production environments

---

**Made with ❤️ for data security and privacy**
