# Cambios de VESTA: recibo QR, inicio de sesión y carga

- El comprobante público `/pedido/FOLIO` ahora itera `order.get("items", [])`; Jinja ya no interpreta `order.items` como el método del diccionario.
- El comprobante expone `url` y `public_url` con la ruta pública, y el enlace de la tarjeta QR abre esa ficha.
- `/checkout` redirige a iniciar sesión cuando no hay cuenta activa. `POST /api/checkout` valida también la sesión y devuelve HTTP 401 sin crear pedido cuando falta.
- Login y registro aceptan una ruta interna `next`, regresan al checkout y conservan el carrito local y los datos de un apartado temporal vigente. Los redirects externos se rechazan.
- Las vistas públicas de producto y la tienda tienen una caché privada corta para mejorar Back/Forward. Al restaurar la tienda se refresca la disponibilidad en segundo plano.
- La migración/siembra de catálogo y los índices de reservas se ejecutan una vez por worker. Las muestras toleran la inserción concurrente entre workers.

## Verificación local realizada

- `python -m py_compile app.py`
- `node --check static/checkout.js`
- `node --check static/store.js`
- Las 13 plantillas HTML compilan con Jinja2.
- Renderizados de prueba de `public_order.html` y `public_reservation.html` con artículos de ejemplo.

No se pudo probar una compra real contra MongoDB Atlas ni desplegar a Render desde este entorno.
