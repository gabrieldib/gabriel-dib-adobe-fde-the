# Creative Automation CLI — Execution Flow & Module Reference

This document walks through the full execution of the application from the CLI entry point to
the final output files, in the exact order that modules and sub-modules are invoked.

---

## 1. Entry Point — `cli.py`

The installed console script `creative-automation` invokes `main()` in `cli.py`.

### 1.1 Environment loading

Before anything else, `_load_default_env_files()` is called. It locates two `.env` files:

- One at the project root (two levels above `cli.py`)
- One at the current working directory (if different)

`_load_env_file(path)` reads each file line by line and calls `os.environ.setdefault(KEY, VALUE)`
for every `KEY=VALUE` pair, skipping comments and blank lines.
`_strip_optional_quotes(value)` cleans surrounding quotes that editors may add.

This is what makes `GEMINI_API_KEY`, `AWS_ACCESS_KEY_ID`, etc. available to the rest of the
app without requiring the shell to have them pre-exported.

### 1.2 Argument parsing — `parse_args()`

`argparse` declares the full CLI surface:

| Flag | Purpose |
|---|---|
| `--brief` | Path to the campaign YAML or JSON file (required) |
| `--assets` | Root folder where product asset folders live |
| `--output` | Root folder where output images and JSON will be written |
| `--provider` | `mock` (no API calls) or `real` (Gemini) |
| `--locale` | A single extra locale code to render (e.g. `pt_br`) |
| `--localize` | Enables full multi-locale rendering from the brief's `locals` list |
| `--dry-run` | Runs the pipeline without writing any files |
| `--gemini-backend` | `developer` (API key) or `vertex` (GCP service account) |
| `--gemini-model` | Model name; defaults to env var `GEMINI_MODEL` |
| `--brand-policy` | Path to brand policy YAML; falls back to `config/brand_policy.yaml` |
| `--strict-brand` | Fail the run (instead of warn) on brand violations |
| `--legal-policy` | Path to legal policy YAML; falls back to `config/legal_policy.yaml` |
| `--strict-legal` | Fail the run on legal violations |
| `--validate-legal-only` | Dry-run legal checks only, no image generation |
| `--generated-image-mode` | `new` / `last` / `id` — controls hero image sourcing |
| `--generated-image-id` | Explicit stored image ID for `--generated-image-mode id` |
| `--storage-root` | Root for the generated-image cache (default `./storage`) |

### 1.3 Image mode resolution — `_resolve_generated_image_selection()`

Normalises the `--generated-image-mode` / `--generated-image-id` pair.
Accepts a bare image ID string as the mode value (shortcut for `--generated-image-mode id`).
`_normalize_generated_image_id()` strips whitespace and `.png` suffixes.

### 1.4 RunConfig construction — `pipeline.RunConfig`

All parsed arguments are assembled into a `RunConfig` dataclass (defined in `pipeline.py`,
used here). `RunConfig` is a `@dataclass(slots=True)` — not a Pydantic model — because its
fields come from the already-validated CLI layer and need no further coercion.

```
RunConfig
  brief_path, assets_root, output_root
  provider_mode, gemini_backend, gemini_model
  locale, localize, dry_run
  brand_policy_path, strict_brand
  legal_policy_path, strict_legal
  storage_root
```

### 1.5 Dispatch

`main()` then calls one of two pipeline functions, both from `pipeline.py`:

- `run_legal_validation_only(config)` — when `--validate-legal-only` is set
- `run_pipeline(config)` — the full image-generation pipeline

---

## 2. `run_legal_validation_only()` — `pipeline.py`

Used when only legal text compliance needs to be verified, without generating any images.

### 2.1 Brief loading — `brief_loader.load_and_validate_brief()`

Reads the campaign YAML or JSON file.

1. `_parse_brief_file(path)` — dispatches to `yaml.safe_load` or `json.loads` based on file
   suffix. The result must be a `dict`; anything else raises `BriefValidationError`.
2. `CampaignBrief.model_validate(parsed)` — Pydantic v2 validates the dict against the model.
   On failure, each Pydantic error is formatted into a human-readable message and re-raised as
   `BriefValidationError`.

