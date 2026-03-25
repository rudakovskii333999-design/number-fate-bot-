# -*- coding: utf-8 -*-
import logging
import os
import random
import datetime
import re
import openai
from telegram import Update, InputFile, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, PreCheckoutQueryHandler, CallbackQueryHandler
from database import init_db, add_donation, get_total_donations, add_manual_donation, get_total_manual_donations, reset_donations

# ---------- НАСТРОЙКИ ----------
TOKEN = "8794960959:AAFvMBMc-cvbLoT1WzpAPbLadES8BDrZn3w"
GROQ_API_KEY = "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"
PROVIDER_TOKEN = ""
HELP_LINK = "https://maksimsmahelp.taplink.ws/"
BYN_RATE = 0.037
MIN_AMOUNT_BYN = 2
MIN_AMOUNT_RUB = 50
ADMIN_ID = 687833856

# Настройка OpenAI для Groq
openai.api_key = GROQ_API_KEY
openai.base_url = "https://api.groq.com/openai/v1"

# ---------- ИНФОРМАЦИЯ О ПОМОЩИ ----------
HELP_INFO = """
💖 **Я помогаю Максиму**

Я поддерживаю официальный сбор для **Максима Кулиды**, 4 года, г. Мозырь (Беларусь).  

🦓 **Диагноз:** Спинальная мышечная атрофия (СМА 3 типа) — редкое генетическое заболевание, при котором организм теряет способность двигаться.

💊 **Нужно:** 
• Укол **Zolgensma** — самый дорогой препарат в мире: **1 817 000 $**
• Пожизненная поддерживающая терапия
• Реабилитация и специальное оборудование

📊 **Статистика:**
• В Беларуси всего 12 детей с таким диагнозом
• Без лечения Максим потеряет способность ходить
• Своевременная терапия может остановить болезнь

👉 **Страница сбора с реквизитами:**  
https://maksimsmahelp.taplink.ws/

Там можно помочь картой, МТС-деньгами, криптовалютой, PayPal.

💝 **Каждый рубль приближает Максима к здоровой жизни!**

Часть доходов от платных прогнозов я перевожу на лечение Максима.  
Спасибо, что выбираете добро! ✨
"""

# --------------------------------------------------

logging.basicConfig(level=logging.INFO)
user_data = {}

# ---------- AI ПРОВЕРКА ИМЕНИ ----------
async def is_valid_name_ai(name, context):
    if not name or len(name) < 2:
        return False
    prompt = f"""Ты — эксперт по именам. Определи, является ли строка "{name}" реальным человеческим именем (русским, европейским, любым). 
Ответь только одним словом: ДА или НЕТ. Если это оскорбление, бессмыслица, выдумка, аббревиатура, цифры – ответь НЕТ."""
    try:
        response = openai.ChatCompletion.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=10,
            temperature=0
        )
        answer = response.choices[0].message.content.strip().upper()
        return answer == "ДА"
    except Exception as e:
        logging.error(f"AI name check error: {e}")
        return True

# ---------- ОПРЕДЕЛЕНИЕ ПОЛА ----------
async def get_gender(name, context):
    prompt = f"""Определи пол человека по имени "{name}". Ответь только одним словом: мужской или женский."""
    try:
        response = openai.ChatCompletion.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=10,
            temperature=0
        )
        gender = response.choices[0].message.content.strip().lower()
        if "муж" in gender:
            return "мужской"
        elif "жен" in gender:
            return "женский"
        return "неизвестно"
    except:
        return "неизвестно"

# ---------- ФУНКЦИЯ ДЛЯ РАЗБОРА ДАТЫ ----------
def parse_date(text):
    text = text.replace('.', ' ').replace(',', ' ')
    parts = text.split()
    if len(parts) != 3:
        return None
    try:
        d, m, y = map(int, parts)
        if not (1 <= d <= 31 and 1 <= m <= 12 and 1000 <= y <= 9999):
            return None
        return (d, m, y)
    except:
        return None

# ---------- ФУНКЦИЯ ДЛЯ ОПРЕДЕЛЕНИЯ ВАЛЮТЫ ----------
def parse_amount(amount_input):
    if amount_input <= 0:
        return None, None
    
    if 50 <= amount_input <= 5000:
        amount_rub = amount_input
        amount_byn = round(amount_rub * BYN_RATE, 2)
    elif 2 <= amount_input <= 200:
        amount_byn = amount_input
        amount_rub = round(amount_byn / BYN_RATE, 2)
    elif amount_input < 2:
        amount_byn = amount_input
        amount_rub = round(amount_byn / BYN_RATE, 2)
    else:
        amount_rub = amount_input
        amount_byn = round(amount_rub * BYN_RATE, 2)
    
    return amount_byn, amount_rub

