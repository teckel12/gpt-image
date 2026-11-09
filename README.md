# GPT Image

Web application for generating images from prompts and editing images with references through the OpenAI Images API. Generated images are previewed in the browser and downloaded there; the backend does not save generated files.

Choose PNG, JPEG, WebP, GIF, or SVG output. Downloads use `generated-image.<format>` as a default name that can be changed when saving. Compression applies to JPEG and WebP; transparent backgrounds apply to PNG and WebP. SVG output requires prompt-only generation.

## Requirements

- Python 3.13 or newer
- Node.js 24.17.0 and npm 11.13.0 (managed with nvm)
- An OpenAI API account with access to the image model you intend to use

## Setup

Create the Python virtual environment, install Python dependencies, and install frontend dependencies:

```bash
./setup.sh
```

Create a `.env` file in the project directory and add your OpenAI API key:

```dotenv
OPENAI_API_KEY=your_api_key_here
```

> Note: GPT Image API requests will incur charges. Check current pricing and model availability before running a workflow.

## Run the web interface in development

Start the Flask API in one terminal:

```bash
./backend.sh
```

Start Vite in another terminal:

```bash
nvm use && npm run dev
```

Open the HTTPS URL printed by Vite. For phone testing, use its Network URL; keep both devices on the same local network and allow Vite's listening port through the computer firewall. Vite proxies `/api` requests to Flask.

To trust the development certificate on a phone, install `~/.vite-plugin-mkcert/rootCA.pem` from the development computer on the phone. On iOS, install the downloaded profile, then enable full trust under **Settings > General > About > Certificate Trust Settings**. Never share `rootCA-key.pem`.

## Run tests

Run the Python and JavaScript unit test suites together:

```bash
nvm use && npm test
```

This uses the project virtual environment created by `./setup.sh`.

## Vue icons

- Material Design Icons are auto-resolved in Vue templates; no per-icon import is needed.
- Icon components use the `i-mdi-<icon-name>` format.
- MDI icon library used for icons in this project: <https://pictogrammers.com/library/mdi/>

## Build and run in production

Build the Vue interface:

```bash
nvm use && npm run build
```

Run the local production server:

```bash
.venv/bin/waitress-serve --listen=127.0.0.1:8080 --call backend.app:create_app
```

Open `http://127.0.0.1:8080`. Deployment must include the Python environment and root `dist/` build output.
