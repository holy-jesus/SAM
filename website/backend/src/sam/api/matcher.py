import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sam.db import get_db
from sam.models.installed_software import InstalledSoftware
from sam.schemas.ai import (
    SmartMatchRequest,
    SmartMatchResponse,
    BatchNormalizeResponse,
)
from sam.services.matcher import match_raw_process_to_catalog, save_learned_signature
from sam.services.compliance_engine import recalculate_compliance_alerts
from sam.services.substitution_service import (
    enqueue_software_substitution_check,
    is_official_software_name,
)

router = APIRouter(prefix="/matcher", tags=["Software Matcher"])


class ConfirmMatchRequest(BaseModel):
    raw_process_name: str
    matched_name: str
    catalog_software_id: Optional[str] = None
    match_source: Optional[str] = "admin"
    category_id: Optional[int] = None


@router.post("/match-software", response_model=SmartMatchResponse)
async def match_software(payload: SmartMatchRequest, db: AsyncSession = Depends(get_db)):
    result = await match_raw_process_to_catalog(
        db=db,
        raw_process_name=payload.raw_process_name,
        binary_hash=payload.binary_hash,
        publisher=payload.publisher,
        install_path=payload.install_path,
        reported_version=payload.version,
    )
    return {
        "raw_process_name": result["raw_process_name"],
        "matched_catalog_software_id": result.get("matched_catalog_software_id"),
        "matched_name": result.get("matched_name"),
        "vendor": result.get("vendor"),
        "matched_version": result.get("matched_version"),
        "confidence": result.get("confidence", 0.0),
        "reasoning": result.get("reasoning", ""),
        "match_source": result.get("match_source"),
    }


@router.post("/batch-normalize", response_model=BatchNormalizeResponse)
async def batch_normalize(db: AsyncSession = Depends(get_db)):
    # Find installed software not yet verified
    result = await db.execute(
        select(InstalledSoftware).where(
            InstalledSoftware.is_verified_by_admin == False
        )
    )
    items = result.scalars().all()

    normalized_count = len(items)
    matched_count = 0

    for item in items:
        match_res = await match_raw_process_to_catalog(
            db=db,
            raw_process_name=item.raw_display_name,
            binary_hash=item.binary_hash,
            publisher=item.raw_publisher,
            install_path=item.install_path,
            reported_version=item.raw_version,
        )
        cat_id = match_res.get("matched_catalog_software_id")
        conf = match_res.get("confidence", 0.0)
        matched_name = match_res.get("matched_name")
        match_source = match_res.get("match_source")

        if matched_name:
            item.normalized_name = matched_name
        if match_source:
            item.match_source = match_source

        if cat_id and conf >= 0.60:
            item.catalog_software_id = uuid.UUID(cat_id)
            if match_res.get("category_id"):
                item.category_id = match_res["category_id"]
            item.match_confidence = conf
            item.is_verified_by_admin = conf >= 0.90
            matched_count += 1

            official_name = matched_name or item.raw_display_name
            if match_source != "ru_registry" and is_official_software_name(official_name):
                enqueue_software_substitution_check(
                    official_name,
                    catalog_software_id=uuid.UUID(cat_id),
                )
        elif conf >= 0.70 and matched_name:
            item.match_confidence = conf
            matched_count += 1

    await db.commit()
    await recalculate_compliance_alerts(db)

    return {
        "normalized_count": normalized_count,
        "matched_count": matched_count,
    }


@router.post("/confirm-match")
async def confirm_match(payload: ConfirmMatchRequest, db: AsyncSession = Depends(get_db)):
    # 1. Update all matching installed_software
    stmt = select(InstalledSoftware).where(
        InstalledSoftware.raw_display_name == payload.raw_process_name
    )
    res = await db.execute(stmt)
    installations = res.scalars().all()

    cat_id = None
    if payload.catalog_software_id:
        try:
            cat_id = uuid.UUID(payload.catalog_software_id)
        except ValueError:
            pass

    for inst in installations:
        inst.normalized_name = payload.matched_name
        inst.match_source = payload.match_source or "admin"
        inst.match_confidence = 1.0
        inst.is_verified_by_admin = True
        if cat_id:
            inst.catalog_software_id = cat_id
        if payload.category_id:
            inst.category_id = payload.category_id

    # 2. Save / update signature in knowledge base
    await save_learned_signature(
        db=db,
        process_name=payload.raw_process_name,
        normalized_name=payload.matched_name,
        binary_hash=None,
        catalog_software_id=cat_id,
        ru_registry_id=None,
        vendor=None,
        confidence=1.0,
        match_source=payload.match_source or "admin",
    )

    await db.commit()
    await recalculate_compliance_alerts(db)

    return {
        "success": True,
        "updated_installations": len(installations),
        "raw_process_name": payload.raw_process_name,
        "matched_name": payload.matched_name,
    }
