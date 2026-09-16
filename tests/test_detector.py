import pytest
from app.services.detector import detect, DetectionResult

def test_detector_clean():
    # Oficial OK + Agente OK -> limpio
    res = detect(
        officer_name="Edward Hidalgo",
        registered_agent="Edward Hidalgo",
        expected_agent="Edward Hidalgo",
        campos_esperados={"officer": "requerido", "agent": "requerido"}
    )
    assert res.is_theft is False
    assert res.officer_clean is True
    assert res.agent_clean is True

def test_detector_officer_replaced():
    # Oficial FALSO + Agente OK -> ALERTA
    res = detect(
        officer_name="Maria Hidalgo",
        registered_agent="Edward Hidalgo",
        expected_agent="Edward Hidalgo",
        campos_esperados={"officer": "requerido", "agent": "requerido"}
    )
    assert res.is_theft is True
    assert res.officer_clean is False
    assert res.agent_clean is True
    assert "Oficial no autorizado" in res.reason

def test_detector_agent_replaced():
    # Oficial OK + Agente FALSO -> ALERTA
    res = detect(
        officer_name="Edward Hidalgo",
        registered_agent="Maria Hidalgo",
        expected_agent="Edward Hidalgo",
        campos_esperados={"officer": "requerido", "agent": "requerido"}
    )
    assert res.is_theft is True
    assert res.officer_clean is True
    assert res.agent_clean is False
    assert "Agente no autorizado" in res.reason

def test_detector_both_replaced():
    # Ambos FALSOS -> ALERTA
    res = detect(
        officer_name="John Doe",
        registered_agent="Maria Hidalgo",
        expected_agent="Edward Hidalgo",
        campos_esperados={"officer": "requerido", "agent": "requerido"}
    )
    assert res.is_theft is True
    assert res.officer_clean is False
    assert res.agent_clean is False
    assert "Oficial no autorizado" in res.reason
    assert "Agente no autorizado" in res.reason

def test_detector_empty_strings():
    # Strings vacíos -> ALERTA por no extraer nada (requeridos)
    res = detect(
        officer_name="",
        registered_agent="",
        expected_agent="Edward Hidalgo",
        campos_esperados={"officer": "requerido", "agent": "requerido"}
    )
    assert res.is_theft is True
    assert res.officer_clean is False
    assert res.agent_clean is False
    assert "Oficial vacío" in res.reason
    assert "Agente vacío" in res.reason

def test_detector_partial_token_match():
    # Tokenización debe fallar si es un substring ("Edwardo" != "Edward")
    res = detect(
        officer_name="Edwardo Hidalgo",
        registered_agent="Edward Hidalgo",
        expected_agent="Edward Hidalgo",
        campos_esperados={"officer": "requerido", "agent": "requerido"}
    )
    assert res.is_theft is True
    assert res.officer_clean is False
    assert res.agent_clean is True

def test_detector_campo_no_publicado():
    # Si un estado no publica oficial, no debe alertar si llega vacío
    res = detect(
        officer_name="",
        registered_agent="Edward Hidalgo",
        expected_agent="Edward Hidalgo",
        campos_esperados={"officer": "no_publicado", "agent": "requerido"}
    )
    assert res.is_theft is False
    assert res.officer_clean is True
    assert res.is_verifiable is True

def test_detector_campo_requerido_vacio():
    # Si un estado publica oficial, y llega vacío, DEBE alertar
    res = detect(
        officer_name="",
        registered_agent="Edward Hidalgo",
        expected_agent="Edward Hidalgo",
        campos_esperados={"officer": "requerido", "agent": "requerido"}
    )
    assert res.is_theft is True
    assert res.officer_clean is False
    assert res.is_verifiable is True
    assert "Oficial vacío (requerido)" in res.reason

def test_detector_campo_sin_verificar_vacio():
    # Si no sabemos qué hace el estado, y llega vacío, NO VERIFICABLE
    res = detect(
        officer_name="",
        registered_agent="Edward Hidalgo",
        expected_agent="Edward Hidalgo",
        campos_esperados={"officer": "sin_verificar", "agent": "requerido"}
    )
    assert res.is_theft is False
    assert res.is_verifiable is False
    assert res.status == "No Verificable"
    assert "Oficial vacío (sin verificar)" in res.reason
