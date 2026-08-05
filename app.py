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
from typing import Any, Dict, List, Optional, Tuple

import requests
from dotenv import load_dotenv
from flask import Flask, request
from google import genai
from google.genai import types


load_dotenv()
app = Flask(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

HTTP = requests.Session()
EXECUTOR = ThreadPoolExecutor(max_workers=4)

BOT_NAME = os.getenv("BOT_NAME", "সবুজ বাড়ি AI").strip()
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "").strip()
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN", "").strip()
META_APP_SECRET = os.getenv("META_APP_SECRET", "").strip()
GRAPH_API_VERSION = os.getenv("GRAPH_API_VERSION", "v26.0").strip()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite").strip()

ADMIN_NAME = os.getenv("ADMIN_NAME", "Arafat Rahman").strip()
ADMIN_PHONE = os.getenv("ADMIN_PHONE", "01780618736").strip()


# =========================================================
# PRODUCTS
# =========================================================

PRODUCTS: List[Dict[str, Any]] = [
    {
        "keywords": ["ক্যামেরা", "camera", "digital camera", "print camera", "প্রিন্ট ক্যামেরা"],
        "name": "Premium Digital Camera",
        "category": "Camera",
        "price": 2150,
        "details": (
            "চীন থেকে সরাসরি ইমপোর্ট করা ভালো মানের প্রোডাক্ট। "
            "পরিষ্কার ছবি তোলে, সঙ্গে সঙ্গে ছবি প্রিন্ট করা যায় এবং "
            "বাচ্চা ও বড়দের জন্য সুন্দর একটি গিফট।"
        ),
        "features": [
            "Includes 32GB Memory Card",
            "পরিষ্কার ছবি তোলে",
            "সঙ্গে সঙ্গে ছবি প্রিন্ট করা যায়",
            "Gift হিসেবে উপযোগী",
        ],
        "colors": [],
        "warranty": "No Warranty",
        "delivery_charge": 100,
        "delivery_time": "২–৪ দিন",
        "stock": "In Stock",
        "image_url": "",
    },
    {
        "keywords": ["4k", "flip camera", "camera", "4k camera", "ফ্লিপ ক্যামেরা"],
        "name": "4K Flip Digital Camera",
        "category": "Camera",
        "price": 2690,
        "details": "4K Recording, Flip Screen ও Premium Design।",
        "features": ["4K Recording", "Flip Screen", "Premium Design"],
        "colors": ["Pink", "Black", "White", "Purple", "Brown"],
        "warranty": "No Warranty",
        "delivery_charge": 100,
        "delivery_time": "২–৪ দিন",
        "stock": "In Stock",
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
        "details": "রুমকে তারাভরা আকাশের মতো সুন্দর করে তোলে।",
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
        "colors": [],
        "warranty": "No Warranty",
        "delivery_charge": 100,
        "delivery_time": "২–৪ দিন",
        "stock": "In Stock",
        "image_url": "",
    },
    {
        "keywords": ["জুসার", "juicer", "blender", "mini juicer"],
        "name": "High Quality Brushless Motor Mini Juicer",
        "category": "Kitchen",
        "price": 890,
        "details": "ফল ও সবজি ব্লেন্ড করার জন্য Portable Mini Juicer।",
        "features": ["Brushless Motor", "Portable", "Fruit & Vegetable Blender"],
        "colors": [],
        "warranty": "No Warranty",
        "delivery_charge": 0,
        "delivery_time": "২–৪ দিন",
        "stock": "In Stock",
        "image_url": "",
    },
    {
        "keywords": ["ইয়ারবাড", "earbuds", "clip on", "open ear", "হেডফোন"],
        "name": "Clip-On Open Ear Wireless Earbuds",
        "category": "Audio",
        "price": 1600,
        "details": (
            "পরিষ্কার ভয়েস কোয়ালিটি, বিল্ট-ইন মাইক্রোফোন এবং "
            "কল রিসিভ/রিজেক্ট সুবিধা রয়েছে।"
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
        "delivery_time": "২–৪ দিন",
        "stock": "In Stock",
        "image_url": "",
    },
    {
        "keywords": ["butterfly", "headset", "butterfly headset", "bluetooth headset"],
        "name": "Butterfly Earrings Bluetooth Headset (2025 New Model)",
        "category": "Audio",
        "price": 1250,
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
        "delivery_time": "২–৪ দিন",
        "stock": "In Stock",
        "image_url": "",
    },
]


FAQS: List[Dict[str, Any]] = [
    {
        "keywords": ["delivery time", "কত দিনে", "ডেলিভারি সময়", "জেলা", "থানা"],
        "answer": (
            "📍 আপনার জেলা ও থানার নাম জানালে এলাকাভিত্তিক সঠিক সময় বলা যাবে। "
            "সাধারণত ২–৪ দিনের মধ্যে ডেলিভারি সম্পন্ন হয়।"
        ),
    },
    {
        "keywords": ["delivery charge", "ডেলিভারি চার্জ", "free delivery"],
        "answer": (
            "🚚 সাধারণ ডেলিভারি চার্জ সারা বাংলাদেশে ৳১০০। "
            "Mini Juicer-এর ক্ষেত্রে Free Delivery।"
        ),
    },
    {
        "keywords": ["cod", "cash on delivery", "payment", "পেমেন্ট", "বিকাশ", "নগদ"],
        "answer": (
            "💳 Cash on Delivery আছে। অগ্রিম পেমেন্ট বাধ্যতামূলক নয়।\n"
            f"📱 বিকাশ/নগদ (Personal): {ADMIN_PHONE}"
        ),
    },
    {
        "keywords": ["location", "লোকেশন", "ভৈরব", "কিশোরগঞ্জ"],
        "answer": (
            "📍 আমাদের লোকেশন: ভৈরব, কিশোরগঞ্জ। আসার আগে যোগাযোগ করুন।\n"
            f"📞 Call/WhatsApp: {ADMIN_PHONE}"
        ),
    },
    {
        "keywords": ["wholesale", "হোলসেল", "bulk", "reselling", "ব্যবসা"],
        "answer": (
            "📦 Wholesale, Reselling বা Bulk Order-এর জন্য অ্যাডমিনের সঙ্গে যোগাযোগ করুন।\n"
            f"👤 {ADMIN_NAME}\n📞 {ADMIN_PHONE}"
        ),
    },
    {
        "keywords": ["return", "রিটার্ন", "return policy"],
        "answer": (
            "🔄 ডেলিভারির ২৪ ঘণ্টার মধ্যে যোগাযোগ করলে রিটার্ন করা যাবে। "
            "৳১২০ রিটার্ন ডেলিভারি চার্জ প্রযোজ্য এবং পণ্য অব্যবহৃত ও "
            "সম্পূর্ণ প্যাকেজিংসহ থাকতে হবে।"
        ),
    },
    {
        "keywords": ["cancel", "বাতিল", "order cancel"],
        "answer": (
            "🛍️ অর্ডার বাতিল বা পরিবর্তন করতে দ্রুত অ্যাডমিনের সঙ্গে যোগাযোগ করুন।\n"
            f"📞 {ADMIN_PHONE}"
        ),
    },
    {
        "keywords": ["scam", "প্রতারণা", "বিশ্বাস", "ভরসা"],
        "answer": (
            "😊 আমরা ভালো মানের পণ্য ও বিশ্বস্ত সেবা দেওয়ার চেষ্টা করি। "
            "Cash on Delivery থাকায় পণ্য হাতে পাওয়ার পর মূল্য পরিশোধ করতে পারবেন।"
        ),
    },
    {
        "keywords": ["parcel", "tracking", "পার্সেল", "ট্র্যাকিং"],
        "answer": (
            "📦 পার্সেলের আপডেট জানতে মোবাইল নম্বরটি পাঠান। "
            f"Admin {ADMIN_NAME} আপডেট জানাবেন।"
        ),
    },
]


CONFIRM_WORDS = {"confirm", "confirmed", "কনফার্ম", "হ্যাঁ কনফার্ম", "yes confirm"}
CANCEL_PHRASES = {
    "cancel", "বাতিল", "অর্ডার বাতিল", "নিবো না", "নেব না",
    "নিতে চাই না", "cancel order", "order cancel"
}
ORDER_PHRASES = {"অর্ডার", "order", "নিতে চাই", "কিনতে চাই", "অর্ডার করতে চাই"}


SESSIONS: Dict[str, Dict[str, Any]] = {}
ORDERS: List[Dict[str, Any]] = []
_processed_messages: Dict[str, float] = {}

_sessions_lock = threading.Lock()
_orders_lock = threading.Lock()
_processed_lock = threading.Lock()


# =========================================================
# HELPERS
# =========================================================

def norm(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).casefold()


def number(value: Any) -> float:
    match = re.search(r"\d+(?:\.\d+)?", str(value or "").replace(",", ""))
    return float(match.group()) if match else 0.0


def money(value: float) -> str:
    value = float(value or 0)
    return f"৳{int(value)}" if value.is_integer() else f"৳{value:.2f}"


def contains_any(text: str, phrases: set) -> bool:
    normalized = norm(text)
    return any(norm(phrase) in normalized for phrase in phrases)


def is_question_like(text: str) -> bool:
    t = norm(text)
    question_words = [
        "কি", "কী", "কত", "কোন", "কেমন", "কেন", "আছে", "হবে",
        "can", "what", "which", "how", "price", "দাম", "চার্জ", "কালার", "রঙ"
    ]
    return "?" in text or any(word in t for word in question_words)


def is_duplicate_message(message_id: str) -> bool:
    if not message_id:
        return False

    now = time.time()

    with _processed_lock:
        expired = [
            key for key, created in _processed_messages.items()
            if now - created > 3600
        ]
        for key in expired:
            _processed_messages.pop(key, None)

        if message_id in _processed_messages:
            return True

        _processed_messages[message_id] = now

    return False


def gemini_configured() -> bool:
    return bool(GEMINI_API_KEY)


def messenger_configured() -> bool:
    return bool(PAGE_ACCESS_TOKEN)


# =========================================================
# PRODUCT / FAQ SEARCH
# =========================================================

def find_product(query: str) -> Optional[Dict[str, Any]]:
    q = norm(query)
    if not q:
        return None

    best_product = None
    best_score = 0.0

    for product in PRODUCTS:
        name = norm(product["name"])
        keywords = [norm(item) for item in product["keywords"]]
        searchable = norm(
            " ".join(
                [
                    product["name"],
                    product["category"],
                    " ".join(product["keywords"]),
                    product["details"],
                    " ".join(product["features"]),
                ]
            )
        )

        score = 0.0

        if name in q:
            score = 1.0
        elif q in searchable:
            score = 0.94
        else:
            for keyword in keywords + [name]:
                if keyword in q or q in keyword:
                    score = max(score, 0.90)
                score = max(score, SequenceMatcher(None, q, keyword).ratio())

            q_tokens = set(q.split())
            p_tokens = set(searchable.split())
            if q_tokens:
                score = max(score, len(q_tokens & p_tokens) / len(q_tokens))

        if score > best_score:
            best_product = product
            best_score = score

    return best_product if best_score >= 0.48 else None


def find_faq(query: str) -> Optional[str]:
    q = norm(query)
    if not q:
        return None

    best_answer = None
    best_score = 0.0

    for item in FAQS:
        for keyword in item["keywords"]:
            k = norm(keyword)
            score = 0.95 if (k in q or q in k) else SequenceMatcher(None, q, k).ratio()

            if score > best_score:
                best_score = score
                best_answer = item["answer"]

    return best_answer if best_score >= 0.58 else None


def product_text(product: Dict[str, Any]) -> str:
    lines = [
        f"🛍️ {product['name']}",
        f"💰 মূল্য: {money(product['price'])}",
        f"📦 স্টক: {product['stock']}",
        product["details"],
        "✨ প্রধান ফিচার:",
    ]

    lines.extend(f"• {feature}" for feature in product["features"][:8])

    if product["colors"]:
        lines.append("🎨 রঙ: " + ", ".join(product["colors"]))

    lines.append(f"🛡️ ওয়ারেন্টি: {product['warranty']}")
    lines.append(f"🚚 ডেলিভারি: {product['delivery_time']}")
    lines.append(
        "💳 ডেলিভারি চার্জ: "
        + ("ফ্রি" if product["delivery_charge"] == 0 else money(product["delivery_charge"]))
    )
    lines.append('\nঅর্ডার করতে “অর্ডার করতে চাই” লিখুন।')

    return "\n".join(lines)


def camera_list_text() -> str:
    cameras = [p for p in PRODUCTS if p["category"] == "Camera"]
    lines = ["📷 আমাদের ক্যামেরাগুলো:"]
    for product in cameras:
        lines.append(f"• {product['name']} — {money(product['price'])}")
    lines.append("\nযেটির বিস্তারিত চান, নামটি লিখুন।")
    return "\n".join(lines)


# =========================================================
# GEMINI
# =========================================================

def get_gemini_client() -> genai.Client:
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is missing.")
    return genai.Client(api_key=GEMINI_API_KEY)


def business_context() -> str:
    catalog = [
        {
            "name": p["name"],
            "keywords": p["keywords"],
            "price": p["price"],
            "details": p["details"],
            "features": p["features"],
            "colors": p["colors"],
            "warranty": p["warranty"],
            "delivery_charge": p["delivery_charge"],
            "delivery_time": p["delivery_time"],
            "stock": p["stock"],
        }
        for p in PRODUCTS
    ]

    return f"""
আপনি “{BOT_NAME}”, Facebook Page-এর বাংলা বিক্রয় সহকারী।

ব্যবসার তথ্য:
- Admin: {ADMIN_NAME}
- Call/WhatsApp: {ADMIN_PHONE}
- Location: ভৈরব, কিশোরগঞ্জ
- Steadfast Courier
- সাধারণ ডেলিভারি ২–৪ দিন
- সাধারণ ডেলিভারি চার্জ ৳১০০
- Cash on Delivery আছে
- কোনো পণ্যকে Pre-order বলবেন না

নিয়ম:
- নিচের catalog ছাড়া দাম, স্টক, রঙ, ফিচার বা warranty বানাবেন না।
- প্রশ্নের সরাসরি, সংক্ষিপ্ত, ভদ্র বাংলা উত্তর দিন।
- গ্রাহক Roman Bangla লিখলেও বুঝে বাংলা উত্তর দিন।
- অর্ডারের তথ্য চাইলে নাম, মোবাইল, এলাকা/গ্রাম, থানা, জেলা, receive location ও পূর্ণ ঠিকানা প্রয়োজন।
- নিশ্চিত তথ্য না থাকলে Admin-এর সঙ্গে যোগাযোগ করতে বলুন।

Product Catalog:
{json.dumps(catalog, ensure_ascii=False)}

FAQ:
{json.dumps(FAQS, ensure_ascii=False)}
"""


def gemini_reply(text: str) -> str:
    if not GEMINI_API_KEY:
        return "প্রোডাক্টের নাম বা প্রশ্নটি আরেকটু পরিষ্কার করে লিখুন।"

    client = get_gemini_client()
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=text,
        config=types.GenerateContentConfig(
            system_instruction=business_context(),
            temperature=0.2,
            max_output_tokens=350,
        ),
    )

    return (response.text or "").strip() or "প্রোডাক্টের নাম বা ছবি পাঠান।"


