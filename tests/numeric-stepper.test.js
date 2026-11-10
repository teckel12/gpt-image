import assert from "node:assert/strict";
import test from "node:test";

import { stepIntegerValue } from "../src/numeric-stepper.js";

test("steps integer values by configured increments within bounds", () => {
  const config = { min: 20, max: 2000, step: 20 };

  assert.equal(stepIntegerValue(200, 1, config), 220);
  assert.equal(stepIntegerValue(200, -1, config), 180);
  assert.equal(stepIntegerValue(2000, 1, config), 2000);
  assert.equal(stepIntegerValue(20, -1, config), 20);
});

test("steps invalid and off-increment values to nearest valid value in direction", () => {
  const config = { min: 20, max: 2000, step: 20 };

  assert.equal(stepIntegerValue(21, 1, config), 40);
  assert.equal(stepIntegerValue(21, -1, config), 20);
  assert.equal(stepIntegerValue("", 1, config), 20);
  assert.equal(stepIntegerValue(0, 1, config), 20);
});
