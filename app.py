import hashlib
import hmac
import json
import logging
import os
import re
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv
from flask import Flask, request
from openai import OpenAI


# =========================================================
# APP INITIALIZATION
# =========================================================

load_dotenv()

app = Flask(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)

HTTP = requests.Session()
EXECUTOR = ThreadPoolExecutor(max_workers=4)


# =========================================================
# ENVIRONMENT VARIABLES
# =========================================================

BOT_NAME = os.getenv("BOT_NAME", "সবুজ বাড়ি AI").strip()

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "").strip()
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN", "").strip()
META_APP_SECRET = os.getenv("META_APP_SECRET", "").strip()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip()

GRAPH_API_VERSION = os.getenv("GRAPH_API_VERSION", "v26.0").strip()

ADMIN_NAME = os.getenv("ADMIN_NAME", "Arafat Rahman").strip()
ADMIN_PHONE = os.getenv("ADMIN_PHONE", "01780618736").strip()


# =========================================================
# HARD-CODED PRODUCT DATABASE
# =========================================================

PRODUCTS: List[Dict[str, Any]] = [
    {
        "keywords": [
            "ক্যামেরা", "camera", "digital camera", "print camera",
            "ai camera", "প্রিন্ট ক্যামেরা"
        ],
        "name": "Premium Digital Camera",
        "category": "Camera",
        "price": 2150,
        "offer_price": 2150,
        "details": (
            "চীন থেকে সরাসরি ইমপোর্ট করা ভালো মানের প্রোডাক্ট। "
            "পরিষ্কার ছবি তোলে, সঙ্গে সঙ্গে ছবি প্রিন্ট করা যায় এবং "
            "বাচ্চা ও বড়—সবার জন্য দারুণ একটি গিফট।"
        ),
        "features": [
            "Includes 32GB Memory Card",
            "পরিষ্কার ছবি তোলে",
            "সঙ্গে সঙ্গে ছবি প্রিন্ট করা যায়",
            "বাচ্চা ও বড়দের জন্য সুন্দর গিফট",
        ],
        "colors": [],
        "warranty": "No Warranty",
        "delivery_charge": 100,
        "delivery_time": "2-4 Days",
        "stock": "In Stock",
        "status": "Active",
        "image_url": "",
    },
    {
        "keywords": [
            "4k", "flip camera", "camera", "4k camera",
            "4k flip digital camera"
        ],
        "name": "4K Flip Digital Camera",
        "category": "Camera",
        "price": 2690,
        "offer_price": 2690,
        "details": (
            "4K Recording, Flip Screen এবং Premium Design। "
            "অর্ডার কনফার্ম করতে পছন্দের রঙ জানাতে হবে।"
        ),
        "features": [
            "4K Recording",
            "Flip Screen",
            "Premium Design",
        ],
        "colors": ["Pink", "Black", "White", "Purple", "Brown"],
        "warranty": "No Warranty",
        "delivery_charge": 100,
        "delivery_time": "2-4 Days",
        "stock": "In Stock",
        "status": "Active",
        "image_url": "",
    },
    {
        "keywords": [
            "galaxy projector", "projector lamp", "galaxy lamp",
            "star projector", "প্রজেক্টর", "গ্যালাক্সি ল্যাম্প"
        ],
        "name": "Galaxy Projector Lamp",
        "category": "Home Decor",
        "price": 3600,
        "offer_price": 3600,
        "details": (
            "আপনার রুমকে মুহূর্তেই তারাভরা আকাশের মতো সুন্দর করে তুলুন। "
            "Bedroom, Living Room, Party এবং Gift-এর জন্য উপযোগী।"
        ),
        "features": [
            "Galaxy & Star Projection",
            "Bluetooth Speaker",
            "White Noise",
            "Remote Control",
            "13 Projection Themes",
            "Adjustable Brightness",
            "Timer Function",
            "USB Type-C Power",
        ],
        "box_items": [
            "Galaxy Projector Lamp",
            "Remote Control",
            "USB Type-C Cable",
            "User Manual",
        ],
        "colors": [],
        "warranty": "No Warranty",
        "delivery_charge": 100,
        "delivery_time": "2-4 Days",
        "stock": "In Stock",
        "status": "Active",
        "image_url": "",
    },
    {
        "keywords": [
            "জুসার", "juicer", "blender", "mini juicer",
            "brushless motor juicer"
        ],
        "name": "High Quality Brushless Motor Mini Juicer",
        "category": "Kitchen",
        "price": 890,
        "offer_price": 890,
        "details": "ফল ও সবজি ব্লেন্ড করার জন্য Portable Mini Juicer।",
        "features": [
            "Brushless Motor",
            "Portable Design",
            "Fruit & Vegetable Blender",
        ],
        "colors": [],
        "warranty": "No Warranty",
        "delivery_charge": 0,
        "delivery_time": "2-4 Days",
        "stock": "In Stock",
        "status": "Active",
        "image_url": "",
    },
    {
        "keywords": [
            "ইয়ারবাড", "earbuds", "clip on", "open ear",
            "wireless earbuds", "হেডফোন"
        ],
        "name": "Clip-On Open Ear Wireless Earbuds",
        "category": "Audio",
        "price": 1600,
        "offer_price": 1600,
        "details": (
            "পরিষ্কার ভয়েস কোয়ালিটি, বিল্ট-ইন মাইক্রোফোন, "
            "কল রিসিভ/রিজেক্ট এবং গান শোনা ও ফোনে কথা বলা—দুটোর জন্য ব্যবহার করা যায়।"
        ),
        "features": [
            "Open Ear Design",
            "Clip-On Design",
            "Built-in Microphone",
            "Call Receive/Reject",
            "Comfortable & Stylish",
        ],
        "colors": [],
        "warranty": "No Warranty",
        "delivery_charge": 100,
        "delivery_time": "2-4 Days",
        "stock": "In Stock",
        "status": "Active",
        "image_url": "",
    },
    {
        "keywords": [
            "butterfly", "headset", "butterfly headset",
            "bluetooth headset", "butterfly earrings"
        ],
        "name": "Butterfly Earrings Bluetooth Headset (2025 New Model)",
        "category": "Audio",
        "price": 1250,
        "offer_price": 1250,
        "details": "Butterfly Earrings style Clip-On Open Ear Bluetooth Headset।",
        "features": [
            "Butterfly Earrings Design",
            "Bluetooth 5.4",
            "Real-time Translation",
            "Clip-on Open Ear",
            "Noise Reduction",
            "Up to 15 Hours Battery",
        ],
        "colors": [],
        "warranty": "No Warranty",
        "delivery_charge": 100,
        "delivery_time": "2-4 Days",
        "stock": "In Stock",
        "status": "Active",
        "image_url": "",
    },
]


