# -*- coding: ascii -*-
# ==========================================================
# SOBUJ BARI MESSENGER BOT
# CLEAN FIXED VERSION
# ==========================================================

import os
import re
import json
import time
import uuid
import random
import logging
import requests

from datetime import datetime
from flask import Flask, request
from dotenv import load_dotenv


# ==========================================================
# LOAD ENV
# ==========================================================

load_dotenv()


# ==========================================================
# FLASK
# ==========================================================

app = Flask(__name__)


# ==========================================================
# FACEBOOK CONFIG
# ==========================================================

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "")
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN", "")
GRAPH_API = "https://graph.facebook.com/v23.0/me/messages"


# ==========================================================
# BOT CONFIG
# ==========================================================

BOT_NAME = "\u09b8\u09ac\u09c1\u099c \u09ac\u09be\u09a1\u09bc\u09bf Assistant"
PAGE_NAME = "\u09b8\u09ac\u09c1\u099c \u09ac\u09be\u09a1\u09bc\u09bf"
DEFAULT_LANGUAGE = "bn"
VERSION = "1.0.1"


# ==========================================================
# FILES
# ==========================================================

DATA_DIR = "data"
PRODUCT_FILE = os.path.join(DATA_DIR, "products.json")
FAQ_FILE = os.path.join(DATA_DIR, "faq.json")
ORDER_FILE = os.path.join(DATA_DIR, "orders.json")
LOG_FILE = os.path.join(DATA_DIR, "bot.log")
BACKUP_DIR = os.path.join(DATA_DIR, "backup")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(BACKUP_DIR, exist_ok=True)


# ==========================================================
# LOGGING
# ==========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("SabujBariBot")


def log_info(message):
    logger.info(message)


def log_error(message):
    logger.error(message)


# ==========================================================
# GLOBAL MEMORY
# ==========================================================

USERS = {}
ORDER_STEPS = {}
UNKNOWN_COUNTER = {}

PRODUCTS = []
ORDERS = []
FAQ_DATABASE = []

PRODUCT_INDEX = {}
PRODUCT_ALIASES = {}
FAQ_INDEX = {}
FAQ_CACHE = {}


# ==========================================================
# SETTINGS
# ==========================================================

MAX_HISTORY = 20
ENABLE_TYPING = True
MIN_TYPING_DELAY = 0.8
MAX_TYPING_DELAY = 1.8


# ==========================================================
# DEFAULT REPLIES
# ==========================================================

DEFAULT_REPLY = (
    "\u09a6\u09c1\u0983\u0996\u09bf\u09a4, \u0986\u09ae\u09bf \u09ac\u09bf\u09b7\u09af\u09bc\u099f\u09bf \u09ac\u09c1\u099d\u09a4\u09c7 \u09aa\u09be\u09b0\u09bf\u09a8\u09bf\u0964 "
    "\u0985\u09a8\u09c1\u0997\u09cd\u09b0\u09b9 \u0995\u09b0\u09c7 \u09aa\u09cd\u09b0\u09cb\u09a1\u09be\u0995\u09cd\u099f\u09c7\u09b0 \u09a8\u09be\u09ae \u09ac\u09be \u09aa\u09cd\u09b0\u09b6\u09cd\u09a8\u099f\u09bf \u0986\u09ac\u09be\u09b0 \u09b2\u09bf\u0996\u09c1\u09a8\u0964"
)

ORDER_SUCCESS_REPLY = (
    "\u2705 \u0986\u09aa\u09a8\u09be\u09b0 \u0985\u09b0\u09cd\u09a1\u09be\u09b0 \u09b8\u09ab\u09b2\u09ad\u09be\u09ac\u09c7 \u0997\u09cd\u09b0\u09b9\u09a3 \u0995\u09b0\u09be \u09b9\u09af\u09bc\u09c7\u099b\u09c7\u0964 "
    "\u0986\u09ae\u09be\u09a6\u09c7\u09b0 \u09aa\u09cd\u09b0\u09a4\u09bf\u09a8\u09bf\u09a7\u09bf \u09a6\u09cd\u09b0\u09c1\u09a4 \u09af\u09cb\u0997\u09be\u09af\u09cb\u0997 \u0995\u09b0\u09ac\u09c7\u09a8\u0964"
)

HUMAN_REPLY = (
    "\U0001f468\u200d\U0001f4bc \u0986\u09aa\u09a8\u09be\u09b0 \u0985\u09a8\u09c1\u09b0\u09cb\u09a7\u099f\u09bf \u0986\u09ae\u09be\u09a6\u09c7\u09b0 \u099f\u09bf\u09ae\u09c7\u09b0 \u0995\u09be\u099b\u09c7 \u09aa\u09be\u09a0\u09be\u09a8\u09cb \u09b9\u09af\u09bc\u09c7\u099b\u09c7\u0964\n\n"
    "\u0985\u09a8\u09c1\u0997\u09cd\u09b0\u09b9 \u0995\u09b0\u09c7 \u098f\u0995\u099f\u09c1 \u0985\u09aa\u09c7\u0995\u09cd\u09b7\u09be \u0995\u09b0\u09c1\u09a8\u0964\n\n"
    "\u0986\u09ae\u09be\u09a6\u09c7\u09b0 \u09aa\u09cd\u09b0\u09a4\u09bf\u09a8\u09bf\u09a7\u09bf \u0996\u09c1\u09ac \u09a6\u09cd\u09b0\u09c1\u09a4 \u0986\u09aa\u09a8\u09be\u09b0 \u09b8\u09be\u09a5\u09c7 \u09af\u09cb\u0997\u09be\u09af\u09cb\u0997 \u0995\u09b0\u09ac\u09c7\u09a8\u0964 \U0001f60a"
)


