import assert from "node:assert/strict";
import test from "node:test";

import {
  addActualCost,
  formatActualCost,
  parseActualCost,
} from "../src/modules/actual-cost.js";

test("parses valid backend cost values and ignores missing or invalid values", () => {
  assert.equal(parseActualCost("0.0108"), 0.0108);
  assert.equal(parseActualCost("0"), 0);
  assert.equal(parseActualCost(null), null);
  assert.equal(parseActualCost(""), null);
  assert.equal(parseActualCost("invalid"), null);
});

test("adds available partial costs without inventing a zero-cost result", () => {
  assert.equal(addActualCost(null, null), null);
  assert.equal(addActualCost(null, 0.01), 0.01);
  assert.equal(addActualCost(0.01, 0.02), 0.03);
  assert.equal(addActualCost(0.01, null), 0.01);
});

test("formats actual cost to exactly three decimal places", () => {
  assert.equal(formatActualCost(0.005, "en-US"), "$0.005");
  assert.equal(formatActualCost(0.01, "en-US"), "$0.010");
});
