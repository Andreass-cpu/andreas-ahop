import hashlib
import hmac
import os
import re
from datetime import datetime, timezone
from functools import wraps

from bson import ObjectId
from dotenv import load_dotenv
from flask import Flask, abort, flash, jsonify, redirect, render_template, request, session, url_for
from pymongo import MongoClient, ReturnDocument
from pymongo.errors import DuplicateKeyError, PyMongoError
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
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "andreas")
# Keep the password in Render Environment / local .env; never bake it into public source.
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "").strip()
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "").strip()
STORE_NAME = os.getenv("STORE_NAME", "VESTA")
CURRENCY = os.getenv("CURRENCY", "mxn").lower()

mongo_client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000) if MONGODB_URI else None

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
    """Show the sample catalog even before Atlas credentials are configured."""
    now = utcnow()
    return [json_product({**p, "_id": sample_product_id(p["name"]), "active": True, "created_at": now, "updated_at": now}) for p in SEED_PRODUCTS]


def seed_products(db):
    # Add missing examples even if this database already has a few products.
    # Existing products and their IDs are never overwritten.
    now = utcnow()
    for product in SEED_PRODUCTS:
        if db.products.find_one({"name": product["name"]}, {"_id": 1}):
            continue
        sample_id = sample_product_id(product["name"])
        if db.products.find_one({"_id": sample_id}, {"_id": 1}):
            continue
        db.products.insert_one({**product, "_id": sample_id, "active": True, "created_at": now, "updated_at": now})


