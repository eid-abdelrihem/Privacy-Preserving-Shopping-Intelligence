# Phase 1 Threat Model and Privacy Boundary

- Status: Initial Phase 1 model
- Scope: R1 centralized training, simulated R2A/FedAvg, repository/CI, and research artifacts
- Source revision reviewed: 440fd745144b3b28c443c3393ae1f080eaea4f07
- Owner: S1-SE-04
- Required refresh: S2-SE-07 after the architecture and demo protocol are frozen

This document describes security and privacy boundaries that the repository actually
implements or explicitly plans. It is not a vulnerability report and does not claim that
hypothetical attacks have been demonstrated.

## 1. Overview

### 1.1 Intended use

The repository is an offline research system for controlled comparison of shopping
recommendation training regimes. Phase 1 currently provides:

- local CSV-to-Parquet preparation for REES46 research data;
- a shared tensor contract and local trainer core;
- an R1 centralized adapter;
- a local, synthetic R2A Flower/FedAvg simulation backed by Ray;
- trusted internal checkpoint and experiment-result contracts.

It is not currently a web service, remote federated deployment, browser application, or
multi-tenant system. No anonymous network client, application authentication layer, or
production telemetry endpoint exists in the reviewed source.

### 1.2 Components and source evidence

| Component | Role and sensitive data | Evidence |
|---|---|---|
| Data conversion | Reads event time/type, product/category/brand, price, user, and session identifiers; writes processed and rejection artifacts | docs/data-source.md:114-124, scripts/data/convert_rees46.py:193-207 |
| Phase1Batch v1 | Carries history, query, candidates, labels, gains, and task masks | ppsi/training/batch.py:114-137 |
| R1 centralized adapter | Makes all supplied batches available to one process and model | ppsi/training/centralized.py:35-68 |
| Shared-state contract | Currently declares every safe floating parameter/buffer shared and validates keys, shapes, dtypes, and finiteness | ppsi/training/state.py:39-72, ppsi/training/state.py:124-176 |
| R2A Flower client | Receives shared state, trains on client-local batches, and returns updated state plus metrics and digests | scripts/training_smoke.py:74-109, ppsi/training/flower.py:82-123 |
| Flower coordinator | Initializes the model and runs FedAvg rounds over local Ray workers | scripts/training_smoke.py:155-216 |
| Server evaluator | In the current synthetic smoke, recreates both clients' batches centrally for evaluation | scripts/training_smoke.py:135-152 |
| Checkpoint loader | Loads trusted internal PyTorch checkpoints only after byte and semantic checks | ppsi/training/checkpoint.py:220-270 |
| Experiment result | Records regime/run identity, compatibility hashes, metrics, artifact references, and optional federated metadata | ppsi/training/result.py:40-105 |
| Repository and future CI | Stores source, small fixtures, schemas, evidence, and lockfiles; review is intended to require another member | docs/decisions.md:25-31, docs/artifacts.md:3-55 |

### 1.3 Primary data flows and trust zones

~~~mermaid
flowchart LR
    DS[REES46 source and local artifact storage]

    subgraph R1Zone[R1 centralized host]
        R1Loader[Centralized loader]
        R1Trainer[Shared trainer core]
        R1Loader -->|raw histories and labels| R1Trainer
    end

    subgraph SimHost[Shared Flower and Ray simulation host]
        Coord[Flower coordinator]
        C1[Logical client 1]
        C2[Logical client 2]
        Eval[Server evaluator]
        Coord -->|shared model state and config| C1
        Coord -->|shared model state and config| C2
        C1 -->|updated state and approved metrics| Coord
        C2 -->|updated state and approved metrics| Coord
        Coord --> Eval
    end

    Repo[Git repository and future CI]
    Store[Checkpoint, result, and artifact storage]

    DS --> R1Loader
    DS -. future client partitions .-> C1
    DS -. future client partitions .-> C2
    R1Trainer --> Store
    Coord --> Store
    Repo --> R1Zone
    Repo --> SimHost
    Store -->|approved manifests and aggregate evidence only| Repo
