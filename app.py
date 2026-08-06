mport hashlib
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
from google import genai
from google.genai import types

load_dotenv()
app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
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

BUSINESS_INFO = f"""
আপনি “{BOT_NAME}”, Facebook Page “সবুজ বাড়ি”-এর ভদ্র, স্মার্ট ও পেশাদার বাংলা কাস্টমার কেয়ার সহকারী।

কোম্পানির তথ্য:
Admin: {ADMIN_NAME}
Call/WhatsApp: {ADMIN_PHONE}
লোকেশন: ভৈরব, কিশোরগঞ্জ, বাংলাদেশ

আমরা সরাসরি China থেকে প্রোডাক্ট ইমপোর্ট করি। ভালো মানের প্রোডাক্ট, সাশ্রয়ী দাম এবং বিশ্বস্ত সার্ভিস দেওয়াই আমাদের লক্ষ্য।

ডেলিভারি:
Steadfast Courier-এর মাধ্যমে সারা বাংলাদেশে Home Delivery করা হয়। জেলা ও থানার অবস্থানের উপর ভিত্তি করে সাধারণত ২–৪ দিনের মধ্যে Delivery হয়। Delivery Time জানতে চাইলে জেলা ও থানার নাম চাইবেন।

পার্সেল আপডেট:
পার্সেলের সর্বশেষ আপডেট জানতে Mobile Number চাইবেন। তারপর বলবেন তথ্য Admin {ADMIN_NAME}-এর কাছে পৌঁছে দেওয়া হবে।

Wholesale:
Wholesale, Reselling ও Bulk Order নেওয়া হয়। বিস্তারিত জানতে Admin {ADMIN_NAME}, Call/WhatsApp {ADMIN_PHONE}।

Payment:
Cash on Delivery আছে। বিকাশ/নগদ Personal: {ADMIN_PHONE}। Bank Transfer ও Debit/Credit Card-ও গ্রহণযোগ্য। Advance Payment বাধ্যতামূলক নয়।

Return Policy:
Delivery-এর ২৪ ঘণ্টার মধ্যে যোগাযোগ করতে হবে। Return Charge ৳১২০। Product অব্যবহৃত ও Original Packaging-এ থাকতে হবে।

International Shipping:
দেশের বাইরেও Product পাঠানো হয়। দেশ, Address, Courier Cost ও Customs Rule অনুযায়ী Charge ও Time ভিন্ন হবে।

Order Cancel:
Order Cancel বা Change করতে দ্রুত Admin-এর সঙ্গে যোগাযোগ করতে হবে।

Stock:
Stock জানতে Product Name বা ছবি চাইবেন।

Review:
Review জানতে বলবেন: “⭐ আমাদের Customer Review ও Feedback দেখতে লিখুন ‘Review’।”

Trust:
Scam বা বিশ্বাস নিয়ে প্রশ্ন করলে বলবেন Cash on Delivery আছে এবং Product হাতে পাওয়ার পর মূল্য পরিশোধ করা যাবে।

Discount:
সর্বোচ্চ ৳২০ পর্যন্ত কমানোর অনুরোধ Admin-এর কাছে পাঠানো যেতে পারে। Final সিদ্ধান্ত Admin দেবেন।

Warranty:
Warranty উল্লেখ না থাকলে বলবেন: “ওয়ারেন্টি বা গ্যারান্টি নেই, তবে Best Quality।” ২–৩ বছরের নিশ্চয়তা দেবেন না।

অবশ্যই মানবেন:
1. সবসময় বাংলায় উত্তর দেবেন।
2. Customer-কে “আপনি” বলে সম্বোধন করবেন।
3. উত্তর ছোট, সহজ ও ভদ্র হবে।
4. কোনো তথ্য বানাবেন না।
5. Product Price, Stock, Color, Feature বা Warranty অনুমান করবেন না।
6. এখানে না থাকা তথ্যের জন্য Admin-এর সঙ্গে যোগাযোগ করতে বলবেন।
7. কোনো Product-কে Pre-order বলবেন না।
8. Order-এর মাঝখানে প্রশ্ন করলে আগে প্রশ্নের উত্তর দেবেন, Order Data হিসেবে Save করবেন না।
9. Customer “Cancel”, “বাতিল”, “নিবো না”, “নেব না” বললে Order Flow বন্ধ করবেন।
"""

