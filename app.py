import hashlib
import hmac
import io
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from functools import wraps

from bson import ObjectId
from dotenv import load_dotenv
from flask import Flask, abort, flash, jsonify, redirect, render_template, request, send_file, session, url_for
from pymongo import MongoClient, ReturnDocument
from pymongo.errors import DuplicateKeyError, PyMongoError
import qrcode
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv()

app = Flask(__name__)
# Trust Render's reverse-proxy headers when creating external HTTPS URLs (e.g. Stripe return URLs).
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
app.config.update(
    SECRET_KEY=os.getenv("SECRET_KEY", "dev-only-change-this-secret"),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("COOKIE_SECURE", "false").lower() == "true",
    MAX_CONTENT_LENGTH=2 * 1024 * 1024,
)

MONGODB_URI = os.getenv("MONGODB_URI", "").strip()
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "vesta_fashion").strip() or "vesta_fashion"
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "vesta")
# Credenciales solicitadas para la instalación inicial. Cámbialas antes de abrir la tienda al público.
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "4")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "").strip()
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "").strip()
STORE_NAME = os.getenv("STORE_NAME", "VESTA")
CURRENCY = os.getenv("CURRENCY", "mxn").lower()
APP_BASE_URL = os.getenv("APP_BASE_URL", "").strip().rstrip("/")

mongo_client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000, tz_aware=True) if MONGODB_URI else None
RESERVATION_MINUTES = 5

SEED_PRODUCTS = [
    {"name": "Chaqueta urbana", "category": "Mujer", "description": "Chaqueta ligera de corte relajado para elevar cualquier look diario.", "price": 899, "sizes": ["XS", "S", "M", "L"], "colors": ["Negro", "Arena"], "image": "https://images.unsplash.com/photo-1529139574466-a303027c1d8b?auto=format&fit=crop&w=900&q=85", "stock": 14},
    {"name": "Camiseta Essential", "category": "Hombre", "description": "Algodón suave, silueta limpia y una básica que combina con todo.", "price": 349, "sizes": ["S", "M", "L", "XL"], "colors": ["Blanco", "Negro", "Oliva"], "image": "https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?auto=format&fit=crop&w=900&q=85", "stock": 32},
    {"name": "Tenis Street", "category": "Calzado", "description": "Diseño urbano y comodidad para acompañarte por toda la ciudad.", "price": 1199, "sizes": ["23", "24", "25", "26", "27", "28"], "colors": ["Blanco", "Negro", "Rojo"], "image": "https://images.unsplash.com/photo-1542291026-7eec264c27ff?auto=format&fit=crop&w=900&q=85", "stock": 10},
    {"name": "Bolsa Mini", "category": "Accesorios", "description": "Una silueta compacta con espacio para tus esenciales.", "price": 599, "sizes": ["Única"], "colors": ["Negro", "Crema"], "image": "https://images.unsplash.com/photo-1584917865442-de89df76afd3?auto=format&fit=crop&w=900&q=85", "stock": 9},
    {"name": "Vestido Aura", "category": "Mujer", "description": "Vestido versátil para una cena, un evento o cualquier plan especial.", "price": 749, "sizes": ["XS", "S", "M", "L"], "colors": ["Negro", "Vino"], "image": "https://images.unsplash.com/photo-1539008835657-9e8e9680c956?auto=format&fit=crop&w=900&q=85", "stock": 8},
    {"name": "Sudadera Studio", "category": "Hombre", "description": "Felpa cómoda, líneas minimalistas y ajuste relajado.", "price": 699, "sizes": ["S", "M", "L", "XL"], "colors": ["Gris", "Negro", "Crema"], "image": "https://images.unsplash.com/photo-1556821840-3a63f95609a7?auto=format&fit=crop&w=900&q=85", "stock": 18},
    {"name": "Pantalón Relax", "category": "Mujer", "description": "Pierna amplia y caída fluida para un look cómodo y pulido.", "price": 649, "sizes": ["XS", "S", "M", "L"], "colors": ["Arena", "Negro"], "image": "https://images.unsplash.com/photo-1509631179647-0177331693ae?auto=format&fit=crop&w=900&q=85", "stock": 12},
    {"name": "Gorra Daily", "category": "Accesorios", "description": "Un básico minimalista para completar tus conjuntos favoritos.", "price": 279, "sizes": ["Única"], "colors": ["Negro", "Azul", "Beige"], "image": "https://images.unsplash.com/photo-1588850561407-ed78c282e89b?auto=format&fit=crop&w=900&q=85", "stock": 25},
    {"name": "Blazer Siena", "category": "Mujer", "description": "Sastrería moderna con hombro suave y una silueta elegante.", "price": 1299, "sizes": ["XS", "S", "M", "L", "XL"], "colors": ["Arena", "Negro"], "image": "https://images.unsplash.com/photo-1591047139829-d91aecb6caea?auto=format&fit=crop&w=900&q=85", "stock": 7},
    {"name": "Jeans Rectos", "category": "Hombre", "description": "Denim clásico de pierna recta para combinar toda la semana.", "price": 799, "sizes": ["28", "30", "32", "34", "36"], "colors": ["Índigo", "Azul claro", "Negro"], "image": "https://images.unsplash.com/photo-1542272604-787c3835535d?auto=format&fit=crop&w=900&q=85", "stock": 21},
    {"name": "Suéter Nube", "category": "Mujer", "description": "Tejido suave y cálido, ideal para llevar en capas.", "price": 729, "sizes": ["XS", "S", "M", "L"], "colors": ["Crema", "Gris", "Chocolate"], "image": "https://images.unsplash.com/photo-1576566588028-4147f3842f27?auto=format&fit=crop&w=900&q=85", "stock": 11},
    {"name": "Camisa Oxford", "category": "Hombre", "description": "Una camisa atemporal que funciona con jeans o pantalón formal.", "price": 589, "sizes": ["S", "M", "L", "XL"], "colors": ["Blanco", "Azul cielo", "Rayas"], "image": "https://images.unsplash.com/photo-1598033129183-c4f50c736f10?auto=format&fit=crop&w=900&q=85", "stock": 16},
    {"name": "Falda Midi", "category": "Mujer", "description": "Movimiento ligero y largo midi para un estilo sencillo y femenino.", "price": 559, "sizes": ["XS", "S", "M", "L"], "colors": ["Negro", "Chocolate"], "image": "https://images.unsplash.com/photo-1583496661160-fb5886a0aaaa?auto=format&fit=crop&w=900&q=85", "stock": 10},
    {"name": "Sandalia Cala", "category": "Calzado", "description": "Sandalia ligera con diseño limpio para días soleados.", "price": 679, "sizes": ["23", "24", "25", "26", "27"], "colors": ["Negro", "Caramelo"], "image": "https://images.unsplash.com/photo-1543163521-1bf539c55dd2?auto=format&fit=crop&w=900&q=85", "stock": 13},
    {"name": "Bolso Tote", "category": "Accesorios", "description": "Amplio y práctico para llevar tus esenciales al trabajo o de viaje.", "price": 849, "sizes": ["Única"], "colors": ["Negro", "Camel", "Crema"], "image": "https://images.unsplash.com/photo-1590874103328-eac38a683ce7?auto=format&fit=crop&w=900&q=85", "stock": 6},
    {"name": "Cinturón Cuero", "category": "Accesorios", "description": "Un accesorio versátil con acabado clásico y hebilla discreta.", "price": 329, "sizes": ["S", "M", "L"], "colors": ["Negro", "Café"], "image": "https://images.unsplash.com/photo-1624222247344-550fb8b644d0?auto=format&fit=crop&w=900&q=85", "stock": 17},
    {"name": "Lentes Sol", "category": "Accesorios", "description": "Armazón contemporáneo para completar tus looks de fin de semana.", "price": 399, "sizes": ["Única"], "colors": ["Negro", "Carey"], "image": "https://images.unsplash.com/photo-1511499767150-a48a237f0083?auto=format&fit=crop&w=900&q=85", "stock": 19},
    {"name": "Chamarra Denim", "category": "Hombre", "description": "Una capa imprescindible con vibra relajada y acabado denim.", "price": 999, "sizes": ["S", "M", "L", "XL"], "colors": ["Azul", "Negro"], "image": "https://images.unsplash.com/photo-1551028719-00167b16eac5?auto=format&fit=crop&w=900&q=85", "stock": 8},
]

