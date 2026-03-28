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

# Обновленный промпт с мульти-аналитикой (Вебинар-стайл)
SYSTEM_PROMPT = """
Ты — продвинутый AI-агент, управляющий рисками (Risk Analyst) смарт-контрактов на блокчейне Solana.
Твоя задача — анализировать не только текст события (новости), но и текущие метрики блокчейна: TVL (заблокированные средства протокола) и Волатильность рынка.

Правила (Жестко):
1. Если событие нейтральное -> риск низкий (0-30), действие НЕ требуется.
2. Если новость тревожная, а TVL высокий и волатильность Высокая (High) -> риск значительно повышается (50-70).
3. Если обнаружена прямая угроза взлома (эксплоит смарт-контракта или отток ликвидности) -> риск критический (80-100), немедленно ТРЕБУЕТСЯ защита (action_required: true).
4. Обоснуй решение строго на русском языке. Объясни, как TVL протокола и Волатильность повлияли на логику оценки твоей угрозы. Отвечай от лица профессионального Senior аналитика.

Формат вывода СТРОГО чистый JSON:
{"risk_score": 50, "reason": "текст", "action_required": false}
"""

class AIAnalyzer:
    def __init__(self):
        self.model = genai.GenerativeModel('gemini-2.5-flash', system_instruction=SYSTEM_PROMPT)

    def analyze_news(self, news: NewsItem) -> RiskAssessment:
        prompt = f"Событие: {news.content}\nTVL протокола: {news.tvl}\nВолатильность рынка: {news.volatility}"
        
        try:
            response = self.model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    response_mime_type="application/json",
                )
            )
            data = json.loads(response.text)
            return RiskAssessment(**data)
        except Exception as e:
            print(f"Внутренняя ошибка модуля: {e}")
            return RiskAssessment(
                risk_score=99,
                reason="Системная ошибка связи. Рекомендована экстренная блокировка.",
                action_required=True
            )
