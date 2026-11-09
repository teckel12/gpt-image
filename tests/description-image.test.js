import assert from "node:assert/strict";
import test from "node:test";

import {
  createDescriptionImageBlob,
  MAX_DESCRIPTION_PIXELS,
} from "../src/description-image.js";

function createBrowserEnvironment(sourceWidth, sourceHeight) {
  const state = {
    createdUrl: "",
    revokedUrl: "",
    canvasWidth: 0,
    canvasHeight: 0,
    drawDimensions: null,
  };
  class MockImage {
    naturalWidth = sourceWidth;
    naturalHeight = sourceHeight;

    async decode() {}
  }

  const environment = {
    ImageClass: MockImage,
    documentObject: {
      createElement(tagName) {
        assert.equal(tagName, "canvas");
        return {
          getContext(contextType) {
            assert.equal(contextType, "2d");
            return {
              drawImage(_image, _x, _y, width, height) {
                state.drawDimensions = [width, height];
              },
            };
          },
          toBlob(callback, type) {
            callback(new Blob(["description"], { type }));
          },
          set width(value) {
            state.canvasWidth = value;
          },
          set height(value) {
            state.canvasHeight = value;
          },
        };
      },
    },
    urlApi: {
      createObjectURL() {
        state.createdUrl = "blob:generated";
        return state.createdUrl;
      },
      revokeObjectURL(url) {
        state.revokedUrl = url;
      },
    },
  };
  return { environment, state };
}

test("keeps image dimensions below one megapixel without scaling", async () => {
  const { environment, state } = createBrowserEnvironment(800, 500);

  const descriptionBlob = await createDescriptionImageBlob(
    new Blob(["source"], { type: "image/svg+xml" }),
    environment,
  );

  assert.equal(state.canvasWidth, 800);
  assert.equal(state.canvasHeight, 500);
  assert.deepEqual(state.drawDimensions, [800, 500]);
  assert.equal(descriptionBlob.type, "image/png");
  assert.equal(state.revokedUrl, state.createdUrl);
});

test("scales images larger than one megapixel proportionally", async () => {
  const { environment, state } = createBrowserEnvironment(1600, 1000);

  await createDescriptionImageBlob(new Blob(["source"]), environment);

  assert.ok(state.canvasWidth * state.canvasHeight <= MAX_DESCRIPTION_PIXELS);
  assert.ok(Math.abs(state.canvasWidth / state.canvasHeight - 1.6) < 0.01);
  assert.deepEqual(state.drawDimensions, [state.canvasWidth, state.canvasHeight]);
  assert.equal(state.revokedUrl, state.createdUrl);
});

test("keeps extreme aspect ratios within one megapixel", async () => {
  const { environment, state } = createBrowserEnvironment(1, 2_000_000);

  await createDescriptionImageBlob(new Blob(["source"]), environment);

  assert.ok(state.canvasWidth * state.canvasHeight <= MAX_DESCRIPTION_PIXELS);
});
