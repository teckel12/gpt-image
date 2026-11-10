export function stepNumericValue(value, direction, { min, max, step }) {
  const precision = Math.max(
    ...[min, max, step].map((number) => String(number).split(".")[1]?.length ?? 0),
  );
  const scale = 10 ** precision;
  const scaledMin = Math.round(min * scale);
  const scaledMax = Math.round(max * scale);
  const scaledStep = Math.round(step * scale);
  const scaledValue = Number.isFinite(value)
    ? Math.round(value * scale)
    : scaledMin;
  const stepIndex = (scaledValue - scaledMin) / scaledStep;
  const nextStepIndex =
    direction > 0 ? Math.floor(stepIndex) + 1 : Math.ceil(stepIndex) - 1;
  const nextValue = Math.min(
    scaledMax,
    Math.max(scaledMin, scaledMin + nextStepIndex * scaledStep),
  );
  return nextValue / scale;
}