~~~

The dotted client-data flows are future real-data work. The currently executable Flower
smoke generates deterministic synthetic batches inside local workers.

### 1.4 Effective resource boundaries

| Deployment or workflow | Resource or capability | Safe effective value or location | Readers, writers, or recipients | Enforcing control | Evidence or unknowns |
|---|---|---|---|---|---|
| Full conversion | Raw REES46 CSV | Local storage outside normal Git history | Local operator and converter | Expected size, SHA-256, and header checks before scanning | docs/data-source.md:188-206, scripts/data/convert_rees46.py:90-111 |
| Full conversion | Processed/rejected Parquet and reports | Ignored local artifact directory or an approved artifact store | Researchers with host/store access | Refuse overwrite, reconciliation, and recorded hashes | scripts/data/convert_rees46.py:277-308, scripts/data/convert_rees46.py:339-405 |
| Shared smoke fixture | Complete selected user histories | fixtures/smoke_sample.parquet in Git | Every repository checkout and future CI job | Repository access/review only; namespacing is not anonymization | .gitignore:431-439, docs/s1-ds-03-canonical-event.md:44-65 |
| R1 | Training histories and labels | Centralized process memory | R1 host and its operator | Host access controls; trainer validation protects integrity, not confidentiality | ppsi/training/centralized.py:35-68 |
| Simulated R2A | Client batches and shared state | One shared Flower/Ray host | Host operator, Ray workers, coordinator as allowed by process memory | Logical message/API separation plus state validation; no physical isolation | scripts/training_smoke.py:74-109, scripts/training_smoke.py:206-216 |
| Checkpoints | Model, optimizer, scheduler, and RNG state | Caller-selected trusted artifact path | Runtime and authorized artifact readers/writers | Atomic save, expected SHA-256, and semantic compatibility | ppsi/training/checkpoint.py:220-270; canonical ACL, encryption, and retention remain undefined |
| Results/evidence | Metrics, identifiers, hashes, and artifact references | Repository-relative evidence or future registry | Researchers, reviewers, and future CI | Schema and hash validation; access control belongs to Git/artifact store | ppsi/training/result.py:40-105 |

## 2. Threat Model, Trust Boundaries, and Assumptions

### 2.1 Protected assets

- Raw and processed browsing histories, including views, carts, purchases, timestamps,
  products, categories, brands, prices, user IDs, and session IDs.
- Task labels, query/candidate sets, cohort membership, and per-client contribution data.
- Model parameters, model updates, optimizer state, checkpoints, and local-only state in
  future personalized regimes.
- Secrets and credentials used by developers, CI, cloud compute, or artifact stores.
- Scientific integrity: dataset, split, protocol, configuration, initialization, evaluator,
  Git revision, result, and artifact identities.
- Repository/CI authority and the ability to approve, merge, publish, or alter evidence.
- Accuracy of the project's privacy claims.

Stable dataset IDs are treated as linkable behavioral identifiers. Prefixing or hashing an
ID does not establish anonymity.

### 2.2 Actors and realistic starting capabilities

| Actor | Starting capability | Capability not assumed |
|---|---|---|
| Dataset supplier or local file writer | Can supply malformed or modified local input | Cannot change the trusted manifest or repository review without separate authority |
| Research developer/contributor | Can create branches and propose source/config/artifact changes | Cannot legitimately supply the independent approval required by team policy |
| R1 host operator | Can read all R1 training examples and process memory by design | Is not treated as privacy-isolated from centralized training data |
| Flower coordinator operator | Controls aggregation, server configuration, and received updates/metadata | Must not be described as unable to inspect received updates |
| Logical federated client | In a future deployment, may control local examples, update, weight, metrics, and failure behavior | Does not automatically have repository, coordinator, or artifact-store authority |
| Shared Flower/Ray host operator | Can potentially inspect memory, temporary files, logs, and processes for all simulated clients | Is not a physically isolated device or mutually distrusting client |
| Repository/CI actor | Can read tracked fixtures and execute workflows with granted permissions | Does not receive secrets or artifact-store write authority unless explicitly granted |
| Artifact-store reader/writer | Can access the specific artifacts allowed by external policy | Does not gain authenticity merely because a file carries a hash beside it |

