# Creative Automation CLI (POC)

Python CLI proof-of-concept that ingests campaign briefs, reuses/generates product hero images, creates ratio variants, overlays campaign text, applies optional logo placement, and writes manifest + metrics outputs.

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

### 3) Install package

```bash
pip install -e .
```

Optional Gemini backend dependency:

```bash
pip install -e .[gemini]
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
                         [--generated-image-mode GENERATED_IMAGE_MODE]
                         [--generated-image-id GENERATED_IMAGE_ID]
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
  --generated-image-mode GENERATED_IMAGE_MODE
                        For missing product images: use 'new', 'last', 'id', or
                        pass an image ID directly.
  --generated-image-id GENERATED_IMAGE_ID
                        Image ID to use when --generated-image-mode id
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

## Cloud Storage Adaptation

`GeneratedImageStore` in `src/creative_automation_cli/storage/generated_store.py` provides three methods (`save_new`, `load_last_for_product`, `load_by_id`) against a local filesystem. Swapping to cloud storage (AWS S3, Azure Blob, Dropbox) requires only replacing those three method bodies with the relevant SDK calls — the rest of the pipeline is unaffected.

## Assumptions and Limitations

- Local execution only (no cloud storage integration). See **Cloud Storage Adaptation** above for the extension path.
- No authentication/security/compliance features beyond API key env vars for provider access.
- Translation is implemented: `--localize --provider mock` uses a `[locale] message` prefix; `--localize --provider real` calls the Gemini Developer API to translate the campaign message into each locale.
- Real provider support depends on model/account access and optional `google-genai` dependency (`pip install -e .[gemini]`).