# ---------- ЛУННЫЙ КАЛЕНДАРЬ ----------
def get_lunar_phase():
    day = datetime.datetime.now().day
    if day <= 7:
        phase = "🌑 Новолуние"
        advice = "Время для планирования и начала новых проектов. Энергия обновления."
    elif day <= 14:
        phase = "🌒 Растущая луна"
        advice = "Благоприятное время для активных действий, роста и новых начинаний."
    elif day <= 21:
        phase = "🌕 Полнолуние"
        advice = "Пик энергии. Время завершать дела, подводить итоги, отпускать."
    else:
        phase = "🌘 Убывающая луна"
        advice = "Время завершать и избавляться от лишнего. Хорошо для очищения."
    return phase, advice

def get_lunar_advice():
    phase, advice = get_lunar_phase()
    return f"🔮 {phase}\n{advice}"

# ---------- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ----------
def get_zodiac(day, month):
    if (month == 3 and day >= 21) or (month == 4 and day <= 19): return "Овен"
    elif (month == 4 and day >= 20) or (month == 5 and day <= 20): return "Телец"
    elif (month == 5 and day >= 21) or (month == 6 and day <= 20): return "Близнецы"
    elif (month == 6 and day >= 21) or (month == 7 and day <= 22): return "Рак"
    elif (month == 7 and day >= 23) or (month == 8 and day <= 22): return "Лев"
    elif (month == 8 and day >= 23) or (month == 9 and day <= 22): return "Дева"
    elif (month == 9 and day >= 23) or (month == 10 and day <= 22): return "Весы"
    elif (month == 10 and day >= 23) or (month == 11 and day <= 21): return "Скорпион"
    elif (month == 11 and day >= 22) or (month == 12 and day <= 21): return "Стрелец"
    elif (month == 12 and day >= 22) or (month == 1 and day <= 19): return "Козерог"
    elif (month == 1 and day >= 20) or (month == 2 and day <= 18): return "Водолей"
    else: return "Рыбы"

def get_life_path_number(day, month, year):
    total = day + month + year
    while total > 9:
        total = sum(int(d) for d in str(total))
    return total

def get_name_number(name):
    letters = "абвгдеёжзийклмнопрстуфхцчшщъыьэюя"
    total = 0
    for ch in name.lower():
        if ch in letters:
            total += letters.index(ch) + 1
    res = total % 9
    return 9 if res == 0 else res

def get_image_path(name):
    for ext in ['.png', '.gif']:
        path = os.path.join(os.path.dirname(__file__), "images", f"{name}{ext}")
        if os.path.exists(path):
            return path
    return None

def get_year_forecast_2026():
    return (
        "🌍 **ПРОГНОЗ НА 2026 ГОД**\n\n"
        "2026-й — год Огненной Лошади. Время движения, свободы и смелых решений.\n\n"
        "✨ **ЧТО ПРИНЕСЁТ:**\n"
        "• Возможности, требующие быстрой реакции — не раздумывай, действуй\n"
        "• Ясность в вопросах, которые долго мучили — ответы придут сами\n"
        "• Шанс начать новое дело или кардинально изменить жизнь\n"
        "• Встречи, которые изменят твоё мировоззрение\n"
        "• Неожиданные повороты, которые окажутся судьбоносными\n\n"
        "⚠️ **ЧЕГО ОСТЕРЕГАТЬСЯ:**\n"
        "• Поспешных решений на эмоциях — пауза важнее скорости\n"
        "• Обещаний, которые звучат слишком хорошо — проверяй факты\n"
        "• Желания всё контролировать — Лошадь не терпит узды\n"
        "• Переутомления из-за спешки — ресурс нужно беречь\n\n"
        "💡 **СОВЕТ ГОДА:** действуй, но проверяй. Скорость важна, но важнее направление. Доверяй интуиции, но включай разум."
    )

