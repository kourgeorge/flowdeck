"""PayPal payment endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from services import paypal_service

router = APIRouter(prefix="/api/payments", tags=["payments"])


class CreatePaymentRequest(BaseModel):
    package_id: str


class CreatePaymentResponse(BaseModel):
    payment_id: str
    approval_url: str


@router.post("/create", response_model=CreatePaymentResponse)
async def create_payment(
    body: CreatePaymentRequest,
    current_user=Depends(get_current_user),
):
    """Create a PayPal payment."""
    try:
        result = paypal_service.create_payment(current_user.id, body.package_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create payment: {str(e)}")


@router.post("/execute")
async def execute_payment(
    payment_id: str = Query(...),
    payer_id: str = Query(..., alias="PayerID"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Execute PayPal payment and credit tokens."""
    try:
        result = paypal_service.execute_payment(payment_id, payer_id, current_user.id, db)
        return result
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to execute payment: {str(e)}")


@router.get("/packages")
async def get_packages():
    """Get available token packages."""
    return paypal_service.get_packages()


