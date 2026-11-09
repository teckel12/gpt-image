<template>
  <main class="page">
    <section class="panel" aria-labelledby="page-title">
      <header class="page-header">
        <h1 id="page-title">GPT Image Generator</h1>
        <p class="intro">
          Generate an image from a prompt, optionally using input images.
        </p>
      </header>

      <form class="form" @submit.prevent="submitForm">
        <fieldset class="form-fields" :disabled="!backendReady">
          <p v-if="error" class="message error" role="alert">{{ error }}</p>
          <button
            type="button"
            class="button-animation"
            :class="{ 'is-hidden': (!generatedImage || generatedImage.descriptionPending) && form.images.length === 0 }"
            @click="resetForm"
          >
            <i-mdi-arrow-u-left-top-bold class="mdi-icon" />
            Reset Form Values
          </button>
          <fieldset
            class="field-group"
            :class="{ 'hide-one-row': (!generatedImage || generatedImage.descriptionPending) && form.images.length === 0 }"
          >
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
              required
              rows="5"
              placeholder="Describe what you want to create or change..."
            />
          </label>

          <div class="field-row">
            <label class="field">
              <span>GPT Image Model</span>
              <select v-model="form.model" required @change="updateModel">
                <option value="" disabled>Select image model</option>
                <option v-for="model in models" :key="model.value" :value="model.value">
                  {{ model.display_name }} ({{ model.description }})
                </option>
              </select>
            </label>
            <label class="field">
              <span>Quality</span>
              <select v-model="form.quality" required>
                <option value="" disabled>Select image quality</option>
                <option v-for="quality in qualities" :key="quality" :value="quality">
                  {{ quality }}
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
                required
                :disabled="Boolean(selectedResolutionImage)"
              >
                <option value="" disabled>Select aspect ratio</option>
                <option
                  v-for="ratio in aspectRatios"
                  :key="ratio.value"
                  :value="ratio.value"
                >
                  {{ ratio.label }}
                </option>
              </select>
            </label>
            <label class="field">
              <span>Megapixels</span>
              <input
                v-model.number="form.megapixels"
                type="number"
                min="0.7"
                max="3.5"
                step="0.4"
                required
                :disabled="Boolean(selectedResolutionImage)"
              />
            </label>
          </div>
          <p v-if="resolution"
            class="resolution"
            :class="{ 'hide-one-row': Boolean(selectedResolutionImage) }"
          >
            Output resolution: <strong>{{ resolution }}</strong>
          </p>
          <p v-if="resolutionError" class="field-error" role="alert">
            {{ resolutionError }}
          </p>

          <div class="field-row">
            <label class="field">
              <span>Output Image Format</span>
              <select v-model="form.outputFormat" required @change="updateOutputFormat">
                <option value="" disabled>Select output image format</option>
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
            <label class="field">
              <span>Image Quality Level</span>
              <input
                v-model.number="form.outputCompression"
                type="number"
                min="1"
                max="100"
                step="1"
                :required="compressionSupported"
                :disabled="!compressionSupported"
              />
            </label>
          </div>
          <div
            class="field-row field-row-animation"
            :class="{ 'is-hidden': !animationOptionsSupported }"
          >
            <label class="field">
              <span>Frame Count</span>
              <input
                v-model.number="form.frameCount"
                type="number"
                min="2"
                max="16"
                step="1"
                :disabled="!animationOptionsSupported"
                :required="animationOptionsSupported"
              />
            </label>
            <label class="field">
              <span>Frame Duration (ms)</span>
              <input
                v-model.number="form.frameDurationMs"
                type="number"
                min="20"
                max="2000"
                step="20"
                :disabled="!animationOptionsSupported"
                :required="animationOptionsSupported"
              />
            </label>
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
            :class="{
              'hide-one-row': !animationOptionsSupported,
              'is-hidden': !transparentBackgroundSupported
            }"
          >
            <label
              class="check-field"
              :class="{ 'is-disabled': !transparentBackgroundSupported }"
            >
              <input
                v-model="form.transparentBackground"
                type="checkbox"
                :disabled="!transparentBackgroundSupported"
              />
              <span>Transparent Background</span>
            </label>
            <label class="check-field hidden">
            </label>
          </div>

          <div v-if="costEstimate" class="hidden">
            <span>
              Estimated cost: <strong>{{ formatCurrency(costEstimate.totalCost) }}</strong>
            </span>
            <span>
              Input: {{ formatCurrency(costEstimate.inputCost, 4) }} ·
              Output: {{ formatCurrency(costEstimate.outputCost, 4) }}
            </span>
          </div>

          <p v-if="costEstimate && (costEstimate.pendingInputCount || costEstimate.unreadableInputCount)" class="cost-estimate" role="status">
            <small v-if="costEstimate.pendingInputCount">
              Reading dimensions for {{ costEstimate.pendingInputCount }} input image(s).
            </small>
            <small v-if="costEstimate.unreadableInputCount" class="error">
              Input estimate excludes {{ costEstimate.unreadableInputCount }} image(s)
              whose dimensions could not be read.
            </small>
          </p>

          <button
            type="submit"
            :disabled=submitDisabled
            class="button-animation"
            :class="{
              'hide-one-row': !transparentBackgroundSupported,
              'hide-two-rows': !transparentBackgroundSupported && !animationOptionsSupported,
            }"
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
            v-if="elapsedSeconds !== null && !(generatedImage && !generatedImage.descriptionPending)"
            class="generation-timer"
            role="timer"
            aria-live="off"
          >
            Generating image: {{ elapsedSeconds.toFixed(1) }} seconds
          </p>

          <div
            v-if="generatedImage && !generatedImage.descriptionPending"
            id="generated-result"
            class="generated-result"
          >
            <p class="message success" role="status">
              <code>{{ generatedImage.filename }}</code>
              <span v-if="generatedImage.elapsedSeconds !== null">
                ({{ generatedImage.elapsedSeconds.toFixed(1) }} seconds<span
                  v-if="generatedImage.cost !== null"
                  >, {{ formatActualCost(generatedImage.cost) }}</span
                >)
              </span>
            </p>
            <p v-if="generatedImage.descriptionPending" class="message" role="status">
              Creating descriptive filename...
            </p>
            <p v-if="generatedImage.descriptionError" class="message error" role="alert">
              {{ generatedImage.descriptionError }}
            </p>

            <img
              ref="generatedImagePreview"
              class="generated-image"
              :src="generatedImage.url"
              alt="Generated image"
              @click="openFullscreen"
            />
            <div class="generated-actions">
              <button
                ref="fullscreenButton"
                type="button"
                @click="openFullscreen"
              >
                <i-mdi-magnify-plus class="mdi-icon" />
                Zoom
              </button>
              <button
                type="button"
                :disabled="generatedImage.descriptionPending"
                @click="downloadImage"
              >
                <i-mdi-download class="mdi-icon" />
                Download
              </button>
              <button
                type="button"
                :disabled="
                  generatedImage.descriptionPending || generatedImage.format === 'svg'
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
} from "./actual-cost.js";
import { estimateGenerationCost } from "./cost-estimator.js";
import { createDescriptionImageBlob } from "./description-image.js";
import {
  parseResolution,
  roundToNearestMultipleOf16,
} from "./resolution.js";

