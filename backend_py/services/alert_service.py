"""Multilingual alert generation and provider-based dispatch.

The message layer is deterministic and works without any API key. When a Gemini
key is configured, it is only used to polish the wording in the selected
language, never to replace the fallback templates.
"""

import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests

try:
    from services.ai_ground_report import get_gemini_api_key
except Exception:  # pragma: no cover - fallback for direct import
    def get_gemini_api_key() -> str:
        return os.getenv("GEMINI_API_KEY", "")

RISK_ORDER = {"LOW": 0, "MODERATE": 1, "HIGH": 2, "CRITICAL": 3}

TEMPLATE_TEXT = {
    "en": {
        "title": "Flood alert for {settlement}",
        "body": "Flood risk is now {risk_level} for {settlement} ({settlement_id}). Safe route: {safe_route}. Nearest shelter: {nearest_shelter}. What to do: {action}.",
    },
    "hi": {
        "title": "{settlement} के लिए बाढ़ अलर्ट",
        "body": "{settlement} ({settlement_id}) में अब बाढ़ का जोखिम {risk_level} है। सुरक्षित मार्ग: {safe_route}। निकटतम आश्रय: {nearest_shelter}। करने योग्य कदम: {action}।",
    },
    "mr": {
        "title": "{settlement} साठी पूर अलर्ट",
        "body": "{settlement} ({settlement_id}) येथे आता पुराचा धोका {risk_level} आहे. सुरक्षित मार्ग: {safe_route}. जवळचा आश्रय: {nearest_shelter}. काय करावे: {action}.",
    },
}


def _as_title_safe(value: Optional[str]) -> str:
    return (value or "this settlement").strip()


def _polish_with_gemini(message: str, language: str) -> Optional[str]:
    key = get_gemini_api_key()
    if not key:
        return None
    try:
        prompt = (
            "Rewrite the following flood alert in a clear, practical and human-safe tone in "
            f"{language}. Keep the exact facts and do not invent new actions, names, or numbers. "
            f"Reply with only the rewritten message:\n\n{message}"
        )
        res = requests.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
            headers={"x-goog-api-key": key},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.2, "maxOutputTokens": 220, "thinkingConfig": {"thinkingBudget": 0}},
            },
            timeout=8,
        )
        if res.status_code != 200:
            return None
        text = res.json().get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
        return text or None
    except Exception:
        return None


def build_alert_message(
    settlement: Dict[str, Any],
    risk_level: str,
    language: str = "en",
    safe_route: Optional[str] = None,
    nearest_shelter: Optional[str] = None,
    action: Optional[str] = None,
) -> Dict[str, Any]:
    settlement_name = settlement.get("name") or settlement.get("settlementName") or "this settlement"
    settlement_id = settlement.get("id") or settlement.get("settlementId") or "UNKNOWN"
    language = (language or "en").lower()
    language = language if language in TEMPLATE_TEXT else "en"

    if not safe_route:
        safe_route = "Use the safest currently marked emergency route"
    if not nearest_shelter:
        nearest_shelter = "the nearest listed shelter or community centre"
    if not action:
        action = {
            "LOW": "continue monitoring and prepare backup shelter arrangements",
            "MODERATE": "move vulnerable residents to higher ground and prepare evacuation kits",
            "HIGH": "move residents to the nearest shelter and keep the route clear for emergency teams",
            "CRITICAL": "evacuate immediately to the nearest shelter and contact emergency responders",
        }.get(str(risk_level).upper(), "follow local emergency instructions")

    template = TEMPLATE_TEXT[language]
    msg = template["body"].format(
        settlement=settlement_name,
        settlement_id=settlement_id,
        risk_level=risk_level,
        safe_route=safe_route,
        nearest_shelter=nearest_shelter,
        action=action,
    )
    title = template["title"].format(
        settlement=settlement_name,
        risk_level=risk_level,
    )

    polished = _polish_with_gemini(msg, language)
    if polished:
        msg = polished
    return {
        "language": language,
        "title": title,
        "message": msg,
        "riskLevel": str(risk_level).upper(),
        "settlementName": settlement_name,
        "safeRoute": safe_route,
        "nearestShelter": nearest_shelter,
        "whatToDo": action,
        "source": "GEMINI" if polished else "TEMPLATE",
    }


class BaseProvider:
    def __init__(self, name: str):
        self.name = name
        self.history: List[Dict[str, Any]] = []

    def send(self, alert: Dict[str, Any], to: Optional[str] = None, channel: str = "sms") -> Dict[str, Any]:
        raise NotImplementedError


