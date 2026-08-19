"""
Unit tests for the PII sanitizer.

Includes the baseline behavior from the brief's own example, plus the
failure case discovered during Day 2 research: phone numbers with no
surrounding whitespace are not detected, because Presidio's recognizer
relies on tokenization boundaries that don't exist in a glued-together
string. This is documented as a known limitation in the README.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend", "app", "services"))

from pii_sanitizer import sanitize_prompt


def test_baseline_matches_brief_example():
    result = sanitize_prompt("Write a reminder email to Ramesh, phone 9840112233.")
    assert "<NAME>" in result.sanitized_text
    assert "<PHONE>" in result.sanitized_text
    assert result.detections == {"NAME": 1, "PHONE": 1}


def test_phone_with_country_code_and_dashes():
    result = sanitize_prompt("Call me at +91 98401-22233 tomorrow.")
    assert "<PHONE>" in result.sanitized_text
    assert result.detections.get("PHONE") == 1


def test_lowercase_name_still_detected():
    result = sanitize_prompt("can you check if priya sent the report yet")
    assert "<NAME>" in result.sanitized_text


def test_company_name_not_flagged_as_person():
    result = sanitize_prompt("Ravi from Infosys called about the order.")
    assert "<NAME>" in result.sanitized_text
    assert "Infosys" in result.sanitized_text  # company name should survive


def test_KNOWN_LIMITATION_glued_phone_number_not_detected():
    """
    Documented failure case (Day 2 research).

    When a phone number has no surrounding whitespace/punctuation, it is
    NOT detected — the raw digits leak into storage unredacted. Adding a
    single space around the same digits (see the passing test below) is
    enough to restore detection, confirming the root cause is tokenization
    boundary loss, not the digit pattern itself.

    Mitigation for production: add a regex-based fallback pass for long
    digit runs (8+ consecutive digits) independent of spaCy tokenization.
    """
    result = sanitize_prompt("mynumberis9840112233callme")
    # This assertion documents CURRENT (broken) behavior intentionally —
    # it will fail (and should) once the mitigation above is implemented.
    assert result.detections == {}
    assert "9840112233" in result.sanitized_text  # unredacted PII leaked


def test_same_number_detected_once_whitespace_is_present():
    result = sanitize_prompt("mynumberis 9840112233 callme")
    assert "<PHONE>" in result.sanitized_text
    assert result.detections.get("PHONE") == 1