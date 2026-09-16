"""Local-only checks. Run from project root with its .venv and browser cache."""
from pathlib import Path
import hashlib
import json
import xml.etree.ElementTree as ET
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
NS = "{http://www.w3.org/2000/svg}"
original = ROOT / "app/static/img/libre-libros-mark.svg"
copy = HERE / "mark-current-copy.svg"
assert original.read_bytes() == copy.read_bytes(), "Reference copy differs"
svg_results = []
for file in (copy, HERE / "mark-blue.svg", HERE / "mark-teal.svg"):
    svg = ET.parse(file).getroot()
    assert svg.tag == NS + "svg"
    assert svg.find(NS + "title") is not None
    assert svg.find(NS + "desc") is not None
    for element in svg.iter():
        assert element.tag not in {NS + "script", NS + "image", NS + "foreignObject"}
        assert not any(key.endswith("href") for key in element.attrib)
    if file != copy:
        assert svg.attrib["viewBox"] == "0 0 32 32"
        assert svg.find(NS + "text") is None
    svg_results.append({"file": file.name, "xml": "pass", "sha256": hashlib.sha256(file.read_bytes()).hexdigest()})

results = {"svg": svg_results, "reference_byte_identical": True, "browser": []}
(HERE / "screenshots").mkdir(exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    results["chromium_version"] = browser.version
    for label, width, height in [("desktop", 1440, 1000), ("mobile", 390, 844)]:
        page = browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=1)
        errors, external = [], []
        page.on("pageerror", lambda error: errors.append(str(error)))
        def intercept(route):
            if route.request.url.startswith(("file://", "data:")):
                route.continue_()
            else:
                external.append(route.request.url)
                route.abort()
        page.route("**/*", intercept)
        page.goto((HERE / "index.html").as_uri(), wait_until="load")
        page.wait_for_function("Array.from(document.images).every(i => i.complete && i.naturalWidth > 0)")
        checks = page.evaluate("""() => ({
            images: document.images.length,
            rows: document.querySelectorAll('.sample-row').length,
            samples: document.querySelectorAll('.slot img').length,
            exactSizes: Array.from(document.querySelectorAll('.slot img')).every(i => {
                const r = i.getBoundingClientRect(); return r.width === i.width && r.height === i.height;
            }),
            decorativeAlts: Array.from(document.images).every(i => i.getAttribute('alt') === ''),
            visibleNames: document.querySelectorAll('.wordmark').length,
            overflow: document.documentElement.scrollWidth > innerWidth
        })""")
        assert checks["images"] == 78 and checks["samples"] == 75 and checks["rows"] == 15
        assert checks["exactSizes"] and checks["decorativeAlts"] and checks["visibleNames"] == 3
        assert not checks["overflow"] and not errors and not external
        page.screenshot(path=str(HERE / "screenshots" / f"{label}.png"), full_page=True)
        if label == "desktop":
            for candidate in ("current", "blue", "teal"):
                page.locator(f"#{candidate}").screenshot(path=str(HERE / "screenshots" / f"{candidate}.png"))
        results["browser"].append({"viewport": [width, height], "device_scale_factor": 1, **checks, "page_errors": errors, "external_requests": external})
        page.close()
    browser.close()
(HERE / "verification.json").write_text(json.dumps(results, indent=2) + "\n")
print(json.dumps(results, indent=2))
