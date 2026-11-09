export const MAX_DESCRIPTION_PIXELS = 1_000_000;

export async function createDescriptionImageBlob(blob, environment = {}) {
  const ImageClass = environment.ImageClass ?? globalThis.Image;
  const documentObject = environment.documentObject ?? globalThis.document;
  const urlApi = environment.urlApi ?? globalThis.URL;
  const objectUrl = urlApi.createObjectURL(blob);

  try {
    const image = new ImageClass();
    image.src = objectUrl;
    await image.decode();

    const sourceWidth = image.naturalWidth;
    const sourceHeight = image.naturalHeight;
    const sourcePixels = sourceWidth * sourceHeight;
    if (
      !Number.isInteger(sourceWidth) ||
      !Number.isInteger(sourceHeight) ||
      sourceWidth < 1 ||
      sourceHeight < 1
    ) {
      throw new Error("Could not read generated image dimensions.");
    }

    const scale =
      sourcePixels > MAX_DESCRIPTION_PIXELS
        ? Math.sqrt(MAX_DESCRIPTION_PIXELS / sourcePixels)
        : 1;
    let width = Math.max(1, Math.floor(sourceWidth * scale));
    let height = Math.max(1, Math.floor(sourceHeight * scale));
    if (width * height > MAX_DESCRIPTION_PIXELS) {
      if (width > height) {
        width = Math.floor(MAX_DESCRIPTION_PIXELS / height);
      } else {
        height = Math.floor(MAX_DESCRIPTION_PIXELS / width);
      }
    }
    const canvas = documentObject.createElement("canvas");
    canvas.width = width;
    canvas.height = height;

    const context = canvas.getContext("2d");
    if (!context) {
      throw new Error("Could not prepare generated image for description.");
    }
    context.drawImage(image, 0, 0, width, height);

    return await new Promise((resolve, reject) => {
      canvas.toBlob(
        (descriptionBlob) => {
          if (descriptionBlob) {
            resolve(descriptionBlob);
          } else {
            reject(new Error("Could not encode generated image for description."));
          }
        },
        "image/png",
      );
    });
  } finally {
    urlApi.revokeObjectURL(objectUrl);
  }
}
