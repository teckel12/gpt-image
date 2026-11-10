export function roundToNearestMultipleOf16(dimension) {
  return Math.max(16, Math.floor(dimension / 16 + 0.5) * 16);
}

export function formatMegapixels(width, height) {
  return ((width * height) / 1_000_000).toFixed(1);
}
