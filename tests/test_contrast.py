"""Offline WCAG text-contrast regression checks for verified GC UI lagoon tokens.

Calculates relative luminance from actual Search CSS values; this is a
targeted token check, not a full visual or screen-reader accessibility audit.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

CSS = (Path(__file__).resolve().parents[1] / "web/styles.css").read_text(encoding="utf-8")


def tokens(selector: str) -> dict[str, str]:
    match = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", CSS, re.S)
    if match is None:
        raise AssertionError(f"Required token scope missing: {selector}")
    return {
        name: value.strip()
        for name, value in re.findall(r"(--gc-[\w-]+)\s*:\s*([^;]+);", match.group(1))
    }


def luminance(color: str) -> float:
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
        raise AssertionError(f"Expected a fixed six-digit CSS color token: {color}")
    channels = [int(color[i:i+2], 16) / 255 for i in (1, 3, 5)]
    linear = [value / 12.92 if value <= .04045 else ((value + .055) / 1.055) ** 2.4
              for value in channels]
    return sum(weight * value for weight, value in zip((.2126, .7152, .0722), linear))


def contrast(foreground: str, background: str) -> float:
    left, right = luminance(foreground), luminance(background)
    return (max(left, right) + .05) / (min(left, right) + .05)


class AccessibleColorTests(unittest.TestCase):
    def test_light_canvas_small_brand_text_uses_contrast_token(self):
        base = tokens(':root[data-accent="lagoon"]')
        light = tokens(':root[data-mode="light"]')
        self.assertIn(".eyebrow { color: var(--gc-on-brand-container)", CSS)
        self.assertIn(".brand strong { color: var(--gc-on-brand-container)", CSS)
        self.assertGreaterEqual(
            contrast(base["--gc-on-brand-container"], light["--gc-canvas"]), 4.5
        )

    def test_dark_canvas_small_brand_text_has_aa_contrast(self):
        dark = tokens(':root[data-mode="dark"]')
        self.assertGreaterEqual(
            contrast(dark["--gc-on-brand-container"], dark["--gc-canvas"]), 4.5
        )

    def test_source_labels_have_aa_contrast_in_both_themes(self):
        base = tokens(':root[data-accent="lagoon"]')
        light = tokens(':root[data-mode="light"]')
        dark = tokens(':root[data-mode="dark"]')
        self.assertIn(".source { color: var(--gc-brand)", CSS)
        for foreground, surface in (
            (base["--gc-brand"], light["--gc-surface"]),
            (dark["--gc-brand"], dark["--gc-surface"]),
        ):
            with self.subTest(foreground=foreground):
                self.assertGreaterEqual(contrast(foreground, surface), 4.5)

    def test_token_values_match_gc_ui_authority(self):
        # Checked against GoreeCloud/gc-ui styles/tokens.css, canonical lagoon.
        base = tokens(':root[data-accent="lagoon"]')
        dark = tokens(':root[data-mode="dark"]')
        self.assertEqual(base["--gc-on-brand-container"], "#07565d")
        self.assertEqual(dark["--gc-on-brand-container"], "#c8fcff")


if __name__ == "__main__":
    unittest.main()
