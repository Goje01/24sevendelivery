import ssl
import os
import json
import time
import uuid
import hmac
import hashlib
import smtplib
import traceback
import urllib.request
import urllib.parse
from email.message import EmailMessage
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, abort
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg2
import psycopg2.extras

try:
    import certifi
    SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    SSL_CONTEXT = ssl.create_default_context()

import os
from flask import Flask

base_dir = os.path.dirname(os.path.abspath(__file__))


app = Flask(
    __name__,
    template_folder=os.path.join(base_dir, 'templates'),
    static_folder=os.path.join(base_dir, 'static')
    
)
@app.route("/contact")
def contact():
    return render_template("contact.html", admin_email=ADMIN_EMAIL)

app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-fallback-secret-key-12345")

app.config['MAX_CONTENT_LENGTH'] = 4 * 1024 * 1024  # 4MB

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL environment variable is not set. "
        "Set it in Vercel: Project → Settings → Environment Variables."
    )
# ── Paystack keys ────────────────────────────────────────────────────────
# Set both of these in Vercel: Project → Settings → Environment Variables.
PAYSTACK_SECRET_KEY = os.environ.get("PAYSTACK_SECRET_KEY", "")
PAYSTACK_PUBLIC_KEY = os.environ.get("PAYSTACK_PUBLIC_KEY", "")

ADMIN_EMAIL     = os.environ.get("ADMIN_EMAIL", "official247delivery@gmail.com")
SMTP_HOST       = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT       = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER       = os.environ.get("SMTP_USER", "official247delivery@gmail.com")
SMTP_PASSWORD   = os.environ.get("SMTP_PASSWORD", "")
SMTP_FROM_NAME  = "24sevendelivery"

ADMIN_PATH = os.environ.get("ADMIN_PATH", "$$")
ADMIN_PASSWORD_HASH = generate_password_hash(
    os.environ.get("ADMIN_PASSWORD", "change-this-password-in-vercel")
)

DISCOUNT_ENABLED = True
DISCOUNT_PERCENT = 15
DISCOUNT_CODES = {
    "482913", "719260", "305847", "861204", "937512",
    "204689", "573198", "690742", "128456", "845017",
}

def is_discount_code_valid(code):
    if not DISCOUNT_ENABLED or not code:
        return False
    code = code.strip()
    if code not in DISCOUNT_CODES:
        return False
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM used_discount_codes WHERE code = %s", (code,))
        already_used = cur.fetchone()
        cur.close()
        return already_used is None
    finally:
        conn.close()

def mark_discount_code_used(code, order_id):
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO used_discount_codes (code, order_id) VALUES (%s, %s) ON CONFLICT (code) DO NOTHING",
            (code, order_id)
        )
        conn.commit()
        cur.close()
    finally:
        conn.close()

