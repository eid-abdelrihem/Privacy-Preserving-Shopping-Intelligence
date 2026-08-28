#!/usr/bin/env node

import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const MASK64 = (1n << 64n) - 1n;
const PRIME64_1 = 0x9e3779b185ebca87n;
const PRIME64_2 = 0xc2b2ae3d27d4eb4fn;
const PRIME64_3 = 0x165667b19e3779f9n;
const PRIME64_4 = 0x85ebca77c2b2ae63n;
const PRIME64_5 = 0x27d4eb2f165667c5n;

function uint64(value) {
  return value & MASK64;
}

function rotateLeft(value, count) {
  const width = BigInt(count);
  return uint64((value << width) | (value >> (64n - width)));
}

function readUint64LE(buffer, offset) {
  let value = 0n;
  for (let index = 0; index < 8; index += 1) {
    value |= BigInt(buffer[offset + index]) << BigInt(8 * index);
  }
  return value;
}

function readUint32LE(buffer, offset) {
  let value = 0n;
  for (let index = 0; index < 4; index += 1) {
    value |= BigInt(buffer[offset + index]) << BigInt(8 * index);
  }
  return value;
}

function xxh64Round(accumulator, lane) {
  let result = uint64(accumulator + uint64(lane * PRIME64_2));
  result = rotateLeft(result, 31);
  return uint64(result * PRIME64_1);
}

function xxh64MergeRound(accumulator, lane) {
  let result = uint64(accumulator ^ xxh64Round(0n, lane));
  return uint64(uint64(result * PRIME64_1) + PRIME64_4);
}

function xxh64(buffer, seed) {
  let offset = 0;
  let hash;

  if (buffer.length >= 32) {
    let lane1 = uint64(seed + PRIME64_1 + PRIME64_2);
    let lane2 = uint64(seed + PRIME64_2);
    let lane3 = uint64(seed);
    let lane4 = uint64(seed - PRIME64_1);
    const limit = buffer.length - 32;

    while (offset <= limit) {
      lane1 = xxh64Round(lane1, readUint64LE(buffer, offset));
      offset += 8;
      lane2 = xxh64Round(lane2, readUint64LE(buffer, offset));
      offset += 8;
      lane3 = xxh64Round(lane3, readUint64LE(buffer, offset));
      offset += 8;
      lane4 = xxh64Round(lane4, readUint64LE(buffer, offset));
      offset += 8;
    }

    hash = uint64(
      rotateLeft(lane1, 1) +
        rotateLeft(lane2, 7) +
        rotateLeft(lane3, 12) +
        rotateLeft(lane4, 18),
    );
    hash = xxh64MergeRound(hash, lane1);
    hash = xxh64MergeRound(hash, lane2);
    hash = xxh64MergeRound(hash, lane3);
    hash = xxh64MergeRound(hash, lane4);
  } else {
    hash = uint64(seed + PRIME64_5);
  }

  hash = uint64(hash + BigInt(buffer.length));

  while (offset + 8 <= buffer.length) {
    const lane = xxh64Round(0n, readUint64LE(buffer, offset));
    hash = uint64(hash ^ lane);
    hash = uint64(uint64(rotateLeft(hash, 27) * PRIME64_1) + PRIME64_4);
    offset += 8;
  }

  if (offset + 4 <= buffer.length) {
    hash = uint64(hash ^ uint64(readUint32LE(buffer, offset) * PRIME64_1));
    hash = uint64(uint64(rotateLeft(hash, 23) * PRIME64_2) + PRIME64_3);
    offset += 4;
  }

  while (offset < buffer.length) {
    hash = uint64(hash ^ uint64(BigInt(buffer[offset]) * PRIME64_5));
    hash = uint64(rotateLeft(hash, 11) * PRIME64_1);
    offset += 1;
  }

  hash = uint64(hash ^ (hash >> 33n));
  hash = uint64(hash * PRIME64_2);
  hash = uint64(hash ^ (hash >> 29n));
  hash = uint64(hash * PRIME64_3);
  return uint64(hash ^ (hash >> 32n));
}

function lengthPrefixedUtf8(value) {
  if (typeof value !== "string" || value.length === 0) {
    throw new Error("identity component must be a non-empty string");
  }
  const encoded = Buffer.from(value, "utf8");
  if (encoded.length > 0xffffffff) {
    throw new Error("identity component exceeds uint32 byte length");
  }
  const prefix = Buffer.alloc(4);
  prefix.writeUInt32BE(encoded.length);
  return Buffer.concat([prefix, encoded]);
}

