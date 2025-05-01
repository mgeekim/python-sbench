import re

import pytest

from simple_bench import LogPattern, GroupDefinition, ParserState, ScenarioHandler, GroupHandler, TaggedLogHandler, \
    parse_line


@pytest.fixture
def group_definitions():
    return {
        "Network": GroupDefinition(
            name="Network",
            start_pattern=re.compile(r"\[Network\] >>> Start network group"),
            end_pattern=re.compile(r"\[Network\] <<< End network group"),
            log_patterns=[LogPattern(name="NetworkLog", pattern=re.compile(r"\[Log:NETWORK\]"), tags=["NETWORK"])]
        ),
        "Database": GroupDefinition(
            name="Database",
            start_pattern=re.compile(r"\[Database\] >>> Start database group"),
            end_pattern=re.compile(r"\[Database\] <<< End database group"),
            log_patterns=[LogPattern(name="DatabaseLog", pattern=re.compile(r"\[Log:DB\]"), tags=["DB"])]
        ),
        "Authentication": GroupDefinition(
            name="Authentication",
            start_pattern=re.compile(r"\[Authentication\] >>> Start authentication group"),
            end_pattern=re.compile(r"\[Authentication\] <<< End authentication group"),
            log_patterns=[LogPattern(name="AuthLog", pattern=re.compile(r"\[Log:AUTH\]"), tags=["AUTH"])]
        )
    }


@pytest.fixture
def sample_logs():
    return [
        "04-30 10:00:00 1234 I [Scenario] LoginFlow",
        "04-30 10:00:01 1234 I [Network] >>> Start network group",
        "04-30 10:00:02 1234 I [Log:NETWORK] Sending request to /api/login",
        "04-30 10:00:03 1234 I [Network] >>> Start network group",  # Same group restarted before ending
        "04-30 10:00:04 1234 I [Log:NETWORK] Received response from /api/login",
        "04-30 10:00:05 1234 I [Authentication] >>> Start authentication group",
        "04-30 10:00:06 1234 I [Log:AUTH] User login initiated",
        "04-30 10:00:07 1234 I [Log:AUTH] Authentication successful",
        "04-30 10:00:08 1234 I [Authentication] <<< End authentication group",
        "04-30 10:00:09 1234 I [Network] <<< End network group",

        "04-30 10:01:00 1234 I [Scenario] SignupFlow",
        "04-30 10:01:01 1234 I [Network] >>> Start network group",
        "04-30 10:01:02 1234 I [Log:NETWORK] Sending request to /api/signup",
        "04-30 10:01:03 1234 I [Log:NETWORK] Waiting for response",
        "04-30 10:01:04 1234 I [Log:NETWORK] Received response from /api/signup",
        "04-30 10:01:05 1234 I [Authentication] >>> Start authentication group",
        "04-30 10:01:06 1234 I [Log:AUTH] User signup initiated",
        "04-30 10:01:07 1234 I [Log:AUTH] Authentication successful",
        "04-30 10:01:08 1234 I [Authentication] <<< End authentication group",
        "04-30 10:01:09 1234 I [Network] <<< End network group",
    ]


def test_parser_state_with_active_and_completed_groups(group_definitions, sample_logs):
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

    # Check that completed groups are correctly saved in the scenario's groups
    assert len(state.scenarios) == 2  # Two scenarios: LoginFlow and SignupFlow

    login_scenario = state.scenarios[0]
    assert len(login_scenario.groups) == 3  # Network, Authentication, and Network groups
    assert login_scenario.groups[0].name == 'Network'
    assert login_scenario.groups[1].name == 'Authentication'
    assert login_scenario.groups[2].name == 'Network'

    assert len(login_scenario.groups[0].logs) == 1  # Network logs
    assert len(login_scenario.groups[1].logs) == 2  # Authentication logs
    assert len(login_scenario.groups[2].logs) == 1  # Second Network logs

    signup_scenario = state.scenarios[1]
    assert len(signup_scenario.groups) == 2  # Network and Authentication groups
    assert signup_scenario.groups[0].name == 'Authentication'
    assert signup_scenario.groups[1].name == 'Network'
    assert len(signup_scenario.groups[0].logs) == 2  # Network logs
    assert len(signup_scenario.groups[1].logs) == 3  # Authentication logs
