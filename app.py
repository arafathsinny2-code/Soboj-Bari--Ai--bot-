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

VERSION = "1.0.0"

# ==========================================================
# FILES
# ==========================================================

DATA_DIR = "data"

PRODUCT_FILE = os.path.join(
    DATA_DIR,
    "products.json"
)

FAQ_FILE = os.path.join(
    DATA_DIR,
    "faq.json"
)

ORDER_FILE = os.path.join(
    DATA_DIR,
    "orders.json"
)

LOG_FILE = os.path.join(
    DATA_DIR,
    "bot.log"
)

# ==========================================================
# CREATE DATA DIRECTORY
# ==========================================================

os.makedirs(
    DATA_DIR,
    exist_ok=True
)

# ==========================================================
# SECTION 1.2
# LOGGING & GLOBAL MEMORY
# ==========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(
            LOG_FILE,
            encoding="utf-8"
        ),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("SabujBariBot")

# ==========================================================
# GLOBAL MEMORY
# ==========================================================

USERS = {}

ORDER_SESSIONS = {}

HUMAN_MODE = {}

CACHE = {}

LAST_REPLY = {}

# ==========================================================
# DEFAULT SETTINGS
# ==========================================================

MAX_MESSAGE_LENGTH = 2000

MAX_HISTORY = 20

ENABLE_LOGGING = True

ENABLE_CACHE = True

ENABLE_MEMORY = True

ENABLE_TYPING = True

# ==========================================================
# DEFAULT REPLIES
# ==========================================================

DEFAULT_REPLY = (
    "দুঃখিত, আমি বিষয়টি বুঝতে পারিনি। "
    "অনুগ্রহ করে প্রোডাক্টের নাম বা প্রশ্নটি আবার লিখুন।"
)

ORDER_SUCCESS_REPLY = (
    "✅ আপনার অর্ডার সফলভাবে গ্রহণ করা হয়েছে। "
    "আমাদের প্রতিনিধি দ্রুত যোগাযোগ করবেন।"
)

# ==========================================================
# TYPING DELAY
# ==========================================================

MIN_TYPING_DELAY = 0.8

MAX_TYPING_DELAY = 1.8

# ==========================================================
# HELPER FUNCTIONS
# ==========================================================

def typing_delay():

    if ENABLE_TYPING:

        time.sleep(

            random.uniform(

                MIN_TYPING_DELAY,

                MAX_TYPING_DELAY

            )

        )

def log_info(message):

    if ENABLE_LOGGING:

        logger.info(message)

def log_error(message):

    logger.error(message)

# ==========================================================
# SECTION 1.3
# JSON DATABASE & BACKUP
# ==========================================================

BACKUP_DIR = os.path.join(DATA_DIR, "backup")

os.makedirs(BACKUP_DIR, exist_ok=True)

def ensure_json_file(path, default_data):

    if not os.path.exists(path):

        with open(path, "w", encoding="utf-8") as f:

            json.dump(
                default_data,
                f,
                ensure_ascii=False,
                indent=4
            )

ensure_json_file(PRODUCT_FILE, [])

ensure_json_file(FAQ_FILE, [])

ensure_json_file(ORDER_FILE, [])

# ==========================================================
# JSON LOAD
# ==========================================================

def load_json(path):

    try:

        with open(

            path,

            "r",

            encoding="utf-8"

        ) as f:

            return json.load(f)

    except Exception as e:

        log_error(f"Load JSON Error : {e}")

        return []

# ==========================================================
# JSON SAVE
# ==========================================================

def save_json(path, data):

    try:

        with open(

            path,

            "w",

            encoding="utf-8"

        ) as f:

            json.dump(

                data,

                f,

                ensure_ascii=False,

                indent=4

            )

        return True

    except Exception as e:

        log_error(f"Save JSON Error : {e}")

        return False

# ==========================================================
# BACKUP
# ==========================================================

def backup_file(path):

    if not os.path.exists(path):

        return

    filename = os.path.basename(path)

    backup_name = (

        datetime.now().strftime("%Y%m%d_%H%M%S")

        + "_"

        + filename

    )

    backup_path = os.path.join(

        BACKUP_DIR,

        backup_name

    )

    with open(path, "rb") as src:

        with open(backup_path, "wb") as dst:

            dst.write(src.read())

# ==========================================================
# DATABASE CACHE
# ==========================================================

PRODUCTS = load_json(PRODUCT_FILE)

ORDERS = load_json(ORDER_FILE)

# ==========================================================
# SECTION 1.4
# NORMALIZE ENGINE
# ==========================================================

BANGLA_DIGITS = str.maketrans(

    "০১২৩৪৫৬৭৮৯",

    "0123456789"

)

def normalize(text):

    if text is None:

        return ""

    text = str(text)

    text = text.translate(BANGLA_DIGITS)

    text = text.lower().strip()

    text = re.sub(r"\s+", " ", text)

    text = re.sub(

        r"[^\w\s\u0980-\u09FF]",

        " ",

        text

    )

    text = re.sub(r"\s+", " ", text)

    return text.strip()

# ==========================================================
# SAFE TEXT
# ==========================================================

def safe_text(text):

    if text is None:

        return ""

    return normalize(text)

# ==========================================================
# KEYWORD MATCH
# ==========================================================

def keyword_match(message, keywords):

    msg = normalize(message)

    for keyword in keywords:

        if normalize(keyword) in msg:

            return True

    return False

# ==========================================================
# CONTAINS ANY
# ==========================================================

