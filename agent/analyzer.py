import os
import json
import warnings
warnings.filterwarnings('ignore')
import google.generativeai as genai
from dotenv import load_dotenv
from agent.models import NewsItem, RiskAssessment

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
if API_KEY:
    genai.configure(api_key=API_KEY)

# ─── Risk Assessment Logic Engine Rules ──────────────────────────────────────

EVALUATION_RULES = """
Роль: Ведущий Risk Auditor в децентрализованной автономной организации (DAO).
Задача: Анализ входящих рыночных и новостных событий для предотвращения эксплойтов.

ТЕХНИЧЕСКИЕ ПРИНЦИПЫ:
1. Аналитический лаконизм. Минимум эмоций, максимум метрических связей.
2. Причинно-следственная связь: Как изменение TVL или волатильности влияет на вероятность атаки?
3. Векторы угроз: Учитывай флеш-лоаны, манипуляцию оракулами, проблемы мостов (Bridges), задержки в L1.

ШКАЛА ОЦЕНКИ (DARS COMPLIANT):
- 00-39: СТАБИЛЬНО (Operational). Фоновые события.
- 40-74: ПРЕДУПРЕЖДЕНИЕ (Elevated). Нестандартные паттерны.
- 75-100: КРИТИЧЕСКИЙ РИСК (Emergency). Автономная активация 'emergency_pause'.

АДАПТИВНОСТЬ (DARS):
- Рекомендуй новый порог (recommended_threshold) на основе текущей макро-волатильности.
- Высокая волатильность -> Понижай порог (например, до 70).
- Низкая волатильность -> Повышай порог (например, до 85-90).

ОТВЕТ В ФОРМАТЕ JSON:
{
  "risk_score": int,
  "reason": "Технический аудит события (до 180 симв.)",
  "action_required": bool,
  "recommended_threshold": int,
  "confidence_score": int
}
"""

class RiskAuditor:
    """
    Main Logic Engine for risk evaluation via off-chain compute.
    """
    def __init__(self):
        self.client = None
        if API_KEY:
            self.client = genai.GenerativeModel('gemini-flash-latest', system_instruction=EVALUATION_RULES)
        else:
            print("[ENGINE WARN] GEMINI_API_KEY missing. Running in deterministic fallback mode.")

    def process_event(self, event: NewsItem) -> RiskAssessment:
        """
        Processes market data and returns a structured risk assessment.
        """
        payload = (
            f"ВХОДНЫЕ ДАННЫЕ ДЛЯ АНАЛИЗА:\n"
            f"Событие: {event.content}\n"
            f"TVL Протокола: {event.tvl}\n"
            f"Рыночная волатильность: {event.volatility}"
        )
        
        try:
            if not self.client:
                raise RuntimeError("Gemini client is not configured")
            response = self.client.generate_content(
                payload,
                generation_config=genai.GenerationConfig(
                    response_mime_type="application/json",
                )
            )
            data = json.loads(response.text)
            
            # String length validation for on-chain compatibility
            if len(data.get('reason', '')) > 195:
                data['reason'] = data['reason'][:192] + "..."
                
            return RiskAssessment(**data)
            
        except Exception as e:
            print(f"[ENGINE_ERR] External processing failed: {e}")
            
            # ─── FALLBACK: Deterministic On-Chain Security ───────────────────
            low_text = event.content.lower()
            score = 20
            reason = "Standard operational baseline. No anomalies detected."
            
            # Critical Exploit Vectors
            critical_patterns = ["hack", "exploit", "взлом", "кража", "threat", "drain", "vulnerability"]
            # Elevated Risk Vectors
            warning_patterns = ["suspicious", "delay", "подозрительно", "scam", "halt", "maintenance"]
            
            if any(x in low_text for x in critical_patterns):
                score = 98
                reason = "CRITICAL: Exploit vector identified in telemetry stream."
            elif any(x in low_text for x in warning_patterns):
                score = 65
                reason = "WARNING: Suspicious network activity or operational delay."
            elif event.volatility == "High":
                score = 45
                reason = "Notice: Market volatility elevated. Protocol on high alert."

            return RiskAssessment(
                risk_score=score,
                reason=reason,
                action_required=(score >= 80),
                recommended_threshold=70 if event.volatility == "High" else 80,
                confidence_score=75
            )
