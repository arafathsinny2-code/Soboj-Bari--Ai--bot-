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

import gspread
import requests
from dotenv import load_dotenv
from flask import Flask, request
from google.oauth2.service_account import Credentials
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

GRAPH_API_VERSION = os.getenv(
    "GRAPH_API_VERSION",
    "v26.0",
).strip()

GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "").strip()
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv(
    "GOOGLE_SERVICE_ACCOUNT_JSON",
    "",
).strip()

ADMIN_NAME = os.getenv("ADMIN_NAME", "Arafat Rahman").strip()
ADMIN_PHONE = os.getenv("ADMIN_PHONE", "01780618736").strip()

PRODUCTS_SHEET = os.getenv("PRODUCTS_SHEET", "Products").strip()
ORDERS_SHEET = os.getenv("ORDERS_SHEET", "Orders").strip()
SESSIONS_SHEET = os.getenv("SESSIONS_SHEET", "Sessions").strip()


# =========================================================
# CONSTANTS
# =========================================================

PRODUCT_HEADERS = [
    "Keywords",
    "Product Name",
    "Category",
    "Price",
    "Offer Price",
    "Details",
    "Features",
    "Colors",
    "Warranty",
    "Delivery Charge",
    "Delivery Time",
    "Stock",
    "Status",
    "Image URL",
]

ORDER_HEADERS = [
    "Order ID",
    "Created At",
    "Facebook User ID",
    "Customer Name",
    "Mobile",
    "Area/Village",
    "Thana",
    "District",
    "Receive From",
    "Full Address",
    "Product Name",
    "Color",
    "Quantity",
    "Unit Price",
    "Delivery Charge",
    "Total",
    "Order Status",
]

SESSION_HEADERS = [
    "Facebook User ID",
    "Stage",
    "Product Name",
    "Color",
    "Quantity",
    "Customer Name",
    "Mobile",
    "Area/Village",
    "Thana",
    "District",
    "Receive From",
    "Full Address",
    "Updated At",
]

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

BUSINESS_RULES = f"""
আপনি “{BOT_NAME}”, একটি Facebook Page-এর বাংলা বিক্রয় সহকারী।

Admin: {ADMIN_NAME}
Call/WhatsApp: {ADMIN_PHONE}
লোকেশন: ভৈরব, কিশোরগঞ্জ।

Steadfast Courier-এর মাধ্যমে সারা বাংলাদেশে সাধারণত ২–৪ দিনে ডেলিভারি।
সাধারণ ডেলিভারি চার্জ ৳১০০।
Google Sheet-এ আলাদা চার্জ থাকলে সেটিই ব্যবহার করবেন।
Cash on Delivery আছে।
কোনো পণ্যকে Pre-order বলবেন না।
Google Sheet ছাড়া দাম, স্টক, রঙ, ফিচার বা ওয়ারেন্টি বানাবেন না।
তথ্য নিশ্চিত না হলে অ্যাডমিনের সহায়তা নিতে বলবেন।
উত্তর সংক্ষিপ্ত, স্বাভাবিক এবং ভদ্র বাংলায় দেবেন।
"""


# =========================================================
# DUPLICATE MESSAGE PROTECTION
# =========================================================

_processed_messages: Dict[str, float] = {}
_processed_lock = threading.Lock()

MESSAGE_CACHE_SECONDS = 60 * 60


def is_duplicate_message(message_id: str) -> bool:
    """
    একই Messenger message একাধিকবার webhook-এ এলে
    পুনরায় process করা বন্ধ করে।
    """

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
    return re.sub(
        r"\s+",
        " ",
        str(value or "").strip(),
    ).casefold()


def number(value: Any) -> float:
    match = re.search(
        r"\d+(?:\.\d+)?",
        str(value or "").replace(",", ""),
    )

    return float(match.group()) if match else 0.0


def money(value: float) -> str:
    value = float(value or 0)

    if value.is_integer():
        return f"৳{int(value)}"

    return f"৳{value:.2f}"