RING_SIZES = [
    {"us": "3",    "uk": "F",       "circumference_mm": 44.1, "diameter_mm": 14.05},
    {"us": "3 ½",  "uk": "G",       "circumference_mm": 45.4, "diameter_mm": 14.45},
    {"us": "4",    "uk": "H",       "circumference_mm": 46.8, "diameter_mm": 14.86},
    {"us": "4 ½",  "uk": "I",       "circumference_mm": 47.9, "diameter_mm": 15.27},
    {"us": "5",    "uk": "J",       "circumference_mm": 49.3, "diameter_mm": 15.70},
    {"us": "5 ½",  "uk": "K ¼",     "circumference_mm": 50.6, "diameter_mm": 16.10},
    {"us": "6",    "uk": "L ¼",     "circumference_mm": 51.9, "diameter_mm": 16.51},
    {"us": "6 ½",  "uk": "M ¼",     "circumference_mm": 53.1, "diameter_mm": 16.92},
    {"us": "7",    "uk": "N ½",     "circumference_mm": 54.4, "diameter_mm": 17.35},
    {"us": "7 ½",  "uk": "O ½",     "circumference_mm": 55.7, "diameter_mm": 17.75},
    {"us": "8",    "uk": "P ½",     "circumference_mm": 57.0, "diameter_mm": 18.19},
    {"us": "8 ½",  "uk": "Q ½",     "circumference_mm": 58.3, "diameter_mm": 18.53},
    {"us": "9",    "uk": "R ½",     "circumference_mm": 59.5, "diameter_mm": 18.89},
    {"us": "9 ½",  "uk": "S ½",     "circumference_mm": 60.8, "diameter_mm": 19.41},
    {"us": "10",   "uk": "T ½",     "circumference_mm": 62.3, "diameter_mm": 19.84},
    {"us": "10 ½", "uk": "U ½",     "circumference_mm": 63.5, "diameter_mm": 20.20},
    {"us": "11",   "uk": "V ½",     "circumference_mm": 64.9, "diameter_mm": 20.68},
    {"us": "11 ½", "uk": "W ½",     "circumference_mm": 66.2, "diameter_mm": 21.08},
    {"us": "12",   "uk": "X ½",     "circumference_mm": 67.5, "diameter_mm": 21.49},
    {"us": "13",   "uk": "Z ½",     "circumference_mm": 69.9, "diameter_mm": 22.25},
    {"us": "14",   "uk": "Z + 2¾",  "circumference_mm": 72.5, "diameter_mm": 23.08},
    {"us": "15",   "uk": "Z + 5",   "circumference_mm": 75.08,"diameter_mm": 23.90},
]

