import React from "react"

import { fmtQty, initials, money, stockClass } from "../format"

export default function ItemGrid({ items, loading, selected, currency, onSelect }) {
  return (
    <div className="grid-wrap">
      <table>
        <thead>
          <tr>
            <th>Item</th>
            <th>Group</th>
            <th>Stock</th>
            <th>Selling price</th>
            <th>Cost</th>
          </tr>
        </thead>
        <tbody>
          {items.map((it) => (
            <tr
              key={it.item_code}
              className={selected && selected.item_code === it.item_code ? "sel" : ""}
              onClick={() => onSelect(it)}
            >
              <td>
                <div className="item-cell">
                  <div className="thumb">
                    {it.image ? <img src={it.image} alt="" /> : initials(it.item_name)}
                  </div>
                  <div>
                    <div className="item-name">{it.item_name}</div>
                    <div className="item-code">{it.item_code}</div>
                  </div>
                </div>
              </td>
              <td>
                <span className="grp-tag">{it.item_group}</span>
              </td>
              <td>
                <span className={`stock-pill ${stockClass(it.stock_status)}`}>
                  {fmtQty(it.qty)} {it.stock_uom}
                </span>
              </td>
              <td className="price">{money(currency, it.selling_rate)}</td>
              <td className="num" style={{ color: "var(--ink-dim)" }}>
                {money(currency, it.cost_rate)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {loading && <div className="hc-loading">Loading…</div>}
      {!loading && !items.length && <div className="empty">No items match these filters.</div>}
    </div>
  )
}
