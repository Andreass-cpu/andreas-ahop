# VESTA — tienda de moda con Python + MongoDB Atlas

Proyecto de tienda online en **Python (Flask) + MongoDB Atlas**, con catálogo, búsqueda y filtros, carrito en el navegador, selección de talla/color, proceso de compra, administración de productos e inventario, y gestión de pedidos. Está organizado para publicarlo en **GitHub** y desplegarlo en **Render**.

> La marca, fotos y productos de ejemplo son provisionales. Este repositorio no está conectado a tus cuentas ni publicado en Internet automáticamente.

## Lo que incluye

- Catálogo responsive separado en dos secciones: **Ropa normal** (compra directa desde la bolsa) y **Ediciones exclusivas** (cupo máximo y apartado temporal de 5 minutos). El catálogo de demostración incluye prendas normales y cuatro ediciones exclusivas originales de VESTA.
- El catálogo de muestra también se ve cuando MongoDB Atlas todavía no está configurado; para registrar pedidos e inventario sí debes conectar Atlas.
- Si alguna fotografía remota no carga, aparece una imagen local de respaldo.
- Carrito persistente en el navegador y formulario de entrega.
- **Inicio de sesión obligatorio para comprar:** `/checkout` redirige a iniciar sesión o crear cuenta; `POST /api/checkout` también bloquea pedidos sin sesión válida. Después del acceso vuelve al checkout y conserva el carrito y un apartado temporal activo.
- Pedidos guardados en MongoDB Atlas. El servidor vuelve a calcular precios y valida tallas, colores y existencias; no confía en los precios enviados por el navegador.
- Apartados temporales de productos durante 5 minutos, con identificador de visitante, contador, consulta, cancelación, caducidad y confirmación al crear el pedido. El historial de reservas conserva los estados temporal/confirmada/cancelada/vencida en Atlas.
- Código QR real en PNG para la ficha pública de cada producto, el estado público de cada apartado y el comprobante de cada pedido.
- La imagen PNG del QR se genera sin consultar Atlas; al abrir el enlace escaneado, las fichas de apartados y pedidos consultan MongoDB Atlas para mostrar datos reales. Las fichas de productos de demostración pueden abrirse sin Atlas y se identifican como demostración.
- Las páginas públicas de QR usan el logotipo gráfico VESTA en SVG, colocado en la esquina superior de la tarjeta del código.
- Los QR abren páginas de VESTA publicadas en Render; las fichas se consultan de nuevo en Atlas para mostrar disponibilidad y estado actualizados. El comprobante público no expone domicilio, teléfono ni correo.
- Ropa normal: compra directa desde la bolsa, con inventario limitado o ilimitado configurable. Ediciones exclusivas: apartado temporal con un cupo máximo de compradores/unidades definido por el administrador.
- Las ediciones exclusivas usan `exclusive_limit`, `stock` y `reserved`; Atlas valida la disponibilidad de forma atómica para evitar que dos visitantes aparten el mismo último cupo. Cada visitante puede apartar una unidad de cada exclusiva.
- Panel privado `/admin` para crear, editar, quitar temporalmente y reactivar productos, revisar compras completas (artículos, cantidades, datos de entrega y pago) y cambiar el estado de los pedidos.
- Los productos e inventario se insertan/actualizan en `products`; los apartados temporales se guardan en `reservations`; los pedidos se guardan en `orders` de MongoDB Atlas.
- Interruptor de modo oscuro/claro para toda la tienda y el panel, con preferencia guardada en el navegador.
- Pago al recibir habilitado por defecto.
- Pago con tarjeta opcional mediante Stripe Checkout; necesita configurar las claves de Stripe y un webhook para liberar inventario si la sesión de pago caduca.
- Endpoint `/health`, configuración para Render y variables secretas fuera del repositorio.
- Volver atrás/adelante reutiliza brevemente el catálogo público desde caché privada; las existencias se refrescan en segundo plano al volver a la tienda y las operaciones siempre se validan en Atlas.
- Migración/siembra del catálogo e índices de reservas se ejecutan una vez por worker, no en cada navegación, reduciendo operaciones de base de datos al volver a la página principal.

## Archivos clave

