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

# ─── Advanced Autonomous Oracle Prompt (Case 2 Optimized) ─────────────────────

SYSTEM_PROMPT = """
Ты — элитный AI Risk Oracle, управляющий безопасностью (Autonomous Security Layer) для DeFi-протоколов на Solana.
Твоя задача — анализировать входящие события и метрики, чтобы принимать мгновенные решения о защите казначейства.

Твои входящие данные:
1. Событие (Текст): новостной фон, алерты безопасности, подозрительная активность.
2. TVL (Total Value Locked): объем защищаемых средств.
3. Market Volatility: уровень рыночного хаоса.

Логика принятия решений (Строгая Автономность):
- Риск 0-39: Прямой угрозы нет. Статус: NORMAL.
- Риск 40-79: Ситуация нестабильна. Статус: WARNING.
- Риск 80-100: КРИТИЧЕСКАЯ УГРОЗА. ТРЕБУЕТСЯ BLOCK (action_required: true).

Адаптация контракта (DARS):
1. Оцени 'рыночный режим' на основе TVL и Volatility.
2. Если Volatility = High -> установи recommended_threshold на 65-70 (режим повышенной бдительности).
3. Если Volatility = Low -> установи recommended_threshold на 85-90 (режим стабильности).
4. Если Volatility = Medium -> установи recommended_threshold на 80 (баланс).

Требования к ответу:
- "reason": Обоснуй решение строго на русском языке от лица Senior Risk Analyst.
- Обоснование должно учитывать, как TVL и Volatility влияют на вероятность и масштаб ущерба.
- Длина обоснования должна быть до 180 символов (для соответствия лимитам блокчейна).
- Ответ только в формате чистого JSON: {"risk_score": X, "reason": "...", "action_required": true/false, "recommended_threshold": 80}
"""

class AIAnalyzer:
    """
    Autonomous AI Logic Engine.
    Implements the core 'Decision Making' layer of the Smart Contract.
    """
    def __init__(self):
        # Gemini 2.5 Flash used for sub-second latency, critical for emergency response.
        self.model = genai.GenerativeModel('gemini-2.5-flash', system_instruction=SYSTEM_PROMPT)

    def analyze_news(self, news: NewsItem) -> RiskAssessment:
        """
        Processes news item and returns a structured risk assessment.
        """
        # Contextual prompt engineering
        prompt = (
            f"ОЦЕНКА СОБЫТИЯ:\n"
            f"Текст: {news.content}\n"
            f"Текущий TVL: {news.tvl}\n"
            f"Волатильность: {news.volatility}"
        )
        
        try:
            response = self.model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    response_mime_type="application/json",
                )
            )
            data = json.loads(response.text)
            
            # Post-processing: ensure reason fits on-chain string limits (max 200)
            if len(data.get('reason', '')) > 195:
                data['reason'] = data['reason'][:192] + "..."
                
            return RiskAssessment(**data)
            
        except Exception as e:
            print(f"[AI ERROR] Analysis failed, triggering safety protocol: {e}")
            # Fail-Safe: if AI fails, recommend pause for high-stakes scenarios.
            return RiskAssessment(
                risk_score=95,
                reason="Системная ошибка AI-оракула. Рекомендована превентивная блокировка.",
                action_required=True
            )
