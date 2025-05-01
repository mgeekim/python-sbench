import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional


# --- 데이터 클래스 정의 ---

@dataclass
class Log:
    timestamp: datetime
    pid: int
    level: str
    content: str
    raw: str


@dataclass
class LogPattern:
    name: str
    pattern: re.Pattern
    tags: List[str]


@dataclass
class Group:
    name: str
    logs: List[Log] = field(default_factory=list)


@dataclass
class Scenario:
    name: str
    groups: List[Group] = field(default_factory=list)


@dataclass
class GroupDefinition:
    name: str
    start_pattern: re.Pattern
    end_pattern: re.Pattern
    log_pattern_names: List[str]  # LogPattern 이름 목록


# --- 정의 레지스트리 클래스 ---
class DefinitionRegistry:
    def __init__(self, group_definitions: List[GroupDefinition], log_patterns: List[LogPattern]):
        self.group_definition_map: Dict[str, GroupDefinition] = {
            definition.name: definition for definition in group_definitions
        }
        self.log_pattern_map: Dict[str, LogPattern] = {
            pattern.name: pattern for pattern in log_patterns
        }

    def get_group_definition(self, name: str) -> Optional[GroupDefinition]:
        return self.group_definition_map.get(name)

    def get_log_pattern(self, name: str) -> Optional[LogPattern]:
        return self.log_pattern_map.get(name)

    def all_group_definitions(self) -> Dict[str, GroupDefinition]:
        return self.group_definition_map


class GroupManager:
    def __init__(self, registry: DefinitionRegistry):
        self._registry = registry
        self._active: Dict[str, Group] = {}

    def start_group(self, name: str) -> Optional[Group]:
        existing_group = self._active.get(name, None)
        self._active[name] = Group(name=name)
        return existing_group  # 기존 그룹을 반환하여 기존 상태를 유지할 수 있도록 함

    def end_group(self, name: str) -> Optional[Group]:
        return self._active.pop(name, None)

    def add_log(self, log: Log):
        for name, group in self._active.items():
            if (definition := self._registry.get_group_definition(name)):
                for pattern_name in definition.log_pattern_names:
                    if (pattern := self._registry.get_log_pattern(pattern_name)) and pattern.pattern.search(
                            log.content):
                        group.logs.append(log)
                        break

    def flush(self) -> List[Group]:
        groups = list(self._active.values())
        self._active.clear()
        return groups


class ScenarioManager:
    def __init__(self):
        self._scenarios: List[Scenario] = []
        self._current: Optional[Scenario] = None

    def start_scenario(self, name: str):
        if self._current:
            self._scenarios.append(self._current)
        self._current = Scenario(name=name)

    def add_group(self, group: Group):
        if self._current:
            self._current.groups.append(group)

    def finalize(self, groups: List[Group]):
        if self._current:
            self._current.groups.extend(groups)
            self._scenarios.append(self._current)
            self._current = None

    def get_scenarios(self) -> List[Scenario]:
        return self._scenarios


class LogParseContext:
    def __init__(self, registry: DefinitionRegistry):
        self._groups = GroupManager(registry)
        self._scenarios = ScenarioManager()

    def start_scenario(self, name: str):
        self._scenarios.start_scenario(name)

    def start_group(self, name: str):
        if (completed := self._groups.start_group(name)):
            self._scenarios.add_group(completed)

    def end_group(self, name: str):
        if (completed := self._groups.end_group(name)):
            self._scenarios.add_group(completed)

    def add_log_to_active_groups(self, log: Log):
        self._groups.add_log(log)

    def finalize(self):
        remaining_groups = self._groups.flush()
        self._scenarios.finalize(remaining_groups)

    def get_scenarios(self) -> List[Scenario]:
        return self._scenarios.get_scenarios()


# --- 로그 핸들러 ---

class BaseLogHandler:
    def handle(self, log: Log, state: LogParseContext):
        raise NotImplementedError()


class ScenarioHandler(BaseLogHandler):
    pattern = re.compile(r"\[Scenario\] (.+)")

    def handle(self, log: Log, state: LogParseContext):
        match = self.pattern.search(log.content)
        if match:
            state.start_scenario(match.group(1))


class GroupHandler(BaseLogHandler):
    def __init__(self, registry: DefinitionRegistry):
        self.registry = registry

    def handle(self, log: Log, state: LogParseContext):
        for name, definition in self.registry.all_group_definitions().items():
            if definition.start_pattern.search(log.content):
                state.start_group(name)
            elif definition.end_pattern.search(log.content):
                state.end_group(name)


class TaggedLogHandler(BaseLogHandler):
    def handle(self, log: Log, state: LogParseContext):
        state.add_log_to_active_groups(log)


# --- 유틸리티 함수 ---

LOG_LINE_PATTERN = re.compile(
    r"(?P<timestamp>\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (?P<pid>\d+) (?P<level>[TDIEW]) (?P<content>.+)"
)


def parse_log_line(line: str) -> Optional[Log]:
    match = LOG_LINE_PATTERN.match(line)
    if not match:
        return None
    return Log(
        timestamp=datetime.strptime(match.group("timestamp"), "%m-%d %H:%M:%S"),
        pid=int(match.group("pid")),
        level=match.group("level"),
        content=match.group("content"),
        raw=line
    )


def parse_line(line: str, state: LogParseContext, handlers: List[BaseLogHandler]):
    log = parse_log_line(line)
    if not log:
        return
    for handler in handlers:
        handler.handle(log, state)


class LogParser:
    def __init__(self, group_definitions: List[GroupDefinition], log_patterns: List[LogPattern]):
        self.registry = DefinitionRegistry(group_definitions, log_patterns)
        self.state = LogParseContext(self.registry)

        self.handlers = [
            ScenarioHandler(),
            GroupHandler(self.registry),
            TaggedLogHandler()
        ]

    def parse_lines(self, lines: List[str]):
        for line in lines:
            parse_line(line, self.state, self.handlers)
        self.state.finalize()

    def get_scenarios(self) -> List[Scenario]:
        return self.state.get_scenarios()