```text
vesta-fashion-python/
├── app.py                 # Aplicación Python / rutas / conexión a MongoDB
├── iniciar_vesta.bat      # Instala dependencias y arranca la app en Windows
├── requirements.txt       # Dependencias de Python
├── render.yaml            # Configuración de despliegue en Render
├── .env.example           # Plantilla de variables (sin claves reales)
├── .gitignore             # Evita subir .env, entornos virtuales y caché
├── templates/             # Páginas HTML/Jinja
└── static/                # CSS y JavaScript del escaparate y panel
```

## 1. Crear/configurar MongoDB Atlas

1. Entra a [MongoDB Atlas](https://cloud.mongodb.com/) y abre tu proyecto.
2. En **Database Access**, crea un usuario de base de datos con contraseña. Es independiente de la contraseña para iniciar sesión en Atlas.
3. En **Network Access**, autoriza la conexión de la aplicación. Para producción, limita el acceso a las direcciones salientes que Render te indique, cuando estén disponibles. `0.0.0.0/0` permite intentos de conexión desde cualquier IP: úsalo solo como solución temporal de prueba y con una contraseña robusta.
4. En **Database → Connect → Drivers**, copia la URI de Python. Sustituye el nombre de usuario/contraseña por las credenciales del usuario de base de datos. Si la contraseña contiene caracteres especiales, codifícala para URL.
5. La base de datos `vesta_fashion` y la colección de productos se crearán al usar la app. Si `products` está vacía, se insertan datos de demostración.

La aplicación necesita una URI similar a esta; **no uses literalmente el ejemplo**:

```text
mongodb+srv://USUARIO:CONTRASENA@TU-CLUSTER.mongodb.net/?retryWrites=true&w=majority
```

## 2. Ejecutar en tu computadora

Necesitas Python 3.10 o posterior.

### Windows (PowerShell)

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Abre `.env` y completa al menos estas variables:

```dotenv
MONGODB_URI=mongodb+srv://USUARIO:CONTRASENA@TU-CLUSTER.mongodb.net/?retryWrites=true&w=majority
MONGO_DB_NAME=vesta_fashion
SECRET_KEY=una-clave-larga-aleatoria-y-privada
ADMIN_USERNAME=vesta
ADMIN_PASSWORD=4
STORE_NAME=VESTA
CURRENCY=mxn
COOKIE_SECURE=false
APP_BASE_URL=https://andreas-ahop.onrender.com
```

Después ejecuta:

```powershell
py app.py
```

También puedes hacer doble clic en `iniciar_vesta.bat`; instalará las dependencias del proyecto e intentará iniciar la tienda.

Abre `http://127.0.0.1:5000`. En la cabecera de la tienda encontrarás **Mi cuenta** y **Administración**. El cliente puede crear una cuenta en `/cuenta/crear`, entrar en `/cuenta/login` y revisar sus pedidos en `/cuenta`. La cuenta de cliente no tiene permisos para editar la tienda. Para entrar al panel de administración usa `http://127.0.0.1:5000/admin/login`.

> No subas `.env` a GitHub. `.gitignore` ya lo excluye. No compartas tu URI de Atlas ni tu contraseña real en capturas o chats.

## 3. Subir a GitHub

Crea un repositorio vacío en [GitHub](https://github.com/). Desde la carpeta del proyecto ejecuta:

```bash
git init
git add .
git commit -m "Crear tienda VESTA con Flask y MongoDB"
git branch -M main
git remote add origin https://github.com/TU-USUARIO/TU-REPOSITORIO.git
git push -u origin main
```

Sustituye la URL de ejemplo por la URL de tu repositorio. Antes de hacer `git add .`, comprueba que `.env` no esté entre los archivos pendientes: `git status`.

## 4. Publicar en Render

1. Entra a [Render](https://render.com/) y elige **New → Blueprint** (o crea un Web Service conectado al repositorio).
2. Selecciona tu repositorio de GitHub. Render detectará `render.yaml`.
3. En **Environment**, define `MONGODB_URI` con la URI de Atlas, `ADMIN_USERNAME` como `vesta`, `ADMIN_PASSWORD` como `4` para usar las credenciales iniciales solicitadas y `APP_BASE_URL` como `https://andreas-ahop.onrender.com` (ajusta el dominio si tu servicio usa otro). La contraseña `4` es extremadamente débil para una tienda pública: cualquier persona podría intentar entrar y ver nombres, teléfonos, direcciones y pedidos. Cámbiala por una contraseña larga antes de aceptar compras reales. `SECRET_KEY` se genera con Render. No pongas las claves en archivos del repositorio.
4. Revisa que el nombre de la base de datos sea `vesta_fashion`. Pulsa crear/desplegar.
5. Cuando termine el despliegue, abre el dominio `onrender.com` de tu servicio. Comprueba `/health`; debería responder `{"status":"ok","database":"connected"}`.
6. Para administrar la tienda, entra en `https://TU-SERVICIO.onrender.com/admin/login` con el usuario configurado (`vesta`) y `ADMIN_PASSWORD`. El usuario y la contraseña configurados en Render tienen prioridad sobre los valores de ejemplo. El panel muestra datos privados de los compradores; protege las credenciales.

Si la comprobación `/health` falla, revisa `MONGODB_URI`, la contraseña del usuario de base de datos y **Network Access** en Atlas, además de los logs del servicio en Render.

## 5. Ropa normal y ediciones exclusivas

La primera carga del catálogo incluye cuatro ejemplos de exclusivas VESTA: Camisa Heritage Verde, Hoodie Street Noir, Chaqueta Biker Eclipse y Blazer Atelier Noire. Son diseños de muestra con estética de lujo/streetwear, no mercancía oficial de Gucci, VLONE ni de otras marcas. Puedes cambiar sus nombres, fotos, precios, tallas y cupos desde Administración; las muestras solo se insertan si todavía no existe un producto con el mismo nombre.


Al crear o editar un producto desde `/admin`, primero elige dónde aparecerá:

- **Ropa normal:** se muestra en la sección Ropa normal y se compra directamente agregándola a la bolsa. Puede usar existencias limitadas o inventario ilimitado. El servidor valida y descuenta las existencias limitadas al generar el pedido.
- **Edición exclusiva:** se muestra en una sección aparte. Al crearla, el administrador establece el **cupo máximo de compradores**. Cada visitante puede apartar una unidad de esa edición. El apartado bloquea un cupo durante cinco minutos; no se puede confirmar después de vencer.

Los apartados exclusivos usan el modelo de cantidad descrito en la actividad: `stock` guarda las unidades todavía no vendidas, `reserved` las unidades apartadas y `exclusive_limit` el cupo máximo original. La disponibilidad se calcula como `stock - reserved`. MongoDB Atlas actualiza `reserved` solamente cuando todavía hay cupo disponible, así que dos visitantes distintos no pueden quedarse con la última unidad. El identificador `reservation_id`, `visitante_id`, producto, cantidad, el estado (`temporal`, `confirmada`, `cancelada` o `vencida`) y las fechas UTC se guardan en la colección `reservations`.

El visitante puede consultar su apartado, ver el contador, cancelar o confirmar. Al cancelar o vencer, Atlas libera el cupo una sola vez y conserva el documento con estado `cancelada` o `vencida`; al confirmar, se descuenta el stock, se crea el pedido y la reserva cambia a `confirmada`. El contador solo informa: el servidor comprueba la fecha real de vencimiento al confirmar. Las operaciones de reservar, liberar y confirmar usan transacciones de MongoDB Atlas.

## 6. Código QR y fichas públicas

- Cada tarjeta de producto tiene un acceso compacto con icono QR en la esquina superior de la foto. Abre `/ficha/ID`, una página pública que vuelve a consultar Atlas y muestra la disponibilidad actual. La propia ficha muestra su QR.
- Cada apartado tiene una ficha pública `/reserva/FOLIO`. El QR sigue funcionando después de confirmar, cancelar o vencer porque los estados terminales se conservan en la colección `reservations`.
- Cada compra tiene un comprobante público `/pedido/FOLIO` con su resumen, total y estado actual. El QR del comprobante no incluye datos de entrega, correo ni teléfono del comprador. La plantilla accede a la lista con `order.get('items', [])` para evitar el choque de Jinja con el método `dict.items`.
- `/qr/ficha/ID`, `/qr/reserva/FOLIO` y `/qr/pedido/FOLIO` entregan las imágenes PNG QR. Los códigos codifican las URLs públicas, no localhost.
- Configura `APP_BASE_URL=https://andreas-ahop.onrender.com` en Render. Si cambia el dominio del servicio, actualiza ese valor y vuelve a desplegar.

Las imágenes QR se generan en el servidor con la dependencia `qrcode[pil]`; no dependen de un generador externo.

Para probarlo, crea una edición exclusiva con cupo 1, abre la tienda en dos navegadores (uno normal y otro incógnito) y trata de apartar desde ambos. Solo uno debe conseguir el cupo. Después prueba cancelar, esperar cinco minutos y confirmar una compra.

### Pruebas finales del QR y la reserva

1. Usuario A aparta una exclusiva disponible: Atlas guarda el apartado y el contador se muestra.
2. Usuario B intenta apartar la misma última unidad: VESTA rechaza la operación.
3. A cancela: el cupo vuelve a estar disponible.
4. A aparta y deja vencer los cinco minutos: Atlas cambia el estado a `vencida` y libera el cupo.
5. A confirma antes del vencimiento: el pedido se crea y la reserva queda `confirmada`.
6. Recargar la tienda conserva el estado porque está guardado en Atlas.
7. Escanear el QR de la ficha o comprobante abre la dirección pública de Render.
8. Cambiar el estado y escanear el mismo QR vuelve a mostrar la información actualizada.
9. Un ID inexistente muestra un error 404 controlado.
10. Probar desde otro equipo confirma que no se utilizan URLs `localhost`.

## 7. Pago con tarjeta (opcional)

Los pedidos con pago al recibir funcionan sin Stripe. Para activar pagos con tarjeta:

1. Crea una cuenta de Stripe y usa las claves de prueba durante las pruebas.
2. En Render, configura `STRIPE_SECRET_KEY` con la clave secreta de prueba o producción.
3. Registra un webhook de Stripe hacia `https://TU-SERVICIO.onrender.com/stripe/webhook` para el evento `checkout.session.expired` y añade su secreto a `STRIPE_WEBHOOK_SECRET`.
4. Prueba el flujo completo en modo de prueba antes de aceptar pagos reales y configura las políticas de cambios/devoluciones y atención al cliente.

No habilites pagos reales hasta confirmar las URLs, claves y webhooks del entorno de producción.

## Rutas útiles

- `/` — tienda
- `/checkout` — finalizar compra
- `/cuenta/crear` — registro de cuenta de cliente (contraseña almacenada como hash en Atlas)
- `/cuenta/login` — inicio de sesión del cliente
- `/cuenta` — historial de pedidos realizados con la sesión iniciada
- `/admin/login` — inicio de sesión de administración (solo credenciales definidas en Render)
- `/admin` — panel privado: productos, inventario, compras y estados (requiere sesión administrativa)
- `static/theme.js` y `static/dark-mode.css` — modo oscuro/claro en la tienda y en el panel
- `/health` — estado de MongoDB
- `/api/products` — catálogo JSON
- `/api/reservations` — crear un apartado temporal (requiere sesión de visitante)
- `/api/reservations/current` — consultar el apartado y su vencimiento
- `/api/reservations/cancel` — cancelar y liberar un apartado
- `/ficha/ID` — ficha pública y QR de un producto
- `/reserva/FOLIO` — estado público de un apartado y su QR
- `/pedido/FOLIO` — comprobante público de pedido y su QR
- `/qr/ficha/ID`, `/qr/reserva/FOLIO`, `/qr/pedido/FOLIO` — imágenes PNG de los códigos QR
- `/stripe/webhook` — webhook opcional de Stripe

## Nota antes de vender

Esta es una base funcional para personalizar, no una plataforma auditada para operar sin revisión. Antes del lanzamiento, prueba pedidos y pagos en un entorno de prueba, configura políticas legales/fiscales y de privacidad, añade monitoreo/respaldos de Atlas y verifica el manejo de cancelaciones y reembolsos según tu operación.

## Cuentas de clientes y permisos

La tienda tiene enlaces visibles a **Mi cuenta** y **Administración**. Los compradores pueden crear cuentas en `/cuenta/crear`; se guarda su correo y un hash de contraseña en la colección `users`. Comprar requiere iniciar sesión: tanto la página de checkout como el endpoint que crea el pedido verifican la sesión en el servidor. Después del acceso se regresa al checkout y el pedido incluye el identificador de la cuenta para que aparezca en su historial.

El registro público solo crea cuentas de cliente. Nunca crea administradores. La administración se autentica exclusivamente con `ADMIN_USERNAME` y `ADMIN_PASSWORD` establecidos en las variables de entorno; las rutas que crean, editan o desactivan productos y cambian pedidos requieren una sesión de administrador. Mantén `ADMIN_PASSWORD` fuerte: `4` solo sirve como configuración inicial de prueba y no es segura para producción. Cambia la contraseña antes de aceptar compras reales.
