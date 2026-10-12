from unittest import mock

from src.core.hardware.raspberry_pi_monitor import RaspberryPiMonitor
from src.core.hardware.throttle import parse_throttled


def test_clean():
    f = parse_throttled("throttled=0x0\n")
    assert not (f.undervoltage or f.throttled or f.freq_capped)


def test_current_and_past_bits():
    f = parse_throttled("throttled=0x50005")
    assert f.undervoltage and f.throttled and not f.freq_capped
    assert f.undervoltage_occurred and f.throttled_occurred
    assert not f.freq_capped_occurred and f.raw_hex == "0x50005"


def test_malformed_returns_none():
    for bad in ("", "garbage", "throttled=zz", "throttled="):
        assert parse_throttled(bad) is None


def test_monitor_survives_missing_or_bad_vcgencmd():
    mon = RaspberryPiMonitor()
    mon._vcgencmd_available = True
    with mock.patch("subprocess.run", side_effect=FileNotFoundError):
        assert mon.get_throttle_flags().raw_hex == "0x0"
    ok = mock.Mock(returncode=0, stdout="throttled=0x1\n")
    with mock.patch("subprocess.run", return_value=ok):
        assert mon.get_throttle_flags().undervoltage
    bad = mock.Mock(returncode=0, stdout="oops")
    with mock.patch("subprocess.run", return_value=bad):
        assert mon.get_throttle_flags().raw_hex == "0x0"
