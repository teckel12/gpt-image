const PIXELS_PER_MEGAPIXEL = 1_000_000;

export function estimateGenerationCost({
  outputWidth,
  outputHeight,
  outputPricePerMegapixel,
  inputImages,
  inputPricePerMegapixel,
  outputFrameCount = 1,
  additionalCost = 0,
}) {
  if (
    !Number.isFinite(outputWidth) ||
    outputWidth <= 0 ||
    !Number.isFinite(outputHeight) ||
    outputHeight <= 0 ||
    !Number.isFinite(outputPricePerMegapixel) ||
    outputPricePerMegapixel < 0 ||
    !Number.isFinite(inputPricePerMegapixel) ||
    inputPricePerMegapixel < 0 ||
    !Number.isInteger(outputFrameCount) ||
    outputFrameCount <= 0 ||
    !Number.isFinite(additionalCost) ||
    additionalCost < 0
  ) {
    return null;
  }

  const outputMultiplier = 1 + (outputFrameCount - 1) / 5;
  const outputCost =
    (outputWidth *
      outputHeight *
      outputPricePerMegapixel *
      outputMultiplier) /
    PIXELS_PER_MEGAPIXEL;
  let inputCost = 0;
  let pendingInputCount = 0;
  let unreadableInputCount = 0;

  for (const image of inputImages) {
    if (!image.dimensionsResolved) {
      pendingInputCount += 1;
    } else if (
      !Number.isFinite(image.width) ||
      image.width <= 0 ||
      !Number.isFinite(image.height) ||
      image.height <= 0
    ) {
      unreadableInputCount += 1;
    } else {
      inputCost +=
        (image.width * image.height * inputPricePerMegapixel) / PIXELS_PER_MEGAPIXEL;
    }
  }

  return {
    inputCost,
    outputCost,
    totalCost: inputCost + outputCost + additionalCost,
    pendingInputCount,
    unreadableInputCount,
  };
}