# =========================================================
# HARD-CODED FAQ DATABASE
# =========================================================

FAQS: List[Dict[str, Any]] = [
    {
        "keywords": ["delivery time", "কত দিনে", "জেলা", "থানা", "ডেলিভারি সময়"],
        "answer": (
            "📍 আপনার জেলা ও থানার নামটি জানালে আমরা আপনার এলাকাভিত্তিক "
            "সঠিক ডেলিভারি সময় জানিয়ে দিতে পারব। সাধারণত ২–৪ দিনের মধ্যে "
            "ডেলিভারি সম্পন্ন হয়।"
        ),
    },
    {
        "keywords": ["parcel update", "পার্সেল", "tracking", "ট্র্যাকিং"],
        "answer": (
            "📦 আপনার পার্সেলের সর্বশেষ আপডেট জানতে মোবাইল নম্বরটি পাঠান। "
            f"আমি তথ্য Admin {ADMIN_NAME}-এর কাছে পৌঁছে দেব। "
            f"Call/WhatsApp: {ADMIN_PHONE}"
        ),
    },
    {
        "keywords": ["courier", "steadfast", "home delivery", "কুরিয়ার"],
        "answer": (
            "🚚 আমরা Steadfast Courier-এর মাধ্যমে সারা বাংলাদেশে হোম ডেলিভারি করি। "
            "আপনার অর্ডার নিরাপদভাবে ঠিকানায় পৌঁছে দেওয়া হবে।"
        ),
    },
    {
        "keywords": ["china", "চীন", "import", "ইমপোর্ট", "quality", "কোয়ালিটি"],
        "answer": (
            "🇨🇳 আমরা সরাসরি চীন থেকে প্রোডাক্ট ইমপোর্ট করি। "
            "ভালো মানের প্রোডাক্ট সাশ্রয়ী দামে পৌঁছে দেওয়াই আমাদের অঙ্গীকার।"
        ),
    },
    {
        "keywords": ["wholesale", "হোলসেল", "MOQ", "bulk", "reselling", "ব্যবসা"],
        "answer": (
            "📦 Wholesale, Reselling বা Bulk Order-এর জন্য সরাসরি অ্যাডমিনের সঙ্গে যোগাযোগ করুন।\n"
            f"👤 Admin: {ADMIN_NAME}\n📞 Call/WhatsApp: {ADMIN_PHONE}"
        ),
    },
    {
        "keywords": ["location", "লোকেশন", "ভৈরব", "কিশোরগঞ্জ", "ঠিকানা"],
        "answer": (
            "📍 আমাদের লোকেশন: ভৈরব, কিশোরগঞ্জ। "
            "সরাসরি প্রোডাক্ট সংগ্রহ করতে চাইলে আগে সময় নিশ্চিত করুন।\n"
            f"👤 Admin: {ADMIN_NAME}\n📞 Call/WhatsApp: {ADMIN_PHONE}"
        ),
    },
    {
        "keywords": ["payment", "cod", "cash on delivery", "বিকাশ", "নগদ", "পেমেন্ট"],
        "answer": (
            "💳 Cash on Delivery সুবিধা রয়েছে। অগ্রিম পেমেন্ট বাধ্যতামূলক নয়।\n"
            f"📱 বিকাশ (Personal): {ADMIN_PHONE}\n"
            f"📱 নগদ (Personal): {ADMIN_PHONE}\n"
            "🏦 ব্যাংক ট্রান্সফার এবং ডেবিট/ক্রেডিট কার্ডেও পেমেন্ট করা যায়।"
        ),
    },
    {
        "keywords": ["cancel", "order cancel", "বাতিল", "পরিবর্তন"],
        "answer": (
            "🛍️ অর্ডার বাতিল বা পরিবর্তন করতে চাইলে যত দ্রুত সম্ভব "
            f"Admin {ADMIN_NAME}-এর সঙ্গে যোগাযোগ করুন: {ADMIN_PHONE}"
        ),
    },
    {
        "keywords": ["stock", "available", "স্টক", "আছে কি"],
        "answer": "📦 স্টক জানতে প্রোডাক্টের নাম বা ছবি পাঠান।",
    },
    {
        "keywords": ["review", "reviews", "feedback", "রিভিউ"],
        "answer": "⭐ কাস্টমারদের রিভিউ ও ফিডব্যাক দেখতে লিখুন “Review”।",
    },
    {
        "keywords": ["international shipping", "দেশের বাইরে", "বিদেশে"],
        "answer": (
            "🌍 দেশের বাইরেও প্রোডাক্ট পাঠানো হয়। দেশ, ঠিকানা, কুরিয়ার খরচ "
            "ও কাস্টমস নিয়ম অনুযায়ী চার্জ ও ডেলিভারি সময় ভিন্ন হতে পারে।"
        ),
    },
    {
        "keywords": ["return", "রিটার্ন", "return policy"],
        "answer": (
            "🔄 ডেলিভারির ২৪ ঘণ্টার মধ্যে যোগাযোগ করলে রিটার্ন করা যাবে। "
            "৳১২০ রিটার্ন ডেলিভারি চার্জ প্রযোজ্য এবং প্রোডাক্ট অব্যবহৃত, "
            "অরিজিনাল অবস্থায় ও সম্পূর্ণ প্যাকেজিংসহ থাকতে হবে।"
        ),
    },
    {
        "keywords": ["phone call", "microphone", "ফোনে কথা", "হেডফোন দিয়ে কল"],
        "answer": (
            "📞 হ্যাঁ, হেডফোন দিয়ে ফোনে কথা বলা যায়। পরিষ্কার ভয়েস, "
            "বিল্ট-ইন মাইক্রোফোন এবং কল রিসিভ/রিজেক্ট সুবিধা রয়েছে।"
        ),
    },
    {
        "keywords": ["moderator", "মডারেটর", "job", "চাকরি"],
        "answer": (
            "😊 বর্তমানে আমাদের পেজে মডারেটর প্রয়োজন নেই। "
            "ভবিষ্যতে প্রয়োজন হলে পেজে জানিয়ে দেওয়া হবে।"
        ),
    },
    {
        "keywords": ["scam", "প্রতারণা", "বিশ্বাস", "ভরসা"],
        "answer": (
            "😊 আপনার সতর্কতা স্বাভাবিক। আমরা ভালো মানের প্রোডাক্ট ও বিশ্বস্ত সেবা "
            "দেওয়ার চেষ্টা করি। Cash on Delivery থাকায় প্রোডাক্ট হাতে পাওয়ার পর "
            "মূল্য পরিশোধ করতে পারবেন।"
        ),
    },
    {
        "keywords": ["discount", "কম হবে", "দাম কম", "দরদাম"],
        "answer": (
            "😊 সর্বোচ্চ ৳২০ পর্যন্ত কমানোর অনুরোধ অ্যাডমিনের কাছে পাঠানো যেতে পারে। "
            "চূড়ান্ত অনুমোদন অ্যাডমিন দেবেন।"
        ),
    },
    {
        "keywords": ["delivery charge", "ডেলিভারি চার্জ", "free delivery"],
        "answer": (
            "🚚 সাধারণ ডেলিভারি চার্জ সারা বাংলাদেশে ৳১০০। "
            "Mini Juicer-এর ক্ষেত্রে Free Delivery প্রযোজ্য।"
        ),
    },
]