def contains_any(message, words):

    msg = normalize(message)

    for word in words:

        if normalize(word) in msg:

            return True

    return False

# ==========================================================
# REMOVE DUPLICATE WORDS
# ==========================================================

def remove_duplicate_words(text):

    words = normalize(text).split()

    result = []

    for word in words:

        if word not in result:

            result.append(word)

    return " ".join(result)

# ==========================================================
# IS EMPTY
# ==========================================================

def is_empty(text):

    return len(normalize(text)) == 0

# ==========================================================
# TEXT LENGTH
# ==========================================================

def text_length(text):

    return len(normalize(text))

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

# ==========================================================
# SAVE USER MESSAGE
# ==========================================================

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

# ==========================================================
# LAST PRODUCT
# ==========================================================

def set_last_product(user_id, product_name):

    user = get_user(user_id)

    user["last_product"] = product_name

    user["updated_at"] = datetime.now().isoformat()

def get_last_product(user_id):

    return get_user(user_id)["last_product"]

# ==========================================================
# LAST REPLY
# ==========================================================

def set_last_reply(user_id, reply):

    user = get_user(user_id)

    user["last_reply"] = reply

def get_last_reply(user_id):

    return get_user(user_id)["last_reply"]

# ==========================================================
# HUMAN MODE
# ==========================================================

def enable_human_mode(user_id):

    get_user(user_id)["human_mode"] = True

def disable_human_mode(user_id):

    get_user(user_id)["human_mode"] = False

def is_human_mode(user_id):

    return get_user(user_id)["human_mode"]

# ==========================================================
# CLEAR MEMORY
# ==========================================================

def clear_memory(user_id):

    if user_id in USERS:

        USERS[user_id]["history"] = []

        USERS[user_id]["last_message"] = ""

        USERS[user_id]["last_product"] = ""

        USERS[user_id]["last_reply"] = ""

# ==========================================================
# SECTION 2.1
# PRODUCT DATABASE ENGINE
# ==========================================================

# PRODUCTS already loaded from JSON above. Do NOT overwrite with []

# ==========================================================
# PRODUCT TEMPLATE
# ==========================================================

def new_product():

    return {

        "id": "",

        "name": "",

        "price": "",

        "price_value": 0,

        "regular_price": "",

        "offer_price": "",

        "stock": "Available",

        "delivery": "২–৪ দিন",

        "delivery_charge": "100",

        "warranty": "No Warranty",

        "description": "",

        "features": [],

        "colors": [],

        "keywords": [],

        "images": [],

        "active": True

    }

# ==========================================================
# PRODUCT FUNCTIONS
# ==========================================================

def add_product(product):

    PRODUCTS.append(product)

def get_all_products():

    return PRODUCTS

def total_products():

    return len(PRODUCTS)

# ==========================================================
# PRODUCT LOOKUP
# ==========================================================

def get_product_by_name(name):

    name = normalize(name)

    for product in PRODUCTS:

        if normalize(product["name"]) == name:

            return product

    return None

def get_product_by_id(product_id):

    for product in PRODUCTS:

        if product["id"] == product_id:

            return product

    return None

# ==========================================================
# PRODUCT STATUS
# ==========================================================

def is_available(product):

    return product.get(

        "stock",

        ""

    ).lower() == "available"

# ==========================================================
# PRODUCT PRICE
# ==========================================================

def product_price(product):

    if product.get("offer_price"):

        return product["offer_price"]

    return product["price"]

# ==========================================================
# PRODUCT COLORS
# ==========================================================

def product_colors(product):

    if not product["colors"]:

        return "Not Available"

    return ", ".join(product["colors"])

# ==========================================================
# SECTION 2.2
# SMART PRODUCT SEARCH ENGINE
# ==========================================================

PRODUCT_INDEX = {}

def build_product_index():

    PRODUCT_INDEX.clear()

    for product in PRODUCTS:

        # Product Name
        PRODUCT_INDEX[
            normalize(product["name"])
        ] = product

        # Keywords
        for keyword in product.get("keywords", []):

            PRODUCT_INDEX[
                normalize(keyword)
            ] = product

def rebuild_product_index():

    build_product_index()

# ==========================================================
# PRODUCT SEARCH
# ==========================================================

def find_product(message):

    msg = normalize(message)

    # Exact Match
    if msg in PRODUCT_INDEX:

        return PRODUCT_INDEX[msg]

    # Contains Match
    for keyword, product in PRODUCT_INDEX.items():

        if keyword in msg:

            return product

    return None

# ==========================================================
# PRODUCT EXISTS
# ==========================================================

def product_exists(message):

    return find_product(message) is not None

# ==========================================================
# GET PRODUCT NAME
# ==========================================================

def get_product_name(message):

    product = find_product(message)

    if product:

        return product["name"]

    return None

# ==========================================================
# PRODUCT SEARCH BY PRICE
# ==========================================================

def search_by_price(price):

    result = []

    for product in PRODUCTS:

        if str(product["price_value"]) == str(price):

            result.append(product)

    return result

# ==========================================================
# PRODUCT SEARCH BY COLOR
# ==========================================================

def search_by_color(color):

    color = normalize(color)

    result = []

    for product in PRODUCTS:

        for c in product.get("colors", []):

            if normalize(c) == color:

                result.append(product)

                break

    return result

# ==========================================================
# PRODUCT SEARCH BY STOCK
# ==========================================================

def available_products():

    return [

        p

        for p in PRODUCTS

        if is_available(p)

    ]

