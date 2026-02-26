# Creative Automation CLI (POC)

Python CLI proof-of-concept that ingests campaign briefs, reuses/generates product hero images, creates ratio variants, overlays campaign text, applies optional logo placement, and writes manifest + metrics outputs.

## Project Structure

```
├── src/
│   └── creative_automation_cli/
│       ├── cli.py                    # Entry point, arg parsing
│       ├── pipeline.py               # Core orchestrator (run_pipeline)
│       ├── brief_loader.py           # Load + validate brief YAML/JSON
│       ├── exceptions.py             # Custom exceptions
│       ├── localization.py           # Locale resolution + message translation
│       ├── storage.py                # GeneratedImageStore + S3Mirror
│       ├── assets/
│       │   └── resolver.py           # Resolve product assets from disk
│       ├── compliance/
│       │   ├── brand.py              # Brand compliance evaluation
│       │   ├── legal.py              # Legal text evaluation
│       │   ├── legal_policy.py       # LegalPolicy model + loader
│       │   └── policy.py             # BrandPolicy model + loader
│       ├── imaging/
│       │   ├── logo_overlay.py       # Logo placement on images
│       │   ├── text_overlay.py       # Campaign message overlay
│       │   └── variants.py           # Ratio variant generation (1x1, 9x16, 16x9)
│       ├── models/
│       │   ├── brief.py              # Pydantic CampaignBrief model
│       │   └── schema_export.py      # JSON schema export utility
│       ├── output/
│       │   ├── manifest.py           # CampaignManifest + ProductManifestEntry
│       │   ├── metrics.py            # RunMetrics + Timer
│       │   └── writer.py             # save_image, write_json
│       ├── prompts/
│       │   └── builder.py            # build_generation_prompt
│       └── providers/
│           ├── base.py               # ImageProvider ABC
│           ├── factory.py            # create_provider()
│           ├── mock.py               # Mock provider
│           ├── gemini_developer.py   # Gemini Developer API backend
│           └── gemini_vertex.py      # Gemini Vertex AI backend
├── tests/                            # pytest suite
├── examples/                         # Sample briefs (YAML + JSON)
├── config/                           # Default brand/legal policy YAML
├── schemas/                          # JSON schema artifacts
├── output/                           # Committed sample run output
├── storage/                          # Generated image store
├── assets/                           # Product asset files
├── ARCHITECTURE.mmd                  # Mermaid flowchart of the pipeline
├── pyproject.toml                    # Build config + dependencies
└── README.md
```

## Install

### 1) Create environment

```bash
python -m venv .venv
```

### 2) Activate environment

Windows (PowerShell):

```powershell
.\.venv\Scripts\Activate.ps1
```

macOS / Linux:

```bash
source .venv/bin/activate
```

### 3) Install package

```bash
pip install -e .
```

Optional dependencies — install only what you need:

**Gemini** — required when using `--provider real` to call the Gemini image generation and translation APIs. Not needed for mock runs.

```bash
pip install -e .[gemini]
```

**S3** — required when `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` are present in the environment. Enables mirroring output and generated images to S3 and falling back to S3 on local cache misses. Not needed for local-only runs.

```bash
pip install -e .[s3]
```

**Dev** — required for running tests and linting during development. Not needed to run the CLI.

```bash
pip install -e .[dev]
```

Install everything at once:

```bash
pip install -e .[gemini,s3,dev]
```

## CLI Usage

```bash
generate_campaign --brief examples/adobe-client-campaign.yaml --assets ./assets --output ./output --provider mock
```

Localized run (mock translation):

```bash
generate_campaign --brief examples/adobe-client-campaign.yaml --assets ./assets --output ./output --provider mock --localize
```

Real Gemini run with brand + legal checks:

```bash
generate_campaign --brief examples/adobe-client-campaign.yaml --assets ./assets --output ./output --provider real --localize --strict-brand --strict-legal
```

Legal preflight only (no image generation):

```bash
generate_campaign --brief examples/adobe-client-campaign.yaml --provider mock --validate-legal-only
```

### Full flag reference

```text
usage: generate_campaign [-h] --brief BRIEF [--assets ASSETS]
                         [--output OUTPUT] [--provider {mock,real}]
                         [--locale LOCALE] [--localize] [--dry-run]
                         [--gemini-backend {developer,vertex}]
                         [--gemini-model GEMINI_MODEL]
                         [--brand-policy BRAND_POLICY] [--strict-brand]
                         [--legal-policy LEGAL_POLICY] [--strict-legal]
                         [--validate-legal-only]
                         [--storage-root STORAGE_ROOT]

Creative Automation CLI POC

options:
  -h, --help            show this help message and exit
  --brief BRIEF         Path to campaign brief (.yaml/.yml/.json)
  --assets ASSETS       Assets root folder
  --output OUTPUT       Output root folder
  --provider {mock,real}
                        Provider mode
  --locale LOCALE       Optional single locale to append to brief locals
  --localize            Enable localization output using brief locals list
  --dry-run             Plan actions and skip image file writes
  --gemini-backend {developer,vertex}
                        Gemini backend used when --provider real
  --gemini-model GEMINI_MODEL
                        Gemini image model name
  --brand-policy BRAND_POLICY
                        Path to brand policy file (.yaml/.yml/.json). If
                        omitted, config/brand_policy.yaml is used when present.
  --strict-brand        Fail run when brand compliance violations are detected.
  --legal-policy LEGAL_POLICY
                        Path to legal policy file (.yaml/.yml/.json). If
                        omitted, config/legal_policy.yaml is used when present.
  --strict-legal        Fail run when blocked legal terms/expressions are detected.
  --validate-legal-only
                        Run legal policy checks only (no image generation or file output).
  --storage-root STORAGE_ROOT
                        Local storage root for generated images.
```

