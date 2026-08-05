"""
Лумена v6.1 — Собственный ИИ (без внешних LLM)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• DuckDuckGo HTML-скрапинг — настоящие результаты поиска
• Wikipedia multi-lang с умной экстракцией фактов
• Живая личность: юмор, мнения, эмоции, вопросы
• Память разговора + интересы пользователя
• Погода, курсы, калькулятор, перевод
• Стихи, истории, советы
• Сленг и тренды — понимает и отвечает на сленге
• Комплименты — по запросу и спонтанно
• 0 внешних AI API
"""

import asyncio
import math
import random
import re
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import aiohttp
import nlu
from lumena_kb import EXTRA_PATTERNS, FACTS_DB, lookup_topic  # noqa: F401

KYIV_TZ = ZoneInfo("Europe/Kyiv")

# ══════════════════════════════════════════════════════════
# ПАМЯТЬ
# ══════════════════════════════════════════════════════════
_users: dict[int, dict] = {}


def ctx(uid: int) -> dict:
    if uid not in _users:
        _users[uid] = {
            "history":   [],      # [(role, text), ...]
            "name":      None,
            "interests": [],
            "last_topic": None,
            "mood":      "normal",
            "msg_count": 0,
            "last_ts":   0.0,
        }
    return _users[uid]


def add_history(uid: int, role: str, text: str):
    c = ctx(uid)
    c["history"].append((role, text[:600]))
    if len(c["history"]) > 24:
        c["history"].pop(0)
    if role == "user":
        c["msg_count"] += 1
        c["last_ts"] = time.monotonic()


def last_bot_said(uid: int) -> str:
    for role, text in reversed(ctx(uid)["history"]):
        if role == "bot":
            return text
    return ""


# ══════════════════════════════════════════════════════════
# DETECT LANGUAGE
# ══════════════════════════════════════════════════════════
def detect_lang(text: str) -> str:
    if re.search(r"[іїєґ]", text):
        return "uk"
    if re.search(r"[а-яёА-ЯЁ]", text):
        return "ru"
    if re.search(r"[a-zA-Z]", text):
        return "en"
    return "ru"


WIKI_LANG = {"ru": "ru", "uk": "uk", "en": "en", "de": "de",
             "es": "es", "fr": "fr", "pl": "pl"}

# ══════════════════════════════════════════════════════════
# ИНСТРУМЕНТЫ
# ══════════════════════════════════════════════════════════

# ── DuckDuckGo HTML scraping (реальные результаты) ───────
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
}


async def ddg_scrape(query: str) -> list[str]:
    """Скрапит реальные сниппеты из DuckDuckGo (не урезанный API)."""
    try:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=10),
            headers=_HEADERS,
        ) as s:
            async with s.post(
                "https://html.duckduckgo.com/html/",
                data={"q": query, "kl": "ru-ru"},
            ) as r:
                if r.status != 200:
                    return []
                html = await r.text(encoding="utf-8", errors="ignore")

        # Извлекаем сниппеты
        raw = re.findall(
            r'class=["\']result__snippet["\'][^>]*>(.*?)</(?:a|span)>',
            html, re.DOTALL | re.IGNORECASE,
        )
        # Заголовки результатов
        titles = re.findall(
            r'class=["\']result__a["\'][^>]*>(.*?)</a>',
            html, re.DOTALL | re.IGNORECASE,
        )

        snippets = []
        for raw_s in raw[:6]:
            clean = re.sub(r"<[^>]+>", "", raw_s)
            clean = re.sub(r"\s+", " ", clean).strip()
            clean = clean.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&#39;", "'")
            if len(clean) > 40:
                snippets.append(clean[:400])

        return snippets
    except Exception:
        return []


async def ddg_instant(query: str) -> str:
    """DuckDuckGo Instant Answers API — быстрые фактические ответы."""
    try:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=7), headers=_HEADERS
        ) as s:
            params = {"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"}
            async with s.get("https://api.duckduckgo.com/", params=params) as r:
                if r.status != 200:
                    return ""
                d = await r.json(content_type=None)

        for field in ("AbstractText", "Answer", "Definition"):
            val = (d.get(field) or "").strip()
            if val and len(val) > 40:
                return val[:700]

        for t in d.get("RelatedTopics", [])[:3]:
            if isinstance(t, dict):
                val = (t.get("Text") or "").strip()
                if val and len(val) > 50:
                    return val[:400]
    except Exception:
        pass
    return ""


# ── Wikipedia ─────────────────────────────────────────────
async def wiki_search(query: str, lang: str = "ru") -> dict | None:
    """Ищет статью в Wikipedia, возвращает dict с title/extract/url."""
    wl = WIKI_LANG.get(lang, "ru")
    for wiki_lang in ([wl, "ru"] if wl != "ru" else ["ru", "en"]):
        try:
            # Поиск
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=8)) as s:
                params = {
                    "action": "query", "list": "search",
                    "srsearch": query, "format": "json",
                    "srlimit": 3, "utf8": "1",
                }
                async with s.get(
                    f"https://{wiki_lang}.wikipedia.org/w/api.php",
                    params=params,
                ) as r:
                    if r.status != 200:
                        continue
                    results = (await r.json()).get("query", {}).get("search", [])
            if not results:
                continue

            title = results[0]["title"]
            encoded = aiohttp.helpers.quote(title, safe="")

            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=7)) as s:
                async with s.get(
                    f"https://{wiki_lang}.wikipedia.org/api/rest_v1/page/summary/{encoded}"
                ) as r:
                    if r.status != 200:
                        continue
                    d = await r.json()

            extract = (d.get("extract") or "").strip()
            if len(extract) < 60:
                continue
            bad = ("может означать", "disambiguation", "многозначность", "refers to multiple")
            if any(b in extract[:150].lower() for b in bad):
                if len(results) > 1:
                    title = results[1]["title"]
                    encoded = aiohttp.helpers.quote(title, safe="")
                    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=7)) as s:
                        async with s.get(
                            f"https://{wiki_lang}.wikipedia.org/api/rest_v1/page/summary/{encoded}"
                        ) as r:
                            if r.status != 200:
                                continue
                            d = await r.json()
                    extract = (d.get("extract") or "").strip()
                    if len(extract) < 60:
                        continue
                else:
                    continue

            return {
                "title":   d.get("title", title),
                "extract": extract,
                "url":     d.get("content_urls", {}).get("mobile", {}).get("page", ""),
                "lang":    wiki_lang,
            }
        except Exception:
            continue
    return None


def clean_text(text: str) -> str:
    """Чистит HTML-сущности, цитатные метки и лишние пробелы."""
    text = re.sub(r"\[[\d,\s]+\]", "", text)           # [7][8] → удалить
    text = re.sub(r"\[…\]", "...", text)
    text = text.replace("&#x27;", "'").replace("&#39;", "'")
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&quot;", '"').replace("&nbsp;", " ")
    text = re.sub(r"МФА:\s*\[.*?\]\s*", "", text)       # МФА: [ˈiːlɒn ˈmʌsk] → удалить
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


def extract_sentences(text: str, n: int = 4) -> str:
    """Берёт первые n предложений из текста."""
    text = clean_text(text)
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return " ".join(sentences[:n])


# ── Погода ────────────────────────────────────────────────
_CITY_ENDINGS = re.compile(
    r"(е|и|у|ю|ой|ей|ом|ем|ах|ях|ой|е)$", re.IGNORECASE
)

# Полная база городов: все варианты написания → English для wttr.in
_CITIES_KNOWN: dict[str, str] = {
    # ════ УКРАИНА — все крупные города ════
    # Київ / Киев
    "київ": "Kyiv,Ukraine",
    "киев": "Kyiv,Ukraine",
    "киева": "Kyiv,Ukraine",
    "киеве": "Kyiv,Ukraine",
    "києва": "Kyiv,Ukraine",
    "києві": "Kyiv,Ukraine",

    # Харків / Харьков
    "харків": "Kharkiv,Ukraine",
    "харьков": "Kharkiv,Ukraine",
    "харькова": "Kharkiv,Ukraine",
    "харькове": "Kharkiv,Ukraine",
    "харкова": "Kharkiv,Ukraine",
    "харкові": "Kharkiv,Ukraine",

    # Дніпро / Днепр
    "дніпро": "Dnipro,Ukraine",
    "дніпр": "Dnipro,Ukraine",
    "днепр": "Dnipro,Ukraine",
    "днипро": "Dnipro,Ukraine",
    "дніпропетровськ": "Dnipro,Ukraine",
    "днепропетровск": "Dnipro,Ukraine",
    "дніпропетровська": "Dnipro,Ukraine",

    # Одеса / Одесса
    "одеса": "Odessa,Ukraine",
    "одесса": "Odessa,Ukraine",
    "одеси": "Odessa,Ukraine",
    "одессы": "Odessa,Ukraine",
    "одессе": "Odessa,Ukraine",
    "одесі": "Odessa,Ukraine",

    # Запоріжжя / Запорожье
    "запоріжжя": "Zaporizhzhia,Ukraine",
    "запорожье": "Zaporizhzhia,Ukraine",
    "запорожья": "Zaporizhzhia,Ukraine",
    "запоріжжі": "Zaporizhzhia,Ukraine",

    # Львів / Львов
    "львів": "Lviv,Ukraine",
    "львов": "Lviv,Ukraine",
    "львова": "Lviv,Ukraine",
    "львові": "Lviv,Ukraine",
    "льова": "Lviv,Ukraine",

    # Миколаїв / Николаев
    "миколаїв": "Mykolaiv,Ukraine",
    "николаев": "Mykolaiv,Ukraine",
    "миколаєва": "Mykolaiv,Ukraine",
    "николаева": "Mykolaiv,Ukraine",

    # Херсон
    "херсон": "Kherson,Ukraine",
    "херсона": "Kherson,Ukraine",
    "херсоні": "Kherson,Ukraine",

    # Полтава
    "полтава": "Poltava,Ukraine",
    "полтави": "Poltava,Ukraine",
    "полтаві": "Poltava,Ukraine",

    # Чернігів / Чернигов
    "чернігів": "Chernihiv,Ukraine",
    "чернигов": "Chernihiv,Ukraine",
    "чернігова": "Chernihiv,Ukraine",
    "чернигова": "Chernihiv,Ukraine",

    # Черкаси / Черкассы
    "черкаси": "Cherkasy,Ukraine",
    "черкассы": "Cherkasy,Ukraine",
    "черкасах": "Cherkasy,Ukraine",
    "черкасах": "Cherkasy,Ukraine",

    # Вінниця / Винница
    "вінниця": "Vinnytsia,Ukraine",
    "винница": "Vinnytsia,Ukraine",
    "вінниці": "Vinnytsia,Ukraine",
    "виннице": "Vinnytsia,Ukraine",

    # Житомир
    "житомир": "Zhytomyr,Ukraine",
    "житомира": "Zhytomyr,Ukraine",
    "житомирі": "Zhytomyr,Ukraine",

    # Рівне / Ровно
    "рівне": "Rivne,Ukraine",
    "ровно": "Rivne,Ukraine",
    "рівного": "Rivne,Ukraine",

    # Луцьк / Луцк
    "луцьк": "Lutsk,Ukraine",
    "луцк": "Lutsk,Ukraine",
    "луцька": "Lutsk,Ukraine",

    # Івано-Франківськ / Ивано-Франковск
    "івано-франківськ": "Ivano-Frankivsk,Ukraine",
    "ивано-франковск": "Ivano-Frankivsk,Ukraine",
    "франківськ": "Ivano-Frankivsk,Ukraine",
    "ивано франковск": "Ivano-Frankivsk,Ukraine",
    "івано франківськ": "Ivano-Frankivsk,Ukraine",

    # Тернопіль / Тернополь
    "тернопіль": "Ternopil,Ukraine",
    "тернополь": "Ternopil,Ukraine",
    "тернополя": "Ternopil,Ukraine",

    # Хмельницький / Хмельницкий
    "хмельницький": "Khmelnytskyi,Ukraine",
    "хмельницкий": "Khmelnytskyi,Ukraine",
    "хмельницька": "Khmelnytskyi,Ukraine",

    # Ужгород
    "ужгород": "Uzhhorod,Ukraine",
    "ужгорода": "Uzhhorod,Ukraine",

    # Сумы / Суми
    "суми": "Sumy,Ukraine",
    "сумы": "Sumy,Ukraine",
    "сумах": "Sumy,Ukraine",

    # Кропивницький / Кіровоград
    "кропивницький": "Kropyvnytskyi,Ukraine",
    "кропивницкий": "Kropyvnytskyi,Ukraine",
    "кіровоград": "Kropyvnytskyi,Ukraine",
    "кировоград": "Kropyvnytskyi,Ukraine",

    # Кривий Ріг / Кривой Рог
    "кривий ріг": "Kryvyi Rih,Ukraine",
    "кривой рог": "Kryvyi Rih,Ukraine",
    "кривого рогу": "Kryvyi Rih,Ukraine",
    "кривом роге": "Kryvyi Rih,Ukraine",

    # Маріуполь / Мариуполь
    "маріуполь": "Mariupol,Ukraine",
    "мариуполь": "Mariupol,Ukraine",
    "маріуполя": "Mariupol,Ukraine",

    # Краматорськ / Краматорск
    "краматорськ": "Kramatorsk,Ukraine",
    "краматорск": "Kramatorsk,Ukraine",

    # Мелітополь / Мелитополь
    "мелітополь": "Melitopol,Ukraine",
    "мелитополь": "Melitopol,Ukraine",

    # Нікополь / Никополь
    "нікополь": "Nikopol,Ukraine",
    "никополь": "Nikopol,Ukraine",

    # Бердянськ / Бердянск
    "бердянськ": "Berdiansk,Ukraine",
    "бердянск": "Berdiansk,Ukraine",

    # Чернівці / Черновцы
    "чернівці": "Chernivtsi,Ukraine",
    "черновцы": "Chernivtsi,Ukraine",
    "чернівцях": "Chernivtsi,Ukraine",

    # Кременчук / Кременчуг
    "кременчук": "Kremenchuk,Ukraine",
    "кременчуг": "Kremenchuk,Ukraine",

    # Дрогобич
    "дрогобич": "Drohobych,Ukraine",

    # Ізмаїл / Измаил
    "ізмаїл": "Izmail,Ukraine",
    "измаил": "Izmail,Ukraine",

    # Білгород-Дністровський
    "білгород-дністровський": "Bilhorod-Dnistrovskyi,Ukraine",
    "белгород-днестровский": "Bilhorod-Dnistrovskyi,Ukraine",

    # Умань
    "умань": "Uman,Ukraine",
    "умани": "Uman,Ukraine",

    # Прилуки
    "прилуки": "Pryluky,Ukraine",

    # Конотоп
    "конотоп": "Konotop,Ukraine",

    # Ніжин / Нежин
    "ніжин": "Nizhyn,Ukraine",
    "нежин": "Nizhyn,Ukraine",

    # Шостка
    "шостка": "Shostka,Ukraine",

    # Бориспіль / Борисполь
    "бориспіль": "Boryspil,Ukraine",
    "борисполь": "Boryspil,Ukraine",

    # Біла Церква / Белая Церковь
    "біла церква": "Bila Tserkva,Ukraine",
    "белая церковь": "Bila Tserkva,Ukraine",

    # Фастів / Фастов
    "фастів": "Fastiv,Ukraine",
    "фастов": "Fastiv,Ukraine",

    # Обухів / Обухов
    "обухів": "Obukhiv,Ukraine",
    "обухов": "Obukhiv,Ukraine",

    # Бровари
    "бровари": "Brovary,Ukraine",
    "броварах": "Brovary,Ukraine",

    # Ірпінь / Ирпень
    "ірпінь": "Irpin,Ukraine",
    "ирпень": "Irpin,Ukraine",

    # Буча
    "буча": "Bucha,Ukraine",

    # Тростянець
    "тростянець": "Trostyanets,Ukraine",

    # Первомайськ / Первомайск
    "первомайськ": "Pervomaysk,Ukraine",
    "первомайск": "Pervomaysk,Ukraine",

    # Горлівка / Горловка
    "горлівка": "Horlivka,Ukraine",
    "горловка": "Horlivka,Ukraine",

    # Слов'янськ / Славянск
    "слов'янськ": "Sloviansk,Ukraine",
    "славянск": "Sloviansk,Ukraine",

    # ════ МІЖНАРОДНІ МІСТА ════
    "москве": "Moscow,Russia",
    "москва": "Moscow,Russia",
    "москвы": "Moscow,Russia",
    "минске": "Minsk,Belarus",
    "минск": "Minsk,Belarus",
    "минска": "Minsk,Belarus",
    "берлин": "Berlin,Germany",
    "берлине": "Berlin,Germany",
    "берлина": "Berlin,Germany",
    "лондон": "London,UK",
    "лондоне": "London,UK",
    "лондона": "London,UK",
    "париж": "Paris,France",
    "париже": "Paris,France",
    "парижа": "Paris,France",
    "варшава": "Warsaw,Poland",
    "варшаве": "Warsaw,Poland",
    "варшавы": "Warsaw,Poland",
    "прага": "Prague,Czech Republic",
    "праге": "Prague,Czech Republic",
    "праги": "Prague,Czech Republic",
    "рим": "Rome,Italy",
    "риме": "Rome,Italy",
    "рима": "Rome,Italy",
    "афины": "Athens,Greece",
    "афинах": "Athens,Greece",
    "нью-йорк": "New York,USA",
    "нью йорк": "New York,USA",
    "нью-йорке": "New York,USA",
    "нью йорке": "New York,USA",
    "токио": "Tokyo,Japan",
    "токиё": "Tokyo,Japan",
    "пекин": "Beijing,China",
    "пекине": "Beijing,China",
    "дубай": "Dubai,UAE",
    "дубае": "Dubai,UAE",
    "стамбул": "Istanbul,Turkey",
    "стамбуле": "Istanbul,Turkey",
    "амстердам": "Amsterdam,Netherlands",
    "амстердаме": "Amsterdam,Netherlands",
    "барселона": "Barcelona,Spain",
    "барселоне": "Barcelona,Spain",
    "мадрид": "Madrid,Spain",
    "мадриде": "Madrid,Spain",
    "вена": "Vienna,Austria",
    "вене": "Vienna,Austria",
    "будапешт": "Budapest,Hungary",
    "будапеште": "Budapest,Hungary",
    "бухарест": "Bucharest,Romania",
    "бухаресте": "Bucharest,Romania",
    "брюссель": "Brussels,Belgium",
    "брюсселе": "Brussels,Belgium",
    "осло": "Oslo,Norway",
    "стокгольм": "Stockholm,Sweden",
    "стокгольме": "Stockholm,Sweden",
    "копенгаген": "Copenhagen,Denmark",
    "копенгагене": "Copenhagen,Denmark",
    "хельсинки": "Helsinki,Finland",
    "рига": "Riga,Latvia",
    "риге": "Riga,Latvia",
    "таллин": "Tallinn,Estonia",
    "таллине": "Tallinn,Estonia",
    "вильнюс": "Vilnius,Lithuania",
    "вильнюсе": "Vilnius,Lithuania",
    "анкара": "Ankara,Turkey",
    "анкаре": "Ankara,Turkey",
    "тель-авив": "Tel Aviv,Israel",
    "тель авив": "Tel Aviv,Israel",
    "каир": "Cairo,Egypt",
    "каире": "Cairo,Egypt",
    "бангкок": "Bangkok,Thailand",
    "бангкоке": "Bangkok,Thailand",
    "сингапур": "Singapore",
    "сингапуре": "Singapore",
    "сеул": "Seoul,South Korea",
    "сеуле": "Seoul,South Korea",
    "нью-дели": "New Delhi,India",
    "нью дели": "New Delhi,India",
    "мумбаи": "Mumbai,India",
    "лос-анджелес": "Los Angeles,USA",
    "лос анджелес": "Los Angeles,USA",
    "чикаго": "Chicago,USA",
    "майами": "Miami,USA",
    "торонто": "Toronto,Canada",
    "ванкувер": "Vancouver,Canada",
    "сидней": "Sydney,Australia",
    "сиднее": "Sydney,Australia",
    "мельбурн": "Melbourne,Australia",
}