### 2.3 Trust boundaries and invariants

#### Dataset storage to preprocessing

- The expected raw file identity and schema must be checked before use.
- Full raw/processed histories and rejected rows must remain outside normal Git history.
- A checksum is an integrity comparison against a trusted reference, not access control.

#### R1 centralized boundary

- R1 intentionally makes all selected histories available to the centralized host.
- R1 must never be described as on-device or federated privacy.
- Logs and evidence must not publish user-level histories or stable identifiers unnecessarily.

#### R2A logical client to coordinator boundary

- The implemented message path sends shared model state and approved scalar
  metrics/identities; it does not emit the raw synthetic history itself
  (scripts/training_smoke.py:74-109).
- Current Phase 1 shares all declared floating state
  (ppsi/training/state.py:47-72). Updates and metadata may leak information.
- Shared/local ownership, state keys, shapes, dtypes, and finiteness must fail closed.
- Client enrollment, transport authentication, Byzantine robustness, secure aggregation,
  and differential privacy do not exist in the current local simulation.

#### Coordinator to simulation-host boundary

- The Flower coordinator and the shared Ray host are separate logical roles but normally
  share one physical host authority in Phase 1.
- A shared simulation host may inspect client memory or runtime resources.
- Logical client/message separation is useful for correctness testing; it does not prove
  physical device, process, user, or administrative isolation.
- The current server evaluator recreates all synthetic client batches centrally
  (scripts/training_smoke.py:135-152), so it is not a private evaluation design.

#### Repository, PR, and CI boundary

- Every PR requires approval from another member and no author should self-merge
  (docs/decisions.md:25-31).
- Branch/ruleset enforcement, CI permissions, fork behavior, secrets, cache keys, and
  retention are owned by #21 and #22. Until verified, the documented review rule is a
  procedural control.
- CI must use synthetic/smoke data only unless a separately approved data-access design
  exists.

#### Artifact and checkpoint boundary

- Checkpoints are trusted internal artifacts only. The loader uses
  torch.load with weights_only=False after integrity checks
  (ppsi/training/checkpoint.py:233-247).
- If checkpoints ever become untrusted inputs, this security assumption no longer holds
  and the deserialization design must be replaced or isolated.
- Artifact paths, readers/writers, retention, and trusted digest source must be explicit.

### 2.4 Security objectives

1. Raw client histories must not be serialized into implemented R2A client-to-server
   messages or routine logs.
2. Only explicitly approved shared state and metadata may cross the logical R2A boundary.
3. Full raw/processed data, rejection artifacts, checkpoints, and user-level derivatives
   must stay outside normal Git history and generic CI artifacts.
4. Result and evidence records must be aggregate or opaque enough to avoid unintended
   user-history linkage.
5. Dataset, protocol, model, initialization, environment, result, and artifact identities
   must be verified at the consumer before scientific comparison.
6. Repository and CI permissions must follow least privilege; secrets must never enter
   source, PR output, caches, or untrusted fork jobs.
7. Untrusted checkpoints must never reach the current PyTorch loader.
8. Claims must distinguish data locality from a formal privacy guarantee.

### 2.5 Privacy claim matrix

| Claim | Phase 1 position |
|---|---|
| R2A's implemented message/API path does not send raw local history | Supported for the current synthetic path, subject to future real-loader verification |
| R2A runs on physically isolated user devices | Not supported; it is a shared-host Ray simulation |
| The coordinator cannot learn from model updates or metadata | Not supported |
| Model updates are anonymous | Not supported |
| Differential privacy is implemented | Not implemented |
| Secure aggregation is implemented | Not implemented |
| Namespaced/hashed IDs are anonymous | Not supported |
| R1 preserves data locality | False by definition; R1 is centralized |

