"""Structured investor profile + editable AI memory."""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from models.db_models import User, UserProfile
from services import token_service


PERSONA_TYPES = {"investor", "trader", "both"}
EXPERIENCE_LEVELS = {"beginner", "intermediate", "advanced", "professional"}
RISK_TOLERANCES = {"conservative", "moderate", "aggressive"}
TIME_HORIZONS = {"intraday", "swing", "medium_term", "long_term"}
PRIMARY_GOALS = {
    "wealth_building",
    "active_trading",
    "retirement",
    "income",
    "capital_preservation",
    "learning",
}
PREFERRED_STYLES = {"balanced", "concise", "professional", "technical"}

CHAT_STYLE_GUIDANCE = {
    "balanced": (
        "Use a balanced tone: clear plain-English explanations, moderate detail, "
        "and a mix of summary plus supporting evidence."
    ),
    "concise": (
        "Keep replies compact and high-signal. Lead with the bottom line, avoid "
        "unnecessary background, and prefer short bullets or tight structure."
    ),
    "professional": (
        "Use a professional, polished tone. Organize the answer clearly and focus "
        "on decision-useful takeaways and tradeoffs."
    ),
    "technical": (
        "Use a more technical analytical style. Assume the user is comfortable with "
        "financial terminology, denser reasoning, and quantified detail when tools support it."
    ),
}

EXPERIENCE_LEVEL_GUIDANCE = {
    "beginner": {
        "terminology": "Use simple, everyday language. Avoid jargon or explain it immediately when necessary.",
        "structure": "Use direct statements with clear reasoning. Break down complex concepts into simple steps.",
        "depth": "Focus on the 'what' and 'why' before the 'how'. Provide context and educational explanations.",
        "examples": "Use concrete examples and analogies to illustrate concepts.",
        "tone": "Be encouraging and educational. Assume no prior knowledge of financial markets.",
        "recommendations": "Give clear, actionable guidance with explicit reasoning. Explain the rationale behind each suggestion.",
    },
    "intermediate": {
        "terminology": "Use standard financial terms but explain less common concepts. Balance accessibility with precision.",
        "structure": "Lead with key insights, then provide supporting details. Use moderate technical depth.",
        "depth": "Explain the reasoning and key assumptions. Cover both opportunities and risks.",
        "examples": "Reference real market scenarios and common investment situations.",
        "tone": "Be informative and practical. Assume basic market knowledge but explain nuances.",
        "recommendations": "Provide clear guidance with trade-offs. Explain why certain approaches work better in different scenarios.",
    },
    "advanced": {
        "terminology": "Use financial terminology freely. Assume familiarity with market concepts, metrics, and analysis frameworks.",
        "structure": "Lead with analysis and implications. Use dense, information-rich explanations.",
        "depth": "Focus on nuanced analysis, edge cases, and second-order effects. Discuss multiple scenarios.",
        "examples": "Reference sophisticated strategies and market dynamics.",
        "tone": "Be analytical and precise. Assume strong market knowledge and analytical skills.",
        "recommendations": "Present options with detailed trade-offs. Discuss risk-reward profiles and positioning strategies.",
    },
    "professional": {
        "terminology": "Use professional-grade financial language. Assume institutional-level knowledge.",
        "structure": "Deliver concise, high-density analysis. Skip basic explanations entirely.",
        "depth": "Focus on actionable insights, market microstructure, and portfolio implications. Discuss positioning, timing, and risk management.",
        "examples": "Reference institutional strategies, market regimes, and professional frameworks.",
        "tone": "Be direct and efficient. Assume expert-level understanding of markets, instruments, and strategies.",
        "recommendations": "Present sophisticated analysis with minimal hand-holding. Focus on execution considerations and portfolio construction.",
    },
}


def _clean_optional_str(value: Any, *, max_len: int) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text[:max_len]


def _clean_choice(value: Any, allowed: set[str], field_name: str) -> Optional[str]:
    cleaned = _clean_optional_str(value, max_len=64)
    if cleaned is None:
        return None
    if cleaned not in allowed:
        raise ValueError(f"Invalid {field_name}")
    return cleaned


def _clean_string_list(value: Any, field_name: str, *, max_items: int = 12, max_len: int = 80) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list")
    out: list[str] = []
    seen: set[str] = set()
    for raw in value:
        cleaned = _clean_optional_str(raw, max_len=max_len)
        if cleaned is None:
            continue
        lowered = cleaned.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        out.append(cleaned)
        if len(out) >= max_items:
            break
    return out