def google_configured() -> bool:
    return bool(
        GOOGLE_SHEET_ID
        and GOOGLE_SERVICE_ACCOUNT_JSON
    )


def openai_configured() -> bool:
    return bool(OPENAI_API_KEY)


def messenger_configured() -> bool:
    return bool(PAGE_ACCESS_TOKEN)


# =========================================================
# META SIGNATURE VERIFICATION
# =========================================================

def verify_signature(
    raw_body: bytes,
    signature_header: Optional[str],
) -> bool:
    """
    Meta webhook signature যাচাই করে।
    META_APP_SECRET না থাকলে development অবস্থায় request allow করে,
    তবে Render-এ META_APP_SECRET যোগ করা উচিত।
    """

    if not META_APP_SECRET:
        logger.warning(
            "META_APP_SECRET is missing. "
            "Webhook signature verification is disabled."
        )
        return True

    if (
        not signature_header
        or not signature_header.startswith("sha256=")
    ):
        return False

    expected_signature = hmac.new(
        META_APP_SECRET.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    received_signature = signature_header.split("=", 1)[1]

    return hmac.compare_digest(
        expected_signature,
        received_signature,
    )


# =========================================================
# OPENAI
# =========================================================

def get_openai_client() -> OpenAI:
    if not OPENAI_API_KEY:
        raise RuntimeError(
            "OPENAI_API_KEY is missing from Render Environment Variables."
        )

    return OpenAI(api_key=OPENAI_API_KEY)


# =========================================================
# GOOGLE SHEETS
# =========================================================

def parse_google_credentials() -> Dict[str, Any]:
    if not GOOGLE_SERVICE_ACCOUNT_JSON:
        raise RuntimeError(
            "GOOGLE_SERVICE_ACCOUNT_JSON is missing."
        )

    try:
        data = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)
    except json.JSONDecodeError as error:
        raise RuntimeError(
            "GOOGLE_SERVICE_ACCOUNT_JSON is not valid JSON."
        ) from error

    if not isinstance(data, dict):
        raise RuntimeError(
            "GOOGLE_SERVICE_ACCOUNT_JSON must contain a JSON object."
        )

    return data


def gs_client():
    if not GOOGLE_SHEET_ID:
        raise RuntimeError(
            "GOOGLE_SHEET_ID is missing."
        )

    credentials_info = parse_google_credentials()

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    credentials = Credentials.from_service_account_info(
        credentials_info,
        scopes=scopes,
    )

    return gspread.authorize(credentials)


def workbook():
    return gs_client().open_by_key(GOOGLE_SHEET_ID)


def ensure_sheet(
    name: str,
    headers: List[str],
):
    book = workbook()

    try:
        worksheet = book.worksheet(name)

    except gspread.WorksheetNotFound:
        worksheet = book.add_worksheet(
            title=name,
            rows=1000,
            cols=max(20, len(headers)),
        )

    if not worksheet.row_values(1):
        worksheet.append_row(
            headers,
            value_input_option="USER_ENTERED",
        )

    return worksheet


def products() -> List[Dict[str, str]]:
    worksheet = ensure_sheet(
        PRODUCTS_SHEET,
        PRODUCT_HEADERS,
    )

    rows = worksheet.get_all_records()
    result: List[Dict[str, str]] = []

    for row in rows:
        product = {
            str(key).strip(): str(value).strip()
            for key, value in row.items()
        }

        product_name = product.get("Product Name")
        status = norm(product.get("Status"))

        if (
            product_name
            and status not in {
                "inactive",
                "off",
                "disabled",
            }
        ):
            result.append(product)

    return result


def safe_products() -> List[Dict[str, str]]:
    """
    Google Sheet error হলে পুরো bot crash না করে
    খালি catalog ফিরিয়ে দেয়।
    """

    if not google_configured():
        logger.warning(
            "Google Sheets configuration is incomplete."
        )
        return []

    try:
        return products()

    except Exception:
        logger.exception(
            "Could not load products from Google Sheet."
        )
        return []


