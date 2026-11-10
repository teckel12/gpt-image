export function roundToNearestMultipleOf16(dimension) {
  return Math.max(16, Math.floor(dimension / 16 + 0.5) * 16);
}

export function parseResolution(resolution) {
  return resolution.split(/[x×]/).map((dimension) => Number(dimension.trim()));
}