# ==========================================================
# SECTION 2.3
# PRODUCT ALIAS ENGINE
# ==========================================================

PRODUCT_ALIASES = {}

def register_alias(alias, product_name):

    PRODUCT_ALIASES[

        normalize(alias)

    ] = normalize(product_name)

def build_alias_index():

    PRODUCT_ALIASES.clear()

    for product in PRODUCTS:

        name = normalize(

            product["name"]

        )

        register_alias(

            product["name"],

            product["name"]

        )

        for keyword in product.get(

            "keywords",

            []

        ):

            register_alias(

                keyword,

                product["name"]

            )

# ==========================================================
# FIND PRODUCT BY ALIAS
# ==========================================================

def find_product_by_alias(message):

    msg = normalize(message)

    for alias, product_name in PRODUCT_ALIASES.items():

        if alias in msg:

            return get_product_by_name(

                product_name

            )

    return None

# ==========================================================
# SMART PRODUCT SEARCH
# ==========================================================

def smart_product_search(message):

    product = find_product(message)

    if product:

        return product

    product = find_product_by_alias(message)

    if product:

        return product

    return None

# ==========================================================
# PRODUCT SUGGESTION
# ==========================================================

def suggest_products(message):

    msg = normalize(message)

    result = []

    for product in PRODUCTS:

        score = 0

        for keyword in product.get(

            "keywords",

            []

        ):

            if normalize(keyword) in msg:

                score += 1

        if score:

            result.append(

                (

                    score,

                    product

                )

            )

    result.sort(

        reverse=True,

        key=lambda x: x[0]

    )

    return [

        item[1]

        for item in result[:3]

    ]

# ==========================================================
# REBUILD
# ==========================================================

def rebuild_search_engine():

    rebuild_product_index()

    build_alias_index()

# ==========================================================
# SECTION 2.4
# PRODUCT REPLY ENGINE
# ==========================================================

def format_product_reply(product):

    features = ""

    for item in product.get("features", []):

        features += f"• {item}\n"

    colors = ", ".join(

        product.get("colors", [])

    )

    return f"""🛍️ {product['name']}

💰 মূল্য: {product['price']}

📦 Stock: {product['stock']}

📝 {product['description']}

🎨 Color:
{colors}

✨ প্রধান Features:

{features}

🛡️ Warranty:
{product['warranty']}

🚚 Delivery:
{product['delivery']}

💳 Delivery Charge:
৳{product['delivery_charge']}

অর্ডার করতে
"অর্ডার করতে চাই"
লিখুন।
"""

# ==========================================================
# PRICE
# ==========================================================

PRICE_KEYWORDS = [

"price",

"দাম",

"মূল্য",

"offer",

"কত",

"tk",

"৳"

]

def is_price_question(message):

    return keyword_match(

        message,

        PRICE_KEYWORDS

    )

def price_reply(product):

    return f"""💰 {product['name']}

মূল্যঃ {product['price']}"""

# ==========================================================
# COLOR
# ==========================================================

COLOR_KEYWORDS = [

"color",

"colour",

"রং",

"কালার"

]

def color_reply(product):

    colors = product.get(

        "colors",

        []

    )

    if not colors:

        return "এই প্রোডাক্টের Color তথ্য নেই।"

    return (

        "🎨 Available Color:\n\n"

        + "\n".join(

            f"• {c}"

            for c in colors

        )

    )

# ==========================================================
# STOCK
# ==========================================================

STOCK_KEYWORDS = [

"stock",

"স্টক",

"available",

"আছে"

]

def stock_reply(product):

    return (

        f"📦 Stock : "

        f"{product['stock']}"

    )

# ==========================================================
# DELIVERY
# ==========================================================

DELIVERY_KEYWORDS = [

"delivery",

"ডেলিভারি",

"কত দিনে",

"courier"

]

def delivery_reply(product):

    return f"""

🚚 Delivery Time

{product['delivery']}

💳 Delivery Charge

৳{product['delivery_charge']}
"""

# ==========================================================
# WARRANTY
# ==========================================================

WARRANTY_KEYWORDS = [

"warranty",

"গ্যারান্টি",

"ওয়ারেন্টি"

]

def warranty_reply(product):

    return (

        "🛡️ Warranty\n\n"

        f"{product['warranty']}"

    )

# ==========================================================
# FEATURES
# ==========================================================

FEATURE_KEYWORDS = [

"feature",

"features",

"স্পেসিফিকেশন",

"কি কি আছে"

]

def feature_reply(product):

    text = "✨ প্রধান Features\n\n"

    for item in product.get(

        "features",

        []

    ):

        text += f"• {item}\n"

    return text

# ==========================================================
# SECTION 2.5
# PRODUCT INTENT ROUTER
# ==========================================================

def product_reply(user_id, message):

    product = smart_product_search(message)

    if not product:

        return None

    set_last_product(user_id, product["name"])

    # Price
    if is_price_question(message):

        return price_reply(product)

    # Color
    if keyword_match(
        message,
        COLOR_KEYWORDS
    ):

        return color_reply(product)

    # Stock
    if keyword_match(
        message,
        STOCK_KEYWORDS
    ):

        return stock_reply(product)

    # Delivery
    if keyword_match(
        message,
        DELIVERY_KEYWORDS
    ):

        return delivery_reply(product)

    # Warranty
    if keyword_match(
        message,
        WARRANTY_KEYWORDS
    ):

        return warranty_reply(product)

    # Features
    if keyword_match(
        message,
        FEATURE_KEYWORDS
    ):

        return feature_reply(product)

    # Default Product Reply
    return format_product_reply(product)

