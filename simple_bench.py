# Re-run the full implementation after code execution environment reset

# Re-import required modules
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict


# === Data Classes ===

@dataclass
class LogEntry:
    timestamp: datetime
    pid: int
    level: str
    raw: str
    type: Optional[str] = None
    content: Optional[str] = None


@dataclass
class LogGroup:
    name: str
    logs: List[LogEntry] = field(default_factory=list)


@dataclass
class ScenarioResult:
    scenario: str
    start_time: datetime
    pid: int
    level: str
    groups: List[LogGroup] = field(default_factory=list)
    logs: List[LogEntry] = field(default_factory=list)


@dataclass
class LogGroupDefinition:
    name: str
    start_pattern: re.Pattern
    end_pattern: re.Pattern
    log_types: List[str]


# === State Management ===

class LogState:
    def __init__(self):
        self.scenarios: List[ScenarioResult] = []
        self.current_scenario: Optional[ScenarioResult] = None
        self.group_stack: List[LogGroup] = []
        self.group_definitions: Dict[str, LogGroupDefinition] = {}

    def set_group_definitions(self, defs: Dict[str, LogGroupDefinition]):
        self.group_definitions = defs

    def start_scenario(self, name: str, entry: LogEntry):
        if self.current_scenario:
            self.scenarios.append(self.current_scenario)
        self.current_scenario = ScenarioResult(
            scenario=name,
            start_time=entry.timestamp,
            pid=entry.pid,
            level=entry.level
        )
        self.group_stack.clear()

    def start_group(self, name: str):
        self.group_stack.append(LogGroup(name=name))

    def end_group(self, name: str):
        for i in reversed(range(len(self.group_stack))):
            if self.group_stack[i].name == name:
                finished_group = self.group_stack.pop(i)
                if self.current_scenario:
                    self.current_scenario.groups.append(finished_group)
                return

    def add_log_to_groups(self, log: LogEntry, log_type: Optional[str]):
        if not log_type:
            return
        for group in self.group_stack:
            defn = self.group_definitions.get(group.name)
            if defn and log_type in defn.log_types:
                group.logs.append(log)

    def add_log_to_scenario(self, log: LogEntry):
        if self.current_scenario:
            self.current_scenario.logs.append(log)

    def finalize(self):
        if self.current_scenario:
            self.scenarios.append(self.current_scenario)
            self.current_scenario = None

    def get_all_results(self) -> List[ScenarioResult]:
        return self.scenarios


# === Handlers ===

class LogHandler:
    def handle(self, log: LogEntry, state: LogState):
        raise NotImplementedError


class ScenarioLogHandler(LogHandler):
    pattern = re.compile(r"\[Scenario\]\s+(?P<name>\w+)")

    def handle(self, log: LogEntry, state: LogState):
        match = self.pattern.search(log.raw)
        if match:
            state.start_scenario(match.group("name"), log)


class GroupLogHandler(LogHandler):
    def __init__(self, group_definitions: Dict[str, LogGroupDefinition]):
        self.group_definitions = group_definitions

    def handle(self, log: LogEntry, state: LogState):
        for defn in self.group_definitions.values():
            if defn.start_pattern.search(log.raw):
                state.start_group(defn.name)
            elif defn.end_pattern.search(log.raw):
                state.end_group(defn.name)


class LogEntryHandler(LogHandler):
    log_type_pattern = re.compile(r"\[Log:(?P<type>\w+)\]\s+(?P<content>.+)")

    def handle(self, log: LogEntry, state: LogState):
        match = self.log_type_pattern.search(log.raw)
        if match:
            log.type = match.group("type")
            log.content = match.group("content")
            state.add_log_to_groups(log, log.type)
        else:
            log.type = log.content = None
        state.add_log_to_scenario(log)


# === Parser ===

LOG_LINE_PATTERN = re.compile(
    r"(?P<timestamp>\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+"
    r"(?P<pid>\d+)\s+"
    r"(?P<level>[A-Z])\s+"
    r"(?P<content>.+)"
)


def parse_log_line(line: str) -> Optional[LogEntry]:
    match = LOG_LINE_PATTERN.match(line)
    if not match:
        return None
    try:
        timestamp = datetime.strptime(match.group("timestamp"), "%m-%d %H:%M:%S")
        return LogEntry(
            timestamp=timestamp,
            pid=int(match.group("pid")),
            level=match.group("level"),
            raw=line.strip(),
            content=match.group("content")
        )
    except Exception:
        return None


def parse_log(line: str, state: LogState, handlers: List[LogHandler]):
    entry = parse_log_line(line)
    if not entry:
        return
    for handler in handlers:
        handler.handle(entry, state)