PRODUCTS = [
    {"id": 1,  "name": "Pizza",              "category": "Food & Treats", "image": "https://i.ibb.co/S4YZbTS0/74e3fb8b-2e02-4a95-973c-0f9295db176c.jpg",  "same_day": 4500000, "standard": None,    "standard_max": None,    "delivery": "same_day",  "description": "Fresh hot pizza delivered to your loved one on the same day."},
    {"id": 2,  "name": "Pizza with Coke",    "category": "Food & Treats", "image": "https://i.ibb.co/gZ5qk0KT/0f85fa01-86f1-4256-89cc-d1b9618d6849.jpg",  "same_day": 5500000, "standard": None,    "standard_max": None,    "delivery": "same_day",  "description": "Fresh hot pizza paired with an ice-cold Coke, delivered the same day."},
    {"id": 3,  "name": "Wine",               "category": "Drinks",        "image": "https://images.unsplash.com/photo-1656054106828-ea940e009329?fm=jpg&q=80&w=1200&auto=format&fit=crop",  "same_day": 8000000, "standard": None,    "standard_max": None,    "delivery": "same_day",  "description": "Premium wine bottle, elegantly presented."},
    {"id": 4,  "name": "Cake (Small)",        "category": "Food & Treats", "image": "https://i.ibb.co/DX8HNDQ/3aeb151b-d7fe-4601-a044-4c37f9762ce5.jpg",  "same_day": 5500000, "standard": None,    "standard_max": None,    "delivery": "same_day",  "description": "Beautifully crafted small celebration cake."},
    {"id": 5,  "name": "Cake (Big)",          "category": "Food & Treats", "image": "https://i.ibb.co/70wp4Yk/ee69fffe-559a-4ee8-8214-2b475b695564.jpg",  "same_day": 9000000, "standard": None,    "standard_max": None,    "delivery": "same_day",  "description": "Grand tiered celebration cake for special moments."},
    {"id": 6,  "name": "Flowers (Real)",      "category": "Flowers",       "image": "https://images.unsplash.com/photo-1610831006059-14fe16fe7ac4?q=80&w=1200&auto=format&fit=crop",  "same_day": 7000000, "standard": None,    "standard_max": None,    "delivery": "same_day",  "description": "Fresh real flowers, beautifully arranged."},
    {"id": 7,  "name": "Glass Flowers",       "category": "Flowers",       "image": "https://i.ibb.co/XkFHKYfw/8c0b0e51-c16f-4cdb-b6dc-a07de79d7543.jpg",  "same_day": 5000000, "standard": None,    "standard_max": None,    "delivery": "same_day",  "description": "Elegant handcrafted glass flower arrangement."},
    {"id": 8,  "name": "Fruit Basket",        "category": "Food & Treats", "image": "https://images.unsplash.com/photo-1694592014083-df5a081aa278?fm=jpg&q=80&w=1200&auto=format&fit=crop",  "same_day": 8000000, "standard": None,    "standard_max": None,    "delivery": "same_day",  "description": "Curated premium fruit basket, fresh and vibrant."},
    {"id": 9,  "name": "Chocolate",           "category": "Food & Treats", "image": "https://images.unsplash.com/photo-1687795097254-f019f9d7fd17?fm=jpg&q=80&w=1200&auto=format&fit=crop",  "same_day": 6500000, "standard": None,    "standard_max": None,    "delivery": "same_day",  "description": "Luxury assorted chocolates in premium packaging."},
    {"id": 10, "name": "Teddy Bear (Small)",  "category": "Plush & Toys",  "image": "https://images.unsplash.com/photo-1602734846297-9299fc2d4703?fm=jpg&q=80&w=1200&auto=format&fit=crop",  "same_day": 5500000, "standard": None,    "standard_max": None,    "delivery": "same_day",  "description": "Adorable soft teddy bear, a classic gift of love."},
    {"id": 11, "name": "Teddy Bear (Big)",    "category": "Plush & Toys",  "image": "https://images.unsplash.com/photo-1556012018-50c5c0da73bf?fm=jpg&q=80&w=1200&auto=format&fit=crop",  "same_day": 7500000, "standard": None,    "standard_max": None,    "delivery": "same_day",  "description": "Giant huggable teddy bear to make them smile."},
    {"id": 12, "name": "Ring (Silver)",       "category": "Jewelry",       "image": "https://i.ibb.co/4RMPw9gw/c41260d4-4e7a-49a9-8c19-025cbbd9b6d7.jpg",  "same_day": 6500000, "standard": 3000000, "standard_max": None,    "delivery": "both",      "description": "Elegant sterling silver ring, timeless and refined.", "sizes": RING_SIZES},
    {"id": 13, "name": "Ring (Gold)",         "category": "Jewelry",       "image": "https://i.ibb.co/q31yMB0R/6182c951-7b49-428f-82d8-fb8b5113e733.jpg",  "same_day": 7500000, "standard": 3500000, "standard_max": None,    "delivery": "both",      "description": "Stunning gold ring, crafted to last a lifetime.", "sizes": RING_SIZES},
    {"id": 14, "name": "Necklace (Standard)", "category": "Jewelry",       "image": "https://i.ibb.co/kVf7514d/8d0dd990-2439-4b54-918d-0c129f85ed6a.jpg",  "same_day": 6000000, "standard": 3500000, "standard_max": None,    "delivery": "both",      "description": "Delicate necklace, a graceful expression of love."},
    {"id": 15, "name": "Flowers (Artificial)","category": "Flowers",       "image": "https://i.ibb.co/mfwkHzv/53f47c20-0476-43b4-8c17-4ec61ee36804.jpg",  "same_day": None,    "standard": 3000000, "standard_max": None,    "delivery": "standard",  "description": "Beautiful artificial flowers that last forever."},
    {"id": 16, "name": "Love Box",            "category": "Gift Sets",     "image": "https://images.unsplash.com/photo-1625552187571-7ee60ac43d2b?q=80&w=1200&auto=format&fit=crop",  "same_day": None,    "standard": 4000000, "standard_max": None,    "delivery": "standard",  "description": "Romantic love box filled with heartfelt surprises."},
    {"id": 17, "name": "Explosion Box",       "category": "Gift Sets",     "image": "https://images.unsplash.com/photo-1647221598398-934ed5cb0e4f?q=80&w=1200&auto=format&fit=crop",  "same_day": None,    "standard": 4000000, "standard_max": None,    "delivery": "standard",  "description": "A beautiful surprise explosion box with layered gifts."},
    {"id": 18, "name": "Handbag (Small)",     "category": "Fashion",       "image": "https://images.unsplash.com/photo-1584917865442-de89df76afd3?q=80&w=1200&auto=format&fit=crop",  "same_day": None,    "standard": 4500000, "standard_max": None,    "delivery": "standard",  "description": "Stylish compact handbag, a fashion statement."},
    {"id": 19, "name": "Handbag (Big)",       "category": "Fashion",       "image": "https://images.unsplash.com/photo-1600857062241-98e5dba7f214?q=80&w=1200&auto=format&fit=crop",  "same_day": None,    "standard": 5500000, "standard_max": None,    "delivery": "standard",  "description": "Luxurious large designer-inspired handbag."},
    {"id": 20, "name": "Wrist Watch",         "category": "Accessories",   "image": "https://images.unsplash.com/photo-1524805444758-089113d48a6d?q=80&w=1200&auto=format&fit=crop",  "same_day": None,    "standard": 4500000, "standard_max": 5000000, "delivery": "standard",  "description": "Premium timepiece, a gift that keeps giving."},
    {"id": 21, "name": "Pants",               "category": "Fashion",       "image": "https://images.unsplash.com/photo-1624378439575-d8705ad7ae80?q=80&w=1200&auto=format&fit=crop",  "same_day": None,    "standard": 3500000, "standard_max": 4000000, "delivery": "standard",  "description": "Quality tailored pants, comfortable and sharp."},
    {"id": 22, "name": "Adult Gift Set",      "category": "Adult",         "image": "https://i.ibb.co/j9KmY1zk/8fc610fd-db2f-45c8-8bf9-038571ba9abe.jpg",  "same_day": None,    "standard": 5000000, "standard_max": 5500000, "delivery": "standard",  "description": "Discreetly packaged adult gift set for the adventurous couple."},
    {"id": 23, "name": "Hoodie",              "category": "Fashion",       "image": "https://images.unsplash.com/photo-1556821840-3a63f95609a7?q=80&w=1200&auto=format&fit=crop",  "same_day": None,    "standard": 5000000, "standard_max": 5500000, "delivery": "standard",  "description": "Cozy premium hoodie, comfort meets style."},
    {"id": 24, "name": "Perfume",             "category": "Beauty",        "image": "https://images.unsplash.com/photo-1624613533305-28d421d70875?q=80&w=1200&auto=format&fit=crop",  "same_day": None,    "standard": 5000000, "standard_max": 5500000, "delivery": "standard",  "description": "Exquisite fragrance to captivate the senses."},
    {"id": 25, "name": "Glasses",             "category": "Accessories",   "image": "https://i.ibb.co/60s68kF3/82913dce-17e1-4901-8807-5aa5a87c167f.jpg",  "same_day": None,    "standard": 3000000, "standard_max": 3500000, "delivery": "standard",  "description": "Chic eyewear that completes any look."},
    {"id": 26, "name": "Bracelet (Standard)", "category": "Jewelry",       "image": "https://i.ibb.co/zT1sHQc4/d0956164-8e59-4844-950c-4487cd783ce3.jpg",  "same_day": None,    "standard": 3000000, "standard_max": 3500000, "delivery": "standard",  "description": "Delicate bracelet, a symbol of elegance."},
    {"id": 27, "name": "Bracelet (Big)",      "category": "Jewelry",       "image": "https://i.ibb.co/XqD6h95/62e0be7e-e9da-49eb-b444-4eb8d3bf63cc.jpg",  "same_day": None,    "standard": 6000000, "standard_max": None,    "delivery": "standard",  "description": "Statement bracelet with a bolder, heavier design."},
    {"id": 28, "name": "Car Key / House Key / Specialty", "category": "Custom", "image": "https://images.unsplash.com/photo-1710006548781-eff5670376fa?q=80&w=1200&auto=format&fit=crop", "same_day": None, "standard": 5000000, "standard_max": None, "delivery": "standard", "description": "Specialty key-handover gift box for that big surprise moment."},
    {"id": 29, "name": "Customized Items",    "category": "Custom",        "image": "https://images.unsplash.com/photo-1549465220-1a8b9238cd48?q=80&w=1200&auto=format&fit=crop",  "same_day": None,    "standard": 5000000, "standard_max": None,    "delivery": "standard",  "description": "Personalized gifts: necklaces, hoodies, pillows, cups and more."},
]
PRODUCT_MAP = {p["id"]: p for p in PRODUCTS}

