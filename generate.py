#!/usr/bin/env python3
"""
Generates the MkDocs component catalog (docs/) from the TMFCnnn component
folders in a checkout of tmforum-rand/TMForum-ODA-Ready-for-publication.
This repo holds only the site generator; the component data lives in that
other (private-org-owned) repo and is located via ODA_DATA_REPO - see
resolve_data_repo() below. Source of truth for each page is that repo's
Specification/*.yaml file plus its sibling PDF, conformance profile and CTK
assets - nothing here is hand-maintained, so re-run this after the data
repo's assets change.

Page layout (hero banner, metadata card, resource cards, Mandatory/Optional
API grouping) follows the TM Forum ODA Component Directory
(tmforum.org/oda/directory) so this catalog reads as a companion to it.
"""
import os
import re
import shutil
from pathlib import Path
from urllib.parse import quote

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
DOCS_DIR = SCRIPT_DIR / "docs"
COMPONENTS_DIR = DOCS_DIR / "components"
STATIC_DIR = SCRIPT_DIR / "static"

DATA_REPO_SLUG = "tmforum-rand/TMForum-ODA-Ready-for-publication"
SOURCE_BRANCH = "v1.0.0"
BLOB_BASE = f"https://github.com/{DATA_REPO_SLUG}/blob/{SOURCE_BRANCH}"
TREE_BASE = f"https://github.com/{DATA_REPO_SLUG}/tree/{SOURCE_BRANCH}"
DATA_REPO_URL = f"https://github.com/{DATA_REPO_SLUG}"

COMPONENT_DIR_RE = re.compile(r"^(TMFC\d+)-(.+)$")


def resolve_data_repo() -> Path:
    """Locates the checkout of the component data repo.

    In CI (see .github/workflows/docs.yml) this is a second actions/checkout
    step pointed at ODA_DATA_REPO. For local development, set the env var
    yourself or place a sibling checkout at ../TMForum-ODA-Ready-for-publication.
    """
    env = os.environ.get("ODA_DATA_REPO")
    if env:
        path = Path(env).resolve()
        if not path.exists():
            raise SystemExit(f"ODA_DATA_REPO={env} does not exist")
        return path
    candidate = SCRIPT_DIR.parent / "TMForum-ODA-Ready-for-publication"
    if candidate.exists():
        return candidate
    raise SystemExit(
        "Could not find the component data repo. Set the ODA_DATA_REPO "
        "environment variable to a checkout of "
        f"{DATA_REPO_SLUG} (branch {SOURCE_BRANCH})."
    )


DATA_REPO_ROOT = resolve_data_repo()

# The TM Forum ODA Component Directory groups components under these
# human-readable ODA Function Block names. Our YAML only stores the
# camelCase enum value, so translate the ones we've seen and fall back to a
# generic camelCase-to-title-case split for anything new.
FUNCTIONAL_BLOCK_LABELS = {
    "CoreCommerce": "Core Commerce Management",
    "PartyManagement": "Party Management",
    "Production": "Production",
    "IntelligenceManagement": "Intelligence Management",
    "EngagementManagement": "Engagement Management",
}

# Left-to-right column order on tmforum.org/oda/directory/components-map
# (Canvas Operator omitted - that's canvas operators, not components).
# Anything we have that isn't one of their categories (Intelligence
# Management doesn't exist as its own block there) is appended after.
FUNCTIONAL_BLOCK_ORDER = [
    "Engagement Management",
    "Party Management",
    "Core Commerce Management",
    "Production",
]


def ordered_block_labels(labels) -> list:
    known = [b for b in FUNCTIONAL_BLOCK_ORDER if b in labels]
    extra = sorted(b for b in labels if b not in FUNCTIONAL_BLOCK_ORDER)
    return known + extra


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