# =========================================================
# PRODUCT SEARCH
# =========================================================

def find_product(
    query: str,
    catalog: List[Dict[str, str]],
) -> Optional[Dict[str, str]]:
    query_normalized = norm(query)

    if not query_normalized:
        return None

    best_product = None
    best_score = 0.0

    for product in catalog:
        product_name = norm(
            product.get("Product Name")
        )

        keywords = [
            norm(item)
            for item in re.split(
                r"[,;\n|]+",
                product.get("Keywords", ""),
            )
            if item.strip()
        ]

        searchable_text = norm(
            " ".join(
                [
                    product.get("Product Name", ""),
                    product.get("Keywords", ""),
                    product.get("Category", ""),
                    product.get("Details", ""),
                    product.get("Features", ""),
                ]
            )
        )

        score = 0.0

        if product_name and product_name in query_normalized:
            score = 1.0

        elif query_normalized in searchable_text:
            score = 0.94

        else:
            terms = keywords + (
                [product_name]
                if product_name
                else []
            )

            for keyword in terms:
                if not keyword:
                    continue

                if (
                    keyword in query_normalized
                    or query_normalized in keyword
                ):
                    score = max(score, 0.90)

                score = max(
                    score,
                    SequenceMatcher(
                        None,
                        query_normalized,
                        keyword,
                    ).ratio(),
                )

            query_tokens = set(
                query_normalized.split()
            )

            product_tokens = set(
                searchable_text.split()
            )

            if query_tokens:
                overlap = (
                    len(query_tokens & product_tokens)
                    / len(query_tokens)
                )

                score = max(score, overlap)

        if score > best_score:
            best_product = product
            best_score = score

    if best_score >= 0.48:
        return best_product

    return None


def product_by_name(
    name: str,
    catalog: List[Dict[str, str]],
) -> Optional[Dict[str, str]]:
    for product in catalog:
        if norm(product.get("Product Name")) == norm(name):
            return product

    return find_product(name, catalog)


def current_price(product: Dict[str, str]) -> float:
    return (
        number(product.get("Offer Price"))
        or number(product.get("Price"))
    )


def delivery_charge(product: Dict[str, str]) -> float:
    charge_text = norm(
        product.get("Delivery Charge")
    )

    if (
        "free" in charge_text
        or "ফ্রি" in charge_text
    ):
        return 0.0

    return (
        number(product.get("Delivery Charge"))
        or 100.0
    )


# =========================================================
# SEND MESSENGER MESSAGES
# =========================================================