def get_db():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    return conn

def ensure_orders_table():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id TEXT PRIMARY KEY,
            product_id INTEGER NOT NULL,
            delivery_type TEXT NOT NULL,
            amount_kobo INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            paystack_reference TEXT,
            sender_name TEXT,
            sender_email TEXT,
            sender_phone TEXT,
            recipient_name TEXT,
            recipient_phone TEXT,
            recipient_address TEXT,
            recipient_city TEXT,
            recipient_country TEXT,
            gift_note TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS tracking_id TEXT")
    cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS discount_code TEXT")
    cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS ring_size TEXT")
    conn.commit()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS used_discount_codes (
            code TEXT PRIMARY KEY,
            order_id TEXT,
            used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    cur.close()
    conn.close()

ensure_orders_table()

def parse_ts(ts):
    return ts

def get_order_by_id(order_id):
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM orders WHERE id = %s", (order_id,))
        row = cur.fetchone()
        cur.close()
        return dict(row) if row else None
    finally:
        conn.close()

def get_order_by_reference(reference):
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM orders WHERE paystack_reference = %s", (reference,))
        row = cur.fetchone()
        cur.close()
        return dict(row) if row else None
    finally:
        conn.close()

def send_email(to_addr, subject, body, attachments=None):
    if not SMTP_USER or not SMTP_PASSWORD or not to_addr:
        print(f"[email skipped — SMTP not configured] to={to_addr} subject={subject}")
        return
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"{SMTP_FROM_NAME} <{SMTP_USER}>"
    msg["To"] = to_addr
    msg.set_content(body)
    for filename, file_bytes, mime_type in (attachments or []):
        if mime_type and "/" in mime_type:
            maintype, subtype = mime_type.split("/", 1)
        else:
            maintype, subtype = "application", "octet-stream"
        msg.add_attachment(file_bytes, maintype=maintype, subtype=subtype, filename=filename)
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        print(f"[email sent] to={to_addr} subject={subject}")
    except Exception as e:
        print(f"[email FAILED] to={to_addr} subject={subject} error={e}")

def order_email_body(order):
    p = PRODUCT_MAP.get(order.get("product_id"), {})
    delivery_label = "Same-Day" if order.get("delivery_type") == "same_day" else "Standard (3–4 Days)"
    ring_size_line = f"Ring Size: {order.get('ring_size')}\n" if order.get("ring_size") else ""
    return (
        f"Order ID: {order['id'][:8].upper()}\n"
        f"Reference: {order.get('paystack_reference', '')}\n"
        f"Status: {order.get('status', '').title()}\n"
        f"Item: {p.get('name', 'Unknown item')}\n"
        f"Delivery: {delivery_label}\n"
        f"{ring_size_line}"
        f"Amount: {fmt_price(order.get('amount_kobo'))}\n"
        f"\n"
        f"Sender: {order.get('sender_name', '')} ({order.get('sender_email', '')}, {order.get('sender_phone', '')})\n"
        f"Recipient: {order.get('recipient_name', '')} ({order.get('recipient_phone', '')})\n"
        f"Address: {order.get('recipient_address', '')}, {order.get('recipient_city', '')}, {order.get('recipient_country', '')}\n"
        f"Gift Note: {order.get('gift_note') or '—'}\n"
    )

def notify_new_paid_order(order):
    print(f"[notify_new_paid_order] firing for order {order.get('id')}")
    p = PRODUCT_MAP.get(order.get("product_id"), {})
    body = order_email_body(order)

    send_email(
        order.get("sender_email"),
        f"Your 24sevendelivery order is confirmed — {p.get('name', 'Gift')}",
        f"Hey {order.get('sender_name', 'there')},\n\nYour payment went through and your gift is on its way!\n\n{body}\nThanks for gifting with us.\n— 24sevendelivery"
    )

    send_email(
        ADMIN_EMAIL,
        f"🎁 New Paid Order — {p.get('name', 'Gift')} ({order['id'][:8].upper()})",
        f"New paid order just came in:\n\n{body}"
    )

def fmt_price(kobo):
    if kobo is None:
        return None
    return f"₦{kobo // 100:,.0f}"

app.jinja_env.filters["fmt_price"] = fmt_price

@app.route("/")
def index():
    featured = PRODUCTS[:8]
    return render_template("index.html", products=featured)

@app.route("/shop")
def shop():
    category = request.args.get("category", "")
    delivery = request.args.get("delivery", "")
    q = request.args.get("q", "").lower()
    products = PRODUCTS
    if category:
        products = [p for p in products if p["category"] == category]
    if delivery == "same_day":
        products = [p for p in products if p["delivery"] in ("same_day", "both")]
    elif delivery == "standard":
        products = [p for p in products if p["delivery"] in ("standard", "both")]
    if q:
        products = [p for p in products if q in p["name"].lower() or q in p["category"].lower()]
    categories = sorted(set(p["category"] for p in PRODUCTS))
    return render_template("shop.html", products=products, categories=categories,
                           sel_category=category, sel_delivery=delivery, search=q)

@app.route("/product/<int:pid>")
def product(pid):
    p = PRODUCT_MAP.get(pid)
    if not p:
        abort(404)
    return render_template("product.html", p=p, paystack_public_key=PAYSTACK_PUBLIC_KEY)

@app.route("/checkout")
def checkout():
    pid = request.args.get("product_id", type=int)
    delivery = request.args.get("delivery", "same_day")
    p = PRODUCT_MAP.get(pid)
    if not p:
        return redirect(url_for("shop"))
    price = p["same_day"] if delivery == "same_day" else p["standard"]
    if price is None:
        return redirect(url_for("product", pid=pid))
    return render_template("checkout.html", p=p, delivery=delivery, price=price,
                           paystack_public_key=PAYSTACK_PUBLIC_KEY, discount_enabled=DISCOUNT_ENABLED)

@app.route("/confirmation/<order_id>")
def confirmation(order_id):
    conn = get_db()
    order = None
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM orders WHERE id = %s", (order_id,))
        order = cur.fetchone()
        cur.close()
    except Exception as e:
        print("confirmation lookup error:", e)
    finally:
        conn.close()
    return render_template("confirmation.html", order=order, order_id=order_id)

@app.route(f"/{ADMIN_PATH}", methods=["GET", "POST"])
def admin_login():
    if session.get("admin"):
        return redirect(url_for("admin_dashboard"))
    error = None
    if request.method == "POST":
        pw = request.form.get("password", "")
        if check_password_hash(ADMIN_PASSWORD_HASH, pw):
            session["admin"] = True
            return redirect(url_for("admin_dashboard"))
        error = "Incorrect password."
    return render_template("admin_login.html", error=error)

@app.route(f"/{ADMIN_PATH}/dashboard")
def admin_dashboard():
    if not session.get("admin"):
        return redirect(url_for("admin_login"))
    conn = get_db()
    orders = []
    stats = {"total": 0, "paid": 0, "pending": 0, "revenue": 0}
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM orders ORDER BY created_at DESC")
        rows = cur.fetchall()
        cur.close()
        for r in rows:
            o = dict(r)
            o["created_at"] = parse_ts(o.get("created_at"))
            orders.append(o)
        stats["total"] = len(orders)
        stats["paid"] = sum(1 for o in orders if o["status"] == "paid")
        stats["pending"] = sum(1 for o in orders if o["status"] == "pending")
        stats["revenue"] = sum(o["amount_kobo"] for o in orders if o["status"] in ("shipped", "delivered"))
    except Exception as e:
        print("admin dashboard error:", e)
    finally:
        conn.close()
    return render_template("admin.html", orders=orders, stats=stats, products_list=PRODUCTS)

@app.route(f"/{ADMIN_PATH}/logout")
def admin_logout():
    session.pop("admin", None)
    return redirect(url_for("admin_login"))

@app.errorhandler(413)
def handle_file_too_large(e):
    return "That file is too large — please attach an image under 4MB and try again.", 413

@app.route(f"/{ADMIN_PATH}/update-order/<order_id>", methods=["POST"])
def admin_update_order(order_id):
    if not session.get("admin"):
        return jsonify({"error": "unauthorized"}), 401
    status = request.form.get("status")
    tracking_id = request.form.get("tracking_id", "").strip()
    if status not in ("pending", "paid", "processing", "shipped", "delivered", "cancelled"):
        return jsonify({"error": "invalid status"}), 400

    attachments = []
    uploaded_file = request.files.get("tracking_image")
    if uploaded_file and uploaded_file.filename:
        file_bytes = uploaded_file.read()
        if file_bytes:
            attachments.append((uploaded_file.filename, file_bytes, uploaded_file.mimetype))

    before = get_order_by_id(order_id)
    had_tracking = bool(before and before.get("tracking_id"))
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE orders SET status=%s, tracking_id=%s, updated_at=CURRENT_TIMESTAMP WHERE id=%s",
            (status, tracking_id or None, order_id)
        )
        conn.commit()
        cur.close()
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()
    order = get_order_by_id(order_id)
    if order:
        p = PRODUCT_MAP.get(order.get("product_id"), {})
        status_messages = {
            "processing": "is now being processed",
            "shipped":    "is on its way",
            "delivered":  "has been delivered — we hope they loved it!",
            "cancelled":  "has been cancelled",
        }
        line = status_messages.get(status)
        newly_tracked = bool(tracking_id) and not had_tracking
        if line or newly_tracked or attachments:
            tracking_line = f"\nTracking ID: {tracking_id}\n" if tracking_id else ""
            attachment_line = "\n(See attached file/image)\n" if attachments else ""
            send_email(
                order.get("sender_email"),
                f"Order update: {p.get('name', 'Your gift')}"
                + (f" {line}" if line else " has a tracking ID"),
                f"Hey {order.get('sender_name', 'there')},\n\n"
                f"Quick update on your order (ID {order['id'][:8].upper()}): "
                f"{line if line else 'a tracking ID has been added'}.\n\n"
                f"Item: {p.get('name', 'Unknown item')}\n"
                f"Status: {status.title()}\n"
                f"{tracking_line}"
                f"{attachment_line}\n"
                f"— 24sevendelivery",
                attachments=attachments
            )
    return redirect(url_for("admin_dashboard"))

