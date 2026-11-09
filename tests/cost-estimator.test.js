import assert from "node:assert/strict";
import test from "node:test";

import { estimateGenerationCost } from "../src/cost-estimator.js";

test("estimates output and all input image costs from pixel dimensions", () => {
  const estimate = estimateGenerationCost({
    outputWidth: 1024,
    outputHeight: 1024,
    outputPricePerMegapixel: 0.12,
    inputImages: [
      { width: 1000, height: 1000, dimensionsResolved: true },
      { width: 2000, height: 1000, dimensionsResolved: true },
    ],
    inputPricePerMegapixel: 0.01,
  });

  assert.equal(estimate.outputCost, 0.12582912);
  assert.equal(estimate.inputCost, 0.03);
  assert.equal(estimate.totalCost, 0.15582912);
  assert.equal(estimate.pendingInputCount, 0);
  assert.equal(estimate.unreadableInputCount, 0);
});

test("reports pending and unreadable input dimensions without hiding output cost", () => {
  const estimate = estimateGenerationCost({
    outputWidth: 1000,
    outputHeight: 1000,
    outputPricePerMegapixel: 0.02,
    inputImages: [
      { width: 500, height: 500, dimensionsResolved: true },
      { width: null, height: null, dimensionsResolved: false },
      { width: null, height: null, dimensionsResolved: true },
    ],
    inputPricePerMegapixel: 0.01,
  });

  assert.equal(estimate.outputCost, 0.02);
  assert.equal(estimate.inputCost, 0.0025);
  assert.equal(estimate.totalCost, 0.0225);
  assert.equal(estimate.pendingInputCount, 1);
  assert.equal(estimate.unreadableInputCount, 1);
});

test("estimates output-only generations without adding input-image cost", () => {
  const estimate = estimateGenerationCost({
    outputWidth: 1000,
    outputHeight: 1000,
    outputPricePerMegapixel: 0.02,
    inputImages: [],
    inputPricePerMegapixel: 0.01,
  });

  assert.equal(estimate.inputCost, 0);
  assert.equal(estimate.totalCost, estimate.outputCost);
});

test("prices nine animated GIF frames at twice single-frame cost", () => {
  const estimate = estimateGenerationCost({
    outputWidth: 1000,
    outputHeight: 1000,
    outputPricePerMegapixel: 0.02,
    inputImages: [{ width: 1000, height: 1000, dimensionsResolved: true }],
    inputPricePerMegapixel: 0.01,
    outputFrameCount: 9,
  });

  assert.equal(estimate.outputCost, 0.04);
  assert.equal(estimate.inputCost, 0.01);
  assert.equal(estimate.totalCost, 0.05);
});

test("returns null for invalid output or rate values", () => {
  assert.equal(
    estimateGenerationCost({
      outputWidth: 0,
      outputHeight: 1000,
      outputPricePerMegapixel: 0.02,
      inputImages: [],
      inputPricePerMegapixel: 0.01,
    }),
    null,
  );
});
