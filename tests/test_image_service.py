import base64
import io
import json
import os
import struct
import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import httpx2
from openai import OpenAI as OpenAIClient

from backend.image_service import (
    DESCRIPTION_PROMPT,
    ImageStreamEvent,
    ImageServiceError,
    ValidationError,
    compute_resolution,
    generate_description,
    generate_image,
    generate_image_stream,
    sanitize_description_filename,
    validate_images,
    validate_request,
    validate_description_image,
)


def png_header(width, height):
    return (
        b"\x89PNG\r\n\x1a\n"
        + struct.pack(">I", 13)
        + b"IHDR"
        + struct.pack(">II", width, height)
    )


def image_api_response(image_bytes):
    encoded_image = base64.b64encode(image_bytes).decode("ascii")
    response_data = {
        "created": 123,
        "data": [
            {
                "b64_json": encoded_image,
                "url": "https://images.example/generated.png",
                "revised_prompt": "A generated image",
            }
        ],
        "usage": {"total_tokens": 42},
    }
    return SimpleNamespace(
        data=[SimpleNamespace(b64_json=encoded_image)],
        usage=None,
        model_dump=lambda mode="json": response_data,
    )


class FakeImageStream:
    def __init__(self, events):
        self.events = events
        self.closed = False

    def __iter__(self):
        return iter(self.events)

    def close(self):
        self.closed = True


def image_stream_event(event_type, image_bytes, *, index=None, usage=None):
    encoded_image = base64.b64encode(image_bytes).decode("ascii")
    response_data = {
        "type": event_type,
        "b64_json": encoded_image,
        "partial_image_index": index,
    }
    return SimpleNamespace(
        type=event_type,
        b64_json=encoded_image,
        partial_image_index=index,
        usage=usage,
        model_dump=lambda mode="json": response_data,
    )


