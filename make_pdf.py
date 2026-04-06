# -*- coding: utf-8 -*-
"""
Generates Autonoma_Pitch.pdf — pitch script + presentation prompt
Uses reportlab for full Cyrillic support.
"""
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor
import os, sys

# ── Colors ──────────────────────────────────────────────────────────────────
BG       = HexColor("#0b0c10")
CARD     = HexColor("#111115")
GREEN    = HexColor("#34c759")
BLUE     = HexColor("#5aa0ff")
YELLOW   = HexColor("#ffcc00")
RED      = HexColor("#ff3b30")
WHITE    = HexColor("#f0f0f2")
MUTED    = HexColor("#80808a")
DIMMED   = HexColor("#444450")

W, H = A4  # 595 x 841 pts
PAD = 18 * mm

# ── Font Setup (use system fonts for Cyrillic) ───────────────────────────────
FONTS_TRIED = []

def try_register(name, bold_name, paths):
    """Try multiple OS paths to find a Unicode/Cyrillic font."""
    for reg_path, bold_path in paths:
        if os.path.exists(reg_path) and os.path.exists(bold_path):
            try:
                pdfmetrics.registerFont(TTFont(name, reg_path))
                pdfmetrics.registerFont(TTFont(bold_name, bold_path))
                return True
            except Exception as e:
                continue
    return False

# Try common Windows Cyrillic-capable fonts
FONT_NAME = "MainFont"
FONT_BOLD = "MainFontBold"

registered = try_register(FONT_NAME, FONT_BOLD, [
    # Arial (ships with Windows, has full Cyrillic)
    (r"C:\Windows\Fonts\arial.ttf",   r"C:\Windows\Fonts\arialbd.ttf"),
    # Calibri
    (r"C:\Windows\Fonts\calibri.ttf", r"C:\Windows\Fonts\calibrib.ttf"),
    # Segoe UI
    (r"C:\Windows\Fonts\segoeui.ttf", r"C:\Windows\Fonts\segoeuib.ttf"),
    # Verdana
    (r"C:\Windows\Fonts\verdana.ttf", r"C:\Windows\Fonts\verdanab.ttf"),
])

if not registered:
    print("[ERROR] No Cyrillic-capable font found in C:\\Windows\\Fonts")
    sys.exit(1)

print(f"[OK] Font registered: {FONT_NAME}")

# ── Helpers ──────────────────────────────────────────────────────────────────
def fill_bg(c: canvas.Canvas):
    c.setFillColor(BG)
    c.rect(0, 0, W, H, fill=1, stroke=0)

def accent_bar(c: canvas.Canvas, y, color=GREEN, thickness=1.5):
    c.setFillColor(color)
    c.rect(PAD, y, W - 2*PAD, thickness, fill=1, stroke=0)

def sidebar(c: canvas.Canvas, x, y, h, color=GREEN, w=3):
    c.setFillColor(color)
    c.rect(x, y, w, h, fill=1, stroke=0)

def draw_text(c, txt, x, y, font=FONT_NAME, size=10, color=WHITE, max_width=None, leading=14):
    """Draw text, wrapping if max_width given. Returns final Y."""
    c.setFont(font, size)
    c.setFillColor(color)
    if max_width is None:
        c.drawString(x, y, txt)
        return y - leading
    # Manual word-wrap
    words = txt.split(' ')
    lines = []
    current = ''
    for w_word in words:
        test = (current + ' ' + w_word).strip()
        if c.stringWidth(test, font, size) <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = w_word
    if current:
        lines.append(current)
    for line in lines:
        c.drawString(x, y, line)
        y -= leading
    return y

def draw_multiline(c, text, x, y, font=FONT_NAME, size=10, color=WHITE,
                   max_width=None, leading=14):
    """Handle \n and word-wrap."""
    paragraphs = text.split('\n')
    for para in paragraphs:
        y = draw_text(c, para, x, y, font, size, color, max_width, leading)
    return y

def section_header(c, title, y, color=GREEN):
    c.setFont(FONT_BOLD, 13)
    c.setFillColor(color)
    c.drawString(PAD, y, title)
    y -= 6
    accent_bar(c, y, color, 1)
    return y - 10

def card_block(c, title, body, x, y, w_box, color=GREEN, title_size=9, body_size=9):
    """Draw a labeled block with left sidebar."""
    # title
    c.setFont(FONT_BOLD, title_size)
    c.setFillColor(color)
    c.drawString(x + 8, y, title)
    y -= 4

    start_y = y
    # body
    y = draw_multiline(c, body, x + 8, y, FONT_NAME, body_size, MUTED,
                       max_width=w_box - 16, leading=13)
    end_y = y

    sidebar(c, x, end_y, start_y - end_y + 12, color)
    return y - 8