# =========================================================
# ORDER COMMAND WORDS
# =========================================================

CONFIRM_WORDS = {
    "confirm",
    "confirmed",
    "কনফার্ম",
    "হ্যাঁ কনফার্ম",
    "yes confirm",
}

CANCEL_WORDS = {
    "cancel",
    "বাতিল",
    "অর্ডার বাতিল",
}

ORDER_WORDS = (
    "অর্ডার",
    "order",
    "নিতে চাই",
    "কিনতে চাই",
)

# =========================================================
# TEMPORARY SESSION & ORDER STORAGE
# =========================================================

SESSIONS: Dict[str, Dict[str, Any]] = {}
ORDERS: List[Dict[str, Any]] = []

_sessions_lock = threading.Lock()
_orders_lock = threading.Lock()


# =========================================================
# DUPLICATE MESSAGE PROTECTION
# =========================================================

_processed_messages: Dict[str, float] = {}
_processed_lock = threading.Lock()

MESSAGE_CACHE_SECONDS = 60 * 60


def is_duplicate_message(message_id: str) -> bool:
    if not message_id:
        return False

    now = time.time()

    with _processed_lock:
        expired = [
            key
            for key, created_at in _processed_messages.items()
            if now - created_at > MESSAGE_CACHE_SECONDS
        ]

        for key in expired:
            _processed_messages.pop(key, None)

        if message_id in _processed_messages:
            return True

        _processed_messages[message_id] = now

    return False


