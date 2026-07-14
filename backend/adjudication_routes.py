import os
import re
import math
import uuid
import json
import httpx
import hashlib
from datetime import datetime, timezone
from typing import List, Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Header, Query, status
from pydantic import BaseModel, Field, EmailStr
from motor.motor_asyncio import AsyncIOMotorClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import text

# ============================================================================
# CONFIGURATION
# ============================================================================
MONGO_URL = os.getenv("MONGO_URL", "mongodb://mongodb:27017")
DB_NAME = os.getenv("DB_NAME", "claim2car_db")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@postgres:5432/claim2car_db")
VPIC_CACHE_TTL_SECONDS = int(os.getenv("VPIC_CACHE_TTL_SECONDS", 2592000))  # 30 days default

# ============================================================================
# DATABASE CLIENTS
# ============================================================================
mongo_client = AsyncIOMotorClient(MONGO_URL)
mongo_db = mongo_client[DB_NAME]

pg_engine = create_async_engine(DATABASE_URL, pool_size=20, max_overflow=10)

router = APIRouter(prefix="/api/v1", tags=["Forensic Adjudication & Ingestion"])

async def get_pg_session():
    async with AsyncSession(pg_engine) as session:
        yield session

# ============================================================================
# PYDANTIC SCHEMAS
# ============================================================================
class GPSPayload(BaseModel):
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    accuracy_meters: float = Field(..., ge=0.0)

class AcousticPayload(BaseModel):
    ambient_noise_db: float = Field(..., le=0.0)
    fft_peaks_hz: List[float]

class FramePayload(BaseModel):
    frame_id: UUID
    angle: str
    sharpness: float
    motion_vector: float
    storage_path: str
    hash: str

class ConsentPayload(BaseModel):
    owner_name: str
    owner_email: EmailStr
    phone: str
    signature_storage_path: str

class CrashBundlePayload(BaseModel):
    bundle_id: UUID
    session_id: UUID
    lead_id: UUID
    vin: str = Field(..., min_length=17, max_length=17)
    gavel_device_fingerprint: str
    gps: GPSPayload
    acoustic: AcousticPayload
    frames: List[FramePayload]
    consent: ConsentPayload
    merkle_root_hash: str = Field(..., min_length=64, max_length=64)

# ============================================================================
# MERKLE & INTEGRITY HELPERS
# ============================================================================
def build_merkle_tree(leaves: List[str]) -> str:
    if not leaves:
        return hashlib.sha256(b"empty_tree").hexdigest()
    sorted_leaves = sorted([l.lower() for l in leaves])
    current_level = [hashlib.sha256(leaf.encode('utf-8')).hexdigest() for leaf in sorted_leaves]
    while len(current_level) > 1:
        next_level = []
        for i in range(0, len(current_level), 2):
            left = current_level[i]
            right = current_level[i+1] if i + 1 < len(current_level) else left
            next_level.append(hashlib.sha256((left + right).encode('utf-8')).hexdigest())
        current_level = next_level
    return current_level[0]


def verify_merkle_root_invariance(frames: List[FramePayload], declared_root: str) -> bool:
    if not frames:
        return False
    frame_hashes = [f.hash for f in frames]
    computed_root = build_merkle_tree(frame_hashes)
    return computed_root.lower() == declared_root.lower()


def calculate_si_trust_score(gps_acc: float, frames_valid: bool, consent_present: bool) -> float:
    c_gps = 1.0 if gps_acc <= 10.0 else (0.7 if gps_acc <= 30.0 else 0.2)
    c_hash = 1.0 if frames_valid else 0.0
    c_meta = 1.0 if consent_present else 0.0
    weighted_product = (c_gps ** 0.30) * (c_hash ** 0.45) * (c_meta ** 0.25)
    return round(weighted_product, 4)

# ============================================================================
# DARCI PHYSICS: KE, Force, Stress, Entropy
# ============================================================================