`CampaignBrief` (in `models/brief.py`) is a `BaseModel` subclass with nested models:

```
CampaignBrief
  campaign_id, message, target_region, target_audience  (required strings)
  locals: list[str]                                     (locale codes)
  products: list[ProductBrief]                          (min 2)
  visual_style: VisualStyle | None
  prompts: dict[str, str] | None
  palette: list[str] | None
  negative_prompt: str | None

ProductBrief
  id, name  (required)
  prompt, image, logo  (optional)

VisualStyle
  keywords: list[str]
  mood: str | None
  palette: list[str]
```

### 2.2 Legal policy loading — `compliance.legal_policy.load_legal_policy()`

Reads the legal policy YAML or JSON, validates it against `schemas/legal_policy.schema.json`
via `jsonschema`, and returns a `LegalPolicy` Pydantic model:

```
LegalPolicy
  version: int
  default_action: "warn" | "block"
  checks: LegalChecksPolicy
    blocked_keywords: list[str]
    blocked_regex: list[str]
  locale_overrides: dict[str, LegalChecksPolicy]
```

If no policy file is found, `ConfigurationError` is raised immediately — legal-only validation
cannot run without a policy.

### 2.3 Localizer setup — `localization.build_localizer()`

Constructs a `MessageLocalizer` that will translate the campaign message for each locale.
Defined in `localization/translator.py`, re-exported via `localization/__init__.py`.

The factory selects the implementation based on the run configuration:

| Condition | Implementation |
|---|---|
| `localize=False` | `NoopLocalizer` — returns message unchanged |
| `localize=True` + `mock` provider | `MockLocalizer` — returns `"[{locale}] {message}"` |
| `localize=True` + `real` + `developer` | `GeminiDeveloperLocalizer` — calls Gemini API |
| anything else | `NoopLocalizer` |

The localizer is built here even for legal-only mode because legal checks run on the
**translated** message in each locale — you need to check what users will actually see.

### 2.4 Locale resolution — `localization.resolve_output_locales()`

Builds the final list of locale codes to check:

1. Always starts with `["en"]`.
2. If `localize=True`, appends `brief.locals` and `config.locale`.
3. Deduplicates, normalising via `normalize_locale()` (lowercase, `-` → `_`).

### 2.5 Per-product legal evaluation loop

For each product in `brief.products`:

1. A stub `ResolvedProductAssets` is constructed with no actual file paths (legal-only mode
   does not touch the filesystem for images).
2. `prompts.builder.build_generation_prompt(brief, resolved)` assembles the AI prompt text
   that would be sent to the image provider — this text is what gets legally checked.
3. `compliance.legal.evaluate_legal_text(prompt, "en", policy)` is called:
   - `_checks_for_locale()` merges global checks with any locale-specific overrides.
   - `_normalize_for_matching()` inserts spaces at camelCase boundaries.
   - Scans for `blocked_keywords` (case-insensitive substring match).
   - Scans for `blocked_regex` patterns (`re.IGNORECASE`).
   - Returns `LegalCheckResult` with `flagged`, `should_block`, `hits`, `violations`.
4. For each locale, `localizer.translate()` is called, then `evaluate_legal_text` on the
   translated message.

The aggregated result is returned as a `summary` dict. If `strict_legal` and any check is
blocked, `ComplianceViolationError` is raised.

---

## 3. `run_pipeline()` — `pipeline.py`

The full image-generation pipeline. Returns `(manifest_dict, metrics_dict)`.

### 3.1 Initialisation

All dependencies are wired up in sequence before the product loop begins:

```
Timer()                                # perf_counter start
load_and_validate_brief()              →  CampaignBrief
create_provider()                      →  ImageProvider
build_localizer()                      →  MessageLocalizer
S3Mirror.from_env()                    →  S3Mirror | None
GeneratedImageStore(root, s3_mirror)   →  generated image cache
resolve_product_assets(assets_root, brief) →  list[ResolvedProductAssets]
_resolve_brand_policy(path)            →  BrandPolicy | None
_resolve_legal_policy(path)            →  LegalPolicy | None
resolve_output_locales(...)            →  list[str]
CampaignManifest(...)                  →  output manifest object
RunMetrics()                           →  counters object
```