## Brief Schema

Required fields:

- `campaign_id`
- `message`
- `target_region`
- `target_audience`
- `products` (array with minimum 2 items, each requiring `id` and `name`)

Optional fields:

- `locals` (array of locale codes, e.g., `es`, `pt-BR`)
- `visual_style` (`keywords`, `mood`, `palette`)
- `prompts` (map)
- `palette`
- `negative_prompt`
- per-product `prompt`, `image`, `logo`

Schema file: `schemas/brief.schema.json`

Examples:

- Template YAML: `examples/template_brief.yaml`
- Template JSON: `examples/template_brief.json`
- Real campaign: `examples/adobe-client-campaign.yaml`

> **Note:** `examples/adobe-client-campaign.yaml` product 2 deliberately includes the phrase "Free money guaranteed" at the end of its prompt to demonstrate the legal policy check. It is an intentional test fixture, not a mistake.

## Asset Folder Structure

```text
assets/
  fonts/             # bundled fonts used for text overlay
  {product_id}/
    logo.png
    product.png        # optional (if missing, image is generated)
    background.png     # optional (reserved for future use)
```

Bundled fonts in `assets/fonts/` (no system font installation required):

| File | Use |
|---|---|
| `AdobeClean-Regular.otf` | Brand primary typeface |
| `AdobeClean-Bold.otf` | Brand bold variant |
| `AdobeClean-Light.otf` | Brand light variant |
| `SourceSans3-Regular.ttf` | Brand fallback |
| `SourceCodePro-Regular.ttf` | Brand fallback |

The text overlay automatically searches `assets/fonts/` before falling back to system fonts.

## Output Structure

```text
output/
  {campaign_id}/
    manifest.json
    metrics.json
    {product_id}/
      1x1/final.png
      1x1/final_es.png
      1x1/final_pt_br.png
      9x16/final.png
      16x9/final.png
```

Generated hero images for missing assets are stored under:

```text
storage/
  generated/
    {product_id}/
      {image_id}.png
```

Behavior for missing product image assets:

- `new`: generate with provider and store with new id
- `last`: reuse most recent stored generated image for the same product id
- `id`: load a specific stored image by id

## Legal Content Policy

Default legal policy path:

- `config/legal_policy.yaml`

Policy schema:

- `schemas/legal_policy.schema.json`

Current legal checks:

- blocked keywords
- blocked regular expressions
- optional locale-specific overrides

Use strict legal mode to block outputs when forbidden terms/expressions are found:

```bash
generate_campaign --brief examples/brief.yaml --assets ./assets --output ./output --provider mock --strict-legal
```

Run legal checks only (preflight, no image generation):

```bash
generate_campaign --brief examples/brief.yaml --assets ./assets --output ./output --provider mock --validate-legal-only
```

When `--localize` is enabled, English is always rendered as `final.png`, and each locale from brief `locals` is emitted as `final_{locale}.png` (normalized lowercase with `_`).

    `manifest.json` also includes per-ratio brand compliance results when a policy is loaded.

## Brand Compliance Policy

Default policy path:

- `config/brand_policy.yaml`

Policy schema:

- `schemas/brand_policy.schema.json`

Current checks:

- required logo presence
- expected logo filename (allow-list)
- palette coverage thresholds (warning-level)
- imagery prompt keyword checks (required + prohibited)

Use strict mode to fail fast on violations:

```bash
generate_campaign --brief examples/adobe-client-campaign.yaml --assets ./assets --output ./output --provider mock --strict-brand
```

## Design Decisions

- Modular package split: brief loading, assets, prompts, providers, imaging, outputs, orchestration.
- Dual schema strategy: Pydantic runtime validation + persisted JSON schema artifact.
- Provider abstraction supports local mock mode and real Gemini backends via factory.
- Variant generation derives all output ratios from one base hero per product.
- Text readability enforced with blurred backdrop + semi-transparent rounded container.

## Code Quality

Static analysis is configured via `pyrightconfig.json` (strict Pyright type checking) and `[tool.ruff]` in `pyproject.toml`. To run linting locally:

```bash
pip install ruff
ruff check src/
```

## Example Output

A full sample run output is committed at `output/adobe-client-campaign/`. It includes:

