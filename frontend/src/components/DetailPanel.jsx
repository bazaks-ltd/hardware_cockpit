import React, { useCallback, useEffect, useState } from "react"

import { api } from "../api"

function Flash({ state }) {
  if (!state) return <span className="saved-flash" />
  return <span className={`saved-flash show${state.err ? " err" : ""}`}>{state.msg}</span>
}

export default function DetailPanel({
  item,
  meta,
  currency,
  warehouse,
  onClose,
  patchItem,
  reload,
  flashToast,
}) {
  const [price, setPrice] = useState("")
  const [cost, setCost] = useState("")
  const [stock, setStock] = useState("")
  const [reorder, setReorder] = useState("")
  const [uom, setUom] = useState("")
  const [flash, setFlash] = useState({})
  const [busy, setBusy] = useState({})

  const code = item && item.item_code

  useEffect(() => {
    if (!item) return
    setPrice(item.selling_rate ?? "")
    setCost(item.cost_rate ?? "")
    setStock(item.qty ?? "")
    setReorder(item.reorder_level ?? "")
    setUom(item.stock_uom ?? "")
    setFlash({})
    setBusy({})
  }, [code]) // eslint-disable-line react-hooks/exhaustive-deps

  const showFlash = useCallback((key, msg, err = false) => {
    setFlash((f) => ({ ...f, [key]: { msg, err } }))
    window.setTimeout(() => setFlash((f) => ({ ...f, [key]: null })), 1800)
  }, [])

  const run = useCallback(
    async (key, fn, okMsg) => {
      setBusy((b) => ({ ...b, [key]: true }))
      try {
        await fn()
        showFlash(key, okMsg)
      } catch (e) {
        showFlash(key, e.message, true)
        flashToast(e.message, true)
      } finally {
        setBusy((b) => ({ ...b, [key]: false }))
      }
    },
    [showFlash, flashToast]
  )

  if (!item) return null

  const uoms = (meta && meta.uoms) || []

  return (
    <div className="detail open">
      <button className="close-x" onClick={onClose}>
        ×
      </button>
      <h2>{item.item_name}</h2>
      <div className="sub">
        {code} · {item.item_group}
      </div>

      <div className="field">
        <label>Selling price</label>
        <div className="field-row">
          <span className="prefix">{currency}</span>
          <input type="number" step="0.01" value={price} onChange={(e) => setPrice(e.target.value)} />
          <button
            className="btn btn-primary btn-inline"
            disabled={busy.price}
            onClick={() =>
              run(
                "price",
                async () => {
                  const r = await api.updatePrice(code, "selling", Number(price) || 0)
                  patchItem(code, { selling_rate: r.rate })
                },
                "✓ Price updated"
              )
            }
          >
            Save
          </button>
        </div>
        <Flash state={flash.price} />
      </div>

      <div className="field">
        <label>Cost price</label>
        <div className="field-row">
          <span className="prefix">{currency}</span>
          <input type="number" step="0.01" value={cost} onChange={(e) => setCost(e.target.value)} />
          <button
            className="btn btn-primary btn-inline"
            disabled={busy.cost}
            onClick={() =>
              run(
                "cost",
                async () => {
                  const r = await api.updatePrice(code, "buying", Number(cost) || 0)
                  patchItem(code, { cost_rate: r.rate })
                },
                "✓ Cost updated"
              )
            }
          >
            Save
          </button>
        </div>
        <Flash state={flash.cost} />
      </div>

      <div className="divider" />

      <div className="field">
        <label>Stock on hand{warehouse ? ` — ${warehouse}` : ""}</label>
        <div className="field-row">
          <input type="number" step="any" value={stock} onChange={(e) => setStock(e.target.value)} />
          <button
            className="btn btn-primary btn-inline"
            disabled={busy.stock}
            onClick={() =>
              run(
                "stock",
                async () => {
                  await api.setStock(code, warehouse, Number(stock) || 0)
                  await reload()
                },
                "✓ Stock adjusted"
              )
            }
          >
            Set
          </button>
        </div>
        <Flash state={flash.stock} />
        <div className="hint">Setting a new value records a stock adjustment behind the scenes.</div>
      </div>

      <div className="field">
        <label>Reorder level</label>
        <div className="field-row">
          <input type="number" step="any" value={reorder} onChange={(e) => setReorder(e.target.value)} />
          <button
            className="btn btn-primary btn-inline"
            disabled={busy.reorder}
            onClick={() =>
              run(
                "reorder",
                async () => {
                  await api.setReorder(code, warehouse, Number(reorder) || 0)
                  await reload()
                },
                "✓ Reorder set"
              )
            }
          >
            Save
          </button>
        </div>
        <Flash state={flash.reorder} />
      </div>

      <div className="field">
        <label>Unit</label>
        <div className="field-row">
          <select value={uom} onChange={(e) => setUom(e.target.value)}>
            {uom && !uoms.includes(uom) && <option value={uom}>{uom}</option>}
            {uoms.map((u) => (
              <option key={u} value={u}>
                {u}
              </option>
            ))}
          </select>
          <button
            className="btn btn-primary btn-inline"
            disabled={busy.uom || uom === item.stock_uom}
            onClick={() =>
              run(
                "uom",
                async () => {
                  await api.updateUom(code, uom)
                  patchItem(code, { stock_uom: uom })
                  await reload()
                },
                "✓ Unit updated"
              )
            }
          >
            Save
          </button>
        </div>
        <Flash state={flash.uom} />
      </div>
    </div>
  )
}
