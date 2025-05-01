import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional


# === 데이터 클래스 정의 ===

@dataclass
class Log:
    timestamp: datetime
    pid: int
    level: str
    content: str


@dataclass
class LogGroup:
    name: str
    logs: List[Log] = field(default_factory=list)


@dataclass
class LogScenario:
    name: str
    groups: List[LogGroup] = field(default_factory=list)


# === 그룹 정의 ===

class GroupDefinition:
    def __init__(self, name: str, start_pattern: re.Pattern, end_pattern: re.Pattern, log_tags: List[str]):
        self.name = name
        self.start_pattern = start_pattern
        self.end_pattern = end_pattern
        self.log_tags = log_tags


# === 상태 관리 ===

class ParserState:
    def __init__(self):
        self.current_scenario: Optional[LogScenario] = None
        self.active_groups: Dict[str, LogGroup] = {}
        self.definitions: Dict[str, GroupDefinition] = {}
        self.completed_scenarios: List[LogScenario] = []

    def set_definitions(self, defs: Dict[str, GroupDefinition]):
        self.definitions = defs

    def start_new_scenario(self, name: str):
        if self.current_scenario:
            self.completed_scenarios.append(self.current_scenario)
        self.current_scenario = LogScenario(name=name)
        self.active_groups.clear()

    def start_group(self, group_name: str):
        if self.current_scenario and group_name not in self.active_groups:
            self.active_groups[group_name] = LogGroup(name=group_name)

    def end_group(self, group_name: str):
        if self.current_scenario and group_name in self.active_groups:
            self.current_scenario.groups.append(self.active_groups.pop(group_name))

    def add_log(self, tag: str, log: Log):
        for group_def in self.definitions.values():
            if tag in group_def.log_tags and group_def.name in self.active_groups:
                self.active_groups[group_def.name].logs.append(log)

    def finalize(self):
        if self.current_scenario:
            for group in self.active_groups.values():
                self.current_scenario.groups.append(group)
            self.completed_scenarios.append(self.current_scenario)
            self.current_scenario = None
            self.active_groups.clear()

    def get_scenarios(self) -> List[LogScenario]:
        return self.completed_scenarios


# === 로그 핸들러 ===

class LogHandler:
    def handle(self, line: str, state: ParserState, parsed: Log):
        raise NotImplementedError


class ScenarioHandler(LogHandler):
    pattern = re.compile(r"\[Scenario\] (?P<name>.+)")

    def handle(self, line: str, state: ParserState, parsed: Log):
        m = self.pattern.search(parsed.content)
        if m:
            state.start_new_scenario(m.group("name"))


class GroupHandler(LogHandler):
    def __init__(self, definitions: Dict[str, GroupDefinition]):
        self.definitions = definitions

    def handle(self, line: str, state: ParserState, parsed: Log):
        for name, defn in self.definitions.items():
            if defn.start_pattern.search(parsed.content):
                state.start_group(name)
            elif defn.end_pattern.search(parsed.content):
                state.end_group(name)


class TaggedLogHandler(LogHandler):
    pattern = re.compile(r"\[Log:(?P<tag>\w+)\] (?P<message>.+)")

    def handle(self, line: str, state: ParserState, parsed: Log):
        m = self.pattern.search(parsed.content)
        if m:
            tag = m.group("tag")
            msg = m.group("message")
            new_log = Log(parsed.timestamp, parsed.pid, parsed.level, msg)
            state.add_log(tag, new_log)


# === 파싱 함수 ===

def extract_log_parts(line: str) -> Optional[Log]:
    pattern = re.compile(
        r"(?P<timestamp>\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (?P<pid>\d+) (?P<level>[TDIEW]) (?P<content>.+)")
    m = pattern.match(line)
    if not m:
        return None
    timestamp = datetime.strptime(m.group("timestamp"), "%m-%d %H:%M:%S")
    pid = int(m.group("pid"))
    level = m.group("level")
    content = m.group("content")
    return Log(timestamp, pid, level, content)


def parse_line(line: str, state: ParserState, handlers: List[LogHandler]):
    parsed = extract_log_parts(line)
    if not parsed:
        return
    for handler in handlers:
        handler.handle(line, state, parsed)