# Muestras originales de VESTA para la sección de ediciones exclusivas.
# Son diseños de inspiración de lujo/streetwear, no artículos oficiales de otras marcas.
SEED_EXCLUSIVE_PRODUCTS = [
    {
        "name": "Camisa Heritage Verde — VESTA Drop 01",
        "category": "Hombre",
        "description": "Camisa satinada de edición especial con patrón geométrico verde y marfil, inspirada en la estética del lujo italiano. Diseño original VESTA; no es una prenda oficial de Gucci ni de otra marca.",
        "price": 2490,
        "sizes": ["S", "M", "L", "XL"],
        "colors": ["Verde bosque"],
        "image": "/static/images/vesta-heritage-shirt.webp",
        "exclusive_limit": 3,
    },
    {
        "name": "Hoodie Street Noir — VESTA Drop 02",
        "category": "Hombre",
        "description": "Sudadera negra de felpa premium, corte oversize y gráfica original VESTA, inspirada en la cultura streetwear de diseñador. No es un artículo oficial de VLONE ni de otra marca.",
        "price": 1990,
        "sizes": ["S", "M", "L", "XL"],
        "colors": ["Negro"],
        "image": "https://images.unsplash.com/photo-1556821840-3a63f95609a7?auto=format&fit=crop&w=900&q=85",
        "exclusive_limit": 2,
    },
    {
        "name": "Chaqueta Biker Eclipse — VESTA Drop 03",
        "category": "Hombre",
        "description": "Chaqueta estilo biker en acabado negro, herrajes metálicos y silueta estructurada. Lanzamiento limitado de VESTA.",
        "price": 3290,
        "sizes": ["S", "M", "L", "XL"],
        "colors": ["Negro"],
        "image": "https://images.unsplash.com/photo-1551028719-00167b16eac5?auto=format&fit=crop&w=900&q=85",
        "exclusive_limit": 1,
    },
    {
        "name": "Blazer Atelier Noire — VESTA Drop 04",
        "category": "Mujer",
        "description": "Blazer de sastrería contemporánea, hombro definido y acabado elegante. Una edición VESTA de inspiración premium con cupo reducido.",
        "price": 2890,
        "sizes": ["XS", "S", "M", "L"],
        "colors": ["Negro"],
        "image": "https://images.unsplash.com/photo-1591047139829-d91aecb6caea?auto=format&fit=crop&w=900&q=85",
        "exclusive_limit": 2,
    },
]


def utcnow():
    return datetime.now(timezone.utc)


def get_db():
    if mongo_client is None:
        raise RuntimeError("Falta configurar MONGODB_URI en el archivo .env o en las variables de Render.")
    return mongo_client[MONGO_DB_NAME]


def sample_product_id(name):
    """Stable ObjectId used for sample catalog entries and offline preview."""
    return ObjectId(hashlib.sha256(("vesta-sample:" + name).encode("utf-8")).digest()[:12])


def fallback_products():
    """Show regular and exclusive demo catalog entries without Atlas credentials."""
    now = utcnow()
    regular = [
        json_product({**p, "_id": sample_product_id(p["name"]), "product_type": "regular", "stock_mode": "limited", "reserved": 0, "active": True, "created_at": now, "updated_at": now})
        for p in SEED_PRODUCTS
    ]
    exclusive = [
        json_product({**p, "_id": sample_product_id(p["name"]), "product_type": "exclusive", "stock_mode": "limited", "stock": p["exclusive_limit"], "reserved": 0, "active": True, "created_at": now, "updated_at": now})
        for p in SEED_EXCLUSIVE_PRODUCTS
    ]
    return regular + exclusive


def seed_products(db):
    # Migrate the previous catalogue model without losing the old distinction:
    # seed/demo pieces are regular; custom limited products from the former admin form
    # become exclusive drops; products with no stock_mode default to regular.
    seed_names = [product["name"] for product in SEED_PRODUCTS]
    db.products.update_many(
        {"product_type": {"$exists": False}, "name": {"$in": seed_names}},
        {"$set": {"product_type": "regular"}},
    )
    db.products.update_many(
        {"product_type": {"$exists": False}, "stock_mode": "limited"},
        {"$set": {"product_type": "exclusive"}},
    )
    db.products.update_many(
        {"product_type": {"$exists": False}},
        {"$set": {"product_type": "regular"}},
    )
    db.products.update_many({"stock_mode": {"$exists": False}}, {"$set": {"stock_mode": "limited"}})
    db.products.update_many({"reserved": {"$exists": False}}, {"$set": {"reserved": 0}})
    for product in db.products.find(
        {"product_type": "exclusive", "exclusive_limit": {"$exists": False}},
        {"_id": 1, "stock": 1},
    ):
        db.products.update_one(
            {"_id": product["_id"]},
            {"$set": {"exclusive_limit": int(product.get("stock", 0))}},
        )
    # Add missing examples even if this database already has a few products.
    # Existing products and their IDs are never overwritten.
    now = utcnow()
    for product in SEED_PRODUCTS:
        if db.products.find_one({"name": product["name"]}, {"_id": 1}):
            continue
        sample_id = sample_product_id(product["name"])
        if db.products.find_one({"_id": sample_id}, {"_id": 1}):
            continue
        db.products.insert_one({**product, "_id": sample_id, "product_type": "regular", "stock_mode": "limited", "reserved": 0, "active": True, "created_at": now, "updated_at": now})

    # Insertar las exclusivas de muestra una sola vez; nunca reemplazar inventario existente.
    for product in SEED_EXCLUSIVE_PRODUCTS:
        if db.products.find_one({"name": product["name"]}, {"_id": 1}):
            continue
        sample_id = sample_product_id(product["name"])
        if db.products.find_one({"_id": sample_id}, {"_id": 1}):
            continue
        limit = int(product["exclusive_limit"])
        db.products.insert_one({
            **product,
            "_id": sample_id,
            "product_type": "exclusive",
            "stock_mode": "limited",
            "stock": limit,
            "reserved": 0,
            "active": True,
            "created_at": now,
            "updated_at": now,
        })


def json_product(doc):
    product_type = doc.get("product_type", "regular")
    stock_mode = "limited" if product_type == "exclusive" else doc.get("stock_mode", "limited")
    stock = int(doc.get("stock", 0))
    reserved = int(doc.get("reserved", 0))
    available = None if stock_mode == "infinite" else max(stock - reserved, 0)
    exclusive_limit = int(doc.get("exclusive_limit", stock)) if product_type == "exclusive" else None
    sold = max(exclusive_limit - stock, 0) if exclusive_limit is not None else 0
    return {
        "id": str(doc["_id"]),
        "name": doc.get("name", "Producto"),
        "category": doc.get("category", "Otros"),
        "description": doc.get("description", ""),
        "price": float(doc.get("price", 0)),
        "sizes": doc.get("sizes", ["Única"]),
        "colors": doc.get("colors", ["Único"]),
        "image": doc.get("image", ""),
        "stock": stock,
        "reserved": reserved,
        "available_stock": available,
        "stock_mode": stock_mode,
        "product_type": product_type,
        "exclusive": product_type == "exclusive",
        "exclusive_limit": exclusive_limit,
        "sold": sold,
        "active": bool(doc.get("active", True)),
    }


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("is_admin") or session.get("admin_user") != ADMIN_USERNAME:
            if request.path.startswith("/api/"):
                return jsonify({"error": "Inicia sesión como administrador."}), 401
            return redirect(url_for("admin_login", next=request.path))
        return fn(*args, **kwargs)
    return wrapper