# ==========================================================
# JSON DATABASE
# ==========================================================

def ensure_json_file(path, default_data):
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(default_data, f, ensure_ascii=False, indent=4)


ensure_json_file(PRODUCT_FILE, [])
ensure_json_file(FAQ_FILE, [])
ensure_json_file(ORDER_FILE, [])


def load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception as e:
        log_error(f"Load JSON Error ({path}) : {e}")
        return []


def save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        log_error(f"Save JSON Error ({path}) : {e}")
        return False


# ==========================================================
# NORMALIZE ENGINE
# ==========================================================

BANGLA_DIGITS = {
    0x09E6: "0",
    0x09E7: "1",
    0x09E8: "2",
    0x09E9: "3",
    0x09EA: "4",
    0x09EB: "5",
    0x09EC: "6",
    0x09ED: "7",
    0x09EE: "8",
    0x09EF: "9",
}


def normalize(text):
    if text is None:
        return ""

    text = str(text).translate(BANGLA_DIGITS).lower().strip()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^\w\s\u0980-\u09FF]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def safe_text(text):
    return normalize(text)


def is_empty(text):
    return len(normalize(text)) == 0


def keyword_match(message, keywords):
    """
    General contains matcher.
    Product/FAQ matching can use partial phrases.
    """
    msg = normalize(message)

    for keyword in keywords:
        key = normalize(keyword)
        if key and key in msg:
            return True

    return False


def intent_keyword_match(message, keywords):
    """
    Safer matcher for HUMAN intents.
    Prevents 'phone' from matching 'headphone'.
    """
    msg = normalize(message)

    if not msg:
        return False

    padded_msg = f" {msg} "

    for keyword in keywords:
        key = normalize(keyword)

        if not key:
            continue

        if f" {key} " in padded_msg:
            return True

    return False


# ==========================================================
# USER SESSION & MEMORY
# ==========================================================

def get_user(user_id):
    if user_id not in USERS:
        USERS[user_id] = {
            "id": user_id,
            "language": DEFAULT_LANGUAGE,
            "last_message": "",
            "last_product": "",
            "last_reply": "",
            "history": [],
            "human_mode": False,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }

    return USERS[user_id]


def save_message(user_id, message):
    user = get_user(user_id)

    user["last_message"] = message
    user["updated_at"] = datetime.now().isoformat()

    user["history"].append({
        "time": datetime.now().isoformat(),
        "message": message
    })

    if len(user["history"]) > MAX_HISTORY:
        user["history"] = user["history"][-MAX_HISTORY:]


def set_last_product(user_id, product_name):
    user = get_user(user_id)
    user["last_product"] = product_name
    user["updated_at"] = datetime.now().isoformat()


def get_last_product(user_id):
    return get_user(user_id)["last_product"]


def enable_human_mode(user_id):
    get_user(user_id)["human_mode"] = True


def disable_human_mode(user_id):
    get_user(user_id)["human_mode"] = False


def is_human_mode(user_id):
    return get_user(user_id)["human_mode"]


# ==========================================================
# PRODUCT DATABASE ENGINE
# ==========================================================

def get_product_by_name(name):
    name = normalize(name)

    for product in PRODUCTS:
        if normalize(product.get("name", "")) == name:
            return product

    return None


def get_product_by_id(product_id):
    for product in PRODUCTS:
        if product.get("id") == product_id:
            return product

    return None


def is_available(product):
    return normalize(product.get("stock", "")) == "available"


def build_product_index():
    PRODUCT_INDEX.clear()

    for product in PRODUCTS:
        if not product.get("active", True):
            continue

        name = normalize(product.get("name", ""))

        if name:
            PRODUCT_INDEX[name] = product

        for keyword in product.get("keywords", []):
            key = normalize(keyword)

            if key:
                PRODUCT_INDEX[key] = product


def build_alias_index():
    PRODUCT_ALIASES.clear()

    for product in PRODUCTS:
        if not product.get("active", True):
            continue

        product_name = product.get("name", "")

        if product_name:
            PRODUCT_ALIASES[normalize(product_name)] = product_name

        for keyword in product.get("keywords", []):
            key = normalize(keyword)

            if key:
                PRODUCT_ALIASES[key] = product_name


def rebuild_search_engine():
    build_product_index()
    build_alias_index()


def find_product(message):
    msg = normalize(message)

    if msg in PRODUCT_INDEX:
        return PRODUCT_INDEX[msg]

    # Prefer longer/more-specific keywords first.
    for keyword in sorted(PRODUCT_INDEX.keys(), key=len, reverse=True):
        if keyword and keyword in msg:
            return PRODUCT_INDEX[keyword]

    return None


def find_product_by_alias(message):
    msg = normalize(message)

    for alias in sorted(PRODUCT_ALIASES.keys(), key=len, reverse=True):
        if alias and alias in msg:
            return get_product_by_name(PRODUCT_ALIASES[alias])

    return None


def smart_product_search(message):
    product = find_product(message)

    if product:
        return product

    return find_product_by_alias(message)