# ==========================================================
# CONTINUE LAST PRODUCT
# ==========================================================

def continue_last_product(
    user_id,
    message
):

    last = get_last_product(user_id)

    if not last:

        return None

    product = get_product_by_name(last)

    if not product:

        return None

    if is_price_question(message):

        return price_reply(product)

    if keyword_match(
        message,
        COLOR_KEYWORDS
    ):

        return color_reply(product)

    if keyword_match(
        message,
        STOCK_KEYWORDS
    ):

        return stock_reply(product)

    if keyword_match(
        message,
        DELIVERY_KEYWORDS
    ):

        return delivery_reply(product)

    if keyword_match(
        message,
        WARRANTY_KEYWORDS
    ):

        return warranty_reply(product)

    if keyword_match(
        message,
        FEATURE_KEYWORDS
    ):

        return feature_reply(product)

    return None

# ==========================================================
# MAIN PRODUCT ENGINE
# ==========================================================

def handle_product_message(
    user_id,
    message
):

    reply = product_reply(user_id, message)

    if reply:

        return reply

    reply = continue_last_product(
        user_id,
        message
    )

    if reply:

        return reply

    return None

# ==========================================================
# SECTION 2.6
# PRODUCT RECOMMENDATION ENGINE
# ==========================================================

BEST_SELLERS = []

NEW_PRODUCTS = []

def register_best_seller(product_name):

    BEST_SELLERS.append(

        normalize(product_name)

    )

def register_new_product(product_name):

    NEW_PRODUCTS.append(

        normalize(product_name)

    )

# ==========================================================
# LIST PRODUCTS
# ==========================================================

def list_products(limit=None):

    items = PRODUCTS

    if limit:

        items = PRODUCTS[:limit]

    text = "🛍️ আমাদের প্রোডাক্টসমূহ\n\n"

    for p in items:

        text += (

            f"• {p['name']}\n"

            f"৳ {p['price']}\n\n"

        )

    return text

# ==========================================================
# BEST SELLER
# ==========================================================

def best_seller_reply():

    text = "🔥 জনপ্রিয় প্রোডাক্ট\n\n"

    for name in BEST_SELLERS:

        product = get_product_by_name(name)

        if product:

            text += (

                f"• {product['name']}\n"

            )

    return text

# ==========================================================
# NEW PRODUCTS
# ==========================================================

def new_product_reply():

    text = "🆕 নতুন প্রোডাক্ট\n\n"

    for name in NEW_PRODUCTS:

        product = get_product_by_name(name)

        if product:

            text += (

                f"• {product['name']}\n"

            )

    return text

# ==========================================================
# CHEAPEST PRODUCT
# ==========================================================

def cheapest_product():

    if not PRODUCTS:

        return None

    product = min(

        PRODUCTS,

        key=lambda x: x["price_value"]

    )

    return format_product_reply(product)

# ==========================================================
# MOST EXPENSIVE
# ==========================================================

def expensive_product():

    if not PRODUCTS:

        return None

    product = max(

        PRODUCTS,

        key=lambda x: x["price_value"]

    )

    return format_product_reply(product)

# ==========================================================
# PRODUCT RECOMMENDATION
# ==========================================================

RECOMMEND_KEYWORDS = [

    "সব",

    "all",

    "product",

    "products",

    "popular",

    "জনপ্রিয়",

    "best",

    "new",

    "নতুন",

    "cheap",

    "সস্তা",

    "expensive",

    "দামি"

]

def recommendation_reply(message):

    msg = normalize(message)

    if "সব" in msg or "all" in msg:

        return list_products()

    if "popular" in msg or "জনপ্রিয়" in msg or "best" in msg:

        return best_seller_reply()

    if "new" in msg or "নতুন" in msg:

        return new_product_reply()

    if "সস্তা" in msg or "cheap" in msg:

        return cheapest_product()

    if "দামি" in msg or "expensive" in msg:

        return expensive_product()

    return None

# ==========================================================
# SECTION 3.1
# FAQ DATABASE
# ==========================================================

FAQ_DATABASE = []

# ==========================================================
# FAQ TEMPLATE
# ==========================================================

def new_faq():

    return {

        "id":"",

        "title":"",

        "keywords":[],

        "reply":"",

        "priority":1,

        "active":True

    }

# ==========================================================
# FAQ FUNCTIONS
# ==========================================================

def add_faq(faq):

    FAQ_DATABASE.append(faq)

def total_faq():

    return len(FAQ_DATABASE)

def get_all_faq():

    return FAQ_DATABASE

# ==========================================================
# FAQ SEARCH
# ==========================================================

def find_faq(message):

    msg = normalize(message)

    best = None

    score = 0

    for faq in FAQ_DATABASE:

        if not faq["active"]:

            continue

        current = 0

        for keyword in faq["keywords"]:

            if normalize(keyword) in msg:

                current += 1

        if current > score:

            score = current

            best = faq

    return best

# ==========================================================
# FAQ REPLY
# ==========================================================

def faq_reply(message):

    faq = find_faq(message)

    if faq:

        return faq["reply"]

    return None

# ==========================================================
# SECTION 3.2
# DEFAULT FAQ DATABASE
# ==========================================================