def calculate_deformation_entropy(crush_depth_cm: float) -> float:
    try:
        depth = float(crush_depth_cm)
    except Exception:
        return 0.0
    if depth <= 0.0:
        return 0.0
    displacements = [
        depth * 0.40,
        depth * 0.25,
        depth * 0.20,
        depth * 0.10,
        depth * 0.05
    ]
    total = sum(displacements)
    probabilities = [d / total for d in displacements if d > 0]
    entropy = -sum(p * math.log2(p) for p in probabilities)
    return round(entropy, 4)


def calculate_metallurgical_stress(kinetic_energy_kj: float, body_class: str, crush_depth_cm: float) -> Dict[str, Any]:
    area_map = {
        "sedan": 0.003, "suv": 0.006, "pickup": 0.008, "van": 0.007, "generic": 0.005
    }
    area = area_map.get(body_class.lower(), 0.005)
    crush_meters = max(0.01, crush_depth_cm / 100.0)
    # kinetic_energy_kj is provided in kJ; convert to Joules for force estimate
    kinetic_j = kinetic_energy_kj * 1000.0
    force_n = kinetic_j / crush_meters
    stress_mpa = (force_n) / (area * 1e6)
    yield_limits = {"boron_steel": 1500.0, "dual_phase": 600.0, "mild_steel": 250.0}
    target_steel = "boron_steel" if body_class.lower() in ["pickup", "suv"] else ("dual_phase" if body_class.lower() == "sedan" else "mild_steel")
    failure_imminent = stress_mpa > yield_limits[target_steel]
    return {
        "stress_mpa": round(stress_mpa, 2),
        "yield_limit_mpa": yield_limits[target_steel],
        "target_steel_class": target_steel,
        "failure_imminent": failure_imminent
    }

# ============================================================================
# NHTSA vPIC integration with Mongo caching (TTL indexed)
# ============================================================================

async def ensure_vpic_cache_index():
    # Create TTL index if not present
    await mongo_db.nhtsa_cache.create_index("cached_at", expireAfterSeconds=VPIC_CACHE_TTL_SECONDS)


@router.post("/vin/decode", response_model=Dict[str, Any])
async def decode_vin_vpic(vin: str = Query(..., min_length=17, max_length=17)):
    vin_upper = vin.upper().strip()
    await ensure_vpic_cache_index()
    cached = await mongo_db.nhtsa_cache.find_one({"vin": vin_upper}, {"_id": 0})
    if cached:
        return {"source": "local_cache", "vehicle": cached["vehicle"]}
    vpic_endpoint = f"https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValuesExtended/{vin_upper}?format=json"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.get(vpic_endpoint)
        if res.status_code != 200:
            raise HTTPException(status_code=502, detail="NHTSA VPIC Service unreachable")
        results = res.json().get("Results", [])[0]
        raw_gvwr = results.get("GVWR") or ""
        extracted_mass = None
        kg_regex = re.search(r"\((\d{1,3}(?:,\d{3})*)\s*kg\)", raw_gvwr)
        if kg_regex:
            try:
                extracted_mass = float(kg_regex.group(1).replace(",", ""))
            except ValueError:
                extracted_mass = None
        if extracted_mass is None:
            # Fallback to other fields or defaults
            try:
                # Some responses have "CurbWeight" or similar fields
                curb = results.get("CurbWeightLb") or results.get("CurbWeightKG")
                if curb:
                    extracted_mass = float(curb)
            except Exception:
                extracted_mass = None
        if extracted_mass is None:
            extracted_mass = 1600.0
        sane_mass = max(500.0, min(5000.0, extracted_mass))
        vehicle_profile = {
            "vin": vin_upper,
            "make": (results.get("Make") or "GENERIC").upper(),
            "model": (results.get("Model") or "VEHICLE").upper(),
            "year": int(results.get("ModelYear")) if results.get("ModelYear") else 2020,
            "body_class": results.get("BodyClass") or "sedan",
            "curb_weight_kg": sane_mass
        }
        await mongo_db.nhtsa_cache.update_one(
            {"vin": vin_upper},
            {"$set": {"vin": vin_upper, "vehicle": vehicle_profile, "cached_at": datetime.now(timezone.utc)}},
            upsert=True
        )
        return {"source": "live_nhtsa_vpic", "vehicle": vehicle_profile}
    except Exception:
        fallback_profile = {"vin": vin_upper, "make": "TOYOTA", "model": "CAMRY", "year": 2021, "body_class": "sedan", "curb_weight_kg": 1495.0}
        return {"source": "fallback_offline_resolver", "vehicle": fallback_profile}

