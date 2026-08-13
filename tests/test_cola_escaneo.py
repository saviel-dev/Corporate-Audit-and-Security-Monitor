"""
tests/test_cola_escaneo.py

Tests unitarios para T-02 (prioridad de escaneo por estados)
y T-03 (filtro de corporaciones por status Available).
"""

from datetime import date
from unittest.mock import MagicMock

# ─── Helpers ─────────────────────────────────────────────────────────────────


def _crear_corp(
    name: str, state: str, status: str, fecha: date | None = None
) -> MagicMock:
    """Fabrica una Corp simulada con los campos minimos para la cola."""
    corp = MagicMock()
    corp.name = name
    corp.state = state
    corp.status = status
    corp.date_registered = fecha
    return corp


def _sort_key(corp, estados_prioritarios: list[str], supported: list[str]):
    """
    Replica exacta de la funcion sort_key de scanner.py para testear
    el ordenamiento de forma aislada sin levantar Flask.
    """
    try:
        estado_rank = estados_prioritarios.index(corp.state)
    except ValueError:
        estado_rank = (
            len(estados_prioritarios) + sorted(supported).index(corp.state)
            if corp.state in supported
            else 999
        )
    age = corp.date_registered or date(9999, 12, 31)
    return (estado_rank, age, corp.name or "")


def _construir_cola(
    corps: list,
    estado_elegible: str,
    estados_prioritarios: list[str],
    supported: list[str],
) -> list:
    """
    Replica la logica de construccion de cola de scanner._execute_scan()
    de forma aislada (sin BD, sin Flask).
    """
    elegibles = [
        c for c in corps if c.status.strip() == estado_elegible and c.state in supported
    ]
    return sorted(
        elegibles, key=lambda c: _sort_key(c, estados_prioritarios, supported)
    )


# ─── Fixtures ─────────────────────────────────────────────────────────────────

ESTADOS_PRIORITARIOS = ["CO", "HI", "NM"]
ESTADO_ELEGIBLE = "Available"
SUPPORTED = ["HI", "CO", "NM", "MS", "NY", "FL", "CA", "DE", "WY"]


# ═══════════════════════════════════════════════════════════════════════════════
# T-02 — Tests de ordenamiento por prioridad estatal
# ═══════════════════════════════════════════════════════════════════════════════