def suggest_products(message):
    msg = normalize(message)
    results = []

    for product in PRODUCTS:
        score = 0

        for keyword in product.get("keywords", []):
            key = normalize(keyword)

            if key and key in msg:
                score += 1

        if score:
            results.append((score, product))

    results.sort(reverse=True, key=lambda x: x[0])
    return [item[1] for item in results[:3]]


# ==========================================================
# PRODUCT REPLY ENGINE
# ==========================================================

PRICE_KEYWORDS = [
    "price",
    "\u09a6\u09be\u09ae",
    "\u09ae\u09c2\u09b2\u09cd\u09af",
    "offer",
    "\u0995\u09a4",
    "tk",
    "\u09f3"
]

COLOR_KEYWORDS = [
    "color",
    "colour",
    "\u09b0\u0982",
    "\u0995\u09be\u09b2\u09be\u09b0"
]

STOCK_KEYWORDS = [
    "stock",
    "\u09b8\u09cd\u099f\u0995",
    "available",
    "\u0986\u099b\u09c7"
]

DELIVERY_KEYWORDS = [
    "delivery",
    "\u09a1\u09c7\u09b2\u09bf\u09ad\u09be\u09b0\u09bf",
    "\u0995\u09a4 \u09a6\u09bf\u09a8\u09c7",
    "courier"
]

WARRANTY_KEYWORDS = [
    "warranty",
    "\u0997\u09cd\u09af\u09be\u09b0\u09be\u09a8\u09cd\u099f\u09bf",
    "\u0993\u09af\u09bc\u09be\u09b0\u09c7\u09a8\u09cd\u099f\u09bf"
]

FEATURE_KEYWORDS = [
    "feature",
    "features",
    "\u09b8\u09cd\u09aa\u09c7\u09b8\u09bf\u09ab\u09bf\u0995\u09c7\u09b6\u09a8",
    "\u0995\u09bf \u0995\u09bf \u0986\u099b\u09c7"
]


def format_product_reply(product):
    features = product.get("features", [])
    colors = product.get("colors", [])

    feature_text = "\n".join(f"\u2022 {item}" for item in features)
    color_text = ", ".join(colors) if colors else "Not Available"

    return (
        f"\U0001f6cd\ufe0f {product.get('name', '')}\n\n"
        f"\U0001f4b0 \u09ae\u09c2\u09b2\u09cd\u09af: {product.get('price', '')}\n\n"
        f"\U0001f4e6 Stock: {product.get('stock', 'Available')}\n\n"
        f"\U0001f4dd {product.get('description', '')}\n\n"
        f"\U0001f3a8 Color:\n{color_text}\n\n"
        f"\u2728 \u09aa\u09cd\u09b0\u09a7\u09be\u09a8 Features:\n\n{feature_text}\n\n"
        f"\U0001f6e1\ufe0f Warranty:\n{product.get('warranty', 'No Warranty')}\n\n"
        f"\U0001f69a Delivery:\n{product.get('delivery', '\u09e8\u2013\u09ea \u09a6\u09bf\u09a8')}\n\n"
        f"\U0001f4b3 Delivery Charge:\n\u09f3{product.get('delivery_charge', '100')}\n\n"
        '\u0985\u09b0\u09cd\u09a1\u09be\u09b0 \u0995\u09b0\u09a4\u09c7 "\u0985\u09b0\u09cd\u09a1\u09be\u09b0 \u0995\u09b0\u09a4\u09c7 \u099a\u09be\u0987" \u09b2\u09bf\u0996\u09c1\u09a8\u0964'
    )


def is_price_question(message):
    return keyword_match(message, PRICE_KEYWORDS)


def price_reply(product):
    return (
        f"\U0001f4b0 {product.get('name', '')}\n\n"
        f"\u09ae\u09c2\u09b2\u09cd\u09af\u0983 {product.get('price', '')}"
    )


def color_reply(product):
    colors = product.get("colors", [])

    if not colors:
        return "\u098f\u0987 \u09aa\u09cd\u09b0\u09cb\u09a1\u09be\u0995\u09cd\u099f\u09c7\u09b0 Color \u09a4\u09a5\u09cd\u09af \u09a8\u09c7\u0987\u0964"

    return "\U0001f3a8 Available Color:\n\n" + "\n".join(f"\u2022 {c}" for c in colors)


def stock_reply(product):
    return f"\U0001f4e6 Stock : {product.get('stock', 'Available')}"


def delivery_reply(product):
    return (
        "\U0001f69a Delivery Time\n\n"
        f"{product.get('delivery', '\u09e8\u2013\u09ea \u09a6\u09bf\u09a8')}\n\n"
        "\U0001f4b3 Delivery Charge\n\n"
        f"\u09f3{product.get('delivery_charge', '100')}"
    )


def warranty_reply(product):
    return (
        "\U0001f6e1\ufe0f Warranty\n\n"
        f"{product.get('warranty', 'No Warranty')}"
    )


def feature_reply(product):
    features = product.get("features", [])

    if not features:
        return "\u098f\u0987 \u09aa\u09cd\u09b0\u09cb\u09a1\u09be\u0995\u09cd\u099f\u09c7\u09b0 Features \u09a4\u09a5\u09cd\u09af \u09a8\u09c7\u0987\u0964"

    return "\u2728 \u09aa\u09cd\u09b0\u09a7\u09be\u09a8 Features\n\n" + "\n".join(
        f"\u2022 {item}" for item in features
    )