@app.route("/api/products")
def api_products():
    return jsonify(PRODUCTS)

@app.route("/api/create-order", methods=["POST"])
def api_create_order():
    data = request.get_json()
    if not data:
        return jsonify({"error": "no data"}), 400
    pid = data.get("product_id")
    p = PRODUCT_MAP.get(pid)
    if not p:
        return jsonify({"error": "product not found"}), 404
    delivery = data.get("delivery_type", "same_day")
    price = p["same_day"] if delivery == "same_day" else p["standard"]
    if price is None:
        return jsonify({"error": "delivery type unavailable"}), 400

    discount_code = (data.get("discount_code") or "").strip()
    discount_applied = False
    if is_discount_code_valid(discount_code):
        price = round(price * (100 - DISCOUNT_PERCENT) / 100)
        discount_applied = True
    else:
        discount_code = None

    ring_size = (data.get("ring_size") or "").strip() or None

    order_id = str(uuid.uuid4())
    ref = f"GD-{order_id[:8].upper()}"
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO orders (id, product_id, delivery_type, amount_kobo, status,
              paystack_reference, sender_name, sender_email, sender_phone,
              recipient_name, recipient_phone, recipient_address,
              recipient_city, recipient_country, gift_note, discount_code, ring_size)
            VALUES (%s,%s,%s,%s,'pending',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (order_id, pid, delivery, price, ref,
              data.get("sender_name"), data.get("sender_email"), data.get("sender_phone"),
              data.get("recipient_name"), data.get("recipient_phone"),
              data.get("recipient_address"), data.get("recipient_city"),
              data.get("recipient_country"), data.get("gift_note"), discount_code, ring_size))
        conn.commit()
        cur.close()
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

    if discount_applied:
        mark_discount_code_used(discount_code, order_id)

    return jsonify({"order_id": order_id, "reference": ref, "amount": price,
                    "email": data.get("sender_email"), "public_key": PAYSTACK_PUBLIC_KEY,
                    "discount_applied": discount_applied})