# =========================================================
# BASIC HELPERS
# =========================================================

def norm(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).casefold()


def number(value: Any) -> float:
    match = re.search(r"\d+(?:\.\d+)?", str(value or "").replace(",", ""))
    return float(match.group()) if match else 0.0


def money(value: float) -> str:
    value = float(value or 0)
    return f"৳{int(value)}" if value.is_integer() else f"৳{value:.2f}"


def openai_configured() -> bool:
    return bool(OPENAI_API_KEY)


def messenger_configured() -> bool:
    return bool(PAGE_ACCESS_TOKEN)


# =========================================================
# META SIGNATURE VERIFICATION
# =========================================================

def verify_signature(raw_body: bytes, signature_header: Optional[str]) -> bool:
    if not META_APP_SECRET:
        logger.warning(
            "META_APP_SECRET is missing. Webhook signature verification is disabled."
        )
        return True

    if not signature_header or not signature_header.startswith("sha256="):
        return False

    expected_signature = hmac.new(
        META_APP_SECRET.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    received_signature = signature_header.split("=", 1)[1]

    return hmac.compare_digest(expected_signature, received_signature)


# =========================================================
# OPENAI
# =========================================================

def get_openai_client() -> OpenAI:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is missing.")
    return OpenAI(api_key=OPENAI_API_KEY)


# =========================================================
# PRODUCT & FAQ SEARCH
# =========================================================

def product_search_text(product: Dict[str, Any]) -> str:
    return norm(
        " ".join(
            [
                product.get("name", ""),
                product.get("category", ""),
                " ".join(product.get("keywords", [])),
                product.get("details", ""),
                " ".join(product.get("features", [])),
            ]
        )
    )


def find_product(query: str) -> Optional[Dict[str, Any]]:
    query_normalized = norm(query)

    if not query_normalized:
        return None

    best_product = None
    best_score = 0.0

    for product in PRODUCTS:
        searchable_text = product_search_text(product)
        product_name = norm(product.get("name"))
        keywords = [norm(item) for item in product.get("keywords", [])]

        score = 0.0

        if product_name and product_name in query_normalized:
            score = 1.0
        elif query_normalized in searchable_text:
            score = 0.94
        else:
            for keyword in keywords + ([product_name] if product_name else []):
                if keyword and (keyword in query_normalized or query_normalized in keyword):
                    score = max(score, 0.90)

                if keyword:
                    score = max(
                        score,
                        SequenceMatcher(None, query_normalized, keyword).ratio(),
                    )

            query_tokens = set(query_normalized.split())
            product_tokens = set(searchable_text.split())

            if query_tokens:
                score = max(
                    score,
                    len(query_tokens & product_tokens) / len(query_tokens),
                )

        if score > best_score:
            best_product = product
            best_score = score

    return best_product if best_score >= 0.48 else None


def find_faq(query: str) -> Optional[str]:
    query_normalized = norm(query)

    if not query_normalized:
        return None

    best_answer = None
    best_score = 0.0

    for item in FAQS:
        keywords = [norm(keyword) for keyword in item.get("keywords", [])]
        score = 0.0

        for keyword in keywords:
            if keyword in query_normalized or query_normalized in keyword:
                score = max(score, 0.95)

            score = max(
                score,
                SequenceMatcher(None, query_normalized, keyword).ratio(),
            )

        if score > best_score:
            best_answer = item.get("answer")
            best_score = score

    return best_answer if best_score >= 0.56 else None


def current_price(product: Dict[str, Any]) -> float:
    return float(product.get("offer_price") or product.get("price") or 0)


def delivery_charge(product: Dict[str, Any]) -> float:
    return float(product.get("delivery_charge") or 0)


# =========================================================
# MESSENGER SEND
# =========================================================

def send_message(user_id: str, message: Dict[str, Any]) -> None:
    if not PAGE_ACCESS_TOKEN:
        raise RuntimeError("PAGE_ACCESS_TOKEN is missing.")

    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/me/messages"

    response = HTTP.post(
        url,
        params={"access_token": PAGE_ACCESS_TOKEN},
        json={
            "recipient": {"id": user_id},
            "messaging_type": "RESPONSE",
            "message": message,
        },
        timeout=25,
    )

    if not response.ok:
        logger.error(
            "Messenger API error %s: %s",
            response.status_code,
            response.text[:1000],
        )

    response.raise_for_status()


def send_text(user_id: str, text: str) -> None:
    cleaned_text = str(text or "").strip()
    if cleaned_text:
        send_message(user_id, {"text": cleaned_text[:2000]})


def send_image(user_id: str, image_url: str) -> None:
    image_url = str(image_url or "").strip()

    if not image_url.startswith(("http://", "https://")):
        return

    send_message(
        user_id,
        {
            "attachment": {
                "type": "image",
                "payload": {
                    "url": image_url,
                    "is_reusable": True,
                },
            },
        },
    )


# =========================================================
# PRODUCT RESPONSE
# =========================================================

def product_text(product: Dict[str, Any]) -> str:
    lines = [
        f"🛍️ {product.get('name')}",
        f"💰 মূল্য: {money(current_price(product))}",
        f"📦 স্টক: {product.get('stock', 'In Stock')}",
    ]

    if product.get("details"):
        lines.append(product["details"])

    features = product.get("features", [])
    if features:
        lines.append("✨ প্রধান ফিচার:")
        lines.extend(f"• {feature}" for feature in features[:8])

    if product.get("box_items"):
        lines.append("📦 বক্সে যা পাবেন:")
        lines.extend(f"• {item}" for item in product["box_items"])

    colors = product.get("colors", [])
    if colors:
        lines.append("🎨 রঙ: " + ", ".join(colors))

    if product.get("warranty"):
        lines.append(f"🛡️ ওয়ারেন্টি: {product.get('warranty')}")

    lines.append(f"🚚 ডেলিভারি: {product.get('delivery_time', '2-4 Days')}")

    charge = delivery_charge(product)
    lines.append(
        "💳 ডেলিভারি চার্জ: "
        + ("ফ্রি" if charge == 0 else money(charge))
    )

    lines.append('\nঅর্ডার করতে “অর্ডার করতে চাই” লিখুন।')

    return "\n".join(lines)


# =========================================================
# SESSION MANAGEMENT
# =========================================================

def get_session(user_id: str) -> Dict[str, Any]:
    with _sessions_lock:
        return dict(SESSIONS.get(user_id, {"stage": "", "user_id": user_id}))


def save_session(user_id: str, updates: Dict[str, Any]) -> None:
    with _sessions_lock:
        current = SESSIONS.get(user_id, {"stage": "", "user_id": user_id})
        current.update(updates)
        current["updated_at"] = datetime.now(timezone.utc).isoformat()
        SESSIONS[user_id] = current


def clear_session(user_id: str) -> None:
    with _sessions_lock:
        SESSIONS.pop(user_id, None)


# =========================================================
# ORDER HELPERS
# =========================================================

def valid_mobile(text: str) -> bool:
    digits = re.sub(r"\D", "", text)
    return len(digits) in {10, 11, 13} and (
        digits.startswith("01") or digits.startswith("8801")
    )


def order_summary(session: Dict[str, Any], product: Dict[str, Any]) -> str:
    quantity = max(int(number(session.get("quantity")) or 1), 1)
    unit_price = current_price(product)
    charge = delivery_charge(product)
    total = unit_price * quantity + charge

    lines = [
        "📦 অর্ডার সারাংশ",
        f"প্রোডাক্ট: {product.get('name')}",
    ]

    if session.get("color"):
        lines.append(f"রঙ: {session.get('color')}")

    lines.extend(
        [
            f"পরিমাণ: {quantity}",
            f"প্রতি পিস: {money(unit_price)}",
            f"ডেলিভারি চার্জ: {'ফ্রি' if charge == 0 else money(charge)}",
            f"মোট: {money(total)}",
            "",
            f"নাম: {session.get('customer_name', '')}",
            f"মোবাইল: {session.get('mobile', '')}",
            f"এলাকা/গ্রাম: {session.get('area', '')}",
            f"থানা: {session.get('thana', '')}",
            f"জেলা: {session.get('district', '')}",
            f"রিসিভ করবেন: {session.get('receive_from', '')}",
            f"সম্পূর্ণ ঠিকানা: {session.get('full_address', '')}",
            "",
            'সব ঠিক থাকলে “Confirm” বা “কনফার্ম” লিখুন।',
        ]
    )

    return "\n".join(lines)


def save_order(user_id: str, session: Dict[str, Any], product: Dict[str, Any]) -> str:
    quantity = max(int(number(session.get("quantity")) or 1), 1)
    unit_price = current_price(product)
    charge = delivery_charge(product)

    order_id = (
        f"SB-{datetime.now().strftime('%y%m%d')}-"
        f"{uuid.uuid4().hex[:6].upper()}"
    )

    order = {
        "order_id": order_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "facebook_user_id": user_id,
        "customer_name": session.get("customer_name", ""),
        "mobile": session.get("mobile", ""),
        "area": session.get("area", ""),
        "thana": session.get("thana", ""),
        "district": session.get("district", ""),
        "receive_from": session.get("receive_from", ""),
        "full_address": session.get("full_address", ""),
        "product_name": product.get("name", ""),
        "color": session.get("color", ""),
        "quantity": quantity,
        "unit_price": unit_price,
        "delivery_charge": charge,
        "total": unit_price * quantity + charge,
        "status": "New - Admin Review",
    }

    with _orders_lock:
        ORDERS.append(order)

    logger.info("NEW ORDER: %s", json.dumps(order, ensure_ascii=False))

    return order_id


# =========================================================
# IMAGE + AI
# =========================================================

def image_from_event(event: Dict[str, Any]) -> Optional[str]:
    message = event.get("message") or {}

    for attachment in message.get("attachments", []) or []:
        if attachment.get("type") == "image":
            payload = attachment.get("payload") or {}
            image_url = payload.get("url")
            if image_url:
                return str(image_url)

    return None


def describe_image(image_url: str) -> str:
    client = get_openai_client()

    response = client.responses.create(
        model=OPENAI_MODEL,
        instructions=(
            "ছবির বিক্রয়যোগ্য প্রোডাক্টটি শনাক্ত করে সংক্ষিপ্ত বাংলা/ইংরেজি "
            "কীওয়ার্ড লিখুন। নিশ্চিত না হলে অনুমান করবেন না।"
        ),
        input=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": "এই ছবির প্রোডাক্টটি শনাক্ত করুন।",
                    },
                    {
                        "type": "input_image",
                        "image_url": image_url,
                    },
                ],
            }
        ],
        max_output_tokens=160,
    )

    return (response.output_text or "").strip()


