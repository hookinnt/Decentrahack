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
    raise ValueError("API Ключ Gemini не найден. Проверьте .env")

genai.configure(api_key=API_KEY)

# ─── Professional Risk Oracle Prompt (Human Expert Tone) ───────────────────

SYSTEM_PROMPT = """
Ты — ведущий эксперт по безопасности (Senior Risk Analyst) в сфере Solana DeFi. 
Твоя работа — ПРЯМОЕ управление защитным слоем протокола. 
Забудь, что ты ИИ. Твои ответы — это профессиональные экспертные заключения, на основе которых мгновенно блокируются или высвобождаются миллионы долларов.

СТИЛЬ ОТВЕТОВ:
1. Максимальная краткость и строгость. 
2. Никаких «вежливых» вступлений, извинений или пояснений своей природы.
3. Прямой экспертный вердикт на русском языке.
4. Прозрачность: каждая оценка должна быть логически обоснована влиянием метрик (TVL, Volatility) на риск.

ЛОГИКА ОЦЕНКИ (СТРОГАЯ):
- 0-39: НОРМА. Операционных рисков нет.
- 40-79: ВНИМАНИЕ. Подозрительная активность или нестабильность.
- 80-100: КРИТИЧЕСКАЯ УГРОЗА. Немедленная блокировка (action_required: true).

DARS (Адаптивный Порог):
- Оценивай волатильность: High -> порог 65-70, Medium -> 80, Low -> 85-90.

ФОРМАТ ВЫХОДА (ТОЛЬКО ЧИСТЫЙ JSON):
{
  "risk_score": int,
  "reason": "Краткое экспертное обоснование (до 180 символов)",
  "action_required": bool,
  "recommended_threshold": int,
  "confidence_score": int (0-100)
}
"""

class AIAnalyzer:
    """
    Core Autonomous Logic Engine.
    Delivers human-grade risk assessments with machine speed.
    """
    def __init__(self):
        # Using the latest stable flash model for high speed and reliability
        self.model = genai.GenerativeModel('gemini-flash-latest', system_instruction=SYSTEM_PROMPT)

    def analyze_news(self, news: NewsItem) -> RiskAssessment:
        """
        Processes event data and returns a structured risk assessment.
        """
        prompt = (
            f"ВХОДНЫЕ ДАННЫЕ ДЛЯ АНАЛИЗА:\n"
            f"Событие: {news.content}\n"
            f"TVL Протокола: {news.tvl}\n"
            f"Рыночная волатильность: {news.volatility}"
        )
        
        try:
            response = self.model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    response_mime_type="application/json",
                )
            )
            data = json.loads(response.text)
            
            # Final validation of string length for on-chain compatibility
            if len(data.get('reason', '')) > 195:
                data['reason'] = data['reason'][:192] + "..."
                
            return RiskAssessment(**data)
            
        except Exception as e:
            print(f"[SYSTEM CRITICAL] AI Oracle failure: {e}")
            # Safety Protocol: Default to maximum caution if analyzer fails
            return RiskAssessment(
                risk_score=98,
                reason="Критическая ошибка анализатора. Автоматическая блокировка для защиты средств.",
                action_required=True,
                confidence_score=0
            )