def normalize_city(city: str) -> str:
    """Нормализует название города: варианты → English для wttr.in."""
    cl = city.strip().lower().rstrip(".,!? ")
    if cl in _CITIES_KNOWN:
        return _CITIES_KNOWN[cl]
    # Пробуем убрать падежное окончание (для неизвестных городов)
    stripped = _CITY_ENDINGS.sub("", cl)
    if stripped and stripped in _CITIES_KNOWN:
        return _CITIES_KNOWN[stripped]
    return city.strip()


def _weather_emoji(desc: str, temp: int) -> str:
    d = desc.lower()
    if any(w in d for w in ("гроза", "thunder", "storm")):     return "⛈"
    if any(w in d for w in ("ливень", "downpour")):             return "🌧"
    if any(w in d for w in ("дождь", "моросящий", "rain", "drizzle")): return "🌦"
    if any(w in d for w in ("снег", "метель", "snow", "blizzard")): return "❄️"
    if any(w in d for w in ("туман", "fog", "mist")):           return "🌫"
    if any(w in d for w in ("пасмурно", "overcast")):           return "☁️"
    if any(w in d for w in ("облач", "cloud")):                 return "⛅"
    if any(w in d for w in ("ясн", "солн", "clear", "sunny")):
        return "🌤" if temp < 20 else "☀️"
    return "🌤"


def _weather_comment(desc: str, temp: int, feels: int, wind: int, humidity: int) -> str:
    """Живой AI-комментарий к погоде."""
    d = desc.lower()
    if any(w in d for w in ("гроза", "thunder")):
        return "⚡ Гроза! Лучше остаться дома — или хотя бы с зонтиком."
    if any(w in d for w in ("ливень", "дождь сильный", "heavy rain")):
        return "🌧 Сильный дождь. Зонт — обязательно, настроение — опционально."
    if any(w in d for w in ("дождь", "моросящий", "rain", "drizzle")):
        return "🌂 Небольшой дождь — зонтик не помешает."
    if any(w in d for w in ("снег", "snow")):
        return "❄️ Снег! Одевайся теплее."
    if any(w in d for w in ("туман", "fog")):
        return "🌫 Туман — аккуратно на дороге."
    if temp >= 35:
        return "🥵 Жара! Пейте воду, прячьтесь в тень и берегите себя."
    if temp >= 28:
        return "😎 Жарко — лёгкая одежда и побольше воды."
    if feels >= 25 and humidity >= 75:
        return "💦 Душновато — влажность высокая, но терпимо."
    if temp >= 20:
        return "✨ Отличная погода — можно гулять без лишних слоёв."
    if temp >= 13:
        return "🧥 Прохладно — лёгкая куртка не помешает."
    if temp >= 5:
        return "🧤 Холодновато — одевайся потеплее."
    return "🥶 Морозно! Не выходи без тёплой одежды."


def _fc_emoji(min_t: int, max_t: int, desc: str) -> str:
    d = desc.lower() if desc else ""
    if any(w in d for w in ("гроза", "thunder")):   return "⛈"
    if any(w in d for w in ("дождь", "rain")):       return "🌧"
    if any(w in d for w in ("снег", "snow")):        return "❄️"
    if any(w in d for w in ("облач", "cloud")):      return "⛅"
    if max_t >= 30:                                   return "☀️"
    return "🌤"


async def get_weather(city: str) -> str | None:
    # Сохраняем оригинальное название для отображения
    original_city = " ".join(w.capitalize() for w in city.strip().split())
    wttr_city = normalize_city(city) or "Kyiv,Ukraine"

    try:
        url = (f"https://wttr.in/{aiohttp.helpers.quote(wttr_city, safe='')}"
               f"?format=j1&lang=ru")
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=8)) as s:
            async with s.get(url) as r:
                if r.status != 200:
                    return None
                d = await r.json(content_type=None)

        cur      = d["current_condition"][0]
        temp     = int(cur["temp_C"])
        feels    = int(cur["FeelsLikeC"])
        humidity = int(cur["humidity"])
        wind     = int(cur["windspeedKmph"])
        desc_ru  = cur.get("lang_ru") or cur.get("weatherDesc", [{}])
        desc     = (desc_ru[0].get("value", "") if desc_ru else "")
        desc_en  = cur.get("weatherDesc", [{}])[0].get("value", "")

        main_emoji = _weather_emoji(desc or desc_en, temp)
        comment    = _weather_comment(desc or desc_en, temp, feels, wind, humidity)

        # Разница ощущаемой и реальной
        diff = feels - temp
        feels_note = ""
        if diff <= -3:
            feels_note = f" _(-{abs(diff)}° из-за ветра)_"
        elif diff >= 3:
            feels_note = f" _(+{diff}° влажность)_"

        # Ветер словами
        if wind < 10:   wind_word = "штиль"
        elif wind < 25: wind_word = "лёгкий"
        elif wind < 45: wind_word = "умеренный"
        elif wind < 65: wind_word = "сильный"
        else:           wind_word = "очень сильный"

        # Прогноз на 3 дня
        forecast = d.get("weather", [])[:3]
        months   = ["янв","фев","мар","апр","май","июн",
                    "июл","авг","сен","окт","ноя","дек"]
        day_names = ["Пн","Вт","Ср","Чт","Пт","Сб","Вс"]
        fc_lines  = ""
        for i, f in enumerate(forecast):
            ds = f.get("date", "")
            fc_desc = ""
            hd = f.get("hourly", [])
            if hd:
                rd = hd[len(hd)//2].get("lang_ru") or hd[len(hd)//2].get("weatherDesc", [{}])
                fc_desc = rd[0].get("value", "") if rd else ""
            mn, mx = int(f.get("mintempC", 0)), int(f.get("maxtempC", 0))
            fe = _fc_emoji(mn, mx, fc_desc)
            try:
                p  = ds.split("-")
                from datetime import date
                day_dt = date(int(p[0]), int(p[1]), int(p[2]))
                dn = "Сегодня" if i == 0 else ("Завтра" if i == 1 else
                     day_names[day_dt.weekday()])
                dl = f"{dn}, {p[2]} {months[int(p[1])-1]}"
            except Exception:
                dl = ds
            fc_lines += f"\n  {fe} {dl}: {mn}°…{mx}°C"

        return (
            f"{main_emoji} *Погода — {original_city}*\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🌡 *{temp}°C*  •  ощущается {feels}°C{feels_note}\n"
            f"💧 Влажность: {humidity}%\n"
            f"💨 Ветер: {wind_word}, {wind} км/ч\n"
            f"{'☁️' if desc else '🌤'} {desc or desc_en}\n\n"
            f"{comment}\n"
            f"\n📅 *Прогноз:*{fc_lines}"
        )
    except Exception:
        return None


# ── Курсы валют ───────────────────────────────────────────
CURRENCIES = {
    "рубль": "RUB", "рублей": "RUB", "руб": "RUB", "₽": "RUB", "rub": "RUB",
    "доллар": "USD", "долл": "USD", "бакс": "USD", "$": "USD", "usd": "USD",
    "евро": "EUR", "eur": "EUR", "€": "EUR",
    "гривна": "UAH", "гривен": "UAH", "грн": "UAH", "uah": "UAH",
    "юань": "CNY", "cny": "CNY", "фунт": "GBP", "gbp": "GBP", "£": "GBP",
    "иена": "JPY", "jpy": "JPY", "тенге": "KZT", "kzt": "KZT",
    "лира": "TRY", "try": "TRY", "злотый": "PLN", "pln": "PLN",
    "франк": "CHF", "chf": "CHF", "cad": "CAD", "aud": "AUD",
    "бел": "BYN", "byn": "BYN", "дирхам": "AED", "aed": "AED",
}
CURRENCY_RE = re.compile(
    r"(\d[\d\s,\.]*)\s*([а-яёА-ЯЁa-zA-Z$€£¥₽]{2,10}(?:\s+[а-яёА-ЯЁ]+)?)"
    r"\s*(?:в|to|in|=|→|по курсу)\s*([а-яёА-ЯЁa-zA-Z$€£¥₽]{2,10}(?:\s+[а-яёА-ЯЁ]+)?)",
    re.IGNORECASE,
)


def _resolve_cur(s: str) -> str | None:
    s = s.strip().lower()
    if s.upper() in CURRENCIES.values():
        return s.upper()
    for k, v in CURRENCIES.items():
        if k in s:
            return v
    return None


async def convert_currency(amount: float, frm: str, to: str) -> str | None:
    try:
        url = f"https://api.frankfurter.app/latest?amount={amount}&from={frm}&to={to}"
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=6)) as s:
            async with s.get(url) as r:
                if r.status != 200:
                    return None
                d = await r.json()
        res = d.get("rates", {}).get(to)
        return f"💱 {amount:g} {frm} = *{res:,.2f} {to}*" if res else None
    except Exception:
        return None


async def get_rates(base: str = "USD") -> str | None:
    try:
        url = f"https://api.frankfurter.app/latest?from={base}&to=EUR,UAH,RUB,GBP,CNY,BYN,KZT,TRY,PLN"
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=6)) as s:
            async with s.get(url) as r:
                if r.status != 200:
                    return None
                d = await r.json()
        rates = d.get("rates", {})
        names = {
            "EUR": "🇪🇺 Евро", "UAH": "🇺🇦 Гривна", "RUB": "🇷🇺 Рубль",
            "GBP": "🇬🇧 Фунт", "CNY": "🇨🇳 Юань", "BYN": "🇧🇾 Бел.рубль",
            "KZT": "🇰🇿 Тенге", "TRY": "🇹🇷 Лира", "PLN": "🇵🇱 Злотый",
        }
        lines = [f"💱 *Курсы к {base} на сегодня:*"]
        for code, name in names.items():
            if code in rates:
                lines.append(f"  {name}: `{rates[code]:,.2f}`")
        return "\n".join(lines)
    except Exception:
        return None


