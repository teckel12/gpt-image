<template>
  <main class="page">
    <section class="panel" aria-labelledby="page-title">
      <header class="page-header">
        <h1 id="page-title">
          GPT Image Generator
          <button
            type="button"
            class="reset-button"
            title="Reset all form fields to default"
            :disabled="loading || !formChanged"
            @click="resetForm"
          >
            <i-mdi-arrow-u-left-top-bold class="mdi-icon" />
            <span>Reset</span>
          </button>
        </h1>
        <p class="intro">
          Generate an image from a prompt, optionally using input images.
        </p>
      </header>

      <form class="form" @submit.prevent="submitForm">
        <fieldset class="form-fields" :disabled="!backendReady">
          <p v-if="error" class="message error" role="alert">{{ error }}</p>

          <fieldset class="field-group">
            <label class="field">
              <span>Input Images (optional)</span>
              <div
                class="image-drop-zone"
                :class="{ 'is-dragging': isDragging }"
                @dragenter="handleDragEnter"
                @dragleave="handleDragLeave"
                @dragover="handleDragOver"
                @drop="handleDrop"
              >
                <label class="file-picker">
                  <span><i-mdi-image-plus class="mdi-icon" /> Add Images</span>
                  <input
                    type="file"
                    accept="image/png,image/jpeg,image/webp,image/gif"
                    multiple
                    title="Select one or more images to upload"
                    @change="updateImages"
                  />
                </label>
                <p class="drop-hint">
                  Drag and drop images here. Supported formats: PNG, JPEG, WebP, GIF
                </p>
              </div>
            </label>
            <ul v-if="form.images.length" class="image-list">
              <li
                v-for="(image, index) in form.images"
                :key="image.previewUrl"
                class="image-card visible"
                :aria-label="`Image ${index + 1}: ${image.file.name}`"
              >
                <strong class="image-label">Image {{ index + 1 }}</strong>
                <i-mdi-trash-can
                  class="mdi-icon remove-image"
                  :aria-label="`Remove Image ${index + 1}: ${image.file.name}`"
                  @click="removeImage(index)"
                />
                <img
                  class="image-preview"
                  :src="image.previewUrl"
                  :alt="`Preview of Image ${index + 1}: ${image.file.name}`"
                  @load="handleImagePreviewLoad(image, $event)"
                  @error="handleImagePreviewError(image)"
                />
                <code class="image-name">{{ image.file.name }}</code>
                <div class="image-resolution">
                  <input
                    class="resolution-selector"
                    type="checkbox"
                    title="Use this image's resolution for output"
                    :checked="form.resolutionImageId === image.previewUrl"
                    :disabled="!image.width || !image.height"
                    :aria-label="`Use Image ${index + 1} resolution for output`"
                    @change="toggleResolutionImage(image, $event)"
                  />
                  <span v-if="image.width && image.height">
                    {{ image.width }} × {{ image.height }}
                  </span>
                  <span v-else-if="image.dimensionsResolved">
                    Resolution unavailable
                  </span>
                  <span v-else>Reading resolution...</span>
                </div>
              </li>
            </ul>
          </fieldset>

          <label class="field">
            <span>Prompt
              <span v-if="form.prompt.trim().length === 0" class="error">
                (required)
              </span>
            </span>
            <textarea
              v-model="form.prompt"
              title="Enter your prompt"
              rows="6"
              required
              placeholder="Describe what you want to create or change..."
            />
          </label>

          <div class="field-row">
            <label class="field">
              <span>GPT Image Model</span>
              <select
                v-model="form.model"
                title="Select the GPT Image model to use"
                required
                @change="updateModel"
              >
                <option v-for="model in models" :key="model.value" :value="model.value">
                  {{ model.display_name }} ({{ model.description }})
                </option>
              </select>
            </label>
            <label class="field">
              <span>Quality</span>
              <select
                v-model="form.quality"
                title="Select the desired output image quality"
                required
              >
                <option v-for="quality in qualities" :key="quality" :value="quality">
                  {{ quality.charAt(0).toUpperCase() + quality.slice(1) }}
                </option>
              </select>
            </label>
          </div>

          <div
            class="field-row field-row-animation"
            :class="{ 'is-hidden': Boolean(selectedResolutionImage) }"
          >
            <label class="field">
              <span>Aspect Ratio</span>
              <select
                v-model="form.aspectRatio"
                title="Select the desired aspect ratio for the output image"
                required
                :disabled="Boolean(selectedResolutionImage)"
              >
                <option
                  v-for="ratio in aspectRatios"
                  :key="ratio.value"
                  :value="ratio.value"
                >
                  {{ ratio.label }}
                </option>
                <option value="specify">Specify Resolution</option>
              </select>
            </label>
            <div class="field">
              <label for="megapixels"><span>Megapixels</span></label>
              <NumericStepper
                id="megapixels"
                :model-value="megapixelsValue"
                @update:model-value="form.megapixels = $event"
                label="megapixels"
                :mask="megapixelMask"
                :min="0.7"
                :max="3.6"
                :step="0.1"
                inputmode="decimal"
                pattern="(?:0\.[7-9]|[1-2](?:\.[0-9])?|3(?:\.[0-6])?)"
                title="Enter a value from 0.7 to 3.6 with at most one decimal place."
                required
                :disabled="isSpecifyResolution || Boolean(selectedResolutionImage)"
              />
            </div>
          </div>
          <div
            class="field-row"
            :class="{ 'hide-one-row': Boolean(selectedResolutionImage) }"
          >
            <div class="field">
              <label for="output-image-width"><span>Output Image Width</span></label>
              <NumericStepper
                id="output-image-width"
                :model-value="resolution[0] ?? ''"
                @update:model-value="form.outputImageWidth = $event"
                label="output image width"
                mask="####"
                :min="512"
                :max="3008"
                :step="16"
                title="Enter a width from 512 to 3008 pixels in increments of 16."
                required
                :disabled="!isSpecifyResolution || Boolean(selectedResolutionImage)"
              />
            </div>
            <div class="field">
              <label for="output-image-height"><span>Output Image Height</span></label>
              <NumericStepper
                id="output-image-height"
                :model-value="resolution[1] ?? ''"
                @update:model-value="form.outputImageHeight = $event"
                label="output image height"
                mask="####"
                :min="512"
                :max="3008"
                :step="16"
                title="Enter a height from 512 to 3008 pixels in increments of 16."
                required
                :disabled="!isSpecifyResolution || Boolean(selectedResolutionImage)"
              />
            </div>
          </div>
          <p
            v-if="resolutionError"
            class="resolution field-error"
            role="alert"
            :class="{ 'hide-one-row': Boolean(selectedResolutionImage) }"
          >
            {{ resolutionError }}
          </p>

          <div class="field-row">
            <label class="field">
              <span>Output Image Format</span>
              <select
                v-model="form.outputFormat"
                title="Select the desired output image format"
                required
                @change="updateOutputFormat"
              >
                <option value="png">PNG</option>
                <option value="jpeg">JPEG</option>
                <option value="webp">WebP</option>
                <option value="gif" :disabled="!outputFormats.includes('gif')">GIF</option>
                <option
                  value="animated-gif"
                  :disabled="!outputFormats.includes('gif')"
                >
                  GIF (animated)
                </option>
                <option
                  value="svg"
                  :disabled="!outputFormats.includes('svg') || form.images.length > 0"
                >
                  SVG
                </option>
              </select>
            </label>
            <div class="field">
              <label for="output-compression"><span>Compression Quality</span></label>
              <NumericStepper
                id="output-compression"
                v-model="form.outputCompression"
                label="compression quality"
                :mask="integerFieldConfig.outputCompression.mask"
                :min="integerFieldConfig.outputCompression.min"
                :max="integerFieldConfig.outputCompression.max"
                :step="integerFieldConfig.outputCompression.step"
                title="Enter an integer from 1 to 100; higher values mean better quality"
                :required="compressionSupported"
                :disabled="!compressionSupported"
              />
            </div>
          </div>

          <div
            class="field-row field-row-animation"
            :class="{ 'is-hidden': !animationOptionsSupported }"
          >
            <div class="field">
              <label for="frame-count"><span>Frame Count</span></label>
              <NumericStepper
                id="frame-count"
                v-model="form.frameCount"
                label="frame count"
                :mask="integerFieldConfig.frameCount.mask"
                :min="integerFieldConfig.frameCount.min"
                :max="integerFieldConfig.frameCount.max"
                :step="integerFieldConfig.frameCount.step"
                title="Enter a value between 1 and 100"
                :disabled="!animationOptionsSupported"
                :required="animationOptionsSupported"
              />
            </div>
            <div class="field">
              <label for="frame-duration-ms"><span>Frame Duration (ms)</span></label>
              <NumericStepper
                id="frame-duration-ms"
                v-model="form.frameDurationMs"
                label="frame duration"
                :mask="integerFieldConfig.frameDurationMs.mask"
                :min="integerFieldConfig.frameDurationMs.min"
                :max="integerFieldConfig.frameDurationMs.max"
                :step="integerFieldConfig.frameDurationMs.step"
                title="Enter a value between 20 and 2000 milliseconds"
                :disabled="!animationOptionsSupported"
                :required="animationOptionsSupported"
              />
            </div>
          </div>

          <p v-if="frameCountError" class="field-error" role="alert">
            {{ frameCountError }}
          </p>
          <p v-if="frameDurationError" class="field-error" role="alert">
            {{ frameDurationError }}
          </p>
          <p v-if="outputCompressionError" class="field-error" role="alert">
            {{ outputCompressionError }}
          </p>

          <div
            class="check-row field-row-animation"
            :class="{ 'hide-one-row': !animationOptionsSupported }"
          >
            <label
              class="check-field"
              :class="{ 'is-disabled': !transparentBackgroundSupported }"
            >
              <input
                v-model="form.transparentBackground"
                type="checkbox"
                title="Generate image with transparent background"
                :disabled="!transparentBackgroundSupported"
              />
              <span>Transparent Background</span>
            </label>
            <label
              class="check-field"
              :class="{ 'is-disabled': !streamingSupported }"
            >
              <input
                v-model="form.streamPartialImages"
                type="checkbox"
                title="Preview the image as it's being generated"
                :disabled="!streamingSupported"
              />
              <span>Preview Rendering Process</span>
            </label>
          </div>

          <button
            type="submit"
            title="Generate the image with the specified options"
            :disabled=submitDisabled
          >
            <i-mdi-image
              v-if="!loading"
              class="mdi-icon"
            />
            {{
              loading
                ? generatedImage?.descriptionPending
                  ? "Generating Description..."
                  : "Generating Image..."
                : "Generate Image" + (costEstimate && !submitDisabled ? " ~" + formatCurrency(costEstimate.totalCost, 2) : "")
            }}
          </button>
          <p v-if="generationError" class="message error" role="alert">
            {{ generationError }}
          </p>
          <p
            v-if="elapsedSeconds !== null && !(generatedImage && !generatedImage.generationPending && !generatedImage.descriptionPending)"
            class="generation-timer"
            role="timer"
            aria-live="off"
          >
            Generating image: {{ elapsedSeconds.toFixed(1) }} seconds
          </p>

          <div
            v-if="generatedImage"
            id="generated-result"
            class="generated-result"
          >
            <p v-if="!generatedImage.generationPending" class="message success" role="status">
              <code>{{ generatedImage.filename }}</code>
              <span v-if="generatedImage.elapsedSeconds !== null">
                ({{ generatedImage.elapsedSeconds.toFixed(1) }} seconds<span
                  v-if="generatedImage.cost !== null"
                  >, {{ formatActualCost(generatedImage.cost) }}</span
                >)
              </span>
            </p>
            <p v-else-if="generatedImage.descriptionError" class="message error" role="alert">
              {{ generatedImage.descriptionError }}
            </p>

            <img
              ref="generatedImagePreview"
              class="generated-image"
              :class="{
                'is-partial-preview':
                  generatedImage.isPartialPreview && generatedImage.generationPending,
              }"
              :src="generatedImage.url"
              :alt="
                generatedImage.generationPending
                  ? 'Image generation preview'
                  : 'Generated image'
              "
              @click="openFullscreen"
            />
            <div class="generated-actions">
              <button
                ref="fullscreenButton"
                type="button"
                :disabled="generatedImage.generationPending"
                @click="openFullscreen"
              >
                <i-mdi-magnify-plus class="mdi-icon" />
                Zoom
              </button>
              <button
                type="button"
                :disabled="
                  generatedImage.generationPending ||
                  generatedImage.descriptionPending ||
                  generatedImage.streamingPending
                "
                @click="downloadImage"
              >
                <i-mdi-download class="mdi-icon" />
                Download
              </button>
              <button
                type="button"
                :disabled="
                  generatedImage.generationPending ||
                  generatedImage.descriptionPending ||
                  generatedImage.streamingPending ||
                  generatedImage.format === 'svg'
                "
                @click="addGeneratedImageAsInput"
              >
                <i-mdi-image-plus class="mdi-icon" />
                Add as Input Image
              </button>
            </div>
            <small v-if="generatedImage.format === 'svg'">
              SVG output cannot be used as an input image.
            </small>
          </div>
        </fieldset>
      </form>

      <p v-if="loadingOptions" class="loading-note">Loading supported options...</p>
    </section>
    <div
      v-if="showFullscreen"
      ref="imageModal"
      class="image-modal"
      role="dialog"
      aria-modal="true"
      aria-label="Full-screen generated image"
      tabindex="-1"
      @click.self="closeFullscreen"
      @keydown.esc.prevent="closeFullscreen"
    >
      <button
        class="image-modal-close"
        type="button"
        aria-label="Close full-screen image"
        @click="closeFullscreen"
      >
        <i-mdi-close-thick class="mdi-icon" />
        Close
      </button>
      <img :src="generatedImage.url" alt="Generated image full screen" />
    </div>
  </main>