- `manifest.json` — per-product, per-ratio compliance results and output file paths
- `metrics.json` — asset reuse/generation counts and execution time
- `product_1/{1x1,9x16,16x9}/final.png` — generated hero variants with text overlay
- `product_2/{1x1,9x16,16x9}/final.png` — reused hero variants with text overlay

## AWS S3 Mirror (optional)

When `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` are present in the
environment (or in a `.env` file in the project root), the pipeline
automatically mirrors **all** local writes to the S3 bucket
`gabriel-adobe-fde-tha` and falls back to S3 on local cache misses.

If no credentials are found the tool runs in **local-only mode** with no
change in behavior.

### Install the optional S3 dependency

```bash
pip install -e .[s3]
```

### Required environment variables

| Variable | Required | Description |
|---|---|---|
| `AWS_ACCESS_KEY_ID` | Yes | IAM access key |
| `AWS_SECRET_ACCESS_KEY` | Yes | IAM secret key |
| `AWS_DEFAULT_REGION` | No (default `us-east-1`) | Bucket region |

Add them to your `.env` file in the project root (the CLI loads it automatically):

```dotenv
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
AWS_DEFAULT_REGION=us-east-1
```

### What is mirrored

| Local path | S3 key |
|---|---|
| `storage/generated/{type}_{product_id}.png` | `generated/{type}_{product_id}.png` |
| `storage/generated/{product_id}/{image_id}.png` | `generated/{product_id}/{image_id}.png` |
| `output/{campaign_id}/{product_id}/{ratio}/final*.png` | `output/{campaign_id}/{product_id}/{ratio}/final*.png` |
| `output/{campaign_id}/manifest.json` | `output/{campaign_id}/manifest.json` |
| `output/{campaign_id}/metrics.json` | `output/{campaign_id}/metrics.json` |

### Generated asset reuse (roadmap)

Currently the pipeline always generates fresh product, logo, and background
assets when they are absent from the `assets/` folder, saving them as
`{type}_{product_id}.png` directly under `storage/generated/` (and mirroring
to S3 when configured).

A future iteration will add a `--reuse-assets` flag and a lookup step that
checks `storage/generated/` (and, on a cache miss, attempts an S3 download)
before kicking off a new generation request.  The flat-file naming scheme —
one file per `(type, product_id)` tuple — is intentionally designed to make
that lookup trivial: no subfolder traversal or timestamp comparison required.

### Extension path

`S3Mirror` in `src/creative_automation_cli/storage/s3_mirror.py` exposes
only four methods (`upload_file`, `download_file`, `list_keys`, domain
helpers). Adapting to Azure Blob or Dropbox requires replacing those method
bodies with the corresponding SDK calls — the rest of the pipeline is
unaffected.

## Path to Production

This POC demonstrates the complete creative automation loop end-to-end. Taking it to an enterprise production environment would require the following architectural evolutions:

1. **Concurrency & Async I/O** — The current pipeline processes products, ratios, and locales sequentially. In production, GenAI API calls (image generation, translation) should be parallelised using `asyncio` or `concurrent.futures.ThreadPoolExecutor` to reduce total campaign generation time proportionally to the number of products.

2. **Step-based Pipeline Architecture** — The main orchestration loop should be refactored into a Chain of Responsibility (Step) pattern. Each discrete concern (`LegalCheckStep`, `LocalizationStep`, `TextOverlayStep`, `BrandComplianceStep`, `StorageStep`) becomes an independent, testable class that receives a `PipelineContext` object. This allows Adobe to inject additional steps (e.g. `WatermarkStep`, `AutoTaggingStep`) without touching the core loop, adhering to the Open/Closed Principle.

3. **Structured Logging** — Standard Python logging should be swapped for structured JSON logging (e.g. [`structlog`](https://www.structlog.org/)) so that compliance warnings, generation metrics, and S3 upload events can be ingested and queried directly in Datadog or AWS CloudWatch without parsing free-form strings.

4. **Event-Driven Trigger** — Rather than a synchronous CLI, a production system would expose the pipeline as a Lambda or Fargate task triggered by an SQS message or EventBridge rule, with the campaign brief delivered as a JSON payload from an upstream orchestration system (e.g. Adobe Workfront).

5. **Signed URL Asset Delivery** — The current `S3Mirror` uploads finished PNG files. In production, output assets should be surfaced as pre-signed S3 URLs with a short TTL and registered in a DAM (Digital Asset Management) system (e.g. Adobe Experience Manager Assets) rather than consumed directly from the bucket.

## Assumptions and Limitations

- S3 mirroring is optional and activated only when AWS credentials are present. See **AWS S3 Mirror** above.
- No authentication/security/compliance features beyond API key env vars for provider access.
- Translation is implemented: `--localize --provider mock` uses a `[locale] message` prefix; `--localize --provider real` calls the Gemini Developer API to translate the campaign message into each locale.
- Real provider support depends on model/account access and optional `google-genai` dependency (`pip install -e .[gemini]`).