def load_default_faq():

    FAQ_DATABASE.clear()

    FAQ_DATABASE.extend([

        {
            "id":"delivery",
            "title":"Delivery",
            "keywords":[
                "delivery",
                "ডেলিভারি",
                "কত দিনে",
                "courier",
                "shipping"
            ],
            "reply":"🚚 সারা বাংলাদেশে হোম ডেলিভারি করা হয়। ডেলিভারি সময় ২–৪ কার্যদিবস।",
            "priority":10,
            "active":True
        },

        {
            "id":"charge",
            "title":"Delivery Charge",
            "keywords":[
                "delivery charge",
                "চার্জ",
                "কুরিয়ার চার্জ",
                "shipping charge"
            ],
            "reply":"💳 ডেলিভারি চার্জ ৳100। কিছু অফারে ফ্রি ডেলিভারি থাকে।",
            "priority":10,
            "active":True
        },

        {
            "id":"payment",
            "title":"Payment",
            "keywords":[
                "payment",
                "পেমেন্ট",
                "কিভাবে টাকা দিব",
                "cash on delivery",
                "cod"
            ],
            "reply":"💵 আমরা Cash on Delivery সুবিধা প্রদান করি।",
            "priority":10,
            "active":True
        },

        {
            "id":"stock",
            "title":"Stock",
            "keywords":[
                "stock",
                "স্টক",
                "available",
                "আছে"
            ],
            "reply":"📦 স্টক প্রতিদিন আপডেট হয়। নির্দিষ্ট প্রোডাক্টের নাম লিখলে বর্তমান স্টক জানানো হবে।",
            "priority":9,
            "active":True
        },

        {
            "id":"order",
            "title":"Order",
            "keywords":[
                "অর্ডার",
                "order",
                "buy",
                "কিনতে চাই"
            ],
            "reply":"🛍️ অর্ডার করতে শুধু লিখুন: 'অর্ডার করতে চাই'।",
            "priority":10,
            "active":True
        },

        {
            "id":"review",
            "title":"Review",
            "keywords":[
                "review",
                "রিভিউ",
                "feedback"
            ],
            "reply":"⭐ আমাদের পেইজে অনেক বাস্তব Customer Review রয়েছে।",
            "priority":8,
            "active":True
        },

        {
            "id":"warranty",
            "title":"Warranty",
            "keywords":[
                "warranty",
                "ওয়ারেন্টি",
                "গ্যারান্টি"
            ],
            "reply":"🛡️ প্রতিটি প্রোডাক্টের Warranty আলাদা। প্রোডাক্টের নাম লিখলে বিস্তারিত জানানো হবে।",
            "priority":9,
            "active":True
        },

        {
            "id":"return",
            "title":"Return",
            "keywords":[
                "return",
                "ফেরত",
                "refund"
            ],
            "reply":"📦 সমস্যা থাকলে আমাদের সাপোর্ট টিমের সাথে যোগাযোগ করুন। শর্ত অনুযায়ী সমাধান দেওয়া হবে।",
            "priority":8,
            "active":True
        }

    ])

# ==========================================================
# LOAD FAQ ON STARTUP
# ==========================================================

load_default_faq()

# ==========================================================
# SECTION 3.3
# SMART FAQ SEARCH ENGINE
# ==========================================================

FAQ_INDEX = {}

FAQ_CACHE = {}

# ==========================================================
# BUILD FAQ INDEX
# ==========================================================

def build_faq_index():

    FAQ_INDEX.clear()

    for faq in FAQ_DATABASE:

        if not faq.get("active", True):

            continue

        for keyword in faq.get("keywords", []):

            FAQ_INDEX[

                normalize(keyword)

            ] = faq

# ==========================================================
# REBUILD FAQ INDEX
# ==========================================================

def rebuild_faq_index():

    build_faq_index()

    FAQ_CACHE.clear()

# ==========================================================
# FAST FAQ SEARCH
# ==========================================================

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

# ==========================================================
# SMART FAQ REPLY
# ==========================================================

def smart_faq_reply(message):

    faq = fast_find_faq(message)

    if faq:

        return faq["reply"]

    return None

# ==========================================================
# FAQ EXISTS
# ==========================================================

def faq_exists(message):

    return fast_find_faq(message) is not None

# ==========================================================
# FAQ COUNT
# ==========================================================

def faq_count():

    return len(FAQ_DATABASE)

# ==========================================================
# LOAD INDEX
# ==========================================================

rebuild_faq_index()

# ==========================================================
# SECTION 3.4
# FAQ INTENT ENGINE
# ==========================================================

FAQ_SYNONYMS = {

    "ডেলিভারি":"delivery",
    "ডেলিভারী":"delivery",
    "courier":"delivery",
    "shipping":"delivery",

    "price":"price",
    "মূল্য":"price",
    "দাম":"price",

    "payment":"payment",
    "pay":"payment",
    "টাকা":"payment",

    "order":"order",
    "buy":"order",
    "কিনতে":"order",
    "অর্ডার":"order",

    "review":"review",
    "feedback":"review",

    "stock":"stock",
    "available":"stock",

    "return":"return",
    "refund":"return",

    "warranty":"warranty",
    "গ্যারান্টি":"warranty",

    "exchange":"exchange",

    "location":"location",
    "address":"location"

}

# ==========================================================
# NORMALIZE FAQ INTENT
# ==========================================================

def normalize_intent(message):

    msg = normalize(message)

    words = msg.split()

    output = []

    for word in words:

        output.append(

            FAQ_SYNONYMS.get(

                word,

                word

            )

        )

    return " ".join(output)

# ==========================================================
# SMART FAQ SEARCH
# ==========================================================