function serializeIdentity(namespace, identifier) {
  return Buffer.concat([lengthPrefixedUtf8(namespace), lengthPrefixedUtf8(identifier)]);
}

function mapDigestToBucket(digest, config) {
  const reserved = Object.values(config.reserved_indices).sort((left, right) => left - right);
  const usableCount = config.bucket_count - reserved.length;
  if (usableCount < 1) {
    throw new Error("no usable bucket");
  }
  let bucket = Number(digest % BigInt(usableCount));
  for (const reservedIndex of reserved) {
    if (bucket >= reservedIndex) {
      bucket += 1;
    } else {
      break;
    }
  }
  if (reserved.includes(bucket)) {
    throw new Error("digest mapped into reserved bucket");
  }
  return bucket;
}

function canonicalJson(value) {
  if (value === null || typeof value !== "object") {
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) {
    return "[" + value.map(canonicalJson).join(",") + "]";
  }
  return (
    "{" +
    Object.keys(value)
      .sort()
      .map((key) => JSON.stringify(key) + ":" + canonicalJson(value[key]))
      .join(",") +
    "}"
  );
}

function assertEqual(actual, expected, field) {
  if (actual !== expected) {
    throw new Error(field + ": expected " + expected + ", got " + actual);
  }
}

function digestHex(value) {
  return value.toString(16).padStart(16, "0");
}

function loadJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf8"));
}

function main() {
  if (process.argv.length !== 4) {
    throw new Error("usage: node verify_hashing_vectors.mjs <config.json> <vectors.json>");
  }
  const configPath = path.resolve(process.argv[2]);
  const vectorsPath = path.resolve(process.argv[3]);
  const config = loadJson(configPath);
  const vectors = loadJson(vectorsPath);

  const configWithoutHash = { ...config };
  delete configWithoutHash.config_sha256;
  const actualConfigHash = crypto
    .createHash("sha256")
    .update(Buffer.from(canonicalJson(configWithoutHash), "utf8"))
    .digest("hex");
  assertEqual(actualConfigHash, config.config_sha256, "config_sha256");
  assertEqual(vectors.hashing_config_sha256, config.config_sha256, "vector config hash");
  assertEqual(config.algorithm.id, "XXH64", "algorithm.id");
  assertEqual(config.algorithm.contract_version, "1", "algorithm.contract_version");

  for (const vector of vectors.algorithm_self_tests) {
    const actual = xxh64(Buffer.from(vector.input_hex, "hex"), BigInt(vector.seed_uint64));
    assertEqual(digestHex(actual), vector.digest_hex, vector.case_id + ".digest_hex");
    assertEqual(actual.toString(), vector.digest_uint64, vector.case_id + ".digest_uint64");
  }

  const seed = BigInt(config.algorithm.seed_uint64);
  for (const vector of vectors.identity_vectors) {
    const serialized = serializeIdentity(vector.namespace, vector.identifier);
    assertEqual(serialized.toString("hex"), vector.serialized_hex, vector.case_id + ".bytes");
    const digest = xxh64(serialized, seed);
    assertEqual(digestHex(digest), vector.digest_hex, vector.case_id + ".digest_hex");
    assertEqual(digest.toString(), vector.digest_uint64, vector.case_id + ".digest_uint64");
    assertEqual(
      mapDigestToBucket(digest, config),
      vector.bucket_index,
      vector.case_id + ".bucket_index",
    );
  }

  for (const vector of vectors.reserved_vectors) {
    assertEqual(vector.hash_applied, false, vector.case_id + ".hash_applied");
    assertEqual(
      config.reserved_indices[vector.input_kind],
      vector.bucket_index,
      vector.case_id + ".bucket_index",
    );
  }

  process.stdout.write(
    JSON.stringify({
      algorithm: "XXH64",
      config_sha256: config.config_sha256,
      runtime: "node-bigint-reference",
      status: "PASS",
      vectors_validated:
        vectors.algorithm_self_tests.length +
        vectors.identity_vectors.length +
        vectors.reserved_vectors.length,
    }) + "\n",
  );
}

try {
  main();
} catch (error) {
  process.stderr.write(String(error.stack || error) + "\n");
  process.exitCode = 1;
}
