<template>
  <div class="numeric-input">
    <input
      :id="id"
      v-model="inputValue"
      v-maska="mask"
      type="text"
      :inputmode="inputmode"
      :pattern="pattern"
      :title="title"
      :min="min"
      :max="max"
      :step="step"
      :required="required"
      :disabled="disabled"
      @keydown.up.prevent="stepValue(1)"
      @keydown.down.prevent="stepValue(-1)"
    />
    <div class="numeric-stepper">
      <button
        type="button"
        :aria-label="`Increase ${label}`"
        :disabled="disabled || modelValue >= max"
        @click="stepValue(1)"
      >
        <i-mdi-chevron-up class="mdi-icon" aria-hidden="true" />
      </button>
      <button
        type="button"
        :aria-label="`Decrease ${label}`"
        :disabled="disabled || modelValue <= min"
        @click="stepValue(-1)"
      >
        <i-mdi-chevron-down class="mdi-icon" aria-hidden="true" />
      </button>
    </div>
  </div>
</template>

<script>
import { vMaska } from "maska/vue";
import { stepNumericValue } from "../modules/numeric-stepper.js";

export default {
  directives: {
    maska: vMaska,
  },
  props: {
    id: { type: String, required: true },
    label: { type: String, required: true },
    modelValue: { type: [Number, String], required: true },
    mask: { type: [String, Object, Function], required: true },
    min: { type: Number, required: true },
    max: { type: Number, required: true },
    step: { type: Number, required: true },
    disabled: { type: Boolean, default: false },
    required: { type: Boolean, default: false },
    inputmode: { type: String, default: "numeric" },
    pattern: { type: String, default: "[0-9]*" },
    title: { type: String, default: "" },
  },
  emits: ["update:modelValue"],
  computed: {
    inputValue: {
      get() {
        return this.modelValue;
      },
      set(value) {
        const numericValue = Number.parseFloat(value);
        this.$emit(
          "update:modelValue",
          Number.isNaN(numericValue) ? value : numericValue,
        );
      },
    },
  },
  methods: {
    stepValue(direction) {
      this.$emit(
        "update:modelValue",
        stepNumericValue(this.modelValue, direction, this),
      );
    },
  },
};
</script>
