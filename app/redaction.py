"""PII redaction (Microsoft Presidio) applied before model calls and after
outputs. Every redaction is recorded as an audit event so redaction efficacy
is itself auditable."""
from functools import lru_cache

from presidio_analyzer import AnalyzerEngine
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_anonymizer import AnonymizerEngine

ENTITIES = ["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "CREDIT_CARD", "IBAN_CODE", "US_SSN", "IP_ADDRESS"]

# Currency-shaped: digits with comma/decimal separators and no spaces.
# Spaced digit groups ("971 50 123 4567") stay phone-shaped and get redacted.
_CURRENCY = __import__("re").compile(r"\d[\d]*[.,][\d.,]*")


def _false_positive(text: str, r) -> bool:
    """Domain false-positive filters, each documented in the security doc:
    - sub-0.35 confidence findings are noise from the statistical recognizers
      (Presidio's pattern recognizers score real phone matches at 0.4)
    - PHONE_NUMBER spans that are pure digits/commas/periods are currency
      fragments (real phone numbers carry +, dashes, or parentheses)
    - single-token PERSON spans are overwhelmingly business vocabulary
      ('Variance', 'Treasury') mis-tagged by NER; real references in
      enterprise reports use full names, which redact correctly"""
    span = text[r.start:r.end]
    if r.score < 0.35:
        return True
    if r.entity_type == "PHONE_NUMBER" and _CURRENCY.fullmatch(span.strip()):
        return True
    if r.entity_type == "PERSON" and " " not in span.strip():
        return True
    return False


@lru_cache(maxsize=1)
def _engines() -> tuple[AnalyzerEngine, AnonymizerEngine]:
    provider = NlpEngineProvider(nlp_configuration={
        "nlp_engine_name": "spacy",
        "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}],
    })
    analyzer = AnalyzerEngine(nlp_engine=provider.create_engine(), supported_languages=["en"])
    return analyzer, AnonymizerEngine()


def redact(text: str) -> tuple[str, list[dict]]:
    """Returns (redacted_text, findings). Findings carry entity type and span
    only, never the raw value, so the audit log itself stays PII-free."""
    if not text:
        return text, []
    analyzer, anonymizer = _engines()
    results = analyzer.analyze(text=text, entities=ENTITIES, language="en")
    results = [r for r in results if not _false_positive(text, r)]
    if not results:
        return text, []
    redacted = anonymizer.anonymize(text=text, analyzer_results=results).text
    findings = [
        {"entity_type": r.entity_type, "start": r.start, "end": r.end, "score": round(r.score, 2)}
        for r in results
    ]
    return redacted, findings
