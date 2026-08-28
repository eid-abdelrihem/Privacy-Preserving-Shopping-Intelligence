"""Deterministic fixed-size product hashing for HashingConfig v1.

XXH64 is a compact representation mechanism, not a cryptographic or privacy
primitive. SHA-256 is used separately for configuration identity.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType
from typing import Any

import torch
import xxhash
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError
from torch import Tensor, nn

HASHING_CONFIG_SCHEMA = "hashing_config_v1"
HASHING_CONFIG_VERSION = "1"
GOLDEN_VECTOR_SCHEMA = "product_hash_golden_vectors_v1"
SERIALIZATION_ID = "lp_u32be_utf8_namespace_id_v1"
ALGORITHM_ID = "XXH64"
ALGORITHM_CONTRACT_VERSION = "1"
REFERENCE_LIBRARY = "python-xxhash"
REFERENCE_LIBRARY_VERSION = "4.0.1"
BACKEND_VERSION = "0.8.3"
UINT32_MAX = (1 << 32) - 1
UINT64_MAX = (1 << 64) - 1
INT64_MAX = (1 << 63) - 1

_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_HASHING_CONFIG_SCHEMA_PATH = (
    _REPO_ROOT / "config/features/schemas/hashing_config.v1.schema.json"
)


class HashingConfigError(ValueError):
    """Raised when HashingConfig v1 is malformed or incompatible."""


class ProductIdentityError(ValueError):
    """Raised when a product identity cannot be serialized canonically."""


class ReservedProductId(StrEnum):
    """Typed non-hashed product states.

    Strings with these spellings remain ordinary product identifiers. A caller
    must pass an enum member to request reserved semantics.
    """

    PAD = "PAD"
    OOV = "OOV"
    NULL = "NULL"


@dataclass(frozen=True, slots=True)
class ProductIdentity:
    """Opaque namespace and identifier strings before canonical serialization."""

    namespace: str
    identifier: str

    def __post_init__(self) -> None:
        _validate_identity_component(self.namespace, "namespace")
        _validate_identity_component(self.identifier, "identifier")


@dataclass(frozen=True, slots=True)
class HashingConfig:
    """Validated runtime view of HashingConfig v1."""

    schema: str
    version: str
    config_id: str
    profile: str
    seed_uint64: int
    bucket_count: int
    reserved_indices: Mapping[str, int]
    residual_embedding_dim: int
    config_sha256: str

    @property
    def pad_index(self) -> int:
        return self.reserved_indices[ReservedProductId.PAD.value]

    @property
    def oov_index(self) -> int:
        return self.reserved_indices[ReservedProductId.OOV.value]

    @property
    def null_index(self) -> int:
        return self.reserved_indices[ReservedProductId.NULL.value]

    @property
    def usable_bucket_count(self) -> int:
        return self.bucket_count - len(self.reserved_indices)

    @classmethod
    def from_record(
        cls,
        record: Mapping[str, Any],
        *,
        schema_path: Path = DEFAULT_HASHING_CONFIG_SCHEMA_PATH,
        verify_runtime: bool = True,
    ) -> HashingConfig:
        """Validate a JSON-like record without silently coercing any field."""

        if not isinstance(record, Mapping):
            raise HashingConfigError("HashingConfig v1 must be an object")
        material = dict(record)
        _validate_against_schema(material, schema_path)

        expected_sha = compute_config_sha256(material)
        actual_sha = material["config_sha256"]
        if actual_sha != expected_sha:
            raise HashingConfigError(
                f"config_sha256 mismatch: expected {expected_sha}, got {actual_sha}"
            )

        seed = _parse_uint64_decimal(material["algorithm"]["seed_uint64"])
        bucket_count = material["bucket_count"]
        residual_dim = material["residual_embedding_dim"]
        reserved = dict(material["reserved_indices"])

        _reject_bool_int(bucket_count, "bucket_count")
        _reject_bool_int(residual_dim, "residual_embedding_dim")
        for name, index in reserved.items():
            _reject_bool_int(index, f"reserved_indices.{name}")

        if len(set(reserved.values())) != len(reserved):
            raise HashingConfigError("reserved indices must be distinct")
        if any(index < 0 or index >= bucket_count for index in reserved.values()):
            raise HashingConfigError("reserved index must be inside [0, bucket_count)")
        if bucket_count - len(reserved) < 1:
            raise HashingConfigError("bucket_count must leave at least one usable bucket")

        if verify_runtime:
            _verify_reference_runtime()

        return cls(
            schema=material["schema"],
            version=material["version"],
            config_id=material["config_id"],
            profile=material["profile"],
            seed_uint64=seed,
            bucket_count=bucket_count,
            reserved_indices=MappingProxyType(reserved),
            residual_embedding_dim=residual_dim,
            config_sha256=actual_sha,
        )


def _validate_against_schema(record: dict[str, Any], schema_path: Path) -> None:
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(record)
    except FileNotFoundError as exc:
        raise HashingConfigError(f"HashingConfig schema not found: {schema_path}") from exc
    except json.JSONDecodeError as exc:
        raise HashingConfigError(f"HashingConfig schema is invalid JSON: {schema_path}") from exc
    except (SchemaError, ValidationError) as exc:
        raise HashingConfigError(f"HashingConfig schema validation failed: {exc.message}") from exc


def _reject_bool_int(value: object, field: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise HashingConfigError(f"{field} must be an integer, not bool")


def _parse_uint64_decimal(value: object) -> int:
    if not isinstance(value, str):
        raise HashingConfigError("algorithm.seed_uint64 must be a decimal string")
    try:
        parsed = int(value, 10)
    except ValueError as exc:
        raise HashingConfigError("algorithm.seed_uint64 must be a decimal string") from exc
    if parsed < 0 or parsed > UINT64_MAX:
        raise HashingConfigError("algorithm.seed_uint64 is outside uint64 range")
    return parsed


def _verify_reference_runtime() -> None:
    if xxhash.VERSION != REFERENCE_LIBRARY_VERSION:
        raise HashingConfigError(
            "python-xxhash version mismatch: "
            f"expected {REFERENCE_LIBRARY_VERSION}, got {xxhash.VERSION}"
        )
    if xxhash.XXHASH_VERSION != BACKEND_VERSION:
        raise HashingConfigError(
            f"xxHash backend mismatch: expected {BACKEND_VERSION}, got {xxhash.XXHASH_VERSION}"
        )


def _reject_nonfinite_or_nonstring_keys(value: Any, path: str = "root") -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise HashingConfigError(f"NaN/Inf not allowed at {path}")
    if isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str):
                raise HashingConfigError(f"non-string key at {path}: {key!r}")
            _reject_nonfinite_or_nonstring_keys(child, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _reject_nonfinite_or_nonstring_keys(child, f"{path}[{index}]")


def canonical_config_bytes(record: Mapping[str, Any]) -> bytes:
    """Canonical semantic JSON bytes, matching the repository identity convention."""

    _reject_nonfinite_or_nonstring_keys(record)
    return json.dumps(
        record,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def compute_config_sha256(record: Mapping[str, Any]) -> str:
    """Compute the semantic config hash with the self-hash field omitted."""

    without_hash = dict(record)
    without_hash.pop("config_sha256", None)
    return hashlib.sha256(canonical_config_bytes(without_hash)).hexdigest()


def load_hashing_config(
    path: Path | str,
    *,
    schema_path: Path = DEFAULT_HASHING_CONFIG_SCHEMA_PATH,
    verify_runtime: bool = True,
) -> HashingConfig:
    """Load and validate HashingConfig v1 from UTF-8 JSON."""

    config_path = Path(path)
    try:
        record = json.loads(config_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise HashingConfigError(f"HashingConfig not found: {config_path}") from exc
    except json.JSONDecodeError as exc:
        raise HashingConfigError(f"HashingConfig is invalid JSON: {config_path}") from exc
    return HashingConfig.from_record(
        record,
        schema_path=schema_path,
        verify_runtime=verify_runtime,
    )


def _validate_identity_component(value: object, field: str) -> None:
    if not isinstance(value, str):
        raise ProductIdentityError(f"{field} must be a string; implicit conversion is forbidden")
    if value == "":
        raise ProductIdentityError(f"{field} must not be empty")
    try:
        encoded = value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ProductIdentityError(f"{field} is not valid Unicode for UTF-8") from exc
    if len(encoded) > UINT32_MAX:
        raise ProductIdentityError(f"{field} UTF-8 encoding exceeds uint32 length")


def parse_canonical_item_id(value: str) -> ProductIdentity:
    """Parse ``source:item:raw-id`` without numeric coercion or trimming."""

    if not isinstance(value, str):
        raise ProductIdentityError("canonical item_id must be a string")
    parts = value.split(":", 2)
    if len(parts) != 3:
        raise ProductIdentityError("canonical item_id must match source:item:raw-id")
    source, entity, identifier = parts
    if source == "" or entity != "item" or identifier == "":
        raise ProductIdentityError("canonical item_id must match source:item:raw-id")
    return ProductIdentity(namespace=f"{source}:{entity}", identifier=identifier)


def _length_prefixed_utf8(value: str) -> bytes:
    encoded = value.encode("utf-8")
    return len(encoded).to_bytes(4, "big", signed=False) + encoded


def serialize_product_identity(identity: ProductIdentity) -> bytes:
    """Return canonical length-prefixed namespace+identifier bytes."""

    if not isinstance(identity, ProductIdentity):
        raise ProductIdentityError("identity must be ProductIdentity")
    return _length_prefixed_utf8(identity.namespace) + _length_prefixed_utf8(identity.identifier)


def hash_product_identity(identity: ProductIdentity, config: HashingConfig) -> int:
    """Return an unsigned XXH64 digest for one nonreserved identity."""

    if not isinstance(config, HashingConfig):
        raise TypeError("config must be a validated HashingConfig")
    payload = serialize_product_identity(identity)
    return xxhash.xxh64(payload, seed=config.seed_uint64).intdigest()


def map_digest_to_bucket(digest: int, config: HashingConfig) -> int:
    """Map an unsigned digest onto the ordered bucket set excluding reservations."""

    if isinstance(digest, bool) or not isinstance(digest, int):
        raise TypeError("digest must be an unsigned uint64 integer")
    if digest < 0 or digest > UINT64_MAX:
        raise ValueError("digest is outside uint64 range")

    bucket = digest % config.usable_bucket_count
    for reserved_index in sorted(config.reserved_indices.values()):
        if bucket >= reserved_index:
            bucket += 1
        else:
            break
    if bucket in config.reserved_indices.values():  # defensive invariant
        raise RuntimeError("internal error: digest mapped into a reserved bucket")
    return bucket


def bucket_product_input(
    value: ProductIdentity | ReservedProductId | None,
    config: HashingConfig,
) -> int:
    """Bucket one typed input; null and sentinels bypass hashing explicitly."""

    if value is None:
        return config.null_index
    if isinstance(value, ReservedProductId):
        return config.reserved_indices[value.value]
    if not isinstance(value, ProductIdentity):
        raise ProductIdentityError(
            "product input must be ProductIdentity, ReservedProductId, or None; "
            "implicit stringification is forbidden"
        )
    return map_digest_to_bucket(hash_product_identity(value, config), config)


def bucket_canonical_item_id(
    value: str | ReservedProductId | None,
    config: HashingConfig,
) -> int:
    """Bucket a CanonicalEvent item_id or an explicit non-hashed state."""

    if value is None or isinstance(value, ReservedProductId):
        return bucket_product_input(value, config)
    return bucket_product_input(parse_canonical_item_id(value), config)


def _validated_shape(shape: Sequence[int]) -> tuple[int, ...]:
    if isinstance(shape, (str, bytes)) or not isinstance(shape, Sequence):
        raise TypeError("shape must be a sequence of integers")
    result = tuple(shape)
    if not result:
        raise ValueError("shape must contain at least one dimension")
    for index, dimension in enumerate(result):
        if isinstance(dimension, bool) or not isinstance(dimension, int):
            raise TypeError(f"shape[{index}] must be an integer")
        if dimension < 0:
            raise ValueError(f"shape[{index}] must be non-negative")
    return result


def _materialize_values(values: Iterable[object]) -> list[object]:
    if isinstance(values, (str, bytes)):
        raise TypeError("values must be an iterable of product inputs, not a string")
    try:
        return list(values)
    except TypeError as exc:
        raise TypeError("values must be iterable") from exc


def bucketize_product_inputs(
    values: Iterable[ProductIdentity | ReservedProductId | None],
    *,
    shape: Sequence[int],
    config: HashingConfig,
) -> Tensor:
    """Bucket flat row-major product inputs into a shape-preserving int64 tensor."""

    output_shape = _validated_shape(shape)
    material = _materialize_values(values)
    expected = math.prod(output_shape)
    if len(material) != expected:
        raise ValueError(f"shape requires {expected} inputs, got {len(material)}")
    bucket_ids = [bucket_product_input(value, config) for value in material]
    return torch.tensor(bucket_ids, dtype=torch.int64).reshape(output_shape)


def bucketize_canonical_item_ids(
    values: Iterable[str | ReservedProductId | None],
    *,
    shape: Sequence[int],
    config: HashingConfig,
) -> Tensor:
    """Bucket flat row-major CanonicalEvent item IDs without string coercion."""

    output_shape = _validated_shape(shape)
    material = _materialize_values(values)
    expected = math.prod(output_shape)
    if len(material) != expected:
        raise ValueError(f"shape requires {expected} inputs, got {len(material)}")
    bucket_ids = [bucket_canonical_item_id(value, config) for value in material]
    return torch.tensor(bucket_ids, dtype=torch.int64).reshape(output_shape)


class ProductHashResidual(nn.Module):
    """Learned residual embedding for product-hash buckets only.

    Category and brand inputs are intentionally absent from this interface and
    remain separate categorical channels in Phase1Batch v1.
    """

    def __init__(self, config: HashingConfig) -> None:
        super().__init__()
        self.config_sha256 = config.config_sha256
        self.bucket_count = config.bucket_count
        self.residual_embedding_dim = config.residual_embedding_dim
        self.padding_idx = config.pad_index
        self.embedding = nn.Embedding(
            num_embeddings=config.bucket_count,
            embedding_dim=config.residual_embedding_dim,
            padding_idx=config.pad_index,
        )

    def forward(self, bucket_ids: Tensor) -> Tensor:
        if bucket_ids.dtype != torch.int64:
            raise TypeError(f"bucket_ids must be torch.int64, got {bucket_ids.dtype}")
        if bucket_ids.numel() > 0:
            minimum = int(bucket_ids.min())
            maximum = int(bucket_ids.max())
            if minimum < 0 or maximum >= self.bucket_count:
                raise ValueError("bucket_ids are outside the configured bucket range")
        residual = self.embedding(bucket_ids)
        return residual.masked_fill(bucket_ids.eq(self.padding_idx).unsqueeze(-1), 0.0)
