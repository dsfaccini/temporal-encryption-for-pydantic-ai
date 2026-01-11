# GCP Cloud KMS Integration

This guide explains how to integrate Google Cloud KMS with the Temporal encryption setup for production key management.

## Why Use Cloud KMS?

- **Automatic key rotation** - GCP rotates keys on a schedule you define
- **Audit logging** - All key usage is logged in Cloud Audit Logs
- **Access control** - IAM policies control who can use keys
- **Hardware security** - Keys can be backed by HSMs (Cloud HSM)
- **No key material exposure** - Keys never leave GCP infrastructure

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Worker    │────▶│  Cloud KMS  │────▶│  Temporal   │
│             │     │  (encrypt)  │     │  (encrypted │
│             │◀────│  (decrypt)  │◀────│   payloads) │
└─────────────┘     └─────────────┘     └─────────────┘
```

## Setup

### 1. Create a Key Ring and Key

```bash
# Set your project
export PROJECT_ID="your-project-id"
export LOCATION="global"  # or a specific region like "us-east1"
export KEY_RING="temporal-keys"
export KEY_NAME="workflow-encryption"

# Create key ring
gcloud kms keyrings create $KEY_RING \
    --location=$LOCATION \
    --project=$PROJECT_ID

# Create symmetric encryption key with automatic rotation
gcloud kms keys create $KEY_NAME \
    --location=$LOCATION \
    --keyring=$KEY_RING \
    --purpose=encryption \
    --rotation-period=90d \
    --next-rotation-time=$(date -u -d "+90 days" +%Y-%m-%dT%H:%M:%SZ) \
    --project=$PROJECT_ID
```

### 2. Grant Access to Your Service Account

```bash
export SERVICE_ACCOUNT="your-worker-sa@${PROJECT_ID}.iam.gserviceaccount.com"

# Grant encrypt/decrypt permissions
gcloud kms keys add-iam-policy-binding $KEY_NAME \
    --location=$LOCATION \
    --keyring=$KEY_RING \
    --member="serviceAccount:${SERVICE_ACCOUNT}" \
    --role="roles/cloudkms.cryptoKeyEncrypterDecrypter" \
    --project=$PROJECT_ID
```

### 3. Install Dependencies

```bash
uv add google-cloud-kms
```

### 4. Implement KMS Codec

```python
# src/temporal_encryption/kms_codec.py
import os
from typing import Iterable

from google.cloud import kms
from temporalio.api.common.v1 import Payload
from temporalio.converter import PayloadCodec


class GCPKMSCodec(PayloadCodec):
    """PayloadCodec that uses GCP Cloud KMS for encryption."""

    def __init__(
        self,
        project: str,
        location: str,
        key_ring: str,
        key: str,
    ) -> None:
        super().__init__()
        self._client = kms.KeyManagementServiceClient()
        self._key_name = self._client.crypto_key_path(
            project, location, key_ring, key
        )

    async def encode(self, payloads: Iterable[Payload]) -> list[Payload]:
        result = []
        for p in payloads:
            plaintext = p.SerializeToString()

            # Encrypt with Cloud KMS
            response = self._client.encrypt(
                request={"name": self._key_name, "plaintext": plaintext}
            )

            result.append(
                Payload(
                    metadata={
                        "encoding": b"binary/gcp-kms",
                        "kms-key": self._key_name.encode(),
                    },
                    data=response.ciphertext,
                )
            )
        return result

    async def decode(self, payloads: Iterable[Payload]) -> list[Payload]:
        result = []
        for p in payloads:
            if p.metadata.get("encoding", b"").decode() != "binary/gcp-kms":
                result.append(p)
                continue

            # Decrypt with Cloud KMS
            response = self._client.decrypt(
                request={"name": self._key_name, "ciphertext": p.data}
            )

            result.append(Payload.FromString(response.plaintext))
        return result


def load_kms_codec() -> GCPKMSCodec:
    """Load KMS codec from environment variables."""
    return GCPKMSCodec(
        project=os.environ["GCP_PROJECT"],
        location=os.environ.get("GCP_KMS_LOCATION", "global"),
        key_ring=os.environ["GCP_KMS_KEY_RING"],
        key=os.environ["GCP_KMS_KEY"],
    )
```

### 5. Use in Worker

```python
# In worker.py, replace load_encryption_codec with load_kms_codec
from .kms_codec import load_kms_codec

async def run_worker():
    load_dotenv()

    kms_codec = load_kms_codec()
    data_converter = dataclasses.replace(
        temporalio.converter.default(),
        payload_codec=kms_codec,
    )
    # ... rest of worker setup
```

## Environment Variables

```bash
# .env for GCP KMS
export GCP_PROJECT="your-project-id"
export GCP_KMS_LOCATION="global"
export GCP_KMS_KEY_RING="temporal-keys"
export GCP_KMS_KEY="workflow-encryption"

# For local development with service account key
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account-key.json"
```

## Key Rotation

Cloud KMS handles key rotation automatically:

1. **Primary version** - Used for new encryptions
2. **Previous versions** - Still available for decryption
3. **Rotation schedule** - Set via `--rotation-period` (e.g., 90 days)

The codec automatically uses the correct key version because:
- Encrypt calls use the primary version
- Decrypt calls include version info in the ciphertext

No code changes needed when keys rotate.

## Performance Considerations

Cloud KMS adds latency (~10-50ms per operation). For high-throughput workloads:

1. **Envelope encryption** - Use KMS to encrypt a data encryption key (DEK), then use DEK locally
2. **Caching** - Cache DEKs with TTL for repeated operations
3. **Batch operations** - Group multiple payloads when possible

### Envelope Encryption Example

```python
class EnvelopeKMSCodec(PayloadCodec):
    """Uses KMS for key encryption, local AES for data encryption."""

    def __init__(self, kms_key_name: str):
        self._client = kms.KeyManagementServiceClient()
        self._kms_key = kms_key_name
        self._dek_cache: dict[str, tuple[bytes, AESGCM]] = {}

    def _get_or_create_dek(self) -> tuple[bytes, AESGCM]:
        # Generate a new DEK
        dek = os.urandom(32)

        # Encrypt DEK with KMS
        response = self._client.encrypt(
            request={"name": self._kms_key, "plaintext": dek}
        )

        return response.ciphertext, AESGCM(dek)

    async def encode(self, payloads: Iterable[Payload]) -> list[Payload]:
        encrypted_dek, cipher = self._get_or_create_dek()

        result = []
        for p in payloads:
            nonce = os.urandom(12)
            ciphertext = cipher.encrypt(nonce, p.SerializeToString(), None)

            result.append(
                Payload(
                    metadata={
                        "encoding": b"binary/envelope-kms",
                        "encrypted-dek": encrypted_dek,
                    },
                    data=nonce + ciphertext,
                )
            )
        return result
```

## Security Best Practices

1. **Separate keys per environment** - dev, staging, prod should use different keys
2. **Minimal permissions** - Only grant `cryptoKeyEncrypterDecrypter`, not admin roles
3. **Enable audit logging** - Monitor key usage in Cloud Audit Logs
4. **Use VPC Service Controls** - Restrict KMS access to your VPC
5. **Consider Cloud HSM** - For highest security, use HSM-backed keys

## Monitoring

Set up alerts in Cloud Monitoring for:

- High error rates on KMS operations
- Unusual encryption/decryption patterns
- Key rotation failures
- Permission denied errors

```bash
# View recent KMS operations
gcloud logging read 'resource.type="cloudkms_cryptokey"' \
    --project=$PROJECT_ID \
    --limit=50
```