**Provider factory — `providers.factory.create_provider()`**

Returns the correct `ImageProvider` implementation:

- `MockImageProvider` (`providers/mock.py`) — generates a gradient image seeded from a SHA-256
  hash of the prompt; draws a "MOCK HERO" label. No API calls.
- `GeminiDeveloperProvider` (`providers/gemini_developer.py`) — reads `GEMINI_API_KEY`,
  builds a `google.genai.Client`, sends the prompt with size hints, extracts the first
  `inline_data` image part.
- `GeminiVertexProvider` (`providers/gemini_vertex.py`) — reads `GOOGLE_CLOUD_PROJECT` and
  `GOOGLE_CLOUD_LOCATION`, uses Vertex AI client with `response_modalities=["IMAGE","TEXT"]`.

All three implement the same `ImageProvider` ABC from `providers/base.py`:
`generate_base_hero(prompt, size, negative_prompt) -> PIL.Image`.

**Storage — `storage.GeneratedImageStore`**

Manages `{storage_root}/generated/{product_id}/` PNG files. Wraps an optional `S3Mirror`
for cloud persistence. Key methods:
- `save_new(product_id, image)` — generates a timestamped ID, saves locally, uploads to S3.
- `load_last_for_product(product_id)` — newest local PNG; falls back to S3 listing.
- `load_by_id(image_id)` — `rglob` search; falls back to S3 download.

**S3 mirror — `storage.S3Mirror`**

Wraps a `boto3` S3 client targeting bucket `gabriel-adobe-fde-tha`.
Created only when `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY` are present in the environment.
All operations are best-effort; errors are logged as warnings and never re-raised.

**Asset resolution — `assets.resolver.resolve_product_assets()`**

For each `ProductBrief`, looks up these paths under `{assets_root}/{product.id}/`:
- `{image_filename}` or `product.png` → `hero_path`
- `logo.png` → `logo_path`
- `background.png` → `background_path`

Sets `hero_source = "reused"` if the hero file exists, `"generated"` otherwise.
Returns one `ResolvedProductAssets` dataclass per product.

### 3.2 Product loop — `_process_product()`

Called once per product in `resolved_assets`. Orchestrates all per-product work.

#### 3.2.1 Prompt building — `prompts.builder.build_generation_prompt()`

If `product.prompt` is explicitly set in the brief, that is used directly.
Otherwise assembles: product name + target audience + target region + visual style keywords
+ mood + "No text overlays" suffix.

#### 3.2.2 Base image acquisition — `_load_reused_or_generate_base()`

Decision tree for the hero image:

```
hero_path exists on disk?
  YES → _compose_reused_variant()          source = "reused"
  NO  →
    mode == "last"?
      YES → store.load_last_for_product()  source = "generated_last"
              (S3 fallback on local miss)
              on miss → fall through to generate
    mode == "id"?
      YES → store.load_by_id(id)           source = "generated_id"
              (S3 fallback on local miss)
              error if not found
    mode == "new" (default):
      provider.generate_base_hero(prompt)  source = "generated_new"
      store.save_new(product_id, image)    (skipped on dry-run)
```

`_compose_reused_variant()` opens the hero PNG as RGBA, composites it centered over the
background image (or a white canvas) cropped to the target ratio size.

#### 3.2.3 Prompt legal check

If a `LegalPolicy` is loaded, `evaluate_legal_text(prompt, "en", policy)` is called.
Result stored in `entry.legal["prompt"]`. If `should_block` → raises `ComplianceViolationError`.

#### 3.2.4 Ratio variant loop

For each of the three aspect ratios `{1x1, 9x16, 16x9}`:

**Variant creation — `imaging.variants.create_variant()`**

`ImageOps.fit` center-crops the base image to the target pixel dimensions using LANCZOS
resampling. For reused assets, `_compose_reused_variant()` is called instead to preserve
alpha compositing.

**Locale rendering loop**

For each locale code in `locales_to_render`:

1. **Translation** — `localizer.translate(brief.message, locale_code)` is called for
   non-English locales. English is always passed through unchanged.

2. **Message legal check** — `evaluate_legal_text(localized_message, locale_code, policy)`.
   Blocks if `should_block`.