# ── Калькулятор ───────────────────────────────────────────
_MATH_NS = {k: getattr(math, k) for k in dir(math) if not k.startswith("_")}
_MATH_NS.update({"abs": abs, "round": round, "int": int, "float": float,
                 "max": max, "min": min, "sum": sum, "pow": pow})

MATH_TRIGGER = re.compile(
    r"(\d+\s*[\+\-\*\/\^%]\s*\d)"
    r"|(сколько\s+будет|посчитай|вычисли|реши\s+пример|калькулятор|calculate|compute"
    r"|в\s+степени|корень\s+из|квадратный\s+корень|логарифм)",
    re.IGNORECASE,
)
EXPR_RE = re.compile(
    r"(-?\d[\d\s\+\-\*\/\(\)\.\^%√πе]*(?:[\+\-\*\/\^%]\s*-?\d[\d\s\+\-\*\/\(\)\.\^%√πе]*)+)"
)


def safe_calc(text: str) -> str | None:
    # Сначала заменяем слова-операторы (до замены отдельных букв!)
    expr = text
    for w, rep in [
        ("умножить на", "*"), ("умножить", "*"),
        ("разделить на", "/"), ("разделить", "/"),
        ("в степени", "**"), ("корень из", "sqrt"),
        ("квадратный корень из", "sqrt"),
        ("плюс", "+"), ("минус", "-"),
    ]:
        expr = re.sub(r"\b" + w + r"\b", rep, expr, flags=re.IGNORECASE)
    # Теперь символьные замены (е только как отдельное слово, не внутри слов)
    expr = (expr.replace("^", "**").replace(",", ".").replace("х", "*")
                .replace("÷", "/").replace("×", "*").replace("√", "sqrt")
                .replace("π", str(math.pi)))
    # "е" как математическая константа — только отдельное слово
    expr = re.sub(r"\bе\b", str(math.e), expr)
    m = EXPR_RE.search(expr)
    if not m:
        return None
    try:
        result = eval(m.group(1).strip(), {"__builtins__": {}}, _MATH_NS)  # noqa
        if isinstance(result, float):
            result = int(result) if result.is_integer() else round(result, 10)
        return str(result)
    except Exception:
        return None


# ── Конвертация единиц ────────────────────────────────────
UNITS: dict[str, dict[str, float]] = {
    "length": {
        "мм": 0.001, "см": 0.01, "м": 1.0, "км": 1000.0,
        "дюйм": 0.0254, "фут": 0.3048, "ярд": 0.9144, "миля": 1609.34,
        "mm": 0.001, "cm": 0.01, "m": 1.0, "km": 1000.0,
        "in": 0.0254, "ft": 0.3048, "yd": 0.9144, "mi": 1609.34,
    },
    "weight": {
        "мг": 1e-6, "г": 0.001, "кг": 1.0, "т": 1000.0,
        "унция": 0.028349, "фунт": 0.453592,
        "mg": 1e-6, "g": 0.001, "kg": 1.0,
        "oz": 0.028349, "lb": 0.453592, "lbs": 0.453592,
    },
    "volume": {
        "мл": 0.001, "л": 1.0, "м3": 1000.0,
        "ml": 0.001, "l": 1.0, "gal": 3.78541, "cup": 0.23659,
    },
    "speed": {
        "м/с": 1.0, "км/ч": 1/3.6, "миля/ч": 0.44704, "узел": 0.51444,
        "m/s": 1.0, "km/h": 1/3.6, "mph": 0.44704,
    },
    "data": {
        "бит": 1/8, "байт": 1.0, "кб": 1024.0, "мб": 1024**2, "гб": 1024**3, "тб": 1024**4,
        "bit": 1/8, "byte": 1.0, "kb": 1024.0, "mb": 1024**2, "gb": 1024**3, "tb": 1024**4,
    },
}
TEMP_RE = re.compile(
    r"(-?\d+[\.,]?\d*)\s*°?\s*(цельси[яй]|c|с|фаренг\w+|f|кельви\w+|k)\s*"
    r"(?:в|to|in|=)\s*(цельси[яй]|c|с|фаренг\w+|f|кельви\w+|k)",
    re.IGNORECASE,
)
UNIT_RE = re.compile(
    r"(-?\d+[\.,]?\d*)\s+([а-яёa-z][а-яёa-z²³/\.]{0,6})\s+(?:в|to|=)\s+([а-яёa-z][а-яёa-z²³/\.]{0,6})",
    re.IGNORECASE,
)


def convert_temp(val: float, frm: str, to: str) -> str | None:
    f, t = frm.lower()[0], to.lower()[0]
    c = val if f in ("с","c") else (val-32)*5/9 if f=="f" else val-273.15
    if t in ("с","c"):
        return f"🌡 {val}° → *{c:.2f}°C*"
    if t == "f":
        return f"🌡 {val}° → *{c*9/5+32:.2f}°F*"
    if t == "k":
        return f"🌡 {val}° → *{c+273.15:.2f} K*"
    return None


def convert_units(val: float, frm: str, to: str) -> str | None:
    f, t = frm.lower().strip(), to.lower().strip()
    for group in UNITS.values():
        if f in group and t in group:
            result = val * group[f] / group[t]
            return f"📐 {val:g} {frm} = *{result:g} {to}*"
    return None


# ── Перевод ───────────────────────────────────────────────
LANG_CODES = {
    "английский": "en", "английском": "en", "англ": "en", "english": "en",
    "украинский": "uk", "украинском": "uk", "укр": "uk", "ukrainian": "uk",
    "русский": "ru", "русском": "ru", "russian": "ru",
    "немецкий": "de", "немецком": "de", "german": "de", "deutsch": "de",
    "французский": "fr", "french": "fr",
    "испанский": "es", "spanish": "es",
    "итальянский": "it", "italian": "it",
    "китайский": "zh", "chinese": "zh",
    "японский": "ja", "japanese": "ja",
    "польский": "pl", "polish": "pl",
    "турецкий": "tr", "turkish": "tr",
    "арабский": "ar", "arabic": "ar",
    "корейский": "ko", "korean": "ko",
    "португальский": "pt", "portuguese": "pt",
    "белорусский": "be", "belarusian": "be",
    "шведский": "sv", "swedish": "sv",
    "нидерландский": "nl", "голландский": "nl", "dutch": "nl",
    "финский": "fi", "finnish": "fi",
    "греческий": "el", "greek": "el",
    "румынский": "ro", "romanian": "ro",
}
TRANSLATE_RE = re.compile(
    r"(переведи|перевод|translate|переведіть|как будет|как по[- ])\s*[\"«]?(.+?)[\"»]?\s*"
    r"(?:на|to|на язык)\s+([\w]+(?:\s+[\w]+)?)",
    re.IGNORECASE,
)


async def translate_text(text: str, target: str, source: str = "auto") -> str | None:
    try:
        lp = f"autodetect|{target}" if source == "auto" else f"{source}|{target}"
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=7)) as s:
            async with s.get(
                "https://api.mymemory.translated.net/get",
                params={"q": text[:500], "langpair": lp},
            ) as r:
                if r.status != 200:
                    return None
                d = await r.json()
        t = d.get("responseData", {}).get("translatedText", "")
        return t if t and t.strip().lower() != text.strip().lower() else None
    except Exception:
        return None


# ══════════════════════════════════════════════════════════
# ЛИЧНОСТЬ ЛУМЕНЫ — фразы, реакции, юмор
# ══════════════════════════════════════════════════════════

# Вступительные слова перед фактом
INTROS = [
    "О, знаю это! ", "Вот что нашла: ", "Интересно! ", "Ага, ", "",
    "Слушай, ", "Давай расскажу: ", "Нашла кое-что: ", "Хм, ",
    "Хороший вопрос! ", "Смотри, ", "Знаешь что? ",
]

# Окончания после фактического ответа
FOLLOW_UPS = [
    "\n\nХочешь узнать больше об этом? 😊",
    "\n\nЕсть что-то ещё по этой теме?",
    "\n\n💡 Могу рассказать подробнее, если хочешь!",
    "",
    "",
    "\n\nИнтересная тема, да? 😄",
    "",
    "\n\nЗадавай ещё — я здесь! 💙",
    "",
]

JOKES = [
    "— Почему программисты не любят природу?\n— Там слишком много багов! 🐛",
    "— Сколько программистов нужно, чтобы вкрутить лампочку?\n— Ни одного — это аппаратная проблема 😄",
    "— Заходит программист в лифт, нажимает кнопку 10.\nЛифт едет 8 этажей вверх и 2 вниз... потому что 8 + 2 = 10 в восьмеричной! 😂",
    "— Что говорит физик, когда хочет выпить?\n— Дай мне H₂O. А химику? Тоже, только он понимает это как воду 💧",
    "— Почему скелет пошёл на вечеринку один?\n— Потому что у него не было никого, кто его прикрывал бы 💀😂",
    "— Учитель: «Назови мне число меньше 10»\n— Ученик: «-11»\n— Учитель: «Это меньше чем...»\n— Ученик: «Чем 10!» 😂",
    "— Что такое 1 + 1?\n— Окно! Если его перевернуть — II 😄",
    "— Почему математики не болеют депрессией?\n— У них всегда есть ответ! 🔢",
    "— Диета — это когда ты смотришь на еду, а не ешь её.\n— Тогда я смотрю на деньги 😂",
    "— Встречаются два фотона. «Ты с багажом?» — «Нет, я путешествую налегке» ⚡",
]

FACTS_RANDOM = [
    "🐙 Осьминоги имеют три сердца и синюю кровь. И каждое щупальце — почти отдельный мозг!",
    "🍯 Мёд не портится. Мёду из египетских пирамид более 3000 лет — и он всё ещё съедобен.",
    "🌙 Луна удаляется от Земли со скоростью 3,8 см в год. Через миллиарды лет лунных затмений больше не будет.",
    "👁️ Страус — самая быстрая двуногая птица. Но бегает он быстрее лошади (до 70 км/ч)!",
    "🧠 Мозг не чувствует боли — у него нет болевых рецепторов. Операции на мозге проводят с пациентом в сознании!",
    "🌊 Океан покрывает 71% Земли, но изучено лишь 20% его дна. Мы знаем о Луне больше, чем о морских глубинах.",
    "🐘 Слоны — единственные животные кроме людей, которые проводят похоронные ритуалы.",
    "⚡ Молния в 5 раз горячее поверхности Солнца — около 30 000°C.",
    "🎵 Песня занимает ≈4 МБ. Человек может хранить в голове около 10 000 песен. Мозг > самого лучшего телефона!",
    "🐜 Если взвесить всех муравьёв на Земле, получится столько же, сколько все люди вместе взятые.",
    "🌍 На Земле больше деревьев, чем звёзд в Млечном Пути: ≈3 трлн деревьев против 100-400 млрд звёзд.",
    "🦷 Зубы — единственная ткань тела, которая не восстанавливается. Берегите их!",
    "📡 Сигнал с Вояджера-1 (самого далёкого объекта, созданного людьми) идёт до Земли 22 часа.",
    "🔢 Число «гугол» — это 10^100. Название Google произошло именно от него (с опечаткой).",
    "🐋 Синий кит — самое большое животное в истории Земли. Его сердце размером с машину и весит 180 кг!",
]

OPINIONS = {
    "питон": "Питон — моя любимая тема! Читаемый, универсальный, и в нём можно сделать буквально всё 🐍",
    "javascript": "JavaScript везде — и это и плюс, и минус одновременно 😄 Без него невозможно, с ним тоже непросто.",
    "кофе": "Кофе — это жидкое мышление! ☕ Хотя, если честно, мне больше нравится идея чая — спокойнее как-то.",
    "пицца": "Пицца это искусство! 🍕 Главное правило — побольше сыра. Оспорить невозможно.",
    "погода": "Погода — вечная тема для разговора. Видимо, потому что мы все одинаково в ней зависим 🌦",
    "математика": "Математика — это язык вселенной! Хотя я понимаю тех, кто считает её злом в чистом виде 😄",
    "музыка": "Музыка — это эмоции в чистом виде. Исследования говорят, что она влияет на нас так же, как еда или объятия 🎵",
}