def gemini_image_reply(image_url: str, user_text: str = "") -> str:
    if not GEMINI_API_KEY:
        return "ছবিটি পেয়েছি। প্রোডাক্টের নামও লিখে পাঠান।"

    image_response = HTTP.get(image_url, timeout=25)
    image_response.raise_for_status()

    mime_type = image_response.headers.get("Content-Type", "image/jpeg").split(";")[0]

    client = get_gemini_client()
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[
            (
                user_text
                or "ছবির পণ্যটি শনাক্ত করুন এবং আমাদের catalog-এর কোন পণ্যের সঙ্গে মিলে তা বলুন।"
            ),
            types.Part.from_bytes(
                data=image_response.content,
                mime_type=mime_type,
            ),
        ],
        config=types.GenerateContentConfig(
            system_instruction=business_context(),
            temperature=0.1,
            max_output_tokens=300,
        ),
    )

    return (response.text or "").strip() or "ছবির পণ্যটি নিশ্চিতভাবে শনাক্ত করা যায়নি।"


# =========================================================
# MESSENGER
# =========================================================

def verify_signature(raw_body: bytes, signature_header: Optional[str]) -> bool:
    if not META_APP_SECRET:
        logger.warning("META_APP_SECRET missing; signature verification disabled.")
        return True

    if not signature_header or not signature_header.startswith("sha256="):
        return False

    expected = hmac.new(
        META_APP_SECRET.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, signature_header.split("=", 1)[1])


