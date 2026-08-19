# Privacy-Preserving-Shopping-Intelligence-via-Federated-On-Device-Learning
_______________________________________________________________________________

## Phase 1 data pipeline

The reproducible REES46 October 2019 CSV-to-Parquet pipeline is documented in
[`docs/s1-ds-02-csv-to-parquet.md`](docs/s1-ds-02-csv-to-parquet.md).

Run its fast synthetic validation with:

```powershell
python scripts/data/convert_rees46.py self-test
```

Raw CSV, ZIP, and generated Parquet artifacts are intentionally excluded from
normal Git history. The repository contains their versioned manifests, hashes,
aggregate conversion report, and reproduction code.