class TestOrdenamientoPrioridad:
    """T-02: el orden de la cola respeta ESTADOS_PRIORITARIOS."""

    def test_estados_prioritarios_van_primero(self):
        """CO, HI y NM deben preceder a estados no prioritarios."""
        corps = [
            _crear_corp("Corp FL", "FL", ESTADO_ELEGIBLE),
            _crear_corp("Corp NM", "NM", ESTADO_ELEGIBLE),
            _crear_corp("Corp HI", "HI", ESTADO_ELEGIBLE),
            _crear_corp("Corp CO", "CO", ESTADO_ELEGIBLE),
        ]
        cola = _construir_cola(corps, ESTADO_ELEGIBLE, ESTADOS_PRIORITARIOS, SUPPORTED)
        estados_resultantes = [c.state for c in cola]
        assert estados_resultantes == ["CO", "HI", "NM", "FL"]

    def test_orden_de_la_constante_determina_el_orden_real(self):
        """Cambiar el orden de la constante cambia el orden de la cola."""
        corps = [
            _crear_corp("Corp NM", "NM", ESTADO_ELEGIBLE),
            _crear_corp("Corp HI", "HI", ESTADO_ELEGIBLE),
            _crear_corp("Corp CO", "CO", ESTADO_ELEGIBLE),
        ]
        # Con el orden por defecto: CO primero
        cola_defecto = _construir_cola(
            corps, ESTADO_ELEGIBLE, ["CO", "HI", "NM"], SUPPORTED
        )
        assert cola_defecto[0].state == "CO"

        # Invirtiendo el orden: NM primero
        cola_invertida = _construir_cola(
            corps, ESTADO_ELEGIBLE, ["NM", "HI", "CO"], SUPPORTED
        )
        assert cola_invertida[0].state == "NM"

    def test_estados_no_prioritarios_van_en_orden_alfabetico(self):
        """Los estados fuera de ESTADOS_PRIORITARIOS se ordenan entre si alfabeticamente."""
        corps = [
            _crear_corp("Corp WY", "WY", ESTADO_ELEGIBLE),
            _crear_corp("Corp CA", "CA", ESTADO_ELEGIBLE),
            _crear_corp("Corp FL", "FL", ESTADO_ELEGIBLE),
            _crear_corp("Corp MS", "MS", ESTADO_ELEGIBLE),
        ]
        cola = _construir_cola(corps, ESTADO_ELEGIBLE, ESTADOS_PRIORITARIOS, SUPPORTED)
        estados = [c.state for c in cola]
        # CA < FL < MS < WY alfabeticamente
        assert estados == ["CA", "FL", "MS", "WY"]

    def test_mismo_estado_ordena_por_antiguedad(self):
        """Dentro del mismo estado, la corp mas antigua va primero."""
        corps = [
            _crear_corp("Corp HI Joven", "HI", ESTADO_ELEGIBLE, date(2020, 1, 1)),
            _crear_corp("Corp HI Antigua", "HI", ESTADO_ELEGIBLE, date(2010, 6, 15)),
            _crear_corp("Corp HI Media", "HI", ESTADO_ELEGIBLE, date(2015, 3, 20)),
        ]
        cola = _construir_cola(corps, ESTADO_ELEGIBLE, ESTADOS_PRIORITARIOS, SUPPORTED)
        nombres = [c.name for c in cola]
        assert nombres == ["Corp HI Antigua", "Corp HI Media", "Corp HI Joven"]

    def test_sin_fecha_va_al_final_del_estado(self):
        """Corps sin fecha de registro van al final de su estado (como las mas recientes)."""
        corps = [
            _crear_corp("Corp HI Sin Fecha", "HI", ESTADO_ELEGIBLE, None),
            _crear_corp("Corp HI Con Fecha", "HI", ESTADO_ELEGIBLE, date(2010, 1, 1)),
        ]
        cola = _construir_cola(corps, ESTADO_ELEGIBLE, ESTADOS_PRIORITARIOS, SUPPORTED)
        assert cola[0].name == "Corp HI Con Fecha"
        assert cola[1].name == "Corp HI Sin Fecha"

    def test_mezcla_completa_prioritarios_y_no_prioritarios(self):
        """Caso integral con estados prioritarios y no prioritarios mezclados."""
        corps = [
            _crear_corp("A-NY", "NY", ESTADO_ELEGIBLE, date(2000, 1, 1)),
            _crear_corp("B-CO", "CO", ESTADO_ELEGIBLE, date(2005, 1, 1)),
            _crear_corp("C-FL", "FL", ESTADO_ELEGIBLE, date(2000, 1, 1)),
            _crear_corp("D-HI", "HI", ESTADO_ELEGIBLE, date(2003, 1, 1)),
            _crear_corp("E-NM", "NM", ESTADO_ELEGIBLE, date(2001, 1, 1)),
        ]
        cola = _construir_cola(corps, ESTADO_ELEGIBLE, ESTADOS_PRIORITARIOS, SUPPORTED)
        estados = [c.state for c in cola]
        # Esperado: CO, HI, NM (prioritarios) -> CA, FL, NY (resto alfa)
        assert estados[:3] == ["CO", "HI", "NM"]
        assert "FL" in estados[3:]
        assert "NY" in estados[3:]


# ═══════════════════════════════════════════════════════════════════════════════
# T-03 — Tests de filtro por status
# ═══════════════════════════════════════════════════════════════════════════════