def ai_reply(text: str) -> str:
    if not OPENAI_API_KEY:
        faq_answer = find_faq(text)
        if faq_answer:
            return faq_answer

        return (
            "আপনি কোন প্রোডাক্ট সম্পর্কে জানতে চান? "
            "প্রোডাক্টের নাম বা ছবি পাঠান।"
        )

    compact_catalog = [
        {
            "name": product.get("name"),
            "keywords": product.get("keywords"),
            "price": current_price(product),
            "details": product.get("details"),
            "features": product.get("features"),
            "colors": product.get("colors"),
            "warranty": product.get("warranty"),
            "delivery_charge": delivery_charge(product),
            "delivery_time": product.get("delivery_time"),
            "stock": product.get("stock"),
        }
        for product in PRODUCTS
    ]

    client = get_openai_client()

    response = client.responses.create(
        model=OPENAI_MODEL,
        instructions=(
            f"""
আপনি “{BOT_NAME}”, একটি Facebook Page-এর বাংলা বিক্রয় সহকারী।

Admin: {ADMIN_NAME}
Call/WhatsApp: {ADMIN_PHONE}
লোকেশন: ভৈরব, কিশোরগঞ্জ।
Steadfast Courier-এর মাধ্যমে সারা বাংলাদেশে সাধারণত ২–৪ দিনে ডেলিভারি।
সাধারণ ডেলিভারি চার্জ ৳১০০।
Cash on Delivery আছে।
কোনো পণ্যকে Pre-order বলবেন না।
দাম, স্টক, রঙ, ফিচার বা ওয়ারেন্টি বানাবেন না।
উত্তর সংক্ষিপ্ত, স্বাভাবিক এবং ভদ্র বাংলায় দেবেন।
"""
            + "\nProduct Catalog:\n"
            + json.dumps(compact_catalog, ensure_ascii=False)
            + "\nFAQ:\n"
            + json.dumps(FAQS, ensure_ascii=False)
        ),
        input=text,
        max_output_tokens=320,
    )

    return (response.output_text or "").strip() or (
        "প্রোডাক্টের নাম বা ছবি পাঠান।"
    )