3. **Text overlay — `imaging.text_overlay.overlay_campaign_message()`**
   - Converts image to RGBA.
   - Defines a text container at the bottom 28% of the image with 5% side padding.
   - Gaussian-blurs that region and composites it back with a rounded-rectangle mask (frosted
     glass effect).
   - Binary-searches for the largest font size that fits the wrapped message, trying brand
     fonts first, then system fonts, then the Pillow default.
   - Draws each line of text centered horizontally with slight transparency.

4. **Logo overlay — `imaging.logo_overlay.overlay_logo()`**
   - Opens the logo PNG as RGBA.
   - Scales it down if wider than 18% of the image width.
   - Alpha-composites it into the top-right corner at a 4% safe margin.

5. **Brand compliance — `compliance.brand.evaluate_brand_compliance()`**
   - **Logo check** — verifies `logo_path` exists and its filename matches the policy's
     `expected_filenames`.
   - **Color palette check** — samples a 120×120 thumbnail and measures what fraction of
     pixels are within the L1 color tolerance of each required palette color.
   - **Imagery keyword check** — scans `prompt_text` for required keywords (warn if absent)
     and avoid keywords (violation if present).
   - Returns `BrandCheckResult`. If not passed and `strict_brand` → raises
     `ComplianceViolationError`. Otherwise logs a warning.

6. **File writing**
   - `output.writer.save_image(image, output_path)` → PNG at
     `{output_root}/{campaign_id}/{product_id}/{ratio_key}/final[_{locale}].png`
     (skipped on dry-run).
   - `s3_mirror.upload_output_file(output_path, output_root)` (if S3 active).

7. Output path recorded in `entry.output_files[ratio_locale_key]`.

Returns `_ProductResult` with all counters and the completed `ProductManifestEntry`.

### 3.3 Aggregation

After each `_process_product` call, results are accumulated into:
- `CampaignManifest.products` — the list of `ProductManifestEntry` objects
- `RunMetrics` — `total_products_processed`, `assets_reused`, `assets_generated`,
  `total_variants_produced`
- Local counters for brand and legal compliance totals

### 3.4 Output writing

```
manifest.finished_at = utc_now_iso()
manifest.brand_compliance_summary = { variants_checked, variants_passed, variants_failed }
manifest.legal_compliance_summary = { checks_executed, checks_flagged, checks_blocked }
metrics.execution_time_seconds = timer.elapsed()

write_json(manifest.to_dict()) → {output_root}/{campaign_id}/manifest.json
write_json(metrics.to_dict())  → {output_root}/{campaign_id}/metrics.json

s3_mirror.upload_output_file(manifest_path)
s3_mirror.upload_output_file(metrics_path)
```

`output.writer.write_json()` creates parent directories if needed and writes indented JSON.
`output.manifest.CampaignManifest.to_dict()` uses `dataclasses.asdict` for full serialisation.

---

## 4. Full Call Tree