def _loads_list(raw: Optional[str]) -> list[str]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [str(item) for item in parsed if item]
    except Exception:
        return []
    return []


def is_profile_complete(profile: Optional[UserProfile]) -> bool:
    if profile is None:
        return False
    return bool(
        profile.persona_type
        and profile.risk_tolerance
        and profile.time_horizon
        and profile.primary_goal
    )


def get_or_create_profile(db: Session, user_id: int) -> UserProfile:
    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    if profile is not None:
        return profile
    profile = UserProfile(user_id=user_id)
    db.add(profile)
    db.flush()
    return profile


def serialize_profile(profile: UserProfile) -> dict[str, Any]:
    return {
        "user_id": profile.user_id,
        "date_of_birth": profile.date_of_birth,
        "persona_type": profile.persona_type,
        "experience_level": profile.experience_level,
        "risk_tolerance": profile.risk_tolerance,
        "time_horizon": profile.time_horizon,
        "primary_goal": profile.primary_goal,
        "goals": _loads_list(profile.goals_json),
        "constraints": _loads_list(profile.constraints_json),
        "preferred_style": profile.preferred_style,
        "ai_memory_text": profile.ai_memory_text,
        "has_completed_investor_profile": is_profile_complete(profile),
        "onboarding_completed_at": profile.onboarding_completed_at,
        "updated_at": profile.updated_at,
    }


def get_profile(db: Session, user_id: int) -> UserProfile:
    return get_or_create_profile(db, user_id)


def update_profile(db: Session, user_id: int, **fields: Any) -> UserProfile:
    profile = get_or_create_profile(db, user_id)

    if "date_of_birth" in fields:
        dob = fields["date_of_birth"]
        if dob is not None and not isinstance(dob, date):
            raise ValueError("Invalid date_of_birth")
        profile.date_of_birth = dob
    if "persona_type" in fields:
        profile.persona_type = _clean_choice(fields["persona_type"], PERSONA_TYPES, "persona_type")
    if "experience_level" in fields:
        profile.experience_level = _clean_choice(fields["experience_level"], EXPERIENCE_LEVELS, "experience_level")
    if "risk_tolerance" in fields:
        profile.risk_tolerance = _clean_choice(fields["risk_tolerance"], RISK_TOLERANCES, "risk_tolerance")
    if "time_horizon" in fields:
        profile.time_horizon = _clean_choice(fields["time_horizon"], TIME_HORIZONS, "time_horizon")
    if "primary_goal" in fields:
        profile.primary_goal = _clean_choice(fields["primary_goal"], PRIMARY_GOALS, "primary_goal")
    if "goals" in fields:
        profile.goals_json = json.dumps(_clean_string_list(fields["goals"], "goals"))
    if "constraints" in fields:
        profile.constraints_json = json.dumps(_clean_string_list(fields["constraints"], "constraints"))
    if "preferred_style" in fields:
        profile.preferred_style = _clean_choice(fields["preferred_style"], PREFERRED_STYLES, "preferred_style")
    if "ai_memory_text" in fields:
        profile.ai_memory_text = _clean_optional_str(fields["ai_memory_text"], max_len=4000)

    profile.onboarding_completed_at = datetime.utcnow() if is_profile_complete(profile) else None
    db.commit()
    db.refresh(profile)
    return profile


def ensure_profile_exists(db: Session, user_id: int) -> UserProfile:
    profile = get_or_create_profile(db, user_id)
    db.flush()
    return profile


