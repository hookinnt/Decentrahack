import sys
from solana.rpc.api import Client
from colorama import Fore, Style

# Подключение к публичному Devnet кластеру Solana
SOLANA_RPC_URL = "https://api.devnet.solana.com"

def verify_solana_or_crash():
    """
    КРИТИЧЕСКОЕ ТРЕБОВАНИЕ ИЗ ВЕБИНАРА (Fail-Fast Rule):
    Вся система должна полностью опираться на блокчейн Solana. 
    Если блокчейн недоступен — приложение обязано немедленно упасть со строгой ошибкой.
    Никаких мягких обработок оффлайн-режима. Нет Solana = Нет работы.
    """
    print(f"{Fore.CYAN}[Система] Инициализация соединения с Solana RPC ({SOLANA_RPC_URL})...")
    
    try:
        # Проверяем реальное подключение к узлу
        client = Client(SOLANA_RPC_URL)
        if not client.is_connected():
            raise ConnectionError("RPC узел не ответил на пинг.")
            
        # Запрашиваем версию ноды, чтобы убедиться, что всё корректно
        version_resp = client.get_version()
        
        # В новой версии библиотеки solana-py get_version() возвращает объект GetVersionResp
        # В зависимости от версии библиотеки ключ может отличаться, но сам факт ответа подтверждает связь
        print(f"{Fore.GREEN}[Успех] Стабильное соединение с блокчейном Solana установлено.")
        
    except Exception as e:
        # Жесткое падение (Crash) в строгом соответствии с требованиями архитектуры
        print(f"\n{Fore.RED}{Style.BRIGHT}======================================================")
        print(f"{Fore.RED}{Style.BRIGHT} [CRITICAL ERROR] SOLANA BLOCKCHAIN IS UNREACHABLE")
        print(f"{Fore.RED}{Style.BRIGHT}======================================================")
        print(f"{Fore.WHITE}Программа была принудительно остановлена (Crash).")
        print(f"{Fore.WHITE}Проект полностью завязан на Solana. Без стабильного блокчейна")
        print(f"{Fore.WHITE}алгоритмы ИИ не имеют смысла. Ошибка связи: {e}\n")
        sys.exit(1)