def send_message(user_id: str, message: Dict[str, Any]) -> None:
    if not PAGE_ACCESS_TOKEN:
        raise RuntimeError("PAGE_ACCESS_TOKEN is missing.")

    response = HTTP.post(
        f"https://graph.facebook.com/{GRAPH_API_VERSION}/me/messages",
        params={"access_token": PAGE_ACCESS_TOKEN},
        json={
            "recipient": {"id": user_id},
            "messaging_type": "RESPONSE",
            "message": message,
        },
        timeout=25,
    )

    if not response.ok:
        logger.error("Messenger API error %s: %s", response.status_code, response.text[:800])

    response.raise_for_status()


def send_text(user_id: str, text: str) -> None:
    text = str(text or "").strip()
    if text:
        send_message(user_id, {"text": text[:2000]})


def image_from_event(event: Dict[str, Any]) -> Optional[str]:
    message = event.get("message") or {}
    for attachment in message.get("attachments", []) or []:
        if attachment.get("type") == "image":
            return str((attachment.get("payload") or {}).get("url") or "") or None
    return None


# =========================================================
# SESSIONS & ORDER FLOW
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


def valid_mobile(text: str) -> bool:
    digits = re.sub(r"\D", "", text)
    return len(digits) in {11, 13} and (
        digits.startswith("01") or digits.startswith("8801")
    )