# Maps a display label back to the CSS class suffix, so "Core Commerce
# Management" (label) and "CoreCommerce" (raw YAML enum) both resolve to the
# same `.oda-block-corecommerce` colour defined in extra.css.
FUNCTIONAL_BLOCK_SLUGS = {label: slugify(raw) for raw, label in FUNCTIONAL_BLOCK_LABELS.items()}


def block_css_class(label: str) -> str:
    return "oda-block-" + FUNCTIONAL_BLOCK_SLUGS.get(label, slugify(label))


def block_label(raw: str) -> str:
    if not raw:
        return "Uncategorized"
    if raw in FUNCTIONAL_BLOCK_LABELS:
        return FUNCTIONAL_BLOCK_LABELS[raw]
    return re.sub(r"(?<!^)(?=[A-Z])", " ", raw)


def github_url(path: Path, is_dir: bool = False) -> str:
    rel = path.relative_to(DATA_REPO_ROOT).as_posix()
    base = TREE_BASE if is_dir else BLOB_BASE
    return f"{base}/{quote(rel)}"


def find_component_dirs():
    return [p for p in sorted(DATA_REPO_ROOT.iterdir()) if p.is_dir() and COMPONENT_DIR_RE.match(p.name)]


def load_spec(component_dir: Path):
    spec_dir = component_dir / "Specification"
    yaml_files = sorted(spec_dir.glob("*.yaml")) if spec_dir.exists() else []
    if not yaml_files:
        return None, None
    with open(yaml_files[0], encoding="utf-8") as f:
        document = yaml.safe_load(f)
    # componentMetadata/coreFunction/etc. live under the top-level `spec:` key
    # of the Kubernetes-style Component manifest.
    return document.get("spec", document), yaml_files[0]


def find_assets(component_dir: Path, yaml_path: Path):
    conf_dir = component_dir / "ComponentConformanceProfile"
    ctk_dir = component_dir / "CTK"
    ri_dir = ctk_dir / "ComponentRI" if ctk_dir.exists() else None
    return {
        "yaml": yaml_path,
        "pdf": next(iter(sorted(component_dir.glob("*.pdf"))), None),
        "conformance": sorted(conf_dir.glob("*")) if conf_dir.exists() else [],
        "ctk_dir": ctk_dir if ctk_dir.exists() else None,
        "ri_dir": ri_dir if ri_dir and ri_dir.exists() else None,
    }


def split_taxonomy_entry(entry: str):
    """'1.2.20|Product_Catalog_Lifecycle_Management|v24.0' -> ('Product Catalog Lifecycle Management', 'v24.0')."""
    parts = [p.strip() for p in str(entry).split("|") if p.strip()]
    if len(parts) < 2:
        return str(entry).replace("_", " "), None
    version = parts[-1]
    label = " › ".join(p.replace("_", " ") for p in parts[:-1])
    return label, version


def is_redacted(value) -> bool:
    return not value or str(value).strip().lower() == "redacted"


def format_person(person: dict) -> str:
    name = person.get("name")
    email = person.get("email")
    url = person.get("url")
    if is_redacted(name) and is_redacted(email) and is_redacted(url):
        return None
    label = name if not is_redacted(name) else "(name withheld)"
    if not is_redacted(email):
        label = f"[{label}](mailto:{email})"
    elif not is_redacted(url):
        label = f"[{label}]({url})"
    return label


def api_entry_url(api: dict):
    spec_list = api.get("specification") or []
    return spec_list[0].get("url") if spec_list else None


def api_entry_version(api: dict):
    spec_list = api.get("specification") or []
    return (spec_list[0].get("version") if spec_list else None) or api.get("version", "—")