```
main()  [cli.py]
├── _load_default_env_files()
├── parse_args()
├── _resolve_generated_image_selection()
│
├── [--validate-legal-only]
│   run_legal_validation_only(config)  [pipeline.py]
│     ├── load_and_validate_brief()    [brief_loader.py]
│     │     └── CampaignBrief.model_validate()  [models/brief.py]
│     ├── load_legal_policy()          [compliance/legal_policy.py]
│     ├── build_localizer()            [localization/translator.py]
│     ├── resolve_output_locales()     [localization/translator.py]
│     └── for each product:
│           build_generation_prompt()  [prompts/builder.py]
│           evaluate_legal_text(prompt, "en")   [compliance/legal.py]
│           for each locale:
│             localizer.translate()
│             evaluate_legal_text(message, locale)
│
└── [default]
    run_pipeline(config)  [pipeline.py]
      ├── load_and_validate_brief()    [brief_loader.py]
      ├── create_provider()            [providers/factory.py]
      │     → MockImageProvider        [providers/mock.py]
      │     → GeminiDeveloperProvider  [providers/gemini_developer.py]
      │     → GeminiVertexProvider     [providers/gemini_vertex.py]
      ├── build_localizer()            [localization/translator.py]
      ├── S3Mirror.from_env()          [storage/s3_mirror.py]
      ├── GeneratedImageStore()        [storage/generated_store.py]
      ├── resolve_product_assets()     [assets/resolver.py]
      ├── _resolve_brand_policy()      [compliance/policy.py]
      ├── _resolve_legal_policy()      [compliance/legal_policy.py]
      ├── resolve_output_locales()     [localization/translator.py]
      │
      └── for each product:
            _process_product()  [pipeline.py]
              ├── build_generation_prompt()        [prompts/builder.py]
              ├── _load_reused_or_generate_base()
              │     ├── reused:  _compose_reused_variant()
              │     ├── last:    store.load_last_for_product()  [storage/generated_store.py]
              │     │              → s3_mirror.list/download    [storage/s3_mirror.py]
              │     ├── id:      store.load_by_id()             [storage/generated_store.py]
              │     │              → s3_mirror.find/download    [storage/s3_mirror.py]
              │     └── new:     provider.generate_base_hero()  [providers/*]
              │                  store.save_new()               [storage/generated_store.py]
              │                    → s3_mirror.upload_generated_image
              ├── evaluate_legal_text(prompt, "en")  [compliance/legal.py]
              └── for each ratio {1x1, 9x16, 16x9}:
                    create_variant()                 [imaging/variants.py]
                    for each locale:
                      localizer.translate()
                      evaluate_legal_text(message)   [compliance/legal.py]
                      overlay_campaign_message()     [imaging/text_overlay.py]
                      overlay_logo()                 [imaging/logo_overlay.py]
                      evaluate_brand_compliance()    [compliance/brand.py]
                      save_image()                   [output/writer.py]
                      s3_mirror.upload_output_file() [storage/s3_mirror.py]
      │
      ├── write_json(manifest)  [output/writer.py]  →  output/{id}/manifest.json
      ├── write_json(metrics)   [output/writer.py]  →  output/{id}/metrics.json
      └── s3_mirror.upload_output_file(manifest, metrics)
```

---

## 5. Module Reference Summary

| Module | Purpose |
|---|---|
| `cli.py` | CLI entry point, env loading, arg parsing, dispatch |
| `pipeline.py` | Core orchestration; `RunConfig`, `run_pipeline`, `run_legal_validation_only` |
| `brief_loader.py` | YAML/JSON → validated `CampaignBrief` |
| `models/brief.py` | Pydantic data models: `CampaignBrief`, `ProductBrief`, `VisualStyle` |
| `models/schema_export.py` | Exports `CampaignBrief` JSON Schema to file |
| `assets/resolver.py` | Maps product IDs to filesystem asset paths |
| `localization/translator.py` | Locale list resolution, `MessageLocalizer` implementations |
| `providers/base.py` | `ImageProvider` ABC |
| `providers/factory.py` | Selects and constructs the correct provider |
| `providers/mock.py` | Deterministic gradient image generator (no API) |
| `providers/gemini_developer.py` | Gemini image generation via API key |
| `providers/gemini_vertex.py` | Gemini image generation via Vertex AI |
| `storage/generated_store.py` | Local PNG cache with timestamp-based IDs |
| `storage/s3_mirror.py` | Best-effort S3 sync for generated and output files |
| `compliance/policy.py` | `BrandPolicy` Pydantic model + YAML loader |
| `compliance/legal_policy.py` | `LegalPolicy` Pydantic model + YAML loader |
| `compliance/brand.py` | Logo, palette, and keyword brand checks |
| `compliance/legal.py` | Keyword and regex legal text checks |
| `imaging/variants.py` | Aspect ratio cropping (`create_variant`) |
| `imaging/text_overlay.py` | Frosted-glass text box renderer |
| `imaging/logo_overlay.py` | Logo placement top-right with safe margin |
| `prompts/builder.py` | Assembles the AI image generation prompt |
| `output/manifest.py` | `CampaignManifest` and `ProductManifestEntry` dataclasses |
| `output/metrics.py` | `RunMetrics` and `Timer` |
| `output/writer.py` | `save_image` and `write_json` filesystem writers |
| `exceptions.py` | `ComplianceViolationError`, `ProviderGenerationError`, `ConfigurationError` |