class ConsoleProvider(BaseProvider):
    def __init__(self):
        super().__init__("console")

    def send(self, alert: Dict[str, Any], to: Optional[str] = None, channel: str = "sms") -> Dict[str, Any]:
        record = {
            "provider": self.name,
            "channel": channel,
            "recipient": to,
            "status": "logged",
            "success": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "messageId": f"{self.name}-{uuid.uuid4().hex[:8]}",
            "settlementId": alert.get("settlementId"),
            "language": alert.get("language"),
            "title": alert.get("title"),
            "message": alert.get("message"),
        }
        self.history.append(record)
        print(f"[ALERT:{self.name}] {alert.get('settlementName')} -> {alert.get('message')}")
        return record


class TwilioProvider(BaseProvider):
    def __init__(self):
        super().__init__("twilio")
        self.account_sid = os.getenv("TWILIO_ACCOUNT_SID", "")
        self.auth_token = os.getenv("TWILIO_AUTH_TOKEN", "")
        self.from_number = os.getenv("TWILIO_FROM_NUMBER", "")

    @classmethod
    def is_configured(cls) -> bool:
        return bool(os.getenv("TWILIO_ACCOUNT_SID") and os.getenv("TWILIO_AUTH_TOKEN") and os.getenv("TWILIO_FROM_NUMBER"))

    def send(self, alert: Dict[str, Any], to: Optional[str] = None, channel: str = "sms") -> Dict[str, Any]:
        if not self.is_configured():
            return {"provider": self.name, "status": "disabled", "success": False, "reason": "TWILIO env vars missing"}
        try:
            from twilio.rest import Client
        except Exception:
            return {"provider": self.name, "status": "disabled", "success": False, "reason": "twilio package not installed"}

        destination = to or os.getenv("TWILIO_ALERT_RECIPIENT") or os.getenv("TWILIO_TO_NUMBER")
        if not destination:
            return {"provider": self.name, "status": "skipped", "success": False, "reason": "no Twilio recipient configured"}

        client = Client(self.account_sid, self.auth_token)
        target = destination if destination.startswith("whatsapp:") or destination.startswith("+") else f"{destination}"
        if channel == "whatsapp" and not destination.startswith("whatsapp:"):
            target = f"whatsapp:{destination}"
        elif channel == "sms" and destination.startswith("whatsapp:"):
            target = destination.replace("whatsapp:", "")

        try:
            if channel == "whatsapp":
                msg = client.messages.create(body=alert.get("message"), from_=f"whatsapp:{self.from_number}", to=target)
            else:
                msg = client.messages.create(body=alert.get("message"), from_=self.from_number, to=target)
            record = {
                "provider": self.name,
                "channel": channel,
                "recipient": destination,
                "status": "sent",
                "success": True,
                "messageId": getattr(msg, "sid", None),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            self.history.append(record)
            return record
        except Exception as exc:  # pragma: no cover - depends on external API
            return {"provider": self.name, "channel": channel, "recipient": destination, "status": "error", "success": False, "error": str(exc)}


class AlertDispatcher:
    def __init__(self, providers: Optional[List[BaseProvider]] = None):
        self.providers = providers or [ConsoleProvider()]
        if TwilioProvider.is_configured() and not any(isinstance(p, TwilioProvider) for p in self.providers):
            self.providers.append(TwilioProvider())
        self.history: List[Dict[str, Any]] = []

    def build_alert(self, settlement: Dict[str, Any], risk_level: str, language: str = "en", safe_route: Optional[str] = None, nearest_shelter: Optional[str] = None, action: Optional[str] = None) -> Dict[str, Any]:
        return build_alert_message(settlement, risk_level, language, safe_route, nearest_shelter, action)

    def send_alert(
        self,
        settlement: Dict[str, Any],
        risk_level: str,
        language: str = "en",
        safe_route: Optional[str] = None,
        nearest_shelter: Optional[str] = None,
        action: Optional[str] = None,
        recipient: Optional[str] = None,
        channel: str = "sms",
    ) -> Dict[str, Any]:
        alert = self.build_alert(settlement, risk_level, language, safe_route, nearest_shelter, action)
        alert["settlementId"] = settlement.get("id") or settlement.get("settlementId")
        alert["sentAt"] = datetime.now(timezone.utc).isoformat()
        provider_results = []
        for provider in self.providers:
            provider_results.append(provider.send(alert, to=recipient, channel=channel))
        alert["providerResults"] = provider_results
        alert["successfulDeliveries"] = sum(1 for r in provider_results if r.get("success"))
        self.history.insert(0, alert)
        return alert


def get_default_dispatcher() -> AlertDispatcher:
    return AlertDispatcher()
