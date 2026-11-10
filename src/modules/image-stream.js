const IMAGE_MIME_TYPES = {
  jpeg: "image/jpeg",
  png: "image/png",
  webp: "image/webp",
};

export function imageBlobFromBase64(encodedImage, outputFormat) {
  const mimeType = IMAGE_MIME_TYPES[outputFormat];
  if (!mimeType || typeof encodedImage !== "string") {
    throw new Error("Image stream returned an invalid image.");
  }

  const binary = atob(encodedImage);
  const bytes = Uint8Array.from(binary, (character) => character.charCodeAt(0));
  return new Blob([bytes], { type: mimeType });
}

export function createPlaceholderImageBlob(width, height) {
  if (!Number.isInteger(width) || width <= 0 || !Number.isInteger(height) || height <= 0) {
    throw new Error("Image placeholder dimensions must be positive integers.");
  }
  const svg =
    `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" ` +
    `viewBox="0 0 ${width} ${height}"><rect width="100%" height="100%" fill="#e9edf4"/></svg>`;
  return new Blob([svg], { type: "image/svg+xml" });
}

export async function consumeImageStream(response, onEvent) {
  if (!response.body) {
    throw new Error("Image stream did not include a response body.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let completed = false;

  const dispatchFrame = async (frame) => {
    const data = frame
      .split(/\r?\n/)
      .filter((line) => line.startsWith("data:"))
      .map((line) => line.slice(5).replace(/^ /, ""))
      .join("\n");
    if (!data) {
      return;
    }

    let event;
    try {
      event = JSON.parse(data);
    } catch {
      throw new Error("Image stream returned invalid event data.");
    }
    if (event.type === "error") {
      throw new Error(event.error || "Image streaming failed.");
    }
    if (
      !["partial_image", "completed"].includes(event.type) ||
      typeof event.b64_json !== "string"
    ) {
      throw new Error("Image stream returned an unsupported event.");
    }

    await onEvent(event);
    completed = event.type === "completed" || completed;
  };

  try {
    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value, { stream: !done });
      let boundary = /\r?\n\r?\n/.exec(buffer);
      while (boundary) {
        await dispatchFrame(buffer.slice(0, boundary.index));
        buffer = buffer.slice(boundary.index + boundary[0].length);
        boundary = /\r?\n\r?\n/.exec(buffer);
      }
      if (done) {
        if (buffer.trim()) {
          await dispatchFrame(buffer);
        }
        break;
      }
    }
  } catch (error) {
    await reader.cancel(error);
    throw error;
  } finally {
    reader.releaseLock();
  }

  if (!completed) {
    throw new Error("Image stream ended before the final image arrived.");
  }
}
