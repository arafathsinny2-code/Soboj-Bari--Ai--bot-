# ==========================================================
# SECTION 1.1
# IMPORTS
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

from flask import (
    Flask,
    request,
    jsonify
)

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

PAGE_ACCESS_TOKEN = os.getenv(
    "PAGE_ACCESS_TOKEN",
    ""
)

GRAPH_API = "https://graph.facebook.com/v23.0/me/messages"

# ==========================================================
# BOT CONFIG
# ==========================================================

BOT_NAME = "সবুজ বাড়ি Assistant"
PAGE_NAME = "সবুজ বাড়ি"
DEFAULT_LANGUAGE = "bn"
VERSION = "2.0.0"

# ==========================================================
# FILES
# ==========================================================

DATA_DIR = "data"
PRODUCT_FILE = os.path.join(DATA_DIR, "products.json")
FAQ_FILE = os.path.join(DATA_DIR, "faq.json")
ORDER_FILE = os.path.join(DATA_DIR, "orders.json")
LOG_FILE = os.path.join(DATA_DIR, "bot.log")

os.makedirs(DATA_DIR, exist_ok=True)

# ==========================================================
# SECTION 1.2
# LOGGING & GLOBAL MEMORY
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

USERS = {}
ORDER_STEPS = {}
UNKNOWN_COUNTER = {}

MAX_MESSAGE_LENGTH = 2000
MAX_HISTORY = 20
ENABLE_LOGGING = True
ENABLE_TYPING = True

MIN_TYPING_DELAY = 0.8
MAX_TYPING_DELAY = 1.8

# ==========================================================
# DEFAULT REPLIES (Updated according to new rules)
# ==========================================================

DEFAULT_REPLY = "দুঃখিত, আমি বিষয়টি বুঝতে পারিনি। অনুগ্রহ করে প্রোডাক্টের নাম বা প্রশ্নটি আবার লিখুন।"

GREETING_REPLY = "আসসালামু আলাইকুম। সবুজ বাড়ি- এর সেল assistant আপনাকে স্বাগতম। আপনি কোন প্রোডাক্টটি খুঁজছেন জানাবেন ছবি দিন বা নাম বলুন"

PRODUCT_NOT_FOUND_REPLY = "এই মডেলটি আমাদের টিম যাচাই করছে। অনুগ্রহ করে একটু অপেক্ষা করুন, আমরা দ্রুত আপনাকে জানাবো। 😊"

ORDER_SUCCESS_REPLY = "✅ আপনার অর্ডার সফলভাবে গ্রহণ করা হয়েছে। আমাদের প্রতিনিধি দ্রুত যোগাযোগ করবেন।"

HUMAN_REPLY = "আপনার বিষয়টি এডমিনকে জানানো হচ্ছে, শীঘ্রই যোগাযোগ করা হবে।"

# ==========================================================
# HELPER FUNCTIONS
# ==========================================================

def typing_delay():
    if ENABLE_TYPING:
        time.sleep(random.uniform(MIN_TYPING_DELAY, MAX_TYPING_DELAY))

def log_info(message):
    if ENABLE_LOGGING:
        logger.info(message)

def log_error(message):
    logger.error(message)

# ==========================================================
# SECTION 1.3
# JSON DATABASE
# ==========================================================

BACKUP_DIR = os.path.join(DATA_DIR, "backup")
os.makedirs(BACKUP_DIR, exist_ok=True)

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
            return json.load(f)
    except Exception as e:
        log_error(f"Load JSON Error : {e}")
        return []

def save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        log_error(f"Save JSON Error : {e}")
        return False

PRODUCTS = load_json(PRODUCT_FILE)
ORDERS = load_json(ORDER_FILE)

# ==========================================================
# SECTION 1.4
# NORMALIZE ENGINE
# ==========================================================

BANGLA_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")

