import re

import pytest

from simple_bench import (
    LogPattern, GroupDefinition, LogParser
)


@pytest.fixture
def log_patterns():
    return [
        LogPattern(name="NetworkLog", pattern=re.compile(r"\[Log:NETWORK\]"), tags=["NETWORK"]),
        LogPattern(name="DatabaseLog", pattern=re.compile(r"\[Log:DB\]"), tags=["DB"]),
        LogPattern(name="UILog", pattern=re.compile(r"\[Log:UI\]"), tags=["UI"]),
    ]


@pytest.fixture
def group_definitions():
    return [
        GroupDefinition(
            name="Network",
            start_pattern=re.compile(r"\[Network\] >>> Start network group"),
            end_pattern=re.compile(r"\[Network\] <<< End network group"),
            log_pattern_names=["NetworkLog", "UILog"]
        ),
        GroupDefinition(
            name="Database",
            start_pattern=re.compile(r"\[Database\] >>> Start database group"),
            end_pattern=re.compile(r"\[Database\] <<< End database group"),
            log_pattern_names=["DatabaseLog"]
        ),
        GroupDefinition(
            name="UI",
            start_pattern=re.compile(r"\[UI\] >>> Start UI group"),
            end_pattern=re.compile(r"\[UI\] <<< End UI group"),
            log_pattern_names=["UILog"]
        )
    ]


@pytest.fixture
def sample_logs():
    return [
        # Scenario: LoginFlow
        "04-30 10:00:00 1234 I [Scenario] LoginFlow",
        "04-30 10:00:01 1234 I [Network] >>> Start network group",
        "04-30 10:00:02 1234 I [Log:NETWORK] Request to /login",
        "04-30 10:00:03 1234 I [Log:UNKNOWN] This log is ignored",
        "04-30 10:00:04 1234 I [Database] >>> Start database group",
        "04-30 10:00:05 1234 I [Log:DB] Select user from db",
        "04-30 10:00:06 1234 I [Log:UNDEFINED] Unmatched log message",
        "04-30 10:00:07 1234 I [Network] <<< End network group",
        "04-30 10:00:08 1234 I [Log:DB] Insert login history",
        "04-30 10:00:09 1234 I [Database] <<< End database group",
        "04-30 10:00:10 1234 I [UI] >>> Start UI group",
        "04-30 10:00:11 1234 I [Log:UI] Render login page",
        "04-30 10:00:12 1234 I [UI] <<< End UI group",

        "04-30 10:01:00 1234 I [Scenario] SignupFlow",
        "04-30 10:01:01 1234 I [Network] >>> Start network group",
        "04-30 10:01:02 1234 I [Log:NETWORK] Request to /signup",

        "04-30 10:01:03 1234 I [Log:UNKNOWN] This log is also ignored",
        "04-30 10:01:04 1234 I [Network] >>> Start network group",
        "04-30 10:01:05 1234 I [Log:NETWORK] Retry request to /signup",
        "04-30 10:01:06 1234 I [Network] <<< End network group",
        "04-30 10:01:07 1234 I [Log:NETWORK] Final response",
        "04-30 10:01:08 1234 I [Network] <<< End network group",

        "04-30 10:02:00 1234 I [Scenario] ProfileUpdate",
        "04-30 10:02:01 1234 I [Database] >>> Start database group",
        "04-30 10:02:02 1234 I [Log:DB] Load user profile",
        "04-30 10:02:03 1234 I [Log:DB] Update user info",
        "04-30 10:02:03 1234 I [Log:UNDEFINED] This should be ignored as well",
        "04-30 10:02:04 1234 I [Database] <<< End database group",
    ]


def test_log_parser_parses_scenarios_correctly(group_definitions, log_patterns, sample_logs):
    parser = LogParser(group_definitions, log_patterns)
    parser.parse_lines(sample_logs)
    scenarios = parser.get_scenarios()

    assert len(scenarios) == 3

    login = scenarios[0]
    signup = scenarios[1]
    profile = scenarios[2]

    # LoginFlow
    assert login.name == "LoginFlow"
    assert len(login.groups) == 3
    assert login.groups[0].name == "Network"
    assert login.groups[1].name == "Database"
    assert login.groups[2].name == "UI"
    assert len(login.groups[0].logs) == 1
    assert len(login.groups[1].logs) == 2
    assert len(login.groups[2].logs) == 1

    # SignupFlow
    assert signup.name == "SignupFlow"
    assert len(signup.groups) == 2
    assert all(group.name == "Network" for group in signup.groups)
    assert len(signup.groups[0].logs) == 1
    assert len(signup.groups[1].logs) == 1

    # ProfileUpdate
    assert profile.name == "ProfileUpdate"
    assert len(profile.groups) == 1
    assert profile.groups[0].name == "Database"
    assert len(profile.groups[0].logs) == 2