def send_message(
    user_id: str,
    message: Dict[str, Any],
) -> None:
    if not PAGE_ACCESS_TOKEN:
        raise RuntimeError(
            "PAGE_ACCESS_TOKEN is missing."
        )

    url = (
        f"https://graph.facebook.com/"
        f"{GRAPH_API_VERSION}/me/messages"
    )

    response = HTTP.post(
        url,
        params={
            "access_token": PAGE_ACCESS_TOKEN,
        },
        json={
            "recipient": {
                "id": user_id,
            },
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


def send_text(
    user_id: str,
    text: str,
) -> None:
    cleaned_text = str(text or "").strip()

    if not cleaned_text:
        return

    send_message(
        user_id,
        {
            "text": cleaned_text[:2000],
        },
    )


def send_image(
    user_id: str,
    image_url: str,
) -> None:
    image_url = str(image_url or "").strip()

    if not image_url.startswith(
        ("http://", "https://")
    ):
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

def product_text(
    product: Dict[str, str],
) -> str:
    price = current_price(product)

    lines = [
        f"🛍️ {product.get('Product Name')}",
        f"💰 মূল্য: {money(price)}",
    ]

    if product.get("Stock"):
        lines.append(
            f"📦 স্টক: {product.get('Stock')}"
        )

    features = [
        item.strip()
        for item in re.split(
            r"[,;\n|]+",
            product.get("Features", ""),
        )
        if item.strip()
    ]

    if features:
        lines.append("✨ প্রধান ফিচার:")

        lines.extend(
            f"• {feature}"
            for feature in features[:6]
        )

    elif product.get("Details"):
        lines.append(
            product.get("Details", "")[:600]
        )

    if product.get("Colors"):
        lines.append(
            f"🎨 রঙ: {product.get('Colors')}"
        )

    if product.get("Warranty"):
        lines.append(
            f"🛡️ ওয়ারেন্টি: "
            f"{product.get('Warranty')}"
        )

    delivery_time = (
        product.get("Delivery Time")
        or "২–৪ দিন"
    )

    lines.append(
        f"🚚 ডেলিভারি: {delivery_time}"
    )

    charge = delivery_charge(product)

    lines.append(
        "💳 ডেলিভারি চার্জ: "
        + (
            "ফ্রি"
            if charge == 0
            else money(charge)
        )
    )

    lines.append(
        '\nঅর্ডার করতে “অর্ডার করতে চাই” লিখুন।'
    )

    return "\n".join(lines)


# =========================================================
# SESSION MANAGEMENT
# =========================================================

def get_session(
    user_id: str,
) -> Dict[str, str]:
    worksheet = ensure_sheet(
        SESSIONS_SHEET,
        SESSION_HEADERS,
    )

    for row in worksheet.get_all_records():
        row_user_id = str(
            row.get("Facebook User ID", "")
        ).strip()

        if row_user_id == user_id:
            return {
                str(key): str(value).strip()
                for key, value in row.items()
            }

    return {
        "Facebook User ID": user_id,
        "Stage": "",
    }


def save_session(
    user_id: str,
    updates: Dict[str, Any],
) -> None:
    worksheet = ensure_sheet(
        SESSIONS_SHEET,
        SESSION_HEADERS,
    )

    rows = worksheet.get_all_records()

    row_index = None
    previous: Dict[str, str] = {}

    for index, row in enumerate(
        rows,
        start=2,
    ):
        row_user_id = str(
            row.get("Facebook User ID", "")
        ).strip()

        if row_user_id == user_id:
            row_index = index

            previous = {
                str(key): str(value).strip()
                for key, value in row.items()
            }

            break

    merged = {
        **previous,
        **{
            key: str(value)
            for key, value in updates.items()
        },
    }

    merged["Facebook User ID"] = user_id
    merged["Updated At"] = (
        datetime.now(timezone.utc).isoformat()
    )

    values = [
        merged.get(header, "")
        for header in SESSION_HEADERS
    ]

    if row_index:
        worksheet.update(
            f"A{row_index}:M{row_index}",
            [values],
            value_input_option="USER_ENTERED",
        )

    else:
        worksheet.append_row(
            values,
            value_input_option="USER_ENTERED",
        )


def clear_session(user_id: str) -> None:
    empty_values = {
        header: ""
        for header in SESSION_HEADERS
        if header not in {
            "Facebook User ID",
            "Updated At",
        }
    }

    save_session(
        user_id,
        empty_values,
    )


# =========================================================
# ORDER HELPERS
# =========================================================

def valid_mobile(text: str) -> bool:
    digits = re.sub(r"\D", "", text)

    return (
        len(digits) in {10, 11, 13}
        and (
            digits.startswith("01")
            or digits.startswith("8801")
        )
    )


def order_summary(
    session: Dict[str, str],
    product: Dict[str, str],
) -> str:
    quantity = max(
        int(number(session.get("Quantity")) or 1),
        1,
    )

    unit_price = current_price(product)
    charge = delivery_charge(product)
    total = unit_price * quantity + charge

    lines = [
        "📦 অর্ডার সারাংশ",
        f"প্রোডাক্ট: {product.get('Product Name')}",
    ]

    if session.get("Color"):
        lines.append(
            f"রঙ: {session.get('Color')}"
        )

    lines.extend(
        [
            f"পরিমাণ: {quantity}",
            f"প্রতি পিস: {money(unit_price)}",
            (
                "ডেলিভারি চার্জ: ফ্রি"
                if charge == 0
                else (
                    "ডেলিভারি চার্জ: "
                    f"{money(charge)}"
                )
            ),
            f"মোট: {money(total)}",
            "",
            f"নাম: {session.get('Customer Name')}",
            f"মোবাইল: {session.get('Mobile')}",
            (
                "এলাকা/গ্রাম: "
                f"{session.get('Area/Village')}"
            ),
            f"থানা: {session.get('Thana')}",
            f"জেলা: {session.get('District')}",
            (
                "রিসিভ করবেন: "
                f"{session.get('Receive From')}"
            ),
            (
                "সম্পূর্ণ ঠিকানা: "
                f"{session.get('Full Address')}"
            ),
            "",
            (
                'সব ঠিক থাকলে “Confirm” '
                'বা “কনফার্ম” লিখুন।'
            ),
        ]
    )

    return "\n".join(lines)


def save_order(
    user_id: str,
    session: Dict[str, str],
    product: Dict[str, str],
) -> str:
    quantity = max(
        int(number(session.get("Quantity")) or 1),
        1,
    )

    unit_price = current_price(product)
    charge = delivery_charge(product)

    order_id = (
        f"SB-{datetime.now().strftime('%y%m%d')}-"
        f"{uuid.uuid4().hex[:6].upper()}"
    )

    row = [
        order_id,
        datetime.now(timezone.utc).isoformat(),
        user_id,
        session.get("Customer Name", ""),
        session.get("Mobile", ""),
        session.get("Area/Village", ""),
        session.get("Thana", ""),
        session.get("District", ""),
        session.get("Receive From", ""),
        session.get("Full Address", ""),
        product.get("Product Name", ""),
        session.get("Color", ""),
        quantity,
        unit_price,
        charge,
        unit_price * quantity + charge,
        "New - Admin Review",
    ]

    worksheet = ensure_sheet(
        ORDERS_SHEET,
        ORDER_HEADERS,
    )

    worksheet.append_row(
        row,
        value_input_option="USER_ENTERED",
    )

    return order_id


# =========================================================
# IMAGE AND AI
# =========================================================

def image_from_event(
    event: Dict[str, Any],
) -> Optional[str]:
    message = event.get("message") or {}

    attachments = (
        message.get("attachments") or []
    )

    for attachment in attachments:
        if attachment.get("type") != "image":
            continue

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
            "ছবির বিক্রয়যোগ্য প্রোডাক্টটি শনাক্ত করে "
            "সংক্ষিপ্ত বাংলা/ইংরেজি কীওয়ার্ড লিখুন। "
            "নিশ্চিত না হলে অনুমান করবেন না।"
        ),
        input=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "এই ছবির প্রোডাক্টটি "
                            "শনাক্ত করুন।"
                        ),
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

    return (
        response.output_text or ""
    ).strip()


