#!/usr/bin/env python3
"""Valida la sintaxis YAML y el subconjunto de interpolación usado en Coolify.

Requiere PyYAML. No ejecuta Docker ni sustituye valores o secretos.
"""
from pathlib import Path
import re
import yaml

ROOT = Path(__file__).resolve().parents[1]
NAME = r"[A-Za-z_][A-Za-z0-9_.]*"
EXPRESSION = re.compile(r"(" + NAME + r")(?::[-?]([^${}]*))?")


def validate(text):
    names = set()
    position = 0
    count = 0
    while True:
        start = text.find("${", position)
        if start == -1:
            break
        end = text.find("}", start + 2)
        if end == -1:
            raise ValueError(f"Interpolación sin cerrar en posición {start}")
        body = text[start + 2:end]
        match = EXPRESSION.fullmatch(body)
        if not match or ':+' in body:
            raise ValueError(f"Interpolación no admitida: {body!r}")
        names.add(match[1])
        count += 1
        position = end + 1
    return count, names


def main():
    text = (ROOT / 'docker-compose.coolify.yml').read_text()
    count, names = validate(text)
    document = yaml.safe_load(text)
    assert isinstance(document, dict) and document.get('services')
    services = document['services']
    for name, service in services.items():
        assert not any(key in service for key in ('profiles', 'ports', 'env_file')), name
        for dependency in service.get('depends_on', {}):
            assert dependency in services, (name, dependency)
    assert services['server']['environment']['NODE_ENV'] == 'production'
    assert services['supervisor']['environment']['COMPUTER_NETWORK'] == document['networks']['default']['name']
    for service in services.values():
        assert 'build' not in service
    assert services['agent-computer']['pull_policy'] == 'always'
    assert services['supervisor']['environment']['COMPUTER_IMAGE'] == services['agent-computer']['image']
    for valid in ('${NAME}', '${NAME:-default}', '${NAME:?msg}', '${NAME.with_dot}'):
        validate(valid)
    # Comprueba también que el validador detecta las formas que queremos evitar.
    for invalid in ('${OUTER:-${INNER:-}}', '${VAR:+value}', '${9BAD}', '${UNCLOSED'):
        try:
            validate(invalid)
        except ValueError:
            pass
        else:
            raise AssertionError(f'No se rechazó {invalid}')
    print(f'OK: YAML válido; {len(services)} servicios; {count} interpolaciones; {len(names)} variables válidas.')


if __name__ == '__main__':
    main()
