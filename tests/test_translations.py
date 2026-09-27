"""
Tests for translations.py.

Plain string tables and a lookup function, no Qt involved — so, like
ytdlp_core, these can be checked without opening a window. The goal isn't to
check every string's wording, it's to catch the kind of mistake that's easy
to make and easy to miss by eye: a key added to English and forgotten in
Spanish, or a quality preset renamed in ytdlp_core without updating the
label that maps it to a translation key.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

import ytdlp_core as core  # noqa: E402
import translations as i18n  # noqa: E402


# ==================================================
# LANGUAGE TABLES STAY IN SYNC
# ==================================================


def test_every_language_defines_the_same_keys():
    reference = set(i18n.TRANSLATIONS[i18n.DEFAULT_LANGUAGE])
    for language, strings in i18n.TRANSLATIONS.items():
        keys = set(strings)
        assert keys == reference, (
            f"{language} differs from {i18n.DEFAULT_LANGUAGE}: "
            f"missing {reference - keys}, extra {keys - reference}"
        )


def test_languages_dict_matches_the_translation_tables():
    assert set(i18n.LANGUAGES) == set(i18n.TRANSLATIONS)


# ==================================================
# QUALITY PRESET LABELS STAY IN SYNC WITH CORE
# ==================================================


def test_quality_label_keys_cover_every_preset_and_no_more():
    # Every label core.py can hand the GUI needs a translation key, and a
    # renamed/removed preset must not leave a stale entry behind either
    assert set(i18n.QUALITY_LABEL_KEYS) == set(core.QUALITY_LABELS)


def test_quality_label_keys_point_at_real_translation_keys():
    for label, key in i18n.QUALITY_LABEL_KEYS.items():
        for language in i18n.TRANSLATIONS:
            assert key in i18n.TRANSLATIONS[language], f"{key} (for {label!r}) missing from {language}"


# ==================================================
# tr()
# ==================================================


def test_tr_looks_up_the_requested_language():
    assert i18n.tr("en", "stop_button") == "Stop"
    assert i18n.tr("es", "stop_button") == "Detener"


def test_tr_falls_back_to_english_for_an_unknown_language():
    assert i18n.tr("xx", "stop_button") == i18n.tr("en", "stop_button")


def test_tr_formats_placeholders_in_both_languages():
    assert "3" in i18n.tr("en", "status_failed", code=3)
    assert "3" in i18n.tr("es", "status_failed", code=3)


# ==================================================
# RUNNING WITHOUT PYTEST
# ==================================================

if __name__ == "__main__":
    failures = 0
    for name, test in sorted(globals().items()):
        if name.startswith("test_") and callable(test):
            try:
                test()
                print(f"  ok   {name}")
            except AssertionError as error:
                failures += 1
                print(f"  FAIL {name}: {error}")

    print(f"\n{'all tests passed' if not failures else f'{failures} failed'}")
    sys.exit(1 if failures else 0)