def ai_reply(
    text: str,
    catalog: List[Dict[str, str]],
) -> str:
    if not OPENAI_API_KEY:
        return (
            "আপনি কোন প্রোডাক্ট সম্পর্কে জানতে চান? "
            "প্রোডাক্টের নাম বা ছবি পাঠান।"
        )

    compact_catalog = [
        {
            "name": product.get("Product Name"),
            "keywords": product.get("Keywords"),
            "price": (
                product.get("Offer Price")
                or product.get("Price")
            ),
            "details": product.get("Details"),
            "features": product.get("Features"),
            "colors": product.get("Colors"),
            "warranty": product.get("Warranty"),
            "delivery_charge": product.get(
                "Delivery Charge"
            ),
            "delivery_time": product.get(
                "Delivery Time"
            ),
            "stock": product.get("Stock"),
        }
        for product in catalog[:100]
    ]

    client = get_openai_client()

    response = client.responses.create(
        model=OPENAI_MODEL,
        instructions=(
            BUSINESS_RULES
            + "\nProduct Catalog:\n"
            + json.dumps(
                compact_catalog,
                ensure_ascii=False,
            )
        ),
        input=text,
        max_output_tokens=320,
    )

    reply = (
        response.output_text or ""
    ).strip()

    return reply or (
        "প্রোডাক্টের নাম বা ছবি পাঠান।"
    )