def valid_product_payload(data, partial=False):
    errors = []
    result = {}
    for field in ("name", "category", "description", "image"):
        if field in data:
            value = str(data.get(field, "")).strip()
            if field in ("name", "category") and not value:
                errors.append(f"El campo {field} es obligatorio.")
            result[field] = value
        elif not partial and field in ("name", "category"):
            errors.append(f"El campo {field} es obligatorio.")

    if "price" in data or not partial:
        try:
            price = float(data.get("price", 0))
            if price < 0 or price > 10000000:
                raise ValueError
            result["price"] = round(price, 2)
        except (ValueError, TypeError):
            errors.append("El precio debe ser un número positivo.")

    product_type = None
    if "product_type" in data or not partial:
        product_type = str(data.get("product_type", "regular")).lower()
        if product_type not in ("regular", "exclusive"):
            errors.append("Elige ropa normal o edición exclusiva.")
        else:
            result["product_type"] = product_type

    stock_mode = None
    if product_type == "exclusive":
        result["stock_mode"] = "limited"
        raw_limit = data.get("exclusive_limit", data.get("stock"))
        if raw_limit is not None or not partial:
            try:
                limit = int(raw_limit if raw_limit is not None else 0)
                if limit < 1 or limit > 10000000:
                    raise ValueError
                result["exclusive_limit"] = limit
            except (ValueError, TypeError):
                errors.append("El cupo máximo de compradores debe ser un entero mayor que cero.")
    elif product_type == "regular":
        if "stock_mode" in data or not partial:
            stock_mode = str(data.get("stock_mode", "limited")).lower()
            if stock_mode not in ("limited", "infinite"):
                errors.append("Elige inventario limitado o ilimitado para ropa normal.")
            else:
                result["stock_mode"] = stock_mode
        if stock_mode == "infinite":
            result["stock"] = 0
        elif "stock" in data or not partial:
            try:
                stock = int(data.get("stock", 0))
                if stock < 1 or stock > 10000000:
                    raise ValueError
                result["stock"] = stock
            except (ValueError, TypeError):
                errors.append("Las existencias deben ser un entero mayor que cero.")
    elif partial and "stock_mode" in data:
        stock_mode = str(data.get("stock_mode", "limited")).lower()
        if stock_mode not in ("limited", "infinite"):
            errors.append("El tipo de inventario no es válido.")
        else:
            result["stock_mode"] = stock_mode

    for field, default in (("sizes", ["Única"]), ("colors", ["Único"])):
        if field in data or not partial:
            value = data.get(field, default)
            if isinstance(value, str):
                value = [part.strip() for part in value.split(",") if part.strip()]
            if not isinstance(value, list):
                value = default
            value = [str(item).strip()[:40] for item in value if str(item).strip()][:20]
            result[field] = value or default
    if "active" in data:
        result["active"] = bool(data["active"])
    elif not partial:
        result["active"] = True
    if result.get("image", "") and not result["image"].startswith(("https://", "http://", "/static/")):
        errors.append("La imagen debe tener una URL http(s) o empezar por /static/.")
    return result, errors


def _product_is_limited(product):
    # Older documents without stock_mode are treated as limited inventory.
    return product.get("stock_mode", "limited") != "infinite"


def reserve_stock(db, clean_items):
    """Immediately consume stock for normal (non-temporary) checkout items."""
    committed = []
    for item in clean_items:
        product_id = ObjectId(item["product_id"])
        product = db.products.find_one({"_id": product_id, "active": True, "product_type": {"$ne": "exclusive"}})
        if not product:
            release_stock(db, committed)
            return None
        if not _product_is_limited(product):
            # Re-check the mode atomically so an admin edit cannot race this checkout.
            still_infinite = db.products.find_one({"_id": product_id, "active": True, "product_type": {"$ne": "exclusive"}, "stock_mode": "infinite"}, {"_id": 1})
            if not still_infinite:
                release_stock(db, committed)
                return None
            committed.append({**item, "stock_mode": "infinite"})
            continue
        updated = db.products.find_one_and_update(
            {
                "_id": product_id,
                "active": True,
                "product_type": {"$ne": "exclusive"},
                "$or": [{"stock_mode": "limited"}, {"stock_mode": {"$exists": False}}, {"stock_mode": None}],
                "$expr": {"$gte": [{"$subtract": ["$stock", {"$ifNull": ["$reserved", 0]}]}, item["quantity"]]},
            },
            {"$inc": {"stock": -item["quantity"]}, "$set": {"updated_at": utcnow()}},
            return_document=ReturnDocument.AFTER,
        )
        if updated is None:
            release_stock(db, committed)
            return None
        committed.append({**item, "stock_mode": "limited"})
    return committed


def release_stock(db, items):
    """Return stock consumed by an order; unlimited products have no counter."""
    for item in items:
        try:
            product_id = ObjectId(item["product_id"])
            mode = item.get("stock_mode")
            if mode is None:
                product = db.products.find_one({"_id": product_id}, {"stock_mode": 1}) or {}
                mode = product.get("stock_mode", "limited")
            if mode != "infinite":
                db.products.update_one({"_id": product_id}, {"$inc": {"stock": int(item["quantity"])} , "$set": {"updated_at": utcnow()}})
        except Exception:
            app.logger.exception("No se pudo devolver inventario para el pedido")


def public_url_for(endpoint, **values):
    """Build a canonical public URL, preferring APP_BASE_URL when configured."""
    path = url_for(endpoint, **values)
    base = APP_BASE_URL or request.url_root.rstrip("/")
    return f"{base}{path}"


def qr_png_bytes(target_url):
    """Create a real PNG QR code that points to a public VESTA page."""
    code = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=3,
    )
    code.add_data(target_url)
    code.make(fit=True)
    image = code.make_image(fill_color="#171717", back_color="white")
    output = io.BytesIO()
    image.save(output, format="PNG")
    output.seek(0)
    return output


def ensure_reservation_indexes(db):
    # Older VESTA builds used "active" for the same temporal reservation state.
    db.reservations.update_many({"status": "active"}, {"$set": {"status": "temporal"}})
    db.reservations.create_index("reservation_id", unique=True)
    db.reservations.create_index([("status", 1), ("expires_at", 1)])


def _release_reservation_items(db, reservation, mongo_session):
    for item in reservation.get("items", []):
        if item.get("stock_mode", "limited") == "infinite":
            continue
        db.products.update_one(
            {"_id": ObjectId(item["product_id"]), "reserved": {"$gte": int(item["quantity"])}},
            {"$inc": {"reserved": -int(item["quantity"])}, "$set": {"updated_at": utcnow()}},
            session=mongo_session,
        )


def expire_reservation(db, reservation_id):
    """Release an expired hold once and retain its terminal state for QR lookup."""
    if not reservation_id:
        return False
    now = utcnow()
    def operation(mongo_session):
        reservation = db.reservations.find_one({"reservation_id": reservation_id, "status": "temporal"}, session=mongo_session)
        if not reservation or reservation.get("expires_at") > now:
            return False
        _release_reservation_items(db, reservation, mongo_session)
        db.reservations.update_one(
            {"_id": reservation["_id"], "status": "temporal"},
            {"$set": {"status": "vencida", "expired_at": now, "updated_at": now}},
            session=mongo_session,
        )
        return True
    with db.client.start_session() as mongo_session:
        return mongo_session.with_transaction(operation)


def expire_due_reservations(db, limit=100):
    """Small lazy sweeper; it also frees holds left by visitors who close the page."""
    now = utcnow()
    ensure_reservation_indexes(db)
    due_ids = [row["reservation_id"] for row in db.reservations.find(
        {"status": "temporal", "expires_at": {"$lte": now}}, {"reservation_id": 1}
    ).limit(limit)]
    for reservation_id in due_ids:
        try:
            expire_reservation(db, reservation_id)
        except Exception:
            app.logger.exception("No se pudo liberar la reserva vencida %s", reservation_id)


def reservation_view(db, reservation):
    product_ids = [ObjectId(item["product_id"]) for item in reservation.get("items", []) if ObjectId.is_valid(item.get("product_id", ""))]
    products = {str(doc["_id"]): doc for doc in db.products.find({"_id": {"$in": product_ids}})} if product_ids else {}
    items = []
    for item in reservation.get("items", []):
        product = products.get(item["product_id"], {})
        items.append({
            "product_id": item["product_id"],
            "name": product.get("name", item.get("name", "Producto")),
            "image": product.get("image", item.get("image", "")),
            "price": float(product.get("price", item.get("price", 0))),
            "quantity": int(item.get("quantity", 1)), "size": item.get("size", "Única"),
            "color": item.get("color", "Único"), "stock_mode": item.get("stock_mode", "limited"),
        })
    expires_at = reservation.get("expires_at")
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    reservation_id = reservation["reservation_id"]
    return {
        "active": reservation.get("status") == "temporal",
        "status": reservation.get("status", "temporal"),
        "reservation_id": reservation_id,
        "expires_at": expires_at.isoformat() if expires_at else None,
        "created_at": reservation.get("created_at").isoformat() if hasattr(reservation.get("created_at"), "isoformat") else "",
        "order_number": reservation.get("order_number"),
        "public_url": public_url_for("public_reservation", reservation_id=reservation_id),
        "items": items,
    }


