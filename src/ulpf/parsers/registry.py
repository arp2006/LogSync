from ulpf.parsers.base import LogParser
from ulpf.parsers.cef_parser import CEFParser
from ulpf.parsers.json_parser import JSONParser
from ulpf.parsers.syslog_parser import SyslogParser


class ParserRegistry:
    def __init__(self) -> None:
        self._parsers: dict[str, LogParser] = {}

    def register(self, format_name: str, parser: LogParser) -> None:
        self._parsers[format_name.lower()] = parser

    def get(self, format_name: str) -> LogParser:
        try:
            return self._parsers[format_name.lower()]
        except KeyError as exc:
            raise ValueError(f"Unsupported input format: {format_name}") from exc

    def supported_formats(self) -> list[str]:
        return sorted(self._parsers.keys())


def create_default_registry() -> ParserRegistry:
    registry = ParserRegistry()
    registry.register("json", JSONParser())
    registry.register("cef", CEFParser())
    registry.register("syslog", SyslogParser())
    return registry


default_registry = create_default_registry()