# ════════════════════════════════════════════════════════════════════════════
# BUILD PDF
# ════════════════════════════════════════════════════════════════════════════
OUT_PATH = os.path.join(os.path.dirname(__file__), "Autonoma_Pitch.pdf")
c = canvas.Canvas(OUT_PATH, pagesize=A4)
c.setTitle("Autonoma Risk Manager — Pitch & Prompt")

# ── PAGE 1: TITLE ─────────────────────────────────────────────────────────────
fill_bg(c)

# Top green accent
c.setFillColor(GREEN)
c.rect(0, H - 4, W, 4, fill=1, stroke=0)

# Big Title
c.setFont(FONT_BOLD, 52)
c.setFillColor(WHITE)
c.drawString(PAD, H - 80, "AUTONOMA")

c.setFont(FONT_BOLD, 34)
c.setFillColor(GREEN)
c.drawString(PAD, H - 120, "Risk Manager")

accent_bar(c, H - 136, GREEN)

c.setFont(FONT_NAME, 12)
c.setFillColor(MUTED)
c.drawString(PAD, H - 158, "Автономная AI-система безопасности для смарт-контрактов Solana")

c.setFont(FONT_NAME, 10)
c.setFillColor(DIMMED)
c.drawString(PAD, H - 176, "Сценарий выступления  •  Prompt для генерации презентации  •  Инструкция запуска")

# Meta tags
meta = [
    ("БЛОКЧЕЙН", "Solana Devnet  /  Anchor (Rust)", GREEN),
    ("AI-ДВИЖОК", "Google Gemini Flash  +  Fallback-детерминизм", BLUE),
    ("ТЕХНОЛОГИЯ","DARS  •  Emergency Pause  •  WebSockets", YELLOW),
]
my = H - 230
for label, val, col in meta:
    c.setFont(FONT_BOLD, 8)
    c.setFillColor(col)
    c.drawString(PAD, my, label)
    c.setFont(FONT_NAME, 9)
    c.setFillColor(WHITE)
    c.drawString(PAD + 72, my, val)
    my -= 18

accent_bar(c, H - 310, DIMMED, 0.5)

c.setFont(FONT_NAME, 8)
c.setFillColor(DIMMED)
c.drawString(PAD, H - 328, "Olympiad Project  ·  2026")

c.showPage()

# ── PAGE 2: LAUNCH GUIDE ──────────────────────────────────────────────────────
fill_bg(c)
c.setFillColor(GREEN)
c.rect(0, H-4, W, 4, fill=1, stroke=0)

y = H - 60
y = section_header(c, "КАК ЗАПУСТИТЬ", y, GREEN)

# Mode 1
c.setFont(FONT_BOLD, 11)
c.setFillColor(GREEN)
c.drawString(PAD, y, "1.  Эмуляция  (без интернета, offline)")
y -= 18

steps_demo = [
    "Двойной клик на  run.bat",
    "Браузер откроется на  http://127.0.0.1:8080",
    'Нажмите кнопку  "ЗАПУСТИТЬ ЭМУЛЯЦИЮ"',
    "Сценарий проигрывается автоматически:",
    "  сканирование → аномалия Wormhole → критическая блокировка (98%)",
    "Нажмите 'РАЗБЛОКИРОВАТЬ СРЕДСТВА' чтобы сбросить состояние",
]
for s in steps_demo:
    c.setFont(FONT_NAME, 9)
    c.setFillColor(WHITE if not s.startswith(" ") else MUTED)
    c.drawString(PAD + 10, y, ("• " if not s.startswith(" ") else "") + s.strip())
    y -= 13
y -= 8

accent_bar(c, y, DIMMED, 0.4)
y -= 14

# Mode 2
c.setFont(FONT_BOLD, 11)
c.setFillColor(BLUE)
c.drawString(PAD, y, "2.  Production Live Engine  (полный стек)")
y -= 18

steps_live = [
    "Заполни  .env  файл: добавь  GEMINI_API_KEY=...",
    "Установи зависимости (один раз):  pip install -r requirements.txt",
    "Двойной клик на  run.bat",
    "Браузер откроется на  http://127.0.0.1:5000",
    "BackgroundMonitor стартует автоматически, дашборд обновляется live",
    "Кнопка 'ПРОВЕРИТЬ СЕЙЧАС' — принудительно запускает AI-аудит",
    "Кнопка 'РАЗБЛОКИРОВАТЬ СРЕДСТВА' — вызывает on-chain resume()",
]
for s in steps_live:
    c.setFont(FONT_NAME, 9)
    c.setFillColor(WHITE)
    c.drawString(PAD + 10, y, "• " + s)
    y -= 13