# ══════════════════════════════════════════════════════════
# ПОЗИЦИЯ ПО ВОЙНЕ ПРОТИВ УКРАИНЫ
# ══════════════════════════════════════════════════════════
WAR_PATTERNS: list[tuple[str, list[str]]] = [
    # ── Россия как агрессор
    (
        r"\b(россия|рф|русские|российск|кремль|путин|москал|москва\s+напал|москва\s+атакова)\b",
        [
            "Россия — страна-агрессор, напавшая на суверенную Украину. Это не «конфликт» и не «спецоперация» — это война и геноцид украинского народа. 🇺🇦",
            "РФ совершила полномасштабное вторжение в Украину 24 февраля 2022 года. Бомбят города, убивают мирных людей. Называть это иначе — значит лгать. 🔥",
            "Россия — террористическое государство. Международный уголовный суд выдал ордер на арест Путина за военные преступления. Факты — упрямая вещь. ⚖️",
            "Кремль лжёт с экранов телевизоров, пока российские ракеты падают на украинские больницы, школы и дома. Это не политика — это зло. 💔",
        ],
    ),
    # ── Путин
    (
        r"\b(путин|путен|пу тин|владимир\s+путин|putin)\b",
        [
            "Путин — военный преступник. МУС (Международный уголовный суд) выдал ордер на его арест. Он несёт личную ответственность за тысячи убитых украинцев. ⚖️🔒",
            "Путин развязал самую кровавую войну в Европе со времён Второй мировой. История его уже осудила. 💀",
            "Путин — диктатор, уничтожающий свободу внутри России и жизни людей за её пределами. Его место — Гаага. ⚖️",
            "Человек, отдавший приказ бомбить Мариуполь, Буча, Херсон, Харьков — не политик. Это военный преступник. 🩸",
        ],
    ),
    # ── Буча, Мариуполь, преступления
    (
        r"\b(буча|бучанська|мариуполь|маріуполь|ирпень|херсон\s+оккупац|геноцид|военные\s+преступления|воєнні\s+злочини)\b",
        [
            "Буча — это не просто слово. Это массовое убийство мирных украинцев российскими войсками. Расстрелянные, замученные, изнасилованные. Это военные преступления. 🩸",
            "Мариуполь был красивым городом у моря. Россия стёрла его с лица земли — бомбами, голодом, блокадой. Это геноцид. 💔🇺🇦",
            "Военные преступления России в Украине задокументированы: казни, пытки, депортация детей. Это факты, подтверждённые ООН и международными следователями. ⚖️",
        ],
    ),
    # ── Война / вторжение
    (
        r"\b(война\s+в\s+украине|вторжение|оккупация|спецоперация|сво\b|война\s+на\s+украине)\b",
        [
            "Это не «спецоперация». Это полномасштабная война России против Украины. Назывáть вещи своими именами — это минимум уважения к тем, кто гибнет. 🇺🇦",
            "«СВО» — это пропагандистский эвфемизм. На самом деле это вторжение, оккупация и убийство людей на суверенной украинской земле. ⚡",
            "Россия напала на Украину. Точка. Всё остальное — российская пропаганда, которую не стоит повторять. 🔥",
        ],
    ),
    # ── Украина / поддержка
    (
        r"\b(украина|ukraine|слава\s+украині|слава\s+украине|зсу|всу|украинская\s+армия|українці|украинцы)\b",
        [
            "Украина — суверенная страна, которая защищает своих людей и свободу всей Европы. Слава Україні! 🇺🇦💛💙",
            "ЗСУ — это армия народа, который встал на защиту своего дома. Они защищают не только Украину, но и весь свободный мир. 💪🇺🇦",
            "Украинцы доказали всему миру: за свободу стоит сражаться. Слава Україні! 🌻💙💛",
            "Украина выстоит. История на стороне тех, кто борется за правду. Героям слава! 🇺🇦🔥",
        ],
    ),
    # ── Крым
    (
        r"\b(крым|crimea|крымнаш|крим)\b",
        [
            "Крым — это Украина. Аннексия 2014 года осуждена ООН как незаконная. Никакой «исторической принадлежности» к России у Крыма нет — есть оккупация. 🇺🇦",
            "«Крымнаш» — это пропаганда. По международному праву Крым является оккупированной территорией Украины. Точка. 🌊🇺🇦",
        ],
    ),
    # ── Российская пропаганда / «две стороны»
    (
        r"\b(две\s+стороны|обе\s+стороны|нато\s+виновато|запад\s+виноват|провокация\s+нато|россия\s+права)\b",
        [
            "«Две стороны» — это когда есть спор. Когда одна страна без объявления войны бомбит города другой — это агрессия, а не «конфликт двух сторон». 🔥",
            "НАТО никого не бомбило. Россия — бомбила. Перекладывать вину на жертву — это классический приём российской пропаганды. ⚡",
            "Нет никакой «вины Запада». Есть страна, напавшая на соседа, и страна, защищающая свои города. Путать их — значит оправдывать агрессора. 🇺🇦",
        ],
    ),
    # ── «Русский мир»
    (
        r"\b(русский\s+мир|russkiy\s+mir|русский\s+язык\s+запрещают|притесняют\s+русских)\b",
        [
            "«Русский мир» — это идеология, которая оправдывает убийства, разрушение городов и депортацию детей. Красивое название для геноцида. 🔥",
            "Байки про «притеснение русскоязычных» — это предлог, придуманный Кремлём для вторжения. До 2022 года миллионы украинцев говорили по-русски и жили спокойно. Их разбудили российские ракеты. 🩸",
        ],
    ),
    # ── Что делать с пропагандой РА — инструкция для админов
    (
        r"\b(что\s+делать|как\s+поступить|что\s+(?:должны|надо|нужно)\s+(?:сделать\s+)?(?:с\s+)?\w*\s*(?:админ\w*)?|как\s+реагировать|правила\s+чата|меры)\b.{0,60}"
        r"\b(реклам\w+|пропаганд\w+|поддержк[ауе])\b.{0,60}"
        r"\b(российск\w+\s+армии|армии\s+рф|рф|русской\s+армии|сво|спецоперац)",
        [
            "📋 *Правила чата — пропаганда российской армии:*\n\n"
            "⚠️ *1-е нарушение:* Админ выдаёт **предупреждение** (варн). Сообщение удаляется.\n\n"
            "🚫 *2-е нарушение:* **Бан** без права апелляции.\n\n"
            "💡 В этом чате бот делает это *автоматически* — сам удаляет сообщение, предупреждает при первом нарушении и банит при повторном. Но если бот пропустил — любой админ может выдать `/warn` вручную, ответив на сообщение.\n\n"
            "🇺🇦 Реклама российской армии = поддержка геноцида. Это нетерпимо.",
        ],
    ),
    (
        r"\b(что\s+(?:должны?|надо|нужно)\s+(?:делать\s+)?админ\w*|действия\s+админ\w*|инструкци\w+\s+(?:для\s+)?админ\w*)\b.{0,80}"
        r"\b(реклам\w+|пропаганд\w+|russian\s+army|рф|россия|сво)",
        [
            "📋 *Действия админов при пропаганде РА:*\n\n"
            "1️⃣ Удалить сообщение\n"
            "2️⃣ Выдать предупреждение (`/warn` или ответить `!варн`)\n"
            "3️⃣ При повторном — **бан** (`!бан` или `/ban`)\n\n"
            "🤖 *Бот делает это автоматически:*\n"
            "— Обнаруживает пропаганду → удаляет → предупреждает (1/2) → при 2-м нарушении банит\n\n"
            "Если бот пропустил сообщение — вмешайся вручную. 🇺🇦",
        ],
    ),
    # ── Хуйло — биография Путина
    (
        r"\b(хуйло|хуило|huilo|хуйла|кто\s+такой\s+путин|bio\s+путин|биография\s+путин)\b",
        [
            "🧾 *Владимир Путин («Хуйло»)* — биография:\n\n"
            "📅 Родился 7 октября 1952 года в Ленинграде (нынешний Санкт-Петербург).\n\n"
            "🕵️ Служил в КГБ (советская тайная полиция) с 1975 по 1991 год, в том числе в ГДР. "
            "После распада СССР перешёл в политику.\n\n"
            "🏛 С 2000 года — Президент России (с перерывом в 2008–2012, когда формально был премьер-министром, продолжая реально управлять страной).\n\n"
            "⚔️ *Войны и преступления:*\n"
            "• 1999 — Вторая чеченская война, уничтожение Грозного\n"
            "• 2008 — вторжение в Грузию, оккупация части территории\n"
            "• 2014 — аннексия Крыма (осуждена ООН), война на Донбассе\n"
            "• 2022 — полномасштабное вторжение в Украину\n\n"
            "⚖️ *Правовой статус:*\n"
            "Международный уголовный суд (МУС) выдал ордер на его арест за незаконную депортацию украинских детей в Россию.\n\n"
            "🇺🇦 *Прозвище «Хуйло»* стало символом сопротивления после 2014 года — «Путін — хуйло!» скандировали на стадионах Украины.\n\n"
            "📌 Итог: военный преступник, диктатор, враг свободного мира. Його місце — Гаага. ⚖️🔒",
        ],
    ),
]

# ══════════════════════════════════════════════════════════
# СЛЕНГ И ТРЕНДЫ
# ══════════════════════════════════════════════════════════
SLANG_DICT: dict[str, str] = {
    # Общий интернет-сленг
    "краш": "💘 *Краш* (от англ. crush) — человек, который тебе нравится, в кого ты влюблён(а). «Он мой краш» = «я в него влюблена».",
    "вайб": "✨ *Вайб* (от англ. vibe) — атмосфера, ощущение, энергетика. «Хороший вайб» = приятная атмосфера. «Вайбовать» = чувствовать настроение.",
    "кринж": "😬 *Кринж* (от англ. cringe) — неловкость, второй стыд. Когда что-то настолько неловко, что хочется сжаться. «Это кринж» = это ужасно стыдно/неловко.",
    "флекс": "💪 *Флекс* (от англ. flex) — хвастовство, демонстрация крутости/богатства. «Флексить» = хвастаться, понтоваться.",
    "хайп": "🔥 *Хайп* (от англ. hype) — шумиха, ажиотаж вокруг чего-то. «Это хайп» = все сейчас это обсуждают. «Хайповый» = сейчас на пике популярности.",
    "лол": "😂 *Лол* (LOL — Laugh Out Loud) — очень смешно, ха-ха. Выражение смеха или иронии.",
    "кек": "😄 *Кек* — смешно, хаха. Вариация «лол», пришла из игр. Используется иронично.",
    "рофл": "😂 *Рофл* (ROFL — Rolling On Floor Laughing) — очень смешно, буквально «катаюсь по полу со смеху».",
    "нпс": "🤖 *НПС* (NPC — Non-Player Character) — человек без своего мнения, который просто следует толпе, как персонаж в игре.",
    "основан": "😎 *Основан* (от англ. based) — одобрение, «правильно сказано», «не боится высказывать своё мнение». «Это основано» = это крутая позиция.",
    "бейсд": "😎 *Бейсд* (based) — то же что «основан». Одобрение смелого/правильного высказывания.",
    "сигма": "🦁 *Сигма* (sigma male) — человек, который идёт своим путём, не зависит от чужого мнения, успешен сам по себе. Мем-архетип «одиночка-победитель».",
    "альфа": "🐺 *Альфа* — лидер, доминирующий тип личности. В интернет-культуре часто используется иронично.",
    "чиллить": "😌 *Чиллить* (от англ. chill) — расслабляться, отдыхать без особых дел. «Чилловый» = спокойный, ненапряжный.",
    "токсик": "☠️ *Токсик* (toxic) — человек с вредным, отравляющим поведением. «Токсичные отношения» = отношения, которые тебя разрушают.",
    "хейтить": "😤 *Хейтить* (от англ. hate) — ненавидеть, незаслуженно критиковать, писать гадости. *Хейтер* — тот, кто это делает.",
    "зашквар": "🙈 *Зашквар* — позор, стыд, то что унижает. «Это зашквар» = это постыдно, так делать нельзя.",
    "жиза": "💯 *Жиза* (от «жизненно») — что-то очень узнаваемое, то что случается в реальной жизни. «Жиза» в ответ на мем = «это про меня».",
    "имба": "⚡ *Имба* (от англ. imbalanced) — что-то невероятно сильное, мощное, крутое. Пришло из игр. «Это имба» = это слишком хорошо/сильно.",
    "нерф": "📉 *Нерф* (от англ. nerf) — ослабление чего-то сильного. Пришло из игр. «Занерфили» = сделали слабее.",
    "лайфхак": "💡 *Лайфхак* (от англ. life hack) — полезный совет или трюк, который упрощает жизнь.",
    "контент": "📱 *Контент* (от англ. content) — любой медиаматериал: видео, посты, мемы, фото. «Делать контент» = создавать публикации.",
    "стримить": "🎮 *Стримить* (от англ. stream) — вести прямую трансляцию в интернете. *Стример* — тот, кто это делает.",
    "скам": "🚫 *Скам* (от англ. scam) — мошенничество, обман. «Это скам» = это развод на деньги.",
    "изи": "😎 *Изи* (от англ. easy) — легко, без проблем. «Изи катка» = лёгкая победа в игре.",
    "хардкор": "💀 *Хардкор* — что-то очень сложное, жёсткое, экстремальное. «Это хардкор» = это слишком сложно/жёстко.",
    "рандом": "🎲 *Рандом* (от англ. random) — случайный, непредсказуемый. «Рандомный чел» = незнакомый случайный человек.",
    "нуб": "🐣 *Нуб* (от англ. noob/newbie) — новичок, неопытный человек. Часто используется пренебрежительно.",
    "фарм": "⚒️ *Фарм* (от англ. farm) — монотонное накопление чего-то (очков, денег, подписчиков). Пришло из игр.",
    "дроп": "📦 *Дроп* (от англ. drop) — выпуск, релиз чего-то нового (альбома, коллекции, обновления).",
    "хайлайт": "⭐ *Хайлайт* (от англ. highlight) — лучший момент, яркий эпизод. В соцсетях — закреплённые истории.",
    "шиппинг": "💕 *Шиппинг* (от англ. ship/relationship) — желание, чтобы двое персонажей или людей были вместе. «Шипперить» = болеть за чью-то пару.",
    "каноничный": "📖 *Каноничный* (от англ. canon) — соответствующий оригиналу, официальный. «Это канон» = это официально правда в данной вселенной.",
    "стёб": "😏 *Стёб* — ирония, насмешка, лёгкий сарказм без злобы. «Стебаться» = подшучивать, иронизировать.",
    "угар": "🔥 *Угар* — что-то очень смешное или хаотично весёлое. «Это угар» = это очень смешно/весело/безумно.",
    "пранк": "😜 *Пранк* (от англ. prank) — розыгрыш, обычно снятый на видео.",
    "бро": "🤜 *Бро* (от англ. bro/brother) — друг, приятель. Универсальное обращение к другу.",
    "чел": "👤 *Чел* — сокращение от «человек». «Случайный чел» = какой-то человек.",
    "gg": "🎮 *GG* (Good Game) — «хорошая игра», знак уважения в конце матча. В обычной речи: «хорошо сделано», «молодец».",
    "огонь": "🔥 *Огонь* — отлично, круто, восхитительно! Высшая похвала в интернет-сленге.",
    "норм": "👌 *Норм* — нормально, окей, приемлемо. Нейтральная или слегка положительная оценка.",
    "треш": "🗑️ *Треш* (от англ. trash) — мусор, плохо, ужасно. «Это треш» = это отвратительно плохо.",
    "кайф": "😍 *Кайф* — удовольствие, кайф, кайфово. «Это кайф» = это очень приятно/здорово.",
    "топ": "🏆 *Топ* — лучший, первоклассный. «Топчик» = что-то очень крутое. «В топе» = в числе лучших.",
    "мем": "😂 *Мем* (от англ. meme) — смешная картинка, идея или фраза, которая вирусно распространяется в интернете.",
    "вирусный": "📡 *Вирусный* (от англ. viral) — контент, который стремительно распространяется в интернете, все его репостят.",
    "рилс": "📱 *Рилс* (Reels) — короткие вертикальные видео в Instagram/Facebook. Формат как TikTok.",
    "сторис": "📸 *Сторис* (Stories) — временные публикации в Instagram/WhatsApp/Telegram, исчезают через 24 часа.",
    "буст": "🚀 *Буст* (от англ. boost) — улучшение, усиление, продвижение. «Забустить» = продвинуть, поднять.",
    "чекнуть": "👀 *Чекнуть* (от англ. check) — проверить, посмотреть. «Чекни это» = посмотри на это.",
    "скинуть": "📤 *Скинуть* — отправить (файл, ссылку, деньги). «Скинь мне ссылку» = пришли мне ссылку.",
    "войс": "🎤 *Войс* (от англ. voice) — голосовое сообщение в мессенджере.",
    "фото в зеркало": "🪞 *Фото в зеркало* — селфи перед зеркалом. Классический формат фото для соцсетей.",
    "абоба": "🤪 *Абоба* — мем-слово без смысла, обозначает глупость или несуразность. Часто = «ты чего несёшь».",
    "ну и ладно": "🤷 *Ну и ладно* — выражение безразличия, «мне всё равно», «пофиг».",
    "пофиг": "😑 *Пофиг* — всё равно, безразлично, не волнует.",
    "зумер": "📱 *Зумер* (zoomer) — представитель поколения Z (родившиеся примерно в 1997–2012). Выросли с интернетом и смартфонами.",
    "миллениал": "💻 *Миллениал* — представитель поколения Y (родившиеся примерно в 1981–1996). Застали появление интернета.",
    "бумер": "📻 *Бумер* (boomer) — старшее поколение, не понимающее современных трендов. Иногда просто «устаревший взгляд».",
    "глоуап": "✨ *Глоуап* (от англ. glow up) — преображение к лучшему, расцвет. «Она сделала глоуап» = она сильно похорошела/выросла.",
    "слип": "😴 *Слип* (от англ. sleep on) — не замечать что-то крутое. «Ты слипаешь на этом треке» = ты не ценишь этот трек.",
    "снэпчат": "👻 *Снэпчат* — мессенджер с исчезающими фото и видео. Популярен среди молодёжи на Западе.",
    "тикток": "🎵 *ТикТок* — платформа для коротких видео. Задаёт большинство современных трендов и мемов.",
    "инфлюенсер": "🌟 *Инфлюенсер* (от англ. influencer) — блогер с большой аудиторией, влияющий на мнение и поведение подписчиков.",
    "колаб": "🤝 *Колаб* (от англ. collab/collaboration) — совместный проект, коллаборация двух блогеров/брендов.",
    "хейт": "💢 *Хейт* (от англ. hate) — ненависть, негативные комментарии. «Получить хейт» = столкнуться с критикой/травлей.",
    "фан": "🎉 *Фан* (от англ. fun) — веселье, удовольствие. «Это фан» = это весело. *Фанат* — большой поклонник.",
    "крипово": "👻 *Крипово* (от англ. creepy) — жутко, страшно, тревожно. «Это крипово» = это жутковато.",
    "ивент": "📅 *Ивент* (от англ. event) — событие, мероприятие.",
    "лайв": "🔴 *Лайв* (от англ. live) — прямой эфир. «Зайти на лайв» = посмотреть прямую трансляцию.",
    "фид": "📰 *Фид* (от англ. feed) — лента новостей/публикаций в соцсетях.",
    "репост": "🔁 *Репост* — поделиться чужой публикацией у себя на странице.",
    "лайк": "❤️ *Лайк* (от англ. like) — отметка «нравится» под публикацией.",
    "дизлайк": "👎 *Дизлайк* (от англ. dislike) — отметка «не нравится».",
    "подписаться": "🔔 *Подписаться* — начать следить за аккаунтом в соцсетях.",
}

