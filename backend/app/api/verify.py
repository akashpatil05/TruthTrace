"""
Verification API Route Handlers.
"""

from fastapi import APIRouter, HTTPException, status
from app.models.schemas import VerificationRequest, VerificationResponse
from app.services.verification import verification_service

router = APIRouter(prefix="/verify", tags=["Verification"])


@router.post("", response_model=VerificationResponse)
async def verify_claim(payload: VerificationRequest) -> VerificationResponse:
    """
    Verify a claim, headline, or article text:
    1. Multi-query semantic search across FAISS vector store
    2. Stance analysis and contradiction discovery
    3. Grounded evidence attribution
    4. Structured verdict: TRUE, FALSE, MISLEADING, or INSUFFICIENT_EVIDENCE
    """
    try:
        return verification_service.verify(payload)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Verification failed: {str(e)}"
        )
