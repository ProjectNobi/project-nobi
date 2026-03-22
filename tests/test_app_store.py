"""
Tests for App Store packaging — app.json, eas.json, store metadata,
privacy/terms pages, and build script.
"""

import json
import os
import subprocess

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOBILE_DIR = os.path.join(PROJECT_ROOT, "mobile")
DOCS_DIR = os.path.join(PROJECT_ROOT, "docs", "landing")


# ── Helpers ──────────────────────────────────────────────────────────

def load_json(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


# ── app.json ─────────────────────────────────────────────────────────

class TestAppJson:
    """Validate mobile/app.json has all required fields."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.path = os.path.join(MOBILE_DIR, "app.json")
        assert os.path.exists(self.path), "app.json not found"
        self.data = load_json(self.path)
        self.expo = self.data.get("expo", {})

    def test_app_name(self):
        assert self.expo.get("name") == "Nori - AI Companion"

    def test_version(self):
        version = self.expo.get("version", "")
        parts = version.split(".")
        assert len(parts) == 3, f"Version should be semver, got {version}"
        assert all(p.isdigit() for p in parts)

    def test_ios_bundle_identifier(self):
        ios = self.expo.get("ios", {})
        assert ios.get("bundleIdentifier") == "ai.projectnobi.nori"

    def test_android_package(self):
        android = self.expo.get("android", {})
        assert android.get("package") == "ai.projectnobi.nori"

    def test_icon_configured(self):
        assert self.expo.get("icon"), "icon must be set"

    def test_splash_configured(self):
        splash = self.expo.get("splash", {})
        assert splash.get("image") or splash.get("backgroundColor"), \
            "splash must have image or backgroundColor"

    def test_scheme_configured(self):
        assert self.expo.get("scheme"), "URL scheme must be set"

    def test_plugins_include_notifications(self):
        plugins = self.expo.get("plugins", [])
        plugin_names = []
        for p in plugins:
            if isinstance(p, str):
                plugin_names.append(p)
            elif isinstance(p, list) and len(p) > 0:
                plugin_names.append(p[0])
        assert "expo-notifications" in plugin_names, \
            "expo-notifications plugin must be configured"

    def test_deep_linking_ios(self):
        ios = self.expo.get("ios", {})
        domains = ios.get("associatedDomains", [])
        has_applinks = any("applinks:" in d for d in domains)
        assert has_applinks, "iOS must have associatedDomains for deep linking"

    def test_deep_linking_android(self):
        android = self.expo.get("android", {})
        filters = android.get("intentFilters", [])
        assert len(filters) > 0, "Android must have intentFilters for deep linking"
        hosts = []
        for f in filters:
            for d in f.get("data", []):
                hosts.append(d.get("host", ""))
        assert any("projectnobi.ai" in h for h in hosts), \
            "Android deep links must point to projectnobi.ai"


# ── eas.json ─────────────────────────────────────────────────────────

class TestEasJson:
    """Validate mobile/eas.json build configuration."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.path = os.path.join(MOBILE_DIR, "eas.json")
        assert os.path.exists(self.path), "eas.json not found"
        self.data = load_json(self.path)

    def test_cli_version(self):
        assert "cli" in self.data
        assert self.data["cli"].get("version"), "CLI version constraint required"

    def test_build_profiles_exist(self):
        build = self.data.get("build", {})
        for profile in ("development", "preview", "production"):
            assert profile in build, f"Missing build profile: {profile}"

    def test_production_ios_release(self):
        prod = self.data.get("build", {}).get("production", {})
        ios = prod.get("ios", {})
        assert ios.get("buildConfiguration") == "Release"

    def test_production_android_bundle(self):
        prod = self.data.get("build", {}).get("production", {})
        android = prod.get("android", {})
        assert android.get("buildType") == "app-bundle"

    def test_submit_section_exists(self):
        assert "submit" in self.data, "Submit configuration required"


# ── Assets ───────────────────────────────────────────────────────────

class TestAssets:
    """Check that placeholder asset files exist."""

    @pytest.mark.parametrize("filename", [
        "icon.png",
        "splash.png",
        "adaptive-icon.png",
        "notification-icon.png",
        "favicon.png",
    ])
    def test_asset_exists(self, filename):
        path = os.path.join(MOBILE_DIR, "assets", filename)
        assert os.path.exists(path), f"Missing asset: {filename}"
        assert os.path.getsize(path) > 0, f"Asset is empty: {filename}"


# ── Store Descriptions ───────────────────────────────────────────────

class TestStoreMetadata:
    """Validate store description files exist and have proper length."""

    def test_ios_description_exists(self):
        path = os.path.join(MOBILE_DIR, "store", "ios", "description.txt")
        assert os.path.exists(path)
        with open(path) as f:
            content = f.read()
        assert len(content) >= 100, "iOS description too short"
        assert len(content) <= 4000, "iOS description exceeds 4000 char limit"

    def test_ios_keywords_exists(self):
        path = os.path.join(MOBILE_DIR, "store", "ios", "keywords.txt")
        assert os.path.exists(path)
        with open(path) as f:
            content = f.read().strip()
        assert len(content) <= 100, "iOS keywords must be ≤100 chars"
        assert "," in content, "Keywords should be comma-separated"

    def test_ios_privacy_url(self):
        path = os.path.join(MOBILE_DIR, "store", "ios", "privacy_policy_url.txt")
        assert os.path.exists(path)
        with open(path) as f:
            url = f.read().strip()
        assert url.startswith("https://"), "Privacy URL must be HTTPS"

    def test_android_description_exists(self):
        path = os.path.join(MOBILE_DIR, "store", "android", "description.txt")
        assert os.path.exists(path)
        with open(path) as f:
            content = f.read()
        assert len(content) >= 100, "Android description too short"
        assert len(content) <= 4000, "Android description exceeds 4000 char limit"

    def test_android_short_description(self):
        path = os.path.join(MOBILE_DIR, "store", "android", "short_description.txt")
        assert os.path.exists(path)
        with open(path) as f:
            content = f.read().strip()
        assert len(content) <= 80, "Android short description must be ≤80 chars"
        assert len(content) >= 10, "Android short description too short"

    def test_screenshots_needed_doc(self):
        path = os.path.join(MOBILE_DIR, "store", "screenshots_needed.md")
        assert os.path.exists(path)
        with open(path) as f:
            content = f.read()
        assert "iOS" in content or "ios" in content
        assert "Android" in content or "android" in content


# ── Privacy & Terms ──────────────────────────────────────────────────

class TestLegalPages:
    """Validate privacy policy and terms of service exist."""

    def test_privacy_policy_exists(self):
        path = os.path.join(DOCS_DIR, "privacy.html")
        assert os.path.exists(path), "privacy.html not found"
        with open(path) as f:
            content = f.read()
        assert "Privacy Policy" in content
        assert "encrypt" in content.lower()
        assert "data" in content.lower()

    def test_terms_of_service_exists(self):
        path = os.path.join(DOCS_DIR, "terms.html")
        assert os.path.exists(path), "terms.html not found"
        with open(path) as f:
            content = f.read()
        assert "Terms of Service" in content or "Terms" in content
        assert "account" in content.lower()

    def test_privacy_covers_key_topics(self):
        path = os.path.join(DOCS_DIR, "privacy.html")
        with open(path) as f:
            content = f.read().lower()
        for topic in ["collect", "encrypt", "delete", "rights", "bittensor"]:
            assert topic in content, f"Privacy policy should cover: {topic}"

    def test_terms_covers_key_topics(self):
        path = os.path.join(DOCS_DIR, "terms.html")
        with open(path) as f:
            content = f.read().lower()
        for topic in ["liability", "termination", "ai"]:
            assert topic in content, f"Terms should cover: {topic}"


# ── Build Script ─────────────────────────────────────────────────────

class TestBuildScript:
    """Validate the build script."""

    def test_build_script_exists(self):
        path = os.path.join(MOBILE_DIR, "scripts", "build.sh")
        assert os.path.exists(path)

    def test_build_script_executable(self):
        path = os.path.join(MOBILE_DIR, "scripts", "build.sh")
        assert os.access(path, os.X_OK), "build.sh must be executable"

    def test_build_script_valid_bash(self):
        path = os.path.join(MOBILE_DIR, "scripts", "build.sh")
        result = subprocess.run(
            ["bash", "-n", path],
            capture_output=True, text=True
        )
        assert result.returncode == 0, \
            f"Bash syntax error: {result.stderr}"

    def test_build_script_has_usage(self):
        path = os.path.join(MOBILE_DIR, "scripts", "build.sh")
        with open(path) as f:
            content = f.read()
        assert "ios" in content.lower()
        assert "android" in content.lower()
