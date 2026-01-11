# temporal-encryption

## Background

This repository demonstrates how to use Pydantic AI with Temporal while keeping all workflow state encrypted. The template can be used by users requiring encryption for data stored in Temporal - which is a common requirement for financial services, healthcare, and other regulated industries.

The demo shows that Temporal supports client-side encryption via its PayloadCodec mechanism, and Pydantic AI's Temporal integration preserves this capability through the `PydanticAIPlugin`.

## What This Repo Demonstrates

1. **Client-side encryption** - All data is encrypted before reaching the Temporal server
2. **Zero-knowledge server** - Temporal server sees only encrypted blobs, cannot access plaintext
3. **BYOK (Bring Your Own Key)** - Users provide their own encryption keys
4. **Key rotation support** - Key IDs in metadata enable seamless key rotation
5. **Production-ready algorithm** - AES-256-GCM (NIST recommended, hardware-accelerated)

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Starter       │     │  Temporal Server │     │     Worker      │
│   (Client)      │────▶│  (Encrypted)     │────▶│   (Decrypts)    │
└─────────────────┘     └──────────────────┘     └─────────────────┘
        │                        │                        │
        ▼                        ▼                        ▼
   PayloadCodec            Only sees              PayloadCodec
   encrypts all            encrypted              decrypts all
   payloads                blobs                  payloads
```

## File Structure

- `src/temporal_encryption/codec.py` - AES-256-GCM PayloadCodec implementation
- `src/temporal_encryption/agent.py` - Trading agent with trading tools
- `src/temporal_encryption/workflow.py` - Temporal workflow wrapping the agent
- `src/temporal_encryption/worker.py` - Worker with encrypted DataConverter
- `src/temporal_encryption/starter.py` - Script to execute workflows
- `docs/gcp-kms.md` - GCP Cloud KMS integration guide

## Configuration Decisions

This setup makes several choices that could be configurable:

1. **Encryption algorithm**: AES-256-GCM (could support ChaCha20-Poly1305, etc.)
2. **Key size**: 256-bit (could support 128-bit for AES)
3. **Key source**: Environment variable (could be KMS, Vault, file, etc.)
4. **Nonce generation**: Random 12 bytes (could be counter-based for some use cases)
5. **Key ID tracking**: Stored in payload metadata (enables rotation)
6. **Encoding identifier**: `binary/encrypted` (allows mixed encrypted/unencrypted payloads)

## Future Considerations

### Simplified Abstraction for Pydantic AI

Currently users must manually:
1. Create a PayloadCodec subclass
2. Build a DataConverter with the codec
3. Pass it to Client.connect alongside PydanticAIPlugin

A simpler API could be:

```python
# Option A: Built-in encrypted plugin
from pydantic_ai.durable_exec.temporal import EncryptedPydanticAIPlugin

client = await Client.connect(
    "localhost:7233",
    plugins=[EncryptedPydanticAIPlugin(
        encryption_key=os.environ["TEMPORAL_ENCRYPTION_KEY"],
        key_id="production-v1",
    )],
)

# Option B: Helper function
from pydantic_ai.durable_exec.temporal import create_encrypted_client

client = await create_encrypted_client(
    "localhost:7233",
    encryption_key=os.environ["TEMPORAL_ENCRYPTION_KEY"],
)
```

### KMS Integration

For production, keys should come from a KMS (AWS KMS, GCP Cloud KMS, Azure Key Vault, HashiCorp Vault). The abstraction could support:

```python
from pydantic_ai.durable_exec.temporal import GCPKMSCodec

codec = GCPKMSCodec(
    project="my-project",
    location="global",
    key_ring="temporal-keys",
    key="workflow-encryption",
)
```

### Trading Example

The current example demonstrates a trading agent that could:
- Fetch market data from Market API
- Analyze positions and opportunities
- Execute trades (with encrypted order details)
- All while keeping sensitive trading data encrypted in Temporal

## Development

```bash
# Install with dev dependencies
uv sync --group dev

# Format code
ruff format src/

# Lint (with auto-fix)
ruff check src/ --fix

# Type check
pyright src/
```
