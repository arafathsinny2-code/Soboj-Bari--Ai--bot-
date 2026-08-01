import hashlib, hmac, json, logging, os, re, uuid
from datetime import datetime, timezone
from difflib import SequenceMatcher

import gspread
import requests
from dotenv import load_dotenv
from flask import Flask, request
from google.oauth2.service_account import Credentials
from openai import OpenAI

load_dotenv()
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

BOT_NAME = os.getenv("BOT_NAME", "সবুজ বাড়ি AI")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "")
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN", "")
META_APP_SECRET = os.getenv("META_APP_SECRET", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
GRAPH_API_VERSION = os.getenv("GRAPH_API_VERSION", "v23.0")
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "")
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")
ADMIN_NAME = os.getenv("ADMIN_NAME", "Arafat Rahman")
ADMIN_PHONE = os.getenv("ADMIN_PHONE", "01780618736")

PRODUCTS_SHEET = os.getenv("PRODUCTS_SHEET", "Products")
ORDERS_SHEET = os.getenv("ORDERS_SHEET", "Orders")
SESSIONS_SHEET = os.getenv("SESSIONS_SHEET", "Sessions")

client = OpenAI(api_key=OPENAI_API_KEY)

PRODUCT_HEADERS = [
    "Keywords","Product Name","Category","Price","Offer Price","Details","Features",
    "Colors","Warranty","Delivery Charge","Delivery Time","Stock","Status","Image URL"
]
ORDER_HEADERS = [
    "Order ID","Created At","Facebook User ID","Customer Name","Mobile",
    "Area/Village","Thana","District","Receive From","Full Address",
    "Product Name","Color","Quantity","Unit Price","Delivery Charge",
    "Total","Order Status"
]
SESSION_HEADERS = [
    "Facebook User ID","Stage","Product Name","Color","Quantity","Customer Name",
    "Mobile","Area/Village","Thana","District","Receive From","Full Address","Updated At"
]

CONFIRM_WORDS = {"confirm","confirmed","কনফার্ম","হ্যাঁ কনফার্ম","yes confirm"}
CANCEL_WORDS = {"cancel","বাতিল","অর্ডার বাতিল"}
ORDER_WORDS = ("অর্ডার","order","নিতে চাই","কিনতে চাই")

BUSINESS_RULES = f"""
আপনি “{BOT_NAME}”, একটি Facebook Page-এর বাংলা বিক্রয় সহকারী।
Admin: {ADMIN_NAME}; Call/WhatsApp: {ADMIN_PHONE}; লোকেশন: ভৈরব, কিশোরগঞ্জ।
Steadfast Courier-এর মাধ্যমে সারা বাংলাদেশে সাধারণত ২–৪ দিনে ডেলিভারি।
সাধারণ ডেলিভারি চার্জ ৳১০০; Sheet-এ আলাদা charge থাকলে সেটিই ব্যবহার করবেন।
Cash on Delivery আছে। কোনো প্রোডাক্টকে Pre-order বলবেন না।
Google Sheet ছাড়া দাম, স্টক, রঙ, ফিচার বা ওয়ারেন্টি বানাবেন না।
অজানা হলে অ্যাডমিনের সহায়তা নিতে বলবেন। উত্তর সংক্ষিপ্ত ও ভদ্র হবে।
"""

def norm(v):
    return re.sub(r"\s+", " ", str(v or "").strip()).casefold()

def number(v):
    m = re.search(r"\d+(?:\.\d+)?", str(v or "").replace(",", ""))
    return float(m.group()) if m else 0.0

def money(v):
    return f"৳{int(v)}" if float(v).is_integer() else f"৳{v:.2f}"

def verify_signature(raw, header):
    if not META_APP_SECRET:
        return True
    if not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(META_APP_SECRET.encode(), raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header.split("=", 1)[1])

def gs_client():
    info = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(info, scopes=scopes)
    return gspread.authorize(creds)

def workbook():
    return gs_client().open_by_key(GOOGLE_SHEET_ID)

def ensure_sheet(name, headers):
    book = workbook()
    try:
        ws = book.worksheet(name)
    except gspread.WorksheetNotFound:
        ws = book.add_worksheet(title=name, rows=1000, cols=max(20, len(headers)))
    if not ws.row_values(1):
        ws.append_row(headers, value_input_option="USER_ENTERED")
    return ws

def products():
    rows = ensure_sheet(PRODUCTS_SHEET, PRODUCT_HEADERS).get_all_records()
    result = []
    for r in rows:
        p = {str(k).strip(): str(v).strip() for k, v in r.items()}
        if p.get("Product Name") and norm(p.get("Status")) not in {"inactive","off","disabled"}:
            result.append(p)
    return result