y -= 10

accent_bar(c, y, DIMMED, 0.4)
y -= 14

# Requirements table
c.setFont(FONT_BOLD, 9)
c.setFillColor(DIMMED)
c.drawString(PAD, y, "ТРЕБОВАНИЯ ДЛЯ LIVE ENGINE")
y -= 14

reqs = [
    ("Python 3.10+",            "python.org  или  Microsoft Store"),
    ("GEMINI_API_KEY",          "aistudio.google.com  → Get API Key (бесплатно)"),
    ("pip install -r ...",      "запустить один раз в папке проекта"),
    ("Solana CLI + Anchor",     "только если деплоишь контракт на devnet"),
]
for cmd, desc in reqs:
    c.setFillColor(CARD)
    c.rect(PAD, y - 2, W - 2*PAD, 13, fill=1, stroke=0)
    c.setFont(FONT_BOLD, 8)
    c.setFillColor(BLUE)
    c.drawString(PAD + 4, y + 7, cmd)
    c.setFont(FONT_NAME, 8)
    c.setFillColor(MUTED)
    c.drawString(PAD + 140, y + 7, desc)
    y -= 16

c.showPage()

# ── PAGE 3: PITCH SCRIPT ──────────────────────────────────────────────────────
fill_bg(c)
c.setFillColor(GREEN)
c.rect(0, H-4, W, 4, fill=1, stroke=0)

y = H - 60
y = section_header(c, "СЦЕНАРИЙ ВЫСТУПЛЕНИЯ", y, GREEN)

c.setFont(FONT_NAME, 8)
c.setFillColor(DIMMED)
c.drawString(PAD, y, "Разговорный стиль. Ориентир, не скрипт — говори своими словами.")
y -= 18

script_sections = [
    ("[ВСТУПЛЕНИЕ — захватываем внимание]", GREEN,
     "Всем привет. В DeFi сейчас есть одна огромная проблема. Хакеры работают со скоростью скриптов, "
     "а команды безопасности — со скоростью живых людей. Пока они понимают что происходит, "
     "пока собирают мультисиг, пока отправляют паузу... проходит от 15 до 40 минут. "
     "А деньги уже ушли. Мы решили убрать человека из этой цепочки."),

    ("[ПРОДУКТ — что мы сделали]", GREEN,
     "Поэтому мы разработали Autonoma Risk Manager. Это не очередной дашборд с графиками. "
     "Это автономный AI-организм для защиты Solana-казначейств. Он делает ровно две вещи: "
     "постоянно мониторит всё что происходит в сети — и самостоятельно блокирует "
     "вывод средств на уровне смарт-контракта. Без единого клика от человека."),

    ("[КАК ЭТО РАБОТАЕТ — под капотом]", BLUE,
     "Под капотом живёт AI-агент, который нон-стоп парсит транзакции, новостной фон, аномалии TVL "
     "и волатильность рынка. Он считает индекс риска. Если тот пробивает порог — сам подписывает "
     "Anchor-транзакцию с вызовом emergency_pause.\n"
     "Ещё есть наша система DARS — Динамическая Автономная Чувствительность Рисков. "
     "Агент работает не с фиксированным порогом. Рынок штормит — порог снижается, "
     "система становится параноиком. Всё тихо — порог поднимается, нет ложных срабатываний."),

    ("[ДЕМОНСТРАЦИЯ — показываем live]", YELLOW,
     'Открываем демо, нажимаем "ЗАПУСТИТЬ ЭМУЛЯЦИЮ".\n'
     "Вот система мониторит сеть — всё зелёное. И сейчас симулируем подозрительную транзакцию "
     "через Wormhole. Риск поднялся до 45%, статус — Опасность. Ещё пару секунд — критический "
     "payload пойман, AI отправил транзакцию паузы прямо в Solana Devnet. 98%. "
     "Средства заморожены. Угроза нейтрализована. И всё это — без единого клика с нашей стороны."),

    ("[ЗАКЛЮЧЕНИЕ]", GREEN,
     "В итоге — plug-and-play решение для любого DeFi-протокола на Solana, "
     "которое переводит безопасность из реактивной в проактивную. Спасибо."),
]

