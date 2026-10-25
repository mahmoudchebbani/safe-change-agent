def test_list_files_finds_service(tools):
    files = tools.list_files("lib/services/claims")
    assert "lib/services/claims/infra/claims-events.ts" in files


def test_list_files_missing_directory_is_an_error(tools):
    result = tools.list_files("lib/services/payment")
    assert len(result) == 1
    assert result[0].startswith("Error:")
    assert "does not exist" in result[0]


def test_search_code_missing_path_is_an_error(tools):
    result = tools.search_code("refund", path_glob="lib/services/payment/*")
    assert result[0].startswith("Error:")


def test_read_file_refuses_path_outside_repo(tools):
    assert tools.read_file("../../etc/passwd").startswith("Error:")


def test_search_code_finds_event_constant(tools):
    matches = tools.search_code("CLAIM_ACCEPTED")
    assert any(m.startswith("lib/services/claims/infra/claims-events.ts:4:") for m in matches)
