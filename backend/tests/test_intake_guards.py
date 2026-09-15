"""app/services/intake_guards.py — the "too little / too much / doesn't make
sense" edge cases for content request intake."""

import pytest

from app.services.intake_guards import (
    MAX_IDEA_LENGTH,
    validate_attachments,
    validate_raw_idea,
    validate_supporting_material,
    validate_target_audience,
)
from shared.errors import ValidationFailure
from shared.models import IntakeAttachmentIn


def test_two_word_idea_is_too_short():
    with pytest.raises(ValidationFailure, match="too short"):
        validate_raw_idea("remote work")


def test_three_word_idea_is_accepted():
    validate_raw_idea("remote team productivity")


def test_idea_over_max_length_is_rejected():
    with pytest.raises(ValidationFailure, match="too long"):
        validate_raw_idea("word " * (MAX_IDEA_LENGTH // 4))


def test_idea_that_is_just_a_url_is_rejected():
    with pytest.raises(ValidationFailure, match="just a URL"):
        validate_raw_idea("https://example.com/some-article")


def test_repeated_character_idea_is_rejected_as_gibberish():
    with pytest.raises(ValidationFailure, match="doesn't look like a usable"):
        validate_raw_idea("aaaaaaaaaaaaaaaaaaaa")


def test_no_vowel_idea_is_rejected_as_gibberish():
    with pytest.raises(ValidationFailure, match="doesn't look like a usable"):
        validate_raw_idea("xkcd fghjklm zxcvbnm")


def test_real_short_idea_is_not_flagged_as_gibberish():
    validate_raw_idea("why small agencies fail")


def test_empty_target_audience_is_rejected():
    with pytest.raises(ValidationFailure):
        validate_target_audience("   ")


def test_oversized_target_audience_is_rejected():
    with pytest.raises(ValidationFailure, match="too long"):
        validate_target_audience("x" * 400)


def test_oversized_supporting_material_is_rejected():
    with pytest.raises(ValidationFailure, match="too large"):
        validate_supporting_material({"notes": "x" * 6000})


def test_too_many_attachments_is_rejected():
    attachments = [IntakeAttachmentIn(type="url", url="https://example.com/a") for _ in range(11)]
    with pytest.raises(ValidationFailure, match="too many attachments"):
        validate_attachments(attachments)


def test_malformed_url_attachment_is_rejected():
    attachments = [IntakeAttachmentIn(type="url", url="not-a-url")]
    with pytest.raises(ValidationFailure, match="valid http"):
        validate_attachments(attachments)


def test_well_formed_attachments_pass():
    validate_attachments([IntakeAttachmentIn(type="url", url="https://example.com/a")])