MAX_W = W - 2*PAD - 24

for tag, color, body in script_sections:
    if y < 100:
        c.showPage()
        fill_bg(c)
        y = H - 40

    c.setFont(FONT_BOLD, 8)
    c.setFillColor(color)
    c.drawString(PAD, y, tag)
    y -= 6

    start_y = y
    y = draw_multiline(c, body, PAD + 12, y, FONT_NAME, 9.5, WHITE,
                       max_width=MAX_W, leading=14)
    end_y = y

    sidebar(c, PAD, end_y, start_y - end_y + 4, color)
    y -= 14

c.showPage()

# ── PAGE 4: PRESENTATION PROMPT ───────────────────────────────────────────────
fill_bg(c)
c.setFillColor(BLUE)
c.rect(0, H-4, W, 4, fill=1, stroke=0)

y = H - 60
y = section_header(c, "PROMPT ДЛЯ ГЕНЕРАЦИИ ПРЕЗЕНТАЦИИ", y, BLUE)

c.setFont(FONT_NAME, 8)
c.setFillColor(DIMMED)
c.drawString(PAD, y, "Вставить в Gamma.app, Tome.app, ChatGPT или другой генератор слайдов.")
y -= 16

prompt_lines = """Создай pitch-презентацию для хакатона из 6 слайдов по следующему плану.

ПРОЕКТ: Autonoma Risk Manager
СУТЬ: Автономная AI-система безопасности для DeFi-протоколов на блокчейне Solana.
Система в реальном времени мониторит угрозы (взломы, аномалии TVL, flash-loan атаки)
и автоматически замораживает смарт-контракт без участия человека.

СТИЛЬ: Dark mode. Минимализм. Enterprise crypto. Черные и темно-серые фоны,
неоновые зеленые (#34c759) и синие акценты. Шрифт — Inter или Geist.
Тон: уверенный, технический, без воды.

--- СЛАЙДЫ ---

СЛАЙД 1. Титульный.
Заголовок: Autonoma Risk Manager
Подзаголовок: Автономная AI-безопасность для Solana-казначейств
Визуал: Строгий интерфейс с зеленым индикатором СТАБИЛЬНО / 12%

СЛАЙД 2. Проблема.
Заголовок: Хакеры быстрее людей
Факты: (1) $2.8 млрд украдено из DeFi в 2023 году.
(2) Среднее время реакции команды безопасности — 15–40 минут.
(3) За это время эксплойт уже выводит средства через миксеры.

СЛАЙД 3. Решение.
Заголовок: Убираем человека из цепочки защиты
3 пункта: AI-агент мониторит сеть 24/7; При Critical Risk — автоматически
вызывает on-chain функцию emergency_pause; Никакого мультисига, никаких задержек.

СЛАЙД 4. Технология DARS.
Заголовок: Dynamic Autonomous Risk Sensitivity
Описание: Не статический порог, а живая адаптация. При высокой волатильности —
порог блокировки снижается. При стабильности — поднимается, чтобы избежать
ложных срабатываний. Threshold обновляется on-chain транзакцией автоматически.

СЛАЙД 5. Архитектура.
Заголовок: On-chain + Off-chain синхронизация
3 блока: [Data Engine] Парсинг цены SOL, TVL, новостей
[LLM Auditor] Gemini AI анализирует риски + детерминированный Fallback
[Solana Program] Anchor-контракт: initialize / emergency_pause / resume / update_threshold

СЛАЙД 6. Итог.
Заголовок: Готово к продакшену
Буллеты: Совместим с Solana Devnet и Mainnet;
Plug-and-play интеграция для любого DeFi-протокола;
Проактивная защита вместо реактивной паники.
Финальная фраза: Autonoma — потому что безопасность не должна зависеть
от скорости реакции человека."""

c.setFillColor(CARD)
c.rect(PAD - 4, y - len(prompt_lines.split('\n')) * 12 - 10,
       W - 2*PAD + 8, len(prompt_lines.split('\n')) * 12 + 16, fill=1, stroke=0)

y = draw_multiline(c, prompt_lines, PAD + 2, y - 2, FONT_NAME, 8, WHITE,
                   max_width=W - 2*PAD - 4, leading=12)

# Footer
c.setFont(FONT_NAME, 7.5)
c.setFillColor(DIMMED)
c.drawCentredString(W/2, 20, "Autonoma Risk Manager  ·  Olympiad Project 2026")

c.showPage()
c.save()
print(f"\n[OK] PDF saved: {OUT_PATH}\n")