def expected_prompt(stage: str) -> str:
    prompts = {
        "waiting_product": "অর্ডারের জন্য প্রোডাক্টের নাম লিখুন।",
        "waiting_color": "অর্ডারের জন্য পছন্দের রঙ লিখুন।",
        "waiting_quantity": "অর্ডারের জন্য কতটি নেবেন, সংখ্যা লিখুন।",
        "waiting_name": "অর্ডারের জন্য আপনার নাম লিখুন।",
        "waiting_mobile": "অর্ডারের জন্য ১১ সংখ্যার মোবাইল নম্বর লিখুন।",
        "waiting_area": "অর্ডারের জন্য এলাকা বা গ্রামের নাম লিখুন।",
        "waiting_thana": "অর্ডারের জন্য থানার নাম লিখুন।",
        "waiting_district": "অর্ডারের জন্য জেলার নাম লিখুন।",
        "waiting_receive": "কোথা থেকে রিসিভ করবেন লিখুন।",
        "waiting_address": "সম্পূর্ণ ঠিকানা লিখুন।",
        "waiting_confirm": 'সব ঠিক থাকলে “Confirm” বা “কনফার্ম” লিখুন।',
    }
    return prompts.get(stage, "")


def answer_interruption(text: str) -> Optional[str]:
    if "camera" in norm(text) or "ক্যামেরা" in norm(text):
        if any(word in norm(text) for word in ["কি কি", "কী কী", "which", "list"]):
            return camera_list_text()

    product = find_product(text)
    if product and is_question_like(text):
        return product_text(product)

    faq = find_faq(text)
    if faq:
        return faq

    return None