def product_reply(user_id, message):
    product = smart_product_search(message)

    if not product:
        return None

    set_last_product(user_id, product.get("name", ""))

    if is_price_question(message):
        return price_reply(product)

    if keyword_match(message, COLOR_KEYWORDS):
        return color_reply(product)

    if keyword_match(message, STOCK_KEYWORDS):
        return stock_reply(product)

    if keyword_match(message, DELIVERY_KEYWORDS):
        return delivery_reply(product)

    if keyword_match(message, WARRANTY_KEYWORDS):
        return warranty_reply(product)

    if keyword_match(message, FEATURE_KEYWORDS):
        return feature_reply(product)

    return format_product_reply(product)


def continue_last_product(user_id, message):
    last = get_last_product(user_id)

    if not last:
        return None

    product = get_product_by_name(last)

    if not product:
        return None

    if is_price_question(message):
        return price_reply(product)

    if keyword_match(message, COLOR_KEYWORDS):
        return color_reply(product)

    if keyword_match(message, STOCK_KEYWORDS):
        return stock_reply(product)

    if keyword_match(message, DELIVERY_KEYWORDS):
        return delivery_reply(product)

    if keyword_match(message, WARRANTY_KEYWORDS):
        return warranty_reply(product)

    if keyword_match(message, FEATURE_KEYWORDS):
        return feature_reply(product)

    return None


def handle_product_message(user_id, message):
    reply = product_reply(user_id, message)

    if reply:
        return reply

    return continue_last_product(user_id, message)


# ==========================================================
# PRODUCT RECOMMENDATION
# ==========================================================

def list_products(limit=None):
    items = PRODUCTS[:limit] if limit else PRODUCTS

    if not items:
        return "\u098f\u0987 \u09ae\u09c1\u09b9\u09c2\u09b0\u09cd\u09a4\u09c7 \u0995\u09cb\u09a8\u09cb \u09aa\u09cd\u09b0\u09cb\u09a1\u09be\u0995\u09cd\u099f \u09b2\u09cb\u09a1 \u0995\u09b0\u09be \u09a8\u09c7\u0987\u0964"

    text = "\U0001f6cd\ufe0f \u0986\u09ae\u09be\u09a6\u09c7\u09b0 \u09aa\u09cd\u09b0\u09cb\u09a1\u09be\u0995\u09cd\u099f\u09b8\u09ae\u09c2\u09b9\n\n"

    for product in items:
        text += f"\u2022 {product.get('name', '')} \u2014 {product.get('price', '')}\n"

    return text.strip()


def cheapest_product():
    if not PRODUCTS:
        return None

    product = min(
        PRODUCTS,
        key=lambda x: int(x.get("price_value", 0) or 0)
    )

    return format_product_reply(product)


def expensive_product():
    if not PRODUCTS:
        return None

    product = max(
        PRODUCTS,
        key=lambda x: int(x.get("price_value", 0) or 0)
    )

    return format_product_reply(product)


def recommendation_reply(message):
    msg = normalize(message)

    if "\u09b8\u09ac \u09aa\u09cd\u09b0\u09cb\u09a1\u09be\u0995\u09cd\u099f" in msg or "all products" in msg:
        return list_products()

    if "\u09b8\u09b8\u09cd\u09a4\u09be" in msg or "cheap" in msg:
        return cheapest_product()

    if "\u09a6\u09be\u09ae\u09bf" in msg or "expensive" in msg:
        return expensive_product()

    return None


# ==========================================================
# FAQ DATABASE
# ==========================================================

def load_default_faq():
    global FAQ_DATABASE

    FAQ_DATABASE = [
        {
            "id": "delivery",
            "title": "Delivery",
            "keywords": [
                "delivery",
                "\u09a1\u09c7\u09b2\u09bf\u09ad\u09be\u09b0\u09bf",
                "\u0995\u09a4 \u09a6\u09bf\u09a8\u09c7",
                "courier",
                "shipping"
            ],
            "reply": (
                "\U0001f69a \u0986\u09ae\u09b0\u09be Steadfast Courier-\u098f\u09b0 \u09ae\u09be\u09a7\u09cd\u09af\u09ae\u09c7 \u09b8\u09be\u09b0\u09be \u09ac\u09be\u0982\u09b2\u09be\u09a6\u09c7\u09b6\u09c7 "
                "\u09b9\u09cb\u09ae \u09a1\u09c7\u09b2\u09bf\u09ad\u09be\u09b0\u09bf \u0995\u09b0\u09c7 \u09a5\u09be\u0995\u09bf\u0964 \u09b8\u09be\u09a7\u09be\u09b0\u09a3\u09a4 \u09e8\u2013\u09ea \u09a6\u09bf\u09a8\u09c7\u09b0 \u09ae\u09a7\u09cd\u09af\u09c7 "
                "\u09a1\u09c7\u09b2\u09bf\u09ad\u09be\u09b0\u09bf \u09b8\u09ae\u09cd\u09aa\u09a8\u09cd\u09a8 \u09b9\u09af\u09bc\u0964"
            ),
            "priority": 10,
            "active": True
        },
        {
            "id": "payment",
            "title": "Payment",
            "keywords": [
                "payment",
                "\u09aa\u09c7\u09ae\u09c7\u09a8\u09cd\u099f",
                "cash on delivery",
                "cod"
            ],
            "reply": (
                "\U0001f4b3 \u0986\u09ae\u09b0\u09be Cash on Delivery (COD) \u09b8\u09c1\u09ac\u09bf\u09a7\u09be \u09a6\u09bf\u09af\u09bc\u09c7 \u09a5\u09be\u0995\u09bf\u0964 "
                "\u09aa\u09cd\u09b0\u09cb\u09a1\u09be\u0995\u09cd\u099f \u09b9\u09be\u09a4\u09c7 \u09aa\u09c7\u09af\u09bc\u09c7 \u09a4\u09be\u09b0\u09aa\u09b0 \u099f\u09be\u0995\u09be \u09aa\u09b0\u09bf\u09b6\u09cb\u09a7 \u0995\u09b0\u09a4\u09c7 \u09aa\u09be\u09b0\u09ac\u09c7\u09a8\u0964"
            ),
            "priority": 10,
            "active": True
        }
    ]


