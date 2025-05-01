import re

from simple_bench import LogState, LogGroupDefinition, ScenarioLogHandler, GroupLogHandler, LogEntryHandler, parse_log

extended_sample_logs = [
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

group_definitions = {
    "Network": LogGroupDefinition(
        name="Network",
        start_pattern=re.compile(r"\[Network\] >>> Start network group"),
        end_pattern=re.compile(r"\[Network\] <<< End network group"),
        log_types=["NETWORK"]
    ),
    "Database": LogGroupDefinition(
        name="Database",
        start_pattern=re.compile(r"\[Database\] >>> Start database group"),
        end_pattern=re.compile(r"\[Database\] <<< End database group"),
        log_types=["DB"]
    )
}


def test_extended_log_parsing():
    state = LogState()
    state.set_group_definitions(group_definitions)
    handlers = [
        ScenarioLogHandler(),
        GroupLogHandler(group_definitions),
        LogEntryHandler()
    ]
    for line in extended_sample_logs:
        parse_log(line, state, handlers)
    state.finalize()

    results = state.get_all_results()
    assert len(results) == 3

    login = results[0]
    signup = results[1]
    profile = results[2]

    assert login.scenario == "LoginFlow"
    assert len(login.groups) == 2
    assert len(login.groups[0].logs) == 2
    assert len(login.groups[1].logs) == 2

    assert signup.scenario == "SignupFlow"
    assert len(signup.groups) == 1
    assert len(signup.groups[0].logs) == 3

    assert profile.scenario == "ProfileUpdate"
    assert len(profile.groups) == 1
    assert len(profile.groups[0].logs) == 2
