import React from "react"

export default function FilterBar({ meta, group, onGroup, stock, onStock, counts, onNew }) {
  const groups = (meta && meta.item_groups) || []
  return (
    <div className="filterbar">
      <span className="filter-label">Group</span>
      <div className="group-chips">
        <button className={`chip ${group === "all" ? "on" : ""}`} onClick={() => onGroup("all")}>
          All
        </button>
        {groups.map((g) => (
          <button key={g} className={`chip ${group === g ? "on" : ""}`} onClick={() => onGroup(g)}>
            {g}
          </button>
        ))}
      </div>

      <div className="filter-sep" />
      <span className="filter-label">Stock</span>
      <div style={{ display: "flex", gap: 8 }}>
        <button className={`chip ${stock === "all" ? "on" : ""}`} onClick={() => onStock("all")}>
          All<span className="count">{counts.all}</span>
        </button>
        <button className={`chip ${stock === "low" ? "on" : ""}`} onClick={() => onStock("low")}>
          Low<span className="count">{counts.low}</span>
        </button>
        <button className={`chip ${stock === "out" ? "on" : ""}`} onClick={() => onStock("out")}>
          Out<span className="count">{counts.out}</span>
        </button>
      </div>

      <button className="new-btn" disabled={!meta} onClick={onNew}>
        + New item
      </button>
    </div>
  )
}
