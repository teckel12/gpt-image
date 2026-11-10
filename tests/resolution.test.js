import assert from "node:assert/strict";
import test from "node:test";

import {
  formatMegapixels,
  roundToNearestMultipleOf16,
} from "../src/modules/resolution.js";

test("rounds image dimensions to the nearest multiple of 16", () => {
  assert.equal(roundToNearestMultipleOf16(1024), 1024);
  assert.equal(roundToNearestMultipleOf16(1025), 1024);
  assert.equal(roundToNearestMultipleOf16(1032), 1040);
  assert.equal(roundToNearestMultipleOf16(1), 16);
});

test("formats custom dimensions as megapixels to one decimal place", () => {
  assert.equal(formatMegapixels(1024, 1024), "1.0");
  assert.equal(formatMegapixels(1200, 1024), "1.2");
});
