# Fixed-Size Hashed Product Representation

Task: S1-SE-05 / Issue #25

Status: the parameterized hashing contract and a CONFORMANCE_ONLY profile are
implemented. No MODEL_DEFAULT configuration is frozen.

The intentionally absent production path is:

    config/features/hashing.v1.json

That file may be created only after all three members approve the bucket count,
residual dimension, uint64 seed, reserved PAD/OOV/NULL indices and semantics,
and ownership of the default configuration.

## Scope and privacy boundary

XXH64 provides a deterministic compact product representation. It is not
encryption, anonymization, pseudonymization, or a cryptographic hash. Product
identifiers must still be handled according to the project's privacy boundary.
SHA-256 is used separately for configuration and artifact integrity.

Category and brand are not folded into the product hash. They remain separate
Phase1Batch v1 categorical channels and can use their own stable vocabularies.

## Canonical item adapter

CanonicalEvent v1 currently exposes item identifiers such as:

    rees46:item:44600062

The source_entity_raw_v1 adapter splits at most twice:

    namespace  = rees46:item
    identifier = 44600062

The identifier remains an opaque string. Numeric conversion, whitespace
trimming, case folding and Unicode normalization are forbidden.

The local CanonicalEvent handoff contains the real smoke Parquet and descriptive
contract, but the synthetic CanonicalEvent golden fixture and reusable schema
validator named in Issue #6 are not present. S1-SE-05 therefore owns only its
hash-specific conformance fixture and records this upstream integration gap.

The integration suite reads real item IDs from fixtures/smoke_sample.parquet,
checks the CanonicalEvent/v1 namespace grammar, and passes those IDs through the
hash adapter into shape-preserving int64 buckets. The missing reusable validator
still prevents S1-SE-05 from claiming ownership of the complete CanonicalEvent
contract.

## Serialization contract

For UTF-8 byte strings N and I:

    u32be(len(N)) || N || u32be(len(I)) || I

Lengths are byte counts, not Unicode code-point counts. There is no BOM.
Empty components and non-string components fail. The maximum encoded component
length is 2^32 - 1 bytes.

The configuration identifier for this serialization is:

    lp_u32be_utf8_namespace_id_v1

## Hash contract

The reference implementation is python-xxhash 4.0.1 with bundled xxHash 0.8.3:

    XXH64(serialized_bytes, uint64_seed).intdigest()

The digest is interpreted as an unsigned 64-bit integer. Golden vectors store
both its 16-character lowercase hexadecimal representation and its unsigned
decimal string. Implementations must not use Python hash() or signed modulo.

The JSON seed is a canonical decimal string so values above JavaScript's safe
integer limit remain exact. Leading zeroes, negative values and values above
2^64 - 1 fail.

## Reserved slots and bucket mapping

PAD, OOV and NULL are typed non-hashed states:

- PAD is used only for masked storage positions.
- OOV is produced only by an explicit upstream OOV sentinel.
- NULL is produced only by an explicit null input.

The strings "PAD", "OOV" and "NULL" are not special product IDs. A caller must
use ReservedProductId. None is handled before serialization and maps to NULL;
it is never stringified.

For R sorted reserved indices:

    usable_count = bucket_count - len(R)
    bucket = unsigned_digest % usable_count
    for reserved_index in R:
        if bucket >= reserved_index:
            bucket += 1

The configuration fails if indices are duplicated, out of range, or leave no
usable bucket. This rank-to-bucket mapping supports non-contiguous reservations
and never takes modulo over a reserved slot.

## Tensor and model boundary

bucketize_product_inputs and bucketize_canonical_item_ids consume flat row-major
values plus an explicit shape. They return a CPU torch.int64 tensor with exactly
that shape. A value-count mismatch fails.

ProductHashResidual is an nn.Embedding-backed product-only interface:

    [B,L] -> [B,L,D]
    [B,K] -> [B,K,D]

PAD output is explicitly zero. The configuration SHA is a Python attribute, not
a persistent integer buffer, because the current federated SharedStateSpec
permits floating model state only. The config reference belongs in the later
ModelConfig/representation identity.

ONNX models consume prehashed int64 bucket tensors. XXH64 string preprocessing
is deliberately outside the standard ONNX graph. Any future mobile or ONNX-side
preprocessor must first pass the same language-neutral golden vectors.

## Conformance profile

fixtures/features/hashing_conformance_config.v1.json deliberately uses:

    profile             CONFORMANCE_ONLY
    seed_uint64         18446744073709551615
    bucket_count        17
    reserved_indices    PAD=0, OOV=3, NULL=16
    residual_dimension  5

These values exercise uint64 handling and non-contiguous reservations. They are
test parameters and are prohibited from becoming model defaults implicitly.

The semantic HashingConfig SHA-256 is:

    27ee2f0a13adf319efd3ff8e6bf17a96970407fa259b2c229a5fba29c0445fd9

The golden vectors cover ASCII, namespace isolation, UTF-8 byte lengths,
NFC/NFD preservation, an identifier larger than uint64, concatenation
ambiguity, digests above signed int64, PAD/OOV/NULL, and known-bad inputs.

The independent Node.js verifier implements XXH64 with BigInt and has no npm
dependency. Node.js is therefore a required test runtime for this contract.

## Validation

Run:

    uv run --locked ruff check ppsi/features scripts/features tests/features
    uv run --locked ruff format --check ppsi/features scripts/features tests/features
    uv run --locked python -m pytest tests/features tests/training/test_batch_contract.py -v
    uv run --locked python scripts/features/validate_hashing.py --cross-runtime node
    uv run --locked python -m pytest -q tests/experiments tests/training tests/features
    uv run --locked python scripts/features/generate_hashing_artifact_manifest.py --verify

The subprocess test repeats validation with PYTHONHASHSEED values 0, 1, 42 and
random and requires byte-identical output.

## Decision gate before MODEL_DEFAULT

The team must provide and approve:

1. unique-product count and item-frequency evidence from the frozen data;
2. collision, occupied-bucket and maximum/p95/p99 load for candidate sizes;
3. model, optimizer-state and federated communication size estimates;
4. the final bucket count and residual dimension;
5. the final uint64 seed;
6. distinct PAD/OOV/NULL indices and the documented semantics above;
7. ownership of config/features/hashing.v1.json.

The production config, downstream ModelConfig reference, final default golden
mapping and Issue closure remain blocked until that decision is recorded.
