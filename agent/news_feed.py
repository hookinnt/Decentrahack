from typing import List
from agent.models import NewsItem

def get_latest_news() -> List[NewsItem]:
    """
    Тестовые данные СТРОГО о Solana экосистеме.
    Никаких упоминаний сторонних блокчейнов.
    """
    return [
        NewsItem(
            id="1",
            headline="Обновление Validator Client Solana",
            content="Разработчики успешно выкатили апдейт Firedancer в тестнете Solana. Пропускная способность увеличена до 1 миллиона TPS."
        ),
        NewsItem(
            id="2",
            headline="Партнерство Solana Foundation",
            content="Крупный платежный гигант Visa интегрировал USDC платежи напрямую в сети блокчейна Solana для ускорения транзакций."
        ),
        NewsItem(
            id="3",
            headline="Критическая уязвимость пула ликвидности на Solana!",
            content="СРОЧНО: Неизвестный хакер нашел уязвимость в DeFi смарт-контракте на сети Solana и вывел 50 миллионов USDC. Аналитики безопасности сообщают, что архитектура Anchor программы содержала дыру."
        )
    ]