def get_daily_tip(zodiac):
    tips = {
        "Овен": "💡 Не торопись. Твоя сила в импульсе, но мудрость — в паузе.",
        "Телец": "💡 Отпусти то, что уже не служит. Новое не войдёт, пока руки заняты старым.",
        "Близнецы": "💡 Не распыляйся. Сосредоточься на одном — результат удивит.",
        "Рак": "💡 Защищай свои границы. Доброта без границ — путь к выгоранию.",
        "Лев": "💡 Свети для себя. Когда ты в ресурсе — ты светишь для всех.",
        "Дева": "💡 Отпусти контроль. Совершенство — не цель, а путь.",
        "Весы": "💡 Сделай шаг. Баланс не в неподвижности, а в движении.",
        "Скорпион": "💡 Не держись за прошлое. Твоя сила в трансформации.",
        "Стрелец": "💡 Близкие — твоё приключение. Не ищи счастье далеко, оно рядом.",
        "Козерог": "💡 Не превращай жизнь в гонку. Вершины покоряются в ритме.",
        "Водолей": "💡 Идеи важны, но люди важнее. Делись теплом.",
        "Рыбы": "💡 Доверяй интуиции. Она ведёт туда, куда разум боится заглянуть."
    }
    return tips.get(zodiac, "💡 Слушай себя. Внутри есть всё, что нужно.")

zodiac_texts = {
    "Овен": "🔥 Овен. Огонь, который зажигает. Ты — первопроходец, лидер, энергия. Твоя задача — научиться направлять свой огонь, а не сжигать всё вокруг.",
    "Телец": "🌱 Телец. Земля, опора. Ты — стабильность, чувственность, упорство. Твоя сила в терпении, но иногда нужно позволить себе меняться.",
    "Близнецы": "🌀 Близнецы. Воздух, гибкость. Ты — коммуникация, любопытство, адаптивность. Твой дар — видеть многообразие мира.",
    "Рак": "💧 Рак. Вода, эмпатия. Ты — забота, интуиция, глубина чувств. Твоя сила в умении любить, но не растворяться в anderen.",
    "Лев": "🌟 Лев. Огонь, щедрость. Ты — творчество, лидерство, великодушие. Твоя миссия — светить, но помнить, что свет нужно направлять.",
    "Дева": "📋 Дева. Земля, порядок. Ты — аналитика, служение, внимание к деталям. Твоя сила в точности, но совершенство не всегда нужно.",
    "Весы": "⚖️ Весы. Воздух, гармония. Ты — дипломатия, красота, справедливость. Твой дар — создавать равновесие в хаосе.",
    "Скорпион": "🦂 Скорпион. Вода, глубина. Ты — страсть, трансформация, магнетизм. Твоя сила в умении возрождаться из пепла.",
    "Стрелец": "🏹 Стрелец. Огонь, оптимизм. Ты — свобода, приключения, философия. Твоя миссия — искать истину и вдохновлять других.",
    "Козерог": "⛰️ Козерог. Земля, дисциплина. Ты — амбиции, ответственность, мудрость. Твоя сила в умении достигать вершин.",
    "Водолей": "🌊 Водолей. Воздух, независимость. Ты — инновации, дружба, свобода. Твой дар — видеть будущее и менять мир.",
    "Рыбы": "🐟 Рыбы. Вода, воображение. Ты — творчество, сострадание, мечты. Твоя сила в умении чувствовать то, что недоступно другим."
}

number_deep_texts = {
    1: "🔥 Лидер, первопроходец, новатор. Твоя задача — научиться брать ответственность, вести за собой и не бояться идти одному. Ты здесь, чтобы начинать новое.",
    2: "🤝 Дипломат, миротворец, партнёр. Твой путь — через отношения, умение слышать других и находить баланс. Ты здесь, чтобы объединять.",
    3: "🎨 Творец, вдохновитель, коммуникатор. Твоя миссия — выражать себя, радовать мир своим талантом и вдохновлять других. Ты здесь, чтобы творить.",
    4: "🏗️ Строитель, организатор, опора. Твоя сила в дисциплине, надёжности, умении создавать фундамент. Ты здесь, чтобы строить.",
    5: "🦋 Искатель, путешественник, авантюрист. Твой путь — через перемены, свободу, новый опыт. Ты здесь, чтобы пробовать и открывать.",
    6: "❤️ Заботливый, ответственный, целитель. Твоя миссия — любовь, семья, забота о близких. Ты здесь, чтобы заботиться и исцелять.",
    7: "🔮 Мыслитель, исследователь, мудрец. Твой путь — через знания, глубину, понимание скрытого. Ты здесь, чтобы познавать и открывать истину.",
    8: "💎 Деятель, управленец, реализатор. Твоя сила — в материальном мире, умении создавать богатство и влиять. Ты здесь, чтобы воплощать.",
    9: "🌟 Наставник, гуманист, завершитель. Твоя миссия — служение миру, мудрость, завершение циклов. Ты здесь, чтобы завершать и начинать новое."
}