def render_api_group(apis: list) -> str:
    """Renders one function's exposed/dependent APIs split into Mandatory / Optional,
    matching the grouping used on the TM Forum component directory page."""
    mandatory = [a for a in apis if a.get("required")]
    optional = [a for a in apis if not a.get("required")]
    parts = []
    for label, group in (("Mandatory", mandatory), ("Optional", optional)):
        parts.append(f'<p class="oda-api-group-label">{label} ({len(group)})</p>')
        if not group:
            parts.append('<ul class="oda-api-list"><li class="oda-api-empty">None declared.</li></ul>')
            continue
        items = []
        for api in group:
            api_id = api.get("id", "—")
            name = api.get("name", "—")
            version = api_entry_version(api)
            url = api_entry_url(api)
            id_html = f'<a href="{url}">{api_id}</a>' if url and url.startswith("http") else api_id
            items.append(
                f'<li><span class="oda-api-id">{id_html}</span>'
                f'<span class="oda-api-name">{name}</span>'
                f'<span class="oda-api-name">{version}</span></li>'
            )
        parts.append('<ul class="oda-api-list">' + "".join(items) + "</ul>")
    return "\n".join(parts)


def event_table(events: list) -> str:
    if not events:
        return "_None declared._\n"
    lines = ["| Event | API | Resources |", "|---|---|---|"]
    for event in events:
        name = event.get("name", "—")
        api_id = event.get("id", "—")
        resources = ", ".join(event.get("resources") or []) or "—"
        lines.append(f"| {name} | {api_id} | {resources} |")
    return "\n".join(lines) + "\n"


def taxonomy_list(entries: list) -> str:
    if not entries:
        return "_None declared._\n"
    lines = []
    for entry in entries:
        label, version = split_taxonomy_entry(entry)
        lines.append(f"- {label}" + (f" ({version})" if version else ""))
    return "\n".join(lines) + "\n"


def resource_card(css_class: str, icon: str, title: str, action: str, url: str) -> str:
    return (
        f'<div class="oda-resource-card {css_class}">'
        f'<div class="oda-resource-icon">{icon}</div>'
        f'<div class="oda-resource-body">'
        f'<span class="oda-resource-title">{title}</span>'
        f'<a class="md-button md-button--primary" href="{url}">{action}</a>'
        f"</div></div>"
    )


def render_resource_cards(assets: dict) -> str:
    cards = [resource_card("oda-resource-yaml", "{ }", "YAML specification", "View", github_url(assets["yaml"]))]
    if assets["pdf"]:
        cards.append(resource_card("oda-resource-pdf", "\U0001F4C4", "Component specification (PDF)", "Download", github_url(assets["pdf"])))
    for f in assets["conformance"]:
        kind = "PDF" if f.suffix.lower() == ".pdf" else "DOCX" if f.suffix.lower() == ".docx" else f.suffix.lstrip(".").upper()
        cards.append(resource_card("oda-resource-conformance", "✓", f"Conformance profile ({kind})", "View", github_url(f)))
    if assets["ctk_dir"]:
        cards.append(resource_card("oda-resource-ctk", "☑", "Conformance Testing Kit (CTK)", "Browse", github_url(assets["ctk_dir"], is_dir=True)))
    if assets["ri_dir"]:
        cards.append(resource_card("oda-resource-ri", "</>", "Reference implementation", "Browse", github_url(assets["ri_dir"], is_dir=True)))
    return f'<div class="oda-resource-grid">{"".join(cards)}</div>'