@app.route("/api/verify-payment", methods=["POST"])
def api_verify_payment():
    data = request.get_json()
    reference = data.get("reference")
    if not reference:
        return jsonify({"error": "no reference"}), 400
    try:
        req = urllib.request.Request(
            f"https://api.paystack.co/transaction/verify/{urllib.parse.quote(reference)}",
            headers={"Authorization": f"Bearer {PAYSTACK_SECRET_KEY}"}
        )
        with urllib.request.urlopen(req, timeout=8, context=SSL_CONTEXT) as res:
            result = json.loads(res.read())
    except Exception as e:
        print("verify-payment request error:", e)
        traceback.print_exc()
        return jsonify({"error": str(e), "success": False}), 502
    if result.get("data", {}).get("status") == "success":
        existing = get_order_by_reference(reference)
        already_paid = existing and existing.get("status") == "paid"
        conn = get_db()
        try:
            cur = conn.cursor()
            cur.execute(
                "UPDATE orders SET status='paid', updated_at=CURRENT_TIMESTAMP WHERE paystack_reference=%s",
                (reference,)
            )
            conn.commit()
            cur.close()
        except Exception as e:
            print("verify-payment update error:", e)
        finally:
            conn.close()
        if existing and not already_paid:
            paid_order = get_order_by_id(existing["id"])
            if paid_order:
                notify_new_paid_order(paid_order)
        order_id = data.get("order_id")
        return jsonify({"success": True, "order_id": order_id})
    return jsonify({"success": False, "message": "Payment not verified"})