def smart_intent_faq(message):

    msg = normalize_intent(message)

    faq = fast_find_faq(msg)

    if faq:

        return faq

    return find_faq(msg)

# ==========================================================
# FINAL FAQ REPLY
# ==========================================================

def final_faq_reply(message):

    faq = smart_intent_faq(message)

    if faq:

        return faq["reply"]

    return None

# ==========================================================
# FAQ PRIORITY
# ==========================================================

def sort_faq():

    FAQ_DATABASE.sort(

        key=lambda x: (

            x["priority"]

        ),

        reverse=True

    )

sort_faq()

# ==========================================================
# SECTION 3.5
# CONVERSATION ENGINE
# ==========================================================

CONVERSATIONS = {

    "greeting":{

        "keywords":[

            "hi",

            "hello",

            "hey",

            "হ্যালো",

            "আসসালামু আলাইকুম",

            "assalamu alaikum",

            "slm",

            "salam"

        ],

        "reply":"আসসালামু আলাইকুম। সবুজ বাড়ি-এ আপনাকে স্বাগতম। 😊\n\nআপনি কোন প্রোডাক্টটি খুঁজছেন?\nপ্রোডাক্টের নাম লিখুন অথবা ছবি পাঠান।"

    },

    "thanks":{

        "keywords":[

            "thanks",

            "thank you",

            "ধন্যবাদ",

            "thank",

            "tnx",

            "thx"

        ],

        "reply":"আপনাকেও ধন্যবাদ। 💚\nআর কোনো তথ্য লাগলে জানাবেন।"

    },

    "ok":{

        "keywords":[

            "ok",

            "okay",

            "okk",

            "ঠিক আছে",

            "আচ্ছা",

            "হুম",

            "hum"

        ],

        "reply":"😊 ঠিক আছে। আর কোনো তথ্য লাগলে জানাবেন।"

    },

    "bye":{

        "keywords":[

            "bye",

            "বিদায়",

            "allah hafez",

            "আল্লাহ হাফেজ"

        ],

        "reply":"আল্লাহ হাফেজ। 💚\nআবার প্রয়োজন হলে অবশ্যই মেসেজ করবেন।"

    }

}

# ==========================================================
# CONVERSATION REPLY
# ==========================================================

def conversation_reply(message):

    msg = normalize(message)

    for item in CONVERSATIONS.values():

        for keyword in item["keywords"]:

            if normalize(keyword) in msg:

                return item["reply"]

    return None

# ==========================================================
# IS SMALL TALK
# ==========================================================

def is_small_talk(message):

    return conversation_reply(message) is not None

# ==========================================================
# SECTION 3.6
# HUMAN HANDOVER ENGINE
# ==========================================================

HUMAN_KEYWORDS = [

    

    "support",

    "agent",

    "human",

    "ম্যানেজার",

    "মানুষ",

    "লোক",

    "অভিযোগ",

    "problem",

    "call",

    "phone",

    "যোগাযোগ",

    "কথা বলতে চাই",

    "লাইভ"

]

HUMAN_REPLY = """
👨‍💼 আপনার অনুরোধটি আমাদের টিমের কাছে পাঠানো হয়েছে।

অনুগ্রহ করে একটু অপেক্ষা করুন।

আমাদের প্রতিনিধি খুব দ্রুত আপনার সাথে যোগাযোগ করবেন। 😊
"""

# ==========================================================
# HUMAN REQUEST
# ==========================================================

def is_human_request(message):

    return keyword_match(

        message,

        HUMAN_KEYWORDS

    )

# ==========================================================
# ENABLE HUMAN
# ==========================================================

def start_human_mode(user_id):

    enable_human_mode(user_id)

    return HUMAN_REPLY

# ==========================================================
# DISABLE HUMAN
# ==========================================================

def stop_human_mode(user_id):

    disable_human_mode(user_id)

    return "✅ আপনি আবার Bot Service-এ ফিরে এসেছেন।"

# ==========================================================
# CHECK MODE
# ==========================================================

def handle_human_mode(user_id, message):

    # Resume bot command
    if normalize(message) in [
        "admin_resume",
        "resume",
        "bot",
        "bot resume"
    ]:
        return admin_resume(user_id)

    # New human request
    if is_human_request(message):
        return start_human_mode(user_id)

    # Already in human mode
    if is_human_mode(user_id):
        return HUMAN_REPLY

    return None
# ==========================================================
# ADMIN COMMAND
# ==========================================================

def admin_resume(user_id):

    disable_human_mode(user_id)

    return "Bot Service চালু হয়েছে।"

# ==========================================================
# SECTION 4.0
# ORDER SYSTEM
# ==========================================================

ORDER_KEYWORDS = [
    "অর্ডার",
    "অর্ডার করতে চাই",
    "order",
    "buy",
    "কিনতে চাই"
]

ORDER_STEPS = {}

def start_order(user_id):

    last_product = get_last_product(user_id)

    if not last_product:
        return "অর্ডার শুরু করতে প্রথমে একটি প্রোডাক্টের নাম লিখুন।"

    product = get_product_by_name(last_product)

    if not product:
        return "প্রোডাক্ট খুঁজে পাওয়া যায়নি। আবার প্রোডাক্টের নাম লিখুন।"

    ORDER_STEPS[user_id] = {
        "step": "name",
        "product": product["name"],
        "price": product["price"],
        "name": "",
        "phone": "",
        "address": ""
    }

    return f"📝 {product['name']} অর্ডার করতে চাচ্ছেন।\n\nআপনার নাম লিখুন।"

