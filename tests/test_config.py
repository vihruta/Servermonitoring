from pathlib import Path

from config import load_monitoring_config


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_example_monitoring_config_can_be_loaded(tmp_path):
    example_config = PROJECT_ROOT / "config.example.yaml"
    test_config = tmp_path / "config.yaml"
    test_config.write_text(
        example_config.read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    (
        interval,
        cpu_temperature,
        cpu_usage,
        ram,
        disks,
        monitored_containers,
    ) = load_monitoring_config(tmp_path)

    assert interval == 60
    assert cpu_temperature.warning == 85
    assert cpu_usage.warning == 85
    assert ram.warning == 85
    assert disks["temperature"].warning == 65
    assert disks["usage"].warning == 80
    assert "vaultwarden" in monitored_containers