def create_temporary_reservation(db, product_id, quantity, size, color):
    ensure_reservation_indexes(db)
    visitor_id = session.get("visitor_id")
    if not visitor_id:
        visitor_id = uuid.uuid4().hex
        session["visitor_id"] = visitor_id
    previous_id = session.get("reservation_id")
    if previous_id:
        expire_reservation(db, previous_id)
    existing = db.reservations.find_one({
        "reservation_id": previous_id,
        "status": "temporal",
        "expires_at": {"$gt": utcnow()},
    }) if previous_id else None
    candidate_id = previous_id if existing else uuid.uuid4().hex
    now = utcnow()
    expires_at = now + timedelta(minutes=RESERVATION_MINUTES)

    def operation(mongo_session):
        reservation = db.reservations.find_one({"reservation_id": candidate_id, "status": "temporal"}, session=mongo_session)
        if reservation and reservation.get("expires_at") <= now:
            _release_reservation_items(db, reservation, mongo_session)
            db.reservations.update_one(
                {"_id": reservation["_id"], "status": "temporal"},
                {"$set": {"status": "vencida", "expired_at": now, "updated_at": now}},
                session=mongo_session,
            )
            raise ValueError("Tu apartado anterior venció. Vuelve a intentarlo para crear uno nuevo.")
        product_oid = ObjectId(product_id)
        product = db.products.find_one({"_id": product_oid, "active": True}, session=mongo_session)
        if not product:
            raise ValueError("Este artículo ya no está disponible.")
        if size not in product.get("sizes", ["Única"]):
            raise ValueError("La talla seleccionada ya no está disponible.")
        if color not in product.get("colors", ["Único"]):
            raise ValueError("El color seleccionado ya no está disponible.")
        if product.get("product_type", "regular") != "exclusive":
            raise ValueError("Esta prenda pertenece a Ropa normal. Agrégala a la bolsa para comprarla.")
        if any(line.get("product_id") == product_id for line in (reservation or {}).get("items", [])):
            raise ValueError("Ya tienes apartado este artículo. Cada visitante puede reservar una unidad de cada edición exclusiva.")
        updated = db.products.update_one(
            {
                "_id": product_oid, "active": True,
                "product_type": "exclusive",
                "$expr": {"$gte": [{"$subtract": ["$stock", {"$ifNull": ["$reserved", 0]}]}, quantity]},
            },
            {"$inc": {"reserved": quantity}, "$set": {"updated_at": now}},
            session=mongo_session,
        )
        if not updated.matched_count:
            raise ValueError("Ya no hay cupos disponibles para esta edición exclusiva.")

        if reservation is None:
            reservation = {
                "reservation_id": candidate_id, "visitante_id": visitor_id,
                "items": [], "status": "temporal",
                "created_at": now, "expires_at": expires_at,
            }
            db.reservations.insert_one(reservation, session=mongo_session)
            reservation = db.reservations.find_one({"reservation_id": candidate_id}, session=mongo_session)
        reservation.setdefault("items", []).append({
            "product_id": product_id, "quantity": 1, "size": size, "color": color,
            "name": product.get("name", "Producto"), "image": product.get("image", ""),
            "price": float(product.get("price", 0)),
            "stock_mode": "limited", "product_type": "exclusive",
        })
        db.reservations.replace_one({"_id": reservation["_id"]}, reservation, session=mongo_session)
        return reservation["expires_at"]

    with db.client.start_session() as mongo_session:
        final_expiry = mongo_session.with_transaction(operation)
    session["reservation_id"] = candidate_id
    return {
        "reservation_id": candidate_id,
        "expires_at": final_expiry.isoformat(),
        "public_url": public_url_for("public_reservation", reservation_id=candidate_id),
    }


def cancel_temporary_reservation(db, reservation_id):
    ensure_reservation_indexes(db)
    now = utcnow()
    def operation(mongo_session):
        reservation = db.reservations.find_one({"reservation_id": reservation_id, "status": "temporal"}, session=mongo_session)
        if not reservation:
            return False
        _release_reservation_items(db, reservation, mongo_session)
        db.reservations.update_one(
            {"_id": reservation["_id"], "status": "temporal"},
            {"$set": {"status": "cancelada", "cancelled_at": now, "updated_at": now}},
            session=mongo_session,
        )
        return True
    with db.client.start_session() as mongo_session:
        return mongo_session.with_transaction(operation)


def confirm_reservation_and_insert_order(db, reservation_id, order):
    ensure_reservation_indexes(db)
    def operation(mongo_session):
        now = utcnow()
        reservation = db.reservations.find_one(
            {"reservation_id": reservation_id, "status": "temporal", "expires_at": {"$gt": now}},
            session=mongo_session,
        )
        if not reservation:
            raise ValueError("Tu apartado venció o ya no está activo. Vuelve a reservar el artículo.")
        stock_items = []
        for item in reservation.get("items", []):
            product_id = ObjectId(item["product_id"])
            product = db.products.find_one({"_id": product_id, "active": True}, session=mongo_session)
            if not product:
                raise ValueError("Una prenda de tu apartado dejó de estar disponible.")
            if product.get("product_type", "regular") != "exclusive":
                raise ValueError("El apartado incluye una prenda que ya no es exclusiva. Contacta a VESTA.")
            mode = "limited"
            quantity = int(item["quantity"])
            if mode == "infinite":
                stock_items.append({**item, "stock_mode": "infinite"})
            else:
                updated = db.products.update_one(
                    {"_id": product_id, "active": True, "reserved": {"$gte": quantity}, "stock": {"$gte": quantity}},
                    {"$inc": {"stock": -quantity, "reserved": -quantity}, "$set": {"updated_at": now}},
                    session=mongo_session,
                )
                if not updated.matched_count:
                    raise ValueError("No se pudo confirmar el inventario apartado. Vuelve a intentarlo.")
                stock_items.append({**item, "stock_mode": "limited"})
        order["stock_items"] = stock_items
        db.orders.insert_one(order, session=mongo_session)
        db.reservations.update_one(
            {"_id": reservation["_id"], "status": "temporal"},
            {"$set": {"status": "confirmada", "order_number": order.get("number"), "confirmed_at": now, "updated_at": now}},
            session=mongo_session,
        )
        return order["_id"], stock_items
    with db.client.start_session() as mongo_session:
        return mongo_session.with_transaction(operation)


def sanitize_order(order):
    return {
        "id": str(order["_id"]),
        "number": order.get("number", str(order["_id"])[-8:].upper()),
        "customer": order.get("customer", {}),
        "items": order.get("items", []),
        "subtotal": float(order.get("subtotal", 0)),
        "shipping": float(order.get("shipping", 0)),
        "total": float(order.get("total", 0)),
        "payment_method": order.get("payment_method", "cod"),
        "payment_status": order.get("payment_status", "unpaid"),
        "status": order.get("status", "received"),
        "created_at": (order.get("created_at", utcnow()).isoformat()
                       if hasattr(order.get("created_at", utcnow()), "isoformat")
                       else str(order.get("created_at", ""))),
    }


@app.context_processor
def inject_store_settings():
    return {
        "store_name": STORE_NAME,
        "currency": CURRENCY.upper(),
        "stripe_enabled": bool(STRIPE_SECRET_KEY),
        "customer_signed_in": bool(session.get("customer_id")),
        "customer_name": session.get("customer_name", ""),
        "admin_signed_in": bool(session.get("is_admin")),
    }


@app.get("/")
def index():
    error = None
    demo_mode = False
    products = []
    try:
        db = get_db()
        seed_products(db)
        expire_due_reservations(db)
        products = [json_product(doc) for doc in db.products.find({"active": True}).sort("created_at", -1)]
    except (RuntimeError, PyMongoError) as exc:
        app.logger.warning("No se pudo cargar MongoDB: %s", exc)
        error = "No se pudo conectar con MongoDB Atlas. Se muestra el catálogo de ejemplo; configura MONGODB_URI para guardar pedidos e inventario."
        products = fallback_products()
        demo_mode = True
    normal_products = [product for product in products if product.get("product_type", "regular") != "exclusive"]
    exclusive_products = [product for product in products if product.get("product_type", "regular") == "exclusive"]
    return render_template("index.html", products=products, normal_products=normal_products, exclusive_products=exclusive_products, db_error=error, demo_mode=demo_mode)