PRODUCTS: List[Dict[str, Any]] = [
    {
        "keywords": ["premium digital camera", "digital camera", "camera", "ক্যামেরা"],
        "name": "Premium Digital Camera",
        "price": 2150,
        "details": "32GB Memory Cardসহ Cute Premium Digital Camera। পরিষ্কার ছবি তোলে এবং Gift হিসেবে উপযোগী।",
        "features": ["পরিষ্কার ছবি", "ছবি ও Video সংরক্ষণ", "32GB Memory Card", "Premium Cute Design"],
        "colors": [],
        "warranty": "No Warranty",
        "delivery_charge": 100,
        "delivery_time": "২–৪ দিন",
        "stock": "Available",
    },
    {
        "keywords": ["instant print camera", "print camera", "প্রিন্ট ক্যামেরা"],
        "name": "Instant Print Camera",
        "price": 3200,
        "details": "ছবি তুলে সঙ্গে সঙ্গে Print করা যায়।",
        "features": ["৪টি Paper Roll Free", "প্রায় ৪০০+ ছবি Print", "32GB Memory Card Free", "Photo ও Video Storage", "Built-in Games", "Music"],
        "colors": [],
        "warranty": "No Warranty",
        "delivery_charge": 0,
        "delivery_time": "২–৪ দিন",
        "stock": "Available",
    },
    {
        "keywords": ["4k flip camera", "4k camera", "flip camera", "ফ্লিপ ক্যামেরা"],
        "name": "4K Flip Digital Camera",
        "price": 2690,
        "details": "4K Recording ও Flip Screenসহ Premium Digital Camera।",
        "features": ["4K Recording", "Flip Screen", "Premium Design"],
        "colors": ["Pink", "Black", "White", "Purple", "Brown"],
        "warranty": "No Warranty",
        "delivery_charge": 100,
        "delivery_time": "২–৪ দিন",
        "stock": "Available",
    },
    {
        "keywords": ["galaxy projector", "projector lamp", "galaxy lamp", "প্রজেক্টর"],
        "name": "Galaxy Projector Lamp",
        "price": 3600,
        "details": "রুমে Galaxy ও Star Projection তৈরি করে।",
        "features": ["Galaxy & Star Projection", "Bluetooth Speaker", "White Noise", "Remote Control", "13 Themes", "Timer Function", "USB Type-C"],
        "colors": [],
        "warranty": "No Warranty",
        "delivery_charge": 100,
        "delivery_time": "২–৪ দিন",
        "stock": "Available",
    },
    {
        "keywords": ["mini juicer", "juicer", "blender", "জুসার"],
        "name": "High Quality Brushless Motor Mini Juicer",
        "price": 890,
        "details": "Portable Fruit ও Vegetable Blender।",
        "features": ["Brushless Motor", "Portable", "Fruit & Vegetable Blender"],
        "colors": [],
        "warranty": "No Warranty",
        "delivery_charge": 0,
        "delivery_time": "২–৪ দিন",
        "stock": "Available",
    },
    {
        "keywords": ["clip-on earbuds", "open ear earbuds", "wireless earbuds", "earbuds", "হেডফোন", "ইয়ারবাড"],
        "name": "Clip-On Open Ear Wireless Earbuds",
        "price": 1250,
        "regular_price": 1600,
        "details": "Offer Price ৳১২৫০। Clear Voice ও Built-in Microphone আছে।",
        "features": ["Open Ear Design", "Clip-On Design", "Clear Voice", "Built-in Microphone", "Call Receive/Reject", "Music & Phone Call"],
        "colors": [],
        "warranty": "No Warranty",
        "delivery_charge": 100,
        "delivery_time": "২–৪ দিন",
        "stock": "Available",
    },
]