const MAX_EDGE = 3840;
const MIN_PIXELS = 655360;
const MAX_PIXELS = 3686400;
const SUPPORTED_IMAGE_EXTENSIONS = new Set(["png", "jpg", "jpeg", "webp", "gif"]);

export default {
  data() {
    return {
      models: [],
      aspectRatios: [],
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
      form: {
        images: [],
        prompt: "",
        model: "",
        quality: "",
        aspectRatio: "",
        megapixels: 1,
        resolutionImageId: null,
        outputFormat: "png",
        outputCompression: 90,
        frameCount: 9,
        frameDurationMs: 200,
        transparentBackground: false,
        generateDescription: true,
      },
    };
  },
  computed: {
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
    frameCountError() {
      if (
        this.animationOptionsSupported &&
        (!Number.isInteger(this.form.frameCount) ||
          this.form.frameCount < 2 ||
          this.form.frameCount > 16)
      ) {
        return "Frame count must be an integer from 2 to 16.";
      }
      return "";
    },
    frameDurationError() {
      if (
        this.animationOptionsSupported &&
        (!Number.isInteger(this.form.frameDurationMs) ||
          this.form.frameDurationMs < 20 ||
          this.form.frameDurationMs > 2000)
      ) {
        return "Frame duration must be an integer from 20 to 2000 ms.";
      }
      return "";
    },
    outputCompressionError() {
      if (
        this.compressionSupported &&
        (!Number.isInteger(this.form.outputCompression) ||
          this.form.outputCompression < 1 ||
          this.form.outputCompression > 100)
      ) {
        return "Image compression must be an integer from 1 to 100.";
      }
      return "";
    },
    resolution() {
      if (this.selectedResolutionImage) {
        const { width, height } = this.selectedResolutionImage;
        if (!width || !height) {
          return "";
        }
        return `${roundToNearestMultipleOf16(width)} × ${roundToNearestMultipleOf16(height)}`;
      }

      if (
        !this.form.aspectRatio ||
        !Number.isFinite(this.form.megapixels) ||
        this.form.megapixels <= 0
      ) {
        return "";
      }

      const [ratioWidth, ratioHeight] = this.form.aspectRatio.split(":").map(Number);
      const targetPixels = this.form.megapixels * 1_000_000;
      const width = Math.max(
        16,
        Math.floor(Math.sqrt(targetPixels * (ratioWidth / ratioHeight)) / 16 + 0.5) * 16,
      );
      const height = Math.max(
        16,
        Math.floor(Math.sqrt(targetPixels * (ratioHeight / ratioWidth)) / 16 + 0.5) * 16,
      );
      return `${width} × ${height}`;
    },
    resolutionError() {
      if (!this.resolution) {
        return this.selectedResolutionImage
          ? "Selected image resolution is unavailable."
          : "Megapixels must be a positive number.";
      }
      const [width, height] = parseResolution(this.resolution);
      const pixels = width * height;
      const selectedImage = Boolean(this.selectedResolutionImage);
      if (width % 16 || height % 16) {
        return "Output width and height must be multiples of 16.";
      }
      if (pixels < MIN_PIXELS) {
        if (selectedImage) {
          return "Selected image resolution is below the minimum supported size of 655,360 pixels. Choose a larger image or clear the selection.";
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

      const [outputWidth, outputHeight] = parseResolution(this.resolution);
      return estimateGenerationCost({
        outputWidth,
        outputHeight,
        outputPricePerMegapixel,
        inputImages: this.form.images,
        inputPricePerMegapixel: this.inputImageCostPerMegapixel,
        outputFrameCount: this.animationOptionsSupported ? this.form.frameCount : 1,
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
      this.stopGenerationTimer();
      this.releasePreviews();
      this.clearGeneratedImage();
      const defaultModel = this.models[0];
      this.form = {
        images: [],
        prompt: "",
        model: defaultModel?.value ?? "",
        quality: defaultModel?.qualities[1] ?? defaultModel?.qualities[0] ?? "",
        aspectRatio: this.aspectRatios[0]?.value ?? "",
        megapixels: 1,
        resolutionImageId: null,
        outputFormat: "png",
        outputCompression: 90,
        frameCount: 9,
        frameDurationMs: 200,
        transparentBackground: false,
        generateDescription: true,
      };
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
      const formData = new FormData();
      for (const image of this.form.images) {
        formData.append("images", image.file, image.file.name);
      }
      formData.append("prompt", this.form.prompt);
      formData.append("model", this.form.model);
      formData.append("quality", this.form.quality);
      formData.append("aspect_ratio", this.form.aspectRatio);
      formData.append("megapixels", String(this.form.megapixels));
      if (this.selectedResolutionImage && this.resolution) {
        const [width, height] = parseResolution(this.resolution).map(String);
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
        const blob = await response.blob();
        this.generatedImage = {
          blob,
          url: URL.createObjectURL(blob),
          filename: `generated-image.${outputFormat}`,
          format: outputFormat,
          cost: parseActualCost(
            response.headers.get("X-Image-Generation-Cost"),
          ),
          downloaded: false,
          descriptionPending: generateDescription,
          descriptionError: "",
          elapsedSeconds: null,
        };
        const generatedImage = this.generatedImage;
        if (generateDescription) {
          try {
            const descriptionBlob = await createDescriptionImageBlob(blob);
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
        this.generationError =
          error instanceof Error
            ? error.message
            : "Image generation failed. Please try again.";
      } finally {
        this.stopGenerationTimer();
        this.loading = false;
        if (this.generatedImage) {
          this.$nextTick(() => {
            document.getElementById("generated-result")?.scrollIntoView({
              behavior: "smooth",
              block: "start",
            });
          });
        }
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