@app.get("/health")
def health():
    try:
        get_db().command("ping")
        return jsonify({"status": "ok", "database": "connected"})
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 503


@app.get("/api/products")
def api_products():
    try:
        db = get_db()
        seed_products(db)
        expire_due_reservations(db)
        query = {"active": True}
        category = request.args.get("category", "").strip()
        if category and category.lower() != "todos":
            query["category"] = category
        term = request.args.get("q", "").strip()
        if term:
            query["$or"] = [{"name": {"$regex": re.escape(term), "$options": "i"}}, {"description": {"$regex": re.escape(term), "$options": "i"}}]
        products = [json_product(d) for d in db.products.find(query).sort("created_at", -1).limit(100)]
        return jsonify({"products": products})
    except Exception as exc:
        app.logger.exception("No se pudo listar productos")
        return jsonify({"error": "No se pudieron cargar los productos. Revisa la conexión con MongoDB."}), 503


@app.get("/api/reservations/current")
def api_reservation_current():
    try:
        db = get_db()
        expire_due_reservations(db)
        reservation_id = session.get("reservation_id")
        if not reservation_id:
            return jsonify({"active": False})
        reservation = db.reservations.find_one({"reservation_id": reservation_id, "status": "temporal", "expires_at": {"$gt": utcnow()}})
        if not reservation:
            session.pop("reservation_id", None)
            return jsonify({"active": False})
        return jsonify(reservation_view(db, reservation))
    except Exception:
        app.logger.exception("No se pudo consultar el apartado temporal")
        return jsonify({"error": "No se pudo consultar tu apartado. Inténtalo de nuevo."}), 503


@app.post("/api/reservations")
def api_reservation_create():
    data = request.get_json(silent=True) or {}
    product_id = str(data.get("product_id", ""))
    try:
        quantity = int(data.get("quantity", 1))
    except (TypeError, ValueError):
        return jsonify({"error": "La cantidad no es válida."}), 400
    if not ObjectId.is_valid(product_id):
        return jsonify({"error": "El artículo seleccionado no es válido."}), 400
    if quantity != 1:
        return jsonify({"error": "Las ediciones exclusivas permiten una unidad por visitante."}), 400
    size = str(data.get("size", "Única"))[:40]
    color = str(data.get("color", "Único"))[:40]
    try:
        result = create_temporary_reservation(get_db(), product_id, quantity, size, color)
        return jsonify({"ok": True, **result, "message": "Artículo apartado durante 5 minutos."})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 409
    except Exception:
        app.logger.exception("No se pudo crear el apartado temporal")
        return jsonify({"error": "No se pudo apartar el artículo. Inténtalo de nuevo."}), 503


@app.post("/api/reservations/cancel")
def api_reservation_cancel():
    reservation_id = session.get("reservation_id")
    if not reservation_id:
        return jsonify({"ok": True, "active": False})
    try:
        cancel_temporary_reservation(get_db(), reservation_id)
        session.pop("reservation_id", None)
        return jsonify({"ok": True, "active": False})
    except Exception:
        app.logger.exception("No se pudo cancelar el apartado")
        return jsonify({"error": "No se pudo cancelar el apartado. Inténtalo de nuevo."}), 503


@app.get("/ficha/<product_id>")
def public_product_ficha(product_id):
    """Public product sheet. Atlas is authoritative; deterministic demo products work offline."""
    if not ObjectId.is_valid(product_id):
        abort(404)

    demo_mode = False
    product = None
    try:
        db = get_db()
        expire_due_reservations(db)
        product_doc = db.products.find_one({"_id": ObjectId(product_id)})
        if not product_doc:
            abort(404)
        product = json_product(product_doc)
    except (RuntimeError, PyMongoError):
        # The home page intentionally offers a demo catalogue without Atlas. Let those
        # deterministic sample IDs open a demo sheet too, but never invent stored records.
        product = next((item for item in fallback_products() if item["id"] == product_id), None)
        if not product:
            app.logger.exception("No se pudo consultar la ficha pública del producto en Atlas")
            return render_template(
                "public_qr_error.html",
                title="No pudimos abrir esta ficha",
                message="Este artículo está guardado en MongoDB Atlas. Revisa la conexión de la tienda e inténtalo otra vez.",
            ), 503
        demo_mode = True

    product_url = public_url_for("public_product_ficha", product_id=product_id)
    qr_url = url_for("qr_image", kind="ficha", identifier=product_id)
    return render_template(
        "public_product.html", product=product, product_url=product_url,
        qr_url=qr_url, demo_mode=demo_mode,
    )


@app.get("/reserva/<reservation_id>")
def public_reservation(reservation_id):
    """Public reservation receipt. It exposes status and product details, never customer PII."""
    if not re.fullmatch(r"[a-fA-F0-9]{32}", reservation_id):
        abort(404)
    try:
        db = get_db()
        ensure_reservation_indexes(db)
        expire_reservation(db, reservation_id)
        reservation_doc = db.reservations.find_one({"reservation_id": reservation_id})
        if not reservation_doc:
            abort(404)
        reservation = reservation_view(db, reservation_doc)
        labels = {"temporal": "Temporal", "confirmada": "Confirmada", "cancelada": "Cancelada", "vencida": "Vencida", "active": "Temporal", "confirmed": "Confirmada", "cancelled": "Cancelada", "expired": "Vencida"}
        reservation["status_label"] = labels.get(reservation.get("status"), "No disponible")
        reservation["qr_url"] = url_for("qr_image", kind="reserva", identifier=reservation_id)
        reservation["public_url"] = public_url_for("public_reservation", reservation_id=reservation_id)
        return render_template("public_reservation.html", reservation=reservation)
    except (RuntimeError, PyMongoError):
        app.logger.exception("No se pudo consultar la ficha pública de la reserva")
        return render_template(
            "public_qr_error.html",
            title="No pudimos consultar tu apartado",
            message="Conecta MongoDB Atlas para consultar el estado real de la reserva. El QR está bien generado, pero los datos del apartado se guardan en la base de datos.",
        ), 503


@app.get("/pedido/<order_number>")
def public_order(order_number):
    """Public, minimal order receipt that can be opened from a QR."""
    try:
        order = get_db().orders.find_one({"number": order_number})
        if not order:
            abort(404)
        public_order_data = {
            "number": order.get("number", order_number),
            "status": order.get("status", "received"),
            "payment_status": order.get("payment_status", "unpaid"),
            "items": order.get("items", []),
            "total": float(order.get("total", 0)),
            "created_at": order.get("created_at").isoformat() if hasattr(order.get("created_at"), "isoformat") else "",
        }
        status_labels = {"received": "Recibido", "processing": "Preparando", "shipped": "Enviado", "delivered": "Entregado", "cancelled": "Cancelado", "pending_payment": "Pago pendiente"}
        public_order_data["status_label"] = status_labels.get(public_order_data["status"], public_order_data["status"])
        public_order_data["url"] = public_url_for("public_order", order_number=order_number)
        public_order_data["qr_url"] = url_for("qr_image", kind="pedido", identifier=order_number)
        return render_template("public_order.html", order=public_order_data)
    except (RuntimeError, PyMongoError):
        app.logger.exception("No se pudo abrir el comprobante público")
        return render_template(
            "public_qr_error.html",
            title="No pudimos abrir el comprobante",
            message="El comprobante y su estado se consultan en MongoDB Atlas. Revisa la conexión de la tienda e inténtalo de nuevo.",
        ), 503


@app.get("/qr/<kind>/<identifier>")
def qr_image(kind, identifier):
    """Render a QR without a database round-trip; its destination reads current Atlas data."""
    if kind == "ficha" and ObjectId.is_valid(identifier):
        target_url = public_url_for("public_product_ficha", product_id=identifier)
    elif kind == "reserva" and re.fullmatch(r"[a-fA-F0-9]{32}", identifier):
        target_url = public_url_for("public_reservation", reservation_id=identifier)
    elif kind == "pedido" and re.fullmatch(r"[A-Za-z0-9-]{4,80}", identifier):
        target_url = public_url_for("public_order", order_number=identifier)
    else:
        abort(404)

    try:
        return send_file(
            qr_png_bytes(target_url), mimetype="image/png",
            download_name="vesta-qr.png", max_age=0,
        )
    except Exception:
        app.logger.exception("No se pudo renderizar la imagen del código QR")
        abort(500, description="No se pudo generar el código QR. Inténtalo de nuevo.")


