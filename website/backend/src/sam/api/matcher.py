import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sam.db import get_db
from sam.models.installed_software import InstalledSoftware
from sam.schemas.ai import (
    SmartMatchRequest,
    SmartMatchResponse,
    BatchNormalizeResponse,
)
from sam.services.matcher import match_raw_process_to_catalog
from sam.services.compliance_engine import recalculate_compliance_alerts
from sam.services.substitution_service import (
    enqueue_software_substitution_check,
    is_official_software_name,
)

router = APIRouter(prefix="/matcher", tags=["Software Matcher"])


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

        if cat_id and conf >= 0.60:
            item.catalog_software_id = uuid.UUID(cat_id)
            if match_res.get("category_id"):
                item.category_id = match_res["category_id"]
            item.match_confidence = conf
            item.is_verified_by_admin = conf >= 0.90
            matched_count += 1

            matched_name = match_res.get("matched_name") or item.raw_display_name
            if match_res.get("match_source") != "ru_registry" and is_official_software_name(matched_name):
                enqueue_software_substitution_check(
                    matched_name,
                    catalog_software_id=uuid.UUID(cat_id),
                )

    await db.commit()
    await recalculate_compliance_alerts(db)

    return {
        "normalized_count": normalized_count,
        "matched_count": matched_count,
    }
