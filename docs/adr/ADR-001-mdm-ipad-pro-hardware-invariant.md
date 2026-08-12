# ADR-001: Standardization on MDM-Locked M4 iPad Pro Hardware Invariant

## Status
**Approved**

## Context
Our legacy technical blueprints made frequent reference to a "Bring-Your-Own-Device" (BYOD) deployment strategy, permitting on-scene tow operators to capture collision evidence using standard personal smartphones (iOS and Android).

However, consumer devices exhibit extreme variance in camera sensor calibration, focal length drift, gyroscopic precision, and LiDAR depth arrays. Attempting to run high-precision, sub-centimeter volumetric crush-depth calculations on uncalibrated, fragmented consumer hardware results in high statistical variance, rendering our physical damage adjudication unreliable and leaving our evidence vulnerable to chain-of-custody and spoliation challenges under Federal Rules of Evidence 901 and 902.

Furthermore, personal mobile units lack centralized Mobile Device Management (MDM) overrides, exposing sensitive B2B property records, GPS telemetry, and driver PII to severe client-side security leaks.

## Decision
We hereby permanently deprecate all support for consumer smartphone and BYOD capture configurations.

**100% of the Gavel Frontline Ingestion pipeline is standardized on fleet-issued, MDM-locked 11-inch M4 iPad Pro units with native physical LiDAR arrays and 5G cellular modems.**

### Hardware Lock
- The Gavel client application will be compiled exclusively for iPadOS, enforcing strict MDM containerization.
- All deployment configurations must enforce iPad Pro M4 as the sole supported device class.
- Device enrollment verified against `calibrated_devices` table in PostgreSQL before any CrashBundle acceptance.

### Hardware Gates
- The client leverages the M4 iPad's physical LiDAR scanner to output raw depth point clouds.
- Completely blocks any 2D visual fallbacks or uncalibrated camera streams.
- Point-cloud data integrity validated before acceptance by backend adjudication service.
- Laplacian sharpness gate (variance ≥ 160) and acoustic noise floor gate (≤ -40 dB) enforced on all 16 frames.

### Calibration Verification
- The API ingestion gate queries incoming device metadata.
- Verifies device's unique MDM enrollment token against active hardware ledger before accepting any `CrashBundle`.
- Rejection criteria:
  - Device not found in `calibrated_devices` table
  - Device status ≠ `ACTIVE`
  - MDM lock not verified
  - LiDAR calibration flag = FALSE
  - Last ping > 48 hours ago

## Consequences

### ✅ Elimination of Sensor Drift
- DARCI Physics Engine receives highly uniform, calibrated 3D spatial data.
- Stabilizes on-scene volumetric crush evaluations.
- Reduces variance in deformation entropy calculations to sub-5% deviation.
- Enables deterministic total-loss verdicts defensible in regulatory audits.

### ✅ Litigation-Grade Chain of Custody
- MDM security profiles allow cryptographic locking of camera, microphone, and filesystem.
- Satisfies strict regulatory audits (FRE 901/902, GDPR, CCPA data integrity).
- Makes data tampering on-scene physically impossible via device-level enforcement.
- Enables cryptographic proof-of-authenticity for all captured evidence.
- Post-quantum Dilithium-2 (ML-DSA) signatures on all CrashBundles for future-proof forensics.

### ✅ Developer Focus & Velocity
- Front-end development teams bypass Android and multi-device viewport optimization.
- Building exclusively for 11-inch iPad Pro landscape viewport (2360 × 1640 resolution).
- Drastically reduces MVP development cycle times (estimated 30% acceleration).
- Simplifies WebRTC, LiDAR, gyroscopic, and microphone API integrations.
- Single-device testing matrix eliminates fragmentation QA burden.

### ⚠️ Operational Constraints
- Tow companies must invest in MDM-managed iPad fleet (estimated $12-15K per unit in 2026).
- Device replacement/upgrade cycles tied to Apple's product roadmap.
- No fallback capture pathway if device is offline or damaged.
- Single point of failure at device level requires robust redundancy.

## Mitigation Strategies

### 1. Spare Device Pool
- Maintain 20% spare inventory for rapid device replacement.
- Pre-provisioned with latest Gavel client and MDM profiles.
- Geographically distributed across operational regions.

### 2. Offline Queue & Resilience
- Implement IndexedDB-based FIFO outbox on device to queue submissions during network downtime.
- Client maintains strict chronological ordering to prevent chain spoliation.
- Auto-retry logic with exponential backoff on network recovery.

### 3. Device Health Monitoring
- Real-time dashboard tracking MDM status, LiDAR calibration, battery health, last-ping timestamp.
- Automated alerts if device goes offline > 24 hours.
- Daily calibration drift assessments sent to backend.

### 4. Staged Rollout
- Pilot with San Antonio tow fleet (50 units) before national expansion.
- A/B test against legacy smartphone captures to validate accuracy improvements.
- Monthly hardware audit and recalibration cycles.

## Alternatives Considered

### Alternative 1: Multi-Device Support with Software Calibration
**Rejected:** Software calibration cannot compensate for hardware-level sensor variance. Risk of litigation-grade evidence rejection under FRE 901. Maintainability nightmare across fragmented device ecosystem.

### Alternative 2: Hybrid BYOD + Fleet Model
**Rejected:** Mixed deployment introduces operational complexity, training burden, and creates regulatory inconsistency in chain-of-custody protocols. Compliance nightmares in audits.

### Alternative 3: Wait for Consumer Android/iOS Standardization
**Rejected:** Consumer hardware evolution is unpredictable and driven by consumer market, not enterprise forensics. Enterprise lock-in to iPad Pro M4 provides stability and litigation defensibility for next 3+ years.

### Alternative 4: Generic Tablet Standard (Samsung Tab, etc.)
**Rejected:** iPad Pro M4 is the only commercial device with LiDAR scanner, 5G modem, and enterprise MDM support in a single package. Alternatives lack hardware gates required for DARCI accuracy.

## Approval & Sign-Off
- **Decision Date:** August 9, 2026
- **Approved By:** Ramsey Ibrahim (Founder, Claim2Car Connect)
- **Engineering Lead:** [GitHub User Assignment Pending]
- **Legal Review:** Texas Transportation Counsel - § 2308.401 Compliance Audit (Approved)
- **Compliance Review:** FRE 901/902 Evidence Standards (Approved)

## Related Issues
- GitHub Issue #1: [PHASE 1] Zero-Trust Container Isolation & PII Encryption
- GitHub Issue #2: [PHASE 2] Replace DARCI Physics Placeholders with Real Calculations
- GitHub Issue #3: [PHASE 3] React PWA Frontend + Capacitor Integration
- ADR-002: Post-Quantum Cryptography (Dilithium-2 ML-DSA) Implementation (Pending)
- ADR-003: Outcome-Blind Payout Enforcement Architecture (Pending)

## References
- Federal Rules of Evidence § 901, 902 (Authentication of Electronic Records)
- Texas Occupations Code § 2308.401, 2308.402 (Outcome-Blind Tow Payout Requirements)
- NIST FIPS 204 ML-DSA Specification (Post-Quantum Digital Signature Standard)
- Apple MDM Framework Documentation (Enterprise Device Management)
- ISO 9241-210:2019 (Ergonomics of Human-System Interaction)
