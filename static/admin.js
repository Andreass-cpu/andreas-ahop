(() => {
  const toast = msg => {
    const el = document.getElementById('toast');
    if (!el) return;
    el.textContent = msg;
    el.classList.add('visible');
    setTimeout(() => el.classList.remove('visible'), 3000);
  };

  const tabs = document.querySelectorAll('[data-tab]');
  const productsSection = document.getElementById('adminProducts');
  const ordersSection = document.getElementById('adminOrders');
  tabs.forEach(tab => tab.addEventListener('click', () => {
    tabs.forEach(item => item.classList.toggle('active', item === tab));
    productsSection.hidden = tab.dataset.tab !== 'products';
    ordersSection.hidden = tab.dataset.tab !== 'orders';
  }));

  const form = document.getElementById('productForm');
  const msg = document.getElementById('productMessage');
  const table = document.getElementById('productsTable');
  const productType = document.getElementById('productType');
  const stockMode = document.getElementById('stockMode');
  const stockModeGroup = document.getElementById('stockModeGroup');
  const stockGroup = document.getElementById('stockFieldGroup');
  const exclusiveLimitGroup = document.getElementById('exclusiveLimitGroup');

  const syncProductFields = () => {
    const exclusive = productType?.value === 'exclusive';
    const unlimited = !exclusive && stockMode?.value === 'infinite';
    if (stockModeGroup) stockModeGroup.hidden = exclusive;
    if (stockGroup) stockGroup.hidden = exclusive || unlimited;
    if (exclusiveLimitGroup) exclusiveLimitGroup.hidden = !exclusive;
    if (form?.elements.stock) {
      form.elements.stock.disabled = exclusive || unlimited;
      form.elements.stock.required = !exclusive && !unlimited;
    }
    if (form?.elements.exclusive_limit) {
      form.elements.exclusive_limit.disabled = !exclusive;
      form.elements.exclusive_limit.required = exclusive;
    }
  };
  productType?.addEventListener('change', syncProductFields);
  stockMode?.addEventListener('change', syncProductFields);
  syncProductFields();

  const clearForm = () => {
    form.reset();
    form.elements.id.value = '';
    productType.value = 'regular';
    stockMode.value = 'limited';
    syncProductFields();
    form.hidden = true;
    msg.textContent = '';
    document.getElementById('newProductButton').textContent = '+ Nuevo producto';
  };

  document.getElementById('newProductButton')?.addEventListener('click', () => {
    if (!form.hidden && !form.elements.id.value) return clearForm();
    form.reset();
    form.elements.id.value = '';
    productType.value = 'regular';
    stockMode.value = 'limited';
    syncProductFields();
    form.hidden = false;
    document.getElementById('newProductButton').textContent = 'Cerrar formulario';
    form.scrollIntoView({behavior: 'smooth', block: 'center'});
  });
  document.getElementById('cancelProduct')?.addEventListener('click', clearForm);

  const splitList = value => String(value || '').split(',').map(item => item.trim()).filter(Boolean);
  form?.addEventListener('submit', async event => {
    event.preventDefault();
    msg.textContent = 'Guardando en MongoDB Atlas...';
    const data = new FormData(form);
    const id = String(data.get('id') || '');
    const type = String(data.get('product_type') || 'regular');
    const mode = type === 'exclusive' ? 'limited' : String(data.get('stock_mode') || 'limited');
    const payload = {
      name: data.get('name'),
      category: data.get('category'),
      description: data.get('description'),
      image: data.get('image'),
      price: Number(data.get('price')),
      product_type: type,
      stock_mode: mode,
      sizes: splitList(data.get('sizes')),
      colors: splitList(data.get('colors')),
      active: true
    };
    if (type === 'exclusive') {
      payload.exclusive_limit = Number(data.get('exclusive_limit'));
    } else {
      payload.stock = mode === 'infinite' ? 0 : Number(data.get('stock'));
    }
    try {
      const response = await fetch(id ? `/api/admin/products/${id}` : '/api/admin/products', {
        method: id ? 'PATCH' : 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || 'No se pudo guardar el producto.');
      toast(type === 'exclusive' ? 'Edición exclusiva guardada en Atlas.' : 'Prenda normal guardada en Atlas.');
      location.reload();
    } catch (error) {
      msg.textContent = error.message;
    }
  });

  table?.addEventListener('click', async event => {
    const edit = event.target.closest('[data-edit-product]');
    const remove = event.target.closest('[data-delete-product]');
    const reactivate = event.target.closest('[data-reactivate-product]');

    if (edit) {
      const row = edit.closest('tr');
      const product = JSON.parse(row.dataset.product);
      form.hidden = false;
      form.elements.id.value = product.id;
      ['name', 'category', 'description', 'image', 'price', 'stock'].forEach(key => {
        if (form.elements[key]) form.elements[key].value = product[key] ?? '';
      });
      productType.value = product.product_type || 'regular';
      stockMode.value = product.stock_mode || 'limited';
      if (form.elements.exclusive_limit) form.elements.exclusive_limit.value = product.exclusive_limit ?? product.stock ?? 1;
      form.elements.sizes.value = (product.sizes || []).join(', ');
      form.elements.colors.value = (product.colors || []).join(', ');
      syncProductFields();
      document.getElementById('newProductButton').textContent = 'Cerrar formulario';
      form.scrollIntoView({behavior: 'smooth', block: 'center'});
    } else if (remove) {
      if (!confirm('¿Quitar este producto de la tienda? Los pedidos previos se conservan y podrás reactivarlo después.')) return;
      try {
        const response = await fetch(`/api/admin/products/${remove.dataset.deleteProduct}`, {method: 'DELETE'});
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || 'No se pudo quitar.');
        toast('Producto quitado de la tienda.');
        location.reload();
      } catch (error) { toast(error.message); }
    } else if (reactivate) {
      try {
        const response = await fetch(`/api/admin/products/${reactivate.dataset.reactivateProduct}`, {
          method: 'PATCH', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({active: true})
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || 'No se pudo reactivar.');
        toast('Producto reactivado.');
        location.reload();
      } catch (error) { toast(error.message); }
    }
  });

  const orderTable = document.getElementById('ordersTable');
  orderTable?.addEventListener('change', async event => {
    const select = event.target.closest('[data-order-status]');
    if (!select) return;
    const original = select.dataset.previous || select.value;
    try {
      const response = await fetch(`/api/admin/orders/${select.dataset.orderStatus}`, {
        method: 'PATCH', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({status: select.value})
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || 'No se pudo actualizar.');
      toast('Estado del pedido actualizado.');
      setTimeout(() => location.reload(), 600);
    } catch (error) {
      toast(error.message);
      select.value = original;
    }
  });
  document.getElementById('refreshOrders')?.addEventListener('click', () => location.reload());
})();
