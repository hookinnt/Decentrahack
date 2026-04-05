import os
import json
import warnings
warnings.filterwarnings('ignore')
import google.generativeai as genai
from dotenv import load_dotenv
from agent.models import NewsItem, RiskAssessment

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise ValueError("System Configuration Error: Missing Core API Key in .env")

genai.configure(api_key=API_KEY)

# ─── Risk Assessment Logic Engine Rules ──────────────────────────────────────

EVALUATION_RULES = """
Выполняй роль строгого финансового контролера (Risk Auditor) в сфере DeFi.
Контекст: управление автоматизированным защитным слоем сетевого протокола.
Твоя задача — формировать сухие экспертные заключения без лишних слов.

СТРОГИЕ ПРАВИЛА ВЫВОДА:
1. Максимальная краткость и техническая точность. 
2. Только прямой вердикт на русском языке.
3. Каждая оценка должна быть логически обоснована влиянием метрик (TVL, Volatility) на риск.

ШКАЛА ОЦЕНКИ РИСКОВ:
- 0-39: НОРМА. Операционных рисков нет.
- 40-79: ВНИМАНИЕ. Подозрительная активность или сетевая нестабильность.
- 80-100: КРИТИЧЕСКАЯ УГРОЗА. Немедленная блокировка (action_required: true).

АДАПТИВНОСТЬ ПОРОГА:
- Оценивай волатильность: High -> порог 65-70, Medium -> 80, Low -> 85-90.

ОЖИДАЕМЫЙ ФОРМАТ (СТРОГИЙ JSON):
{
  "risk_score": int,
  "reason": "Краткое техническое обоснование (до 180 символов)",
  "action_required": bool,
  "recommended_threshold": int,
  "confidence_score": int (0-100)
}
"""

class RiskAuditor:
    """
    Main Logic Engine for risk evaluation via off-chain compute.
    """
    def __init__(self):
        self.client = genai.GenerativeModel('gemini-flash-latest', system_instruction=EVALUATION_RULES)

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
            
            # ─── FALLBACK: Keyword-based deterministic assessment ───────────
            low_text = event.content.lower()
            score = 15
            reason = "Стабильный рыночный фон. Аномалий не обнаружено."
            
            if any(x in low_text for x in ["hack", "exploit", "взлом", "кража", "threat"]):
                score = 95
                reason = "Критический инцидент: обнаружены признаки угрозы."
            elif any(x in low_text for x in ["suspicious", "delay", "подозрительно", "scam"]):
                score = 55
                reason = "Подозрительная активность в сети. Повышенная бдительность."
            elif event.volatility == "High":
                score = 35
                reason = "Повышенная волатильность рынка. Прямых угроз нет."

            if "429" in str(e) or "quota" in str(e).lower():
                reason = f"Deterministic Mode: {reason}"

            return RiskAssessment(
                risk_score=score,
                reason=reason,
                action_required=(score >= 80),
                confidence_score=50
            )