# ============================================================================
# INGESTION SYNC ENDPOINT WITH IDP LOCKS & DARCI IN-LINE PHYSICS
# ============================================================================

@router.post("/sync", status_code=status.HTTP_201_CREATED)
async def ingest_crash_bundle(
    payload: CrashBundlePayload,
    x_idempotency_key: str = Header(...),
    db: AsyncSession = Depends(get_pg_session)
):
    async with db.begin():
        lock_query = text(
            "SELECT status, response_payload FROM idempotency_locks "
            "WHERE idempotency_key = :key FOR UPDATE"
        )
        lock_res = await db.execute(lock_query, {"key": x_idempotency_key})
        lock = lock_res.fetchone()
        if lock:
            if lock.status == "processing":
                raise HTTPException(status_code=409, detail="Transaction currently locked. In-progress.")
            elif lock.status == "completed":
                return lock.response_payload
            await db.execute(text("DELETE FROM idempotency_locks WHERE idempotency_key = :key"), {"key": x_idempotency_key})
        mock_tenant_id = "00000000-0000-0000-0000-000000000000"
        await db.execute(
            text("INSERT INTO idempotency_locks (idempotency_key, tenant_id, status) VALUES (:key, :tenant, 'processing')"),
            {"key": x_idempotency_key, "tenant": mock_tenant_id}
        )
    try:
        merkle_intact = verify_merkle_root_invariance(payload.frames, payload.merkle_root_hash)
        consent_signed = bool(payload.consent and payload.consent.signature_storage_path)
        si_score = calculate_si_trust_score(gps_acc=payload.gps.accuracy_meters, frames_valid=merkle_intact, consent_present=consent_signed)
        if si_score <= 0.0:
            raise ValueError("All-or-Nothing Trap triggered: Forensic Integrity Score collapsed.")
        vpic_result = await decode_vin_vpic(payload.vin)
        vehicle = vpic_result["vehicle"]
        impact_velocity_mph = 35.0
        impact_velocity_mps = impact_velocity_mph * 0.44704
        mass_kg = vehicle["curb_weight_kg"]
        kinetic_energy_joules = 0.5 * mass_kg * (impact_velocity_mps ** 2)
        kinetic_energy_kj = round(kinetic_energy_joules / 1000.0, 2)
        deformation_entropy = calculate_deformation_entropy(30.0)
        metallurgy = calculate_metallurgical_stress(kinetic_energy_kj, vehicle["body_class"], 30.0)
        is_total_loss = (deformation_entropy >= 2.0) or metallurgy["failure_imminent"]
        final_verdict = "TOTAL_LOSS" if is_total_loss else "REPAIRABLE"
        response_payload = {
            "success": True,
            "lead_id": str(payload.lead_id),
            "forensic_integrity_score": si_score * 100,
            "verdict": final_verdict,
            "darci_physics": {
                "kinetic_energy_kj": kinetic_energy_kj,
                "deformation_entropy": deformation_entropy,
                "metallurgy": metallurgy
            }
        }
        async with db.begin():
            await db.execute(
                text("UPDATE idempotency_locks SET status = 'completed', response_payload = :payload, completed_at = :now WHERE idempotency_key = :key"),
                {"payload": json.dumps(response_payload), "now": datetime.now(timezone.utc), "key": x_idempotency_key}
            )
        return response_payload
    except Exception as e:
        async with db.begin():
            await db.execute(text("UPDATE idempotency_locks SET status = 'failed' WHERE idempotency_key = :key"), {"key": x_idempotency_key})
        raise HTTPException(status_code=400, detail=str(e))
