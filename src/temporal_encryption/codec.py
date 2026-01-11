import os
from collections.abc import Iterable

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from temporalio.api.common.v1 import Payload
from temporalio.converter import PayloadCodec


class EncryptionCodec(PayloadCodec):
    """AES-256-GCM encryption codec for Temporal payloads."""

    def __init__(self, key_id: str, key: bytes) -> None:
        if len(key) != 32:
            raise ValueError('Key must be 32 bytes for AES-256-GCM')
        super().__init__()
        self.key_id = key_id
        self._encryptor = AESGCM(key)

    async def encode(self, payloads: Iterable[Payload]) -> list[Payload]:
        return [
            Payload(
                metadata={
                    'encoding': b'binary/encrypted',
                    'encryption-key-id': self.key_id.encode(),
                },
                data=self._encrypt(p.SerializeToString()),
            )
            for p in payloads
        ]

    async def decode(self, payloads: Iterable[Payload]) -> list[Payload]:
        result: list[Payload] = []
        for p in payloads:
            if p.metadata.get('encoding', b'').decode() != 'binary/encrypted':
                result.append(p)
                continue
            key_id = p.metadata.get('encryption-key-id', b'').decode()
            if key_id != self.key_id:
                raise ValueError(f'Unknown key ID {key_id!r}, expected {self.key_id!r}')
            result.append(Payload.FromString(self._decrypt(p.data)))
        return result

    def _encrypt(self, data: bytes) -> bytes:
        nonce = os.urandom(12)
        return nonce + self._encryptor.encrypt(nonce, data, None)

    def _decrypt(self, data: bytes) -> bytes:
        return self._encryptor.decrypt(data[:12], data[12:], None)


def load_encryption_codec() -> EncryptionCodec:
    """Load encryption codec with key from environment."""
    key_hex = os.environ.get('TEMPORAL_ENCRYPTION_KEY')
    if not key_hex:
        raise ValueError('TEMPORAL_ENCRYPTION_KEY environment variable not set')

    key = bytes.fromhex(key_hex)
    key_id = os.environ.get('TEMPORAL_ENCRYPTION_KEY_ID', 'default-key')

    return EncryptionCodec(key_id=key_id, key=key)
