# -*- coding: utf-8 -*-
"""
Generates Autonoma_Pitch.pdf — technical architecture & presentation toolkit.
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

# ── Font Setup ──────────────────────────────────────────────────────────────
def try_register(name, bold_name, paths):
    for reg_path, bold_path in paths:
        if os.path.exists(reg_path) and os.path.exists(bold_path):
            try:
                pdfmetrics.registerFont(TTFont(name, reg_path))
                pdfmetrics.registerFont(TTFont(bold_name, bold_path))
                return True
            except: continue
    return False

FONT_NAME = "MainFont"
FONT_BOLD = "MainFontBold"

registered = try_register(FONT_NAME, FONT_BOLD, [
    (r"C:\Windows\Fonts\arial.ttf",   r"C:\Windows\Fonts\arialbd.ttf"),
    (r"C:\Windows\Fonts\calibri.ttf", r"C:\Windows\Fonts\calibrib.ttf"),
    (r"C:\Windows\Fonts\segoeui.ttf", r"C:\Windows\Fonts\segoeuib.ttf"),
])

if not registered:
    sys.exit(1)

# ── Helpers ──────────────────────────────────────────────────────────────────
def fill_bg(c):
    c.setFillColor(BG)
    c.rect(0, 0, W, H, fill=1, stroke=0)

def accent_bar(c, y, color=GREEN, thickness=1.5):
    c.setFillColor(color)
    c.rect(PAD, y, W - 2*PAD, thickness, fill=1, stroke=0)

def sidebar(c, x, y, h, color=GREEN, w=3):
    c.setFillColor(color)
    c.rect(x, y, w, h, fill=1, stroke=0)

def draw_multiline(c, text, x, y, font=FONT_NAME, size=10, color=WHITE, max_width=None, leading=14):
    c.setFont(font, size)
    c.setFillColor(color)
    paragraphs = text.split('\n')
    for para in paragraphs:
        words = para.split(' ')
        lines = []
        current = ''
        for w_word in words:
            test = (current + ' ' + w_word).strip()
            if c.stringWidth(test, font, size) <= max_width:
                current = test
            else:
                if current: lines.append(current)
                current = w_word
        if current: lines.append(current)
        for line in lines:
            c.drawString(x, y, line)
            y -= leading
    return y

def section_header(c, title, y, color=GREEN):
    c.setFont(FONT_BOLD, 13)
    c.setFillColor(color)
    c.drawString(PAD, y, title)
    y -= 6
    accent_bar(c, y, color, 1)
    return y - 10

# ════════════════════════════════════════════════════════════════════════════
OUT_PATH = os.path.join(os.path.dirname(__file__), "Autonoma_Pitch.pdf")
c = canvas.Canvas(OUT_PATH, pagesize=A4)

# ── PAGE 1: TITLE ─────────────────────────────────────────────────────────────
fill_bg(c)
c.setFillColor(GREEN)
c.rect(0, H - 4, W, 4, fill=1, stroke=0)

c.setFont(FONT_BOLD, 52)
c.setFillColor(WHITE)
c.drawString(PAD, H - 80, "AUTONOMA")
c.setFont(FONT_BOLD, 34)
c.setFillColor(GREEN)
c.drawString(PAD, H - 120, "Risk Manager")

accent_bar(c, H - 136, GREEN)
c.setFont(FONT_NAME, 12)
c.setFillColor(MUTED)
c.drawString(PAD, H - 158, "Autonomous AI Defense for Solana Smart Contracts")

meta = [
    ("PROGRAM", "Anchor Protocol (Rust)", GREEN),
    ("INTELLIGENCE", "Gemini 1.5 Flash + Deterministic Fallback", BLUE),
    ("ALGORITHM", "DARS (Dynamic Autonomous Risk Sensitivity)", YELLOW),
]
my = H - 230
for label, val, col in meta:
    c.setFont(FONT_BOLD, 8)
    c.setFillColor(col)
    c.drawString(PAD, my, label)
    c.setFont(FONT_NAME, 9)
    c.setFillColor(WHITE)
    c.drawString(PAD + 90, my, val)
    my -= 18

c.showPage()

# ── PAGE 2: ARCHITECTURE ──────────────────────────────────────────────────────
fill_bg(c)
c.setFillColor(GREEN)
c.rect(0, H-4, W, 4, fill=1, stroke=0)

y = H - 60
y = section_header(c, "ТЕХНИЧЕСКАЯ АРХИТЕКТУРА", y, GREEN)

arch_sections = [
    ("1. Brain (Off-chain Monitoring)", BLUE, 
     "Система работает на базе Google Gemini 1.5 Flash. Агент непрерывно анализирует "
     "телеметрию: RSS-фиды (CoinTelegraph/CoinDesk), рыночные данные CoinGecko и "
     "статус мостов. LLM используется не просто для чата, а как reasoning engine "
     "для выявления сложных векторов атак (манипуляция оракулами, хаки мостов)."),
     
    ("2. Deterministic Fallback", RED,
     "Для обеспечения доступности 24/7 предусмотрен слой 'жесткой логики'. "
     "Если API ИИ недоступно, вступает в силу движок на базе ключевых слов и "
     "порогов волатильности, гарантируя, что протокол не останется без защиты."),

    ("3. Shield (On-chain Control)", GREEN,
     "Смарт-контракт на Anchor (Rust) хранит состояние TreasuryState в PDA. "
     "Агент обладает уникальным правом подписи (Authority). При обнаружении "
     "угрозы агент автономно строит и подписывает транзакцию `emergency_pause`, "
     "замораживая средства за доли секунды."),

    ("4. DARS Algorithm", YELLOW,
     "Dynamic Autonomous Risk Sensitivity — наша ключевая инновация. "
     "Система автоматически меняет `risk_threshold` в блокчейне. "
     "Рынок спокоен? Порог 85 (минимум ложных срабатываний). "
     "Рыночный шторм? Порог 65 (максимальная паранойя)."),
]

for tag, color, body in arch_sections:
    c.setFont(FONT_BOLD, 10)
    c.setFillColor(color)
    c.drawString(PAD, y, tag)
    y -= 14
    y = draw_multiline(c, body, PAD + 10, y, FONT_NAME, 9.5, WHITE, max_width=W-2*PAD-20, leading=14)
    y -= 10

c.showPage()

# ── PAGE 3: PITCH SCRIPT ──────────────────────────────────────────────────────
fill_bg(c)
c.setFillColor(GREEN)
c.rect(0, H-4, W, 4, fill=1, stroke=0)

y = H - 60
y = section_header(c, "ТЕХНИЧЕСКИЙ ПИТЧ (СЦЕНАРИЙ)", y, GREEN)

script = [
    ("PROBLEM: Human Latency", GREEN,
     "В DeFi сейчас критическая задержка безопасности. Пока команда замечает взлом, "
     "пока собирается мультисиг — средства уже в миксерах. Мы убираем человека из этой цепи."),

    ("ARCHITECTURE: The AI Oracle", BLUE,
     "Autonoma — это 'сторожевой пес' для вашего казначейства. Мы совместили гибкость LLM "
     "с жесткостью смарт-контрактов Solana. Агент постоянно 'дышит' данными из сети "
     "и самостоятельно принимает решение о блокировке."),

    ("INNOVATION: DARS Engine", YELLOW,
     "Главное отличие — мы не работаем со статичным кодом. Алгоритм DARS в реальном времени "
     "адаптирует чувствительность смарт-контракта к рыночной волатильности."),

    ("LIVE DEMO: Zero-Minute Response", GREEN,
     "В нашей демо-версии вы видите, как система ловит аномальный payload "
     "и подписывает Anchor-инструкцию в Devnet автоматически. Это переход от "
     "реактивной безопасности к полностью автономной."),
]

for tag, color, body in script:
    c.setFont(FONT_BOLD, 9)
    c.setFillColor(color)
    c.drawString(PAD, y, tag)
    y -= 12
    y = draw_multiline(c, body, PAD + 10, y, FONT_NAME, 10, WHITE, max_width=W-2*PAD-20, leading=14)
    y -= 12

c.showPage()

# ── PAGE 4: PROMPT ────────────────────────────────────────────────────────────
fill_bg(c)
c.setFillColor(BLUE)
c.rect(0, H-4, W, 4, fill=1, stroke=0)

y = H - 60
y = section_header(c, "AI PRESENTATION PROMPT", y, BLUE)

prompt = """Создай техническую презентацию (6 слайдов) для проекта Autonoma Risk Manager.
СТИЛЬ: Dark Mode, Enterprise DeFi, цвета #34c759 (зеленый) и #5aa0ff (синий).

Слайд 1: Autonoma — Автономная безопасность Solana. Фокус на 0% задержке реакции.
Слайд 2: Проблема 'Manual Ops'. Риски мультисигов и человеческого фактора при взломах.
Слайд 3: Архитектура: Off-chain Oracle (Gemini AI) -> On-chain Shield (Anchor/PDA).
Слайд 4: DARS (Dynamic Autonomous Risk Sensitivity). Адаптивные пороги риска на базе волатильности.
Слайд 5: Автономное подписание транзакций. Как агент вызывает emergency_pause без вмешательства человека.
Слайд 6: Итог. Безопасность со скоростью кода. Готово к интеграции в любой Solana-протокол.
"""

y = draw_multiline(c, prompt, PAD, y, FONT_NAME, 9, WHITE, max_width=W-2*PAD, leading=14)

c.showPage()
c.save()
print(f"[OK] PDF saved: {OUT_PATH}")