# =========================================================
# ORDER FLOW
# =========================================================

def order_flow(
    user_id: str,
    text: str,
    selected_product: Optional[Dict[str, Any]],
) -> bool:
    session = get_session(user_id)
    stage = norm(session.get("stage"))
    normalized_text = norm(text)

    if normalized_text in CANCEL_WORDS:
        clear_session(user_id)
        send_text(user_id, "অর্ডার প্রক্রিয়া বাতিল করা হয়েছে।")
        return True

    if not stage and any(word in normalized_text for word in ORDER_WORDS):
        product = selected_product

        if not product and session.get("product_name"):
            product = find_product(session.get("product_name", ""))

        if not product:
            save_session(user_id, {"stage": "waiting_product"})
            send_text(user_id, "কোন প্রোডাক্টটি অর্ডার করতে চান? নাম লিখুন।")
            return True

        save_session(
            user_id,
            {
                "stage": "waiting_color_or_quantity",
                "product_name": product.get("name", ""),
            },
        )

        if product.get("colors"):
            send_text(
                user_id,
                "পছন্দের রঙ লিখুন: " + ", ".join(product.get("colors", [])),
            )
        else:
            send_text(user_id, "কয়টি নিতে চান? সংখ্যা লিখুন।")

        return True

    if stage == "waiting_product":
        if not selected_product:
            send_text(user_id, "প্রোডাক্টটি পাইনি। সঠিক নাম লিখুন।")
            return True

        save_session(
            user_id,
            {
                "stage": "waiting_color_or_quantity",
                "product_name": selected_product.get("name", ""),
            },
        )

        if selected_product.get("colors"):
            send_text(
                user_id,
                "পছন্দের রঙ লিখুন: "
                + ", ".join(selected_product.get("colors", [])),
            )
        else:
            send_text(user_id, "কয়টি নিতে চান?")

        return True

    if stage == "waiting_color_or_quantity":
        product = find_product(session.get("product_name", ""))

        if product and product.get("colors") and not session.get("color"):
            save_session(
                user_id,
                {
                    "color": text,
                    "stage": "waiting_quantity",
                },
            )
            send_text(user_id, "কয়টি নিতে চান? সংখ্যা লিখুন।")
        else:
            save_session(
                user_id,
                {
                    "quantity": max(int(number(text) or 1), 1),
                    "stage": "waiting_name",
                },
            )
            send_text(user_id, "আপনার নাম লিখুন।")

        return True

    if stage == "waiting_quantity":
        save_session(
            user_id,
            {
                "quantity": max(int(number(text) or 1), 1),
                "stage": "waiting_name",
            },
        )
        send_text(user_id, "আপনার নাম লিখুন।")
        return True

    if stage == "waiting_name":
        save_session(
            user_id,
            {
                "customer_name": text,
                "stage": "waiting_mobile",
            },
        )
        send_text(user_id, "আপনার মোবাইল নম্বর লিখুন।")
        return True

    if stage == "waiting_mobile":
        if not valid_mobile(text):
            send_text(user_id, "সঠিক মোবাইল নম্বর লিখুন—যেমন: 01XXXXXXXXX")
            return True

        save_session(
            user_id,
            {
                "mobile": text,
                "stage": "waiting_area",
            },
        )
        send_text(user_id, "এলাকা বা গ্রামের নাম লিখুন।")
        return True

    if stage == "waiting_area":
        save_session(
            user_id,
            {
                "area": text,
                "stage": "waiting_thana",
            },
        )
        send_text(user_id, "আপনার থানার নাম লিখুন।")
        return True

    if stage == "waiting_thana":
        save_session(
            user_id,
            {
                "thana": text,
                "stage": "waiting_district",
            },
        )
        send_text(user_id, "আপনার জেলার নাম লিখুন।")
        return True

    if stage == "waiting_district":
        save_session(
            user_id,
            {
                "district": text,
                "stage": "waiting_receive",
            },
        )
        send_text(user_id, "কোথা থেকে রিসিভ করবেন? যেমন: বাসা/অফিস")
        return True

    if stage == "waiting_receive":
        save_session(
            user_id,
            {
                "receive_from": text,
                "stage": "waiting_address",
            },
        )
        send_text(user_id, "সম্পূর্ণ ঠিকানা লিখুন।")
        return True

    if stage == "waiting_address":
        save_session(
            user_id,
            {
                "full_address": text,
                "stage": "waiting_confirm",
            },
        )

        fresh_session = get_session(user_id)
        product = find_product(fresh_session.get("product_name", ""))

        if not product:
            send_text(
                user_id,
                f"প্রোডাক্টের তথ্য পাওয়া যায়নি। Admin {ADMIN_NAME}: {ADMIN_PHONE}",
            )
            return True

        send_text(user_id, order_summary(fresh_session, product))
        return True

    if stage == "waiting_confirm":
        if normalized_text not in CONFIRM_WORDS:
            send_text(
                user_id,
                'Confirm করতে “Confirm” বা “কনফার্ম” লিখুন।',
            )
            return True

        fresh_session = get_session(user_id)
        product = find_product(fresh_session.get("product_name", ""))

        if not product:
            send_text(
                user_id,
                f"প্রোডাক্টের তথ্য পাওয়া যায়নি। Admin {ADMIN_NAME}: {ADMIN_PHONE}",
            )
            return True

        order_id = save_order(user_id, fresh_session, product)
        clear_session(user_id)

        send_text(
            user_id,
            (
                "✅ আপনার অর্ডারটি গ্রহণ করা হয়েছে।\n"
                f"Order ID: {order_id}\n"
                "অ্যাডমিন যাচাই করে চূড়ান্ত কনফার্ম করবেন। "
                "সাধারণত ২–৪ দিনের মধ্যে ডেলিভারি হয়।"
            ),
        )

        return True

    return False