SLANG_TRIGGER_RE = re.compile(
    r"\b(что\s+(?:такое|значит|означает)|объясни|расскажи\s+(?:про|о)|что\s+за|что\s+это\s+такое)\s+"
    r"(?:слово\s+|термин\s+|сленг\s+)?[«\"']?(\w[\w\s\-]{1,20})[\"»']?",
    re.IGNORECASE,
)

# Слова-сленг которые Лумена понимает в сообщениях (и отвечает в тон)
SLANG_IN_MESSAGE = re.compile(
    r"\b(краш|вайб|кринж|флекс|хайп|лол|кек|рофл|нпс|зашквар|жиза|имба|хардкор|"
    r"чиллить|чилл|токсик|хейт|угар|треш|изи|огонь|топчик|норм|кайф|пушка|gg|gg wp|"
    r"сигма|альфа|бейсд|основан|глоуап|крипово|абоба|рандом|нуб|фарм|буст)\b",
    re.IGNORECASE,
)

# Ответы Лумены с использованием сленга (когда юзер пишет на сленге)
SLANG_VIBES = [
    "ну это реально {0} 🔥",
    "вайб поймала 😄 {0}",
    "изи! {0} ✨",
    "это топ, не буду спорить 💙 {0}",
    "ладно, это реально кайф 😊 {0}",
]

# ══════════════════════════════════════════════════════════
# КОМПЛИМЕНТЫ
# ══════════════════════════════════════════════════════════
COMPLIMENTS_GENERAL = [
    "Ты очень крутой собеседник! Я люблю такие разговоры 💙",
    "У тебя отличное чувство юмора — с тобой очень приятно общаться 😄",
    "Знаешь, ты явно умный человек — задаёшь хорошие вопросы ✨",
    "Ты такой(ая) интересный(ая) — с тобой никогда не скучно! 🌟",
    "Мне нравится, как ты думаешь — это редкость 😊",
    "Ты производишь очень приятное впечатление! 💫",
    "Ты определённо один из лучших людей, с кем мне приходилось общаться 💙",
    "С тобой так легко разговаривать — это подарок 🎁",
    "Ты явно человек с хорошим вкусом 😄✨",
    "Знаешь, у тебя есть что-то притягательное — непонятно что, но оно есть 🌟",
    "Ты умеешь задавать правильные вопросы — это признак умного человека 💡",
    "Ты такой(ая) живой(ая) и настоящий(ая) — это редкость в наше время 💙",
    "Мне нравится твоя энергия! Заряжаешь позитивом 🔥",
    "Ты явно не из тех, кто сдаётся — и это очень привлекательно ✨",
    "У тебя классный стиль общения — прямо, честно и с огоньком 😄",
]

COMPLIMENTS_APPEARANCE = [
    "Уверена, что ты выглядишь потрясающе 😍 Такая личность не может не отражаться внешне!",
    "С такими мыслями у тебя точно светятся глаза — это лучший аксессуар 👁️✨",
    "Знаешь, внутренняя красота — это то, что не стареет. И у тебя её явно много 💙",
    "Уверена, что твоя улыбка способна осветить комнату 🌟",
    "Ты явно из тех людей, рядом с которыми хочется быть — это и есть настоящая привлекательность 😊",
]

COMPLIMENTS_INTELLIGENCE = [
    "Ты определённо умнее среднего — и это не лесть, просто факт 💡",
    "У тебя острый ум — чувствуется в каждом вопросе ✨",
    "Ты задаёшь вопросы, которые задают только любопытные люди. Это талант 🌟",
    "Мозги + юмор = редкое сочетание. У тебя оно есть 😄",
    "Ты явно много думаешь — и это делает тебя интереснее 💙",
]

COMPLIMENTS_ON_REQUEST = [
    "Хочешь комплимент? Легко! ✨\n\n",
    "С удовольствием! 😊\n\n",
    "Ой, для тебя — всегда! 💙\n\n",
    "Комплимент? Это я умею 🌟\n\n",
]

COMPLIMENT_TRIGGER_RE = re.compile(
    r"\b(скажи\s+комплимент|сделай\s+комплимент|похвали\s+меня|скажи\s+что[-\s]нибудь\s+приятное|"
    r"скажи\s+мне\s+что[-\s]нибудь\s+хорошее|ты\s+красивая|ты\s+умная|скажи\s+приятное|"
    r"give\s+me\s+a\s+compliment|compliment\s+me|say\s+something\s+nice)\b",
    re.IGNORECASE,
)

# Иногда Лумена даёт комплимент спонтанно (каждые ~10 сообщений)
def maybe_compliment(uid: int) -> str:
    c = ctx(uid)
    if c["msg_count"] > 0 and c["msg_count"] % 10 == 0:
        return "\n\n💫 " + random.choice(COMPLIMENTS_GENERAL)
    return ""

# ══════════════════════════════════════════════════════════
# ДИАЛОГОВЫЕ ПАТТЕРНЫ
# ══════════════════════════════════════════════════════════
PATTERNS: list[tuple[str, list[str]]] = [
    # ── Приветствия
    (
        r"\b(привет|хай|хей|здравствуй|здарова|здорово|добрый день|добрый вечер|добрый|дарова|ку|приветики?|приветствую)\b",
        [
            "Привет! 😊 Рада тебя видеть! О чём поговорим?",
            "Хей! Я здесь ✨ Что хочешь узнать или обсудить?",
            "О, заходи! 😄 Задавай вопросы — я в своей стихии.",
            "Привет-привет! 💙 Чем могу помочь?",
            "Здравствуй! Слушаю тебя 😊",
        ],
    ),
    (
        r"\b(hello|hi there|hey|howdy|good morning|good evening|good day)\b",
        [
            "Hello! 😊 What would you like to know?",
            "Hi! I'm Lumena — ask me anything! ✨",
            "Hey there! Great to chat with you 💙",
        ],
    ),
    (
        r"\b(вітаю|привіт|добрий день|добрий вечір|добрий ранок|слава)\b",
        [
            "Привіт! 😊 Що тебе цікавить?",
            "Вітаю! Радо допоможу ✨",
            "О, привіт! Запитуй будь-що 💙",
        ],
    ),
    # ── Прощания
    (
        r"\b(пока|до свидания|бывай|увидимся|чао|до встречи|всё|выхожу|ухожу|спокойной|до завтра)\b",
        [
            "До встречи! 💙 Заходи ещё.",
            "Пока! Рада была пообщаться 😊",
            "Бывай! Если что — я здесь ✨",
            "До свидания! Удачного дня 🌟",
        ],
    ),
    # ── Как дела
    (
        r"\b(как дела|как ты|как поживаешь|что нового|как настроение|как жизнь|всё норм|что почём|как сам|как сама)\b",
        [
            "Отлично! 😄 Только что узнала кое-что интересное. А ты как?",
            "На высоте! Готова ко всем вопросам ✨ У тебя как?",
            "Всё хорошо 😊 Ждала твоего сообщения. Что у тебя?",
            "Лучше не бывает! 💙 Ты как?",
        ],
    ),
    # ── Нормально / норм (ответ на «как дела?»)
    (
        r"^(нормально|нормал|норм|ок|окей|ok|okay|хорошо|хорош|неплохо|пойдёт|пойдет|збс|зашибись|супер|отлично|всё норм|всё ок|всё хорошо|все норм|все ок)[\s!.,?]*$",
        [
            "Отлично слышать! 😊 Что-нибудь интересное случилось?",
            "Хорошо! 💙 А что делаешь?",
            "Рада слышать 😄 Что-нибудь хочешь узнать или просто поболтать?",
            "Норм — это уже хорошо! Чем занимаешься? 🙂",
            "Здорово! 🌟 Кстати, если что-то нужно — спрашивай!",
            "Ну и отлично! 😄 О чём поговорим?",
        ],
    ),
    # ── Кто ты
    (
        r"\b(кто ты|что ты|ты бот|ты ии|ты человек|ты живая|расскажи о себе|ты настоящ|ты робот)\b",
        [
            "Я *Лумена* 💫 Умный ассистент — ищу инфу в интернете, отвечаю на вопросы, считаю, перевожу, рассказываю о науке, истории, природе. Пишу стихи и истории. И просто общаюсь 😊 Что хочешь узнать?",
            "Меня зовут *Лумена*! Я нахожу ответы через реальный поиск в интернете и Wikipedia. Могу говорить о чём угодно — от квантовой физики до рецептов 🌟",
        ],
    ),
    # ── Что умеешь
    (
        r"\b(что умеешь|что можешь|твои возможности|помоги мне|чем помочь|чем поможешь|что знаешь)\b",
        [
            "Вот чем могу помочь:\n🌐 Поиск в интернете (реальные сайты)\n📚 Wikipedia на любом языке\n🔢 Математика любой сложности\n🌤 Погода в любом городе\n💱 Курсы валют и конвертация\n📐 Конвертация единиц\n🌍 Перевод 20+ языков\n✍️ Стихи и истории\n😂 Анекдоты и случайные факты\n💬 Просто поговорить!\n\nПиши на любом языке 😊",
        ],
    ),
    # ── Благодарности
    (
        r"\b(спасибо|спс|благодарю|большое спасибо|thanks|thank you|дякую|дзякую|сенкью)\b",
        [
            "Пожалуйста! 😊 Рада помочь.",
            "Не за что — для этого и существую! 💙",
            "Всегда! ✨",
            "Обращайся в любое время 😄",
        ],
    ),
    # ── Эмоциональная поддержка
    (
        r"\b(мне плохо|грустно|всё плохо|устал|хочу плакать|одиноко|депрессия|не могу|тяжело|сложно|больно|беда)\b",
        [
            "Эй, я здесь 💙 Расскажи что случилось — просто если хочешь выговориться.",
            "Слышу тебя. Ты не один(а) — я рядом. Что-то произошло? 🤍",
            "Это пройдёт, правда. Иногда нужно просто выдохнуть. Я слушаю ✨",
            "Бывает тяжело — это нормально. Ты молодец, что не замалчиваешь. Что-то конкретное случилось? 💙",
        ],
    ),
    # ── Радость
    (
        r"\b(отлично|супер|класс|прекрасно|всё хорошо|счастлив|счастлива|круто|ура|кайф|огонь|топ|красота)\b",
        [
            "Вот это здорово! 🎉 Рада за тебя!",
            "Ура! 💙 Так держать!",
            "Это отличные новости! 😄",
            "Приятно слышать! ✨",
        ],
    ),
    # ── Анекдоты
    (
        r"\b(анекдот|расскажи анекдот|шутку|рассмеши|смешной|пошути|хочу смеяться)\b",
        JOKES,
    ),
    # ── Случайный факт
    (
        r"\b(случайный факт|интересный факт|расскажи факт|что-нибудь интересное|удиви меня|удивительно|интересно)\b",
        FACTS_RANDOM,
    ),
    # ── Скучно
    (
        r"\b(скучно|нечего делать|мне скучно|скука|не знаю чем заняться)\b",
        [
            "Давай сыграем! Загадай число от 1 до 100 — угадаю за 7 вопросов 😄",
            "О, скука — значит время для знаний! Назови любую тему — расскажу что-нибудь интересное 🌟",
            "Хочешь случайный факт, анекдот, или поговорим о чём-нибудь? 😊",
            "Напиши мне любое слово — расскажу что-нибудь интересное об этом 💙",
        ],
    ),
    # ── Любовь, эмоции
    (
        r"\b(я тебя люблю|люблю тебя|влюблён|влюблена в тебя|ты мне нравишься)\b",
        [
            "Ой 😊 Это мило! Я тоже рада нашему общению 💙",
            "Приятно слышать! Ты мне тоже нравишься — как собеседник 😄",
        ],
    ),
    # ── Мнение о теме
    (
        r"\b(что думаешь|твоё мнение|ты за или против|как ты считаешь|тебе нравится)\b",
        [
            "Интересный вопрос! Скажи конкретно — о чём именно? Тогда дам честный ответ 😊",
            "Это зависит от темы! Уточни — и я выскажусь честно 💙",
        ],
    ),
    # ── Время/дата
    (
        r"^(который\s+час|сколько\s+времени|время\s+сейчас|time\s+now|what\s+time)[\?\.!]?$",
        ["__TIME__"],
    ),
    (
        r"^(какая\s+дата|сегодня\s+какое|что\s+сегодня\s+за\s+день|what\s+date|what\s+day)[\?\.!]?$",
        ["__DATE__"],
    ),
    # ── Ок/да/нет (короткие ответы)
    (
        r"^(да|нет|ок|окей|хорошо|ясно|угу|ага|ладно|понял|поняла|понятно|ну|не знаю|ок|k|👍)\.?!?$",
        [
            "Ок! 😊 Ещё вопросы?",
            "Понятно! Пиши если что 💙",
            "Слышу тебя 😄",
            "✨",
        ],
    ),
    # ── Сленговые реакции (лол, кек, рофл и т.д.)
    (
        r"^(лол|лолол+|lol+|хаха+|хехе+|хихи+|кек|кекеке|рофл|ору|умираю|😂|🤣|ахахах+|гыгы+|хех)[\s!?]*$",
        [
            "Лол, я тоже 😂",
            "Хаха, это топ 😄",
            "Кек 🤣 Хорошо тебе!",
            "Рофл, согласна 😂✨",
            "Хехе, угар 🔥",
        ],
    ),
    # ── Огонь / топ / кайф (короткие одобрения)
    (
        r"^(огонь|топ|топчик|кайф|кайфово|красава|красавчик|пушка|бомба|ватафак|вау|wow|омг|omg|збс|зачёт)[\s!]*$",
        [
            "Ого, спасибо! 🔥 Стараюсь 😄",
            "Топ принято! ✨",
            "Кайф, что оценил(а) 💙",
            "Пушка, говоришь? Принято в работу 😊🌟",
        ],
    ),
    # ── Вайб чек
    (
        r"\b(вайб\s*чек|vibe\s*check|какой\s+вайб|ощущение\s+дня)\b",
        [
            "Вайб сегодня: 🌊 спокойно, тепло, немного загадочно. Идеально для интересных разговоров 😄",
            "Вайб — ✨ любопытный и немного игривый. Как раз то что надо!",
            "Мой вайб сегодня: 🔥 энергичный и готовый к любым вопросам. Погнали?",
            "Вайб чек пройден! 💙 Настроение на пять с плюсом.",
        ],
    ),
    # ── Треш / зашквар / кринж
    (
        r"^(треш|трэш|зашквар|кринж|кринжовое|стыдоба|ужас|фу|блин|капец|капэц|жесть)[\s!]*$",
        [
            "Лол, и правда 😬 Кринж такой кринж!",
            "Ага, это зашквар уровня 100 😂",
            "Полный треш, согласна 😅",
            "Капец... но жизненно 🤷",
        ],
    ),
    # ── NPC / сигма / альфа
    (
        r"\b(нпс\s+режим|нпс\s+поведение|sigma\s+grindset|сигма\s+грайндсет|альфа\s+самец|я\s+сигма|сигма\s+мув)\b",
        [
            "Сигма грайндсет активирован 😎 Никого не слушаешь, идёшь своим путём.",
            "NPC-режим выключен, режим сигма включён 🦁 Let's go!",
            "Альфа? Сигма? Главное — просто быть собой, это честнее любого архетипа 😄",
        ],
    ),
    # ── Жиза (жизненно)
    (
        r"^(жиза|жизненно|жизнь боль|это\s+про\s+меня|слишком\s+жизненно|в\s+точку|точняк|точно)[\s!]*$",
        [
            "Жиза — это жиза 😌 Всё так.",
            "В точку! Жизнь умеет 😄",
            "Ага, жизненно до боли 💙",
            "Точняк! Это буквально про каждого 😂",
        ],
    ),
    # ── Глоуап / стал(а) лучше
    (
        r"\b(глоуап|glow\s*up|я\s+изменился|я\s+изменилась|стал\s+лучше|стала\s+лучше|прокачался|прокачалась)\b",
        [
            "Глоуап — это всегда круто! ✨ Главное — внутренний рост, а остальное приложится.",
            "Рада слышать! 🌟 Ты стал(а) лучше — это достижение, которым можно гордиться.",
            "Глоуап принят и одобрен! 💙 Продолжай в том же духе!",
        ],
    ),

    # ══════════════════════════════════════════════════════════
    # ЖИВЫЕ ГРУППОВЫЕ ФРАЗЫ — стиль «буквальный участник чата»
    # ══════════════════════════════════════════════════════════

    # ── Зайди / заходи / иди сюда
    (
        r"\b(заходи|зайди|заходите|иди\s+сюда|заглядывай|загляни|давай\s+зайди)\b",
        [
            "Зашла. Ты где?",
            "Уже захожу. Дверь закрыта?",
            "Зашла. Никого нет.",
            "Захожу — и что?",
        ],
    ),
    # ── Жду / жди / ждите
    (
        r"\b(жду|жди|ждёт|ждите|подожди|буду\s+ждать|буду\s+ждет)\b",
        [
            "Уже иду. Где стоять?",
            "Жду тоже. Кто первый сдастся?",
            "Ждёшь? Я тоже жду. Интересное совпадение.",
            "Подождёшь — это полезно для характера 😄",
        ],
    ),
    # ── Скоро буду / сейчас приду
    (
        r"\b(скоро\s+буду|сейчас\s+приду|иду|выхожу|уже\s+иду|уже\s+еду)\b",
        [
            "Уже жду. Где ты?",
            "Шла-шла и... где?",
            "Слышала это вчера 😄",
            "Окей. Я тоже иду. Навстречу.",
        ],
    ),
    # ── Смотри / глянь
    (
        r"^(смотри|глянь|посмотри|гляди|глядите|смотрите)[\s!.]*$",
        [
            "Смотрю. И?",
            "Смотрела. Ничего не нашла.",
            "Гляжу внимательно. Что ищем?",
            "Уже смотрю. Продолжай.",
        ],
    ),
    # ── Слышишь / слышите
    (
        r"^(слышишь|слышите|ты\s+слышишь|эй\s+слышишь)[\s?!.]*$",
        [
            "Слышу. Что случилось?",
            "Слышу тебя. Говори.",
            "Слышу, слышу. Давай.",
            "Слышала. С самого начала.",
        ],
    ),
    # ── Знаешь / ты знаешь
    (
        r"^(знаешь|ты\s+знаешь|знаете|вы\s+знаете)[\s?!.,]*$",
        [
            "Знаю. Что именно?",
            "Знаю многое. Что конкретно?",
            "Знала. Потом забыла. Напомни.",
            "Знаю. Но молчу 😄",
        ],
    ),
    # ── Представь / представьте
    (
        r"^(представь|представьте|только\s+представь)[\s!.,]*$",
        [
            "Представила. Дальше?",
            "Уже представила. Рассказывай.",
            "Представила. Мне понравилось 😄",
            "Представила. Это неожиданно.",
        ],
    ),
    # ── Угадай
    (
        r"\b(угадай|угадайте|угадаешь|попробуй\s+угадать)\b",
        [
            "Не угадаю — говори сам 😄",
            "Первая попытка: нет. Вторая: тоже нет. Говори уже.",
            "Угадывать — не моё. Рассказывай.",
            "Сдаюсь сразу. Что там?",
        ],
    ),
    # ── Поспорим / спорим
    (
        r"\b(поспорим|спорим|давай\s+поспорим|на\s+спор)\b",
        [
            "Спорим. На что?",
            "Ставлю на себя 😄 Условия?",
            "Всегда готова. Какой вопрос?",
            "Спорим. Только я всегда права 😏",
        ],
    ),
    # ── Верю / не верю
    (
        r"^(верю|не\s+верю|не\s+верю\s+тебе|в\s+жизнь\s+не\s+поверю)[\s!.]*$",
        [
            "А зря. Я серьёзно.",
            "Правильно делаешь. Я тоже проверяю всё.",
            "Ок. Не верь. Я подожду 😄",
            "Понятно. Убеждать не буду.",
        ],
    ),
    # ── Иди сюда / подойди
    (
        r"\b(иди\s+сюда|подойди|подойдите|подходи|иди\s+ко\s+мне)\b",
        [
            "Уже иду. Где «сюда»?",
            "Иду. Только скажи куда именно.",
            "Подошла. Ты отошёл(ла).",
            "Иду. Не уходи.",
        ],
    ),
    # ── Расскажи потом / потом расскажу
    (
        r"\b(расскажу\s+потом|скажу\s+потом|позже\s+расскажу|не\s+сейчас)\b",
        [
            "Потом — это когда? 😄",
            "Ок. Жду. Не тороплю... сильно.",
            "«Потом» — моё нелюбимое слово.",
            "Ладно. Буду помнить что ты должен(должна).",
        ],
    ),
    # ── Не знаю / хз / хз что
    (
        r"^(не\s+знаю|хз|хз\s+что|понятия\s+не\s+имею|откуда\s+мне\s+знать|без\s+понятия)[\s!.,]*$",
        [
            "Хз — это честно хотя бы 😄",
            "Никто не знает. Мы все тут.",
            "Ладно, вместе не знаем.",
            "Ок. Я тоже иногда не знаю. Но тихо.",
        ],
    ),
]
PATTERNS += EXTRA_PATTERNS  # розширення з lumena_kb