def find_product(query, catalog):
    q = norm(query)
    if not q:
        return None
    best, score = None, 0.0
    for p in catalog:
        name = norm(p.get("Product Name"))
        keys = [norm(x) for x in re.split(r"[,;\n|]+", p.get("Keywords","")) if x.strip()]
        hay = norm(" ".join([p.get("Product Name",""),p.get("Keywords",""),p.get("Category",""),
                             p.get("Details",""),p.get("Features","")]))
        s = 0.0
        if name and name in q:
            s = 1.0
        elif q in hay:
            s = .94
        else:
            for k in keys + ([name] if name else []):
                if k:
                    if k in q or q in k:
                        s = max(s, .90)
                    s = max(s, SequenceMatcher(None, q, k).ratio())
            qt, ht = set(q.split()), set(hay.split())
            if qt:
                s = max(s, len(qt & ht) / len(qt))
        if s > score:
            best, score = p, s
    return best if score >= .48 else None

def current_price(p):
    return number(p.get("Offer Price")) or number(p.get("Price"))

def delivery_charge(p):
    t = norm(p.get("Delivery Charge"))
    if "free" in t or "ফ্রি" in t:
        return 0.0
    return number(p.get("Delivery Charge")) or 100.0

def send_message(user_id, message):
    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/me/messages"
    r = requests.post(
        url,
        params={"access_token": PAGE_ACCESS_TOKEN},
        json={"recipient":{"id":user_id},"messaging_type":"RESPONSE","message":message},
        timeout=25,
    )
    r.raise_for_status()

def send_text(user_id, text):
    send_message(user_id, {"text": text[:2000]})

def send_image(user_id, url):
    if url.startswith(("http://","https://")):
        send_message(user_id, {"attachment":{"type":"image","payload":{"url":url,"is_reusable":True}}})

def product_text(p):
    lines = [f"🛍️ {p.get('Product Name')}", f"💰 মূল্য: {money(current_price(p))}"]
    if p.get("Stock"): lines.append(f"📦 স্টক: {p.get('Stock')}")
    feats = [x.strip() for x in re.split(r"[,;\n|]+", p.get("Features","")) if x.strip()]
    if feats:
        lines.append("✨ প্রধান ফিচার:")
        lines.extend([f"• {x}" for x in feats[:6]])
    elif p.get("Details"):
        lines.append(p.get("Details")[:600])
    if p.get("Colors"): lines.append(f"🎨 রঙ: {p.get('Colors')}")
    if p.get("Warranty"): lines.append(f"🛡️ ওয়ারেন্টি: {p.get('Warranty')}")
    lines.append(f"🚚 ডেলিভারি: {p.get('Delivery Time') or '২–৪ দিন'}")
    lines.append(f"💳 ডেলিভারি চার্জ: {p.get('Delivery Charge') or '৳১০০'}")
    lines.append('\nঅর্ডার করতে “অর্ডার করতে চাই” লিখুন।')
    return "\n".join(lines)

def get_session(user_id):
    ws = ensure_sheet(SESSIONS_SHEET, SESSION_HEADERS)
    for row in ws.get_all_records():
        if str(row.get("Facebook User ID","")).strip() == user_id:
            return {str(k):str(v).strip() for k,v in row.items()}
    return {"Facebook User ID":user_id,"Stage":""}

def save_session(user_id, updates):
    ws = ensure_sheet(SESSIONS_SHEET, SESSION_HEADERS)
    rows = ws.get_all_records()
    idx, old = None, {}
    for i,row in enumerate(rows, start=2):
        if str(row.get("Facebook User ID","")).strip() == user_id:
            idx, old = i, {str(k):str(v).strip() for k,v in row.items()}
            break
    merged = {**old, **{k:str(v) for k,v in updates.items()}}
    merged["Facebook User ID"] = user_id
    merged["Updated At"] = datetime.now(timezone.utc).isoformat()
    values = [merged.get(h,"") for h in SESSION_HEADERS]
    if idx:
        ws.update(f"A{idx}:M{idx}", [values], value_input_option="USER_ENTERED")
    else:
        ws.append_row(values, value_input_option="USER_ENTERED")

def clear_session(user_id):
    save_session(user_id, {h:"" for h in SESSION_HEADERS if h not in {"Facebook User ID","Updated At"}})

def product_by_name(name, catalog):
    for p in catalog:
        if norm(p.get("Product Name")) == norm(name):
            return p
    return find_product(name, catalog)

def valid_mobile(t):
    d = re.sub(r"\D","",t)
    return len(d) in {10,11,13} and (d.startswith("01") or d.startswith("8801"))

