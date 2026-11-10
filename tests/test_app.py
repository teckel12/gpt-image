import io
import json
import struct
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from backend.app import create_app
from backend.image_service import (
    DescriptionResult,
    ImageGenerationResult,
    ImageServiceError,
    ImageStreamEvent,
)


class AppTests(unittest.TestCase):
    def setUp(self):
        self.client = create_app().test_client()

    def test_options_endpoint_lists_models_and_aspect_ratios(self):
        response = self.client.get("/api/options")

        self.assertEqual(response.status_code, 200)
        options = response.get_json()
        self.assertEqual(len(options["models"]), 4)
        self.assertEqual(len(options["aspect_ratios"]), 8)
        self.assertEqual(
            [model["value"] for model in options["models"]],
            [
                "gpt-image-2.5-flare",
                "gpt-image-2.5-sunburst",
                "gpt-image-2.6-flare",
                "gpt-image-2.6-sunburst",
            ],
        )
        self.assertEqual(
            [model["display_name"] for model in options["models"]],
            ["2.5 Flare", "2.5 Sunburst", "2.6 Flare", "2.6 Sunburst"],
        )
        self.assertEqual(
            options["models"][0]["description"],
            "fast, high-quality",
        )
        self.assertEqual(
            options["models"][1]["description"],
            "high-precision",
        )
        self.assertEqual(
            options["models"][0]["qualities"],
            ["low", "medium", "high", "xhigh", "max"],
        )
        self.assertEqual(
            options["models"][2]["description"],
            "fastest, high-quality",
        )
        self.assertEqual(
            options["models"][3]["description"],
            "fast, higher-precision",
        )
        self.assertEqual(
            options["input_image_cost_per_megapixel"],
            0.01,
        )
        self.assertEqual(
            options["models"][0]["quality_price_per_megapixel"]["low"],
            0.01,
        )
        self.assertEqual(
            options["models"][2]["quality_price_per_megapixel"]["low"],
            0.04,
        )
        self.assertEqual(
            options["models"][0]["quality_price_per_megapixel"]["medium"],
            0.02,
        )
        self.assertEqual(
            options["models"][2]["quality_price_per_megapixel"]["medium"],
            0.08,
        )
        self.assertEqual(
            options["models"][0]["quality_price_per_megapixel"]["max"],
            options["models"][2]["quality_price_per_megapixel"]["max"],
        )
        self.assertNotIn("gif", options["models"][0]["output_formats"])
        self.assertIn("gif", options["models"][2]["output_formats"])
        self.assertIn("svg", options["models"][2]["output_formats"])

    def test_generate_endpoint_returns_image_bytes_without_saving(self):
        with patch(
            "backend.app.generate_image",
            return_value=ImageGenerationResult(
                image_bytes=b"generated-image",
                cost=Decimal("0.0108"),
            ),
        ) as generate_image:
            response = self.client.post(
                "/api/generate",
                data={
                    "prompt": "Create a red fox in a snowy forest",
                    "model": "gpt-image-2.5-sunburst",
                    "quality": "medium",
                    "aspect_ratio": "1:1",
                    "megapixels": "1",
                    "resolution_width": "1280",
                    "resolution_height": "1024",
                    "output_format": "webp",
                    "output_compression": "75",
                    "background": "transparent",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "image/webp")
        self.assertEqual(response.data, b"generated-image")
        self.assertEqual(response.headers["X-Image-Generation-Cost"], "0.0108")
        self.assertEqual(
            response.headers["Content-Disposition"],
            "inline; filename=generated-image.webp",
        )
        self.assertEqual(generate_image.call_args.args[0], [])
        image_request = generate_image.call_args.args[1]
        self.assertEqual(image_request.size, "1280x1024")
        self.assertEqual(image_request.output_compression, 75)
        self.assertEqual(image_request.background, "transparent")

    def test_generate_endpoint_passes_gif_animation_settings(self):
        with patch(
            "backend.app.generate_image",
            return_value=ImageGenerationResult(
                image_bytes=b"generated-gif",
                cost=None,
            ),
        ) as generate_image:
            response = self.client.post(
                "/api/generate",
                data={
                    "prompt": "Create an animation",
                    "model": "gpt-image-2.6-sunburst",
                    "quality": "medium",
                    "aspect_ratio": "1:1",
                    "megapixels": "1",
                    "output_format": "gif",
                    "animated_gif": "true",
                    "frame_count": "3",
                    "frame_duration_ms": "120",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "image/gif")
        self.assertNotIn("X-Image-Generation-Cost", response.headers)
        image_request = generate_image.call_args.args[1]
        self.assertTrue(image_request.animated_gif)
        self.assertEqual(image_request.frame_count, 3)
        self.assertEqual(image_request.frame_duration_ms, 120)

    def test_stream_endpoint_relays_partial_and_completed_events(self):
        image_events = iter(
            [
                ImageStreamEvent(
                    type="partial_image",
                    b64_json="cHJldmlldw==",
                    partial_image_index=0,
                ),
                ImageStreamEvent(
                    type="completed",
                    b64_json="ZmluYWw=",
                    cost=Decimal("0.0108"),
                ),
            ]
        )
        with patch(
            "backend.app.generate_image_stream",
            return_value=image_events,
        ) as generate_image_stream:
            response = self.client.post(
                "/api/generate",
                data={
                    "prompt": "Create an image",
                    "model": "gpt-image-2.6-sunburst",
                    "quality": "medium",
                    "aspect_ratio": "1:1",
                    "megapixels": "1",
                    "output_format": "png",
                    "stream": "true",
                },
            )
            response_data = response.get_data(as_text=True)

        payloads = [
            json.loads(line.removeprefix("data: "))
            for line in response_data.splitlines()
            if line.startswith("data: ")
        ]
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "text/event-stream")
        self.assertEqual(
            [payload["type"] for payload in payloads],
            ["partial_image", "completed"],
        )
        self.assertEqual(payloads[0]["partial_image_index"], 0)
        self.assertEqual(payloads[1]["cost"], "0.0108")
        self.assertTrue(generate_image_stream.call_args.args[1].stream)

    def test_stream_endpoint_reports_iteration_errors_as_events(self):
        def image_events():
            yield ImageStreamEvent(
                type="partial_image",
                b64_json="cHJldmlldw==",
                partial_image_index=0,
            )
            raise ImageServiceError("Image stream ended without a completed image.")

        with self.assertLogs("backend.app", level="ERROR"):
            with patch(
                "backend.app.generate_image_stream",
                return_value=image_events(),
            ):
                response = self.client.post(
                    "/api/generate",
                    data={
                        "prompt": "Create an image",
                        "model": "gpt-image-2.6-sunburst",
                        "quality": "medium",
                        "aspect_ratio": "1:1",
                        "megapixels": "1",
                        "output_format": "png",
                        "stream": "true",
                    },
                )
                response_data = response.get_data(as_text=True)

        payloads = [
            json.loads(line.removeprefix("data: "))
            for line in response_data.splitlines()
            if line.startswith("data: ")
        ]
        self.assertEqual(payloads[-1]["type"], "error")
        self.assertIn("without a completed image", payloads[-1]["error"])

    def test_stream_endpoint_rejects_gif_output(self):
        response = self.client.post(
            "/api/generate",
            data={
                "prompt": "Create an image",
                "model": "gpt-image-2.6-sunburst",
                "quality": "medium",
                "aspect_ratio": "1:1",
                "megapixels": "1",
                "output_format": "gif",
                "stream": "true",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("not supported", response.get_json()["error"])

    def test_description_endpoint_returns_filename_for_png(self):
        image_bytes = (
            b"\x89PNG\r\n\x1a\n"
            + struct.pack(">I", 13)
            + b"IHDR"
            + struct.pack(">II", 20, 30)
        )
        with patch(
            "backend.app.generate_description",
            return_value=DescriptionResult(
                filename="red_fox_in_snow",
                cost=Decimal("0.02"),
            ),
        ) as generate_description:
            response = self.client.post(
                "/api/describe",
                data={
                    "image": (io.BytesIO(image_bytes), "description.png", "image/png"),
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json(),
            {"filename": "red_fox_in_snow", "cost": "0.02"},
        )
        self.assertEqual(
            generate_description.call_args.args[0],
            image_bytes,
        )

    def test_description_endpoint_requires_an_image(self):
        response = self.client.post("/api/describe", data={})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json(), {"error": "Description image is required."})

    def test_production_root_serves_built_frontend(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            Path(temporary_directory, "index.html").write_text(
                "<title>GPT Image Generator</title>",
                encoding="utf-8",
            )
            with patch("backend.app.FRONTEND_DIST", Path(temporary_directory)):
                response = self.client.get("/")

                self.assertEqual(response.status_code, 200)
                self.assertIn(b"GPT Image Generator", response.data)
                response.close()


if __name__ == "__main__":
    unittest.main()
