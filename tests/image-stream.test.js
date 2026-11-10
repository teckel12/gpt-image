import assert from "node:assert/strict";
import test from "node:test";

import {
  createPlaceholderImageBlob,
  consumeImageStream,
  imageBlobFromBase64,
} from "../src/image-stream.js";

function responseFromChunks(chunks) {
  const encoder = new TextEncoder();
  return new Response(
    new ReadableStream({
      start(controller) {
        for (const chunk of chunks) {
          controller.enqueue(encoder.encode(chunk));
        }
        controller.close();
      },
    }),
  );
}

test("consumes split partial and completion SSE events", async () => {
  const received = [];
  const response = responseFromChunks([
    'data: {"type":"partial_image","b64_json":"cHJldmlldw=="}\r\n',
    '\r\ndata: {"type":"completed","b64_json":"ZmluYWw=","cost":"0.02"}\r\n\r\n',
  ]);

  await consumeImageStream(response, (event) => received.push(event));

  assert.deepEqual(received, [
    { type: "partial_image", b64_json: "cHJldmlldw==" },
    { type: "completed", b64_json: "ZmluYWw=", cost: "0.02" },
  ]);
});

test("waits for each asynchronous event handler before dispatching the next event", async () => {
  let releaseFirstEvent;
  let secondEventReceived = false;
  const response = responseFromChunks([
    'data: {"type":"partial_image","b64_json":"cHJldmlldw=="}\n\n',
    'data: {"type":"completed","b64_json":"ZmluYWw="}\n\n',
  ]);
  const consuming = consumeImageStream(response, async (event) => {
    if (event.type === "partial_image") {
      await new Promise((resolve) => {
        releaseFirstEvent = resolve;
      });
    } else {
      secondEventReceived = true;
    }
  });

  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(secondEventReceived, false);
  releaseFirstEvent();
  await consuming;
  assert.equal(secondEventReceived, true);
});

test("reports stream errors and incomplete streams", async () => {
  await assert.rejects(
    consumeImageStream(
      responseFromChunks(['data: {"type":"error","error":"API failed"}\n\n']),
      () => {},
    ),
    /API failed/,
  );
  await assert.rejects(
    consumeImageStream(
      responseFromChunks(['data: {"type":"partial_image","b64_json":"cA=="}\n\n']),
      () => {},
    ),
    /final image arrived/,
  );
});

test("converts supported streamed images to typed blobs", async () => {
  const blob = imageBlobFromBase64("aW1hZ2U=", "png");

  assert.equal(blob.type, "image/png");
  assert.deepEqual(new Uint8Array(await blob.arrayBuffer()), new TextEncoder().encode("image"));
  assert.throws(() => imageBlobFromBase64("aW1hZ2U=", "gif"), /invalid image/);
});

test("creates output-sized blank placeholder blobs", async () => {
  const blob = createPlaceholderImageBlob(1024, 768);
  const source = await blob.text();

  assert.equal(blob.type, "image/svg+xml");
  assert.match(source, /width="1024" height="768"/);
  assert.throws(() => createPlaceholderImageBlob(0, 768), /positive integers/);
});