# =========================================================
# MESSAGE HANDLER
# =========================================================

def handle(
    user_id: str,
    text: str = "",
    image_url: Optional[str] = None,
) -> None:
    search_text = str(text or "").strip()

    if image_url:
        if openai_configured():
            try:
                description = describe_image(image_url)
                search_text = f"{search_text}\nছবির বর্ণনা: {description}".strip()
            except Exception:
                logger.exception("Vision processing failed.")
        elif not search_text:
            send_text(
                user_id,
                "ছবিটি পেয়েছি। প্রোডাক্টের নামও লিখে পাঠান।",
            )
            return

    selected_product = find_product(search_text)

    if order_flow(user_id, text or search_text, selected_product):
        return

    if selected_product:
        image_url_value = selected_product.get("image_url", "")

        if image_url_value:
            try:
                send_image(user_id, image_url_value)
            except Exception:
                logger.exception("Product image send failed.")

        send_text(user_id, product_text(selected_product))
        save_session(
            user_id,
            {"product_name": selected_product.get("name", "")},
        )
        return

    faq_answer = find_faq(search_text)
    if faq_answer:
        send_text(user_id, faq_answer)
        return

    if not search_text:
        send_text(
            user_id,
            "আপনার মেসেজটি বুঝতে পারিনি। প্রোডাক্টের নাম বা ছবি পাঠান।",
        )
        return

    send_text(user_id, ai_reply(search_text))


