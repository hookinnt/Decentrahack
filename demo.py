import time
from colorama import init, Fore, Style
from agent.news_feed import get_latest_news
from agent.analyzer import AIAnalyzer
from agent.solana_client import verify_solana_or_crash

# Инициализируем colorama (для того, чтобы цвета работали в консоли Windows)
init(autoreset=True)

def print_header():
    print(f"{Fore.CYAN}{Style.BRIGHT}======================================================")
    print(f"{Fore.CYAN}{Style.BRIGHT}   [ *** AI Agent: Risk & Treasury Management (Demo) *** ]")
    print(f"{Fore.CYAN}{Style.BRIGHT}======================================================\n")

def run_demo():
    print_header()
    
    # КРИТИЧЕСКОЕ ПРАВИЛО: БЕЗ СОЛАНЫ - ПАДЕНИЕ (Fail-Fast Rule)
    verify_solana_or_crash()

    print(f"\n{Fore.YELLOW}[Система] Загрузка новостного фида для анализа...\n")
    time.sleep(1.5)
    
    # Инициализация ИИ-оракула и новостной ленты
    news_list = get_latest_news()
    analyzer = AIAnalyzer()
    
    for news in news_list:
        print(f"{Fore.WHITE}{Style.BRIGHT}[>>> НОВОСТЬ ПОЛУЧЕНА]")
        print(f"Заголовок: {news.headline}")
        print(f"Текст: {news.content}")
        print(f"{Fore.CYAN}[### AI-Агент] Обработка данных и анализ рисков...")
        
        # Симулируем задержку, так как запрос к API занимает время
        time.sleep(0.5) 
        
        try:
            assessment = analyzer.analyze_news(news)
            
            # Цветовая логика для эффектной презентации
            if assessment.risk_score >= 80 and assessment.action_required:
                color = Fore.RED
                action_text = f"{Fore.RED}{Style.BRIGHT}[!!!] ИНИЦИИРУЮ ЗАЩИТУ: ОТПРАВКА ТРАНЗАКЦИИ В СОЛАНУ"
                print(f"{color}Оценка Риска: {assessment.risk_score} / 100")
                print(f"{color}Размышления: {assessment.reason}")
                print(action_text)
                
                # Реальный вызов блокчейна
                from agent.solana_client import execute_emergency_pause
                tx_hash = execute_emergency_pause(assessment.reason, assessment.risk_score)
                if tx_hash:
                    print(f"{Fore.GREEN}[SUCCESS] Solscan: https://solscan.io/tx/{tx_hash}?cluster=devnet")
                else:
                    print(f"{Fore.RED}[FAILED] Не удалось отправить транзакцию (недостаточно SOL?)")

            elif assessment.risk_score >= 40:
                color = Fore.YELLOW
                action_text = f"{Fore.YELLOW}[~] Режим ожидания. Статус: Наблюдение."
                print(f"{color}Оценка Риска: {assessment.risk_score} / 100")
                print(f"{color}Размышления: {assessment.reason}")
                print(action_text)
            else:
                color = Fore.GREEN
                action_text = f"{Fore.GREEN}[✓] Рисков не обнаружено. Штатная работа."
                print(f"{color}Оценка Риска: {assessment.risk_score} / 100")
                print(f"{color}Размышления: {assessment.reason}")
                print(action_text)
                
        except Exception as e:
            print(f"{Fore.RED}[Ошибка] Внутренний сбой: {e}")
            
        print("-" * 54 + "\n")
        time.sleep(2.5)

if __name__ == "__main__":
    try:
        run_demo()
    except KeyboardInterrupt:
        print(f"{Fore.WHITE}[Система] Остановка демо-режима.")