@app.route("/api/order-status/<order_id>")
def api_order_status(order_id):
    order = get_order_by_id(order_id)
    if not order:
        return jsonify({"error": "not found"}), 404
    return jsonify({"status": order.get("status"), "tracking_id": order.get("tracking_id")})

@app.route("/paystack-webhook", methods=["POST"])
def paystack_webhook():
    sig = request.headers.get("X-Paystack-Signature", "")
    body = request.get_data()
    expected = hmac.new(PAYSTACK_SECRET_KEY.encode(), body, hashlib.sha512).hexdigest()
    if not hmac.compare_digest(sig, expected):
        abort(400)
    event = request.get_json()
    if event and event.get("event") == "charge.success":
        ref = event["data"]["reference"]
        existing = get_order_by_reference(ref)
        already_paid = existing and existing.get("status") == "paid"
        conn = get_db()
        try:
            cur = conn.cursor()
            cur.execute("UPDATE orders SET status='paid', updated_at=CURRENT_TIMESTAMP WHERE paystack_reference=%s", (ref,))
            conn.commit()
            cur.close()
        except Exception as e:
            print("webhook update error:", e)
        finally:
            conn.close()
        if existing and not already_paid:
            paid_order = get_order_by_id(existing["id"])
            if paid_order:
                notify_new_paid_order(paid_order)
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)