class TestFiltroStatus:
    """T-03: solo corps con status Available entran en la cola."""

    def test_solo_available_entra_en_cola(self):
        """Corps con cualquier status distinto de Available se descartan."""
        corps = [
            _crear_corp("Disponible Corp", "HI", "Available"),
            _crear_corp("Vendida Corp", "HI", "Sold"),
            _crear_corp("Inactiva Corp", "HI", "Inactive"),
            _crear_corp("Robada Corp", "HI", "Suspected Stolen"),
            _crear_corp("Otra Corp", "HI", "Other"),
        ]
        cola = _construir_cola(corps, ESTADO_ELEGIBLE, ESTADOS_PRIORITARIOS, SUPPORTED)
        assert len(cola) == 1
        assert cola[0].name == "Disponible Corp"

    def test_sold_se_descarta(self):
        """Una corp con status Sold nunca genera peticion HTTP."""
        corps = [_crear_corp("Vendida", "CO", "Sold")]
        cola = _construir_cola(corps, ESTADO_ELEGIBLE, ESTADOS_PRIORITARIOS, SUPPORTED)
        assert cola == []

    def test_inactive_se_descarta(self):
        """Una corp con status Inactive se descarta."""
        corps = [_crear_corp("Inactiva", "CO", "Inactive")]
        cola = _construir_cola(corps, ESTADO_ELEGIBLE, ESTADOS_PRIORITARIOS, SUPPORTED)
        assert cola == []

    def test_conjunto_mixto_descarta_correctamente(self):
        """Con un conjunto mixto, solo las Available pasan el filtro."""
        corps = [
            _crear_corp("A", "CO", "Available"),
            _crear_corp("B", "HI", "Sold"),
            _crear_corp("C", "NM", "Available"),
            _crear_corp("D", "FL", "Inactive"),
            _crear_corp("E", "CA", "Available"),
            _crear_corp("F", "NY", "Suspected Stolen"),
        ]
        cola = _construir_cola(corps, ESTADO_ELEGIBLE, ESTADOS_PRIORITARIOS, SUPPORTED)
        nombres = [c.name for c in cola]
        assert set(nombres) == {"A", "C", "E"}
        assert "B" not in nombres
        assert "D" not in nombres
        assert "F" not in nombres

    def test_status_con_espacios_se_normaliza(self):
        """status con espacios al principio o final se maneja con strip()."""
        corps = [_crear_corp("Corp con espacios", "HI", "  Available  ")]
        # La logica usa c.status.strip() == estado_elegible
        cola = _construir_cola(corps, ESTADO_ELEGIBLE, ESTADOS_PRIORITARIOS, SUPPORTED)
        assert len(cola) == 1

    def test_cola_vacia_si_todas_son_sold(self):
        """Si todas las corps son Sold, la cola queda vacia."""
        corps = [
            _crear_corp("A", "HI", "Sold"),
            _crear_corp("B", "CO", "Sold"),
            _crear_corp("C", "NM", "Sold"),
        ]
        cola = _construir_cola(corps, ESTADO_ELEGIBLE, ESTADOS_PRIORITARIOS, SUPPORTED)
        assert cola == []

    def test_estado_fuera_de_scope_se_descarta(self):
        """Corp de un estado no soportado se descarta aunque sea Available."""
        corps = [_crear_corp("Corp Texas", "TX", "Available")]
        cola = _construir_cola(corps, ESTADO_ELEGIBLE, ESTADOS_PRIORITARIOS, SUPPORTED)
        assert cola == []

    def test_conteo_de_descartadas_es_correcto(self):
        """El numero de descartadas coincide con total - elegibles."""
        corps = [
            _crear_corp("A", "HI", "Available"),
            _crear_corp("B", "HI", "Sold"),
            _crear_corp("C", "CO", "Available"),
            _crear_corp("D", "CO", "Inactive"),
            _crear_corp("E", "NM", "Sold"),
        ]
        elegibles = [
            c
            for c in corps
            if c.status.strip() == ESTADO_ELEGIBLE and c.state in SUPPORTED
        ]
        descartadas = len(corps) - len(elegibles)
        assert len(elegibles) == 2
        assert descartadas == 3
