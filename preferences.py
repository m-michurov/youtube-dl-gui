import json
from pathlib import Path
from typing import Any


class Preferences:
    def __init__(self, path: Path) -> None:
        self._path = path

        self._config: dict[str, Any] = {}

        try:
            self._update()
        except FileNotFoundError:
            pass

    def _update(self) -> None:
        with self._path.open(mode='rt', encoding='utf-8') as config_file:
            self._config: dict[str, Any] = json.load(config_file)

    def _flush(self) -> None:
        with self._path.open(mode='wt', encoding='utf-8') as config_file:
            json.dump(self._config, config_file)

    def get(self, key: str, default: Any) -> Any:
        return self._config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._config[key] = value
        self._flush()