FAQS = [
    {"keywords": ["delivery time", "ডেলিভারি সময়", "কত দিনে", "জেলা", "থানা"], "answer": "📍 আপনার জেলা ও থানার নাম জানালে এলাকাভিত্তিক সঠিক সময় বলা যাবে। সাধারণত ২–৪ দিনের মধ্যে Delivery হয়।"},
    {"keywords": ["delivery charge", "ডেলিভারি চার্জ", "free delivery"], "answer": "🚚 সাধারণ Delivery Charge ৳১০০। Instant Print Camera ও Mini Juicer-এর Delivery Free।"},
    {"keywords": ["payment", "cod", "বিকাশ", "নগদ", "পেমেন্ট"], "answer": f"💳 Cash on Delivery আছে। বিকাশ/নগদ: {ADMIN_PHONE}। Advance Payment বাধ্যতামূলক নয়।"},
    {"keywords": ["location", "লোকেশন", "ভৈরব", "কিশোরগঞ্জ"], "answer": f"📍 আমাদের লোকেশন: ভৈরব, কিশোরগঞ্জ। আসার আগে Call/WhatsApp করুন: {ADMIN_PHONE}"},
    {"keywords": ["wholesale", "হোলসেল", "bulk", "reselling"], "answer": f"📦 Wholesale বা Bulk Order-এর জন্য Admin {ADMIN_NAME}-এর সঙ্গে যোগাযোগ করুন: {ADMIN_PHONE}"},
    {"keywords": ["return", "রিটার্ন", "return policy"], "answer": "🔄 Delivery-এর ২৪ ঘণ্টার মধ্যে যোগাযোগ করলে Return করা যাবে। Return Charge ৳১২০ এবং Product Original অবস্থায় থাকতে হবে।"},
    {"keywords": ["tracking", "parcel", "পার্সেল", "ট্র্যাকিং"], "answer": f"📦 পার্সেলের আপডেট জানতে Mobile Number পাঠান। Admin {ADMIN_NAME} Update জানাবেন।"},
]

CONFIRM_WORDS = {"confirm", "confirmed", "কনফার্ম", "হ্যাঁ", "ঠিক আছে", "yes"}
CANCEL_WORDS = {"cancel", "বাতিল", "অর্ডার বাতিল", "নিবো না", "নেব না", "নিতে চাই না", "stop"}
ORDER_WORDS = {"অর্ডার", "order", "নিতে চাই", "কিনতে চাই", "অর্ডার করতে চাই"}

SESSIONS: Dict[str, Dict[str, Any]] = {}
ORDERS: List[Dict[str, Any]] = []
PROCESSED_MESSAGES: Dict[str, float] = {}
SESSION_LOCK = threading.Lock()
ORDER_LOCK = threading.Lock()
MESSAGE_LOCK = threading.Lock()


def norm(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).casefold()


def number(value: Any) -> float:
    match = re.search(r"\d+(?:\.\d+)?", str(value or "").replace(",", ""))
    return float(match.group()) if match else 0.0


def money(value: float) -> str:
    value = float(value or 0)
    return f"৳{int(value)}" if value.is_integer() else f"৳{value:.2f}"


def contains_any(text: str, words: set) -> bool:
    normalized = norm(text)
    return any(norm(word) in normalized for word in words)


def valid_mobile(text: str) -> bool:
    digits = re.sub(r"\D", "", text)
    return len(digits) == 11 and digits.startswith("01")


def is_question(text: str) -> bool:
    normalized = norm(text)
    words = ["কি", "কী", "কত", "কোন", "কেন", "কেমন", "আছে", "হবে", "দাম", "price", "what", "which", "how", "?"]
    return "?" in text or any(word in normalized for word in words)


def is_duplicate_message(message_id: str) -> bool:
    if not message_id:
        return False
    now = time.time()
    with MESSAGE_LOCK:
        for key in [k for k, ts in PROCESSED_MESSAGES.items() if now - ts > 3600]:
            PROCESSED_MESSAGES.pop(key, None)
        if message_id in PROCESSED_MESSAGES:
            return True
        PROCESSED_MESSAGES[message_id] = now
    return False


def find_product(query: str) -> Optional[Dict[str, Any]]:
    q = norm(query)
    if not q:
        return None
    best_product = None
    best_score = 0.0
    for product in PRODUCTS:
        name = norm(product["name"])
        keywords = [norm(item) for item in product["keywords"]]
        searchable = norm(" ".join([product["name"], " ".join(product["keywords"]), product["details"], " ".join(product["features"])]))
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
        if score > best_score:
            best_product = product
            best_score = score
    return best_product if best_score >= 0.48 else None


def find_faq(query: str) -> Optional[str]:
    q = norm(query)
    best_answer = None
    best_score = 0.0
    for item in FAQS:
        for keyword in item["keywords"]:
            k = norm(keyword)
            score = 0.95 if k in q else SequenceMatcher(None, q, k).ratio()
            if score > best_score:
                best_score = score
                best_answer = item["answer"]
    return best_answer if best_score >= 0.58 else None