def order_summary(session: Dict[str, Any], product: Dict[str, Any]) -> str:
    quantity = max(int(number(session.get("quantity")) or 1), 1)
    charge = float(product["delivery_charge"])
    total = product["price"] * quantity + charge

    lines = [
        "📦 অর্ডার সারাংশ",
        f"প্রোডাক্ট: {product['name']}",
    ]

    if session.get("color"):
        lines.append(f"রঙ: {session['color']}")

    lines.extend([
        f"পরিমাণ: {quantity}",
        f"প্রতি পিস: {money(product['price'])}",
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
    ])

    return "\n".join(lines)


def save_order(user_id: str, session: Dict[str, Any], product: Dict[str, Any]) -> str:
    quantity = max(int(number(session.get("quantity")) or 1), 1)
    charge = float(product["delivery_charge"])

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
        "product_name": product["name"],
        "color": session.get("color", ""),
        "quantity": quantity,
        "unit_price": product["price"],
        "delivery_charge": charge,
        "total": product["price"] * quantity + charge,
        "status": "New - Admin Review",
    }

    with _orders_lock:
        ORDERS.append(order)

    logger.info("NEW ORDER: %s", json.dumps(order, ensure_ascii=False))
    return order_id


def order_flow(user_id: str, text: str, selected: Optional[Dict[str, Any]]) -> bool:
    session = get_session(user_id)
    stage = norm(session.get("stage"))
    t = norm(text)

    if contains_any(text, CANCEL_PHRASES):
        clear_session(user_id)
        send_text(user_id, "✅ অর্ডার প্রক্রিয়া বাতিল করা হয়েছে।")
        return True

    # During order, answer clear questions without corrupting stored fields.
    if stage and stage != "waiting_confirm":
        interruption = answer_interruption(text)
        if interruption and is_question_like(text):
            send_text(
                user_id,
                interruption + "\n\n📌 " + expected_prompt(stage),
            )
            return True

    if not stage and contains_any(text, ORDER_PHRASES):
        product = selected

        if not product and session.get("product_name"):
            product = find_product(session["product_name"])

        if not product:
            save_session(user_id, {"stage": "waiting_product"})
            send_text(user_id, expected_prompt("waiting_product"))
            return True

        save_session(user_id, {"product_name": product["name"]})

        if product["colors"]:
            save_session(user_id, {"stage": "waiting_color"})
            send_text(user_id, "পছন্দের রঙ লিখুন: " + ", ".join(product["colors"]))
        else:
            save_session(user_id, {"stage": "waiting_quantity"})
            send_text(user_id, expected_prompt("waiting_quantity"))
        return True

    if stage == "waiting_product":
        if not selected:
            send_text(user_id, "প্রোডাক্টটি খুঁজে পাইনি। সঠিক নাম লিখুন।")
            return True

        save_session(user_id, {"product_name": selected["name"]})

        if selected["colors"]:
            save_session(user_id, {"stage": "waiting_color"})
            send_text(user_id, "পছন্দের রঙ লিখুন: " + ", ".join(selected["colors"]))
        else:
            save_session(user_id, {"stage": "waiting_quantity"})
            send_text(user_id, expected_prompt("waiting_quantity"))
        return True

    if stage == "waiting_color":
        product = find_product(session.get("product_name", ""))
        valid_colors = [norm(c) for c in (product or {}).get("colors", [])]

        if valid_colors and not any(color in t for color in valid_colors):
            send_text(
                user_id,
                "সঠিক রঙ লিখুন: " + ", ".join((product or {}).get("colors", [])),
            )
            return True

        save_session(user_id, {"color": text, "stage": "waiting_quantity"})
        send_text(user_id, expected_prompt("waiting_quantity"))
        return True

    if stage == "waiting_quantity":
        qty = int(number(text) or 0)
        if qty < 1 or qty > 100:
            send_text(user_id, "সঠিক পরিমাণ লিখুন—যেমন: 1")
            return True

        save_session(user_id, {"quantity": qty, "stage": "waiting_name"})
        send_text(user_id, expected_prompt("waiting_name"))
        return True

    if stage == "waiting_name":
        if is_question_like(text) or len(text.strip()) < 2:
            send_text(user_id, expected_prompt("waiting_name"))
            return True

        save_session(user_id, {"customer_name": text, "stage": "waiting_mobile"})
        send_text(user_id, expected_prompt("waiting_mobile"))
        return True

    if stage == "waiting_mobile":
        if not valid_mobile(text):
            send_text(user_id, expected_prompt("waiting_mobile"))
            return True

        save_session(user_id, {"mobile": text, "stage": "waiting_area"})
        send_text(user_id, expected_prompt("waiting_area"))
        return True

    simple_steps = {
        "waiting_area": ("area", "waiting_thana"),
        "waiting_thana": ("thana", "waiting_district"),
        "waiting_district": ("district", "waiting_receive"),
        "waiting_receive": ("receive_from", "waiting_address"),
    }

    if stage in simple_steps:
        key, next_stage = simple_steps[stage]

        if is_question_like(text) or len(text.strip()) < 2:
            send_text(user_id, expected_prompt(stage))
            return True

        save_session(user_id, {key: text, "stage": next_stage})
        send_text(user_id, expected_prompt(next_stage))
        return True

    if stage == "waiting_address":
        if is_question_like(text) or len(text.strip()) < 5:
            send_text(user_id, expected_prompt("waiting_address"))
            return True

        save_session(user_id, {"full_address": text, "stage": "waiting_confirm"})
        fresh = get_session(user_id)
        product = find_product(fresh.get("product_name", ""))

        if not product:
            clear_session(user_id)
            send_text(user_id, f"প্রোডাক্ট পাওয়া যায়নি। Admin: {ADMIN_PHONE}")
            return True

        send_text(user_id, order_summary(fresh, product))
        return True

    if stage == "waiting_confirm":
        if t not in {norm(word) for word in CONFIRM_WORDS}:
            if contains_any(text, CANCEL_PHRASES):
                clear_session(user_id)
                send_text(user_id, "✅ অর্ডার বাতিল করা হয়েছে।")
            else:
                send_text(user_id, expected_prompt("waiting_confirm"))
            return True

        fresh = get_session(user_id)
        product = find_product(fresh.get("product_name", ""))

        if not product:
            clear_session(user_id)
            send_text(user_id, f"প্রোডাক্ট পাওয়া যায়নি। Admin: {ADMIN_PHONE}")
            return True

        order_id = save_order(user_id, fresh, product)
        clear_session(user_id)

        send_text(
            user_id,
            (
                "✅ আপনার অর্ডার গ্রহণ করা হয়েছে।\n"
                f"Order ID: {order_id}\n"
                "অ্যাডমিন যাচাই করে চূড়ান্ত কনফার্ম করবেন।"
            ),
        )
        return True

    return False


