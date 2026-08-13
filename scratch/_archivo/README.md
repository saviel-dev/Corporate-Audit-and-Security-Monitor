# Archivo de Scripts de Diagnóstico

Este directorio contiene scripts históricos de diagnóstico e investigación (inspección de Shadow DOM, pruebas de selectores, pruebas de Stealth).

Han sido movidos aquí y renombrados a `.py.bak` para evitar su ejecución accidental, ya que **instancian Playwright directamente**, violando la regla 1.4 de la arquitectura (todo scraping debe pasar por el flujo de `app/scrapers/base.py` para garantizar el uso de Stealth y pausas de limitación de frecuencia).

Mantén este directorio como referencia técnica, pero no los ejecutes.