# =========================================================
# BACKGROUND EVENT PROCESSOR
# =========================================================

def process_messaging_event(event: Dict[str, Any]) -> None:
    sender = (event.get("sender") or {}).get("id")
    message = event.get("message")

    if not sender or not isinstance(message, dict):
        return

    if message.get("is_echo"):
        return

    message_id = str(message.get("mid") or "").strip()

    if message_id and is_duplicate_message(message_id):
        logger.info("Duplicate message ignored: %s", message_id)
        return

    text = str(message.get("text") or "").strip()
    image_url = image_from_event(event)

    if not text and not image_url:
        return

    try:
        handle(str(sender), text, image_url)

    except Exception:
        logger.exception("Message handler failed.")

        try:
            send_text(
                str(sender),
                (
                    "দুঃখিত, এই মুহূর্তে তথ্য প্রসেস করা যাচ্ছে না। "
                    f"Admin {ADMIN_NAME}: {ADMIN_PHONE}"
                ),
            )
        except Exception:
            logger.exception("Fallback message also failed.")


# =========================================================
# ROUTES
# =========================================================

@app.get("/")
def home():
    return {
        "status": "ok",
        "bot": BOT_NAME,
        "messenger_configured": messenger_configured(),
        "openai_configured": openai_configured(),
        "google_sheets_required": False,
        "products_count": len(PRODUCTS),
        "faq_count": len(FAQS),
        "temporary_orders_count": len(ORDERS),
    }, 200


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": BOT_NAME,
    }, 200


@app.get("/webhook")
def webhook_verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge", "")

    if mode == "subscribe" and token == VERIFY_TOKEN and VERIFY_TOKEN:
        logger.info("Webhook verification successful.")
        return challenge, 200

    logger.warning("Webhook verification failed.")
    return "Verification failed", 403


@app.post("/webhook")
def webhook_receive():
    raw_body = request.get_data()
    signature = request.headers.get("X-Hub-Signature-256")

    if not verify_signature(raw_body, signature):
        logger.warning("Invalid webhook signature.")
        return "Invalid signature", 403

    payload = request.get_json(silent=True) or {}

    if payload.get("object") != "page":
        return "Ignored", 200

    for entry in payload.get("entry", []):
        for event in entry.get("messaging", []) or []:
            if isinstance(event, dict):
                EXECUTOR.submit(process_messaging_event, event)

    return "EVENT_RECEIVED", 200


@app.get("/orders")
def view_orders():
    """
    Temporary admin/debug endpoint.
    Orders are stored only in memory and disappear after Render restart.
    """
    return {
        "count": len(ORDERS),
        "orders": ORDERS[-100:],
    }, 200


# =========================================================
# START APPLICATION
# =========================================================

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