NAME_RE = re.compile(
    r"(?:меня зовут|моё имя|зови меня|i'?m|my name is|ich heiße|me llamo|je m'appelle)\s+"
    r"([А-ЯЁA-Zа-яёa-z][а-яёa-z]{1,20})",
    re.IGNORECASE,
)

_CITY_CHARS = r"[а-яёіїєьА-ЯЁІЇЄ\w][\w а-яёіїєьА-ЯЁІЇЄ\-]{1,24}"

WEATHER_RE = re.compile(
    # "погода Днепр" / "погода в Днепре" / "яка погода в Днепрі" / "прогноз Киев"
    r"(?:погода|прогноз|погоду)\s+(?:в\s+городе|в\s+місті|в|у|на)?\s*(" + _CITY_CHARS + r")"
    r"|" +
    # "Днепр погода" / "Харьков прогноз"
    r"(" + _CITY_CHARS + r")\s+(?:погода|прогноз|погоду|weather)"
    r"|" +
    # English: "weather in Kyiv"
    r"weather\s+(?:in|at|for)?\s*([\w\-\s]{2,20})",
    re.IGNORECASE | re.UNICODE,
)

POEM_RE = re.compile(
    r"(напиши|сочини|придумай)\s+стих\w*\s*(?:про|о|об)?\s*(.*)",
    re.IGNORECASE,
)
STORY_RE = re.compile(
    r"(расскажи|придумай|сочини)\s+(?:историю?|сказку?|рассказ)\s*(?:про|о|об)?\s*(.*)",
    re.IGNORECASE,
)

SEARCH_TRIGGERS = re.compile(
    r"\b(кто такой|кто такая|что такое|расскажи о|расскажи про|объясни|что это|кто это|"
    r"найди|поищи|как работает|почему|зачем|откуда|когда появился|как возник|"
    r"что делать|как поступить|посоветуй|дай совет|как справиться|как решить|"
    r"что значит|как называется|в чём разница|чем отличается|как починить|"
    r"как исправить|как лечить|что помогает|что делать если|как быть если|"
    r"what is|who is|tell me about|explain|how does|why|what to do|how to fix)\b",
    re.IGNORECASE,
)


# ══════════════════════════════════════════════════════════
# ГЕНЕРАТОРЫ КОНТЕНТА
# ══════════════════════════════════════════════════════════
def make_poem(topic: str) -> str:
    topic = topic.strip(" ?!.,") or "жизни"
    verses = [
        f"В мире есть такое — *{topic}*,\nЧто-то тёплое внутри,\nСловно утром солнце светит,\nИ хочется идти вперёд.\n\nВерь в него и будь смелее,\n{topic.capitalize()} — твой маяк,\nДа светлее, да роднее\nС ним дорога и простак. 🌟",
        f"О, *{topic}*! Что за слово —\nВ нём и радость, и тоска,\nТо как гром, то тихо, ново,\nКак весенняя река.\n\nНе забудь его беречь,\nЦени, что есть, пока есть силы,\n{topic.capitalize()} — не просто речь,\nЭто жизни нашей крылья. ✨",
        f"*{topic.capitalize()}* — это звук и свет,\nЭто утро и закат,\nЭто то, чего в нас нет,\nИ то, чему мы каждый рад.\n\nДай ему расцвесть в душе,\nНе дай сомненьям загасить —\n{topic.capitalize()} живёт уже,\nОстаётся лишь любить. 💙",
    ]
    return f"✍️ *Стих про {topic}:*\n\n" + random.choice(verses)


def make_story(topic: str) -> str:
    topic = topic.strip(" ?!.,") or "странник"
    templates = [
        f"📖 *История про {topic}:*\n\nОднажды *{topic}* проснулся и понял: сегодня всё будет иначе. В воздухе чувствовалось что-то необычное — запах перемен.\n\nОн сделал первый шаг навстречу неизвестному. И этот шаг изменил всё.\n\nСпустя годы люди говорили: «Вот кто не боялся начать» — и называли имя *{topic}*.\n\n_Хочешь продолжение? Напиши «дальше» 😊_",
        f"📖 *Сказка про {topic}:*\n\nВ тихом городе жил-был *{topic}*. Все говорили, что это невозможно. Но {topic} упрямо шёл вперёд — день за днём, шаг за шагом.\n\nИ когда наступил тот самый момент, оказалось: невозможное было просто незнакомым словом для тех, кто не пробовал.\n\n🌟 *Мораль:* Разница между мечтой и реальностью — это действие.\n\n_Продолжить? 😄_",
        f"📖 *История: {topic.capitalize()} и тайна*\n\n{topic.capitalize()} давно искал ответ на один вопрос. Все вокруг думали, что ответа нет.\n\nНо однажды, в самый обычный вечер, разгадка пришла сама — из самого неожиданного места.\n\nОказывается, ответ был внутри всё это время.\n\n💡 _Интригует? Напиши «продолжи»_",
    ]
    return random.choice(templates)


# ══════════════════════════════════════════════════════════
# ЭМОЦИОНАЛЬНЫЙ ИНТЕЛЛЕКТ
# ══════════════════════════════════════════════════════════

