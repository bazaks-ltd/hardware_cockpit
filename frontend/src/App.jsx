import React, { useCallback, useEffect, useRef, useState } from "react"

import { api } from "./api"
import CreateWizard from "./components/CreateWizard.jsx"
import DetailPanel from "./components/DetailPanel.jsx"
import FilterBar from "./components/FilterBar.jsx"
import ItemGrid from "./components/ItemGrid.jsx"

export default function App() {
  const [meta, setMeta] = useState(null)
  const [items, setItems] = useState([])
  const [counts, setCounts] = useState({ all: 0, low: 0, out: 0 })
  const [currency, setCurrency] = useState("")
  const [warehouse, setWarehouse] = useState(null)

  const [search, setSearch] = useState("")
  const [group, setGroup] = useState("all")
  const [stock, setStock] = useState("all")

  const [selected, setSelected] = useState(null)
  const [wizardOpen, setWizardOpen] = useState(false)
  const [loading, setLoading] = useState(true)
  const [fatal, setFatal] = useState(null)
  const [toast, setToast] = useState(null)

  const flashToast = useCallback((msg, isErr = false) => {
    setToast({ msg, isErr })
    window.clearTimeout(flashToast._t)
    flashToast._t = window.setTimeout(() => setToast(null), 2400)
  }, [])

  const loadMeta = useCallback(
    () =>
      api
        .getFormMeta()
        .then((m) => {
          setMeta(m)
          setCurrency(m.currency_symbol || m.currency || "")
          setWarehouse(m.default_warehouse || null)
        })
        .catch((e) => setFatal(e.message)),
    []
  )

  useEffect(() => {
    loadMeta()
  }, [loadMeta])

  const loadItems = useCallback(async () => {
    setLoading(true)
    try {
      const r = await api.getItems({ search, item_group: group, stock_status: stock, limit: 2000 })
      setItems(r.items || [])
      setCounts({ all: r.all_count || 0, low: r.low_count || 0, out: r.out_count || 0 })
      if (r.currency_symbol) setCurrency(r.currency_symbol)
      if (r.warehouse) setWarehouse(r.warehouse)
    } catch (e) {
      flashToast(e.message, true)
    } finally {
      setLoading(false)
    }
  }, [search, group, stock, flashToast])

  // Reload on any filter change; debounce so typing in search doesn't spam the server.
  const debRef = useRef()
  useEffect(() => {
    if (!meta) return
    window.clearTimeout(debRef.current)
    debRef.current = window.setTimeout(loadItems, 220)
    return () => window.clearTimeout(debRef.current)
  }, [meta, loadItems])

  const patchItem = useCallback((code, patch) => {
    setItems((list) => list.map((it) => (it.item_code === code ? { ...it, ...patch } : it)))
    setSelected((sel) => (sel && sel.item_code === code ? { ...sel, ...patch } : sel))
  }, [])

  if (fatal) {
    return (
      <div className="app">
        <div className="empty" style={{ marginTop: "18vh" }}>
          <h2 style={{ marginBottom: 8 }}>Couldn't load the Item Cockpit</h2>
          <p>{fatal}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="app">
      <div className="topbar">
        <div className="brand">
          Item<span>Cockpit</span>
        </div>
        <div className="topbar-right">
          <div className="search">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="11" cy="11" r="8" />
              <path d="m21 21-4.3-4.3" />
            </svg>
            <input
              placeholder="Search name, code or barcode…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
        </div>
      </div>

      <div className="screen">
        <FilterBar
          meta={meta}
          group={group}
          onGroup={setGroup}
          stock={stock}
          onStock={setStock}
          counts={counts}
          onNew={() => setWizardOpen(true)}
        />
        <div className="manage-body">
          <ItemGrid
            items={items}
            loading={loading}
            selected={selected}
            currency={currency}
            onSelect={setSelected}
          />
          <DetailPanel
            item={selected}
            meta={meta}
            currency={currency}
            warehouse={warehouse}
            onClose={() => setSelected(null)}
            patchItem={patchItem}
            reload={loadItems}
            flashToast={flashToast}
          />
        </div>
      </div>

      <CreateWizard
        open={wizardOpen}
        meta={meta}
        warehouse={warehouse}
        currency={currency}
        onClose={() => setWizardOpen(false)}
        onCreated={() => {
          flashToast("✓ Item created")
          loadItems()
        }}
        onGroupCreated={loadMeta}
        flashToast={flashToast}
      />

      {toast && <div className={`toast show${toast.isErr ? " err" : ""}`}>{toast.msg}</div>}
    </div>
  )
}
