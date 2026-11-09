import base64
import json
import logging
import math
import os
import re
import struct
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, BinaryIO, Literal, Protocol, Sequence

from openai import OpenAI

LOGGER = logging.getLogger(__name__)
TOKENS_PER_MILLION = Decimal(1_000_000)
IMAGE_TOKEN_RATES = (
    (("input_tokens_details", "image_tokens"), Decimal("8")),
    (("input_tokens_details", "text_tokens"), Decimal("5")),
    (("output_tokens",), Decimal("30")),
)
DESCRIPTION_TOKEN_RATES = (
    (("input_tokens",), Decimal("0.10")),
    (("output_tokens",), Decimal("0.50")),
)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_QUALITIES = {
    "gpt-image-2.5-flare": ("low", "medium", "high", "xhigh", "max"),
    "gpt-image-2.5-sunburst": ("low", "medium", "high", "xhigh", "max"),
    "gpt-image-2.6-flare": ("low", "medium", "high", "xhigh", "max"),
    "gpt-image-2.6-sunburst": ("low", "medium", "high", "xhigh", "max"),
}
MODEL_DISPLAY_NAMES = {
    "gpt-image-2.5-sunburst": "2.5 Sunburst",
    "gpt-image-2.5-flare": "2.5 Flare",
    "gpt-image-2.6-sunburst": "2.6 Sunburst",
    "gpt-image-2.6-flare": "2.6 Flare",
}
MODEL_DESCRIPTIONS = {
    "gpt-image-2.5-sunburst": "high-precision",
    "gpt-image-2.5-flare": "fast, high-quality",
    "gpt-image-2.6-sunburst": "fast, higher-precision",
    "gpt-image-2.6-flare": "fastest, high-quality",
}
MODEL_QUALITY_COST_PER_MEGAPIXEL = {
    "gpt-image-2.5-sunburst": {
        "low": 0.01,
        "medium": 0.02,
        "high": 0.12,
        "xhigh": 0.20,
        "max": 0.40,
    },
    "gpt-image-2.5-flare": {
        "low": 0.01,
        "medium": 0.02,
        "high": 0.12,
        "xhigh": 0.20,
        "max": 0.40,
    },
    "gpt-image-2.6-sunburst": {
        "low": 0.04,
        "medium": 0.08,
        "high": 0.12,
        "xhigh": 0.20,
        "max": 0.40,
    },
    "gpt-image-2.6-flare": {
        "low": 0.04,
        "medium": 0.08,
        "high": 0.12,
        "xhigh": 0.20,
        "max": 0.40,
    },
}
INPUT_IMAGE_COST_PER_MEGAPIXEL = 0.01
ASPECT_RATIOS = {
    "1:1": ("Square", 1, 1),
    "2:3": ("Portrait Photo", 2, 3),
    "3:2": ("Photo", 3, 2),
    "3:4": ("Portrait Standard", 3, 4),
    "4:3": ("Standard", 4, 3),
    "9:16": ("Portrait Widescreen", 9, 16),
    "16:9": ("Widescreen", 16, 9),
    "21:9": ("Ultrawide", 21, 9),
}
MAX_EDGE = 3840
MIN_PIXELS = 655_360
MAX_PIXELS = 3_686_400
MAX_INPUT_IMAGES = 16
INPUT_FORMATS = {"png", "jpg", "jpeg", "webp", "gif"}
OUTPUT_FORMATS = {"png", "jpeg", "webp", "svg", "gif"}
MODEL_OUTPUT_FORMATS = {
    "gpt-image-2.5-sunburst": {"png", "jpeg", "webp"},
    "gpt-image-2.5-flare": {"png", "jpeg", "webp"},
    "gpt-image-2.6-sunburst": OUTPUT_FORMATS,
    "gpt-image-2.6-flare": OUTPUT_FORMATS,
}
OUTPUT_COMPRESSION_FORMATS = {"jpeg", "webp"}
TRANSPARENT_BACKGROUND_FORMATS = {"png", "webp"}
OUTPUT_MIME_TYPES = {
    "png": "image/png",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
    "svg": "image/svg+xml",
    "gif": "image/gif",
}
DESCRIPTION_MODEL = "gpt-6-luna"
DESCRIPTION_MAX_PIXELS = 1_000_000
DESCRIPTION_PROMPT = """Analyze this image and generate a concise, highly descriptive text phrase that captures the core subject or primary action. Formulate this text specifically to be used directly as a file name.

Strict Formatting Rules:
1. Use a descriptive "Subject_Action_Context" or "Subject_Attribute" format.
2. Use snake_case (lowercase letters with underscores separating words).
3. Do not include a file extension (e.g., do not add .jpg, .png, or .txt).
4. Strictly omit all spaces and special characters. Valid characters are only: a-z, 0-9, and _.
5. Keep the total length between 3 to 6 words (maximum 50 characters).

Return ONLY the final file name string. Do not include markdown code blocks, quotes, or any introductory or conversational text."""