def build_faq_index():
    FAQ_INDEX.clear()

    for faq in FAQ_DATABASE:
        if not faq.get("active", True):
            continue

        for keyword in faq.get("keywords", []):
            key = normalize(keyword)

            if key:
                FAQ_INDEX[key] = faq


def rebuild_faq_index():
    build_faq_index()
    FAQ_CACHE.clear()


def find_faq(message):
    msg = normalize(message)
    best = None
    best_score = 0

    for faq in FAQ_DATABASE:
        if not faq.get("active", True):
            continue

        score = 0

        for keyword in faq.get("keywords", []):
            key = normalize(keyword)

            if key and key in msg:
                score += 1

        if score > best_score:
            best_score = score
            best = faq

    return best


def final_faq_reply(message):
    faq = find_faq(message)
    return faq.get("reply") if faq else None


# ==========================================================
# CONVERSATION ENGINE
# ==========================================================

CONVERSATIONS = {
    "greeting": {
        "keywords": [
            "hi",
            "hello",
            "hey",
            "\u09b9\u09cd\u09af\u09be\u09b2\u09cb",
            "\u0986\u09b8\u09b8\u09be\u09b2\u09be\u09ae\u09c1 \u0986\u09b2\u09be\u0987\u0995\u09c1\u09ae",
            "assalamu alaikum",
            "slm",
            "salam"
        ],
        "reply": (
            "\u0986\u09b8\u09b8\u09be\u09b2\u09be\u09ae\u09c1 \u0986\u09b2\u09be\u0987\u0995\u09c1\u09ae\u0964 \u09b8\u09ac\u09c1\u099c \u09ac\u09be\u09a1\u09bc\u09bf-\u098f \u0986\u09aa\u09a8\u09be\u0995\u09c7 \u09b8\u09cd\u09ac\u09be\u0997\u09a4\u09ae\u0964 \U0001f60a\n\n"
            "\u0986\u09aa\u09a8\u09bf \u0995\u09cb\u09a8 \u09aa\u09cd\u09b0\u09cb\u09a1\u09be\u0995\u09cd\u099f\u099f\u09bf \u0996\u09c1\u0981\u099c\u099b\u09c7\u09a8?\n"
            "\u09aa\u09cd\u09b0\u09cb\u09a1\u09be\u0995\u09cd\u099f\u09c7\u09b0 \u09a8\u09be\u09ae \u09b2\u09bf\u0996\u09c1\u09a8 \u0985\u09a5\u09ac\u09be \u099b\u09ac\u09bf \u09aa\u09be\u09a0\u09be\u09a8\u0964"
        )
    },
    "thanks": {
        "keywords": [
            "thanks",
            "thank you",
            "\u09a7\u09a8\u09cd\u09af\u09ac\u09be\u09a6",
            "tnx",
            "thx"
        ],
        "reply": "\u0986\u09aa\u09a8\u09be\u0995\u09c7\u0993 \u09a7\u09a8\u09cd\u09af\u09ac\u09be\u09a6\u0964 \U0001f49a\n\u0986\u09b0 \u0995\u09cb\u09a8\u09cb \u09a4\u09a5\u09cd\u09af \u09b2\u09be\u0997\u09b2\u09c7 \u099c\u09be\u09a8\u09be\u09ac\u09c7\u09a8\u0964"
    },
    "ok": {
        "keywords": [
            "ok",
            "okay",
            "okk",
            "\u09a0\u09bf\u0995 \u0986\u099b\u09c7",
            "\u0986\u099a\u09cd\u099b\u09be",
            "\u09b9\u09c1\u09ae"
        ],
        "reply": "\U0001f60a \u09a0\u09bf\u0995 \u0986\u099b\u09c7\u0964 \u0986\u09b0 \u0995\u09cb\u09a8\u09cb \u09a4\u09a5\u09cd\u09af \u09b2\u09be\u0997\u09b2\u09c7 \u099c\u09be\u09a8\u09be\u09ac\u09c7\u09a8\u0964"
    },
    "bye": {
        "keywords": [
            "bye",
            "\u09ac\u09bf\u09a6\u09be\u09af\u09bc",
            "allah hafez",
            "\u0986\u09b2\u09cd\u09b2\u09be\u09b9 \u09b9\u09be\u09ab\u09c7\u099c"
        ],
        "reply": "\u0986\u09b2\u09cd\u09b2\u09be\u09b9 \u09b9\u09be\u09ab\u09c7\u099c\u0964 \U0001f49a\n\u0986\u09ac\u09be\u09b0 \u09aa\u09cd\u09b0\u09af\u09bc\u09cb\u099c\u09a8 \u09b9\u09b2\u09c7 \u0985\u09ac\u09b6\u09cd\u09af\u0987 \u09ae\u09c7\u09b8\u09c7\u099c \u0995\u09b0\u09ac\u09c7\u09a8\u0964"
    }
}