@app.get("/checkout")
def checkout():
    if not MONGODB_URI:
        flash("Configura MongoDB Atlas en .env antes de realizar pedidos.", "error")
    return render_template("checkout.html")


@app.post("/api/checkout")
def api_checkout():
    data = request.get_json(silent=True) or {}
    customer = data.get("customer") or {}
    payment_method = str(data.get("payment_method", "cod")).lower()
    reservation_id = str(data.get("reservation_id", ""))
    required = {"name": "Nombre", "email": "Correo", "phone": "Teléfono", "address": "Dirección", "city": "Ciudad"}
    missing = [label for key, label in required.items() if not str(customer.get(key, "")).strip()]
    if missing:
        return jsonify({"error": "Completa los campos: " + ", ".join(missing)}), 400
    if "@" not in str(customer.get("email", "")):
        return jsonify({"error": "Escribe un correo electrónico válido."}), 400
    if payment_method not in ("cod", "card"):
        return jsonify({"error": "Método de pago no válido."}), 400
    if payment_method == "card" and not STRIPE_SECRET_KEY:
        return jsonify({"error": "El pago con tarjeta aún no está configurado. Configura STRIPE_SECRET_KEY en Render o elige pago al recibir."}), 400

    reserved_checkout = bool(reservation_id)
    if reserved_checkout and reservation_id != session.get("reservation_id"):
        return jsonify({"error": "No encontramos tu apartado en esta sesión. Vuelve a reservar el artículo."}), 409

    clean_items = []
    try:
        if reserved_checkout:
            db = get_db()
            expire_due_reservations(db)
            reservation = db.reservations.find_one({"reservation_id": reservation_id, "status": "temporal", "expires_at": {"$gt": utcnow()}})
            if not reservation:
                session.pop("reservation_id", None)
                return jsonify({"error": "Tu apartado venció. Vuelve a reservar la prenda para continuar."}), 409
            for item in reservation.get("items", []):
                clean_items.append({"product_id": str(item["product_id"]), "quantity": int(item["quantity"]), "size": str(item.get("size", "Única"))[:40], "color": str(item.get("color", "Único"))[:40], "product_type": "exclusive"})
        else:
            raw_items = data.get("items") or []
            if not isinstance(raw_items, list) or not raw_items:
                return jsonify({"error": "Tu bolsa está vacía."}), 400
            for raw in raw_items[:40]:
                product_id = str(raw.get("product_id", ""))
                if not ObjectId.is_valid(product_id):
                    return jsonify({"error": "Hay un producto inválido en el carrito. Vacía el carrito y vuelve a intentarlo."}), 400
                quantity = int(raw.get("quantity", 1))
                if quantity < 1 or quantity > 20:
                    return jsonify({"error": "La cantidad por producto debe estar entre 1 y 20."}), 400
                clean_items.append({"product_id": product_id, "quantity": quantity, "size": str(raw.get("size", "Única"))[:40], "color": str(raw.get("color", "Único"))[:40]})
    except (TypeError, ValueError):
        return jsonify({"error": "La cantidad de un producto no es válida."}), 400

    try:
        db = get_db()
        product_ids = [ObjectId(item["product_id"]) for item in clean_items]
        product_docs = {str(product["_id"]): product for product in db.products.find({"_id": {"$in": product_ids}, "active": True})}
        if len(product_docs) != len(set(item["product_id"] for item in clean_items)):
            return jsonify({"error": "Un producto ya no está disponible. Actualiza el apartado o la bolsa."}), 409
        detail_items = []
        subtotal = 0
        for item in clean_items:
            product = product_docs[item["product_id"]]
            actual_type = product.get("product_type", "regular")
            if reserved_checkout and actual_type != "exclusive":
                return jsonify({"error": "El apartado solo puede contener prendas de Ediciones exclusivas."}), 409
            if not reserved_checkout and actual_type == "exclusive":
                return jsonify({"error": "Esta edición exclusiva requiere un apartado de 5 minutos. Regresa a la sección de exclusivas."}), 409
            if item["size"] not in product.get("sizes", ["Única"]):
                return jsonify({"error": f"La talla elegida para {product['name']} ya no está disponible."}), 409
            if item["color"] not in product.get("colors", ["Único"]):
                return jsonify({"error": f"El color elegido para {product['name']} ya no está disponible."}), 409
            price = float(product.get("price", 0))
            line_total = round(price * item["quantity"], 2)
            subtotal += line_total
            detail_items.append({"product_id": item["product_id"], "name": product["name"], "image": product.get("image", ""), "price": price, "quantity": item["quantity"], "size": item["size"], "color": item["color"], "product_type": actual_type, "line_total": line_total})
        subtotal = round(subtotal, 2)
        shipping = 0 if subtotal >= 1500 else 99
        total = round(subtotal + shipping, 2)
        now = utcnow()
        order = {
            "_id": ObjectId(),
            "number": f"VST-{now.strftime('%y%m%d')}-{str(ObjectId())[-6:].upper()}",
            "customer": {key: str(customer.get(key, "")).strip()[:200] for key in required.keys()} | {"postal_code": str(customer.get("postal_code", "")).strip()[:30], "notes": str(customer.get("notes", "")).strip()[:500]},
            "customer_account_id": session.get("customer_id") if ObjectId.is_valid(str(session.get("customer_id", ""))) else None,
            "items": detail_items,
            "subtotal": subtotal,
            "shipping": shipping,
            "total": total,
            "currency": CURRENCY,
            "payment_method": payment_method,
            "payment_status": "unpaid" if payment_method == "cod" else "pending",
            "status": "received" if payment_method == "cod" else "pending_payment",
            "stock_released": False,
            "created_at": now,
            "updated_at": now,
        }
        if reserved_checkout:
            try:
                inserted_id, stock_items = confirm_reservation_and_insert_order(db, reservation_id, order)
            except ValueError as exc:
                return jsonify({"error": str(exc)}), 409
            session.pop("reservation_id", None)
        else:
            stock_items = reserve_stock(db, clean_items)
            if stock_items is None:
                return jsonify({"error": "No hay suficiente inventario para uno de los artículos. Revisa las cantidades."}), 409
            order["stock_items"] = stock_items
            try:
                db.orders.insert_one(order)
                inserted_id = order["_id"]
            except Exception:
                release_stock(db, stock_items)
                raise

        if payment_method == "card":
            try:
                import stripe
                stripe.api_key = STRIPE_SECRET_KEY
                line_items = []
                for item in detail_items:
                    line_items.append({"price_data": {"currency": CURRENCY, "product_data": {"name": item["name"], "description": f"Talla: {item['size']} · Color: {item['color']}"}, "unit_amount": int(round(item["price"] * 100))}, "quantity": item["quantity"]})
                if shipping > 0:
                    line_items.append({"price_data": {"currency": CURRENCY, "product_data": {"name": "Envío"}, "unit_amount": int(round(shipping * 100))}, "quantity": 1})
                checkout_session = stripe.checkout.Session.create(
                    mode="payment", payment_method_types=["card"], line_items=line_items,
                    success_url=url_for("checkout_success", _external=True) + "?session_id={CHECKOUT_SESSION_ID}",
                    cancel_url=url_for("checkout_cancel", _external=True) + f"?order_id={inserted_id}",
                    customer_email=customer["email"], metadata={"order_id": str(inserted_id)},
                )
                db.orders.update_one({"_id": inserted_id}, {"$set": {"stripe_session_id": checkout_session.id}})
                return jsonify({"redirect_url": checkout_session.url, "order_number": order["number"]})
            except Exception:
                release_stock(db, stock_items)
                db.orders.update_one({"_id": inserted_id}, {"$set": {"status": "cancelled", "stock_released": True, "updated_at": utcnow()}})
                app.logger.exception("No se pudo iniciar checkout de Stripe")
                return jsonify({"error": "No pudimos iniciar el pago con tarjeta. Revisa la configuración de Stripe o elige pago al recibir."}), 502
        return jsonify({"ok": True, "order_number": order["number"], "redirect_url": url_for("order_success", order_number=order["number"])})
    except (RuntimeError, PyMongoError) as exc:
        app.logger.exception("No se pudo crear el pedido")
        return jsonify({"error": "No se pudo guardar el pedido. Revisa la conexión con MongoDB Atlas."}), 503
    except Exception:
        app.logger.exception("Error inesperado al crear el pedido")
        return jsonify({"error": "Ocurrió un error al procesar el pedido. Inténtalo de nuevo."}), 500


