import json
import logging
from io import BytesIO
from pathlib import Path

from dotenv import load_dotenv
from flask import (
    Flask,
    Response,
    abort,
    jsonify,
    request,
    send_file,
    send_from_directory,
    stream_with_context,
)
from openai import OpenAIError

from backend.image_service import (
    ASPECT_RATIOS,
    INPUT_IMAGE_COST_PER_MEGAPIXEL,
    MODEL_DESCRIPTIONS,
    MODEL_DISPLAY_NAMES,
    MODEL_OUTPUT_FORMATS,
    MODEL_QUALITY_COST_PER_MEGAPIXEL,
    MODEL_QUALITIES,
    OUTPUT_MIME_TYPES,
    PROJECT_ROOT,
    ConfigurationError,
    ImageServiceError,
    ValidationError,
    generate_description,
    generate_image,
    generate_image_stream,
    validate_images,
    validate_request,
)

FRONTEND_DIST = PROJECT_ROOT / "dist"


def create_app() -> Flask:
    load_dotenv(PROJECT_ROOT / ".env")
    app = Flask(__name__, static_folder=None)

    @app.get("/api/options")
    def options():
        return jsonify(
            models=[
                {
                    "value": model,
                    "display_name": MODEL_DISPLAY_NAMES[model],
                    "description": MODEL_DESCRIPTIONS[model],
                    "qualities": list(qualities),
                    "quality_price_per_megapixel": (
                        MODEL_QUALITY_COST_PER_MEGAPIXEL[model]
                    ),
                    "output_formats": sorted(MODEL_OUTPUT_FORMATS[model]),
                }
                for model, qualities in MODEL_QUALITIES.items()
            ],
            input_image_cost_per_megapixel=INPUT_IMAGE_COST_PER_MEGAPIXEL,
            aspect_ratios=[
                {"value": value, "label": f"{value} ({details[0]})"}
                for value, details in ASPECT_RATIOS.items()
            ],
        )

    @app.post("/api/generate")
    def generate():
        try:
            image_request = validate_request(
                prompt=request.form.get("prompt", ""),
                model=request.form.get("model", ""),
                quality=request.form.get("quality", ""),
                aspect_ratio=request.form.get("aspect_ratio", ""),
                megapixels=request.form.get("megapixels", ""),
                resolution_width=request.form.get("resolution_width"),
                resolution_height=request.form.get("resolution_height"),
                output_format=request.form.get("output_format", "png"),
                output_compression=request.form.get("output_compression"),
                background=request.form.get("background"),
                animated_gif=request.form.get("animated_gif"),
                frame_count=request.form.get("frame_count"),
                frame_duration_ms=request.form.get("frame_duration_ms"),
                stream=request.form.get("stream"),
            )
            images = validate_images(request.files.getlist("images"))
            if image_request.stream:
                image_events = generate_image_stream(images, image_request)

                def stream_response():
                    try:
                        for event in image_events:
                            payload = {
                                "type": event.type,
                                "b64_json": event.b64_json,
                            }
                            if event.type == "partial_image":
                                payload["partial_image_index"] = (
                                    event.partial_image_index
                                )
                            else:
                                payload["cost"] = (
                                    str(event.cost)
                                    if event.cost is not None
                                    else None
                                )
                            yield f"data: {json.dumps(payload)}\n\n"
                    except OpenAIError:
                        app.logger.exception("OpenAI image stream failed")
                        yield (
                            "data: "
                            + json.dumps(
                                {
                                    "type": "error",
                                    "error": (
                                        "OpenAI image request failed. "
                                        "Check server logs."
                                    ),
                                }
                            )
                            + "\n\n"
                        )
                    except ImageServiceError as error:
                        app.logger.exception("Image API stream returned invalid data")
                        yield (
                            "data: "
                            + json.dumps(
                                {"type": "error", "error": str(error)}
                            )
                            + "\n\n"
                        )

                return Response(
                    stream_with_context(stream_response()),
                    mimetype="text/event-stream",
                    headers={
                        "Cache-Control": "no-cache",
                        "X-Accel-Buffering": "no",
                    },
                )
            image_result = generate_image(images, image_request)
        except ValidationError as error:
            return jsonify(error=str(error)), 400
        except ConfigurationError as error:
            return jsonify(error=str(error)), 503
        except OpenAIError:
            app.logger.exception("OpenAI image request failed")
            return jsonify(error="OpenAI image request failed. Check server logs."), 502
        except ImageServiceError as error:
            app.logger.exception("Image API returned invalid image data")
            return jsonify(error=str(error)), 502

        response = send_file(
            BytesIO(image_result.image_bytes),
            mimetype=OUTPUT_MIME_TYPES[image_request.output_format],
            as_attachment=False,
            download_name=f"generated-image.{image_request.output_format}",
        )
        if image_result.cost is not None:
            response.headers["X-Image-Generation-Cost"] = str(image_result.cost)
        return response

    @app.post("/api/describe")
    def describe():
        image = request.files.get("image")
        if image is None:
            return jsonify(error="Description image is required."), 400
        try:
            description = generate_description(image.read())
        except ValidationError as error:
            return jsonify(error=str(error)), 400
        except ConfigurationError as error:
            return jsonify(error=str(error)), 503
        except OpenAIError:
            app.logger.exception("OpenAI description request failed")
            return jsonify(error="OpenAI description request failed. Check server logs."), 502
        except ImageServiceError as error:
            app.logger.exception("OpenAI returned an invalid image description")
            return jsonify(error=str(error)), 502

        return jsonify(
            filename=description.filename,
            cost=str(description.cost) if description.cost is not None else None,
        )

    @app.get("/")
    @app.get("/<path:asset_path>")
    def frontend(asset_path: str = ""):
        if asset_path.startswith("api/"):
            abort(404)
        if not (FRONTEND_DIST / "index.html").is_file():
            return jsonify(error="Frontend build not found. Run the Vite production build."), 503
        requested_file = FRONTEND_DIST / asset_path
        if asset_path and requested_file.is_file():
            return send_from_directory(FRONTEND_DIST, asset_path)
        return send_from_directory(FRONTEND_DIST, "index.html")

    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    create_app().run(host="127.0.0.1", port=5050, debug=True)