# =========================================================
# MAIN HANDLER
# =========================================================

def handle(user_id: str, text: str = "", image_url: Optional[str] = None) -> None:
    search_text = str(text or "").strip()

    if image_url:
        try:
            send_text(user_id, gemini_image_reply(image_url, search_text))
        except Exception:
            logger.exception("Gemini image processing failed.")
            send_text(user_id, "ছবিটি পেয়েছি। প্রোডাক্টের নামও লিখে পাঠান।")
        return

    selected = find_product(search_text)

    if order_flow(user_id, search_text, selected):
        return

    # Special list queries
    t = norm(search_text)
    if ("camera" in t or "ক্যামেরা" in t) and any(
        word in t for word in ["কি কি", "কী কী", "which", "list", "গুলো"]
    ):
        send_text(user_id, camera_list_text())
        return

    if selected:
        send_text(user_id, product_text(selected))
        save_session(user_id, {"product_name": selected["name"]})
        return

    faq = find_faq(search_text)
    if faq:
        send_text(user_id, faq)
        return

    # Only unknown/complex queries use Gemini.
    try:
        send_text(user_id, gemini_reply(search_text))
    except Exception:
        logger.exception("Gemini text generation failed.")
        send_text(
            user_id,
            (
                "প্রশ্নটি বুঝতে সমস্যা হচ্ছে। প্রোডাক্টের নাম লিখুন অথবা "
                f"Admin-এর সঙ্গে যোগাযোগ করুন: {ADMIN_PHONE}"
            ),
        )