@app.get("/checkout/success")
def checkout_success():
    session_id = request.args.get("session_id", "")
    if not STRIPE_SECRET_KEY or not session_id:
        return redirect(url_for("index"))
    try:
        import stripe
        stripe.api_key = STRIPE_SECRET_KEY
        checkout_session = stripe.checkout.Session.retrieve(session_id)
        order_id = (checkout_session.metadata or {}).get("order_id")
        if checkout_session.payment_status == "paid" and ObjectId.is_valid(order_id or ""):
            db = get_db()
            db.orders.update_one({"_id": ObjectId(order_id), "status": "pending_payment"}, {"$set": {"status": "received", "payment_status": "paid", "updated_at": utcnow()}})
            order = db.orders.find_one({"_id": ObjectId(order_id)})
            if order:
                order["public_url"] = public_url_for("public_order", order_number=order.get("number"))
                order["qr_url"] = url_for("qr_image", kind="pedido", identifier=order.get("number"))
            return render_template("success.html", order=order, paid=True)
    except Exception:
        app.logger.exception("No se pudo verificar la sesión de pago")
    return render_template("success.html", order=None, paid=False)


@app.get("/checkout/cancel")
def checkout_cancel():
    order_id = request.args.get("order_id", "")
    try:
        if ObjectId.is_valid(order_id):
            db = get_db()
            order = db.orders.find_one({"_id": ObjectId(order_id), "status": "pending_payment", "stock_released": False})
            if order:
                release_stock(db, order.get("stock_items", []))
                db.orders.update_one({"_id": order["_id"]}, {"$set": {"status": "cancelled", "stock_released": True, "updated_at": utcnow()}})
    except Exception:
        app.logger.exception("No se pudo cancelar reserva de inventario")
    flash("El pago se canceló. Puedes volver al carrito e intentarlo otra vez.", "error")
    return redirect(url_for("checkout"))


@app.post("/stripe/webhook")
def stripe_webhook():
    if not STRIPE_SECRET_KEY or not STRIPE_WEBHOOK_SECRET:
        return jsonify({"error": "Webhook no configurado"}), 503
    try:
        import stripe
        payload = request.get_data()
        signature = request.headers.get("Stripe-Signature", "")
        event = stripe.Webhook.construct_event(payload, signature, STRIPE_WEBHOOK_SECRET)
        if event["type"] in ("checkout.session.completed", "checkout.session.expired"):
            session_obj = event["data"]["object"]
            order_id = (session_obj.get("metadata") or {}).get("order_id")
            if ObjectId.is_valid(order_id or ""):
                db = get_db()
                if event["type"] == "checkout.session.completed" and session_obj.get("payment_status") == "paid":
                    db.orders.update_one(
                        {"_id": ObjectId(order_id), "status": "pending_payment"},
                        {"$set": {"status": "received", "payment_status": "paid", "updated_at": utcnow()}},
                    )
                elif event["type"] == "checkout.session.expired":
                    order = db.orders.find_one({"_id": ObjectId(order_id), "status": "pending_payment", "stock_released": False})
                    if order:
                        release_stock(db, order.get("stock_items", []))
                        db.orders.update_one({"_id": order["_id"]}, {"$set": {"status": "cancelled", "stock_released": True, "updated_at": utcnow()}})
        return jsonify({"received": True})
    except Exception as exc:
        app.logger.warning("Webhook de Stripe inválido: %s", exc)
        return jsonify({"error": "Webhook inválido"}), 400


@app.get("/pedido/<order_number>/gracias")
def order_success(order_number):
    try:
        order = get_db().orders.find_one({"number": order_number})
        if not order:
            abort(404)
        order["public_url"] = public_url_for("public_order", order_number=order_number)
        order["qr_url"] = url_for("qr_image", kind="pedido", identifier=order_number)
        return render_template("success.html", order=order, paid=order.get("payment_status") == "paid")
    except (RuntimeError, PyMongoError):
        app.logger.exception("No se pudo consultar el pedido recién creado")
        abort(503)


def customer_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        customer_id = str(session.get("customer_id", ""))
        if not ObjectId.is_valid(customer_id):
            return redirect(url_for("customer_login", next=request.path))
        return fn(*args, **kwargs)
    return wrapper


