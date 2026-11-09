export function parseActualCost(value) {
  if (typeof value !== "string" || value.trim() === "") {
    return null;
  }
  const cost = Number(value);
  return Number.isFinite(cost) && cost >= 0 ? cost : null;
}

export function addActualCost(total, additionalCost) {
  return additionalCost === null ? total : (total ?? 0) + additionalCost;
}

export function formatActualCost(amount, locale) {
  return new Intl.NumberFormat(locale, {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 3,
    maximumFractionDigits: 3,
  }).format(amount);
}