def process_messaging_event(event: Dict[str, Any]) -> None:
    sender = (event.get("sender") or {}).get("id")
    message = event.get("message")

    if not sender or not isinstance(message, dict) or message.get("is_echo"):
        return

    message_id = str(message.get("mid") or "").strip()
    if message_id and is_duplicate_message(message_id):
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
                f"সাময়িক সমস্যা হয়েছে। Admin {ADMIN_NAME}: {ADMIN_PHONE}",
            )
        except Exception:
            logger.exception("Fallback send failed.")


# =========================================================
# ROUTES
# =========================================================

@app.get("/")
def home():
    return {
        "status": "ok",
        "bot": BOT_NAME,
        "messenger_configured": messenger_configured(),
        "gemini_configured": gemini_configured(),
        "gemini_model": GEMINI_MODEL,
        "products_count": len(PRODUCTS),
        "faq_count": len(FAQS),
        "orders_in_memory": len(ORDERS),
    }, 200


@app.get("/health")
def health():
    return {"status": "healthy", "service": BOT_NAME}, 200


@app.get("/webhook")
def webhook_verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge", "")

    if mode == "subscribe" and token == VERIFY_TOKEN and VERIFY_TOKEN:
        return challenge, 200

    return "Verification failed", 403


@app.post("/webhook")
def webhook_receive():
    raw_body = request.get_data()
    signature = request.headers.get("X-Hub-Signature-256")

    if not verify_signature(raw_body, signature):
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
    return {"count": len(ORDERS), "orders": ORDERS[-100:]}, 200


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "5000")),
    )
