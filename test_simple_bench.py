import re

import pytest

from simple_bench import (
    ParserState, GroupDefinition, LogPattern,
    ScenarioHandler, GroupHandler, TaggedLogHandler, parse_line
)


@pytest.fixture
def group_definitions():
    return {
        "Network": GroupDefinition(
            name="Network",
            start_pattern=re.compile(r"\[Network\] >>> Start network group"),
            end_pattern=re.compile(r"\[Network\] <<< End network group"),
            log_patterns=[
                LogPattern(name="NetworkLog", pattern=re.compile(r"\[Log:NETWORK\]"), tags=["NETWORK"])
            ]
        ),
        "Database": GroupDefinition(
            name="Database",
            start_pattern=re.compile(r"\[Database\] >>> Start database group"),
            end_pattern=re.compile(r"\[Database\] <<< End database group"),
            log_patterns=[
                LogPattern(name="DatabaseLog", pattern=re.compile(r"\[Log:DB\]"), tags=["DB"])
            ]
        )
    }


@pytest.fixture
def sample_logs():
    return [
        "04-30 10:00:00 1234 I [Scenario] LoginFlow",
        "04-30 10:00:01 1234 I [Network] >>> Start network group",
        "04-30 10:00:02 1234 I [Log:NETWORK] Sending request to /api/login",
        "04-30 10:00:03 1234 I [Database] >>> Start database group",
        "04-30 10:00:04 1234 I [Log:DB] Querying user table",
        "04-30 10:00:05 1234 I [Log:NETWORK] Received response from /api/login",
        "04-30 10:00:06 1234 I [Network] <<< End network group",
        "04-30 10:00:07 1234 I [Log:DB] Inserting login history",
        "04-30 10:00:08 1234 I [Database] <<< End database group",
        "04-30 10:01:00 1234 I [Scenario] SignupFlow",
        "04-30 10:01:01 1234 I [Network] >>> Start network group",
        "04-30 10:01:02 1234 I [Log:NETWORK] Sending request to /api/signup",
        "04-30 10:01:03 1234 I [Log:NETWORK] Waiting for response",
        "04-30 10:01:04 1234 I [Log:NETWORK] Received response from /api/signup",
        "04-30 10:01:05 1234 I [Network] <<< End network group",
        "04-30 10:02:00 1234 I [Scenario] ProfileUpdate",
        "04-30 10:02:01 1234 I [Database] >>> Start database group",
        "04-30 10:02:02 1234 I [Log:DB] Fetching user profile",
        "04-30 10:02:03 1234 I [Log:DB] Updating user info",
        "04-30 10:02:04 1234 I [Database] <<< End database group",
    ]


def test_parser_state_with_multiple_scenarios_and_groups(group_definitions, sample_logs):
    state = ParserState()
    state.set_definitions(group_definitions)

    handlers = [
        ScenarioHandler(),
        GroupHandler(group_definitions),
        TaggedLogHandler()
    ]

    for line in sample_logs:
        parse_line(line, state, handlers)
    state.finalize()

    scenarios = state.get_scenarios()
    assert len(scenarios) == 3

    login, signup, profile = scenarios

    # LoginFlow
    assert login.name == "LoginFlow"
    assert len(login.groups) == 2
    assert login.groups[0].name == "Network"
    assert login.groups[1].name == "Database"
    assert len(login.groups[0].logs) == 2  # NETWORK logs
    assert len(login.groups[1].logs) == 2  # DB logs

    # SignupFlow
    assert signup.name == "SignupFlow"
    assert len(signup.groups) == 1
    assert signup.groups[0].name == "Network"
    assert len(signup.groups[0].logs) == 3

    # ProfileUpdate
    assert profile.name == "ProfileUpdate"
    assert len(profile.groups) == 1
    assert profile.groups[0].name == "Database"
    assert len(profile.groups[0].logs) == 2