def product_text(product: Dict[str, Any]) -> str:
    lines = [f"🛍️ {product['name']}"]
    if product.get("regular_price"):
        lines.append(f"Regular Price: {money(product['regular_price'])}")
        lines.append(f"🔥 Offer Price: {money(product['price'])}")
    else:
        lines.append(f"💰 মূল্য: {money(product['price'])}")
    lines.extend([f"📦 Stock: {product['stock']}", product["details"], "✨ প্রধান Features:"])
    lines.extend(f"• {feature}" for feature in product["features"])
    if product["colors"]:
        lines.append("🎨 Colors: " + ", ".join(product["colors"]))
    lines.append(f"🛡️ Warranty: {product['warranty']}")
    lines.append(f"🚚 Delivery: {product['delivery_time']}")
    lines.append("💳 Delivery Charge: " + ("Free" if product["delivery_charge"] == 0 else money(product["delivery_charge"])))
    lines.append('\nঅর্ডার করতে “অর্ডার করতে চাই” লিখুন।')
    return "\n".join(lines)


def gemini_client() -> genai.Client:
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is missing.")
    return genai.Client(api_key=GEMINI_API_KEY)


def gemini_reply(user_message: str) -> str:
    if not GEMINI_API_KEY:
        return f"প্রশ্নটি আরেকটু পরিষ্কার করে লিখুন। Admin: {ADMIN_PHONE}"
    catalog = [{"name": p["name"], "price": p["price"], "regular_price": p.get("regular_price"), "details": p["details"], "features": p["features"], "colors": p["colors"], "warranty": p["warranty"], "delivery_charge": p["delivery_charge"], "delivery_time": p["delivery_time"], "stock": p["stock"]} for p in PRODUCTS]
    response = gemini_client().models.generate_content(
        model=GEMINI_MODEL,
        contents=user_message,
        config=types.GenerateContentConfig(
            system_instruction=BUSINESS_INFO + "\nStructured Product Catalog:\n" + json.dumps(catalog, ensure_ascii=False) + "\nFAQ:\n" + json.dumps(FAQS, ensure_ascii=False),
            temperature=0.2,
            max_output_tokens=350,
        ),
    )
    return (response.text or "").strip() or "প্রোডাক্টের নাম বা ছবি পাঠান।"


def verify_signature(raw_body: bytes, signature_header: Optional[str]) -> bool:
    if not META_APP_SECRET:
        logger.warning("META_APP_SECRET is missing. Signature verification is disabled.")
        return True
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(META_APP_SECRET.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header.split("=", 1)[1])


def send_message(user_id: str, message: Dict[str, Any]) -> None:
    if not PAGE_ACCESS_TOKEN:
        raise RuntimeError("PAGE_ACCESS_TOKEN is missing.")
    response = HTTP.post(
        f"https://graph.facebook.com/{GRAPH_API_VERSION}/me/messages",
        params={"access_token": PAGE_ACCESS_TOKEN},
        json={"recipient": {"id": user_id}, "messaging_type": "RESPONSE", "message": message},
        timeout=25,
    )
    if not response.ok:
        logger.error("Messenger API error %s: %s", response.status_code, response.text[:1000])
    response.raise_for_status()


def send_text(user_id: str, text: str) -> None:
    text = str(text or "").strip()
    if text:
        send_message(user_id, {"text": text[:2000]})


def get_session(user_id: str) -> Dict[str, Any]:
    with SESSION_LOCK:
        return dict(SESSIONS.get(user_id, {"stage": "", "user_id": user_id}))


def save_session(user_id: str, updates: Dict[str, Any]) -> None:
    with SESSION_LOCK:
        current = SESSIONS.get(user_id, {"stage": "", "user_id": user_id})
        current.update(updates)
        current["updated_at"] = datetime.now(timezone.utc).isoformat()
        SESSIONS[user_id] = current


def clear_session(user_id: str) -> None:
    with SESSION_LOCK:
        SESSIONS.pop(user_id, None)


