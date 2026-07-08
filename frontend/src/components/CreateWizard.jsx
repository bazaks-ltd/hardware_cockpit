import React, { useCallback, useEffect, useRef, useState } from "react"

import { api } from "../api"

const EMPTY = {
  name: "",
  item_code: "",
  item_group: "",
  barcode: "",
  cost: "",
  price: "",
  opening_qty: "",
  reorder_level: "",
}

export default function CreateWizard({
  open,
  meta,
  warehouse,
  currency,
  onClose,
  onCreated,
  onGroupCreated,
  flashToast,
}) {
  const [step, setStep] = useState(0)
  const [draft, setDraft] = useState(EMPTY)
  const [uom, setUom] = useState("")
  const [busy, setBusy] = useState(false)
  const [extraGroups, setExtraGroups] = useState([])
  const [newGroup, setNewGroup] = useState(null) // null = pick from list; string = typing a new group
  const [groupBusy, setGroupBusy] = useState(false)
  const nameRef = useRef()

  const baseGroups = (meta && meta.item_groups) || []
  const groups = [...new Set([...extraGroups, ...baseGroups])]
  const uoms = (meta && meta.uoms) || []
  const defaultUom = (meta && meta.default_uom) || (uoms.includes("Unit") ? "Unit" : uoms[0]) || ""

  useEffect(() => {
    if (open) {
      setStep(0)
      setDraft({ ...EMPTY, item_group: baseGroups[0] || "" })
      setUom(defaultUom)
      setExtraGroups([])
      setNewGroup(null)
      setGroupBusy(false)
      setBusy(false)
    }
  }, [open]) // eslint-disable-line react-hooks/exhaustive-deps

  const set = (k, v) => setDraft((d) => ({ ...d, [k]: v }))

  const createGroupNow = useCallback(async () => {
    if (groupBusy) return
    const name = (newGroup || "").trim()
    if (!name) return
    setGroupBusy(true)
    try {
      const r = await api.createGroup(name)
      const g = r.item_group
      setExtraGroups((list) => (list.includes(g) ? list : [...list, g]))
      set("item_group", g)
      setNewGroup(null)
      onGroupCreated && onGroupCreated() // refresh the grid's group chips too
    } catch (e) {
      flashToast(e.message, true)
    } finally {
      setGroupBusy(false)
    }
  }, [newGroup, groupBusy, onGroupCreated, flashToast])

  const margin = () => {
    const c = Number(draft.cost) || 0
    const p = Number(draft.price) || 0
    if (c > 0 && p > 0) {
      const profit = p - c
      if (p >= c) return { ok: true, text: `Margin ${((profit / p) * 100).toFixed(0)}% · ${currency} ${profit.toFixed(2)} profit per unit` }
      return { ok: false, text: `Below cost — ${currency} ${Math.abs(profit).toFixed(2)} loss per unit` }
    }
    return { ok: true, text: "" }
  }

  const submit = useCallback(async () => {
    setBusy(true)
    try {
      await api.createItem({
        name: draft.name.trim(),
        item_code: draft.item_code.trim(),
        item_group: draft.item_group,
        stock_uom: uom,
        barcode: draft.barcode.trim(),
        cost: Number(draft.cost) || 0,
        price: Number(draft.price) || 0,
        opening_qty: Number(draft.opening_qty) || 0,
        reorder_level: Number(draft.reorder_level) || 0,
        warehouse,
      })
      onCreated()
    } catch (e) {
      flashToast(e.message, true)
    } finally {
      setBusy(false)
    }
  }, [draft, uom, warehouse, onCreated, flashToast])

  const next = useCallback(() => {
    if (step === 0 && !draft.name.trim()) {
      nameRef.current && nameRef.current.focus()
      return
    }
    if (step < 2) {
      setStep((s) => s + 1)
      return
    }
    submit()
  }, [step, draft.name, submit])

  // Enter advances / Esc cancels. While typing a new group, Enter creates it and Esc backs out.
  useEffect(() => {
    if (!open) return
    const h = (e) => {
      if (e.key === "Escape") {
        if (newGroup !== null) setNewGroup(null)
        else onClose()
      } else if (e.key === "Enter" && !busy) {
        if (newGroup !== null) {
          e.preventDefault()
          createGroupNow()
        } else {
          next()
        }
      }
    }
    window.addEventListener("keydown", h)
    return () => window.removeEventListener("keydown", h)
  }, [open, busy, next, onClose, newGroup, createGroupNow])

  if (!open) return null
  const m = margin()

  return (
    <div className="overlay open">
      <div className="modal">
        <div className="wiz-steps">
          {[0, 1, 2].map((i) => (
            <div key={i} className={`wiz-dot${i < step ? " done" : ""}${i === step ? " active" : ""}`} />
          ))}
        </div>
        <div className="wiz-step-label">Step {step + 1} of 3</div>

        <div className="modal-b">
          {step === 0 && (
            <>
              <h3 style={{ marginBottom: 4 }}>What are you adding?</h3>
              <div style={{ color: "var(--ink-dim)", fontSize: ".88rem", marginBottom: 18 }}>
                Just the basics. Edit everything later.
              </div>

              <div className="wiz-field">
                <label>Item name</label>
                <input
                  ref={nameRef}
                  autoFocus
                  placeholder="e.g. 16mm Hex Bolt"
                  value={draft.name}
                  onChange={(e) => set("name", e.target.value)}
                />
              </div>

              <div className="wiz-field">
                <label>
                  Group
                  {newGroup === null && (
                    <button type="button" className="link-add" onClick={() => setNewGroup("")}>
                      + New group
                    </button>
                  )}
                </label>
                {newGroup === null ? (
                  <select value={draft.item_group} onChange={(e) => set("item_group", e.target.value)}>
                    {groups.map((g) => (
                      <option key={g} value={g}>
                        {g}
                      </option>
                    ))}
                  </select>
                ) : (
                  <div className="field-row">
                    <input
                      autoFocus
                      placeholder="New group name"
                      value={newGroup}
                      onChange={(e) => setNewGroup(e.target.value)}
                    />
                    <button
                      type="button"
                      className="btn btn-primary btn-inline"
                      disabled={groupBusy || !newGroup.trim()}
                      onClick={createGroupNow}
                    >
                      {groupBusy ? "…" : "Create"}
                    </button>
                    <button type="button" className="btn btn-ghost btn-inline" onClick={() => setNewGroup(null)}>
                      Cancel
                    </button>
                  </div>
                )}
              </div>

              <div className="wiz-inline">
                <div className="wiz-field">
                  <label>Unit</label>
                  <select value={uom} onChange={(e) => setUom(e.target.value)}>
                    {uom && !uoms.includes(uom) && <option value={uom}>{uom}</option>}
                    {uoms.map((u) => (
                      <option key={u} value={u}>
                        {u}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="wiz-field">
                  <label>
                    Item code <span style={{ textTransform: "none", color: "var(--ink-dim)" }}>(optional)</span>
                  </label>
                  <input
                    placeholder="Auto"
                    value={draft.item_code}
                    onChange={(e) => set("item_code", e.target.value)}
                  />
                </div>
              </div>

              <div className="wiz-field">
                <label>
                  Barcode <span style={{ textTransform: "none", color: "var(--ink-dim)" }}>(optional)</span>
                </label>
                <input
                  placeholder="Scan or type…"
                  value={draft.barcode}
                  onChange={(e) => set("barcode", e.target.value)}
                />
              </div>
            </>
          )}

          {step === 1 && (
            <>
              <h3 style={{ marginBottom: 4 }}>Pricing</h3>
              <div style={{ color: "var(--ink-dim)", fontSize: ".88rem", marginBottom: 18 }}>
                What you pay, and what you charge.
              </div>
              <div className="wiz-inline">
                <div className="wiz-field">
                  <label>Cost price</label>
                  <div className="money-row">
                    <span className="prefix2">{currency}</span>
                    <input
                      type="number"
                      step="0.01"
                      placeholder="0.00"
                      value={draft.cost}
                      onChange={(e) => set("cost", e.target.value)}
                    />
                  </div>
                </div>
                <div className="wiz-field">
                  <label>Selling price</label>
                  <div className="money-row">
                    <span className="prefix2">{currency}</span>
                    <input
                      type="number"
                      step="0.01"
                      placeholder="0.00"
                      value={draft.price}
                      onChange={(e) => set("price", e.target.value)}
                    />
                  </div>
                </div>
              </div>
              <div className="margin-hint" style={{ color: m.ok ? "var(--accent)" : "var(--danger)" }}>
                {m.text}
              </div>
            </>
          )}

          {step === 2 && (
            <>
              <h3 style={{ marginBottom: 4 }}>Opening stock</h3>
              <div style={{ color: "var(--ink-dim)", fontSize: ".88rem", marginBottom: 18 }}>
                How many do you have right now?
              </div>
              <div className="wiz-inline">
                <div className="wiz-field">
                  <label>Quantity on hand</label>
                  <input
                    type="number"
                    step="any"
                    placeholder="0"
                    value={draft.opening_qty}
                    onChange={(e) => set("opening_qty", e.target.value)}
                  />
                </div>
                <div className="wiz-field">
                  <label>Reorder alert at</label>
                  <input
                    type="number"
                    step="any"
                    placeholder="0"
                    value={draft.reorder_level}
                    onChange={(e) => set("reorder_level", e.target.value)}
                  />
                </div>
              </div>
              <div style={{ background: "var(--panel-2)", borderRadius: 9, padding: 14, marginTop: 8 }}>
                <div className="review-row">
                  <span>Name</span>
                  <span>{draft.name || "—"}</span>
                </div>
                <div className="review-row">
                  <span>Group</span>
                  <span>{draft.item_group || "—"}</span>
                </div>
                <div className="review-row">
                  <span>Unit</span>
                  <span>{uom || "—"}</span>
                </div>
                <div className="review-row">
                  <span>Code</span>
                  <span>{draft.item_code.trim() || "auto"}</span>
                </div>
                <div className="review-row" style={{ border: 0 }}>
                  <span>Cost / Sell</span>
                  <span>
                    {currency} {(Number(draft.cost) || 0).toFixed(2)} / {currency}{" "}
                    {(Number(draft.price) || 0).toFixed(2)}
                  </span>
                </div>
              </div>
            </>
          )}
        </div>

        <div className="modal-f">
          <button className="btn secondary" onClick={step === 0 ? onClose : () => setStep((s) => s - 1)}>
            {step === 0 ? "Cancel" : "Back"}
          </button>
          <button
            className="btn btn-primary"
            disabled={busy || (step === 0 && newGroup !== null)}
            onClick={next}
          >
            {step < 2 ? "Next" : busy ? "Creating…" : "Create item"}
          </button>
        </div>
      </div>
    </div>
  )
}
