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
        self.scenarios: List[Scenario] = []  # 모든 시나리오 보존
        self.current_scenario: Optional[Scenario] = None  # 현재 시나리오
        self.active_groups: Dict[str, Group] = {}  # 활성 그룹
        self.group_definitions: Dict[str, GroupDefinition] = {}  # 그룹 정의

    def set_definitions(self, definitions: Dict[str, GroupDefinition]):
        self.group_definitions = definitions

    def start_scenario(self, name: str):
        # 새로운 시나리오가 시작되면 기존 시나리오는 self.scenarios에 저장
        if self.current_scenario:
            self.scenarios.append(self.current_scenario)
        self.current_scenario = Scenario(name=name)  # 새로운 시나리오 시작

    def start_group(self, name: str):
        if self.current_scenario is None:
            return
        # 이미 active_groups에 해당 이름의 그룹이 존재하면, 이전 그룹을 'end' 상태로 변경
        if name in self.active_groups:
            completed_group = self.active_groups.pop(name)
            self.current_scenario.groups.append(completed_group)  # 완료된 그룹을 scenario의 groups에 추가

        group = Group(name=name)
        self.active_groups[name] = group  # 새로운 그룹을 active_groups에 추가

    def end_group(self, name: str):
        if name in self.active_groups:
            completed_group = self.active_groups.pop(name)
            self.current_scenario.groups.append(completed_group)  # 완료된 그룹을 scenario의 groups에 추가

    def add_log_to_active_groups(self, log: Log):
        for group_name, group in self.active_groups.items():
            definition = self.group_definitions.get(group_name)
            if not definition:
                continue
            for pattern in definition.log_patterns:
                if any(tag in log.content for tag in pattern.tags):
                    group.logs.append(log)

    def finalize(self):
        # 모든 활성 그룹을 완료 상태로 변경하여 scenario의 groups에 추가
        for group_name, group in self.active_groups.items():
            self.current_scenario.groups.append(group)
        self.active_groups.clear()

        # 현재 시나리오가 존재하면 self.scenarios에 추가
        if self.current_scenario:
            self.scenarios.append(self.current_scenario)
        self.current_scenario = None  # 현재 시나리오를 초기화

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