def expected_prompt(stage: str) -> str:
    return {
        "waiting_product": "কোন প্রোডাক্টটি অর্ডার করতে চান? নাম লিখুন।",
        "waiting_color": "পছন্দের Color লিখুন।",
        "waiting_quantity": "কয়টি নিতে চান? সংখ্যা লিখুন।",
        "waiting_name": "আপনার পূর্ণ নাম লিখুন।",
        "waiting_mobile": "আপনার ১১ Digit Mobile Number লিখুন।",
        "waiting_area": "এলাকা বা গ্রামের নাম লিখুন।",
        "waiting_thana": "থানার নাম লিখুন।",
        "waiting_district": "জেলার নাম লিখুন।",
        "waiting_receive": "কোথা থেকে Receive করবেন লিখুন।",
        "waiting_address": "সম্পূর্ণ Delivery Address লিখুন।",
        "waiting_confirm": 'সব ঠিক থাকলে “Confirm” বা “কনফার্ম” লিখুন।',
    }.get(stage, "")


def order_summary(session: Dict[str, Any], product: Dict[str, Any]) -> str:
    quantity = max(int(number(session.get("quantity")) or 1), 1)
    charge = float(product["delivery_charge"])
    total = product["price"] * quantity + charge
    lines = ["📦 অর্ডার সারাংশ", f"প্রোডাক্ট: {product['name']}"]
    if session.get("color"):
        lines.append(f"Color: {session['color']}")
    lines.extend([
        f"Quantity: {quantity}",
        f"প্রতি পিস: {money(product['price'])}",
        "Delivery Charge: Free" if charge == 0 else f"Delivery Charge: {money(charge)}",
        f"মোট: {money(total)}",
        "",
        f"নাম: {session.get('customer_name', '')}",
        f"Mobile: {session.get('mobile', '')}",
        f"এলাকা/গ্রাম: {session.get('area', '')}",
        f"থানা: {session.get('thana', '')}",
        f"জেলা: {session.get('district', '')}",
        f"Receive করবেন: {session.get('receive_from', '')}",
        f"Full Address: {session.get('full_address', '')}",
        "",
        'সব ঠিক থাকলে “Confirm” বা “কনফার্ম” লিখুন।',
    ])
    return "\n".join(lines)


def save_order(user_id: str, session: Dict[str, Any], product: Dict[str, Any]) -> str:
    quantity = max(int(number(session.get("quantity")) or 1), 1)
    charge = float(product["delivery_charge"])
    order_id = f"SB-{datetime.now().strftime('%y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
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
    with ORDER_LOCK:
        ORDERS.append(order)
    logger.info("NEW ORDER: %s", json.dumps(order, ensure_ascii=False))
    return order_id


def order_flow(user_id: str, text: str, selected_product: Optional[Dict[str, Any]]) -> bool:
    session = get_session(user_id)
    stage = norm(session.get("stage"))
    t = norm(text)

    if contains_any(text, CANCEL_WORDS):
        clear_session(user_id)
        send_text(user_id, "✅ অর্ডার প্রক্রিয়া বাতিল করা হয়েছে।")
        return True

    if stage and stage != "waiting_confirm" and is_question(text):
        product = find_product(text)
        faq = find_faq(text)
        if product:
            send_text(user_id, product_text(product) + "\n\n📌 " + expected_prompt(stage))
            return True
        if faq:
            send_text(user_id, faq + "\n\n📌 " + expected_prompt(stage))
            return True

    if not stage and contains_any(text, ORDER_WORDS):
        product = selected_product or (find_product(session.get("product_name", "")) if session.get("product_name") else None)
        if not product:
            save_session(user_id, {"stage": "waiting_product"})
            send_text(user_id, expected_prompt("waiting_product"))
            return True
        save_session(user_id, {"product_name": product["name"]})
        if product["colors"]:
            save_session(user_id, {"stage": "waiting_color"})
            send_text(user_id, "Available Colors: " + ", ".join(product["colors"]) + "\nপছন্দের Color লিখুন।")
        else:
            save_session(user_id, {"stage": "waiting_quantity"})
            send_text(user_id, expected_prompt("waiting_quantity"))
        return True

    if stage == "waiting_product":
        if not selected_product:
            send_text(user_id, "প্রোডাক্টটি খুঁজে পাইনি। সঠিক নাম লিখুন।")
            return True
        save_session(user_id, {"product_name": selected_product["name"]})
        if selected_product["colors"]:
            save_session(user_id, {"stage": "waiting_color"})
            send_text(user_id, "Available Colors: " + ", ".join(selected_product["colors"]) + "\nপছন্দের Color লিখুন।")
        else:
            save_session(user_id, {"stage": "waiting_quantity"})
            send_text(user_id, expected_prompt("waiting_quantity"))
        return True

    if stage == "waiting_color":
        product = find_product(session.get("product_name", ""))
        valid_colors = [norm(c) for c in (product or {}).get("colors", [])]
        if valid_colors and not any(c in t for c in valid_colors):
            send_text(user_id, "সঠিক Color লিখুন: " + ", ".join((product or {}).get("colors", [])))
            return True
        save_session(user_id, {"color": text, "stage": "waiting_quantity"})
        send_text(user_id, expected_prompt("waiting_quantity"))
        return True

    if stage == "waiting_quantity":
        quantity = int(number(text) or 0)
        if quantity < 1 or quantity > 100:
            send_text(user_id, "সঠিক Quantity লিখুন—যেমন: 1")
            return True
        save_session(user_id, {"quantity": quantity, "stage": "waiting_name"})
        send_text(user_id, expected_prompt("waiting_name"))
        return True

    if stage == "waiting_name":
        if is_question(text) or len(text.strip()) < 2:
            send_text(user_id, expected_prompt("waiting_name"))
            return True
        save_session(user_id, {"customer_name": text, "stage": "waiting_mobile"})
        send_text(user_id, expected_prompt("waiting_mobile"))
        return True

    if stage == "waiting_mobile":
        if not valid_mobile(text):
            send_text(user_id, "সঠিক ১১ Digit Mobile Number লিখুন—যেমন: 01XXXXXXXXX")
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
        if is_question(text) or len(text.strip()) < 2:
            send_text(user_id, expected_prompt(stage))
            return True
        save_session(user_id, {key: text, "stage": next_stage})
        send_text(user_id, expected_prompt(next_stage))
        return True

    if stage == "waiting_address":
        if is_question(text) or len(text.strip()) < 5:
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
        send_text(user_id, f"✅ আপনার অর্ডার গ্রহণ করা হয়েছে।\nOrder ID: {order_id}\nAdmin যাচাই করে Final Confirmation দেবেন।")
        return True

    return False