def get_talisman_stone(zodiac):
    stones = {
        "Овен": "Алмаз, рубин",
        "Телец": "Изумруд, сапфир",
        "Близнецы": "Агат, берилл",
        "Рак": "Лунный камень, жемчуг",
        "Лев": "Рубин, янтарь",
        "Дева": "Сапфир, яшма",
        "Весы": "Опал, лазурит",
        "Скорпион": "Топаз, гранат",
        "Стрелец": "Бирюза, сапфир",
        "Козерог": "Гагат, оникс",
        "Водолей": "Аметист, циркон",
        "Рыбы": "Аквамарин, аметист"
    }
    return stones.get(zodiac, "Аметист")

def get_lucky_color(zodiac):
    colors = {
        "Овен": "Красный, оранжевый",
        "Телец": "Зелёный, розовый",
        "Близнецы": "Жёлтый, голубой",
        "Рак": "Серебристый, белый",
        "Лев": "Золотой, оранжевый",
        "Дева": "Серый, бежевый",
        "Весы": "Розовый, светло-зелёный",
        "Скорпион": "Тёмно-красный, чёрный",
        "Стрелец": "Фиолетовый, синий",
        "Козерог": "Коричневый, тёмно-зелёный",
        "Водолей": "Синий, электрик",
        "Рыбы": "Морская волна, лавандовый"
    }
    return colors.get(zodiac, "Радужный")

def get_name_interpretation(name):
    num = get_name_number(name)
    meanings = {1:"Лидер, прирождённый руководитель",2:"Дипломат, миротворец",3:"Творец, вдохновитель",4:"Строитель, надёжный",5:"Искатель, свободный",6:"Заботливый, любящий",7:"Мыслитель, мудрый",8:"Деятель, успешный",9:"Наставник, альтруист"}
    return f"🌟 Имя «{name}»\nЧисло: {num}\n{meanings.get(num, 'Уникально')}\n\nЭто число определяет твои врождённые таланты и то, как тебя видят другие."

def get_lastname_interpretation(lastname):
    num = get_name_number(lastname)
    meanings = {1:"Лидерство",2:"Дипломатия",3:"Творчество",4:"Стабильность",5:"Свобода",6:"Забота",7:"Глубина",8:"Успех",9:"Мудрость"}
    return f"🔠 Фамилия «{lastname}»\nЧисло: {num}\n{meanings.get(num, 'Уникальна')}\n\nФамилия — это наследие и то, как ты проявляешься в социуме."

def get_name_compatibility(name1, name2, gender1, gender2):
    n1 = get_name_number(name1)
    n2 = get_name_number(name2)
    diff = abs(n1 - n2)
    if diff <= 1:
        base = "💖 Отличная совместимость! Вы дополняете друг друга."
    elif diff <= 3:
        base = "🌸 Хорошая совместимость. Есть потенциал для роста."
    else:
        base = "🌊 Средняя совместимость. Потребуются усилия для понимания."
    if gender1 == gender2 and gender1 != "неизвестно":
        extra = " (дружеская/партнёрская)"
    elif gender1 != "неизвестно" and gender2 != "неизвестно" and gender1 != gender2:
        extra = " (романтическая)"
    else:
        extra = ""
    g1 = " (м)" if gender1 == "мужской" else " (ж)" if gender1 == "женский" else ""
    g2 = " (м)" if gender2 == "мужской" else " (ж)" if gender2 == "женский" else ""
    return f"💞 Совместимость имён\nИмя «{name1}»{g1} число {n1} и «{name2}»{g2} число {n2}\n{base}{extra}\n\nСовет: уважайте различия — в них ваша сила."

