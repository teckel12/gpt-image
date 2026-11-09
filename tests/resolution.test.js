import assert from "node:assert/strict";
import test from "node:test";

import {
  parseResolution,
  roundToNearestMultipleOf16,
} from "../src/resolution.js";

test("rounds image dimensions to the nearest multiple of 16", () => {
  assert.equal(roundToNearestMultipleOf16(1024), 1024);
  assert.equal(roundToNearestMultipleOf16(1025), 1024);
  assert.equal(roundToNearestMultipleOf16(1032), 1040);
  assert.equal(roundToNearestMultipleOf16(1), 16);
});

test("parses display resolutions with either multiplication separator", () => {
  assert.deepEqual(parseResolution("1024 × 768"), [1024, 768]);
  assert.deepEqual(parseResolution("1024 x 768"), [1024, 768]);
});