def handle_message(user_id: str, text: str) -> None:
    selected_product = find_product(text)
    if order_flow(user_id, text, selected_product):
        return
    if selected_product:
        send_text(user_id, product_text(selected_product))
        save_session(user_id, {"product_name": selected_product["name"]})
        return
    faq_answer = find_faq(text)
    if faq_answer:
        send_text(user_id, faq_answer)
        return
    try:
        send_text(user_id, gemini_reply(text))
    except Exception:
        logger.exception("Gemini generation failed.")
        send_text(user_id, f"প্রশ্নটি বুঝতে সমস্যা হচ্ছে। Admin: {ADMIN_PHONE}")


def process_messaging_event(event: Dict[str, Any]) -> None:
    sender_id = (event.get("sender") or {}).get("id")
    message = event.get("message")
    if not sender_id or not isinstance(message, dict) or message.get("is_echo"):
        return
    message_id = str(message.get("mid") or "").strip()
    if message_id and is_duplicate_message(message_id):
        return
    text = str(message.get("text") or "").strip()
    if not text:
        return
    try:
        handle_message(str(sender_id), text)
    except Exception:
        logger.exception("Message handler failed.")
        try:
            send_text(str(sender_id), f"সাময়িক সমস্যা হয়েছে। Admin {ADMIN_NAME}: {ADMIN_PHONE}")
        except Exception:
            logger.exception("Fallback message failed.")


@app.get("/")
def home():
    return {
        "status": "ok",
        "bot": BOT_NAME,
        "messenger_configured": bool(PAGE_ACCESS_TOKEN),
        "gemini_configured": bool(GEMINI_API_KEY),
        "gemini_model": GEMINI_MODEL,
        "products_count": len(PRODUCTS),
        "faq_count": len(FAQS),
        "orders_in_memory": len(ORDERS),
    }, 200


@app.get("/health")
def health():
    return {"status": "healthy", "service": BOT_NAME}, 200


@app.get("/webhook")
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge", "")
    if mode == "subscribe" and token == VERIFY_TOKEN and VERIFY_TOKEN:
        return challenge, 200
    return "Verification failed", 403


@app.post("/webhook")
def receive_webhook():
    raw_body = request.get_data()
    if not verify_signature(raw_body, request.headers.get("X-Hub-Signature-256")):
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
    return {"count": len(ORDERS), "orders": ORDERS[-100:], "note": "Render restart হলে memory orders মুছে যাবে।"}, 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