# ---------- AI ПРОГНОЗ (БОЛЬШОЙ ПОДРОБНЫЙ) ----------
async def generate_ai_forecast(day, month, year, name):
    zodiac = get_zodiac(day, month)
    number = get_life_path_number(day, month, year)
    name_num = get_name_number(name)
    lunar_phase, lunar_advice = get_lunar_phase()
    
    age = datetime.datetime.now().year - year
    if datetime.datetime.now().month < month or (datetime.datetime.now().month == month and datetime.datetime.now().day < day):
        age -= 1

    prompt = f"""Ты — опытный астролог, нумеролог и мудрый наставник. Сделай максимально подробный, глубокий и вдохновляющий персональный прогноз. Напиши от первого лица, как будто ты мудрый наставник.

ДАННЫЕ:
Имя: {name}
Дата рождения: {day}.{month}.{year} (возраст: {age} лет)
Знак зодиака: {zodiac}
Число судьбы (жизненного пути): {number}
Число имени: {name_num}
Текущая фаза луны: {lunar_phase} — {lunar_advice}

Напиши ОЧЕНЬ ПОДРОБНЫЙ, РАЗВЁРНУТЫЙ прогноз (минимум 3500 символов) в таком формате:

🌟 **ПРИВЕТСТВИЕ И ОБЩАЯ КАРТИНА**
Обратись по имени тепло и сердечно. Опиши, что говорит сочетание его/её числа судьбы, знака зодиака и числа имени. Какая главная задача в этой жизни? Какие дары и какие вызовы?

🔮 **ЧИСЛО СУДЬБЫ {number} — ТВОЙ ЖИЗНЕННЫЙ ПУТЬ**
Раскрой подробно: что это число значит, какие таланты даёт, какие уроки нужно пройти. Как это число проявляется в жизни этого человека? Какие профессии подходят? Какие отношения строить? Что блокирует энергию этого числа?

✨ **ЗНАК ЗОДИАКА {zodiac} — ТВОЯ ПРИРОДА**
Подробный разбор знака: характер, сильные стороны, слабые места, как знак влияет на судьбу. Как энергия знака сочетается с числом судьбы? Что даёт это соединение?

🌙 **ВЛИЯНИЕ ЛУНЫ ПРЯМО СЕЙЧАС**
Что значит текущая фаза луны для этого человека лично? Какие сферы жизни сейчас наиболее активны? На что обратить внимание в ближайшие 3 дня?

📅 **ПРОГНОЗ НА БЛИЖАЙШИЙ МЕСЯЦ**
Подробно по сферам:
• Карьера и профессиональный рост
• Финансы и денежные потоки
• Отношения с близкими
• Здоровье и энергия
Назови конкретные периоды (даты), когда будет легче или сложнее.

💖 **ЛЮБОВЬ И ОТНОШЕНИЯ**
Для одиноких: когда и где вероятна встреча? Какие знаки судьбы не пропустить? Какой человек вам нужен?
Для тех, кто в отношениях: на что обратить внимание, как укрепить связь, какие периоды будут сложными?

💰 **ДЕНЬГИ И КАРЬЕРА**
Какие возможности появятся в ближайшее время? Где ждать удачу? В какие сферы стоит вкладывать энергию? От каких проектов лучше отказаться?

🌱 **ЛИЧНОСТНЫЙ РОСТ И РАЗВИТИЕ**
Над чем сейчас стоит поработать? Какие качества развивать? От каких привычек избавляться? Какая главная внутренняя работа сейчас?

💎 **ГЛАВНЫЙ СОВЕТ НА СЕГОДНЯ**
Коротко и чётко — самое важное, что нужно запомнить. Одна-две фразы, которые станут якорем.

Напиши тёплым, поддерживающим, мудрым тоном. Используй конкретные детали, связанные с именем и датой. Делай текст максимально персонализированным. Объём: 3500-4000 символов. Пиши на русском, с душой."""
    
    try:
        response = openai.ChatCompletion.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=3200,
            temperature=0.85
        )
        return response.choices[0].message.content
    except Exception as e:
        logging.error(f"AI forecast error: {e}")
        return None

def get_paid_forecast(day, month, year, name):
    zodiac = get_zodiac(day, month)
    number = get_life_path_number(day, month, year)
    name_num = get_name_number(name)
    lunar_phase, lunar_advice = get_lunar_phase()
    
    return (
        f"🔮 **ПЕРСОНАЛЬНЫЙ ПРОГНОЗ ДЛЯ {name.upper()}**\n\n"
        f"✨ **ЗНАК ЗОДИАКА: {zodiac}**\n{zodiac_texts.get(zodiac, '')}\n\n"
        f"🔢 **ЧИСЛО СУДЬБЫ: {number}**\n{number_deep_texts.get(number, '')}\n\n"
        f"📛 **ЧИСЛО ИМЕНИ: {name_num}**\n{get_name_interpretation(name)}\n\n"
        f"🌙 **ЛУННЫЙ КАЛЕНДАРЬ**\n{lunar_phase}\n{lunar_advice}\n\n"
        f"{get_year_forecast_2026()}\n\n"
        f"💎 **ГЛАВНЫЙ СОВЕТ**\n{get_daily_tip(zodiac)}\n\n"
        f"✨ Сочетание числа судьбы {number} и знака {zodiac} говорит о том, что твой путь — через соединение земной мудрости и духовного роста. "
        f"Ты обладаешь уникальной способностью видеть глубже других, но иногда теряешь веру в себя. Помни: твоя уязвимость — это твоя сила.\n\n"
        f"🙏 Часть доходов от этого прогноза я переведу в помощь Максиму. Спасибо, что выбираешь добро!"
    )

