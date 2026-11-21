(() => {
  const CART_KEY = 'vesta_cart_v1'; const currency = window.VESTA_CONFIG?.currency || 'MXN';
  const money = value => new Intl.NumberFormat('es-MX', {style:'currency', currency}).format(Number(value || 0));
  const readCart = () => { try { return JSON.parse(localStorage.getItem(CART_KEY) || '[]'); } catch { return []; } };
  const writeCart = cart => localStorage.setItem(CART_KEY, JSON.stringify(cart));
  const itemsEl = document.getElementById('checkoutItems'); const submit = document.getElementById('submitOrder'); const errorEl = document.getElementById('checkoutError');
  const notice = document.getElementById('reservationCheckoutNotice'); const reservationTimer = document.getElementById('reservationCheckoutTimer');
  let cart = readCart(); let activeReservation = null; let timer = null; let expirationRefreshPending = false;
  const fmt = ms => { const sec = Math.max(0, Math.ceil(ms / 1000)); return `${String(Math.floor(sec / 60)).padStart(2,'0')}:${String(sec % 60).padStart(2,'0')}`; };
  function escapeHTML(s) { return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
  const escapeAttr = escapeHTML;
  function renderTimer() {
    if (!activeReservation || !reservationTimer) return;
    const left = new Date(activeReservation.expires_at).getTime() - Date.now();
    reservationTimer.textContent = fmt(left);
    if (left <= 0 && !expirationRefreshPending) {
      expirationRefreshPending = true;
      submit.disabled = true;
      errorEl.textContent = 'El tiempo de apartado terminó. Actualizando disponibilidad...';
      refreshReservation(true).finally(() => { expirationRefreshPending = false; });
    }
  }
  async function cancelReservation() {
    const button = document.getElementById('cancelReservationCheckout'); if (button) button.disabled = true;
    try {
      const response = await fetch('/api/reservations/cancel', {method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
      const result = await response.json(); if (!response.ok) throw new Error(result.error || 'No se pudo cancelar el apartado.');
      activeReservation = null; cart = readCart(); if (timer) clearInterval(timer); render(); errorEl.textContent = 'Apartado cancelado. Las unidades volvieron a estar disponibles.';
    } catch (error) { errorEl.textContent = error.message; }
    finally { if (button) button.disabled = false; }
  }
  async function refreshReservation(afterExpiry = false) {
    try {
      const response = await fetch('/api/reservations/current', {cache:'no-store'});
      const result = await response.json();
      activeReservation = response.ok && result.active ? result : null;
      if (activeReservation) {
        cart = activeReservation.items.map(item => ({...item}));
        if (notice) notice.hidden = false;
        if (timer) clearInterval(timer); timer = setInterval(renderTimer, 1000); renderTimer();
      } else {
        if (notice) notice.hidden = true;
        if (timer) clearInterval(timer); timer = null;
        cart = readCart();
        if (afterExpiry) errorEl.textContent = 'Tu apartado venció y las unidades fueron liberadas. Puedes volver a apartarlas.';
      }
      render();
    } catch {
      activeReservation = null; cart = readCart(); if (notice) notice.hidden = true; render();
    }
  }
  function render() {
    if (!cart.length) {
      itemsEl.innerHTML = '<div class="empty-cart"><div class="empty-cart-icon">♡</div><h3>Tu bolsa está vacía</h3><p>Encuentra algo que te encante.</p><a href="/" class="text-link">Volver a la colección ↗</a></div>';
      submit.disabled = true; document.getElementById('summarySubtotal').textContent = money(0); document.getElementById('summaryShipping').textContent = '—'; document.getElementById('summaryTotal').textContent = money(0); return;
    }
    submit.disabled = false; let subtotal = 0;
    itemsEl.innerHTML = cart.map((item, index) => {
      const price = Number(item.price || 0); const quantity = Number(item.quantity || 1); subtotal += price * quantity;
      const controls = activeReservation ? '<small class="reserved-lock-note">Cantidad bloqueada durante el apartado</small>' : `<div class="qty-control"><button type="button" data-qty="${index}" data-delta="-1" aria-label="Reducir cantidad">−</button><span>${quantity}</span><button type="button" data-qty="${index}" data-delta="1" aria-label="Aumentar cantidad">+</button><button type="button" class="remove-item" data-remove="${index}">Quitar</button></div>`;
      return `<div class="checkout-item"><img src="${escapeAttr(item.image || '')}" alt=""><div class="checkout-item-details"><strong>${escapeHTML(item.name || 'Producto')}</strong><small>Talla ${escapeHTML(item.size || 'Única')} · ${escapeHTML(item.color || 'Único')}</small>${controls}</div><strong class="checkout-item-price">${money(price * quantity)}</strong></div>`;
    }).join('');
    const shipping = subtotal >= 1500 ? 0 : 99;
    document.getElementById('summarySubtotal').textContent = money(subtotal);
    document.getElementById('summaryShipping').textContent = shipping ? money(shipping) : 'Gratis';
    document.getElementById('summaryTotal').textContent = money(subtotal + shipping);
    document.getElementById('shippingHint').textContent = shipping ? `Te faltan ${money(1500 - subtotal)} para obtener envío gratis.` : '¡Tu pedido tiene envío gratis!';
  }
  itemsEl?.addEventListener('click', event => {
    if (activeReservation) return;
    const qty = event.target.closest('[data-qty]'); const remove = event.target.closest('[data-remove]');
    if (qty) { const i = Number(qty.dataset.qty); cart[i].quantity = Math.max(1, Math.min(20, Number(cart[i].quantity || 1) + Number(qty.dataset.delta))); writeCart(cart); render(); }
    else if (remove) { cart.splice(Number(remove.dataset.remove), 1); writeCart(cart); render(); }
  });
  document.getElementById('cancelReservationCheckout')?.addEventListener('click', cancelReservation);

  document.getElementById('checkoutForm')?.addEventListener('submit', async event => {
    event.preventDefault(); errorEl.textContent = '';
    if (!cart.length) { errorEl.textContent = 'Tu bolsa está vacía.'; return; }
    if (activeReservation && new Date(activeReservation.expires_at).getTime() <= Date.now()) { errorEl.textContent = 'Tu apartado venció. Vuelve a reservar el artículo.'; return; }
    const form = event.currentTarget; const data = new FormData(form);
    const customer = Object.fromEntries(['name','email','phone','address','city','postal_code','notes'].map(key => [key, String(data.get(key) || '').trim()]));
    const payment_method = data.get('payment_method') || 'cod';
    const payload = {customer, payment_method};
    if (activeReservation) payload.reservation_id = activeReservation.reservation_id;
    else payload.items = cart.map(i => ({product_id:i.product_id, quantity:i.quantity, size:i.size, color:i.color}));
    submit.disabled = true; submit.innerHTML = '<span class="spinner"></span> Procesando...';
    try {
      const response = await fetch('/api/checkout', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
      const result = await response.json(); if (response.status === 401 && result.login_required && result.login_url) { window.location.assign(result.login_url); return; } if (!response.ok) throw new Error(result.error || 'No pudimos procesar tu pedido.');
      if (!activeReservation) writeCart([]);
      if (result.redirect_url) { window.location.href = result.redirect_url; return; }
      window.location.href = `/pedido/${encodeURIComponent(result.order_number)}/gracias`;
    } catch (error) { errorEl.textContent = error.message || 'Ocurrió un error. Inténtalo de nuevo.'; submit.disabled = false; submit.innerHTML = 'Confirmar pedido <span>↗</span>'; if (activeReservation) refreshReservation(); }
  });
  refreshReservation();
  window.addEventListener('pageshow', event => {
    if (event.persisted) refreshReservation();
  });
})();