def json_product(doc):
    return {
        "id": str(doc["_id"]),
        "name": doc.get("name", "Producto"),
        "category": doc.get("category", "Otros"),
        "description": doc.get("description", ""),
        "price": float(doc.get("price", 0)),
        "sizes": doc.get("sizes", ["Única"]),
        "colors": doc.get("colors", ["Único"]),
        "image": doc.get("image", ""),
        "stock": int(doc.get("stock", 0)),
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
    text_fields = ("name", "category", "description", "image")
    for field in text_fields:
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
    if "stock" in data or not partial:
        try:
            stock = int(data.get("stock", 0))
            if stock < 0 or stock > 10000000:
                raise ValueError
            result["stock"] = stock
        except (ValueError, TypeError):
            errors.append("El inventario debe ser un entero igual o mayor que cero.")
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


def reserve_stock(db, clean_items):
    reserved = []
    for item in clean_items:
        updated = db.products.find_one_and_update(
            {"_id": ObjectId(item["product_id"]), "active": True, "stock": {"$gte": item["quantity"]}},
            {"$inc": {"stock": -item["quantity"]}, "$set": {"updated_at": utcnow()}},
            return_document=ReturnDocument.AFTER,
        )
        if updated is None:
            for previous in reserved:
                db.products.update_one({"_id": ObjectId(previous["product_id"])}, {"$inc": {"stock": previous["quantity"]}})
            return False
        reserved.append(item)
    return True


def release_stock(db, items):
    for item in items:
        try:
            db.products.update_one({"_id": ObjectId(item["product_id"])}, {"$inc": {"stock": int(item["quantity"])}},)
        except Exception:
            app.logger.exception("No se pudo devolver inventario para el pedido")


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
        products = [json_product(doc) for doc in db.products.find({"active": True}).sort("created_at", -1)]
    except (RuntimeError, PyMongoError) as exc:
        app.logger.warning("No se pudo cargar MongoDB: %s", exc)
        error = "No se pudo conectar con MongoDB Atlas. Se muestra el catálogo de ejemplo; configura MONGODB_URI para guardar pedidos e inventario."
        products = fallback_products()
        demo_mode = True
    return render_template("index.html", products=products, db_error=error, demo_mode=demo_mode)


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


@app.get("/checkout")
def checkout():
    if not MONGODB_URI:
        flash("Configura MongoDB Atlas en .env antes de realizar pedidos.", "error")
    return render_template("checkout.html")


@app.post("/api/checkout")
def api_checkout():
    data = request.get_json(silent=True) or {}
    customer = data.get("customer") or {}
    raw_items = data.get("items") or []
    payment_method = str(data.get("payment_method", "cod")).lower()
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
    if not isinstance(raw_items, list) or not raw_items:
        return jsonify({"error": "Tu carrito está vacío."}), 400
    clean_items = []
    try:
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
        product_docs = {str(p["_id"]): p for p in db.products.find({"_id": {"$in": product_ids}, "active": True})}
        if len(product_docs) != len(set(item["product_id"] for item in clean_items)):
            return jsonify({"error": "Un producto ya no está disponible. Actualiza el carrito."}), 409
        detail_items = []
        subtotal = 0
        for item in clean_items:
            product = product_docs[item["product_id"]]
            if item["size"] not in product.get("sizes", ["Única"]):
                return jsonify({"error": f"La talla elegida para {product['name']} ya no está disponible."}), 409
            if item["color"] not in product.get("colors", ["Único"]):
                return jsonify({"error": f"El color elegido para {product['name']} ya no está disponible."}), 409
            price = float(product.get("price", 0))
            line_total = round(price * item["quantity"], 2)
            subtotal += line_total
            detail_items.append({"product_id": item["product_id"], "name": product["name"], "image": product.get("image", ""), "price": price, "quantity": item["quantity"], "size": item["size"], "color": item["color"], "line_total": line_total})
        subtotal = round(subtotal, 2)
        shipping = 0 if subtotal >= 1500 else 99
        total = round(subtotal + shipping, 2)
        if not reserve_stock(db, clean_items):
            return jsonify({"error": "No hay suficiente inventario para uno de los artículos. Revisa las cantidades."}), 409
        now = utcnow()
        order = {
            "number": f"VST-{now.strftime('%y%m%d')}-{str(ObjectId())[-6:].upper()}",
            "customer": {key: str(customer.get(key, "")).strip()[:200] for key in required.keys()} | {"postal_code": str(customer.get("postal_code", "")).strip()[:30], "notes": str(customer.get("notes", "")).strip()[:500]},
            "customer_account_id": session.get("customer_id") if ObjectId.is_valid(str(session.get("customer_id", ""))) else None,
            "items": detail_items,
            "stock_items": clean_items,
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
        try:
            inserted = db.orders.insert_one(order)
            order["_id"] = inserted.inserted_id
        except Exception:
            release_stock(db, clean_items)
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
                    cancel_url=url_for("checkout_cancel", _external=True) + f"?order_id={inserted.inserted_id}",
                    customer_email=customer["email"], metadata={"order_id": str(inserted.inserted_id)},
                )
                db.orders.update_one({"_id": inserted.inserted_id}, {"$set": {"stripe_session_id": checkout_session.id}})
                return jsonify({"redirect_url": checkout_session.url, "order_number": order["number"]})
            except Exception as exc:
                release_stock(db, clean_items)
                db.orders.update_one({"_id": inserted.inserted_id}, {"$set": {"status": "cancelled", "stock_released": True, "updated_at": utcnow()}})
                app.logger.exception("No se pudo iniciar checkout de Stripe")
                return jsonify({"error": "No pudimos iniciar el pago con tarjeta. Revisa la configuración de Stripe o elige pago al recibir."}), 502
        return jsonify({"ok": True, "order_number": order["number"], "redirect_url": url_for("order_success", order_number=order["number"])})
    except (RuntimeError, PyMongoError) as exc:
        app.logger.exception("No se pudo crear el pedido")
        return jsonify({"error": "No se pudo guardar el pedido. Revisa la conexión con MongoDB Atlas."}), 503
    except Exception as exc:
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
    return render_template("success.html", order={"number": order_number}, paid=False)


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
    if session.get("is_admin"):
        return redirect(url_for("admin_dashboard"))
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
    payload.update({"created_at": utcnow(), "updated_at": utcnow()})
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
        result = get_db().products.update_one({"_id": ObjectId(product_id)}, {"$set": payload})
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
        result = get_db().products.update_one({"_id": ObjectId(product_id)}, {"$set": {"active": False, "updated_at": utcnow()}})
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