def conversation_reply(message):
    msg = normalize(message)
    padded = f" {msg} "

    for item in CONVERSATIONS.values():
        for keyword in item["keywords"]:
            key = normalize(keyword)

            if key and f" {key} " in padded:
                return item["reply"]

    return None


# ==========================================================
# HUMAN HANDOVER ENGINE
# ==========================================================

HUMAN_KEYWORDS = [
    "support",
    "agent",
    "human",
    "\u09ae\u09cd\u09af\u09be\u09a8\u09c7\u099c\u09be\u09b0",
    "\u09ae\u09be\u09a8\u09c1\u09b7",
    "\u0985\u09ad\u09bf\u09af\u09cb\u0997",
    "problem",
    "\u09af\u09cb\u0997\u09be\u09af\u09cb\u0997",
    "\u0995\u09a5\u09be \u09ac\u09b2\u09a4\u09c7 \u099a\u09be\u0987",
    "\u09b2\u09be\u0987\u09ad",
    "customer care"
]

RESUME_KEYWORDS = [
    "admin_resume",
    "resume",
    "bot",
    "bot resume",
    "\u09ac\u099f \u099a\u09be\u09b2\u09c1"
]


def is_human_request(message):
    # IMPORTANT:
    # exact/whole phrase matching prevents
    # "phone" from matching "headphone".
    return intent_keyword_match(message, HUMAN_KEYWORDS)


def start_human_mode(user_id):
    enable_human_mode(user_id)
    return HUMAN_REPLY


def admin_resume(user_id):
    disable_human_mode(user_id)
    return "Bot Service \u099a\u09be\u09b2\u09c1 \u09b9\u09af\u09bc\u09c7\u099b\u09c7\u0964"


def handle_human_mode(user_id, message):
    msg = normalize(message)

    if msg in [normalize(x) for x in RESUME_KEYWORDS]:
        return admin_resume(user_id)

    if is_human_request(message):
        return start_human_mode(user_id)

    if is_human_mode(user_id):
        return HUMAN_REPLY

    return None


# ==========================================================
# ORDER SYSTEM
# ==========================================================

ORDER_KEYWORDS = [
    "\u0985\u09b0\u09cd\u09a1\u09be\u09b0",
    "\u0985\u09b0\u09cd\u09a1\u09be\u09b0 \u0995\u09b0\u09a4\u09c7 \u099a\u09be\u0987",
    "order",
    "buy",
    "\u0995\u09bf\u09a8\u09a4\u09c7 \u099a\u09be\u0987"
]


def start_order(user_id):
    last_product = get_last_product(user_id)

    if not last_product:
        return "\u0985\u09b0\u09cd\u09a1\u09be\u09b0 \u09b6\u09c1\u09b0\u09c1 \u0995\u09b0\u09a4\u09c7 \u09aa\u09cd\u09b0\u09a5\u09ae\u09c7 \u098f\u0995\u099f\u09bf \u09aa\u09cd\u09b0\u09cb\u09a1\u09be\u0995\u09cd\u099f\u09c7\u09b0 \u09a8\u09be\u09ae \u09b2\u09bf\u0996\u09c1\u09a8\u0964"

    product = get_product_by_name(last_product)

    if not product:
        return "\u09aa\u09cd\u09b0\u09cb\u09a1\u09be\u0995\u09cd\u099f \u0996\u09c1\u0981\u099c\u09c7 \u09aa\u09be\u0993\u09af\u09bc\u09be \u09af\u09be\u09af\u09bc\u09a8\u09bf\u0964 \u0986\u09ac\u09be\u09b0 \u09aa\u09cd\u09b0\u09cb\u09a1\u09be\u0995\u09cd\u099f\u09c7\u09b0 \u09a8\u09be\u09ae \u09b2\u09bf\u0996\u09c1\u09a8\u0964"

    ORDER_STEPS[user_id] = {
        "step": "name",
        "product": product.get("name", ""),
        "price": product.get("price", ""),
        "name": "",
        "phone": "",
        "address": ""
    }

    return f"\U0001f4dd {product.get('name', '')} \u0985\u09b0\u09cd\u09a1\u09be\u09b0 \u0995\u09b0\u09a4\u09c7 \u099a\u09be\u099a\u09cd\u099b\u09c7\u09a8\u0964\n\n\u0986\u09aa\u09a8\u09be\u09b0 \u09a8\u09be\u09ae \u09b2\u09bf\u0996\u09c1\u09a8\u0964"


