# Hardware Cockpit

A single-screen **Item Cockpit** for non-technical hardware-store staff, built on top of
ERPNext. It collapses routine item management — search, filter, stock, pricing, and item
creation — into one page, while every write still flows through ERPNext documents so all
validation, permissions, ledgers, and accounting stay intact.

Scope of this app: the **Manage** screen (item list + filters + inline detail editing + a
3-step creation wizard). The Sell/POS screen is out of scope (see the `pos_next` app).

## Architecture

- **Backend** — `hardware_cockpit/api.py`: whitelisted methods (`get_items`, `update_price`,
  `set_stock`, `set_reorder`, `update_uom`, `create_item`, `get_form_meta`). Every write goes
  through `frappe.get_doc(...).insert()/.save()/.submit()` and is permission-checked.
- **Frontend** — `frontend/`: a React + Vite single-page app, built into
  `hardware_cockpit/public/item_cockpit/` and served at **`/item-cockpit`** via the Jinja
  template `hardware_cockpit/www/item_cockpit.html`.
- **Defaults** — reuse existing ERPNext settings (Selling/Buying Settings price lists,
  Stock Settings default warehouse, Global Defaults company/currency). No new Settings DocType.

## Develop

```bash
# from the bench root
bench get-app hardware_cockpit apps/hardware_cockpit
bench --site pos.local install-app hardware_cockpit

# build the frontend (writes public/item_cockpit + www/item_cockpit.html)
cd apps/hardware_cockpit/frontend
yarn install
yarn build

# live dev server (proxies /api,/assets,... to the Frappe backend)
yarn dev
```

Then open `/item-cockpit` on your site (login required).

## Test

```bash
bench --site pos.local run-tests --app hardware_cockpit
```

## License

MIT
