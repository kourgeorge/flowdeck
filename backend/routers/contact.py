"""Contact form submission – sends email to admin."""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr

from services.email_service import send_contact_form_email

router = APIRouter(prefix="/api", tags=["contact"])


class ContactRequest(BaseModel):
    name: str = ""
    email: EmailStr
    message: str = ""


@router.post("/contact")
def submit_contact(req: ContactRequest):
    """
    Submit the contact form. Sends an email to kourgeorge@gmail.com with name, email, and message.
    No authentication required.
    """
    try:
        sent = send_contact_form_email(
            name=(req.name or "").strip(),
            email=req.email.strip(),
            message=(req.message or "").strip(),
        )
        if not sent:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Email service is not configured. Please try again later or email us directly.",
            )
        return {"ok": True, "message": "Message sent successfully."}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send message. Please try again or email us directly.",
        ) from e
