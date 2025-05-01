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
    log_patterns: List[str]  # LogPattern 이름 목록


def create_log_pattern_map(patterns: List[LogPattern]) -> Dict[str, LogPattern]:
    return {pattern.name: pattern for pattern in patterns}


def create_group_definition_map(definitions: List[GroupDefinition]) -> Dict[str, GroupDefinition]:
    return {definition.name: definition for definition in definitions}


# --- 파서 상태 ---

class ParserState:
    def __init__(self):
        self.scenarios: List[Scenario] = []
        self.current_scenario: Optional[Scenario] = None
        self.active_groups: Dict[str, Group] = {}
        self.group_definitions: Dict[str, GroupDefinition] = {}
        self.log_patterns: Dict[str, LogPattern] = {}

    def set_definitions(self, definitions: Dict[str, GroupDefinition], log_patterns: Dict[str, LogPattern]):
        self.group_definitions = definitions
        self.log_patterns = log_patterns

    def start_scenario(self, name: str):
        if self.current_scenario:
            self.scenarios.append(self.current_scenario)
        self.current_scenario = Scenario(name=name)
        self.active_groups.clear()

    def start_group(self, name: str):
        if self.current_scenario is None:
            return

        # 동일 이름 그룹이 이미 존재하면 완료 처리 후 교체
        if name in self.active_groups:
            completed_group = self.active_groups.pop(name)
            self.current_scenario.groups.append(completed_group)

        group = Group(name=name)
        self.active_groups[name] = group

    def end_group(self, name: str):
        if self.current_scenario is None:
            return
        group = self.active_groups.pop(name, None)
        if group:
            self.current_scenario.groups.append(group)

    def add_log_to_active_groups(self, log: Log):
        for name, group in self.active_groups.items():
            definition = self.group_definitions.get(name)
            if not definition:
                continue

            for pattern_name in definition.log_patterns:
                pattern = self.log_patterns.get(pattern_name)
                if pattern and pattern.pattern.search(log.content):
                    group.logs.append(log)
                    break

    def finalize(self):
        if self.current_scenario:
            # 종료되지 않은 그룹도 포함하여 마무리
            for group in self.active_groups.values():
                self.current_scenario.groups.append(group)
            self.scenarios.append(self.current_scenario)
            self.current_scenario = None
        self.active_groups.clear()

    def get_scenarios(self) -> List[Scenario]:
        return self.scenarios


# --- 로그 핸들러 ---

class BaseLogHandler:
    def handle(self, log: Log, state: ParserState):
        raise NotImplementedError()


class ScenarioHandler(BaseLogHandler):
    pattern = re.compile(r"\[Scenario\] (.+)")

    def handle(self, log: Log, state: ParserState):
        match = self.pattern.search(log.content)
        if match:
            state.start_scenario(match.group(1))


class GroupHandler(BaseLogHandler):
    def __init__(self, definitions: Dict[str, GroupDefinition]):
        self.definitions = definitions

    def handle(self, log: Log, state: ParserState):
        for name, definition in self.definitions.items():
            if definition.start_pattern.search(log.content):
                state.start_group(name)
            elif definition.end_pattern.search(log.content):
                state.end_group(name)


class TaggedLogHandler(BaseLogHandler):
    def handle(self, log: Log, state: ParserState):
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


def parse_line(line: str, state: ParserState, handlers: List[BaseLogHandler]):
    log = parse_log_line(line)
    if not log:
        return
    for handler in handlers:
        handler.handle(log, state)