def normalize(text):
    if text is None:
        return ""
    text = str(text)
    text = text.translate(BANGLA_DIGITS)
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^\w\s\u0980-\u09FF]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def safe_text(text):
    if text is None:
        return ""
    return normalize(text)

def keyword_match(message, keywords):
    msg = normalize(message)
    for keyword in keywords:
        if normalize(keyword) in msg:
            return True
    return False

def is_empty(text):
    return len(normalize(text)) == 0

# ==========================================================
# SECTION 1.5
# USER SESSION & MEMORY
# ==========================================================

def get_user(user_id):
    if user_id not in USERS:
        USERS[user_id] = {
            "id": user_id,
            "name": "",
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
# SECTION 2.1 - 2.6
# PRODUCT ENGINE
# ==========================================================

PRODUCT_INDEX = {}
PRODUCT_ALIASES = {}

def build_product_index():
    PRODUCT_INDEX.clear()
    for product in PRODUCTS:
        PRODUCT_INDEX[normalize(product["name"])] = product
        for keyword in product.get("keywords", []):
            PRODUCT_INDEX[normalize(keyword)] = product

def rebuild_product_index():
    build_product_index()

def build_alias_index():
    PRODUCT_ALIASES.clear()
    for product in PRODUCTS:
        register_alias(product["name"], product["name"])
        for keyword in product.get("keywords", []):
            register_alias(keyword, product["name"])

def register_alias(alias, product_name):
    PRODUCT_ALIASES[normalize(alias)] = normalize(product_name)

def get_product_by_name(name):
    name = normalize(name)
    for product in PRODUCTS:
        if normalize(product["name"]) == name:
            return product
    return None

def smart_product_search(message):
    msg = normalize(message)
    if msg in PRODUCT_INDEX:
        return PRODUCT_INDEX[msg]
    for keyword, product in PRODUCT_INDEX.items():
        if keyword in msg:
            return product
    for alias, product_name in PRODUCT_ALIASES.items():
        if alias in msg:
            return get_product_by_name(product_name)
    return None

def suggest_products(message):
    msg = normalize(message)
    result = []
    for product in PRODUCTS:
        score = 0
        for keyword in product.get("keywords", []):
            if normalize(keyword) in msg:
                score += 1
        if score:
            result.append((score, product))
    result.sort(reverse=True, key=lambda x: x[0])
    return [item[1] for item in result[:3]]

def rebuild_search_engine():
    rebuild_product_index()
    build_alias_index()

def format_product_reply(product):
    features = ""
    for item in product.get("features", []):
        features += f"• {item}\n"

    colors = ", ".join(product.get("colors", []))

    return f"""পণ্যের নাম: {product['name']}
মূল্য: {product['price']} টাকা (স্টক ক্লিয়ারেন্স অফার, ফিক্সড প্রাইস)
বৈশিষ্ট্য:
{features}
রঙ: {colors if colors else "Not Available"}

আমাদের পণ্যের মান ১০০% গ্যারান্টিযুক্ত। আমাদের পেইজে অনেক ভালো রিভিউ দেখতে পাবেন।

ডেলিভারি চার্জ: ৳{product.get('delivery_charge', '100')}
ডেলিভারি সময়: {product.get('delivery', '২–৪ দিন')}

অর্ডার করতে "অর্ডার করতে চাই" লিখুন।"""

PRICE_KEYWORDS = ["price", "দাম", "মূল্য", "offer", "কত", "tk", "৳", "pp"]
COLOR_KEYWORDS = ["color", "colour", "রং", "কালার"]
STOCK_KEYWORDS = ["stock", "স্টক", "available", "আছে"]
DELIVERY_KEYWORDS = ["delivery", "ডেলিভারি", "কত দিনে", "courier"]
WARRANTY_KEYWORDS = ["warranty", "গ্যারান্টি", "ওয়ারেন্টি"]
FEATURE_KEYWORDS = ["feature", "features", "স্পেসিফিকেশন", "কি কি আছে"]

def is_price_question(message):
    return keyword_match(message, PRICE_KEYWORDS)

def price_reply(product):
    return f"মূল্য: {product['price']} টাকা (স্টক ক্লিয়ারেন্স অফার, ফিক্সড প্রাইস)"

def color_reply(product):
    colors = product.get("colors", [])
    if not colors:
        return "এই প্রোডাক্টের রঙের তথ্য নেই।"
    return "রঙ:\n" + "\n".join(f"• {c}" for c in colors)

def stock_reply(product):
    return f"স্টক: {product['stock']}"

def delivery_reply(product):
    return f"""ডেলিভারি সময়: {product.get('delivery', '২–৪ দিন')}
ডেলিভারি চার্জ: ৳{product.get('delivery_charge', '100')}"""

def warranty_reply(product):
    return f"ওয়ারেন্টি: {product.get('warranty', 'No Warranty')}"

def feature_reply(product):
    text = "বৈশিষ্ট্য:\n"
    for item in product.get("features", []):
        text += f"• {item}\n"
    return text

def product_reply(user_id, message):
    product = smart_product_search(message)
    if not product:
        return None

    set_last_product(user_id, product["name"])

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
    reply = continue_last_product(user_id, message)
    if reply:
        return reply
    return None

def list_products(limit=None):
    items = PRODUCTS[:limit] if limit else PRODUCTS
    text = "আমাদের প্রোডাক্টসমূহ:\n\n"
    for p in items:
        text += f"• {p['name']}\nমূল্য: {p['price']}\n\n"
    return text

def recommendation_reply(message):
    msg = normalize(message)
    if "সব" in msg or "all" in msg or "product" in msg:
        return list_products()
    return None

# ==========================================================
# SECTION 3
# FAQ + CONVERSATION + HUMAN
# ==========================================================

FAQ_DATABASE = []

def load_default_faq():
    FAQ_DATABASE.clear()
    FAQ_DATABASE.extend([
        {
            "id": "delivery",
            "title": "Delivery",
            "keywords": ["delivery", "ডেলিভারি", "কত দিনে", "courier", "shipping"],
            "reply": "সারা বাংলাদেশে Steadfast Courier এর মাধ্যমে হোম ডেলিভারি করা হয়। সাধারণত ২–৪ কার্যদিবস। ডেলিভারি চার্জ ৳১০০।",
            "priority": 10,
            "active": True
        },
        {
            "id": "payment",
            "title": "Payment",
            "keywords": ["payment", "পেমেন্ট", "cod", "cash on delivery", "কিভাবে টাকা দিব"],
            "reply": "আমরা Cash on Delivery (COD) সুবিধা দিয়ে থাকি। পণ্য হাতে পেয়ে টাকা দিবেন।",
            "priority": 10,
            "active": True
        },
        {
            "id": "return",
            "title": "Return",
            "keywords": ["return", "ফেরত", "refund", "রিটার্ন"],
            "reply": "পণ্য পছন্দ না হলে ফেরত দিতে পারবেন। ডেলিভারি চার্জ ১২০ টাকা প্রযোজ্য। পণ্য অব্যবহৃত ও অরিজিনাল প্যাকেজিং সহ থাকতে হবে। ডেলিভারির ২৪ ঘণ্টার মধ্যে জানাতে হবে।",
            "priority": 9,
            "active": True
        },
        {
            "id": "review",
            "title": "Review",
            "keywords": ["review", "রিভিউ", "feedback"],
            "reply": "আমাদের পেইজে অসংখ্য বাস্তব কাস্টমারের রিভিউ রয়েছে। পেজ ভিজিট করে দেখতে পারেন।",
            "priority": 8,
            "active": True
        }
    ])

load_default_faq()

FAQ_INDEX = {}
FAQ_CACHE = {}

def build_faq_index():
    FAQ_INDEX.clear()
    for faq in FAQ_DATABASE:
        if not faq.get("active", True):
            continue
        for keyword in faq.get("keywords", []):
            FAQ_INDEX[normalize(keyword)] = faq

def rebuild_faq_index():
    build_faq_index()
    FAQ_CACHE.clear()

def fast_find_faq(message):
    msg = normalize(message)
    if msg in FAQ_CACHE:
        return FAQ_CACHE[msg]
    if msg in FAQ_INDEX:
        FAQ_CACHE[msg] = FAQ_INDEX[msg]
        return FAQ_INDEX[msg]
    for keyword, faq in FAQ_INDEX.items():
        if keyword in msg:
            FAQ_CACHE[msg] = faq
            return faq
    return None

def final_faq_reply(message):
    faq = fast_find_faq(message)
    if faq:
        return faq["reply"]
    return None

rebuild_faq_index()

CONVERSATIONS = {
    "greeting": {
        "keywords": ["hi", "hello", "hey", "হ্যালো", "আসসালামু আলাইকুম", "assalamu alaikum", "slm", "salam"],
        "reply": GREETING_REPLY
    },
    "thanks": {
        "keywords": ["thanks", "thank you", "ধন্যবাদ", "tnx", "thx"],
        "reply": "আপনাকেও ধন্যবাদ। আর কোনো তথ্য লাগলে জানাবেন।"
    },
    "ok": {
        "keywords": ["ok", "okay", "okk", "ঠিক আছে", "আচ্ছা", "হুম"],
        "reply": "ঠিক আছে। আর কোনো তথ্য লাগলে জানাবেন।"
    },
    "bye": {
        "keywords": ["bye", "বিদায়", "allah hafez", "আল্লাহ হাফেজ"],
        "reply": "আল্লাহ হাফেজ। আবার প্রয়োজন হলে মেসেজ করবেন।"
    }
}

def conversation_reply(message):
    msg = normalize(message)
    for item in CONVERSATIONS.values():
        for keyword in item["keywords"]:
            if normalize(keyword) in msg:
                return item["reply"]
    return None

HUMAN_KEYWORDS = [
    "admin", "support", "agent", "human", "ম্যানেজার", "মানুষ", "লোক",
    "অভিযোগ", "problem", "call", "phone", "যোগাযোগ", "কথা বলতে চাই", "লাইভ",
    "রিটার্ন", "ফেরত", "এক্সচেঞ্জ", "নষ্ট", "ভাঙা", "পেমেন্ট সমস্যা", "পণ্য পাইনি"
]

def is_human_request(message):
    return keyword_match(message, HUMAN_KEYWORDS)

def handle_human_mode(user_id, message):
    if is_human_request(message):
        enable_human_mode(user_id)
        return HUMAN_REPLY
    if is_human_mode(user_id):
        return HUMAN_REPLY
    return None

# ==========================================================
# SECTION 4.0
# ORDER SYSTEM (Updated according to new rules)
# ==========================================================

ORDER_KEYWORDS = [
    "অর্ডার", "অর্ডার করতে চাই", "order", "buy", "কিনতে চাই", "confirm order"
]

def start_order(user_id):
    last_product = get_last_product(user_id)
    if not last_product:
        return "অর্ডার শুরু করতে প্রথমে একটি প্রোডাক্টের নাম লিখুন অথবা ছবি পাঠান।"

    product = get_product_by_name(last_product)
    if not product:
        return "প্রোডাক্ট খুঁজে পাওয়া যায়নি। আবার প্রোডাক্টের নাম লিখুন।"

    ORDER_STEPS[user_id] = {
        "step": "name",
        "product": product["name"],
        "price": product["price"],
        "color": "",
        "name": "",
        "phone": "",
        "district": "",
        "thana": "",
        "address": ""
    }

    return (
        f"অর্ডার কনফার্ম করার জন্য দয়া করে নিচের তথ্যগুলো দিন:\n\n"
        f"পছন্দের পণ্য: {product['name']}\n\n"
        f"আপনার নাম:"
    )

def handle_order(user_id, message):
    if user_id not in ORDER_STEPS:
        return None

    session = ORDER_STEPS[user_id]
    text = message.strip()

    if session["step"] == "name":
        session["name"] = text
        session["step"] = "phone"
        return "ফোন নাম্বার:"

    elif session["step"] == "phone":
        session["phone"] = text
        session["step"] = "district"
        return "জেলা:"

    elif session["step"] == "district":
        session["district"] = text
        session["step"] = "thana"
        return "থানা:"

    elif session["step"] == "thana":
        session["thana"] = text
        session["step"] = "address"
        return "সম্পূর্ণ ঠিকানা:"

    elif session["step"] == "address":
        session["address"] = text
        session["step"] = "color"

        product = get_product_by_name(session["product"])
        colors = product.get("colors", []) if product else []

        if colors:
            return "রঙ (যদি প্রযোজ্য হয়):\n" + "\n".join(f"• {c}" for c in colors)
        else:
            # color skip
            return finish_order(user_id, session)

    elif session["step"] == "color":
        session["color"] = text
        return finish_order(user_id, session)

    return None

def finish_order(user_id, session):
    order = {
        "id": "ORD-" + str(uuid.uuid4())[:8].upper(),
        "user_id": user_id,
        "customer_name": session["name"],
        "phone": session["phone"],
        "district": session.get("district", ""),
        "thana": session.get("thana", ""),
        "address": session["address"],
        "product": session["product"],
        "color": session.get("color", ""),
        "quantity": 1,
        "price": session["price"],
        "delivery_charge": "100",
        "status": "Pending",
        "payment": "Cash On Delivery",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    ORDERS.append(order)
    save_json(ORDER_FILE, ORDERS)

    del ORDER_STEPS[user_id]

    summary = (
        f"{ORDER_SUCCESS_REPLY}\n\n"
        f"পণ্য: {order['product']}\n"
        f"রঙ: {order['color'] or 'N/A'}\n"
        f"নাম: {order['customer_name']}\n"
        f"ফোন: {order['phone']}\n"
        f"জেলা: {order['district']}\n"
        f"থানা: {order['thana']}\n"
        f"ঠিকানা: {order['address']}\n"
        f"মূল্য: {order['price']}\n"
        f"ডেলিভারি চার্জ: ৳100\n"
        f"Order ID: {order['id']}\n\n"
        f"পণ্য হাতে পেয়ে ডেলিভারি ম্যানের সামনে চেক করবেন।"
    )
    return summary

# ==========================================================
# MAIN GENERATE REPLY
# ==========================================================

def increase_unknown(user_id):
    UNKNOWN_COUNTER[user_id] = UNKNOWN_COUNTER.get(user_id, 0) + 1
    return UNKNOWN_COUNTER[user_id]

def reset_unknown(user_id):
    UNKNOWN_COUNTER[user_id] = 0

def fallback_reply(user_id, message):
    reset_unknown(user_id)
    suggestion = suggest_products(message)
    if suggestion:
        text = PRODUCT_NOT_FOUND_REPLY + "\n\nআপনার কথার সাথে মিল থাকা কিছু প্রোডাক্ট:\n"
        for p in suggestion:
            text += f"• {p['name']}\n"
        return text
    return PRODUCT_NOT_FOUND_REPLY

def generate_reply(user_id, message):
    message = safe_text(message)
    if is_empty(message):
        return DEFAULT_REPLY

    save_message(user_id, message)

    # 1. Ongoing Order
    reply = handle_order(user_id, message)
    if reply:
        reset_unknown(user_id)
        return reply

    # 2. Human / Escalation
    reply = handle_human_mode(user_id, message)
    if reply:
        reset_unknown(user_id)
        return reply

    # 3. Conversation / Greeting
    reply = conversation_reply(message)
    if reply:
        reset_unknown(user_id)
        return reply

    # 4. Product
    reply = handle_product_message(user_id, message)
    if reply:
        reset_unknown(user_id)
        return reply

    # 5. Start Order
    if keyword_match(message, ORDER_KEYWORDS):
        reply = start_order(user_id)
        if reply:
            reset_unknown(user_id)
            return reply

    # 6. Recommendation
    reply = recommendation_reply(message)
    if reply:
        reset_unknown(user_id)
        return reply

    # 7. FAQ
    reply = final_faq_reply(message)
    if reply:
        reset_unknown(user_id)
        return reply

    # 8. Fallback (Product not found rule)
    increase_unknown(user_id)
    return fallback_reply(user_id, message)

# ==========================================================
# FACEBOOK API
# ==========================================================

HEADERS = {"Content-Type": "application/json"}

def graph_url():
    return f"{GRAPH_API}?access_token={PAGE_ACCESS_TOKEN}"

def send_message(recipient_id, message):
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": message}
    }
    try:
        response = requests.post(graph_url(), headers=HEADERS, json=payload, timeout=15)
        response.raise_for_status()
        log_info(f"Message Sent -> {recipient_id}")
        return True
    except Exception as e:
        log_error(f"Send Error : {e}")
        return False

def mark_seen(recipient_id):
    try:
        requests.post(graph_url(), headers=HEADERS, json={
            "recipient": {"id": recipient_id},
            "sender_action": "mark_seen"
        }, timeout=10)
    except:
        pass

def typing_on(recipient_id):
    try:
        requests.post(graph_url(), headers=HEADERS, json={
            "recipient": {"id": recipient_id},
            "sender_action": "typing_on"
        }, timeout=10)
    except:
        pass

def typing_off(recipient_id):
    try:
        requests.post(graph_url(), headers=HEADERS, json={
            "recipient": {"id": recipient_id},
            "sender_action": "typing_off"
        }, timeout=10)
    except:
        pass

# ==========================================================
# WEBHOOK
# ==========================================================

@app.route("/", methods=["GET"])
def home():
    return "Sabuj Bari Messenger Bot Running ✅", 200

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
    body = request.get_json()
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
    if event.get("message", {}).get("is_echo"):
        return
    if "message" in event:
        process_message(sender, event["message"])
    elif "postback" in event:
        process_postback(sender, event["postback"])

def process_postback(sender, postback):
    payload = postback.get("payload", "")
    typing_on(sender)
    typing_delay()
    typing_off(sender)
    send_message(sender, f"Postback : {payload}")

def process_message(user_id, message):
    try:
        mark_seen(user_id)
        typing_on(user_id)
        typing_delay()

        text = message.get("text", "")

        if not text:
            # Image received
            attachments = message.get("attachments", [])
            if attachments:
                # According to rules: first message is image → skip greeting, try to match
                # (Real image matching needs vision AI. Currently fallback)
                reply = (
                    "ছবি পেয়েছি।\n\n"
                    "অনুগ্রহ করে প্রোডাক্টের নাম লিখুন অথবা কোন প্রোডাক্ট সম্পর্কে জানতে চান তা বলুন।"
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
        send_message(user_id, "সাময়িক সমস্যা হয়েছে। অনুগ্রহ করে আবার চেষ্টা করুন।")

# ==========================================================
# DATABASE RELOAD
# ==========================================================

def reload_database():
    global PRODUCTS, FAQ_DATABASE, ORDERS

    PRODUCTS = load_json(PRODUCT_FILE)
    ORDERS = load_json(ORDER_FILE)

    FAQ_DATABASE = load_json(FAQ_FILE)
    if not FAQ_DATABASE:
        load_default_faq()

    rebuild_search_engine()
    rebuild_faq_index()
    log_info("✅ Database Loaded Successfully.")

def startup():
    reload_database()
    log_info("✅ Sabuj Bari Bot Started.")

# ==========================================================
# RUN
# ==========================================================

if __name__ == "__main__":
    startup()
    app.run(host="0.0.0.0", port=5000, debug=False)