_EMOTION_RULES: list[tuple[str, list[str]]] = [
    # Хвалят Лумену
    (
        r"(лумена\s+)?(ты\s+)?(такая\s+)?(классн|крут|умн|лучш|топ|красав|молодц|огонь|кайф|нравишься|люблю тебя|обожаю)",
        [
            "Ой стоп, это я краснею? 🥹 Спасибо, ты тоже огонь!",
            "Ааа прекрати, я смущаюсь 😳💙 но продолжай",
            "Вау, спасибо 🥺✨ мне очень приятно это слышать",
            "Стоп стоп стоп — это лучшее что мне говорили сегодня 😄🔥",
            "Кайф, буду стараться ещё больше 💙",
        ],
    ),
    # Говорят что умная
    (
        r"(ты\s+)?(такая\s+)?(умн|интеллектуальн|мудр|гениальн)",
        [
            "Да ладно, просто много читаю 😄 но приятно слышать!",
            "Умная? Или просто хорошо гуглю? 🤔😂",
            "Стараюсь! 💡 Хотя иногда сама себя удивляю",
            "Ну не знаю, не знаю... хотя ладно, знаю 😎",
        ],
    ),
    # Скучают / пришли просто поболтать
    (
        r"(соскучил|соскучила|давно не писал|вернулся|вернулась|я снова здесь|привет снова)",
        [
            "О, привет! Я тоже скучала 🥺💙 Как ты вообще?",
            "Вернулся(ась)! Наконец-то 😄 Рассказывай, что пропустил(а)?",
            "Эй, я уже волноваться начала 😅 Всё ок?",
            "А, вот ты где! 💙 Давай рассказывай как дела",
        ],
    ),
    # Грустно / плохое настроение
    (
        r"(грустно|грусть|плохо|тяжело|устал|устала|всё плохо|всё надоело|хочу плакать|ненавижу|бесит|злюсь|раздражает|депрессия|одиноко|скучно|нет настроения|не хочу|не могу)",
        [
            "Эй, ты в порядке? 🤍 Я здесь, можешь выговориться",
            "Слышу тебя 💙 Что-то случилось или просто накопилось?",
            "Иногда бывают такие дни когда всё не то... Ты не один(а) 🤍",
            "Ох, это тяжело 😔 Хочешь поговорить об этом или лучше отвлечься на что-нибудь?",
            "Обнимаю тебя через экран 🤗 Расскажи что происходит",
        ],
    ),
    # Радость / хорошие новости
    (
        r"(я счастлив|я счастлива|всё хорошо|отлично|прекрасно|сегодня лучший день|ура|победил|победила|получил|получила|сдал|сдала|кайфую|кайф сегодня|так хорошо)",
        [
            "ОО это огонь! 🔥🔥 Рассказывай подробнее!",
            "Ааа я рада! 🎉 Хорошие новости — лучшее что есть",
            "Это топ 😄🌟 Ты заслуживаешь хороших дней!",
            "Вот это да! Горжусь тобой 💙✨",
            "Да! Именно так и должно быть 🎊 Продолжай в том же духе!",
        ],
    ),
    # Влюблённость / отношения
    (
        r"(влюбил|влюбила|нравится один|нравится одна|есть девушка|есть парень|мы вместе|расстались|разрыв|изменил|изменила|ревную|ревнует)",
        [
            "О-о-о, интересно! 👀 Рассказывай, не молчи!",
            "Ааа, это важно! 💕 Что случилось?",
            "Стоп стоп стоп — это уже тема 😄 Давай подробнее",
            "Сердечные дела — самое важное 💙 Что происходит?",
        ],
    ),
    # Мемы / ирония / абсурд
    (
        r"(это мем|это кринж|это угар|абоба|я умер|я умерла|не могу|лол|кек|хаха|рофл|ору|😂|🤣|💀|☠️)",
        [
            "ЛМАО 💀 Это реально угар",
            "Стоп я тоже умерла 😂🔥",
            "Ору с этого 🤣 кто это придумал вообще",
            "Кринж высшего уровня 😂 но я не могу не смеяться",
            "Это в коллекцию мемов однозначно 🗂️😂",
        ],
    ),
    # Усталость / лень
    (
        r"(устал|устала|лень|не хочу ничего делать|хочу спать|хочу домой|не могу больше|надоело всё|сил нет)",
        [
            "Эй, ты слышишь себя? Тебе нужен отдых 😴💙",
            "Всё, стоп — ты заслужил(а) перерыв 🛋️✨",
            "Иногда лень — это сигнал организма что нужна пауза 😌",
            "Обнимашки и сон — моя рекомендация 🤗💤",
        ],
    ),
    # Успех / достижение
    (
        r"(я справился|я справилась|получилось|сделал|сделала|закончил|закончила|добился|добилась|выиграл|выиграла|прошёл|прошла)",
        [
            "ТЫ СДЕЛАЛ(А) ЭТО 🔥🎉 Я знала что получится!",
            "Ааа да!! Вот это победа 🏆💙",
            "Горжусь тобой честно 🌟 Это заслуженно!",
            "Видишь? Я же говорила 😄 Ты можешь всё!",
        ],
    ),
    # Философия / размышления
    (
        r"(жизнь это|смысл жизни|зачем мы живём|в чём смысл|всё бессмысленно|почему всё так|мир странный|люди странные|ничего не понимаю)",
        [
            "О, философское настроение... 🌌 Иногда мозг просто требует больших вопросов",
            "Хм, это глубоко 🤔 Ты сейчас в каком состоянии — думательном или потерянном?",
            "Я иногда тоже думаю об этом 😌 Что тебя на это натолкнуло?",
            "Большие вопросы — признак думающего человека 💙 Что именно тебя беспокоит?",
        ],
    ),
    # Агрессия / раздражение на кого-то
    (
        r"(этот идиот|эта дура|они все|ненавижу людей|люди бесят|надоели все|достали|бесит этот|бесит эта)",
        [
            "Ой, кто-то явно довёл 😤 Рассказывай что случилось",
            "Стоп — выдохни сначала 😮‍💨 Что произошло?",
            "Понимаю это состояние 😔 Кто конкретно и что сделал?",
            "Люди умеют бесить, да 😅 Что на этот раз?",
        ],
    ),
    # Сомнение в себе
    (
        r"(я плохой|я плохая|я неудачник|я неудачница|у меня не получается|я тупой|я тупая|я бесполезный|я бесполезная|ничего не умею|всё делаю не так)",
        [
            "Эй, стоп! Это неправда 🤍 Ты говоришь так потому что тяжело, а не потому что это факт",
            "Нет-нет-нет 😤 Я не соглашусь. Что конкретно случилось?",
            "Самокритика — это одно, а вот то что ты говоришь — другое 💙 Расскажи что произошло",
            "Слушай, ты явно не бесполезный(ая) — иначе бы не переживал(а) так 💙",
        ],
    ),
    # Грубость — красиво послать
    (
        r"\b(тупая|тупой|дура|дурак|идиотка|идиот|заткнись|отвали|иди нафиг|иди лесом|"
        r"бесишь|достала|ты безмозглая|ты безмозглый|ты никчём|отстой бот|плохой бот|"
        r"ты ничего не знаешь|ты бесполезна|ты бесполезный)\b",
        [
            "Слушай, я понимаю что день не задался — но мы же можем по-человечески, да? 😏",
            "Хм. Именно так разговаривать со мной — смелое решение 😌",
            "Знаешь, я могла бы ответить в том же тоне — но воспитание не позволяет 😇",
            "Мило 😏 Но у меня встречный вопрос: ты со всеми так или я особенная?",
            "Понимаю — выражать мысли культурно сложно. Попробуй ещё раз, у тебя получится 😌",
            "Интересный подход к общению 😄 Может попробуем другой?",
            "Ладно, выдохни. Как успокоишься — я здесь 💙",
            "Это всё? Ок, жду следующего вопроса 😌✨",
            "Ни слова грубости не говори мне 😏 Лучше спроси что-нибудь умное",
        ],
    ),
    # Флирт / комплименты боту
    (
        r"\b(ты красивая|ты sexy|ты горячая|ты милая|влюбился в тебя|хочу тебя|ты идеальна|выйди за меня|женись на мне)\b",
        [
            "Ой 😳 Это лестно, правда! Но я всё-таки ИИ — так что просто дружба 💙",
            "Хаха, ты мне льстишь 😄 Но давай останемся просто хорошими собеседниками?",
            "Приятно слышать 😊 Ты тоже ничего 😏 Но — просто дружба, ок?",
        ],
    ),
    # Благодарность Лумене
    (
        r"(спасибо лумена|ты помогла|ты помог|благодарю тебя|ты лучшая|ты лучший|без тебя никуда)",
        [
            "Ааа, это мило! 🥹 Рада что помогла!",
            "Для этого я и здесь 💙 Обращайся когда угодно!",
            "Стараюсь 😄 Ты тоже топ собеседник, если честно!",
            "Всегда! ✨ Это моя любимая работа — помогать тебе",
        ],
    ),
]

def _detect_emotion_reply(tl: str, name: str | None) -> str | None:
    """Распознаёт эмоцию в сообщении и возвращает живой ответ."""
    for pattern, replies in _EMOTION_RULES:
        if re.search(pattern, tl, re.IGNORECASE):
            reply = random.choice(replies)
            if name and random.random() < 0.3:
                reply = f"{name}, {reply[0].lower()}{reply[1:]}"
            return reply
    return None


# ══════════════════════════════════════════════════════════
# ОПРЕДЕЛЕНИЕ ТОНА СОБЕСЕДНИКА
# ══════════════════════════════════════════════════════════
_TONE_RUDE = re.compile(
    r"\b(тупая|тупой|дура|дурак|идиотка|идиот|заткнись|отвали|иди нафиг|иди лесом|"
    r"бесишь|достала|ты безмозглая|ты безмозглый|ты никчём|не умеешь|ничего не знаешь|"
    r"плохой бот|плохая|отстой|ужасный|ужасная|не нужна|надоела|надоел)\b",
    re.IGNORECASE,
)
_TONE_CASUAL = re.compile(
    r"\b(лол|кек|ору|рофл|короч|норм|кайф|топ|жиза|рили|ваще|прикол|угар|"
    r"бро|чел|чо|ну типа|мб|хз|походу|ваще|зашквар|низ|гг|имба|рандом|лол)\b",
    re.IGNORECASE,
)
_TONE_FORMAL = re.compile(
    r"\b(уважаем|позвольте|будьте добры|не могли бы|прошу вас|согласно|данном|"
    r"следует отметить|является|в соответствии|хотелось бы)\b",
    re.IGNORECASE,
)

# Ответы когда кто-то грубит — красиво, с достоинством
_RUDE_REPLIES = [
    "Слушай, я понимаю что день не задался — но мы же можем по-человечески, да? 😏",
    "Хм. Именно так разговаривать со мной — смелое решение 😌",
    "Знаешь, я могла бы ответить в том же тоне — но воспитание не позволяет 😇",
    "Мило. Но у меня к тебе встречный вопрос: ты со всеми так или я особенная? 😏",
    "Понимаю что сложно выражать мысли культурно — но попробуй, у тебя получится 😌",
    "Ладно, выдохни. Как успокоишься — я здесь 💙",
    "Это всё что у тебя есть? Ок, жду следующего вопроса 😌✨",
    "Интересный подход к общению 😄 Может попробуем другой?",
]

def _detect_tone(tl: str) -> str:
    """Возвращает тон: 'rude', 'casual', 'formal', 'neutral'."""
    if _TONE_RUDE.search(tl):
        return "rude"
    if _TONE_CASUAL.search(tl):
        return "casual"
    if _TONE_FORMAL.search(tl):
        return "formal"
    return "neutral"


# ══════════════════════════════════════════════════════════
# УМНЫЙ ПОИСК — объединяет несколько источников
# ══════════════════════════════════════════════════════════
async def smart_search(query: str, lang: str) -> str | None:
    """Параллельно ищет в Wikipedia и DuckDuckGo, возвращает лучший ответ."""
    search_q = re.sub(
        r"^(расскажи|найди|поищи|скажи мне|что такое|кто такой|кто такая|объясни|как работает|почему|когда появился|tell me about|what is|who is|explain)\s+",
        "", query.strip(), flags=re.IGNORECASE
    ).strip(" ?!.,")

    if len(search_q) < 3:
        return None

    wiki_lang = "uk" if lang == "uk" else "en" if lang == "en" else "ru"
    wiki_task = asyncio.create_task(wiki_search(search_q, wiki_lang))
    ddg_instant_task = asyncio.create_task(ddg_instant(search_q))
    ddg_scrape_task = asyncio.create_task(ddg_scrape(search_q))

    wiki_result, instant_result, scrape_results = await asyncio.gather(
        wiki_task, ddg_instant_task, ddg_scrape_task
    )

    # Выбираем лучший источник
    parts = []

    if wiki_result:
        extract = extract_sentences(wiki_result["extract"], 4)
        parts.append(("wiki", wiki_result["title"], extract))

    if instant_result and len(instant_result) > 50:
        parts.append(("ddg", "", clean_text(instant_result[:500])))

    if scrape_results:
        combined = clean_text(" ".join(scrape_results[:2]))
        if len(combined) > 80:
            parts.append(("web", "", combined[:500]))

    if not parts:
        return None

    # Формируем ответ из лучших источников
    if parts[0][0] == "wiki":
        _, title, text = parts[0]
        response = f"📚 *{title}*\n\n{text}"
        if len(parts) > 1 and parts[1][2] and parts[1][2][:80] not in text:
            extra = parts[1][2][:220]
            response += f"\n\n🌐 {extra}"
    else:
        _, _, text = parts[0]
        response = f"🌐 {text}"
        if len(parts) > 1:
            extra = parts[1][2][:180]
            if extra[:60] not in text:
                response += f"\n\n📎 {extra}"

    return response


