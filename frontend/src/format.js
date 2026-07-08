export function initials(name) {
  return (name || "")
    .split(" ")
    .slice(0, 2)
    .map((w) => w[0] || "")
    .join("")
    .toUpperCase()
}

// Decimal-aware quantity (e.g. 12.5), trailing zeros stripped.
export function fmtQty(v) {
  const n = Number(v) || 0
  return n.toLocaleString(undefined, { maximumFractionDigits: 3 })
}

export function money(symbol, v) {
  const n = Number(v) || 0
  return `${symbol || ""} ${n.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`.trim()
}

export function stockClass(status) {
  return status === "out" ? "stock-out" : status === "low" ? "stock-low" : "stock-ok"
}