class UploadedImage(Protocol):
    filename: str
    mimetype: str
    stream: BinaryIO


class OpenAIResponse(Protocol):
    def model_dump(self, *, mode: Literal["json"]) -> dict[str, Any]: ...


class ValidationError(ValueError):
    pass


class ConfigurationError(RuntimeError):
    pass


class ImageServiceError(RuntimeError):
    pass


def _log_openai_response(
    response: OpenAIResponse,
    operation: str,
    *,
    image_response: bool = False,
) -> None:
    response_data = response.model_dump(mode="json")
    if image_response:
        for image in response_data.get("data") or []:
            image.pop("b64_json", None)
            image.pop("url", None)
    LOGGER.info("OpenAI %s response: %s", operation, json.dumps(response_data))


@dataclass(frozen=True)
class ImageRequest:
    prompt: str
    model: str
    quality: str
    size: str
    output_format: str
    output_compression: int | None
    background: str
    animated_gif: bool
    frame_count: int
    frame_duration_ms: int


@dataclass(frozen=True)
class ImageGenerationResult:
    image_bytes: bytes
    cost: Decimal | None


@dataclass(frozen=True)
class DescriptionResult:
    filename: str
    cost: Decimal | None


def _usage_cost(
    usage: Any,
    token_rates: tuple[tuple[tuple[str, ...], Decimal], ...],
) -> Decimal | None:
    if usage is None:
        return None

    cost = Decimal(0)
    has_usage = False
    for path, rate in token_rates:
        token_data = usage
        for field in path:
            token_data = getattr(token_data, field, None)
            if token_data is None:
                break
        if (
            isinstance(token_data, int)
            and not isinstance(token_data, bool)
            and token_data >= 0
        ):
            cost += Decimal(token_data) * rate / TOKENS_PER_MILLION
            has_usage = True
    return cost if has_usage else None


def validate_output_dimensions(width: int, height: int) -> tuple[int, int]:
    if width <= 0 or height <= 0:
        raise ValidationError("Output dimensions must be positive integers.")
    if width % 16 or height % 16:
        raise ValidationError("Output width and height must be multiples of 16.")
    if width * height < MIN_PIXELS:
        raise ValidationError(
            f"Requested size is below the minimum supported image pixel budget ({MIN_PIXELS:,} pixels)."
        )
    if (
        width > MAX_EDGE
        or height > MAX_EDGE
        or width * height > MAX_PIXELS
        or not 1 / 3 <= width / height <= 3
    ):
        raise ValidationError(
            f"Requested size is outside supported image limits (maximum edge {MAX_EDGE}px and {MAX_PIXELS:,} pixels)."
        )
    return width, height


def compute_resolution(aspect_ratio: str, megapixels: float) -> tuple[int, int]:
    if aspect_ratio not in ASPECT_RATIOS:
        raise ValidationError("Select a supported aspect ratio.")
    if not math.isfinite(megapixels) or megapixels <= 0:
        raise ValidationError("Megapixels must be a positive number.")

    _, ratio_width, ratio_height = ASPECT_RATIOS[aspect_ratio]
    ratio = ratio_width / ratio_height
    pixels = megapixels * 1_000_000
    width = max(16, math.floor(math.sqrt(pixels * ratio) / 16 + 0.5) * 16)
    height = max(16, math.floor(math.sqrt(pixels / ratio) / 16 + 0.5) * 16)
    return validate_output_dimensions(width, height)


