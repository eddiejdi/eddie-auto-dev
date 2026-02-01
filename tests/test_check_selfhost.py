from tools.deploy.check_selfhost import has_matching_runner


def test_has_matching_runner_true():
    data = {
        "runners": [
            {
                "id": 1,
                "name": "runner-1",
                "labels": [{"name": "self-hosted"}, {"name": "linux"}],
            },
            {"id": 2, "name": "runner-2", "labels": [{"name": "ubuntu"}]},
        ]
    }

    assert has_matching_runner(data, ["self-hosted"]) is True
    assert has_matching_runner(data, ["homelab"]) is False


def test_has_matching_runner_false_empty():
    assert has_matching_runner({}, ["self-hosted"]) is False


def test_has_matching_runner_with_homelab_label():
    data = {"runners": [{"id": 3, "name": "runner-3", "labels": [{"name": "homelab"}]}]}
    assert has_matching_runner(data, ["homelab"]) is True
