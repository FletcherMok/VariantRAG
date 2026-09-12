"""Small local HTTP adapter around the real Mutalyzer normalization library."""

from fastapi import FastAPI, HTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .security import LocalBoundary

app = FastAPI(title="VariantRAG local Mutalyzer adapter")
app.add_middleware(LocalBoundary)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "[::1]", "mutalyzer"])


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/normalize/{description:path}")
def normalize_description(description: str, only_variants: bool = False, sequence: str | None = None):
    if len(description) > 4096 or (sequence and len(sequence) > 100000):
        raise HTTPException(413, "Normalization input exceeds local limits")
    from mutalyzer.normalizer import normalize

    return normalize(description, only_variants=only_variants, sequence=sequence)