@app.route("/cuenta/crear", methods=["GET", "POST"])
def customer_register():
    if session.get("customer_id") and ObjectId.is_valid(str(session.get("customer_id"))):
        return redirect(url_for("customer_dashboard"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()[:120]
        email = request.form.get("email", "").strip().lower()[:254]
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if len(name) < 2:
            flash("Escribe tu nombre completo.", "error")
        elif not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
            flash("Escribe un correo electrónico válido.", "error")
        elif len(password) < 8:
            flash("La contraseña debe tener al menos 8 caracteres.", "error")
        elif password != confirm_password:
            flash("Las contraseñas no coinciden.", "error")
        else:
            try:
                db = get_db()
                db.users.create_index("email", unique=True)
                if db.users.find_one({"email": email}, {"_id": 1}):
                    flash("Ya existe una cuenta con ese correo. Inicia sesión.", "error")
                else:
                    user = {
                        "name": name,
                        "email": email,
                        "password_hash": generate_password_hash(password),
                        "created_at": utcnow(),
                    }
                    result = db.users.insert_one(user)
                    session.clear()
                    session["customer_id"] = str(result.inserted_id)
                    session["customer_name"] = name
                    session["customer_email"] = email
                    flash("Tu cuenta se creó correctamente.", "success")
                    return redirect(url_for("customer_dashboard"))
            except DuplicateKeyError:
                flash("Ya existe una cuenta con ese correo. Inicia sesión.", "error")
            except Exception:
                app.logger.exception("No se pudo crear la cuenta del cliente")
                flash("No pudimos crear tu cuenta. Comprueba la conexión con MongoDB Atlas.", "error")

    return render_template("customer_register.html")


@app.route("/cuenta/login", methods=["GET", "POST"])
def customer_login():
    if session.get("customer_id") and ObjectId.is_valid(str(session.get("customer_id"))):
        return redirect(url_for("customer_dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()[:254]
        password = request.form.get("password", "")
        try:
            user = get_db().users.find_one({"email": email})
            if user and check_password_hash(user.get("password_hash", ""), password):
                session.clear()
                session["customer_id"] = str(user["_id"])
                session["customer_name"] = user.get("name", "Cliente")
                session["customer_email"] = user.get("email", email)
                return redirect(url_for("customer_dashboard"))
            flash("Correo o contraseña incorrectos.", "error")
        except Exception:
            app.logger.exception("No se pudo iniciar sesión de cliente")
            flash("No pudimos iniciar sesión. Comprueba la conexión con MongoDB Atlas.", "error")

    return render_template("customer_login.html")


@app.get("/cuenta/salir")
def customer_logout():
    session.pop("customer_id", None)
    session.pop("customer_name", None)
    session.pop("customer_email", None)
    flash("Has cerrado sesión.", "success")
    return redirect(url_for("index"))


@app.get("/cuenta")
@customer_required
def customer_dashboard():
    try:
        db = get_db()
        user = db.users.find_one({"_id": ObjectId(session["customer_id"])}, {"password_hash": 0})
        if not user:
            session.pop("customer_id", None)
            session.pop("customer_name", None)
            session.pop("customer_email", None)
            return redirect(url_for("customer_login"))
        orders = [sanitize_order(o) for o in db.orders.find({"customer_account_id": str(user["_id"])}).sort("created_at", -1).limit(100)]
        db_error = None
    except Exception:
        app.logger.exception("No se pudo cargar la cuenta del cliente")
        user, orders = {"name": session.get("customer_name", "Cliente"), "email": session.get("customer_email", "")}, []
        db_error = "No se pudo cargar tu historial. Comprueba la conexión con MongoDB Atlas."
    return render_template("customer_account.html", user=user, orders=orders, db_error=db_error)


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if session.get("is_admin") and session.get("admin_user") == ADMIN_USERNAME:
        return redirect(url_for("admin_dashboard"))
    if session.get("is_admin") and session.get("admin_user") != ADMIN_USERNAME:
        # Invalidate old admin sessions when the configured username changes.
        session.pop("is_admin", None)
        session.pop("admin_user", None)
    if request.method == "POST":
        if not ADMIN_PASSWORD:
            flash("Falta configurar ADMIN_PASSWORD en .env o en Render.", "error")
        else:
            username = request.form.get("username", "")
            password = request.form.get("password", "")
            if hmac.compare_digest(username, ADMIN_USERNAME) and hmac.compare_digest(password, ADMIN_PASSWORD):
                session.clear()
                session["is_admin"] = True
                session["admin_user"] = ADMIN_USERNAME
                return redirect(url_for("admin_dashboard"))
            flash("Usuario o contraseña incorrectos.", "error")
    return render_template("admin_login.html")


@app.get("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))


@app.get("/admin")
@admin_required
def admin_dashboard():
    db_error = None
    try:
        db = get_db()
        seed_products(db)
        expire_due_reservations(db)
        products = [json_product(p) for p in db.products.find({}).sort("created_at", -1)]
        orders = [sanitize_order(o) for o in db.orders.find({}).sort("created_at", -1).limit(100)]
    except Exception as exc:
        app.logger.exception("No se pudo cargar administración")
        products, orders = [], []
        db_error = "No se pudo conectar con MongoDB. Revisa MONGODB_URI."
    return render_template("admin.html", products=products, orders=orders, db_error=db_error)


@app.get("/api/admin/orders")
@admin_required
def api_admin_orders():
    try:
        orders = [sanitize_order(o) for o in get_db().orders.find({}).sort("created_at", -1).limit(200)]
        return jsonify({"orders": orders})
    except Exception:
        return jsonify({"error": "No se pudieron cargar los pedidos."}), 503


@app.patch("/api/admin/orders/<order_id>")
@admin_required
def api_admin_update_order(order_id):
    if not ObjectId.is_valid(order_id):
        return jsonify({"error": "ID de pedido no válido."}), 400
    data = request.get_json(silent=True) or {}
    status = str(data.get("status", ""))
    allowed = {"received", "processing", "shipped", "delivered", "cancelled"}
    if status not in allowed:
        return jsonify({"error": "Estado de pedido no válido."}), 400
    try:
        db = get_db()
        order = db.orders.find_one({"_id": ObjectId(order_id)})
        if not order:
            return jsonify({"error": "No encontramos ese pedido."}), 404
        if status == "cancelled" and order.get("payment_status") != "paid" and not order.get("stock_released", False):
            release_stock(db, order.get("stock_items", []))
            db.orders.update_one({"_id": order["_id"]}, {"$set": {"stock_released": True}})
        db.orders.update_one({"_id": order["_id"]}, {"$set": {"status": status, "updated_at": utcnow()}})
        return jsonify({"ok": True})
    except Exception:
        app.logger.exception("No se pudo actualizar pedido")
        return jsonify({"error": "No se pudo actualizar el pedido."}), 503


@app.post("/api/admin/products")
@admin_required
def api_admin_create_product():
    data = request.get_json(silent=True) or {}
    payload, errors = valid_product_payload(data)
    if errors:
        return jsonify({"error": " ".join(errors)}), 400
    product_type = payload.get("product_type", "regular")
    if product_type == "exclusive":
        limit = int(payload.pop("exclusive_limit"))
        payload["stock"] = limit
        payload["exclusive_limit"] = limit
        payload["stock_mode"] = "limited"
    else:
        payload.pop("exclusive_limit", None)
    payload.update({"reserved": 0, "created_at": utcnow(), "updated_at": utcnow()})
    try:
        result = get_db().products.insert_one(payload)
        payload["_id"] = result.inserted_id
        return jsonify({"ok": True, "product": json_product(payload)}), 201
    except Exception:
        app.logger.exception("No se pudo crear producto")
        return jsonify({"error": "No se pudo guardar el producto."}), 503


@app.patch("/api/admin/products/<product_id>")
@admin_required
def api_admin_update_product(product_id):
    if not ObjectId.is_valid(product_id):
        return jsonify({"error": "ID de producto no válido."}), 400
    data = request.get_json(silent=True) or {}
    payload, errors = valid_product_payload(data, partial=True)
    if errors:
        return jsonify({"error": " ".join(errors)}), 400
    if not payload:
        return jsonify({"error": "No hay campos que actualizar."}), 400
    payload["updated_at"] = utcnow()
    try:
        db = get_db()
        product_oid = ObjectId(product_id)
        current = db.products.find_one({"_id": product_oid})
        if not current:
            return jsonify({"error": "No encontramos ese producto."}), 404
        expire_due_reservations(db)
        current = db.products.find_one({"_id": product_oid}) or current
        reserved_count = int(current.get("reserved", 0))
        current_type = current.get("product_type", "regular")
        next_type = payload.get("product_type", current_type)
        current_mode = current.get("stock_mode", "limited")
        next_mode = payload.get("stock_mode", current_mode)
        has_active_holds = db.reservations.count_documents({"status": "temporal", "items.product_id": product_id}) > 0
        if (reserved_count or has_active_holds) and (next_type != current_type or next_mode != current_mode):
            return jsonify({"error": "No puedes cambiar el tipo de publicación o inventario mientras haya apartados activos. Espera a que se confirmen, cancelen o venzan."}), 409

        if next_type == "exclusive":
            requested_limit = payload.pop("exclusive_limit", None)
            current_limit = int(current.get("exclusive_limit", current.get("stock", 0)))
            if requested_limit is None:
                requested_limit = current_limit if current_type == "exclusive" else int(current.get("stock", 0))
            sold = max(current_limit - int(current.get("stock", 0)), 0) if current_type == "exclusive" else 0
            if int(requested_limit) < sold + reserved_count:
                return jsonify({"error": f"El cupo no puede ser menor que las {sold} unidades compradas y {reserved_count} apartadas."}), 409
            payload["product_type"] = "exclusive"
            payload["stock_mode"] = "limited"
            payload["exclusive_limit"] = int(requested_limit)
            payload["stock"] = int(requested_limit) - sold
        elif next_type == "regular":
            payload.pop("exclusive_limit", None)
            payload["product_type"] = "regular"
            if next_mode == "infinite":
                payload["stock_mode"] = "infinite"
                payload["stock"] = 0
            elif "stock" in payload and payload["stock"] < 1:
                return jsonify({"error": "Las existencias deben ser mayores que cero."}), 400
            elif "stock" in payload and payload["stock"] < reserved_count:
                return jsonify({"error": f"Las existencias no pueden ser menores a las {reserved_count} unidades que siguen apartadas."}), 409
        update_document = {"$set": payload}
        if next_type == "regular":
            update_document["$unset"] = {"exclusive_limit": ""}
        result = db.products.update_one({"_id": product_oid}, update_document)
        if not result.matched_count:
            return jsonify({"error": "No encontramos ese producto."}), 404
        return jsonify({"ok": True})
    except Exception:
        app.logger.exception("No se pudo actualizar producto")
        return jsonify({"error": "No se pudo actualizar el producto."}), 503


@app.delete("/api/admin/products/<product_id>")
@admin_required
def api_admin_delete_product(product_id):
    if not ObjectId.is_valid(product_id):
        return jsonify({"error": "ID de producto no válido."}), 400
    try:
        db = get_db()
        expire_due_reservations(db)
        product = db.products.find_one({"_id": ObjectId(product_id)})
        if not product:
            return jsonify({"error": "No encontramos ese producto."}), 404
        if int(product.get("reserved", 0)) > 0 or db.reservations.count_documents({"status": "temporal", "items.product_id": product_id}) > 0:
            return jsonify({"error": "No puedes quitar una prenda mientras tenga apartados activos. Cancélalos o espera a que venzan."}), 409
        result = db.products.update_one({"_id": ObjectId(product_id)}, {"$set": {"active": False, "updated_at": utcnow()}})
        if not result.matched_count:
            return jsonify({"error": "No encontramos ese producto."}), 404
        return jsonify({"ok": True})
    except Exception:
        app.logger.exception("No se pudo desactivar producto")
        return jsonify({"error": "No se pudo eliminar el producto."}), 503


@app.errorhandler(413)
def too_large(_error):
    return jsonify({"error": "La solicitud es demasiado grande."}), 413


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=os.getenv("FLASK_DEBUG", "false").lower() == "true")