def render_component_page(component_dir: Path, spec: dict, assets: dict) -> str:
    meta = spec.get("componentMetadata", {}) or {}
    component_id = meta.get("id", "—")
    name = meta.get("name", component_dir.name)
    display_name = re.sub(r"(?<!^)(?=[A-Z])", " ", name)
    version = meta.get("version", "—")
    status = meta.get("status", "—")
    functional_block_raw = meta.get("functionalBlock", "")
    functional_block = block_label(functional_block_raw)
    description = (meta.get("description") or "").strip()
    publication_date = meta.get("publicationDate", "—")

    owners = [format_person(o) for o in (meta.get("owners") or [])]
    owners = [o for o in owners if o]
    maintainers = [format_person(m) for m in (meta.get("maintainers") or [])]
    maintainers = [m for m in maintainers if m]

    core = spec.get("coreFunction") or {}
    mgmt = spec.get("managementFunction") or {}
    sec = spec.get("securityFunction") or {}
    events = spec.get("eventNotification") or {}

    hero = f"""<div class="oda-hero" markdown="1">
<p class="oda-breadcrumb">Home &rsaquo; Components &rsaquo; {display_name}</p>

# {component_id} – {display_name}

<p class="oda-hero-desc">{description or "No description provided."}</p>
</div>

<div class="oda-meta-card" markdown="1">

| | |
|---|---|
| **ODA Function Block** | {functional_block} |
| **Component ID** | {component_id} |
| **Component version** | {version} |
| **Status** | {status} |
| **Published date** | {publication_date} |
| **Owners** | {', '.join(owners) if owners else '—'} |
| **Maintainers** | {', '.join(maintainers) if maintainers else '—'} |

</div>
"""

    parts = [
        hero,
        "## Component resources",
        "",
        render_resource_cards(assets),
        "",
        "## Exposed APIs",
        "",
        render_api_group(core.get("exposedAPIs") or []),
        "",
        "## Dependent APIs",
        "",
        render_api_group(core.get("dependentAPIs") or []),
        "",
        "??? note \"Management & security function APIs\"",
        "",
        "    **Management function – exposed**",
        "",
        "    " + render_api_group(mgmt.get("exposedAPIs") or []).replace("\n", "\n    "),
        "",
        "    **Management function – dependent**",
        "",
        "    " + render_api_group(mgmt.get("dependentAPIs") or []).replace("\n", "\n    "),
        "",
        "    **Security function – exposed**",
        "",
        "    " + render_api_group(sec.get("exposedAPIs") or []).replace("\n", "\n    "),
        "",
        "    **Security function – dependent**",
        "",
        "    " + render_api_group(sec.get("dependentAPIs") or []).replace("\n", "\n    "),
        "",
        "## Events",
        "",
        "### Published events",
        "",
        event_table(events.get("publishedEvents") or []),
        "### Subscribed events",
        "",
        event_table(events.get("subscribedEvents") or []),
        "## eTOM process alignment",
        "",
        taxonomy_list(meta.get("eTOMs") or []),
        "## Functional Framework alignment",
        "",
        taxonomy_list(meta.get("functionalFrameworkFunctions") or []),
        "## SID alignment",
        "",
        taxonomy_list(meta.get("SIDs") or []),
    ]
    return "\n".join(parts) + "\n"


def panel_flex_basis(count: int) -> str:
    """Wider panels for blocks with more components, narrower for fewer -
    matching how tmforum.org/oda/directory/components-map gives Party
    Management (many items) far more width than Canvas Operator (few)
    instead of forcing every block to the same column width."""
    cols = 1 if count <= 4 else 2 if count <= 9 else 3
    card = 220
    gap = 16
    padding = 48  # 24px left + right panel padding
    width = cols * card + (cols - 1) * gap + padding
    return f"{width}px"