class ImageServiceTests(unittest.TestCase):
    def test_computed_dimensions_are_multiples_of_16_and_match_ratio(self):
        width, height = compute_resolution("16:9", 1)

        self.assertEqual(width % 16, 0)
        self.assertEqual(height % 16, 0)
        self.assertAlmostEqual(width / height, 16 / 9, delta=0.03)

    def test_resolution_rejects_size_above_model_limits(self):
        self.assertEqual(compute_resolution("1:1", 3.6864), (1920, 1920))
        with self.assertRaisesRegex(ValidationError, "outside supported image limits"):
            compute_resolution("1:1", 3.75)

    def test_resolution_rejects_size_below_minimum_pixel_budget(self):
        with self.assertRaisesRegex(
            ValidationError,
            "minimum supported image pixel budget",
        ):
            compute_resolution("16:9", 0.5)

    def test_request_uses_and_validates_explicit_output_dimensions(self):
        image_request = validate_request(
            prompt="Create an image",
            model="gpt-image-2.5-sunburst",
            quality="medium",
            aspect_ratio="unused",
            megapixels="unused",
            resolution_width="1280",
            resolution_height="720",
        )
        self.assertEqual(image_request.size, "1280x720")

        with self.assertRaisesRegex(ValidationError, "both output width and height"):
            validate_request(
                prompt="Create an image",
                model="gpt-image-2.5-sunburst",
                quality="medium",
                aspect_ratio="1:1",
                megapixels=1,
                resolution_width="1280",
            )
        with self.assertRaisesRegex(ValidationError, "multiples of 16"):
            validate_request(
                prompt="Create an image",
                model="gpt-image-2.5-sunburst",
                quality="medium",
                aspect_ratio="1:1",
                megapixels=1,
                resolution_width="1025",
                resolution_height="1024",
            )
        with self.assertRaisesRegex(
            ValidationError,
            "minimum supported image pixel budget",
        ):
            validate_request(
                prompt="Create an image",
                model="gpt-image-2.5-sunburst",
                quality="medium",
                aspect_ratio="1:1",
                megapixels=1,
                resolution_width="512",
                resolution_height="512",
            )
        with self.assertRaisesRegex(ValidationError, "outside supported image limits"):
            validate_request(
                prompt="Create an image",
                model="gpt-image-2.5-sunburst",
                quality="medium",
                aspect_ratio="1:1",
                megapixels=1,
                resolution_width="3840",
                resolution_height="1024",
            )

    def test_request_requires_prompt_and_supported_model_quality(self):
        with self.assertRaisesRegex(ValidationError, "Prompt is required"):
            validate_request(
                prompt=" ",
                model="gpt-image-2.5-sunburst",
                quality="medium",
                aspect_ratio="1:1",
                megapixels=1,
            )

        for quality in ("xhigh", "max"):
            image_request = validate_request(
                prompt="Create an image",
                model="gpt-image-2.5-sunburst",
                quality=quality,
                aspect_ratio="1:1",
                megapixels=1,
            )
            self.assertEqual(image_request.quality, quality)

        with self.assertRaisesRegex(ValidationError, "supported quality"):
            validate_request(
                prompt="Edit image",
                model="gpt-image-2.5-sunburst",
                quality="invalid",
                aspect_ratio="1:1",
                megapixels=1,
            )

    def test_request_rejects_invalid_size_and_output_format(self):
        with self.assertRaisesRegex(ValidationError, "positive number"):
            validate_request(
                prompt="Edit image",
                model="gpt-image-2.5-sunburst",
                quality="medium",
                aspect_ratio="1:1",
                megapixels=0,
            )

        with self.assertRaisesRegex(ValidationError, "supported output format"):
            validate_request(
                prompt="Edit image",
                model="gpt-image-2.5-sunburst",
                quality="medium",
                aspect_ratio="1:1",
                megapixels=1,
                output_format="bmp",
            )

    def test_gif_and_svg_output_require_a_2_6_model(self):
        for output_format in ("gif", "svg"):
            with self.assertRaisesRegex(ValidationError, "require a 2.6 model"):
                validate_request(
                    prompt="Create an image",
                    model="gpt-image-2.5-sunburst",
                    quality="medium",
                    aspect_ratio="1:1",
                    megapixels=1,
                    output_format=output_format,
                )

            image_request = validate_request(
                prompt="Create an image",
                model="gpt-image-2.6-sunburst",
                quality="medium",
                aspect_ratio="1:1",
                megapixels=1,
                output_format=output_format,
            )
            self.assertEqual(image_request.output_format, output_format)

    def test_gif_animation_settings_validate_ranges_and_require_gif_output(self):
        image_request = validate_request(
            prompt="Create an animation",
            model="gpt-image-2.6-sunburst",
            quality="medium",
            aspect_ratio="1:1",
            megapixels=1,
            output_format="gif",
        )
        self.assertFalse(image_request.animated_gif)
        self.assertEqual(image_request.frame_count, 9)
        self.assertEqual(image_request.frame_duration_ms, 200)

        animated_default = validate_request(
            prompt="Create an animation",
            model="gpt-image-2.6-sunburst",
            quality="medium",
            aspect_ratio="1:1",
            megapixels=1,
            output_format="gif",
            animated_gif=True,
        )
        self.assertTrue(animated_default.animated_gif)
        self.assertEqual(animated_default.frame_count, 9)
        self.assertEqual(animated_default.frame_duration_ms, 200)

        for frame_count in (2, 16):
            image_request = validate_request(
                prompt="Create an animation",
                model="gpt-image-2.6-sunburst",
                quality="medium",
                aspect_ratio="1:1",
                megapixels=1,
                output_format="gif",
                animated_gif=True,
                frame_count=frame_count,
                frame_duration_ms=20,
            )
            self.assertTrue(image_request.animated_gif)
            self.assertEqual(image_request.frame_count, frame_count)

        for frame_count in (1, 17, "1.5"):
            with self.subTest(frame_count=frame_count):
                with self.assertRaisesRegex(ValidationError, "Frame count"):
                    validate_request(
                        prompt="Create an animation",
                        model="gpt-image-2.6-sunburst",
                        quality="medium",
                        aspect_ratio="1:1",
                        megapixels=1,
                        output_format="gif",
                        animated_gif=True,
                        frame_count=frame_count,
                    )

        for frame_duration_ms in (20, 2000):
            image_request = validate_request(
                prompt="Create an animation",
                model="gpt-image-2.6-sunburst",
                quality="medium",
                aspect_ratio="1:1",
                megapixels=1,
                output_format="gif",
                animated_gif=True,
                frame_count=2,
                frame_duration_ms=frame_duration_ms,
            )
            self.assertEqual(image_request.frame_duration_ms, frame_duration_ms)

        for frame_duration_ms in (19, 2001, "20.5"):
            with self.subTest(frame_duration_ms=frame_duration_ms):
                with self.assertRaisesRegex(ValidationError, "Frame duration"):
                    validate_request(
                        prompt="Create an animation",
                        model="gpt-image-2.6-sunburst",
                        quality="medium",
                        aspect_ratio="1:1",
                        megapixels=1,
                        output_format="gif",
                        animated_gif=True,
                        frame_count=2,
                        frame_duration_ms=frame_duration_ms,
                    )

        with self.assertRaisesRegex(ValidationError, "require animated GIF output"):
            validate_request(
                prompt="Create an image",
                model="gpt-image-2.6-sunburst",
                quality="medium",
                aspect_ratio="1:1",
                megapixels=1,
                output_format="png",
                frame_count=2,
            )

        with self.assertRaisesRegex(ValidationError, "Animated GIF requires GIF output"):
            validate_request(
                prompt="Create an image",
                model="gpt-image-2.6-sunburst",
                quality="medium",
                aspect_ratio="1:1",
                megapixels=1,
                output_format="png",
                animated_gif=True,
            )

        with self.assertRaisesRegex(ValidationError, "must be true or false"):
            validate_request(
                prompt="Create an image",
                model="gpt-image-2.6-sunburst",
                quality="medium",
                aspect_ratio="1:1",
                megapixels=1,
                output_format="gif",
                animated_gif="yes",
            )

    def test_request_validates_conditional_output_options(self):
        image_request = validate_request(
            prompt="Create an icon",
            model="gpt-image-2.5-sunburst",
            quality="medium",
            aspect_ratio="1:1",
            megapixels=1,
            output_format="webp",
            output_compression="90",
            background="transparent",
        )
        self.assertEqual(image_request.output_compression, 90)
        self.assertEqual(image_request.background, "transparent")

        with self.assertRaisesRegex(ValidationError, "1 to 100"):
            validate_request(
                prompt="Create an icon",
                model="gpt-image-2.5-sunburst",
                quality="medium",
                aspect_ratio="1:1",
                megapixels=1,
                output_format="jpeg",
                output_compression="101",
            )

        with self.assertRaisesRegex(ValidationError, "only supported for PNG and WebP"):
            validate_request(
                prompt="Create an icon",
                model="gpt-image-2.6-sunburst",
                quality="medium",
                aspect_ratio="1:1",
                megapixels=1,
                output_format="svg",
                background="transparent",
            )

        default_compression = validate_request(
            prompt="Create an icon",
            model="gpt-image-2.5-sunburst",
            quality="medium",
            aspect_ratio="1:1",
            megapixels=1,
            output_format="jpeg",
        )
        self.assertEqual(default_compression.output_compression, 90)
        self.assertEqual(default_compression.background, "auto")

        with self.assertRaisesRegex(ValidationError, "Background must be"):
            validate_request(
                prompt="Create an icon",
                model="gpt-image-2.5-sunburst",
                quality="medium",
                aspect_ratio="1:1",
                megapixels=1,
                background="opaque",
            )

    def test_streaming_is_off_by_default_and_rejected_for_gif_and_svg(self):
        image_request = validate_request(
            prompt="Create an image",
            model="gpt-image-2.6-sunburst",
            quality="medium",
            aspect_ratio="1:1",
            megapixels=1,
        )
        self.assertFalse(image_request.stream)

        streamed_request = validate_request(
            prompt="Create an image",
            model="gpt-image-2.6-sunburst",
            quality="medium",
            aspect_ratio="1:1",
            megapixels=1,
            stream="true",
        )
        self.assertTrue(streamed_request.stream)

        for output_format in ("gif", "svg"):
            with self.subTest(output_format=output_format):
                with self.assertRaisesRegex(ValidationError, "not supported"):
                    validate_request(
                        prompt="Create an image",
                        model="gpt-image-2.6-sunburst",
                        quality="medium",
                        aspect_ratio="1:1",
                        megapixels=1,
                        output_format=output_format,
                        stream="true",
                    )

        with self.assertRaisesRegex(ValidationError, "must be true or false"):
            validate_request(
                prompt="Create an image",
                model="gpt-image-2.6-sunburst",
                quality="medium",
                aspect_ratio="1:1",
                megapixels=1,
                stream="yes",
            )

    def test_image_selection_allows_no_input_and_rejects_empty_files(self):
        self.assertEqual(validate_images([]), [])
        with self.assertRaisesRegex(ValidationError, "empty"):
            validate_images(
                [
                    SimpleNamespace(
                        filename="empty.png",
                        stream=io.BytesIO(b""),
                    )
                ]
            )

    def test_generation_sends_selected_options_and_returns_image_bytes(self):
        image_request = validate_request(
            prompt="Edit image",
            model="gpt-image-2.5-flare",
            quality="high",
            aspect_ratio="1:1",
            megapixels=1,
            output_format="webp",
            output_compression=84,
            background="transparent",
        )
        image = SimpleNamespace(
            filename="reference.png",
            mimetype="image/png",
            stream=io.BytesIO(b"reference"),
        )
        response = image_api_response(b"generated")

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("backend.image_service.OpenAI") as openai:
                openai.return_value.images.edit.return_value = response
                result = generate_image([image], image_request)

        self.assertEqual(result.image_bytes, b"generated")
        request = openai.return_value.images.edit.call_args.kwargs
        self.assertEqual(request["model"], "gpt-image-2.5-flare")
        self.assertEqual(request["quality"], "high")
        self.assertEqual(request["size"], "1008x1008")
        self.assertEqual(request["output_format"], "webp")
        self.assertEqual(request["output_compression"], 84)
        self.assertEqual(request["background"], "transparent")

    def test_generation_without_input_images_uses_generate_endpoint(self):
        image_request = validate_request(
            prompt="A red fox in a snowy forest",
            model="gpt-image-2.5-sunburst",
            quality="medium",
            aspect_ratio="1:1",
            megapixels=1,
        )
        response = image_api_response(b"generated")

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("backend.image_service.OpenAI") as openai:
                openai.return_value.images.generate.return_value = response
                result = generate_image([], image_request)

        self.assertEqual(result.image_bytes, b"generated")
        request = openai.return_value.images.generate.call_args.kwargs
        self.assertEqual(request["prompt"], "A red fox in a snowy forest")
        self.assertEqual(request["model"], "gpt-image-2.5-sunburst")
        self.assertNotIn("output_compression", request)
        self.assertNotIn("frame_count", request)
        self.assertNotIn("frame_duration_ms", request)
        self.assertEqual(request["background"], "auto")
        openai.return_value.images.edit.assert_not_called()

    def test_gif_generation_uses_explicit_animation_selection(self):
        response = image_api_response(b"generated-gif")
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("backend.image_service.OpenAI") as openai:
                openai.return_value.images.generate.return_value = response
                image_request = validate_request(
                    prompt="Create an animation",
                    model="gpt-image-2.6-sunburst",
                    quality="medium",
                    aspect_ratio="1:1",
                    megapixels=1,
                    output_format="gif",
                    animated_gif=True,
                    frame_count=4,
                    frame_duration_ms=120,
                )
                self.assertEqual(
                    generate_image([], image_request).image_bytes,
                    b"generated-gif",
                )

        request = openai.return_value.images.generate.call_args.kwargs
        self.assertEqual(
            request["extra_body"],
            {"frame_count": 4, "frame_duration_ms": 120},
        )

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("backend.image_service.OpenAI") as openai:
                openai.return_value.images.generate.return_value = response
                image_request = validate_request(
                    prompt="Create a still image",
                    model="gpt-image-2.6-sunburst",
                    quality="medium",
                    aspect_ratio="1:1",
                    megapixels=1,
                    output_format="gif",
                    animated_gif=False,
                )
                self.assertEqual(
                    generate_image([], image_request).image_bytes,
                    b"generated-gif",
                )
                self.assertEqual(image_request.frame_count, 9)

        request = openai.return_value.images.generate.call_args.kwargs
        self.assertIsNone(request["extra_body"])

    def test_gif_edit_sends_animation_options(self):
        response = image_api_response(b"generated-gif")
        image = SimpleNamespace(
            filename="reference.png",
            mimetype="image/png",
            stream=io.BytesIO(b"reference"),
        )
        image_request = validate_request(
            prompt="Animate this image",
            model="gpt-image-2.6-sunburst",
            quality="medium",
            aspect_ratio="1:1",
            megapixels=1,
            output_format="gif",
            animated_gif=True,
            frame_count=2,
            frame_duration_ms=100,
        )

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("backend.image_service.OpenAI") as openai:
                openai.return_value.images.edit.return_value = response
                self.assertEqual(
                    generate_image([image], image_request).image_bytes,
                    b"generated-gif",
                )

        request = openai.return_value.images.edit.call_args.kwargs
        self.assertEqual(
            request["extra_body"],
            {"frame_count": 2, "frame_duration_ms": 100},
        )

    def test_openai_sdk_serializes_gif_options_from_extra_body(self):
        requests = []

        def handle_request(request):
            requests.append(json.loads(request.read()))
            return httpx2.Response(
                200,
                json={
                    "data": [
                        {
                            "b64_json": base64.b64encode(b"generated-gif").decode(
                                "ascii"
                            )
                        }
                    ]
                },
            )

        client = OpenAIClient(
            api_key="test-key",
            http_client=httpx2.Client(
                transport=httpx2.MockTransport(handle_request),
            ),
        )
        image_request = validate_request(
            prompt="Create an animation",
            model="gpt-image-2.6-sunburst",
            quality="medium",
            aspect_ratio="1:1",
            megapixels=1,
            output_format="gif",
            animated_gif=True,
            frame_count=4,
            frame_duration_ms=120,
        )
        try:
            with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
                with patch("backend.image_service.OpenAI", return_value=client):
                    self.assertEqual(
                        generate_image([], image_request).image_bytes,
                        b"generated-gif",
                    )
        finally:
            client.close()

        self.assertEqual(requests[0]["frame_count"], 4)
        self.assertEqual(requests[0]["frame_duration_ms"], 120)

    def test_streamed_generation_requests_three_partials_and_logs_no_image_data(self):
        image_bytes = b"final-image"
        stream = FakeImageStream(
            [
                image_stream_event(
                    "image_generation.partial_image",
                    b"preview-image",
                    index=0,
                ),
                image_stream_event(
                    "image_generation.completed",
                    image_bytes,
                    usage=SimpleNamespace(
                        input_tokens_details=SimpleNamespace(
                            image_tokens=100,
                            text_tokens=200,
                        ),
                        output_tokens=300,
                    ),
                ),
            ]
        )
        image_request = validate_request(
            prompt="Create an image",
            model="gpt-image-2.6-sunburst",
            quality="medium",
            aspect_ratio="1:1",
            megapixels=1,
            stream=True,
        )

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("backend.image_service.OpenAI") as openai:
                client = openai.return_value.__enter__.return_value
                client.images.generate.return_value = stream
                with self.assertLogs("backend.image_service", level="INFO") as logs:
                    events = list(generate_image_stream([], image_request))

        request = client.images.generate.call_args.kwargs
        self.assertTrue(request["stream"])
        self.assertEqual(request["partial_images"], 3)
        self.assertEqual(
            [event.type for event in events],
            ["partial_image", "completed"],
        )
        self.assertIsInstance(events[0], ImageStreamEvent)
        self.assertEqual(events[0].partial_image_index, 0)
        self.assertEqual(events[1].cost, Decimal("0.0108"))
        self.assertTrue(stream.closed)
        self.assertNotIn(
            base64.b64encode(b"preview-image").decode("ascii"),
            "\n".join(logs.output),
        )
        self.assertNotIn(
            base64.b64encode(image_bytes).decode("ascii"),
            "\n".join(logs.output),
        )

    def test_streamed_edit_uses_images_edit_endpoint(self):
        stream = FakeImageStream(
            [
                image_stream_event(
                    "image_edit.completed",
                    b"edited-image",
                    usage=SimpleNamespace(output_tokens=1_000),
                )
            ]
        )
        image = SimpleNamespace(
            filename="reference.png",
            mimetype="image/png",
            stream=io.BytesIO(b"reference"),
        )
        image_request = validate_request(
            prompt="Edit this image",
            model="gpt-image-2.6-sunburst",
            quality="medium",
            aspect_ratio="1:1",
            megapixels=1,
            stream=True,
        )

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("backend.image_service.OpenAI") as openai:
                client = openai.return_value.__enter__.return_value
                client.images.edit.return_value = stream
                events = list(generate_image_stream([image], image_request))

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].type, "completed")
        self.assertTrue(client.images.edit.call_args.kwargs["stream"])
        self.assertEqual(client.images.edit.call_args.kwargs["partial_images"], 3)

    def test_openai_sdk_streams_partial_images_and_serializes_request_options(self):
        requests = []
        encoded_preview = base64.b64encode(b"preview").decode("ascii")
        encoded_final = base64.b64encode(b"final").decode("ascii")
        events = [
            {
                "type": "image_generation.partial_image",
                "b64_json": encoded_preview,
                "partial_image_index": 0,
                "background": "auto",
                "created_at": 123,
                "output_format": "png",
                "quality": "medium",
                "size": "1024x1024",
            },
            {
                "type": "image_generation.completed",
                "b64_json": encoded_final,
                "background": "auto",
                "created_at": 123,
                "output_format": "png",
                "quality": "medium",
                "size": "1024x1024",
                "usage": {
                    "input_tokens": 300,
                    "input_tokens_details": {
                        "image_tokens": 100,
                        "text_tokens": 200,
                    },
                    "output_tokens": 300,
                    "total_tokens": 600,
                },
            },
        ]

        def handle_request(request):
            requests.append(json.loads(request.read()))
            body = "".join(
                f"event: {event['type']}\ndata: {json.dumps(event)}\n\n"
                for event in events
            )
            return httpx2.Response(
                200,
                headers={"content-type": "text/event-stream"},
                content=body,
            )

        client = OpenAIClient(
            api_key="test-key",
            http_client=httpx2.Client(
                transport=httpx2.MockTransport(handle_request),
            ),
        )
        image_request = validate_request(
            prompt="Create an image",
            model="gpt-image-2.6-sunburst",
            quality="medium",
            aspect_ratio="1:1",
            megapixels=1,
            stream=True,
        )
        try:
            with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
                with patch("backend.image_service.OpenAI", return_value=client):
                    image_events = list(generate_image_stream([], image_request))
        finally:
            client.close()

        self.assertTrue(requests[0]["stream"])
        self.assertEqual(requests[0]["partial_images"], 3)
        self.assertEqual(
            [event.type for event in image_events],
            ["partial_image", "completed"],
        )
        self.assertEqual(image_events[-1].cost, Decimal("0.0108"))

    def test_image_response_logs_metadata_without_image_payload(self):
        image_bytes = b"private-image-data"
        response = image_api_response(image_bytes)
        image_request = validate_request(
            prompt="Create an image",
            model="gpt-image-2.5-sunburst",
            quality="medium",
            aspect_ratio="1:1",
            megapixels=1,
        )

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("backend.image_service.OpenAI") as openai:
                openai.return_value.images.generate.return_value = response
                with self.assertLogs("backend.image_service", level="INFO") as logs:
                    result = generate_image([], image_request)
                    self.assertEqual(result.image_bytes, image_bytes)

        log_output = "\n".join(logs.output)
        self.assertIn('"created": 123', log_output)
        self.assertIn('"total_tokens": 42', log_output)
        self.assertIn("A generated image", log_output)
        self.assertNotIn(base64.b64encode(image_bytes).decode("ascii"), log_output)
        self.assertNotIn("https://images.example/generated.png", log_output)

    def test_svg_generation_rejects_input_images(self):
        image_request = validate_request(
            prompt="Create vector art",
            model="gpt-image-2.6-sunburst",
            quality="medium",
            aspect_ratio="1:1",
            megapixels=1,
            output_format="svg",
        )
        image = SimpleNamespace(
            filename="reference.png",
            mimetype="image/png",
            stream=io.BytesIO(b"reference"),
        )

        with self.assertRaisesRegex(ValidationError, "SVG output is not supported"):
            generate_image([image], image_request)

    def test_image_generation_cost_uses_available_token_categories(self):
        response = image_api_response(b"generated")
        response.usage = SimpleNamespace(
            input_tokens_details=SimpleNamespace(
                image_tokens=100_000,
                text_tokens=200_000,
            ),
            output_tokens=300_000,
        )
        image_request = validate_request(
            prompt="Create an image",
            model="gpt-image-2.5-sunburst",
            quality="medium",
            aspect_ratio="1:1",
            megapixels=1,
        )

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("backend.image_service.OpenAI") as openai:
                openai.return_value.images.generate.return_value = response
                result = generate_image([], image_request)

        self.assertEqual(result.cost, Decimal("10.8"))

    def test_image_generation_cost_is_partial_when_usage_is_incomplete(self):
        response = image_api_response(b"generated")
        response.usage = SimpleNamespace(output_tokens=100_000)
        image_request = validate_request(
            prompt="Create an image",
            model="gpt-image-2.5-sunburst",
            quality="medium",
            aspect_ratio="1:1",
            megapixels=1,
        )

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("backend.image_service.OpenAI") as openai:
                openai.return_value.images.generate.return_value = response
                result = generate_image([], image_request)

        self.assertEqual(result.cost, Decimal("3"))

    def test_image_generation_cost_is_unavailable_without_usage(self):
        image_request = validate_request(
            prompt="Create an image",
            model="gpt-image-2.5-sunburst",
            quality="medium",
            aspect_ratio="1:1",
            megapixels=1,
        )

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("backend.image_service.OpenAI") as openai:
                openai.return_value.images.generate.return_value = (
                    image_api_response(b"generated")
                )
                result = generate_image([], image_request)

        self.assertIsNone(result.cost)

    def test_description_image_must_be_png_and_at_most_one_megapixel(self):
        validate_description_image(png_header(1000, 1000))

        with self.assertRaisesRegex(ValidationError, "valid PNG"):
            validate_description_image(b"not an image")
        with self.assertRaisesRegex(ValidationError, "no larger than 1 megapixel"):
            validate_description_image(png_header(1001, 1000))

    def test_description_filename_is_sanitized_and_limited(self):
        self.assertEqual(
            sanitize_description_filename("A Red Fox in Snowy Forest.PNG"),
            "a_red_fox_in_snowy_forest",
        )
        self.assertLessEqual(
            len(sanitize_description_filename("one two three " + "x" * 60)),
            50,
        )
        with self.assertRaisesRegex(ImageServiceError, "at least three"):
            sanitize_description_filename("fox image")

    def test_description_uses_responses_api_and_requested_model_settings(self):
        image_bytes = png_header(24, 32)
        response = SimpleNamespace(
            output_text="Blue bird perched on branch",
            usage=SimpleNamespace(input_tokens=100_000, output_tokens=20_000),
            model_dump=lambda mode="json": {
                "id": "resp_test",
                "output_text": "Blue bird perched on branch",
                "usage": {"total_tokens": 18},
            },
        )

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("backend.image_service.OpenAI") as openai:
                openai.return_value.responses.create.return_value = response
                with self.assertLogs("backend.image_service", level="INFO") as logs:
                    result = generate_description(image_bytes)

        self.assertEqual(result.filename, "blue_bird_perched_on_branch")
        self.assertEqual(result.cost, Decimal("0.02"))
        self.assertIn("OpenAI responses.create response", logs.output[0])
        self.assertIn("resp_test", logs.output[0])
        self.assertIn('"total_tokens": 18', logs.output[0])
        request = openai.return_value.responses.create.call_args.kwargs
        self.assertEqual(request["model"], "gpt-6-luna")
        self.assertEqual(request["reasoning"], {"effort": "none"})
        self.assertEqual(
            request["input"][0]["content"][0],
            {"type": "input_text", "text": DESCRIPTION_PROMPT},
        )
        self.assertEqual(
            request["input"][0]["content"][1]["image_url"],
            "data:image/png;base64," + base64.b64encode(image_bytes).decode("ascii"),
        )


if __name__ == "__main__":
    unittest.main()