def build_user_context_snapshot(user_id: int, db: Session) -> str:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return "User not found."

    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    balance = token_service.get_balance(user_id, db)
    member_since = user.created_at.strftime("%B %d, %Y") if user.created_at else "Unknown"
    goals = _loads_list(profile.goals_json if profile else None)
    constraints = _loads_list(profile.constraints_json if profile else None)

    def _fmt(value: Optional[str], fallback: str = "Not set") -> str:
        return value if value else fallback

    lines = [
        "# Your FlowDeck Profile",
        f"Email: {user.email}",
        f"Name: {_fmt(user.name)}",
        f"Token Balance: {balance:,} tokens",
        f"Member Since: {member_since}",
        f"Account Type: {'Admin' if user.is_admin else 'Standard'}",
        "",
        "# Investor Preferences",
        f"Persona Type: {_fmt(profile.persona_type if profile else None)}",
        f"Experience Level: {_fmt(profile.experience_level if profile else None)}",
        f"Risk Tolerance: {_fmt(profile.risk_tolerance if profile else None)}",
        f"Time Horizon: {_fmt(profile.time_horizon if profile else None)}",
        f"Primary Goal: {_fmt(profile.primary_goal if profile else None)}",
        f"Preferred AI Style: {_fmt(profile.preferred_style if profile else None)}",
        f"Date of Birth: {profile.date_of_birth.isoformat() if profile and profile.date_of_birth else 'Not set'}",
        f"Goals: {', '.join(goals) if goals else 'None saved'}",
        f"Constraints: {', '.join(constraints) if constraints else 'None saved'}",
        "",
        "# Saved AI Memory",
        profile.ai_memory_text if profile and profile.ai_memory_text else "No saved memory.",
    ]
    return "\n".join(lines)


def build_chat_personalization_context(user_id: int, db: Session) -> str:
    """Build explicit prompt instructions so chat responses follow saved profile style and memory."""
    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    if profile is None:
        return ""

    goals = _loads_list(profile.goals_json)
    constraints = _loads_list(profile.constraints_json)
    snapshot = build_user_context_snapshot(user_id, db)

    instructions = [
        "## Personalization Instructions",
        "Use the saved profile below to tailor the response unless the user overrides it in this conversation.",
        "- Follow the saved preferred style when writing the answer.",
        "- Use saved AI memory as durable context for how to frame explanations, risk tradeoffs, examples, and follow-through.",
        "- Treat investor preferences as default decision criteria when the user asks for guidance, comparisons, or recommendations.",
        "- If the live request conflicts with saved preferences or memory, follow the live request and treat it as an override.",
        "- Do not mention the saved profile or memory unless it materially helps the answer.",
    ]

    if profile.preferred_style:
        style_guidance = CHAT_STYLE_GUIDANCE.get(profile.preferred_style)
        instructions.append(f"- Preferred AI Style: {profile.preferred_style}")
        if style_guidance:
            instructions.append(f"- Style behavior: {style_guidance}")

    if profile.ai_memory_text:
        instructions.append(f"- Saved AI Memory: {profile.ai_memory_text[:600]}")
        instructions.append(
            "- Memory behavior: incorporate these notes when prioritizing risks, "
            "positioning ideas, and the level of explanation."
        )

    if profile.persona_type:
        if profile.persona_type == "investor":
            instructions.append(
                "- Persona behavior: default toward investment thesis, fundamentals, "
                "valuation, and longer-term compounding implications."
            )
        elif profile.persona_type == "trader":
            instructions.append(
                "- Persona behavior: default toward setups, catalysts, timing, "
                "risk management, and shorter-term decision framing."
            )
        else:
            instructions.append(
                "- Persona behavior: balance investor-style thesis work with "
                "trader-style timing and risk management."
            )

    if profile.experience_level:
        exp_level = profile.experience_level
        guidance = EXPERIENCE_LEVEL_GUIDANCE.get(exp_level)
        if guidance:
            instructions.append(f"- Experience Level: {exp_level}")
            instructions.append(f"- Terminology: {guidance['terminology']}")
            instructions.append(f"- Structure: {guidance['structure']}")
            instructions.append(f"- Depth: {guidance['depth']}")
            instructions.append(f"- Examples: {guidance['examples']}")
            instructions.append(f"- Tone: {guidance['tone']}")
            instructions.append(f"- Recommendations: {guidance['recommendations']}")

    if profile.risk_tolerance:
        instructions.append(f"- Default risk tolerance: {profile.risk_tolerance}")
    if profile.time_horizon:
        instructions.append(f"- Default time horizon: {profile.time_horizon}")
    if profile.primary_goal:
        instructions.append(f"- Primary goal: {profile.primary_goal}")
    if goals:
        instructions.append(f"- Additional goals: {', '.join(goals)}")
    if constraints:
        instructions.append(f"- Constraints: {', '.join(constraints)}")

    instructions.extend(
        [
            "",
            "## Saved User Profile",
            snapshot[:2500],
        ]
    )
    return "\n".join(instructions)
