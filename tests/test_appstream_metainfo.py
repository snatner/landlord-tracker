"""AppStream metainfo guards.

The metainfo file is what makes the app visible in GNOME Software and KDE
Discover, and it is a hard requirement for both Flathub and the Snap Store
submission. Stores reject a build when its identity disagrees with itself, so
the checks here are mostly about *agreement* between four separate places:

  context.APP_ID  ==  metainfo <id>  ==  <launchable> desktop-id basename
                  ==  the .desktop basename written by dist/install.sh
                  ==  StartupWMClass

and about the release entry tracking the app's real version, so the store never
publishes stale release notes.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlparse

import pytest

from landlord_tracker.context import APP_ID, APP_VERSION

ROOT = Path(__file__).resolve().parents[1]
METAINFO = (ROOT / "src" / "landlord_tracker" / "resources"
            / f"{APP_ID}.metainfo.xml")
INSTALLER = ROOT / "dist" / "install.sh"


@pytest.fixture(scope="module")
def component() -> ET.Element:
    assert METAINFO.exists(), (
        f"AppStream metadata is required by Flathub and the Snap Store; "
        f"missing {METAINFO.relative_to(ROOT)}"
    )
    return ET.parse(METAINFO).getroot()


def _text(element: ET.Element, tag: str, lang: str | None = None) -> str | None:
    for child in element.findall(tag):
        if lang is None:
            if "{http://www.w3.org/XML/1998/namespace}lang" not in child.attrib:
                return child.text
        elif child.attrib.get("{http://www.w3.org/XML/1998/namespace}lang") == lang:
            return child.text
    return None


# --- identity must agree everywhere ---------------------------------------


def test_metainfo_is_well_formed_and_of_the_right_component_type(component):
    assert component.tag == "component"
    assert component.get("type") == "desktop-application"


def test_component_id_matches_the_app_id(component):
    assert _text(component, "id") == APP_ID


def test_launchable_matches_the_installed_desktop_file(component):
    launchables = component.findall("launchable")
    assert launchables, "a desktop app must declare a <launchable>"
    desktop_ids = [n.text for n in launchables if n.get("type") == "desktop-id"]
    assert desktop_ids == [f"{APP_ID}.desktop"]


def test_installer_writes_the_same_desktop_basename_and_wm_class(component):
    installer = INSTALLER.read_text(encoding="utf-8")
    assert f'"$APPS_DIR/{APP_ID}.desktop"' in installer, (
        "dist/install.sh must install the .desktop under the app id"
    )
    match = re.search(r"^StartupWMClass=(.+)$", installer, re.MULTILINE)
    assert match and match.group(1).strip() == APP_ID


# --- required fields -------------------------------------------------------


def test_required_fields_are_present(component):
    assert _text(component, "name")
    assert _text(component, "summary")
    assert _text(component, "metadata_license")
    assert _text(component, "project_license") == "GPL-3.0-or-later"

    developer = component.find("developer")
    assert developer is not None, "Flathub requires a <developer> element"
    assert developer.get("id") == APP_ID.rsplit(".", 1)[0]
    assert (developer.findtext("name") or "").strip()

    rating = component.find("content_rating")
    assert rating is not None and rating.get("type", "").startswith("oars-")

    categories = {c.text for c in component.findall("./categories/category")}
    assert {"Office", "Finance"} <= categories


def test_urls_are_https(component):
    urls = component.findall("url")
    assert urls, "at least a homepage URL is required"
    for url in urls:
        assert url.text and url.text.startswith("https://"), url.text


def test_portuguese_translation_is_present(component):
    """The app ships pt-PT, so the store listing must too."""
    assert _text(component, "summary", lang="pt")
    descriptions = [d for d in component.findall("description")
                    if d.attrib.get("{http://www.w3.org/XML/1998/namespace}lang") == "pt"]
    assert descriptions, "the pt description is missing from the store listing"


# --- screenshots -----------------------------------------------------------


def test_screenshots_exist_and_are_reachable_urls(component):
    shots = component.findall("./screenshots/screenshot")
    assert len(shots) >= 3, "Flathub expects several real screenshots"
    for shot in shots:
        images = shot.findall("image")
        assert images, "every screenshot needs an <image>"
        for image in images:
            url = image.text or ""
            parsed = urlparse(url)
            assert parsed.scheme == "https", url
            assert parsed.netloc, url
            # Hosted in the app's own repo so they cannot silently go stale.
            assert "githubusercontent.com" in parsed.netloc, url
            assert url.endswith(".png"), url
        assert shot.findtext("caption"), "screenshots need captions"


def test_screenshots_referenced_actually_ship_in_the_repo(component):
    """Catch a caption/URL typo pointing at a file that does not exist."""
    missing = []
    for image in component.findall("./screenshots/screenshot/image"):
        name = urlparse(image.text or "").path.rsplit("/", 1)[-1]
        if not (ROOT / "artifacts" / "screenshots" / name).exists():
            missing.append(name)
    assert not missing, f"metainfo references screenshots that do not exist: {missing}"


# --- release tracking ------------------------------------------------------


def test_newest_release_entry_matches_the_app_version(component):
    """Forces the version bump: you cannot ship a store listing that lies."""
    releases = component.findall("./releases/release")
    assert releases, "Flathub requires at least one <release>"
    versions = [r.get("version") for r in releases]
    assert APP_VERSION in versions, (
        f"APP_VERSION is {APP_VERSION} but the metainfo advertises {versions}. "
        f"Bump one of them — a store listing must not misreport its version."
    )
    for release in releases:
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", release.get("date") or ""), \
            f"release {release.get('version')} needs an ISO date"