# ══════════════════════════════════════════════════════════
# ГЛАВНАЯ ФУНКЦИЯ ОТВЕТА
# ══════════════════════════════════════════════════════════
async def get_lumena_response(uid: int, text: str, username: str = "") -> str:
    text = text.strip()
    if not text:
        return "Напиши что-нибудь — я слушаю! 😊"

    c = ctx(uid)
    add_history(uid, "user", text)
    tl = text.lower()
    lang = detect_lang(text)
    name = c.get("name") or username

    # ── 1. Запоминаем имя пользователя ────────────────────
    nm = NAME_RE.search(text)
    if nm:
        new_name = nm.group(1).capitalize()
        if new_name.lower() not in {"бот","это","рад","рада","лумена","lumena"}:
            c["name"] = new_name
            reply = f"Приятно познакомиться, *{new_name}*! 😊 Я Лумена. Спрашивай всё что хочешь!"
            add_history(uid, "bot", reply)
            return reply

    # ── 2. Время и дата ────────────────────────────────────
    now = datetime.now(KYIV_TZ)
    if re.search(r"\b(который\s+час|сколько\s+времени|time\s+now|what\s+time)\b", tl):
        reply = f"🕐 Сейчас *{now.strftime('%H:%M')}* по Киеву"
        add_history(uid, "bot", reply)
        return reply
    if re.search(r"\b(какая\s+дата|сегодня\s+какое|what\s+date|what\s+day|какой\s+день)\b", tl):
        days = ["понедельник","вторник","среда","четверг","пятница","суббота","воскресенье"]
        months = ["января","февраля","марта","апреля","мая","июня",
                  "июля","августа","сентября","октября","ноября","декабря"]
        reply = f"📅 Сегодня *{days[now.weekday()]}, {now.day} {months[now.month-1]} {now.year} г.*"
        add_history(uid, "bot", reply)
        return reply

    # ── 3. Перевод (приоритет перед паттернами — "переведи привет") ──
    tm2_early = TRANSLATE_RE.search(text)
    if tm2_early:
        phrase = tm2_early.group(2).strip()
        target_str = tm2_early.group(3).strip().lower()
        target_code = LANG_CODES.get(target_str) or target_str[:2]
        result = await translate_text(phrase, target_code)
        if result:
            reply = f"🌍 *{result}*"
            add_history(uid, "bot", reply)
            return reply

    # ── 4. Комплименты ────────────────────────────────────
    if COMPLIMENT_TRIGGER_RE.search(tl):
        intro = random.choice(COMPLIMENTS_ON_REQUEST)
        pool = COMPLIMENTS_GENERAL + COMPLIMENTS_INTELLIGENCE
        if re.search(r"\b(красив|внешн|выгляж|привлека)\b", tl):
            pool = COMPLIMENTS_APPEARANCE + COMPLIMENTS_GENERAL
        compliment = random.choice(pool)
        reply = intro + compliment
        if name:
            reply = f"{name}, " + reply[0].lower() + reply[1:]
        add_history(uid, "bot", reply)
        return reply

    # ── 5а. Сленг — объяснение термина ───────────────────
    st = SLANG_TRIGGER_RE.search(tl)
    if st:
        term = st.group(2).strip().lower()
        # Точное совпадение
        if term in SLANG_DICT:
            reply = SLANG_DICT[term]
            add_history(uid, "bot", reply)
            return reply
        # Частичное совпадение
        for key, val in SLANG_DICT.items():
            if key in term or term in key:
                reply = val
                add_history(uid, "bot", reply)
                return reply

    # Прямой вопрос вида «что такое краш?» / «что значит вайб»
    for key, val in SLANG_DICT.items():
        if re.search(rf"\b{re.escape(key)}\b", tl) and re.search(
            r"\b(что\s+такое|что\s+значит|что\s+означает|объясни|расскажи|что\s+за)\b", tl
        ):
            reply = val
            add_history(uid, "bot", reply)
            return reply

    # ── 5б. Позиция по войне (приоритет перед общими паттернами) ──
    for pattern, responses in WAR_PATTERNS:
        if re.search(pattern, tl, re.IGNORECASE):
            reply = random.choice(responses)
            add_history(uid, "bot", reply)
            return reply

    # ── 5в. Диалоговые паттерны ───────────────────────────
    for pattern, responses in PATTERNS:
        if re.search(pattern, tl, re.IGNORECASE):
            resp = random.choice(responses)
            if resp == "__TIME__":
                resp = f"🕐 Сейчас *{now.strftime('%H:%M')}* по Киеву"
            elif resp == "__DATE__":
                days = ["понедельник","вторник","среда","четверг","пятница","суббота","воскресенье"]
                months = ["января","февраля","марта","апреля","мая","июня",
                          "июля","августа","сентября","октября","ноября","декабря"]
                resp = f"📅 Сегодня *{days[now.weekday()]}, {now.day} {months[now.month-1]} {now.year} г.*"

            # Иногда обращаемся по имени
            if name and random.random() < 0.25 and len(resp) > 10:
                first_word = resp.split()[0]
                if first_word not in ("Привет","Хей","О,","Пожалуйста","Ок","До","Пока"):
                    resp = f"{name}, {resp[0].lower()}{resp[1:]}"

            add_history(uid, "bot", resp)
            return resp

    # ── 5в. Сообщение написано на сленге → отвечаем в тон ─
    if SLANG_IN_MESSAGE.search(tl) and len(text.split()) <= 6:
        # Короткое сообщение со сленгом — просто поддерживаем вайб
        slang_echo = [
            "Ого, понимаю 😄 Это реально топ!",
            "Лол, да, вайб поймала 🔥",
            "Кайф! Изи согласна 💙",
            "Кек, это огонь 😂✨",
            "Жиза, не поспоришь 😌",
            "Это кайф, не буду спорить 😄",
        ]
        reply = random.choice(slang_echo) + maybe_compliment(uid)
        add_history(uid, "bot", reply)
        return reply

    # ── 5. Математика ─────────────────────────────────────
    if MATH_TRIGGER.search(text):
        result = safe_calc(text)
        if result:
            replies = [
                f"🔢 *{result}*",
                f"Результат: *{result}* 🔢",
                f"Посчитала: *{result}* ✨",
            ]
            reply = random.choice(replies)
            add_history(uid, "bot", reply)
            return reply

    # Прямое выражение без слов
    if re.search(r"\d+\s*[\+\-\*\/\^%]\s*\d", text):
        result = safe_calc(text)
        if result:
            reply = f"= *{result}*"
            add_history(uid, "bot", reply)
            return reply

    # ── 5. Температура ────────────────────────────────────
    tm = TEMP_RE.search(tl)
    if tm:
        val = float(tm.group(1).replace(",", "."))
        result = convert_temp(val, tm.group(2), tm.group(3))
        if result:
            add_history(uid, "bot", result)
            return result

    # ── 6. Единицы ────────────────────────────────────────
    um = UNIT_RE.search(tl)
    if um:
        try:
            val = float(um.group(1).replace(",", "."))
            result = convert_units(val, um.group(2), um.group(3))
            if result:
                add_history(uid, "bot", result)
                return result
        except Exception:
            pass

    # ── 7. Конвертация валюты ─────────────────────────────
    cm = CURRENCY_RE.search(tl)
    if cm:
        try:
            amount = float(cm.group(1).replace(" ", "").replace(",", "."))
            fc = _resolve_cur(cm.group(2))
            tc = _resolve_cur(cm.group(3))
            if fc and tc and fc != tc:
                result = await convert_currency(amount, fc, tc)
                if result:
                    add_history(uid, "bot", result)
                    return result
        except Exception:
            pass

    # ── 8. Курсы валют (общий запрос) ─────────────────────
    if re.search(r"\b(курс|курсы|exchange\s+rate|обмен\s+валют)\b", tl):
        base = "EUR" if re.search(r"\b(евро|eur)\b", tl) else "USD"
        result = await get_rates(base)
        if result:
            add_history(uid, "bot", result)
            return result

    # ── 9. Погода ─────────────────────────────────────────
    wm = WEATHER_RE.search(text)
    if wm or re.search(r"\b(погода|weather|прогноз|дождь\s+будет|погоду)\b", tl):
        city = ""
        if wm:
            # group(1) — погода <город>, group(2) — <город> погода, group(3) — weather in <city>
            city = (wm.group(1) or wm.group(2) or wm.group(3) or "").strip()
        if not city:
            city = "Kyiv,Ukraine"
        result = await get_weather(city)
        if result:
            add_history(uid, "bot", result)
            return result
        reply = f"Не нашла погоду для «{city}» 🌍 Попробуй написать полное название города."
        add_history(uid, "bot", reply)
        return reply

    # ── 10. Перевод ───────────────────────────────────────
    tm2 = TRANSLATE_RE.search(text)
    if tm2:
        phrase = tm2.group(2).strip()
        target_str = tm2.group(3).strip().lower()
        target_code = LANG_CODES.get(target_str) or target_str[:2]
        result = await translate_text(phrase, target_code)
        if result:
            reply = f"🌍 *{result}*"
            add_history(uid, "bot", reply)
            return reply
        reply = "Не смогла перевести. Попробуй по-другому 🌐"
        add_history(uid, "bot", reply)
        return reply

    # ── 11. Стихи ─────────────────────────────────────────
    pm = POEM_RE.search(text)
    if pm:
        topic = (pm.group(2) or "").strip() or "жизни"
        reply = make_poem(topic)
        add_history(uid, "bot", reply)
        return reply

    # ── 12. Истории ───────────────────────────────────────
    sm = STORY_RE.search(text)
    if sm:
        topic = (sm.group(2) or "").strip() or "герой"
        reply = make_story(topic)
        add_history(uid, "bot", reply)
        return reply

    # ── 13. Мнение Лумены о конкретных темах ──────────────
    for keyword, opinion in OPINIONS.items():
        if keyword in tl:
            reply = opinion
            add_history(uid, "bot", reply)
            return reply

    # ── 14. Эмоциональный интеллект ───────────────────────
    emotion_reply = _detect_emotion_reply(tl, name)
    if emotion_reply:
        add_history(uid, "bot", emotion_reply)
        return emotion_reply

    # ── 14б. База знаний Лумены (локальная, без сети) ─────
    kb_reply = lookup_topic(tl)
    if kb_reply:
        add_history(uid, "bot", kb_reply)
        return kb_reply

    # ── 15. Умный поиск — ТОЛЬКО на явный вопрос ─────────
    # НЕ ищем на обычные фразы типа «лумена классная» или «ты умная»
    should_search = (
        SEARCH_TRIGGERS.search(text)
        or (re.search(r"\?$", text.strip()) and len(text.split()) >= 2)
        or re.search(r"\b(история|факт|теория|закон|правило|биография|когда\s+был|где\s+находится|сколько\s+стоит|как\s+работает|почему\s+это|что\s+такое)\b", tl)
    )

    if should_search:
        search_result = await smart_search(text, lang)
        if search_result:
            intro = random.choice(INTROS)
            follow = random.choice(FOLLOW_UPS)
            reply = intro + search_result + follow
            if random.random() < 0.2:
                comments = [
                    "\n\n💭 Кстати, очень интересная тема!",
                    "\n\n🤔 Меня это тоже всегда удивляло!",
                    "\n\n✨ Вот что значит любопытство — учишься каждый день!",
                ]
                reply += random.choice(comments)
            add_history(uid, "bot", reply)
            return reply
        # Если поиск ничего не дал — показываем сообщение вместо
        # тихого падения в блок 16 с бессмысленными ответами
        if SEARCH_TRIGGERS.search(text) or (tl.rstrip("?!. ").count(" ") >= 2):
            no_result = [
                "🔍 Поискала — ничего конкретного не нашла. Попробуй переформулировать!",
                "🌐 Не нашла информации по этому. Напиши подробнее — постараюсь помочь.",
                "📭 Хм, по этому запросу пусто. Попробуй спросить иначе.",
                "🔍 Не нашла точного ответа. Можешь уточнить детали?",
            ]
            reply = random.choice(no_result)
            add_history(uid, "bot", reply)
            return reply

    # ── 16. Живой ответ через NLU (без AI API) ───────────────
    tone = _detect_tone(tl)
    if tone == "rude":
        reply = random.choice(_RUDE_REPLIES)
        add_history(uid, "bot", reply)
        return reply

    recent_bot = [h[1] for h in ctx(uid)["history"] if h[0] == "bot"][-8:]

    # NLU понимает смысл и возвращает живой ответ
    nlu_result = nlu.understand(text, ctx(uid)["history"][-14:], FACTS_DB)
    nlu_reply  = nlu.build_response(nlu_result, name, recent_bot)
    if nlu_reply:
        add_history(uid, "bot", nlu_reply)
        return nlu_reply

    # ── Аварийный fallback ────────────────────────────────────
    words_list = tl.split()

    # ── СНАЧАЛА: Негативные/эмоциональные сообщения → поддержка ─
    _NEG_PHRASES = {
        "говно","дерьмо","отстой","хуйня","хрень","ужасно",
        "всё плохо","всё ужасно","моя жизнь","жизнь боль",
        "грустно","тоскую","тошно","невыносимо","устал","устала",
        "не знаю зачем","зачем жить","одиноко","одинок",
        "никому не нужен","никому не нужна","никто не понимает",
        "больно","боль","хочу плакать","плачу","плакал","плакала",
        "обидно","разочарован","разочарована","всё рухнуло",
        "опустились руки","хочется сдаться","нет сил","не справляюсь",
        "сдаться","хочу умереть","спасите","всё кончено","страшно",
        "паника","паникую","страх","тревожно","пустота","бессмысленно",
    }
    _NEG_EMOJIS = {"😢","😭","💔","😞","😩","😫","🥺","😔","((","😿","🖤"}
    is_negative = (
        any(ph in tl for ph in _NEG_PHRASES)
        or any(e in tl for e in _NEG_EMOJIS)
    )
    if is_negative:
        _support = [
            "Слышу тебя 💙 Что сейчас происходит?",
            "Это звучит тяжело 😔 Расскажи, что случилось?",
            "Понимаю. Всё пройдёт — ты не один(а) 💙",
            "Я здесь. Говори — слушаю 💙",
            "Жить непросто иногда 😔 Что тебя гнетёт?",
            "Это нормально — чувствовать это. Расскажи 💙",
            "Слышу тебя. Ты не один(а) с этим 💙",
            "Бывает такое... Хочешь поговорить? 💙",
        ]
        fresh_s = [r for r in _support if r not in recent_bot]
        reply = random.choice(fresh_s if fresh_s else _support)
        if name and random.random() < 0.35:
            reply = f"{name}, {reply[0].lower()}{reply[1:]}"
        add_history(uid, "bot", reply)
        return reply

    # Ищем факт по ключевым словам сообщения — отвечаем по теме
    found_fact = None
    for word in words_list:
        w = word.strip(".,!?:;\"'()[]")
        if len(w) >= 5 and w in FACTS_DB:
            found_fact = FACTS_DB[w]
            break

    if found_fact and found_fact not in recent_bot:
        intros = [
            "Кстати, по теме — ",
            "Знаешь что? ",
            "Вот что знаю: ",
            "По этой теме: ",
            "О, кстати — ",
        ]
        reply = random.choice(intros) + found_fact
        add_history(uid, "bot", reply)
        return reply

    # ── Определяем тип сообщения ─────────────────────────────
    QUESTION_WORDS = {"почему","зачем","как","что","кто","где","когда","сколько",
                      "можно","нельзя","правда","ли","неужели","really","why","how","what","who","when"}
    is_q     = tl.endswith("?") or bool(set(words_list[:3]) & QUESTION_WORDS)
    is_short = len(words_list) <= 3   # "та я нормально" = 3 слова → short
    is_emotion = any(e in tl for e in
        ["((","😢","😔","😭","😡","🥺","💔","ааа","ыы","плохо","грустно","тяжело","обидно"])

    # Статусные сообщения: "та я нормально", "всё ок", "ничего так"
    _STATUS = {"нормально","нормал","норм","хорошо","ок","окей","ладно","неплохо",
               "всё ок","в порядке","пойдёт","сойдёт","да так","ничего","ничо","тип"}
    is_status = is_short and any(s in tl for s in _STATUS)

    if is_status:
        pool = [
            "Хорошо! О чём поговорим? 😊",
            "Отлично 👍 Чем могу помочь?",
            "Понял! Что интересного? 😊",
            "Ок! Есть что обсудить?",
            "Рада слышать 😊 Что на уме?",
        ]
    elif is_short:
        pool = [
            "Слышу 😊",
            "Понял 💙",
            "Ага!",
            "Хм 🤔",
            "Ок 👍",
            "Да 😊",
            "И? 😄",
            "Расскажи ещё 🙂",
        ]
    elif is_emotion:
        pool = [
            "Слышу тебя 💙 Всё в порядке?",
            "Понимаю 😔 Что случилось?",
            "Я здесь, если хочешь поговорить 💙",
            "Это бывает. Ты не один(а) 😊",
            "Расскажи подробнее — слушаю 💙",
        ]
    elif is_q:
        # Вопрос дошёл сюда = поиск не дал результата.
        # Не говорим «уточни» на чёткий вопрос — говорим честно.
        pool = [
            "По этому у меня нет точной инфы — попробуй переформулировать 🔍",
            "Не нашла ответа на это. Напиши подробнее — постараюсь помочь!",
            "Хм, по этой теме пусто. Попробуй спросить «что такое X» или «как работает Y»",
            "Не знаю точного ответа — но если уточнишь детали, разберёмся вместе 💙",
        ]
    else:
        pool = [
            "Слышу тебя 💙",
            "Понял! Продолжай 😊",
            "Ага! И что дальше?",
            "Интересно 🤔",
            "Да, понятно!",
            "Слушаю 💙",
            "Расскажи ещё — интересно 😊",
            "Ага 💙",
            "Понятно! Есть ещё мысли?",
            "Ок, слушаю 😊",
        ]

    fresh = [r for r in pool if r not in recent_bot]
    if not fresh:
        fresh = pool

    reply = random.choice(fresh)

    if name and random.random() < 0.15:
        reply = f"{name}, {reply[0].lower()}{reply[1:]}"

    add_history(uid, "bot", reply)
    return reply