def order_summary(s,p):
    qty = max(int(number(s.get("Quantity")) or 1),1)
    unit, charge = current_price(p), delivery_charge(p)
    total = unit*qty+charge
    lines = [
        "📦 অর্ডার সারাংশ",
        f"প্রোডাক্ট: {p.get('Product Name')}",
        f"রঙ: {s.get('Color')}" if s.get("Color") else "",
        f"পরিমাণ: {qty}",
        f"প্রতি পিস: {money(unit)}",
        f"ডেলিভারি চার্জ: {'ফ্রি' if charge == 0 else money(charge)}",
        f"মোট: {money(total)}",
        "",
        f"নাম: {s.get('Customer Name')}",
        f"মোবাইল: {s.get('Mobile')}",
        f"এলাকা/গ্রাম: {s.get('Area/Village')}",
        f"থানা: {s.get('Thana')}",
        f"জেলা: {s.get('District')}",
        f"রিসিভ করবেন: {s.get('Receive From')}",
        f"সম্পূর্ণ ঠিকানা: {s.get('Full Address')}",
        "",
        'সব ঠিক থাকলে “Confirm” বা “কনফার্ম” লিখুন।'
    ]
    return "\n".join([x for x in lines if x != ""])

def save_order(user_id,s,p):
    qty = max(int(number(s.get("Quantity")) or 1),1)
    unit, charge = current_price(p), delivery_charge(p)
    order_id = f"SB-{datetime.now().strftime('%y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    row = [
        order_id, datetime.now(timezone.utc).isoformat(), user_id,
        s.get("Customer Name",""), s.get("Mobile",""), s.get("Area/Village",""),
        s.get("Thana",""), s.get("District",""), s.get("Receive From",""),
        s.get("Full Address",""), p.get("Product Name",""), s.get("Color",""),
        qty, unit, charge, unit*qty+charge, "New - Admin Review"
    ]
    ensure_sheet(ORDERS_SHEET, ORDER_HEADERS).append_row(row, value_input_option="USER_ENTERED")
    return order_id

def image_from_event(event):
    for a in (event.get("message") or {}).get("attachments",[]) or []:
        if a.get("type") == "image":
            return (a.get("payload") or {}).get("url")
    return None

def describe_image(url):
    r = client.responses.create(
        model=OPENAI_MODEL,
        instructions="ছবির বিক্রয়যোগ্য প্রোডাক্টটি শনাক্ত করে সংক্ষিপ্ত বাংলা/ইংরেজি কীওয়ার্ড লিখুন। নিশ্চিত না হলে অনুমান করবেন না।",
        input=[{"role":"user","content":[
            {"type":"input_text","text":"এই ছবির প্রোডাক্টটি শনাক্ত করুন।"},
            {"type":"input_image","image_url":url}
        ]}],
        max_output_tokens=160,
    )
    return (r.output_text or "").strip()

def ai_reply(text,catalog):
    compact = [{
        "name":p.get("Product Name"),"keywords":p.get("Keywords"),
        "price":p.get("Offer Price") or p.get("Price"),"details":p.get("Details"),
        "features":p.get("Features"),"colors":p.get("Colors"),
        "warranty":p.get("Warranty"),"delivery_charge":p.get("Delivery Charge"),
        "delivery_time":p.get("Delivery Time"),"stock":p.get("Stock")
    } for p in catalog[:100]]
    r = client.responses.create(
        model=OPENAI_MODEL,
        instructions=BUSINESS_RULES+"\nProduct Catalog:\n"+json.dumps(compact,ensure_ascii=False),
        input=text,
        max_output_tokens=320,
    )
    return (r.output_text or "").strip() or "প্রোডাক্টের নাম বা ছবি পাঠান।"

