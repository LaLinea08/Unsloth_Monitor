from unsloth_monitor.settings import Settings, load_settings, save_settings


def test_roundtrip_and_no_credentials(tmp_path):
    path = tmp_path / "settings.json"
    settings = Settings("http://127.0.0.1:9000/v1", 10)
    save_settings(path, settings)
    assert load_settings(path) == settings
    assert "token" not in path.read_text()


def test_corrupt_or_unsafe_preferences_fall_back(tmp_path):
    path = tmp_path / "settings.json"
    for data in ('{', '[]', '{"base_url":"http://evil.example/v1"}', '{"interval":true}'):
        path.write_text(data)
        assert load_settings(path) == Settings()