# =========================================================
# ORDER FLOW
# =========================================================

def order_flow(
    user_id: str,
    text: str,
    catalog: List[Dict[str, str]],
    selected: Optional[Dict[str, str]],
) -> bool:
    if not google_configured():
        return False

    session = get_session(user_id)

    stage = norm(
        session.get("Stage")
    )

    normalized_text = norm(text)

    if normalized_text in CANCEL_WORDS:
        clear_session(user_id)

        send_text(
            user_id,
            "অর্ডার প্রক্রিয়া বাতিল করা হয়েছে।",
        )

        return True

    if (
        not stage
        and any(
            word in normalized_text
            for word in ORDER_WORDS
        )
    ):
        product = (
            selected
            or product_by_name(
                session.get("Product Name", ""),
                catalog,
            )
        )

        if not product:
            save_session(
                user_id,
                {
                    "Stage": "waiting_product",
                },
            )

            send_text(
                user_id,
                (
                    "কোন প্রোডাক্টটি অর্ডার "
                    "করতে চান? নাম বা ছবি পাঠান।"
                ),
            )

            return True

        save_session(
            user_id,
            {
                "Stage": "waiting_color_or_quantity",
                "Product Name": product.get(
                    "Product Name",
                    "",
                ),
            },
        )

        if product.get("Colors"):
            prompt = (
                "পছন্দের রঙ লিখুন: "
                f"{product.get('Colors')}"
            )
        else:
            prompt = (
                "কয়টি নিতে চান? সংখ্যা লিখুন।"
            )

        send_text(user_id, prompt)
        return True

    if stage == "waiting_product":
        if not selected:
            send_text(
                user_id,
                (
                    "প্রোডাক্টটি পাইনি। "
                    "সঠিক নাম বা পরিষ্কার ছবি পাঠান।"
                ),
            )

            return True

        save_session(
            user_id,
            {
                "Stage": "waiting_color_or_quantity",
                "Product Name": selected.get(
                    "Product Name",
                    "",
                ),
            },
        )

        if selected.get("Colors"):
            prompt = (
                "পছন্দের রঙ লিখুন: "
                f"{selected.get('Colors')}"
            )
        else:
            prompt = "কয়টি নিতে চান?"

        send_text(user_id, prompt)
        return True

    if stage == "waiting_color_or_quantity":
        product = product_by_name(
            session.get("Product Name", ""),
            catalog,
        )

        if (
            product
            and product.get("Colors")
            and not session.get("Color")
        ):
            save_session(
                user_id,
                {
                    "Color": text,
                    "Stage": "waiting_quantity",
                },
            )

            send_text(
                user_id,
                "কয়টি নিতে চান? সংখ্যা লিখুন।",
            )

        else:
            quantity = max(
                int(number(text) or 1),
                1,
            )

            save_session(
                user_id,
                {
                    "Quantity": quantity,
                    "Stage": "waiting_name",
                },
            )

            send_text(
                user_id,
                "আপনার নাম লিখুন।",
            )

        return True

    steps = {
        "waiting_quantity": (
            "Quantity",
            max(int(number(text) or 1), 1),
            "waiting_name",
            "আপনার নাম লিখুন।",
        ),
        "waiting_name": (
            "Customer Name",
            text,
            "waiting_mobile",
            "আপনার মোবাইল নম্বর লিখুন।",
        ),
        "waiting_area": (
            "Area/Village",
            text,
            "waiting_thana",
            "আপনার থানার নাম লিখুন।",
        ),
        "waiting_thana": (
            "Thana",
            text,
            "waiting_district",
            "আপনার জেলার নাম লিখুন।",
        ),
        "waiting_district": (
            "District",
            text,
            "waiting_receive",
            "কোথা থেকে রিসিভ করবেন?",
        ),
        "waiting_receive": (
            "Receive From",
            text,
            "waiting_address",
            "সম্পূর্ণ ঠিকানা লিখুন।",
        ),
    }

    if stage in steps:
        key, value, next_stage, prompt = steps[stage]

        save_session(
            user_id,
            {
                key: value,
                "Stage": next_stage,
            },
        )

        send_text(user_id, prompt)
        return True

    if stage == "waiting_mobile":
        if not valid_mobile(text):
            send_text(
                user_id,
                (
                    "সঠিক মোবাইল নম্বর লিখুন—"
                    "যেমন: 01XXXXXXXXX"
                ),
            )

            return True

        save_session(
            user_id,
            {
                "Mobile": text,
                "Stage": "waiting_area",
            },
        )

        send_text(
            user_id,
            "এলাকা বা গ্রামের নাম লিখুন।",
        )

        return True

    if stage == "waiting_address":
        save_session(
            user_id,
            {
                "Full Address": text,
                "Stage": "waiting_confirm",
            },
        )

        fresh_session = get_session(user_id)

        product = product_by_name(
            fresh_session.get(
                "Product Name",
                "",
            ),
            catalog,
        )

        if not product:
            send_text(
                user_id,
                (
                    "প্রোডাক্টের তথ্য পাওয়া যায়নি। "
                    f"Admin {ADMIN_NAME}: {ADMIN_PHONE}"
                ),
            )

            return True

        send_text(
            user_id,
            order_summary(
                fresh_session,
                product,
            ),
        )

        return True

    if stage == "waiting_confirm":
        if normalized_text not in CONFIRM_WORDS:
            send_text(
                user_id,
                (
                    'Confirm করতে “Confirm” '
                    'বা “কনফার্ম” লিখুন।'
                ),
            )

            return True

        fresh_session = get_session(user_id)

        product = product_by_name(
            fresh_session.get(
                "Product Name",
                "",
            ),
            catalog,
        )

        if not product:
            send_text(
                user_id,
                (
                    "প্রোডাক্টের তথ্য পাওয়া যায়নি। "
                    f"Admin {ADMIN_NAME}: {ADMIN_PHONE}"
                ),
            )

            return True

        order_id = save_order(
            user_id,
            fresh_session,
            product,
        )

        clear_session(user_id)

        send_text(
            user_id,
            (
                "✅ অর্ডার গ্রহণ করা হয়েছে।\n"
                f"Order ID: {order_id}\n"
                "অ্যাডমিন যাচাই করে "
                "চূড়ান্ত কনফার্ম করবেন।"
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
    catalog = safe_products()

    search_text = str(text or "").strip()

    if image_url:
        if openai_configured():
            try:
                image_description = describe_image(
                    image_url
                )

                search_text = (
                    f"{search_text}\n"
                    f"ছবির বর্ণনা: "
                    f"{image_description}"
                ).strip()

            except Exception:
                logger.exception(
                    "Vision processing failed."
                )

        elif not search_text:
            send_text(
                user_id,
                (
                    "ছবিটি পেয়েছি। "
                    "প্রোডাক্টের নামও লিখে পাঠান।"
                ),
            )

            return

    selected_product = find_product(
        search_text,
        catalog,
    )

    if order_flow(
        user_id,
        text or search_text,
        catalog,
        selected_product,
    ):
        return

    if selected_product:
        image = selected_product.get(
            "Image URL"
        )

        if image:
            try:
                send_image(
                    user_id,
                    image,
                )

            except Exception:
                logger.exception(
                    "Product image send failed."
                )

        send_text(
            user_id,
            product_text(selected_product),
        )

        if google_configured():
            try:
                save_session(
                    user_id,
                    {
                        "Product Name": (
                            selected_product.get(
                                "Product Name",
                                "",
                            )
                        )
                    },
                )

            except Exception:
                logger.exception(
                    "Could not save selected product."
                )

        return

    if not search_text:
        send_text(
            user_id,
            (
                "আপনার মেসেজটি বুঝতে পারিনি। "
                "প্রোডাক্টের নাম বা ছবি পাঠান।"
            ),
        )

        return

    reply = ai_reply(
        search_text,
        catalog,
    )

    send_text(
        user_id,
        reply,
    )


# =========================================================
# BACKGROUND EVENT PROCESSOR
# =========================================================

def process_messaging_event(
    event: Dict[str, Any],
) -> None:
    sender = (
        event.get("sender") or {}
    ).get("id")

    message = event.get("message")

    # Delivery, read, reaction, postback বা অন্যান্য event বাদ
    if (
        not sender
        or not isinstance(message, dict)
    ):
        return

    # Bot-এর নিজের পাঠানো echo message বাদ
    if message.get("is_echo"):
        return

    message_id = str(
        message.get("mid") or ""
    ).strip()

    # একই message দ্বিতীয়বার process হবে না
    if (
        message_id
        and is_duplicate_message(message_id)
    ):
        logger.info(
            "Duplicate message ignored: %s",
            message_id,
        )
        return

    text = str(
        message.get("text") or ""
    ).strip()

    image_url = image_from_event(event)

    # Text বা image কোনোটিই না থাকলে বাদ
    if not text and not image_url:
        return

    try:
        handle(
            str(sender),
            text,
            image_url,
        )

    except Exception:
        logger.exception(
            "Message handler failed."
        )

        # একই event-এর জন্য শুধু একবার fallback পাঠানো হবে
        try:
            send_text(
                str(sender),
                (
                    "দুঃখিত, এই মুহূর্তে তথ্য "
                    "প্রসেস করা যাচ্ছে না। "
                    f"Admin {ADMIN_NAME}: {ADMIN_PHONE}"
                ),
            )

        except Exception:
            logger.exception(
                "Fallback message also failed."
            )


# =========================================================
# ROUTES
# =========================================================

@app.get("/")
def home():
    return {
        "status": "ok",
        "bot": BOT_NAME,
        "messenger_configured": (
            messenger_configured()
        ),
        "google_sheets_configured": (
            google_configured()
        ),
        "openai_configured": (
            openai_configured()
        ),
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
    token = request.args.get(
        "hub.verify_token"
    )
    challenge = request.args.get(
        "hub.challenge",
        "",
    )

    if (
        mode == "subscribe"
        and token == VERIFY_TOKEN
        and VERIFY_TOKEN
    ):
        logger.info(
            "Webhook verification successful."
        )

        return challenge, 200

    logger.warning(
        "Webhook verification failed."
    )

    return "Verification failed", 403


@app.post("/webhook")
def webhook_receive():
    raw_body = request.get_data()

    signature = request.headers.get(
        "X-Hub-Signature-256"
    )

    if not verify_signature(
        raw_body,
        signature,
    ):
        logger.warning(
            "Invalid webhook signature."
        )

        return "Invalid signature", 403

    payload = (
        request.get_json(silent=True)
        or {}
    )

    if payload.get("object") != "page":
        return "Ignored", 200

    # Meta-কে দ্রুত response দেওয়া হবে।
    # AI/Google Sheet processing background thread-এ চলবে।
    for entry in payload.get("entry", []):
        messaging_events = (
            entry.get("messaging", [])
            or []
        )

        for event in messaging_events:
            if isinstance(event, dict):
                EXECUTOR.submit(
                    process_messaging_event,
                    event,
                )

    return "EVENT_RECEIVED", 200


# =========================================================
# START APPLICATION
# =========================================================

if __name__ == "__main__":
    port = int(
        os.getenv("PORT", "5000")
    )

    app.run(
        host="0.0.0.0",
        port=port,
    )
