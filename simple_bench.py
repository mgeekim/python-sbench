# log_parser_refactored.py

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
    log_patterns: List[LogPattern]


# --- 상태 관리 ---

class ParserState:
    def __init__(self):
        self.scenarios: List[Scenario] = []
        self.current_scenario: Optional[Scenario] = None
        self.active_groups: Dict[str, List[Group]] = {}
        self.group_definitions: Dict[str, GroupDefinition] = {}

    def set_definitions(self, definitions: Dict[str, GroupDefinition]):
        self.group_definitions = definitions

    def start_scenario(self, name: str):
        self.current_scenario = Scenario(name=name)
        self.scenarios.append(self.current_scenario)
        self.active_groups.clear()

    def start_group(self, name: str):
        if self.current_scenario is None:
            return
        group = Group(name=name)
        self.current_scenario.groups.append(group)
        self.active_groups.setdefault(name, []).append(group)

    def end_group(self, name: str):
        if name in self.active_groups and self.active_groups[name]:
            self.active_groups[name].pop()
            if not self.active_groups[name]:
                del self.active_groups[name]

    def add_log_to_active_groups(self, log: Log):
        for group_name, group_list in self.active_groups.items():
            definition = self.group_definitions.get(group_name)
            if not definition:
                continue
            for pattern in definition.log_patterns:
                if any(tag in log.content for tag in pattern.tags):
                    for group in group_list:
                        group.logs.append(log)
                    break

    def finalize(self):
        self.active_groups.clear()

    def get_scenarios(self) -> List[Scenario]:
        return self.scenarios


# --- 핸들러 정의 ---

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
