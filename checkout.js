(() => {
  const CART_KEY = 'vesta_cart_v1'; const currency = window.VESTA_CONFIG?.currency || 'MXN';
  const money = value => new Intl.NumberFormat('es-MX', {style:'currency', currency}).format(Number(value || 0));
  const readCart = () => { try { return JSON.parse(localStorage.getItem(CART_KEY) || '[]'); } catch { return []; } };
  const writeCart = cart => localStorage.setItem(CART_KEY, JSON.stringify(cart));
  const itemsEl = document.getElementById('checkoutItems'); const submit = document.getElementById('submitOrder'); const errorEl = document.getElementById('checkoutError');
  let cart = readCart();
  function render() {
    if (!cart.length) { itemsEl.innerHTML = '<div class="empty-cart"><div class="empty-cart-icon">♡</div><h3>Tu bolsa está vacía</h3><p>Encuentra algo que te encante.</p><a href="/" class="text-link">Volver a la colección ↗</a></div>'; submit.disabled = true; document.getElementById('summarySubtotal').textContent = money(0); document.getElementById('summaryShipping').textContent = '—'; document.getElementById('summaryTotal').textContent = money(0); return; }
    submit.disabled = false; let subtotal = 0;
    itemsEl.innerHTML = cart.map((item, index) => { const price = Number(item.price || 0); subtotal += price * Number(item.quantity || 1); return `<div class="checkout-item"><img src="${escapeAttr(item.image || '')}" alt=""><div class="checkout-item-details"><strong>${escapeHTML(item.name || 'Producto')}</strong><small>Talla ${escapeHTML(item.size || 'Única')} · ${escapeHTML(item.color || 'Único')}</small><div class="qty-control"><button type="button" data-qty="${index}" data-delta="-1" aria-label="Reducir cantidad">−</button><span>${Number(item.quantity || 1)}</span><button type="button" data-qty="${index}" data-delta="1" aria-label="Aumentar cantidad">+</button><button type="button" class="remove-item" data-remove="${index}">Quitar</button></div></div><strong class="checkout-item-price">${money(price * Number(item.quantity || 1))}</strong></div>`; }).join('');
    const shipping = subtotal >= 1500 ? 0 : 99; document.getElementById('summarySubtotal').textContent = money(subtotal); document.getElementById('summaryShipping').textContent = shipping ? money(shipping) : 'Gratis'; document.getElementById('summaryTotal').textContent = money(subtotal + shipping); document.getElementById('shippingHint').textContent = shipping ? `Te faltan ${money(1500 - subtotal)} para obtener envío gratis.` : '¡Tu pedido tiene envío gratis!';
  }
  function escapeHTML(s) { return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
  function escapeAttr(s) { return escapeHTML(s); }
  itemsEl?.addEventListener('click', event => { const qty = event.target.closest('[data-qty]'); const remove = event.target.closest('[data-remove]'); if (qty) { const i = Number(qty.dataset.qty); cart[i].quantity = Math.max(1, Math.min(20, Number(cart[i].quantity || 1) + Number(qty.dataset.delta))); writeCart(cart); render(); } else if (remove) { cart.splice(Number(remove.dataset.remove), 1); writeCart(cart); render(); } });
  document.getElementById('checkoutForm')?.addEventListener('submit', async event => {
    event.preventDefault(); errorEl.textContent = ''; if (!cart.length) { errorEl.textContent = 'Tu bolsa está vacía.'; return; }
    const form = event.currentTarget; const data = new FormData(form); const customer = Object.fromEntries(['name','email','phone','address','city','postal_code','notes'].map(key => [key, String(data.get(key) || '').trim()])); const payment_method = data.get('payment_method') || 'cod';
    submit.disabled = true; submit.innerHTML = '<span class="spinner"></span> Procesando...';
    try {
      const response = await fetch('/api/checkout', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({customer, payment_method, items:cart.map(i => ({product_id:i.product_id, quantity:i.quantity, size:i.size, color:i.color}))})});
      const result = await response.json(); if (!response.ok) throw new Error(result.error || 'No pudimos procesar tu pedido.');
      if (result.redirect_url) { writeCart([]); window.location.href = result.redirect_url; return; }
      writeCart([]); window.location.href = result.redirect_url || `/pedido/${encodeURIComponent(result.order_number)}/gracias`;
    } catch (error) { errorEl.textContent = error.message || 'Ocurrió un error. Inténtalo de nuevo.'; submit.disabled = false; submit.innerHTML = 'Confirmar pedido <span>↗</span>'; }
  });
  render();
})();
