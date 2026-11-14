import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sam.db import get_db
from sam.models.installed_software import InstalledSoftware
from sam.models.license import License
from sam.schemas.ai import (
    SmartMatchRequest,
    SmartMatchResponse,
    BatchNormalizeResponse,
    EulaAnalyzeRequest,
    EulaAnalysisResponse,
    AIChatRequest,
    AIChatResponse,
)
from sam.services.ai_matcher import match_raw_process_to_catalog
from sam.services.ai_eula import analyze_eula_text
from sam.services.ai_chat import process_ai_chat_query
from sam.services.compliance_engine import recalculate_compliance_alerts

router = APIRouter(prefix="/ai", tags=["AI Modules"])


@router.post("/match-software", response_model=SmartMatchResponse)
async def match_software(payload: SmartMatchRequest, db: AsyncSession = Depends(get_db)):
    result = await match_raw_process_to_catalog(db, payload.raw_process_name)
    return {
        "raw_process_name": result["raw_process_name"],
        "matched_catalog_software_id": result["matched_catalog_software_id"],
        "matched_name": result["matched_name"],
        "vendor": result["vendor"],
        "confidence": result["confidence"],
        "reasoning": result["reasoning"],
    }


@router.post("/batch-normalize", response_model=BatchNormalizeResponse)
async def batch_normalize(db: AsyncSession = Depends(get_db)):
    # Find installed software not yet verified or unmatched
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
            db, item.raw_display_name, item.raw_publisher
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

    await db.commit()
    await recalculate_compliance_alerts(db)

    return {
        "normalized_count": normalized_count,
        "matched_count": matched_count,
    }


@router.post("/analyze-eula", response_model=EulaAnalysisResponse)
async def analyze_eula(payload: EulaAnalyzeRequest, db: AsyncSession = Depends(get_db)):
    analysis = analyze_eula_text(payload.eula_text)

    if payload.license_id:
        try:
            lid = uuid.UUID(payload.license_id)
            lic_res = await db.execute(select(License).where(License.id == lid))
            lic = lic_res.scalar_one_or_none()
            if lic:
                # Store serialized analysis
                serializable = {
                    "commercial_use_allowed": analysis["commercial_use_allowed"],
                    "risk_level": analysis["risk_level"],
                    "has_auto_renewal": analysis["has_auto_renewal"],
                    "trial_period_days": analysis["trial_period_days"],
                    "key_restrictions": analysis["key_restrictions"],
                    "summary_ru": analysis["summary_ru"],
                    "analyzed_at": analysis["analyzed_at"].isoformat(),
                }
                lic.eula_analysis = serializable
                lic.eula_text = payload.eula_text
                await db.commit()
        except Exception as e:
            print(f"Notice: saving EULA to license failed: {e}")

    return analysis


@router.post("/chat", response_model=AIChatResponse)
async def chat_assistant(payload: AIChatRequest, db: AsyncSession = Depends(get_db)):
    res = await process_ai_chat_query(db, payload.query)
    return res
