from deye.cli import main

def test_status(capsys):
    assert main(["status"]) == 0
    assert "deye_version" in capsys.readouterr().out

def test_capabilities(capsys):
    assert main(["capabilities"]) == 0
    assert "search" in capsys.readouterr().out

def test_connectors(capsys):
    assert main(["connectors"]) == 0
    out = capsys.readouterr().out
    assert "web_fetch" in out and "search_duckduckgo" in out

def test_doctor_surfaces(capsys):
    assert main(["doctor", "--surfaces"]) == 0
    assert "Claude Code CLI" in capsys.readouterr().out