The approved wording is data locality and reduced raw-data centralization
(docs/papers-notes.md:260-290). Differential privacy and secure aggregation remain future
work (docs/papers-notes.md:399-408).

### 2.6 Assumptions, exclusions, and open questions

- Current R1 and R2A examples use synthetic Phase1Batch values; real REES46 orchestration
  is later work.
- Current R2A is local simulation. Remote client authentication, enrollment, transport,
  storage, and device isolation are outside the implemented boundary.
- Dataset hosting terms must be reviewed before redistribution
  (docs/data-source.md:198-206).
- Repository visibility, protection, CI, and security-setting read-back are maintained by
  #21/#22 and must be referenced after those tasks merge.
- The tracked Parquet fixture is an explicit exception to the general Parquet ignore rule
  (.gitignore:431-439). Its approved audience, retention, and publication decision need
  explicit confirmation.
- Ray temporary/object-store/log paths and cleanup use host/library defaults; exact
  locations and retention are not defined by repository code.
- Checkpoint ACLs, encryption, canonical location, backup, and retention are not yet
  frozen.
- R2A per-client metrics allowed in stored evidence are not yet frozen.
- This model does not treat an attacker who already controls the local operator or
  repository owner account as gaining a new capability through ordinary authorized use.

## 3. Attack Surface, Mitigations, and Attacker Stories

All rows below are threat hypotheses for design and review. They are not validated
vulnerabilities.

| Priority | Scenario and capability gain | Prerequisites | Impact | Existing controls | Required mitigation and residual risk | Evidence |
|---|---|---|---|---|---|---|
| High | A contributor or artifact publisher commits or uploads raw/derived user histories, rejection rows, or an overly rich fixture | Ability to propose a change or publish to an artifact store | Broadens access to linkable shopping behavior beyond the approved audience | Dataset patterns are ignored; PR review is documented | #21/#22 enforcement, secret/data review checklist, manifest/allowlist, aggregate-only evidence, explicit fixture audience and retention. Git history and approved artifact recipients remain residual exposure | docs/data-source.md:188-206, .gitignore:431-439 |
| High | A future malicious client returns a poisoned update or dishonest aggregation weight/metrics | Real clients or externally controlled partitions are introduced | Model integrity failure, targeted degradation, or manipulated research conclusions | State key/shape/dtype/finiteness checks and deterministic aggregation smoke | Freeze enrollment, weighting, clipping/outlier rules, failure handling, and robust validation before remote/untrusted clients. Current FedAvg has no Byzantine defense | ppsi/training/flower.py:82-123, ppsi/training/state.py:135-158 |
| High | An untrusted checkpoint reaches the current loader and abuses unsafe deserialization | The trusted-internal-only contract is bypassed and attacker controls a checkpoint plus trusted hash reference | Code execution with training-host authority | Byte hash and semantic checks before torch.load; contract excludes untrusted checkpoints | Keep source and expected digest independently trusted, restrict artifact writers, and never accept external checkpoints. Replace/isolate the loader if this assumption changes | ppsi/training/checkpoint.py:220-270 |
| High | A contributor changes splits, protocol, config, initialization, or evidence so incomparable runs appear comparable | Change is merged or artifact identity is not verified at consumption | Invalid thesis results and false privacy/utility conclusions | Versioned schemas, compatibility hashes, artifact manifests, peer-review policy | #28 cross-lane checks, #12 leakage tests, immutable manifests, signed/reviewed Git source, and consumer-side hash verification. Trusted reviewer collusion remains a governance risk | ppsi/training/result.py:40-105, docs/artifacts.md:17-55 |
| Medium | Model updates or per-client metrics expose membership, behavior, or participation information | Real user partitions and stored/transmitted client-level evidence | Privacy leakage without raw-history transmission | Raw batches are not in the current message payload; shared-state validation | Minimize per-client fields, use opaque client IDs, aggregate reports, restrict retention/access, and evaluate DP/Secure Aggregation separately before claiming them. Plain FedAvg residual risk remains | scripts/training_smoke.py:74-109, docs/papers-notes.md:267-290 |
| Medium | Shared Ray host, logs, temp files, or object store expose multiple clients' histories/state | Real client batches enter a shared simulation host | One host operator can inspect all simulated clients, defeating physical isolation | Host OS access controls; current data is synthetic | Use synthetic CI data, configure/clean runtime storage, restrict host access, and treat simulation as one trust zone. Physical isolation remains unproven until a separate deployment exists | scripts/training_smoke.py:206-216 |
| Medium | A secret enters source, PR output, workflow logs, caches, or artifacts | Developer/CI has a credential and mishandles it | Repository, cloud, dataset, or artifact-store compromise | Basic .env ignore; #21 owns the full policy | Apply #21 secret policy/push protection and #22 least-privilege workflow permissions; rotate on exposure. Provider-side copies remain outside repository control | docs/decisions.md:25-31 |
| Medium | Stable IDs, small cohorts, or detailed failure/loss records enable linkage in published evidence | Real user-level metadata is persisted and audience has auxiliary information | Inference about an individual's shopping behavior or participation | ExperimentResult is structured; current committed smoke is synthetic | Freeze an allowlist of aggregate fields, minimum-support/redaction rules, opaque IDs, retention, and audience. Exact re-identification risk remains dataset/context dependent | ppsi/training/result.py:66-104 |
| Low | Externally influenced client/round/shape settings exhaust CPU, RAM, disk, or CI budget | A configuration boundary becomes untrusted | Availability loss or unexpected cloud cost | Current configs are repository-controlled and small | Validate maximums, timeouts, concurrency, disk limits, and CI budgets before accepting untrusted configuration | config/unified_trainer_smoke.v1.json:1-10 |

