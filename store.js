(() => {
  const CART_KEY = 'vesta_cart_v1';
  const FAV_KEY = 'vesta_favs_v1';
  const currency = window.VESTA_CONFIG?.currency || 'MXN';
  const money = value => new Intl.NumberFormat('es-MX', {style:'currency', currency}).format(Number(value || 0));
  const read = (key, fallback) => { try { return JSON.parse(localStorage.getItem(key)) ?? fallback; } catch { return fallback; } };
  const write = (key, value) => localStorage.setItem(key, JSON.stringify(value));
  const toast = msg => { const el = document.getElementById('toast'); if (!el) return; el.textContent = msg; el.classList.add('visible'); clearTimeout(window.__toastTimer); window.__toastTimer = setTimeout(() => el.classList.remove('visible'), 2600); };
  const updateCount = () => { const count = read(CART_KEY, []).reduce((n, item) => n + Number(item.quantity || 1), 0); const el = document.getElementById('cartCount'); if (el) el.textContent = count; };
  const favorites = read(FAV_KEY, []);
  document.querySelectorAll('[data-favorite]').forEach(button => { const id = button.dataset.favorite; if (favorites.includes(id)) { button.classList.add('is-favorite'); button.textContent = '♥'; } button.addEventListener('click', () => { const favs = read(FAV_KEY, []); const index = favs.indexOf(id); if (index >= 0) { favs.splice(index, 1); button.classList.remove('is-favorite'); button.textContent = '♡'; toast('Quitado de favoritos'); } else { favs.push(id); button.classList.add('is-favorite'); button.textContent = '♥'; toast('Guardado en favoritos'); } write(FAV_KEY, favs); }); });
  document.querySelectorAll('[data-add]').forEach(button => button.addEventListener('click', () => {
    const card = button.closest('.product-card'); if (!card || Number(card.dataset.stock) < 1) return;
    const size = card.querySelector('.size-select')?.value || 'Única'; const color = card.querySelector('.color-select')?.value || 'Único';
    const cart = read(CART_KEY, []); const found = cart.find(item => item.product_id === card.dataset.id && item.size === size && item.color === color);
    if (found) { if (found.quantity >= 20) return toast('Has alcanzado el máximo por artículo.'); found.quantity += 1; }
    else cart.push({product_id: card.dataset.id, name: card.querySelector('h3')?.textContent || '', price: Number(card.dataset.price), image: card.dataset.image, size, color, quantity: 1});
    write(CART_KEY, cart); updateCount(); toast('Añadido a tu bolsa');
  }));
  const tabs = [...document.querySelectorAll('[data-category]')]; const search = document.getElementById('productSearch'); const cards = [...document.querySelectorAll('.product-card')]; const empty = document.getElementById('emptyState'); let currentCategory = 'Todos';
  const filter = () => { const q = (search?.value || '').trim().toLowerCase(); let shown = 0; cards.forEach(card => { const matchCat = currentCategory === 'Todos' || card.dataset.category === currentCategory; const matchText = !q || `${card.dataset.name} ${card.dataset.description} ${card.dataset.category.toLowerCase()}`.includes(q); card.hidden = !(matchCat && matchText); if (!card.hidden) shown++; }); if (empty) empty.hidden = shown !== 0; };
  tabs.forEach(tab => tab.addEventListener('click', () => { currentCategory = tab.dataset.category; tabs.forEach(t => t.classList.toggle('active', t === tab)); filter(); })); search?.addEventListener('input', filter);
  const searchBox = document.getElementById('searchBox'); document.getElementById('searchToggle')?.addEventListener('click', () => { document.getElementById('coleccion')?.scrollIntoView({behavior:'smooth'}); if(searchBox) searchBox.classList.add('search-open'); search?.focus({preventScroll:true}); });
  document.getElementById('newsletterForm')?.addEventListener('submit', event => { event.preventDefault(); toast('¡Gracias! El formulario de novedades es una demostración.'); event.target.reset(); });
  updateCount();
})();
