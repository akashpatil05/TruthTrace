import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_verify_cancer_coffee_claim():
    # Test claim from master prompt
    claim = "Scientists have discovered that drinking coffee completely prevents cancer."
    res = client.post("/api/verify", json={"text": claim})
    assert res.status_code == 200
    data = res.json()
    
    assert data["verdict"] in ["FALSE", "MISLEADING"]
    assert data["confidence"] > 0.5
    assert len(data["contradicting_evidence"]) >= 1
    assert "coffee" in data["contradicting_evidence"][0]["text"].lower()
    assert len(data["reasoning"]) >= 1

def test_verify_unrelated_claim_insufficient_evidence():
    claim = "Martians have landed in Antarctica and begun construction of an underground palace."
    res = client.post("/api/verify", json={"text": claim})
    assert res.status_code == 200
    data = res.json()
    assert data["verdict"] == "INSUFFICIENT_EVIDENCE"
    assert data["confidence"] <= 0.3
    assert len(data["reasoning"]) >= 1