def validate_request(
    *,
    prompt: str,
    model: str,
    quality: str,
    aspect_ratio: str,
    megapixels: str | float,
    resolution_width: str | int | None = None,
    resolution_height: str | int | None = None,
    output_format: str = "png",
    output_compression: str | int | None = None,
    background: str | None = None,
    animated_gif: str | bool | None = None,
    frame_count: str | int | None = None,
    frame_duration_ms: str | int | None = None,
) -> ImageRequest:
    prompt = prompt.strip()
    if not prompt:
        raise ValidationError("Prompt is required.")
    if model not in MODEL_QUALITIES:
        raise ValidationError("Select a supported model.")
    if quality not in MODEL_QUALITIES[model]:
        raise ValidationError("Select a supported quality for this model.")
    has_resolution_width = resolution_width not in (None, "")
    has_resolution_height = resolution_height not in (None, "")
    if has_resolution_width != has_resolution_height:
        raise ValidationError("Provide both output width and height.")
    if has_resolution_width:
        try:
            width = int(resolution_width)
            height = int(resolution_height)
        except (TypeError, ValueError) as error:
            raise ValidationError(
                "Output dimensions must be positive integers."
            ) from error
        width, height = validate_output_dimensions(width, height)
    else:
        try:
            megapixels_value = float(megapixels)
        except (TypeError, ValueError) as error:
            raise ValidationError("Megapixels must be a positive number.") from error
        width, height = compute_resolution(aspect_ratio, megapixels_value)
    if output_format not in OUTPUT_FORMATS:
        raise ValidationError("Select a supported output format.")
    if output_format not in MODEL_OUTPUT_FORMATS[model]:
        raise ValidationError("GIF and SVG output require a 2.6 model.")

    if animated_gif is True or animated_gif == "true":
        animated_gif_value = True
    elif animated_gif is False or animated_gif in (None, "", "false"):
        animated_gif_value = False
    else:
        raise ValidationError("Animated GIF selection must be true or false.")
    if animated_gif_value and output_format != "gif":
        raise ValidationError("Animated GIF requires GIF output.")

    frame_count_value = 9
    frame_duration_value = 200
    has_frame_settings = frame_count not in (None, "") or frame_duration_ms not in (
        None,
        "",
    )
    if animated_gif_value:
        try:
            frame_count_value = (
                9 if frame_count in (None, "") else int(frame_count)
            )
        except (TypeError, ValueError) as error:
            raise ValidationError(
                "Frame count must be an integer from 2 to 16."
            ) from error
        if not 2 <= frame_count_value <= 16:
            raise ValidationError("Frame count must be an integer from 2 to 16.")
        try:
            frame_duration_value = (
                200 if frame_duration_ms in (None, "") else int(frame_duration_ms)
            )
        except (TypeError, ValueError) as error:
            raise ValidationError(
                "Frame duration must be an integer from 20 to 2000 ms."
            ) from error
        if not 20 <= frame_duration_value <= 2000:
            raise ValidationError(
                "Frame duration must be an integer from 20 to 2000 ms."
            )
    elif has_frame_settings:
        raise ValidationError("Frame settings require animated GIF output.")

    compression = None
    if output_format in OUTPUT_COMPRESSION_FORMATS:
        try:
            compression = (
                90 if output_compression in (None, "") else int(output_compression)
            )
        except (TypeError, ValueError) as error:
            raise ValidationError(
                "Image compression must be an integer from 1 to 100."
            ) from error
        if not 1 <= compression <= 100:
            raise ValidationError("Image compression must be from 1 to 100.")

    if background in (None, ""):
        background = "auto"
    elif background == "transparent":
        if output_format not in TRANSPARENT_BACKGROUND_FORMATS:
            raise ValidationError(
                "Transparent background is only supported for PNG and WebP."
            )
    elif background != "auto":
        raise ValidationError("Background must be auto or transparent.")

    return ImageRequest(
        prompt=prompt,
        model=model,
        quality=quality,
        size=f"{width}x{height}",
        output_format=output_format,
        output_compression=compression,
        background=background,
        animated_gif=animated_gif_value,
        frame_count=frame_count_value,
        frame_duration_ms=frame_duration_value,
    )


def validate_images(images: Sequence[UploadedImage]) -> list[UploadedImage]:
    selected_images = [image for image in images if image.filename]
    if len(selected_images) > MAX_INPUT_IMAGES:
        raise ValidationError(f"Select no more than {MAX_INPUT_IMAGES} input images.")

    for image in selected_images:
        extension = Path(image.filename).suffix.lower().lstrip(".")
        if extension not in INPUT_FORMATS:
            raise ValidationError(
                f"Unsupported input image type: {image.filename}. Use PNG, JPEG, WebP, or GIF."
            )
        image.stream.seek(0, os.SEEK_END)
        size = image.stream.tell()
        image.stream.seek(0)
        if size == 0:
            raise ValidationError(f"Input image is empty: {image.filename}.")
    return selected_images