def handle_order(user_id, message):
    if user_id not in ORDER_STEPS:
        return None

    session = ORDER_STEPS[user_id]
    raw_message = str(message).strip()

    if session["step"] == "name":
        session["name"] = raw_message
        session["step"] = "phone"
        return "\U0001f4de \u0986\u09aa\u09a8\u09be\u09b0 \u09ae\u09cb\u09ac\u09be\u0987\u09b2 \u09a8\u09ae\u09cd\u09ac\u09b0 \u09b2\u09bf\u0996\u09c1\u09a8\u0964"

    if session["step"] == "phone":
        phone = normalize(raw_message).replace(" ", "")

        if not re.fullmatch(r"01\d{9}", phone):
            return "\U0001f4de \u09b8\u09a0\u09bf\u0995 \u09e7\u09e7 \u09b8\u0982\u0996\u09cd\u09af\u09be\u09b0 \u09ae\u09cb\u09ac\u09be\u0987\u09b2 \u09a8\u09ae\u09cd\u09ac\u09b0 \u09b2\u09bf\u0996\u09c1\u09a8\u0964 \u0989\u09a6\u09be\u09b9\u09b0\u09a3: 017XXXXXXXX"

        session["phone"] = phone
        session["step"] = "address"
        return "\U0001f4cd \u0986\u09aa\u09a8\u09be\u09b0 \u09b8\u09ae\u09cd\u09aa\u09c2\u09b0\u09cd\u09a3 \u09a0\u09bf\u0995\u09be\u09a8\u09be \u09b2\u09bf\u0996\u09c1\u09a8\u0964"

    if session["step"] == "address":
        session["address"] = raw_message

        order = {
            "id": "ORD-" + str(uuid.uuid4())[:8].upper(),
            "user_id": user_id,
            "customer_name": session["name"],
            "phone": session["phone"],
            "address": session["address"],
            "product": session["product"],
            "quantity": 1,
            "price": session["price"],
            "status": "Pending",
            "payment": "Cash On Delivery",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        ORDERS.append(order)
        save_json(ORDER_FILE, ORDERS)
        del ORDER_STEPS[user_id]

        return (
            f"{ORDER_SUCCESS_REPLY}\n\n"
            f"\U0001f6cd\ufe0f \u09aa\u09cd\u09b0\u09cb\u09a1\u09be\u0995\u09cd\u099f: {order['product']}\n"
            f"\U0001f464 \u09a8\u09be\u09ae: {order['customer_name']}\n"
            f"\U0001f4de \u09ab\u09cb\u09a8: {order['phone']}\n"
            f"\U0001f4cd \u09a0\u09bf\u0995\u09be\u09a8\u09be: {order['address']}\n"
            f"\U0001f194 Order ID: {order['id']}"
        )

    return None


# ==========================================================
# FALLBACK
# ==========================================================

def increase_unknown(user_id):
    UNKNOWN_COUNTER[user_id] = UNKNOWN_COUNTER.get(user_id, 0) + 1
    return UNKNOWN_COUNTER[user_id]


def reset_unknown(user_id):
    UNKNOWN_COUNTER[user_id] = 0


def suggest_similar_product(message):
    products = suggest_products(message)

    if not products:
        return None

    text = "\U0001f60c \u0986\u09aa\u09a8\u09be\u09b0 \u0995\u09a5\u09be\u09b0 \u09b8\u09be\u09a5\u09c7 \u09ae\u09bf\u09b2 \u09a5\u09be\u0995\u09be \u0995\u09bf\u099b\u09c1 \u09aa\u09cd\u09b0\u09cb\u09a1\u09be\u0995\u09cd\u099f:\n\n"

    for product in products:
        text += f"\u2022 {product.get('name', '')}\n"

    text += "\n\u09af\u09c7\u099f\u09bf \u099c\u09be\u09a8\u09a4\u09c7 \u099a\u09be\u09a8, \u09b6\u09c1\u09a7\u09c1 \u09a8\u09be\u09ae \u09b2\u09bf\u0996\u09c1\u09a8\u0964"
    return text


def fallback_reply(user_id, message):
    suggestion = suggest_similar_product(message)

    if suggestion:
        return suggestion

    return DEFAULT_REPLY


# ==========================================================
# MAIN REPLY ENGINE
# ==========================================================

def generate_reply(user_id, message):
    original_message = str(message or "").strip()
    message = safe_text(original_message)

    if is_empty(message):
        return DEFAULT_REPLY

    save_message(user_id, message)

    # 1. Resume command ALWAYS has highest priority.
    if message in [normalize(x) for x in RESUME_KEYWORDS]:
        reset_unknown(user_id)
        return admin_resume(user_id)

    # 2. Ongoing order.
    reply = handle_order(user_id, original_message)
    if reply:
        reset_unknown(user_id)
        return reply

    # 3. Human handover.
    reply = handle_human_mode(user_id, message)
    if reply:
        reset_unknown(user_id)
        return reply

    # 4. Conversation.
    reply = conversation_reply(message)
    if reply:
        reset_unknown(user_id)
        return reply

    # 5. Product.
    reply = handle_product_message(user_id, message)
    if reply:
        reset_unknown(user_id)
        return reply

    # 6. Start order.
    if keyword_match(message, ORDER_KEYWORDS):
        reply = start_order(user_id)
        if reply:
            reset_unknown(user_id)
            return reply

    # 7. Recommendations.
    reply = recommendation_reply(message)
    if reply:
        reset_unknown(user_id)
        return reply

    # 8. FAQ.
    reply = final_faq_reply(message)
    if reply:
        reset_unknown(user_id)
        return reply

    increase_unknown(user_id)
    return fallback_reply(user_id, message)


# ==========================================================
# FACEBOOK MESSENGER API
# ==========================================================

HEADERS = {
    "Content-Type": "application/json"
}


def graph_url():
    return f"{GRAPH_API}?access_token={PAGE_ACCESS_TOKEN}"


def typing_delay():
    if ENABLE_TYPING:
        time.sleep(random.uniform(MIN_TYPING_DELAY, MAX_TYPING_DELAY))


def send_message(recipient_id, message):
    payload = {
        "recipient": {
            "id": recipient_id
        },
        "message": {
            "text": str(message)[:2000]
        }
    }

    try:
        response = requests.post(
            graph_url(),
            headers=HEADERS,
            json=payload,
            timeout=15
        )

        response.raise_for_status()
        log_info(f"Message Sent -> {recipient_id}")
        return True

    except Exception as e:
        log_error(f"Send Error : {e}")
        return False


def sender_action(recipient_id, action):
    payload = {
        "recipient": {
            "id": recipient_id
        },
        "sender_action": action
    }

    try:
        requests.post(
            graph_url(),
            headers=HEADERS,
            json=payload,
            timeout=10
        )
    except Exception:
        pass


def mark_seen(recipient_id):
    sender_action(recipient_id, "mark_seen")


def typing_on(recipient_id):
    sender_action(recipient_id, "typing_on")


def typing_off(recipient_id):
    sender_action(recipient_id, "typing_off")


# ==========================================================
# FACEBOOK WEBHOOK
# ==========================================================

@app.route("/", methods=["GET"])
def home():
    return "Sabuj Bari Messenger Bot Running \u2705", 200


@app.route("/webhook", methods=["GET"])
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200

    return "Verification Failed", 403


@app.route("/webhook", methods=["POST"])
def webhook():
    body = request.get_json(silent=True) or {}

    if body.get("object") != "page":
        return "ignored", 200

    for entry in body.get("entry", []):
        for event in entry.get("messaging", []):
            process_event(event)

    return "ok", 200


def process_event(event):
    sender = event.get("sender", {}).get("id")

    if not sender:
        return

    message = event.get("message", {})

    if message.get("is_echo"):
        return

    if "message" in event:
        process_message(sender, event["message"])

    elif "postback" in event:
        payload = event["postback"].get("payload", "")
        process_message(sender, {"text": payload})


def process_message(user_id, message):
    try:
        mark_seen(user_id)
        typing_on(user_id)
        typing_delay()

        text = message.get("text", "")

        if not text:
            attachments = message.get("attachments", [])

            if attachments:
                reply = (
                    "\U0001f4f7 \u099b\u09ac\u09bf \u09aa\u09c7\u09af\u09bc\u09c7\u099b\u09bf\u0964\n\n"
                    "\u0985\u09a8\u09c1\u0997\u09cd\u09b0\u09b9 \u0995\u09b0\u09c7 \u09aa\u09cd\u09b0\u09cb\u09a1\u09be\u0995\u09cd\u099f\u09c7\u09b0 \u09a8\u09be\u09ae \u09b2\u09bf\u0996\u09c1\u09a8 \u0985\u09a5\u09ac\u09be "
                    "\u099b\u09ac\u09bf\u099f\u09bf \u0995\u09cb\u09a8 \u09aa\u09cd\u09b0\u09cb\u09a1\u09be\u0995\u09cd\u099f \u09b8\u09ae\u09cd\u09aa\u09b0\u09cd\u0995\u09c7 \u099c\u09be\u09a8\u09a4\u09c7 \u099a\u09be\u09a8 \u09a4\u09be \u09ac\u09b2\u09c1\u09a8\u0964"
                )
            else:
                reply = DEFAULT_REPLY
        else:
            reply = generate_reply(user_id, text)

        typing_off(user_id)
        send_message(user_id, reply)

    except Exception as e:
        typing_off(user_id)
        log_error(f"Process Message Error : {e}")

        send_message(
            user_id,
            "\u274c \u09b8\u09be\u09ae\u09af\u09bc\u09bf\u0995 \u09b8\u09ae\u09b8\u09cd\u09af\u09be \u09b9\u09af\u09bc\u09c7\u099b\u09c7\u0964 \u0985\u09a8\u09c1\u0997\u09cd\u09b0\u09b9 \u0995\u09b0\u09c7 \u0986\u09ac\u09be\u09b0 \u099a\u09c7\u09b7\u09cd\u099f\u09be \u0995\u09b0\u09c1\u09a8\u0964"
        )


# ==========================================================
# DATABASE RELOAD / STARTUP
# ==========================================================

def reload_database():
    global PRODUCTS
    global FAQ_DATABASE
    global ORDERS

    PRODUCTS = load_json(PRODUCT_FILE)
    ORDERS = load_json(ORDER_FILE)
    FAQ_DATABASE = load_json(FAQ_FILE)

    if not FAQ_DATABASE:
        load_default_faq()

    rebuild_search_engine()
    rebuild_faq_index()

    log_info(
        f"Database Loaded Successfully. "
        f"Products={len(PRODUCTS)}, FAQ={len(FAQ_DATABASE)}, Orders={len(ORDERS)}"
    )


def startup():
    reload_database()
    log_info("Sabuj Bari Bot Started.")


# IMPORTANT:
# Keep startup outside __main__ so gunicorn app:app also initializes indexes.
startup()


# ==========================================================
# RUN APPLICATION
# ==========================================================

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", 5000)),
        debug=False
    )