def order_flow(user_id,text,catalog,selected):
    s = get_session(user_id)
    stage, ntext = norm(s.get("Stage")), norm(text)

    if ntext in CANCEL_WORDS:
        clear_session(user_id); send_text(user_id,"অর্ডার প্রক্রিয়া বাতিল করা হয়েছে।"); return True

    if not stage and any(w in ntext for w in ORDER_WORDS):
        p = selected or product_by_name(s.get("Product Name",""),catalog)
        if not p:
            save_session(user_id,{"Stage":"waiting_product"})
            send_text(user_id,"কোন প্রোডাক্টটি অর্ডার করতে চান? নাম বা ছবি পাঠান।")
            return True
        save_session(user_id,{"Stage":"waiting_color_or_quantity","Product Name":p.get("Product Name","")})
        send_text(user_id, f"পছন্দের রঙ লিখুন: {p.get('Colors')}" if p.get("Colors") else "কয়টি নিতে চান? সংখ্যা লিখুন।")
        return True

    if stage == "waiting_product":
        if not selected:
            send_text(user_id,"প্রোডাক্টটি পাইনি। সঠিক নাম বা পরিষ্কার ছবি পাঠান।"); return True
        save_session(user_id,{"Stage":"waiting_color_or_quantity","Product Name":selected.get("Product Name","")})
        send_text(user_id, f"পছন্দের রঙ লিখুন: {selected.get('Colors')}" if selected.get("Colors") else "কয়টি নিতে চান?")
        return True

    if stage == "waiting_color_or_quantity":
        p = product_by_name(s.get("Product Name",""),catalog)
        if p and p.get("Colors") and not s.get("Color"):
            save_session(user_id,{"Color":text,"Stage":"waiting_quantity"})
            send_text(user_id,"কয়টি নিতে চান? সংখ্যা লিখুন।")
        else:
            save_session(user_id,{"Quantity":max(int(number(text) or 1),1),"Stage":"waiting_name"})
            send_text(user_id,"আপনার নাম লিখুন।")
        return True

    steps = {
        "waiting_quantity":("Quantity",max(int(number(text) or 1),1),"waiting_name","আপনার নাম লিখুন।"),
        "waiting_name":("Customer Name",text,"waiting_mobile","আপনার মোবাইল নম্বর লিখুন।"),
        "waiting_area":("Area/Village",text,"waiting_thana","আপনার থানার নাম লিখুন।"),
        "waiting_thana":("Thana",text,"waiting_district","আপনার জেলার নাম লিখুন।"),
        "waiting_district":("District",text,"waiting_receive","কোথা থেকে রিসিভ করবেন?"),
        "waiting_receive":("Receive From",text,"waiting_address","সম্পূর্ণ ঠিকানা লিখুন।"),
    }
    if stage in steps:
        key,val,next_stage,prompt = steps[stage]
        save_session(user_id,{key:val,"Stage":next_stage}); send_text(user_id,prompt); return True

    if stage == "waiting_mobile":
        if not valid_mobile(text):
            send_text(user_id,"সঠিক মোবাইল নম্বর লিখুন—যেমন: 01XXXXXXXXX"); return True
        save_session(user_id,{"Mobile":text,"Stage":"waiting_area"})
        send_text(user_id,"এলাকা বা গ্রামের নাম লিখুন।"); return True

    if stage == "waiting_address":
        save_session(user_id,{"Full Address":text,"Stage":"waiting_confirm"})
        fresh = get_session(user_id); p = product_by_name(fresh.get("Product Name",""),catalog)
        send_text(user_id,order_summary(fresh,p)); return True

    if stage == "waiting_confirm":
        if ntext not in CONFIRM_WORDS:
            send_text(user_id,'Confirm করতে “Confirm” বা “কনফার্ম” লিখুন।'); return True
        fresh = get_session(user_id); p = product_by_name(fresh.get("Product Name",""),catalog)
        oid = save_order(user_id,fresh,p); clear_session(user_id)
        send_text(user_id,f"✅ অর্ডার গ্রহণ করা হয়েছে।\nOrder ID: {oid}\nঅ্যাডমিন যাচাই করে চূড়ান্ত কনফার্ম করবেন।")
        return True
    return False

def handle(user_id,text="",image_url=None):
    catalog = products()
    search = text
    if image_url:
        try:
            search = f"{text}\nছবির বর্ণনা: {describe_image(image_url)}"
        except Exception:
            app.logger.exception("Vision error")
    selected = find_product(search,catalog)

    if order_flow(user_id,text or search,catalog,selected):
        return

    if selected:
        if selected.get("Image URL"):
            try: send_image(user_id,selected.get("Image URL"))
            except Exception: app.logger.exception("Image send error")
        send_text(user_id,product_text(selected))
        save_session(user_id,{"Product Name":selected.get("Product Name","")})
        return

    send_text(user_id,ai_reply(search,catalog))

@app.get("/")
def home():
    return {"status":"ok","bot":BOT_NAME},200

@app.get("/webhook")
def webhook_verify():
    if request.args.get("hub.mode")=="subscribe" and request.args.get("hub.verify_token")==VERIFY_TOKEN:
        return request.args.get("hub.challenge",""),200
    return "Verification failed",403

@app.post("/webhook")
def webhook_receive():
    raw = request.get_data()
    if not verify_signature(raw,request.headers.get("X-Hub-Signature-256")):
        return "Invalid signature",403
    payload = request.get_json(silent=True) or {}
    if payload.get("object")!="page":
        return "Ignored",200
    for entry in payload.get("entry",[]):
        for event in entry.get("messaging",[]):
            sender = (event.get("sender") or {}).get("id")
            msg = event.get("message") or {}
            if not sender or msg.get("is_echo"): continue
            text = str(msg.get("text") or "").strip()
            image = image_from_event(event)
            try:
                handle(sender,text,image)
            except Exception:
                app.logger.exception("Handler error")
                send_text(sender,f"সাময়িক সমস্যা হয়েছে। Admin {ADMIN_NAME}: {ADMIN_PHONE}")
    return "EVENT_RECEIVED",200

if __name__ == "__main__":
    app.run(host="0.0.0.0",port=int(os.getenv("PORT","5000")))
