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


class LogParseContext:
    def __init__(self, registry: DefinitionRegistry):
        self.scenarios: List[Scenario] = []
        self.current_scenario: Optional[Scenario] = None
        self.active_groups: Dict[str, Group] = {}
        self.registry = registry

    def start_scenario(self, name: str):
        if self.current_scenario:
            self.scenarios.append(self.current_scenario)
        self.current_scenario = Scenario(name=name)
        self.active_groups.clear()

    def start_group(self, name: str):
        if self.current_scenario is None:
            return
        if name in self.active_groups:
            completed_group = self.active_groups.pop(name)
            self.current_scenario.groups.append(completed_group)
        self.active_groups[name] = Group(name=name)

    def end_group(self, name: str):
        if self.current_scenario is None:
            return
        group = self.active_groups.pop(name, None)
        if group:
            self.current_scenario.groups.append(group)

    def add_log_to_active_groups(self, log: Log):
        for name, group in self.active_groups.items():
            definition = self.registry.get_group_definition(name)
            if not definition:
                continue
            for pattern_name in definition.log_pattern_names:
                pattern = self.registry.get_log_pattern(pattern_name)
                if pattern and pattern.pattern.search(log.content):
                    group.logs.append(log)
                    break

    def finalize(self):
        if self.current_scenario:
            for group in self.active_groups.values():
                self.current_scenario.groups.append(group)
            self.scenarios.append(self.current_scenario)
            self.current_scenario = None
        self.active_groups.clear()

    def get_scenarios(self) -> List[Scenario]:
        return self.scenarios


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
