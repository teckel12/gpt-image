export function stepIntegerValue(value, direction, { min, max, step }) {
  if (!Number.isInteger(value)) {
    return min;
  }
  const stepIndex = (value - min) / step;
  const nextStepIndex =
    direction > 0 ? Math.floor(stepIndex) + 1 : Math.ceil(stepIndex) - 1;
  return Math.min(max, Math.max(min, min + nextStepIndex * step));
}