</template>

<script>
import {
  addActualCost,
  formatActualCost,
  parseActualCost,
} from "./modules/actual-cost.js";
import {
  createPlaceholderImageBlob,
  consumeImageStream,
  imageBlobFromBase64,
} from "./modules/image-stream.js";
import { estimateGenerationCost } from "./modules/cost-estimator.js";
import { createDescriptionImageBlob } from "./modules/description-image.js";
import {
  formatMegapixels,
  roundToNearestMultipleOf16,
} from "./modules/resolution.js";
import NumericStepper from "./components/NumericStepper.vue";

const MAX_EDGE = 3840;
const MIN_PIXELS = 655360;
const MAX_PIXELS = 3686400;
const SUPPORTED_IMAGE_EXTENSIONS = new Set(["png", "jpg", "jpeg", "webp", "gif"]);
const INTEGER_FIELD_CONFIG = {
  outputCompression: { min: 1, max: 100, step: 1, mask: "###" },
  frameCount: { min: 2, max: 16, step: 1, mask: "##" },
  frameDurationMs: { min: 20, max: 2000, step: 20, mask: "####" },
};
const MEGAPIXEL_MASK = {
  mask: (value) => value.split(".")[0].length > 1 ? "#" : "#.d",
  tokens: {
    d: { pattern: /[0-9]/, optional: true },
  },
};
const DEFAULT_FORM_VALUES = {
  images: [],
  prompt: "",
  model: "",
  quality: "",
  aspectRatio: "",
  megapixels: 1.0,
  outputImageWidth: 1024,
  outputImageHeight: 1024,
  resolutionImageId: null,
  outputFormat: "png",
  outputCompression: 90,
  frameCount: 9,
  frameDurationMs: 200,
  transparentBackground: false,
  streamPartialImages: false,
  generateDescription: true,
};