## 4. Severity Calibration

Severity is based on realistic new capability, affected asset, reachability, and effective
controls. Confidence or missing evidence is reported separately from impact.

### Critical

Examples:

- unauthenticated remote compromise of a deployed service that yields the full raw dataset,
  all repository/CI secrets, or arbitrary code execution across trusted infrastructure;
- compromise of an organization-wide signing or release authority with immediate broad
  impact.

Current counterexample: no deployed public service, remote client enrollment path, or
organization-wide release system exists in the reviewed source. Do not label a local
operator's authorized filesystem access Critical.

### High

Examples:

- unintended publication of full or substantial user-level shopping histories to an
  unauthorized audience;
- untrusted checkpoint deserialization reaching a training host;
- a merged protocol/artifact integrity break that invalidates the central thesis result;
- poisoning that materially controls a real federated model used for consequential output.

Severity falls when the input is demonstrably synthetic, the attacker already owns the
host, or independent review/hash enforcement prevents the boundary crossing.

### Medium

Examples:

- leakage of per-client participation, losses, or updates for a bounded cohort;
- secrets exposed to a limited CI job with prompt rotation and narrow privileges;
- shared-host simulation artifacts revealing real client data to an additional authorized
  researcher;
- resource exhaustion of one research runner.

Severity rises with stable linkage, large cohorts, long retention, broader recipients, or
privileged reusable credentials.

### Low

Examples:

- disclosure of non-sensitive synthetic smoke metrics;
- local availability impact requiring the same operator who runs the experiment;
- documentation drift that does not change enforcement or a scientific result;
- a rejected malformed input with no sensitive content and no persisted side effect.

### Unsupported or out-of-scope stories

- Claims that current R2A provides anonymity, Differential Privacy, Secure Aggregation, or
  physical device isolation are unsupported, not security controls.
- A scenario requiring an Internet-facing API, tenant boundary, browser origin, production
  customer data pipeline, or remote client enrollment is conditional until that deployment
  is designed and reviewed.
- Ordinary access by the authorized R1 host to centralized R1 data is expected behavior,
  not a privilege escalation.