def generate_image(
    images: Sequence[UploadedImage],
    image_request: ImageRequest,
) -> ImageGenerationResult:
    selected_images = validate_images(images)
    if selected_images and image_request.output_format == "svg":
        raise ValidationError("SVG output is not supported with input images.")
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ConfigurationError(
            "OPENAI_API_KEY is not configured in the project .env file."
        )

    client = OpenAI(api_key=api_key)
    options: dict[str, str | int] = {
        "prompt": image_request.prompt,
        "model": image_request.model,
        "size": image_request.size,
        "quality": image_request.quality,
        "output_format": image_request.output_format,
    }
    animation_options: dict[str, int] = {}
    if image_request.output_compression is not None:
        options["output_compression"] = image_request.output_compression
    if image_request.animated_gif:
        animation_options = {
            "frame_count": image_request.frame_count,
            "frame_duration_ms": image_request.frame_duration_ms,
        }
    options["background"] = image_request.background
    if selected_images:
        response = client.images.edit(
            image=[
                (image.filename, image.stream, image.mimetype)
                for image in selected_images
            ],
            extra_body=animation_options or None,
            **options,
        )
        _log_openai_response(response, "images.edit", image_response=True)
    else:
        response = client.images.generate(
            extra_body=animation_options or None,
            **options,
        )
        _log_openai_response(response, "images.generate", image_response=True)
    if not response.data or not response.data[0].b64_json:
        raise ImageServiceError("Image API returned no image data.")
    try:
        image_bytes = base64.b64decode(response.data[0].b64_json, validate=True)
    except ValueError as error:
        raise ImageServiceError("Image API returned invalid image data.") from error
    return ImageGenerationResult(
        image_bytes=image_bytes,
        cost=_usage_cost(getattr(response, "usage", None), IMAGE_TOKEN_RATES),
    )


def validate_description_image(image_bytes: bytes) -> None:
    if (
        len(image_bytes) < 24
        or image_bytes[:8] != b"\x89PNG\r\n\x1a\n"
        or image_bytes[12:16] != b"IHDR"
    ):
        raise ValidationError("Description image must be a valid PNG.")

    width, height = struct.unpack(">II", image_bytes[16:24])
    if width == 0 or height == 0:
        raise ValidationError("Description image dimensions must be positive.")
    if width * height > DESCRIPTION_MAX_PIXELS:
        raise ValidationError("Description image must be no larger than 1 megapixel.")


def sanitize_description_filename(description: str) -> str:
    normalized = description.strip().lower()
    normalized = re.sub(r"\.(?:png|jpe?g|webp|gif|svg|txt)$", "", normalized)
    words = re.findall(r"[a-z0-9]+", normalized)[:6]
    if len(words) < 3:
        raise ImageServiceError(
            "Image description did not contain at least three filename words."
        )

    while len(words) > 3 and len("_".join(words)) > 50:
        words.pop()
    excess = len("_".join(words)) - 50
    for index in range(len(words) - 1, -1, -1):
        trim = min(excess, len(words[index]) - 1)
        if trim:
            words[index] = words[index][:-trim]
            excess -= trim
        if excess == 0:
            break
    return "_".join(words)


def generate_description(image_bytes: bytes) -> DescriptionResult:
    validate_description_image(image_bytes)
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ConfigurationError(
            "OPENAI_API_KEY is not configured in the project .env file."
        )

    response = OpenAI(api_key=api_key).responses.create(
        model=DESCRIPTION_MODEL,
        reasoning={"effort": "none"},
        input=[
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": DESCRIPTION_PROMPT},
                    {
                        "type": "input_image",
                        "image_url": (
                            "data:image/png;base64,"
                            f"{base64.b64encode(image_bytes).decode('ascii')}"
                        ),
                    },
                ],
            }
        ],
    )
    _log_openai_response(response, "responses.create")
    if not isinstance(response.output_text, str):
        raise ImageServiceError("Image API returned no filename description.")
    return DescriptionResult(
        filename=sanitize_description_filename(response.output_text),
        cost=_usage_cost(getattr(response, "usage", None), DESCRIPTION_TOKEN_RATES),
    )
