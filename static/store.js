(() => {
  const CART_KEY = 'vesta_cart_v1';
  const FAV_KEY = 'vesta_favs_v1';
  const currency = window.VESTA_CONFIG?.currency || 'MXN';
  const read = (key, fallback) => { try { return JSON.parse(localStorage.getItem(key)) ?? fallback; } catch { return fallback; } };
  const write = (key, value) => localStorage.setItem(key, JSON.stringify(value));
  const toast = msg => { const el = document.getElementById('toast'); if (!el) return; el.textContent = msg; el.classList.add('visible'); clearTimeout(window.__toastTimer); window.__toastTimer = setTimeout(() => el.classList.remove('visible'), 2800); };
  const updateCount = () => { const count = read(CART_KEY, []).reduce((n, item) => n + Number(item.quantity || 1), 0); const el = document.getElementById('cartCount'); if (el) el.textContent = count; };
  const favorites = read(FAV_KEY, []);
  document.querySelectorAll('[data-favorite]').forEach(button => {
    const id = button.dataset.favorite;
    if (favorites.includes(id)) { button.classList.add('is-favorite'); button.textContent = '♥'; }
    button.addEventListener('click', () => {
      const favs = read(FAV_KEY, []); const index = favs.indexOf(id);
      if (index >= 0) { favs.splice(index, 1); button.classList.remove('is-favorite'); button.textContent = '♡'; toast('Quitado de favoritos'); }
      else { favs.push(id); button.classList.add('is-favorite'); button.textContent = '♥'; toast('Guardado en favoritos'); }
      write(FAV_KEY, favs);
    });
  });

  document.querySelectorAll('[data-add]').forEach(button => button.addEventListener('click', () => {
    const card = button.closest('.product-card');
    if (!card) return;
    if (card.dataset.productType !== 'regular') return toast('Las ediciones exclusivas se apartan desde su sección.');
    const stockMode = card.dataset.stockMode || 'limited';
    const available = Number(card.dataset.stock || 0);
    if (stockMode !== 'infinite' && available < 1) return toast('Esta prenda está agotada.');
    const size = card.querySelector('.size-select')?.value || 'Única';
    const color = card.querySelector('.color-select')?.value || 'Único';
    const cart = read(CART_KEY, []);
    const found = cart.find(item => item.product_id === card.dataset.id && item.size === size && item.color === color);
    if (found) {
      if (found.quantity >= 20) return toast('Has alcanzado el máximo por artículo.');
      if (stockMode !== 'infinite' && found.quantity >= available) return toast('No hay más unidades libres para agregar.');
      found.quantity += 1;
    } else {
      cart.push({product_id:card.dataset.id,name:card.querySelector('h3')?.textContent || '',price:Number(card.dataset.price),image:card.dataset.image,size,color,quantity:1});
    }
    write(CART_KEY, cart); updateCount(); toast('Añadido a tu bolsa');
  }));

  const banner = document.getElementById('reservationBanner');
  const bannerText = document.getElementById('reservationBannerText');
  const bannerTimer = document.getElementById('reservationBannerTimer');
  let activeReservation = null; let reservationInterval = null; let expirationRefreshPending = false;
  const fmt = ms => { const sec = Math.max(0, Math.ceil(ms / 1000)); return `${String(Math.floor(sec / 60)).padStart(2,'0')}:${String(sec % 60).padStart(2,'0')}`; };
  const renderReservationBanner = () => {
    if (!banner || !activeReservation) { if (banner) banner.hidden = true; return; }
    banner.hidden = false;
    const units = activeReservation.items.reduce((sum, item) => sum + Number(item.quantity || 1), 0);
    bannerText.textContent = `${units} unidad(es) apartada(s). Confirma tu compra antes de que termine el tiempo.`;
    const remaining = new Date(activeReservation.expires_at).getTime() - Date.now();
    bannerTimer.textContent = fmt(remaining);
    const qrLink = document.getElementById('reservationQrLink');
    if (qrLink && activeReservation.public_url) qrLink.href = activeReservation.public_url;
    banner.classList.toggle('reservation-expiring', remaining <= 60000);
    if (remaining <= 0 && !expirationRefreshPending) {
      expirationRefreshPending = true;
      refreshReservation().finally(() => { expirationRefreshPending = false; });
    }
  };
  async function refreshCatalogAvailability() {
    try {
      const response = await fetch('/api/products', {cache:'no-store'});
      if (!response.ok) return;
      const result = await response.json();
      const byId = new Map((result.products || []).map(product => [product.id, product]));
      document.querySelectorAll('.product-card').forEach(card => {
        const product = byId.get(card.dataset.id);
        if (!product) return;
        const available = product.stock_mode === 'infinite' ? null : Number(product.available_stock || 0);
        card.dataset.stock = available === null ? '-1' : String(available);
        const badge = card.querySelector('.stock-badge');
        if (badge) {
          badge.classList.toggle('out', available !== null && available <= 0);
          if (product.product_type === 'exclusive') badge.textContent = available <= 0 ? 'Cupo completo' : `${available} cupos disponibles`;
          else if (product.stock_mode === 'infinite') badge.textContent = 'Disponibilidad ilimitada';
          else if (available <= 0) badge.textContent = 'Agotado';
          else badge.textContent = available <= 4 ? `${available} disponibles` : '';
        }
        const button = card.querySelector('[data-add], [data-reserve]');
        if (button) button.disabled = available !== null && available <= 0;
      });
    } catch { /* MongoDB stays the source of truth when a visitor tries to reserve or buy. */ }
  }
  async function refreshReservation() {
    try {
      const response = await fetch('/api/reservations/current', {cache:'no-store'});
      const result = await response.json();
      activeReservation = response.ok && result.active ? result : null;
      renderReservationBanner();
      if (reservationInterval) clearInterval(reservationInterval);
      if (activeReservation) reservationInterval = setInterval(renderReservationBanner, 1000);
      await refreshCatalogAvailability();
    } catch { /* The server will validate expiration during confirmation. */ }
  }
  async function cancelReservation() {
    const button = document.getElementById('cancelReservationBanner');
    if (button) button.disabled = true;
    try {
      const response = await fetch('/api/reservations/cancel', {method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'});
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || 'No se pudo cancelar el apartado.');
      activeReservation = null; renderReservationBanner();
      if (reservationInterval) clearInterval(reservationInterval);
      toast('Apartado cancelado. Los cupos volvieron a estar disponibles.'); await refreshCatalogAvailability();
    } catch (error) { toast(error.message); }
    finally { if (button) button.disabled = false; }
  }
  document.getElementById('cancelReservationBanner')?.addEventListener('click', cancelReservation);

  document.querySelectorAll('[data-reserve]').forEach(button => button.addEventListener('click', async () => {
    const card = button.closest('.product-card'); if (!card) return;
    if (card.dataset.productType !== 'exclusive') return toast('Solo las ediciones exclusivas usan apartado temporal.');
    const size = card.querySelector('.size-select')?.value || 'Única';
    const color = card.querySelector('.color-select')?.value || 'Único';
    button.disabled = true; const previous = button.textContent; button.textContent = 'Apartando...';
    try {
      const response = await fetch('/api/reservations', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({product_id:card.dataset.id,quantity:1,size,color})});
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || 'No se pudo apartar esta prenda.');
      await refreshReservation(); toast('Prenda apartada durante 5 minutos.');
    } catch (error) { toast(error.message); }
    finally { button.disabled = false; button.textContent = previous; }
  }));

  const tabs = [...document.querySelectorAll('[data-category]')];
  const search = document.getElementById('productSearch');
  const cards = [...document.querySelectorAll('.product-card')];
  const normalSection = document.getElementById('ropa-normal');
  const exclusiveSection = document.getElementById('ediciones-exclusivas');
  const normalEmpty = document.getElementById('normalEmptyState');
  const exclusiveEmpty = document.getElementById('exclusiveEmptyState');
  let currentCategory = 'Todos';
  const filter = () => {
    const q = (search?.value || '').trim().toLowerCase();
    let normalShown = 0;
    let exclusiveShown = 0;
    cards.forEach(card => {
      const matchCategory = currentCategory === 'Todos' || card.dataset.category === currentCategory;
      const matchText = !q || `${card.dataset.name} ${card.dataset.description} ${card.dataset.category.toLowerCase()}`.includes(q);
      card.hidden = !(matchCategory && matchText);
      if (!card.hidden && card.dataset.productType === 'exclusive') exclusiveShown++;
      else if (!card.hidden) normalShown++;
    });
    if (normalEmpty) normalEmpty.hidden = normalShown !== 0;
    if (exclusiveEmpty) exclusiveEmpty.hidden = exclusiveShown !== 0;
    if (normalSection) normalSection.hidden = false;
    if (exclusiveSection) exclusiveSection.hidden = false;
  };
  tabs.forEach(tab => tab.addEventListener('click', () => {
    currentCategory = tab.dataset.category;
    tabs.forEach(item => item.classList.toggle('active', item === tab));
    filter();
  }));
  search?.addEventListener('input', filter);
  filter();
  const searchBox = document.getElementById('searchBox');
  document.getElementById('searchToggle')?.addEventListener('click', () => { document.getElementById('ropa-normal')?.scrollIntoView({behavior:'smooth'}); if(searchBox) searchBox.classList.add('search-open'); search?.focus({preventScroll:true}); });
  document.getElementById('newsletterForm')?.addEventListener('submit', event => { event.preventDefault(); toast('¡Gracias! El formulario de novedades es una demostración.'); event.target.reset(); });
  updateCount(); refreshReservation();
  setInterval(() => { if (!document.hidden) refreshCatalogAvailability(); }, 12000);
})();
