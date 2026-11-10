import assert from "node:assert/strict";
import test from "node:test";

import { stepNumericValue } from "../src/modules/numeric-stepper.js";

test("steps integer values by configured increments within bounds", () => {
  const config = { min: 20, max: 2000, step: 20 };

  assert.equal(stepNumericValue(200, 1, config), 220);
  assert.equal(stepNumericValue(200, -1, config), 180);
  assert.equal(stepNumericValue(2000, 1, config), 2000);
  assert.equal(stepNumericValue(20, -1, config), 20);
});

test("steps invalid and off-increment values to nearest valid value in direction", () => {
  const config = { min: 20, max: 2000, step: 20 };

  assert.equal(stepNumericValue(21, 1, config), 40);
  assert.equal(stepNumericValue(21, -1, config), 20);
  assert.equal(stepNumericValue("", 1, config), 40);
  assert.equal(stepNumericValue(0, 1, config), 20);
});

test("steps decimal values without floating-point drift", () => {
  const config = { min: 0.7, max: 3.6, step: 0.1 };

  assert.equal(stepNumericValue(1, 1, config), 1.1);
  assert.equal(stepNumericValue(1.1, -1, config), 1);
  assert.equal(stepNumericValue(3.6, 1, config), 3.6);
  assert.equal(stepNumericValue(0.7, -1, config), 0.7);
});