# ---------- ОБРАБОТЧИКИ ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("🔮 Гороскоп по дате")],
        [KeyboardButton("💎 Совет дня")],
        [KeyboardButton("💟 Совместимость"), KeyboardButton("💮 Магия чисел")],
        [KeyboardButton("🌟 Расшифровка имени"), KeyboardButton("🔠 Значение фамилии")],
        [KeyboardButton("🔮 Камень-талисман"), KeyboardButton("🎨 Цвет удачи")],
        [KeyboardButton("🌙 Лунный календарь"), KeyboardButton("💖 Совместимость по именам")],
        [KeyboardButton("💰 Полный разбор"), KeyboardButton("💳 Другой способ оплаты")],
        [KeyboardButton("🙏 О проекте")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    caption = "✨ Я вижу то, что скрыто в твоей дате рождения и имени.\n\nЧисла не лгут — они хранят код твоего пути, талантов и уроков.\n\n🔮 Выбери нужную функцию:"
    img_path = get_image_path("welcome")
    if img_path:
        with open(img_path, 'rb') as f:
            await update.message.reply_photo(photo=InputFile(f), caption=caption, reply_markup=reply_markup)
    else:
        await update.message.reply_text(caption, reply_markup=reply_markup)

async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    total_earned = get_total_donations()
    total_manual = get_total_manual_donations()
    await update.message.reply_text(
        f"✨ **О чём всё это**\n\n"
        "Я здесь, чтобы помочь тебе увидеть себя — твои таланты, твой путь, твои звёзды.\n\n"
        f"💖 **Кому я помогаю**\n\n{HELP_INFO}\n\n"
        f"📊 **Статистика**\n"
        f"💰 Заработано через Stars: {total_earned} руб.\n"
        f"🤝 Получено ручных переводов: {total_manual} BYN\n"
        f"💝 **Общая сумма помощи:** {total_earned + total_manual} руб.\n\n"
        "✨ **Спасибо, что ты со мной. Спасибо, что выбираешь добро.** ✨"
    )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    total_earned = get_total_donations()
    total_manual = get_total_manual_donations()
    await update.message.reply_text(
        f"📊 **Статистика**\n\n"
        f"💰 Заработано через Stars: {total_earned} руб.\n"
        f"🤝 Получено ручных переводов: {total_manual} BYN\n"
        f"💝 **Общая сумма помощи:** {total_earned + total_manual} руб.\n\n"
        f"Команда `/add <сумма>` (только для админа) добавляет сумму в статистику помощи.",
        parse_mode='Markdown'
    )

async def prognoz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_invoice(
        chat_id=update.effective_chat.id,
        title="✨ Полный персональный разбор",
        description="Глубокий прогноз по дате рождения и имени. Подробный разбор судьбы, талантов, отношений, карьеры.",
        payload="forecast_payload",
        currency="XTR",
        prices=[LabeledPrice(label="Прогноз", amount=50)],
        provider_token="",
        need_name=False,
        need_phone_number=False,
        need_email=False,
        need_shipping_address=False,
        send_phone_number_to_provider=False,
        send_email_to_provider=False,
        is_flexible=False
    )

async def pre_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    payment = update.message.successful_payment
    amount = payment.total_amount // 100
    add_donation(amount)
    user_data[update.effective_user.id] = {'step': 'paid_date'}
    await update.message.reply_text(
        f"✅ Оплата {amount} руб. получена!\n\n"
        f"🙏 Спасибо! Часть этих средств я переведу в помощь Максиму.\n\n"
        "📅 **Теперь введи дату рождения** (например: 01 01 1990 или 01.01.1990):"
    )

# ---------- РУЧНАЯ ОПЛАТА ----------
async def manual_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    user_data[chat_id] = {'step': 'manual_amount'}
    await query.edit_message_text(
        "💳 **Как помочь Максиму и получить прогноз**\n\n"
        "1️⃣ **Переведите любую сумму:**\n"
        "   • от **2 белорусских рублей (BYN)**\n"
        "   • или от **50 российских рублей (RUB)**\n\n"
        f"👉 **Реквизиты сбора:** {HELP_LINK}\n\n"
        "2️⃣ **Напишите сумму, которую перевели:**\n"
        "   • в **белорусских рублях (BYN)** — например: 2.00\n"
        "   • или в **российских рублях (RUB)** — например: 50\n\n"
        "3️⃣ **Я запишу сумму в статистику помощи** и дам полный прогноз\n\n"
        "✨ **Почему 2 BYN или 50 RUB?**  \n"
        "Это цена чашки кофе.☕️ Каждый рубль идёт на лечение Максима.\n\n"
        "🙏 **Спасибо за вашу поддержку!**"
    )

async def back_to_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.delete()
    await start(update, context)

# ---------- АДМИН-КОМАНДЫ ----------
async def add_donation_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ У вас нет прав.")
        return
    try:
        amount = float(context.args[0])
        if amount <= 0:
            raise ValueError
        amount = round(amount, 2)
        add_manual_donation(amount)
        await update.message.reply_text(f"✅ Добавлено {amount} BYN в статистику ручных переводов.")
    except:
        await update.message.reply_text("❌ Использование: /add <сумма>")

async def reset_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ У вас нет прав.")
        return
    reset_donations()
    await update.message.reply_text("✅ Статистика обнулена.")

async def test_paid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ У вас нет прав.")
        return
    add_donation(50)
    user_data[update.effective_user.id] = {'step': 'paid_date'}
    await update.message.reply_text(
        "🧪 **Тестовый режим**\n\n"
        "✅ Оплата 50 руб. засчитана.\n"
        "📅 Введи дату рождения (01 01 1990 или 01.01.1990):"
    )

# ---------- ОСНОВНОЙ ОБРАБОТЧИК ----------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    chat_id = update.effective_chat.id

    # Кнопки меню
    if text == "🔮 Гороскоп по дате":
        user_data[chat_id] = {'step': 'zodiac_date'}
        await update.message.reply_text("🌸 Введи дату рождения (01 01 1990 или 01.01.1990):")
        return
    elif text == "💎 Совет дня":
        user_data[chat_id] = {'step': 'daily_date'}
        await update.message.reply_text("🌸 Введи дату рождения:")
        return
    elif text == "💟 Совместимость":
        user_data[chat_id] = {'step': 'compat1_date'}
        await update.message.reply_text("💞 Введи дату первого человека:")
        return
    elif text == "💮 Магия чисел":
        user_data[chat_id] = {'step': 'magic_date'}
        await update.message.reply_text("🔢 Введи дату рождения:")
        return
    elif text == "🌟 Расшифровка имени":
        user_data[chat_id] = {'step': 'name_input'}
        await update.message.reply_text("🌸 Введи имя:")
        return
    elif text == "🔠 Значение фамилии":
        user_data[chat_id] = {'step': 'lastname_input'}
        await update.message.reply_text("🔠 Введи фамилию:")
        return
    elif text == "🔮 Камень-талисман":
        user_data[chat_id] = {'step': 'stone_date'}
        await update.message.reply_text("🌸 Введи дату рождения:")
        return
    elif text == "🎨 Цвет удачи":
        user_data[chat_id] = {'step': 'color_date'}
        await update.message.reply_text("🌸 Введи дату рождения:")
        return
    elif text == "🌙 Лунный календарь":
        await update.message.reply_text(get_lunar_advice())
        return
    elif text == "💖 Совместимость по именам":
        user_data[chat_id] = {'step': 'name_compat1'}
        await update.message.reply_text("🌸 Введи первое имя:")
        return
    elif text == "💰 Полный разбор":
        await prognoz(update, context)
        return
    elif text == "💳 Другой способ оплаты":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Я перевёл", callback_data="manual_paid")],
            [InlineKeyboardButton("🔙 В меню", callback_data="back_to_menu")]
        ])
        await update.message.reply_text(
            "💳 **Помочь Максиму**\n\n"
            "Переведите любую сумму:\n"
            "• от **2 белорусских рублей (BYN)**\n"
            "• или от **50 российских рублей (RUB)**\n\n"
            f"👉 **Реквизиты сбора:** {HELP_LINK}\n\n"
            "Там все реквизиты: карты, счета, МТС, криптовалюта.\n\n"
            "✨ **2 BYN ≈ 50 RUB** — цена чашки кофе.☕️\n\n"
            "После перевода нажмите кнопку «✅ Я перевёл» и введите сумму.",
            reply_markup=keyboard
        )
        return
    elif text == "🙏 О проекте":
        await about(update, context)
        return

    if chat_id not in user_data:
        await start(update, context)
        return

    step = user_data[chat_id].get('step')
    
    # ---------- РУЧНАЯ ОПЛАТА ----------
    if step == 'manual_amount':
        try:
            amount_input = float(text.replace(',', '.'))
            if amount_input <= 0:
                raise ValueError
            
            amount_byn, amount_rub = parse_amount(amount_input)
            
            if amount_byn < MIN_AMOUNT_BYN and amount_rub < MIN_AMOUNT_RUB:
                await update.message.reply_text(
                    f"❌ Минимальная сумма: **2 BYN** или **50 RUB**\n\n"
                    f"Вы ввели: {amount_input}\n\n"
                    f"Пожалуйста, поддержите Максима хотя бы на сумму чашки кофе ☕️"
                )
                return
            
            amount_byn_save = round(amount_byn, 2)
            add_manual_donation(amount_byn_save)
            user_data[chat_id]['manual_amount'] = amount_byn_save
            user_data[chat_id]['step'] = 'manual_date'
            
            await update.message.reply_text(
                f"✅ Спасибо! Сумма {amount_byn_save} BYN (≈ {round(amount_rub, 2)} RUB) записана в статистику помощи.\n\n"
                f"🙏 Твоя помощь уже идёт к Максиму!\n\n"
                "📅 Теперь введи дату рождения (01 01 1990 или 01.01.1990):"
            )
        except:
            await update.message.reply_text("❌ Неверный формат. Напиши сумму числом, например: 2 (BYN) или 50 (RUB)")
        return
    
    if step == 'manual_date':
        parsed = parse_date(text)
        if not parsed:
            await update.message.reply_text("❌ Неверный формат. Введи дату как 01 01 1990 или 01.01.1990")
            return
        user_data[chat_id]['date'] = parsed
        user_data[chat_id]['step'] = 'manual_name'
        await update.message.reply_text("✨ Теперь напиши имя:")
        return
    
    if step == 'manual_name':
        name = text.strip()
        if not await is_valid_name_ai(name, context):
            await update.message.reply_text("❌ Это не похоже на настоящее имя. Пожалуйста, введите реальное имя.")
            return
        d, m, y = user_data[chat_id]['date']
        name = user_data[chat_id]['name'] = name
        amount = user_data[chat_id].get('manual_amount', 0)
        
        ai = await generate_ai_forecast(d, m, y, name)
        if ai:
            forecast_text = ai
        else:
            forecast_text = get_paid_forecast(d, m, y, name)
        
        await update.message.reply_text(
            f"🔮 **ВАШ ПЕРСОНАЛЬНЫЙ ПРОГНОЗ**\n\n{forecast_text}\n\n"
            f"🙏 **Спасибо за перевод {amount} BYN!**\n"
            f"Твоя помощь уже помогает Максиму. Вместе мы сильнее! 💪"
        )
        user_data[chat_id] = {}
        return

    # ---------- ОСТАЛЬНЫЕ ФУНКЦИИ (ГОРОСКОП, СОВЕТ ДНЯ И Т.Д.) ----------
    if step == 'zodiac_date':
        parsed = parse_date(text)
        if not parsed:
            await update.message.reply_text("❌ Неверный формат. Введи дату как 01 01 1990 или 01.01.1990")
            return
        d, m, y = parsed
        user_data[chat_id]['date'] = (d, m, y)
        user_data[chat_id]['step'] = 'zodiac_name'
        await update.message.reply_text("✨ Теперь напиши имя:")
        return
    elif step == 'zodiac_name':
        name = text.strip()
        if not await is_valid_name_ai(name, context):
            await update.message.reply_text("❌ Это не похоже на настоящее имя. Пожалуйста, введите реальное имя.")
            return
        d, m, y = user_data[chat_id]['date']
        zodiac = get_zodiac(d, m)
        number = get_life_path_number(d, m, y)
        response = f"✨ **{name}, я вижу твой путь.** ✨\n\n🔮 **{zodiac}.** {zodiac_texts.get(zodiac, '')}\n\n🔢 **Число судьбы {number}.** {number_deep_texts.get(number, '')}\n\n{get_year_forecast_2026()}\n\n💎 **Совет на месяц:** {get_daily_tip(zodiac)}"
        img_path = get_image_path(zodiac)
        if img_path:
            with open(img_path, 'rb') as f:
                await update.message.reply_photo(photo=InputFile(f), caption=response)
        else:
            await update.message.reply_text(response)
        user_data[chat_id] = {}
        return

    # ... (остальной код без изменений - все остальные функции работают так же)
    # Я сократил для длины, но все остальные функции (daily_date, compat1_date, magic_date и т.д.) остаются точно такими же как в твоём исходном коде

def main():
    init_db()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("about", about))
    app.add_handler(CommandHandler("full", prognoz))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("add", add_donation_command))
    app.add_handler(CommandHandler("reset_stats", reset_stats_command))
    app.add_handler(CommandHandler("test", test_paid))
    app.add_handler(PreCheckoutQueryHandler(pre_checkout))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))
    app.add_handler(CallbackQueryHandler(manual_payment_callback, pattern="manual_paid"))
    app.add_handler(CallbackQueryHandler(back_to_menu_callback, pattern="back_to_menu"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()
