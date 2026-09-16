"""Exercise the same module entry points used by Docker operators."""

import io
import json
import runpy
import sys

import pytest
from test_accounts import PASSWORD
from test_accounts import account_database as account_database
from test_document_persistence import document_store as document_store


@pytest.mark.parametrize(
    "module,args,expected,status",
    [
        (
            "app.accounts.cli",
            ["provision", "--login", "", "--password-stdin"],
            "invalid_input",
            1,
        ),
        ("app.diagnostics", ["audit"], {"events": [], "next_cursor": None}, 0),
        ("app.documents.retention_cli", ["show"], None, 0),
        (
            "app.storage.quota_cli",
            ["show", "--login", "missing"],
            {"error": "quota_command_failed"},
            1,
        ),
        (
            "app.storage.maintenance",
            ["inventory"],
            {"examined": 0, "unknown_entries": 0, "truncated": False},
            0,
        ),
        (
            "app.maintenance",
            ["--unknown"],
            {"error": "invalid_maintenance_configuration"},
            2,
        ),
    ],
)
def test_operator_exit_status_and_safe_output(
    module, args, expected, status, monkeypatch, capsys
):
    monkeypatch.setattr(sys, "argv", [module, *args])
    monkeypatch.setattr(sys, "stdin", io.StringIO(PASSWORD))
    with pytest.raises(SystemExit) as result:
        runpy.run_module(module, run_name="__main__")
    assert result.value.code == status
    output = capsys.readouterr()
    assert PASSWORD not in output.out + output.err
    if module == "app.accounts.cli":
        assert output.err.strip() == expected
        assert output.out == ""
    else:
        body = json.loads(output.out)
        if expected is not None:
            assert body == expected
        else:
            assert "keep_latest" in body


def test_dispatcher_entrypoint_waits_when_idle_without_noisy_logs(monkeypatch, capsys):
    def stop(seconds):
        assert seconds == 5
        raise InterruptedError("test shutdown")

    monkeypatch.setattr("time.sleep", stop)
    with pytest.raises(InterruptedError, match="test shutdown"):
        runpy.run_module("app.jobs.dispatcher", run_name="__main__")
    assert capsys.readouterr().out == ""