def render_index(catalog: list) -> str:
    blocks = {}
    for entry in catalog:
        blocks.setdefault(entry["functional_block"], []).append(entry)

    hero = f"""<div class="oda-hero" markdown="1">
<p class="oda-breadcrumb">Home</p>

# TM Forum ODA Component Catalog

<p class="oda-hero-desc">Published <a href="https://www.tmforum.org/oda/">ODA</a> component
specifications, conformance profiles and Component Test Kits (CTKs) from
<a href="{DATA_REPO_URL}">{DATA_REPO_SLUG}</a>, generated from the <code>{SOURCE_BRANCH}</code> branch.
Laid out to match the <a href="https://www.tmforum.org/oda/directory">TM Forum ODA Component Directory</a>,
grouped by each component's own declared ODA Function Block.</p>
</div>
"""

    certifiable_count = sum(1 for e in catalog if e["certifiable"])
    toolbar = f"""<div class="oda-toolbar" markdown="1">

**{len(catalog)} components** across **{len(blocks)} functional blocks** &middot; **{certifiable_count}** ship a conformance profile.

<label class="oda-switch">
<input type="checkbox" id="oda-certifiable-toggle">
<span class="oda-switch-track"><span class="oda-switch-thumb"></span></span>
Certifiable components only
</label>
</div>
"""

    lines = [hero, toolbar, '<div class="oda-blocks-row" markdown="1">']
    for block in ordered_block_labels(blocks.keys()):
        css_class = block_css_class(block)
        basis = panel_flex_basis(len(blocks[block]))
        lines.append("")
        lines.append(f'<div class="oda-block-column {css_class}" style="flex-basis:{basis}" markdown="1">')
        lines.append(f'## <span class="oda-block-dot {css_class}" style="background:currentColor"></span> {block}')
        lines.append("")
        lines.append('<div class="oda-block-card-list" markdown="1">')
        for entry in sorted(blocks[block], key=lambda e: e["id"]):
            certifiable_badge = '<span class="oda-certifiable-badge">Certifiable</span>' if entry["certifiable"] else ""
            # Blank lines before/after are required: without them python-markdown
            # merges consecutive inline `<a>` tags into a single <p>, which
            # leaves the list with just one child instead of one per card.
            lines.append("")
            lines.append(
                f'<a class="oda-catalog-card {css_class}" href="components/{entry["slug"]}/" '
                f'data-certifiable="{"true" if entry["certifiable"] else "false"}">'
                f'<span class="oda-catalog-card-title">{entry["display_name"]}</span>'
                f'<span class="oda-catalog-card-meta">'
                f'<span class="oda-chip {css_class}">{entry["id"]}</span>'
                f'<span>v{entry["version"]}</span>'
                f'<span>{entry["status"]}</span>'
                f"{certifiable_badge}"
                f"</span></a>"
            )
            lines.append("")
        lines.append("</div>")
        lines.append("</div>")
    lines.append("")
    lines.append("</div>")
    return "\n".join(lines) + "\n"


def copy_static():
    if not STATIC_DIR.exists():
        return
    shutil.copytree(STATIC_DIR, DOCS_DIR, dirs_exist_ok=True)


def main():
    if DOCS_DIR.exists():
        shutil.rmtree(DOCS_DIR)
    COMPONENTS_DIR.mkdir(parents=True)
    copy_static()

    (COMPONENTS_DIR / ".pages").write_text("title: Components\n", encoding="utf-8")

    catalog = []
    for component_dir in find_component_dirs():
        spec, yaml_path = load_spec(component_dir)
        if spec is None:
            print(f"skipping {component_dir.name}: no Specification/*.yaml found")
            continue
        assets = find_assets(component_dir, yaml_path)
        meta = spec.get("componentMetadata", {}) or {}
        name = meta.get("name", component_dir.name)

        page = render_component_page(component_dir, spec, assets)
        slug = component_dir.name
        (COMPONENTS_DIR / f"{slug}.md").write_text(page, encoding="utf-8")

        catalog.append(
            {
                "id": meta.get("id", component_dir.name.split("-")[0]),
                "name": name,
                "display_name": re.sub(r"(?<!^)(?=[A-Z])", " ", name),
                "version": meta.get("version", "—"),
                "status": meta.get("status", "—"),
                "functional_block": block_label(meta.get("functionalBlock", "")),
                "slug": slug,
                "certifiable": bool(assets["conformance"]),
            }
        )

    (DOCS_DIR / "index.md").write_text(render_index(catalog), encoding="utf-8")
    print(f"generated {len(catalog)} component pages into {COMPONENTS_DIR}")


if __name__ == "__main__":
    main()