def handle_order(user_id, message):

    if user_id not in ORDER_STEPS:
        return None

    session = ORDER_STEPS[user_id]

    if session["step"] == "name":

        session["name"] = message.strip()
        session["step"] = "phone"

        return "📞 আপনার মোবাইল নম্বর লিখুন।"

    elif session["step"] == "phone":

        session["phone"] = message.strip()
        session["step"] = "address"

        return "📍 আপনার সম্পূর্ণ ঠিকানা লিখুন।"

    elif session["step"] == "address":

        session["address"] = message.strip()

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
            f"🛍️ প্রোডাক্ট: {order['product']}\n"
            f"👤 নাম: {order['customer_name']}\n"
            f"📞 ফোন: {order['phone']}\n"
            f"📍 ঠিকানা: {order['address']}\n"
            f"🆔 Order ID: {order['id']}"
        )

    return None

# ==========================================================
# SECTION 3.7 + 3.8
# MAIN REPLY ENGINE (Single Definition)
# ==========================================================

UNKNOWN_COUNTER = {}

def increase_unknown(user_id):

    UNKNOWN_COUNTER[user_id] = (

        UNKNOWN_COUNTER.get(user_id, 0) + 1

    )

    return UNKNOWN_COUNTER[user_id]

def reset_unknown(user_id):

    UNKNOWN_COUNTER[user_id] = 0

def unknown_count(user_id):

    return UNKNOWN_COUNTER.get(user_id, 0)

# ==========================================================
# SIMILAR PRODUCT
# ==========================================================

def suggest_similar_product(message):

    products = suggest_products(message)

    if not products:

        return None

    text = "😌 আপনার কথার সাথে মিল থাকা কিছু প্রোডাক্ট:\n\n"

    for p in products:

        text += f"• {p['name']}\n"

    text += "\nযেটি জানতে চান, শুধু নাম লিখুন।"

    return text

# ==========================================================
# FINAL FALLBACK
# ==========================================================

def fallback_reply(user_id, message):

    reset_unknown(user_id)

    suggestion = suggest_similar_product(message)

    if suggestion:

        return suggestion

    return DEFAULT_REPLY

# ==========================================================
# MAIN GENERATE REPLY (Only one definition)
# ==========================================================

def generate_reply(user_id, message):

    message = safe_text(message)

    if is_empty(message):

        return DEFAULT_REPLY

    save_message(user_id, message)
    # Admin / Bot Resume
    if normalize(message) in [
        "admin_resume",
        "resume",
        "bot",
        "bot resume"
    ]:
        reset_unknown(user_id)
        return admin_resume(user_id)
    # 1. Ongoing Order Handling (highest priority)
    reply = handle_order(user_id, message)
    if reply:
        reset_unknown(user_id)
        return reply

    # 2. Human Mode
    reply = handle_human_mode(user_id, message)
    if reply:
        reset_unknown(user_id)
        return reply

    # 3. Conversation
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

    # 8. Fallback
    increase_unknown(user_id)
    return fallback_reply(user_id, message)

# ==========================================================
# QUICK REPLY
# ==========================================================

def quick_reply(user_id, message):

    return generate_reply(

        user_id,

        message

    )

# ==========================================================
# PROCESS TEXT MESSAGE
# ==========================================================

def process_text_message(

    user_id,

    message

):

    return generate_reply(

        user_id,

        message

    )

# ==========================================================
# SECTION 4.1
# FACEBOOK MESSENGER API
# ==========================================================

HEADERS = {
    "Content-Type": "application/json"
}

def graph_url():

    return (

        f"{GRAPH_API}"

        f"?access_token={PAGE_ACCESS_TOKEN}"

    )

# ==========================================================
# SEND API
# ==========================================================

