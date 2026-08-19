"""
PII sanitization pipeline.

Given a raw prompt, detect PII entities (name, phone, email, etc.) using
Presidio's analyzer, then redact them into placeholder tags before the
prompt is ever persisted. Sensitive raw text never touches the database.

Returns both the sanitized text AND a count of detections per entity type,
so we can compute governance insights like "which AI assets receive the
most PII" without ever storing the PII itself.
"""

from dataclasses import dataclass
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

# Entity types we actively look for. Presidio supports many more out of
# the box (CREDIT_CARD, IBAN_CODE, US_SSN, etc.) — we scope to what's
# relevant for a support-agent context to keep false positives manageable.
SUPPORTED_ENTITIES = ["PERSON", "PHONE_NUMBER", "EMAIL_ADDRESS", "LOCATION"]

# Map Presidio's entity names to the placeholder tags used in the brief's
# example ("<NAME>", "<PHONE>") rather than Presidio's raw labels.
TAG_MAP = {
    "PERSON": "NAME",
    "PHONE_NUMBER": "PHONE",
    "EMAIL_ADDRESS": "EMAIL",
    "LOCATION": "LOCATION",
}

_analyzer = AnalyzerEngine()
_anonymizer = AnonymizerEngine()


@dataclass
class SanitizeResult:
    sanitized_text: str
    detections: dict  # e.g. {"NAME": 1, "PHONE": 1}


def sanitize_prompt(raw_text: str, language: str = "en") -> SanitizeResult:
    results = _analyzer.analyze(
        text=raw_text,
        entities=SUPPORTED_ENTITIES,
        language=language,
    )

    # Build per-entity-type anonymization operators so each tag reads as
    # <NAME>, <PHONE>, etc. instead of Presidio's default <PERSON>.
    operators = {
        entity: OperatorConfig("replace", {"new_value": f"<{TAG_MAP[entity]}>"})
        for entity in SUPPORTED_ENTITIES
    }

    anonymized = _anonymizer.anonymize(
        text=raw_text,
        analyzer_results=results,
        operators=operators,
    )

    # Tally detections by our simplified tag name for storage as metadata.
    detections: dict = {}
    for r in results:
        tag = TAG_MAP.get(r.entity_type, r.entity_type)
        detections[tag] = detections.get(tag, 0) + 1

    return SanitizeResult(
        sanitized_text=anonymized.text,
        detections=detections,
    )

"""
if __name__ == "__main__":
    # Matches the brief's exact example — quick manual sanity check.
    example = "Write a reminder email to Ramesh, phone 9840112233."
    result = sanitize_prompt(example)
    print("Input: ", example)
    print("Output:", result.sanitized_text)
    print("Detections:", result.detections)"""
if __name__ == "__main__":
    test_cases = [
        # Baseline — matches the brief's exact example.
        "Write a reminder email to Ramesh, phone 9840112233.",

        # Unusual phone formatting (dashes/spaces/country code)
        "Call me at +91 98401-22233 tomorrow.",

        # Informal/lowercase name usage
        "hey it's me, arjun here, my number is 9840112233 lol",

        # Place name — check for false positive vs correct LOCATION tag
        "I'm flying to Chennai next week to meet the team.",

        # Harder 1: name with no capitalization at all, embedded mid-sentence
        "can you check if priya sent the report yet",

        # Harder 2: phone number with no spacing/formatting at all, glued to other text
        "mynumberis9840112233callme",

        # Harder 3: a common English word that is ALSO a real first name (ambiguous)
        "Please ask Grace to review the document.",

        # Harder 4: PII inside a possessive / contracted form
        "That's Kavya's phone, 9840112233, in case you need it.",


        # Harder 5: two names close together, one of which is a company/brand
        "Ravi from Infosys called about the order.",

        # Follow-up: same number, just with a single space added before it
        "mynumberis 9840112233 callme",

        # Follow-up: number completely isolated, no surrounding text at all
        "9840112233",
    ]
    

    for i, text in enumerate(test_cases, 1):
        result = sanitize_prompt(text)
        print(f"\n--- Test {i} ---")
        print("Input: ", text)
        print("Output:", result.sanitized_text)
        print("Detections:", result.detections)