const createDefaultForm = (overrides = {}) => ({
  ...DEFAULT_FORM_VALUES,
  ...overrides,
  images: [],
});

export default {
  components: {
    NumericStepper,
  },
  data() {
    return {
      models: [],
      aspectRatios: [],
      megapixelMask: MEGAPIXEL_MASK,
      integerFieldConfig: INTEGER_FIELD_CONFIG,
      inputImageCostPerMegapixel: 0,
      loadingOptions: true,
      loading: false,
      elapsedSeconds: null,
      generationTimerId: null,
      generationStartedAt: null,
      backendReady: false,
      error: "",
      generationError: "",
      generatedImage: null,
      showFullscreen: false,
      isDragging: false,
      dragDepth: 0,
      form: createDefaultForm(),
    };
  },
  watch: {
    "form.aspectRatio"(newValue, oldValue) {
      if (newValue === "specify" || (!this.isSpecifyResolution && oldValue === "specify")) {
        this.form.megapixels = 1.0;
      }
    },
  },
  computed: {
    isSpecifyResolution() {
      return this.form.aspectRatio === "specify";
    },
    selectedResolutionImage() {
      return (
        this.form.images.find(
          (image) => image.previewUrl === this.form.resolutionImageId,
        ) ?? null
      );
    },
    selectedModel() {
      return this.models.find((model) => model.value === this.form.model) ?? {};
    },
    qualities() {
      return this.selectedModel.qualities ?? [];
    },
    outputFormats() {
      return this.selectedModel.output_formats ?? [];
    },
    apiOutputFormat() {
      return this.form.outputFormat === "animated-gif"
        ? "gif"
        : this.form.outputFormat;
    },
    compressionSupported() {
      return ["jpeg", "webp"].includes(this.form.outputFormat);
    },
    transparentBackgroundSupported() {
      return ["png", "webp"].includes(this.form.outputFormat);
    },
    animationOptionsSupported() {
      return (
        this.form.outputFormat === "animated-gif" &&
        this.outputFormats.includes("gif")
      );
    },
    streamingSupported() {
      return !["gif", "animated-gif", "svg"].includes(this.form.outputFormat);
    },
    frameCountError() {
      const { min, max } = this.integerFieldConfig.frameCount;
      if (
        this.animationOptionsSupported &&
        (!Number.isInteger(this.form.frameCount) ||
          this.form.frameCount < min ||
          this.form.frameCount > max)
      ) {
        return `Frame count must be an integer from ${min} to ${max}.`;
      }
      return "";
    },
    frameDurationError() {
      const { min, max, step } = this.integerFieldConfig.frameDurationMs;
      if (
        this.animationOptionsSupported &&
        (!Number.isInteger(this.form.frameDurationMs) ||
          this.form.frameDurationMs < min ||
          this.form.frameDurationMs > max ||
          (this.form.frameDurationMs - min) % step !== 0)
      ) {
        return `Frame duration must be an integer from ${min} to ${max} ms in increments of ${step} ms.`;
      }
      return "";
    },
    outputCompressionError() {
      const { min, max } = this.integerFieldConfig.outputCompression;
      if (
        this.compressionSupported &&
        (!Number.isInteger(this.form.outputCompression) ||
          this.form.outputCompression < min ||
          this.form.outputCompression > max)
      ) {
        return `Image compression must be an integer from ${min} to ${max}.`;
      }
      return "";
    },
    megapixelsValue() {
      return this.isSpecifyResolution
        ? formatMegapixels(this.form.outputImageWidth, this.form.outputImageHeight)
        : this.form.megapixels;
    },
    resolution() {
      if (this.selectedResolutionImage) {
        const { width, height } = this.selectedResolutionImage;
        if (!width || !height) {
          return [];
        }
        return [roundToNearestMultipleOf16(width), roundToNearestMultipleOf16(height)];
      }

      if (this.isSpecifyResolution) {
        const width = Number(this.form.outputImageWidth);
        const height = Number(this.form.outputImageHeight);
        if (!Number.isFinite(width) || !Number.isFinite(height)) {
          return [];
        }
        return [width, height];
      }

      if (
        !this.form.aspectRatio ||
        !Number.isFinite(Number(this.megapixelsValue)) ||
        Number(this.megapixelsValue) <= 0
      ) {
        return [];
      }

      const [ratioWidth, ratioHeight] = this.form.aspectRatio.split(":").map(Number);
      const targetPixels = Number(this.megapixelsValue) * 1_000_000;
      const width = Math.max(
        16,
        Math.floor(Math.sqrt(targetPixels * (ratioWidth / ratioHeight)) / 16 + 0.5) * 16,
      );
      const height = Math.max(
        16,
        Math.floor(Math.sqrt(targetPixels * (ratioHeight / ratioWidth)) / 16 + 0.5) * 16,
      );
      return [width, height];
    },
    resolutionError() {
      if (!this.resolution) {
        if (this.selectedResolutionImage) {
          return "Selected image resolution is unavailable.";
        }
        return this.isSpecifyResolution
          ? "Output width and height must be integers."
          : "Megapixels must be a positive number.";
      }
      const [width, height] = this.resolution;
      const pixels = width * height;
      const selectedImage = Boolean(this.selectedResolutionImage);
      if (
        this.isSpecifyResolution &&
        (width < 512 || width > 3008 || height < 512 || height > 3008)
      ) {
        return "Output width and height must be from 512 to 3008 pixels.";
      }
      if (width % 16 || height % 16) {
        return "Output width and height must be multiples of 16.";
      }
      if (pixels < MIN_PIXELS) {
        if (selectedImage) {
          return "Selected image resolution is below the minimum supported size of 655,360 pixels. Choose a larger image or clear the selection.";
        }
        if (this.isSpecifyResolution) {
          return "Specified resolution is below the minimum supported size of 655,360 pixels. Increase output width or height.";
        }
        return "Computed resolution is below the minimum supported size of 655,360 pixels. Increase megapixels.";
      }
      if (
        width > MAX_EDGE ||
        height > MAX_EDGE ||
        pixels > MAX_PIXELS ||
        width / height < 1 / 3 ||
        width / height > 3
      ) {
        if (selectedImage) {
          return "Selected image resolution exceeds supported image limits. Choose a smaller image or clear the selection.";
        }
        if (this.isSpecifyResolution) {
          return "Specified resolution exceeds supported image limits. Decrease output width or height.";
        }
        return "Computed resolution exceeds the maximum supported size of 3,686,400 pixels. Decrease megapixels.";
      }
      return "";
    },
    costEstimate() {
      const outputPricePerMegapixel =
        this.selectedModel.quality_price_per_megapixel?.[this.form.quality];
      if (!this.resolution || this.resolutionError || !outputPricePerMegapixel) {
        return null;
      }

      const [outputWidth, outputHeight] = this.resolution;
      return estimateGenerationCost({
        outputWidth,
        outputHeight,
        outputPricePerMegapixel,
        inputImages: this.form.images,
        inputPricePerMegapixel: this.inputImageCostPerMegapixel,
        outputFrameCount: this.animationOptionsSupported ? this.form.frameCount : 1,
        additionalCost: this.form.streamPartialImages ? 0.009 : 0,
      });
    },
    submitDisabled() {
      return (
        this.loading ||
        !this.form.prompt.trim() ||
        !this.resolution ||
        Boolean(this.resolutionError) ||
        Boolean(this.frameCountError) ||
        Boolean(this.frameDurationError) ||
        Boolean(this.outputCompressionError)
      )
    },
    formChanged() {
      return JSON.stringify(this.form) !== JSON.stringify(createDefaultForm({
        model: this.models[0]?.value ?? "",
        quality: this.models[0]?.qualities[1] ?? this.models[0]?.qualities[0] ?? "",
        aspectRatio: this.aspectRatios[0]?.value ?? "",
      }));
    },
  },
  async mounted() {
    try {
      const response = await fetch("/api/options");
      if (!response.ok) {
        throw new Error(
          `Backend not available. Start the backend with ./backend.sh.`,
        );
      }
      const options = await response.json();
      this.models = options.models;
      this.aspectRatios = options.aspect_ratios;
      this.inputImageCostPerMegapixel = options.input_image_cost_per_megapixel;
      this.form.model = this.models[0]?.value ?? "";
      this.form.quality = this.models[0]?.qualities[1] ?? this.models[0]?.qualities[0] ?? "";
      this.form.aspectRatio = this.aspectRatios[0]?.value ?? "";
      this.backendReady = true;
    } catch (error) {
      this.error =
        error instanceof TypeError
          ? "Could not connect to the Flask API. Start ./backend.sh, then reload the page."
          : error.message;
    } finally {
      this.loadingOptions = false;
    }
  },
  beforeUnmount() {
    this.stopGenerationTimer();
    this.releasePreviews();
    this.clearGeneratedImage();
  },
  methods: {
    resetForm() {
      if (!this.backendReady || !this.confirmGeneratedImageReplacement()) {
        return;
      }
      this.stopGenerationTimer();
      this.releasePreviews();
      // this.clearGeneratedImage();
      const defaultModel = this.models[0];
      this.form = createDefaultForm({
        model: defaultModel?.value ?? "",
        quality: defaultModel?.qualities[1] ?? defaultModel?.qualities[0] ?? "",
        aspectRatio: this.aspectRatios[0]?.value ?? "",
      });
      this.error = "";
      this.generationError = "";
      this.elapsedSeconds = null;
      this.isDragging = false;
      this.dragDepth = 0;
    },
    updateImages(event) {
      const input = event.target;
      this.setImages(Array.from(input.files ?? []), true);
      input.value = "";
    },
    isSupportedImage(file) {
      const extensionIndex = file.name.lastIndexOf(".");
      const extension = file.name.slice(extensionIndex + 1).toLowerCase();
      return extensionIndex > 0 && SUPPORTED_IMAGE_EXTENSIONS.has(extension);
    },
    setImages(files, append) {
      const supportedFiles = files.filter((file) => this.isSupportedImage(file));
      const unsupportedFiles = files.filter((file) => !this.isSupportedImage(file));
      if (supportedFiles.length) {
        const newImages = supportedFiles.map((file) => ({
          file,
          previewUrl: URL.createObjectURL(file),
          width: null,
          height: null,
          dimensionsResolved: false,
        }));
        if (append) {
          this.form.images = [...this.form.images, ...newImages];
        } else {
          this.releasePreviews();
          this.form.images = newImages;
          this.form.resolutionImageId = null;
        }
      }
      if (this.form.images.length && this.form.outputFormat === "svg") {
        this.form.outputFormat = "png";
      }
      this.error = unsupportedFiles.length
        ? `Skipped unsupported image file${unsupportedFiles.length === 1 ? "" : "s"}: ${unsupportedFiles.map((file) => file.name).join(", ")}. Use PNG, JPEG, WebP, or GIF.`
        : "";
    },
    releasePreviews() {
      for (const image of this.form.images) {
        URL.revokeObjectURL(image.previewUrl);
      }
    },
    handleImagePreviewLoad(image, event) {
      const preview = event.target;
      image.width = preview.naturalWidth;
      image.height = preview.naturalHeight;
      image.dimensionsResolved = true;
    },
    handleImagePreviewError(image) {
      image.width = null;
      image.height = null;
      image.dimensionsResolved = true;
    },
    toggleResolutionImage(image, event) {
      this.form.resolutionImageId = event.target.checked
        ? image.previewUrl
        : null;
    },
    removeImage(index) {
      const [removedImage] = this.form.images.splice(index, 1);
      if (removedImage) {
        URL.revokeObjectURL(removedImage.previewUrl);
        if (this.form.resolutionImageId === removedImage.previewUrl) {
          this.form.resolutionImageId = null;
        }
        this.error = "";
      }
    },
    updateOutputFormat() {
      if (!this.transparentBackgroundSupported) {
        this.form.transparentBackground = false;
      }
      if (!this.streamingSupported) {
        this.form.streamPartialImages = false;
      }
    },
    updateModel() {
      if (!this.outputFormats.includes(this.apiOutputFormat)) {
        this.form.outputFormat = "png";
      }
      this.form.quality = this.qualities.includes(this.form.quality)
        ? this.form.quality
        : this.qualities[1] ?? this.qualities[0] ?? "";
      this.updateOutputFormat();
    },
    addGeneratedImageAsInput() {
      if (
        !this.generatedImage ||
        this.generatedImage.format === "svg"
      ) {
        return;
      }
      const file = new File([this.generatedImage.blob], this.generatedImage.filename, {
        type: this.generatedImage.blob.type,
      });
      this.setImages([file], true);
    },
    confirmGeneratedImageReplacement() {
      if (!this.generatedImage || this.generatedImage.downloaded) {
        return true;
      }
      return window.confirm(
        "The current generated image has not been downloaded. Continuing will erase it. Continue?",
      );
    },
    clearGeneratedImage() {
      if (this.generatedImage) {
        URL.revokeObjectURL(this.generatedImage.url);
        this.generatedImage = null;
      }
      this.showFullscreen = false;
    },
    async createLoadedImageUrl(blob) {
      const url = URL.createObjectURL(blob);
      try {
        const image = new Image();
        image.src = url;
        await image.decode();
        return url;
      } catch (error) {
        URL.revokeObjectURL(url);
        throw error;
      }
    },
    async updateGeneratedImagePreview(blob, updates = {}, waitForPaint = false) {
      const url = await this.createLoadedImageUrl(blob);
      const previousUrl = this.generatedImage?.url;
      this.generatedImage = {
        ...this.generatedImage,
        ...updates,
        blob,
        url,
      };
      if (previousUrl) {
        URL.revokeObjectURL(previousUrl);
      }
      await this.$nextTick();
      if (waitForPaint) {
        await new Promise((resolve) => {
          window.requestAnimationFrame(() =>
            window.requestAnimationFrame(resolve),
          );
        });
      }
    },
    isFileDrag(event) {
      return Array.from(event.dataTransfer?.types ?? []).includes("Files");
    },
    handleDragEnter(event) {
      if (this.backendReady && this.isFileDrag(event)) {
        this.dragDepth += 1;
        this.isDragging = true;
      }
    },
    handleDragLeave(event) {
      if (this.backendReady && this.isFileDrag(event)) {
        this.dragDepth = Math.max(0, this.dragDepth - 1);
        this.isDragging = this.dragDepth > 0;
      }
    },
    handleDragOver(event) {
      if (this.isFileDrag(event)) {
        event.preventDefault();
        event.dataTransfer.dropEffect = this.backendReady ? "copy" : "none";
      }
    },
    handleDrop(event) {
      event.preventDefault();
      this.dragDepth = 0;
      this.isDragging = false;
      if (!this.backendReady) {
        return;
      }
      this.setImages(Array.from(event.dataTransfer?.files ?? []), true);
    },
    startGenerationTimer() {
      this.stopGenerationTimer();
      this.elapsedSeconds = 0;
      const startedAt = performance.now();
      this.generationStartedAt = startedAt;
      this.generationTimerId = window.setInterval(() => {
        if (this.generationStartedAt === startedAt) {
          this.elapsedSeconds = (performance.now() - startedAt) / 1000;
        }
      }, 200);
    },
    stopGenerationTimer() {
      if (this.generationTimerId !== null) {
        window.clearInterval(this.generationTimerId);
        this.generationTimerId = null;
      }
      if (this.generationStartedAt !== null) {
        const elapsedSeconds =
          (performance.now() - this.generationStartedAt) / 1000;
        this.generationStartedAt = null;
        if (this.generatedImage) {
          this.elapsedSeconds = elapsedSeconds;
          this.generatedImage.elapsedSeconds = this.elapsedSeconds;
        } else {
          this.elapsedSeconds = null;
        }
      }
    },
    async submitForm() {
      if (!this.backendReady || !this.confirmGeneratedImageReplacement()) {
        return;
      }
      this.loading = true;
      this.error = "";
      this.generationError = "";
      this.clearGeneratedImage();
      const outputFormat = this.apiOutputFormat;
      const generateDescription = this.form.generateDescription;
      const streamPartialImages = this.form.streamPartialImages;
      const [placeholderWidth, placeholderHeight] = this.resolution;
      const placeholderBlob = createPlaceholderImageBlob(
        placeholderWidth,
        placeholderHeight,
      );
      this.generatedImage = {
        blob: placeholderBlob,
        url: URL.createObjectURL(placeholderBlob),
        filename: `generated-image.${outputFormat}`,
        format: outputFormat,
        cost: null,
        downloaded: false,
        descriptionPending: false,
        descriptionError: "",
        elapsedSeconds: null,
        generationPending: true,
        streamingPending: streamPartialImages,
        isPartialPreview: false,
      };
      const formData = new FormData();
      for (const image of this.form.images) {
        formData.append("images", image.file, image.file.name);
      }
      if (this.generatedImage) {
        setTimeout(() => {
          document.getElementById("generated-result")?.scrollIntoView({
            behavior: "smooth",
            block: "start",
          });
        }, 100);
      }
      formData.append("prompt", this.form.prompt);
      formData.append("model", this.form.model);
      formData.append("quality", this.form.quality);
      formData.append("aspect_ratio", this.form.aspectRatio);
      formData.append("megapixels", String(this.megapixelsValue));
      if (
        (this.selectedResolutionImage || this.isSpecifyResolution) &&
        this.resolution
      ) {
        const [width, height] = this.resolution.map(String);
        formData.append("resolution_width", width);
        formData.append("resolution_height", height);
      }
      formData.append("output_format", outputFormat);
      formData.append("animated_gif", String(this.animationOptionsSupported));
      if (this.compressionSupported) {
        formData.append("output_compression", String(this.form.outputCompression));
      }
      if (this.animationOptionsSupported) {
        formData.append("frame_count", String(this.form.frameCount));
        formData.append("frame_duration_ms", String(this.form.frameDurationMs));
      }
      const background =
        this.transparentBackgroundSupported && this.form.transparentBackground
          ? "transparent"
          : "auto";
      formData.append("background", background);
      formData.append("stream", String(streamPartialImages));

      this.startGenerationTimer();
      try {
        const response = await fetch("/api/generate", {
          method: "POST",
          body: formData,
        });
        if (!response.ok) {
          const data = await response.json().catch(() => null);
          throw new Error(
            typeof data?.error === "string" && data.error.trim()
              ? data.error
              : "Image generation failed. Please try again.",
          );
        }
        if (streamPartialImages) {
          await consumeImageStream(response, async (event) => {
            const blob = imageBlobFromBase64(event.b64_json, outputFormat);
            const completed = event.type === "completed";
            await this.updateGeneratedImagePreview(
              blob,
              {
                cost: completed
                  ? parseActualCost(event.cost)
                  : this.generatedImage.cost,
                generationPending: !completed,
                streamingPending: !completed,
                isPartialPreview: !completed,
              },
              true,
            );
          });
          this.generatedImage.descriptionPending = generateDescription;
        } else {
          const blob = await response.blob();
          await this.updateGeneratedImagePreview(blob, {
            cost: parseActualCost(response.headers.get("X-Image-Generation-Cost")),
            descriptionPending: generateDescription,
            generationPending: false,
            streamingPending: false,
            isPartialPreview: false,
          });
        }
        const generatedImage = this.generatedImage;
        if (generateDescription) {
          try {
            const descriptionBlob = await createDescriptionImageBlob(
              generatedImage.blob,
            );
            const descriptionData = new FormData();
            descriptionData.append("image", descriptionBlob, "description.png");
            const descriptionResponse = await fetch("/api/describe", {
              method: "POST",
              body: descriptionData,
            });
            if (!descriptionResponse.ok) {
              const data = await descriptionResponse.json();
              throw new Error(data.error || "Description generation failed.");
            }
            const description = await descriptionResponse.json();
            generatedImage.cost = addActualCost(
              generatedImage.cost,
              parseActualCost(description.cost),
            );
            if (
              typeof description.filename !== "string" ||
              description.filename.length > 50 ||
              !/^[a-z0-9]+(?:_[a-z0-9]+){2,5}$/.test(description.filename)
            ) {
              throw new Error("Description service returned an invalid filename.");
            }
            generatedImage.filename = `${description.filename}.${outputFormat}`;
          } catch (error) {
            generatedImage.descriptionError =
              `Image generated, but filename description failed: ${error.message} ` +
              `Using default filename ${generatedImage.filename}.`;
          } finally {
            generatedImage.descriptionPending = false;
          }
        }
      } catch (error) {
        if (this.generatedImage?.generationPending) {
          this.clearGeneratedImage();
        }
        this.generationError =
          error instanceof Error
            ? error.message
            : "Image generation failed. Please try again.";
      } finally {
        this.stopGenerationTimer();
        this.loading = false;
      }
    },
    downloadImage() {
      if (!this.generatedImage) {
        return;
      }
      const link = document.createElement("a");
      link.href = this.generatedImage.url;
      link.download = this.generatedImage.filename;
      document.body.append(link);
      link.click();
      link.remove();
      this.generatedImage.downloaded = true;
    },
    openFullscreen() {
      if (!this.generatedImage || this.generatedImage.generationPending) {
        return;
      }
      this.showFullscreen = true;
      this.$nextTick(() => this.$refs.imageModal?.focus());
    },
    closeFullscreen() {
      this.showFullscreen = false;
      this.$nextTick(() => this.$refs.fullscreenButton?.focus());
    },
    formatCurrency(amount, maxFractionDigits = 2) {
      return new Intl.NumberFormat(undefined, {
        style: "currency",
        currency: "USD",
        minimumFractionDigits: 2,
        maximumFractionDigits: maxFractionDigits,
      }).format(amount);
    },
    formatActualCost,
  },
};
</script>