def send_message(

    recipient_id,

    message

):

    payload = {

        "recipient": {

            "id": recipient_id

        },

        "message": {

            "text": message

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

        log_info(

            f"Message Sent -> {recipient_id}"

        )

        return True

    except Exception as e:

        log_error(

            f"Send Error : {e}"

        )

        return False

# ==========================================================
# MARK AS SEEN
# ==========================================================

def mark_seen(

    recipient_id

):

    payload = {

        "recipient": {

            "id": recipient_id

        },

        "sender_action": "mark_seen"

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

# ==========================================================
# TYPING ON
# ==========================================================

def typing_on(

    recipient_id

):

    payload = {

        "recipient": {

            "id": recipient_id

        },

        "sender_action": "typing_on"

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

# ==========================================================
# TYPING OFF
# ==========================================================

def typing_off(

    recipient_id

):

    payload = {

        "recipient": {

            "id": recipient_id

        },

        "sender_action": "typing_off"

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

# ==========================================================
# SECTION 4.2
# FACEBOOK WEBHOOK
# ==========================================================

@app.route("/", methods=["GET"])
def home():

    return "Sabuj Bari Messenger Bot Running ✅", 200

# ==========================================================
# WEBHOOK VERIFY
# ==========================================================

@app.route("/webhook", methods=["GET"])
def verify_webhook():

    mode = request.args.get("hub.mode")

    token = request.args.get("hub.verify_token")

    challenge = request.args.get("hub.challenge")

    if (

        mode == "subscribe"

        and

        token == VERIFY_TOKEN

    ):

        return challenge, 200

    return "Verification Failed", 403

# ==========================================================
# WEBHOOK RECEIVE
# ==========================================================

@app.route("/webhook", methods=["POST"])
def webhook():

    body = request.get_json()

    if body.get("object") != "page":

        return "ignored", 200

    for entry in body.get("entry", []):

        for event in entry.get("messaging", []):

            process_event(event)

    return "ok", 200

# ==========================================================
# PROCESS EVENT
# ==========================================================

def process_event(event):

    sender = event.get("sender", {}).get("id")

    if not sender:

        return

    # Ignore Echo Message
    if event.get("message", {}).get("is_echo"):

        return

    # Text Message
    if "message" in event:

        process_message(

            sender,

            event["message"]

        )

    # Postback
    elif "postback" in event:

        process_postback(

            sender,

            event["postback"]

        )

# ==========================================================
# POSTBACK
# ==========================================================

def process_postback(

    sender,

    postback

):

    payload = postback.get(

        "payload",

        ""

    )

    reply = f"Postback : {payload}"

    typing_on(sender)

    typing_delay()

    typing_off(sender)

    send_message(

        sender,

        reply

    )

# ==========================================================
# SECTION 4.3
# PROCESS MESSAGE
# ==========================================================

def process_message(user_id, message):

    try:

        mark_seen(user_id)

        typing_on(user_id)

        typing_delay()

        text = message.get("text", "")

        # -----------------------------
        # Attachment
        # -----------------------------
        if not text:

            attachments = message.get("attachments", [])

            if attachments:

                reply = (
                    "📷 ছবি পেয়েছি।\n\n"
                    "অনুগ্রহ করে প্রোডাক্টের নাম লিখুন অথবা "
                    "ছবিটি কোন প্রোডাক্ট সম্পর্কে জানাতে চান তা বলুন।"
                )

            else:

                reply = DEFAULT_REPLY

        # -----------------------------
        # Text
        # -----------------------------
        else:

            reply = generate_reply(

                user_id,

                text

            )

        typing_off(user_id)

        send_message(

            user_id,

            reply

        )

    except Exception as e:

        typing_off(user_id)

        log_error(

            f"Process Message Error : {e}"

        )

        send_message(

            user_id,

            "❌ সাময়িক সমস্যা হয়েছে। অনুগ্রহ করে আবার চেষ্টা করুন।"

        )

# ==========================================================
# IMAGE CHECK
# ==========================================================

def has_image(message):

    attachments = message.get(

        "attachments",

        []

    )

    for item in attachments:

        if item.get("type") == "image":

            return True

    return False

# ==========================================================
# FILE CHECK
# ==========================================================

def has_file(message):

    attachments = message.get(

        "attachments",

        []

    )

    return len(attachments) > 0

# ==========================================================
# GET TEXT
# ==========================================================

def get_message_text(message):

    return message.get(

        "text",

        ""

    ).strip()

# ==========================================================
# SECTION 4.4
# QUICK REPLY & BUTTON MESSAGE
# ==========================================================

def send_quick_reply(

    recipient_id,

    text,

    buttons

):

    quick_replies = []

    for button in buttons:

        quick_replies.append({

            "content_type":"text",

            "title":button["title"],

            "payload":button["payload"]

        })

    payload = {

        "recipient":{

            "id":recipient_id

        },

        "message":{

            "text":text,

            "quick_replies":quick_replies

        }

    }

    try:

        requests.post(

            graph_url(),

            headers=HEADERS,

            json=payload,

            timeout=15

        )

        return True

    except Exception as e:

        log_error(

            f"Quick Reply Error : {e}"

        )

        return False

# ==========================================================
# BUTTON TEMPLATE
# ==========================================================

def send_button_message(

    recipient_id,

    text,

    buttons

):

    payload = {

        "recipient":{

            "id":recipient_id

        },

        "message":{

            "attachment":{

                "type":"template",

                "payload":{

                    "template_type":"button",

                    "text":text,

                    "buttons":buttons

                }

            }

        }

    }

    try:

        requests.post(

            graph_url(),

            headers=HEADERS,

            json=payload,

            timeout=15

        )

        return True

    except Exception as e:

        log_error(

            f"Button Message Error : {e}"

        )

        return False

# ==========================================================
# URL BUTTON
# ==========================================================

def url_button(

    title,

    url

):

    return {

        "type":"web_url",

        "title":title,

        "url":url

    }

# ==========================================================
# POSTBACK BUTTON
# ==========================================================

def postback_button(

    title,

    payload

):

    return {

        "type":"postback",

        "title":title,

        "payload":payload

    }

# ==========================================================
# PHONE BUTTON
# ==========================================================

def phone_button(

    title,

    phone

):

    return {

        "type":"phone_number",

        "title":title,

        "payload":phone

    }

# ==========================================================
# DATABASE RELOAD
# ==========================================================

def reload_database():

    global PRODUCTS
    global FAQ_DATABASE
    global ORDERS

    PRODUCTS = load_json(PRODUCT_FILE)
    ORDERS = load_json(ORDER_FILE)

    # FAQ Load (JSON first, fallback to default)
    FAQ_DATABASE = load_json(FAQ_FILE)

    if not FAQ_DATABASE:
        load_default_faq()

    rebuild_search_engine()
    rebuild_faq_index()

    log_info("✅ Database Loaded Successfully.")


# ==========================================================
# STARTUP
# ==========================================================

def startup():

    reload_database()

    log_info("✅ Sabuj Bari Bot Started.")


# ==========================================================
# RUN APPLICATION
# ==========================================================

if __name__ == "__main__":

    startup()

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )
