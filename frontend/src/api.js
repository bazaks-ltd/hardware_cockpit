// Tiny Frappe RPC client for the Item Cockpit. Uses the desk session cookie for auth and a
// CSRF token (injected as window.csrf_token in production, refreshed on demand in dev).

const BASE = "/api/method/hardware_cockpit.api"

function getCookie(name) {
  const m = document.cookie.match("(^|;)\\s*" + name + "\\s*=\\s*([^;]+)")
  return m ? decodeURIComponent(m.pop()) : null
}

let csrfToken = window.csrf_token || getCookie("csrf_token") || null

async function refreshCsrf() {
  try {
    const r = await fetch(`${BASE}.get_csrf_token`, {
      method: "GET",
      credentials: "include",
      cache: "no-store",
      headers: { Accept: "application/json" },
    })
    if (r.ok) {
      const j = await r.json()
      csrfToken = (j && j.message && j.message.csrf_token) || csrfToken
      window.csrf_token = csrfToken
    }
  } catch (_) {
    /* ignore — surfaced by the retried call */
  }
  return csrfToken
}

function extractMessage(data, fallback) {
  try {
    if (data && data._server_messages) {
      const msgs = JSON.parse(data._server_messages)
      if (msgs.length) {
        const first = typeof msgs[0] === "string" ? JSON.parse(msgs[0]) : msgs[0]
        if (first && first.message) return String(first.message).replace(/<[^>]*>/g, "")
      }
    }
  } catch (_) {
    /* fall through */
  }
  if (data && data.exception) return String(data.exception).split(":").slice(1).join(":").trim() || fallback
  return fallback
}

async function call(method, args = {}, { retry = true } = {}) {
  const res = await fetch(`${BASE}.${method}`, {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      "X-Frappe-CSRF-Token": csrfToken || "",
    },
    body: JSON.stringify(args),
  })

  let data = {}
  try {
    data = await res.json()
  } catch (_) {
    /* non-JSON error body */
  }

  if (!res.ok) {
    if ((res.status === 403 || res.status === 400) && retry) {
      await refreshCsrf()
      return call(method, args, { retry: false })
    }
    throw new Error(extractMessage(data, `Something went wrong (${res.status}). Please try again.`))
  }
  return data.message
}

export const api = {
  getFormMeta: () => call("get_form_meta"),
  getItems: (params) => call("get_items", params),
  updatePrice: (item_code, price_type, rate) => call("update_price", { item_code, price_type, rate }),
  setStock: (item_code, warehouse, qty) => call("set_stock", { item_code, warehouse, qty }),
  setReorder: (item_code, warehouse, reorder_level) =>
    call("set_reorder", { item_code, warehouse, reorder_level }),
  updateUom: (item_code, stock_uom) => call("update_uom", { item_code, stock_uom }),
  createItem: (payload) => call("create_item", { payload }),
  createGroup: (group_name, parent) => call("create_group", { group_name, parent }),
}
