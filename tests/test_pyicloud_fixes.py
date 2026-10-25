"""Workarounds applied to pyicloud (icloud.py): 412 on SMS verification and SMS-only 2FA."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
import requests
from pyicloud import PyiCloudService
from pyicloud.exceptions import PyiCloudAPIResponseException

from hme_bitwarden import icloud
from hme_bitwarden.icloud import ICloudAccount


def apple_error(status: int, repair_session: bool = True, body=None) -> PyiCloudAPIResponseException:
    response = MagicMock(spec=requests.Response)
    response.status_code = status
    response.headers = {"X-Apple-Repair-Session-Token": "repair"} if repair_session else {}
    response.json.return_value = body if body is not None else {"securityCode": {"securityCodeLocked": False}}
    return PyiCloudAPIResponseException("Apple said no", status, response)


def install_with(monkeypatch, error: Exception) -> None:
    def validate(_self, _code):
        raise error

    monkeypatch.setattr(PyiCloudService, "_validate_sms_code", validate)
    icloud._accept_sms_code_with_repair_pending()


def test_patched_pyicloud_internals_still_exist():
    # A pyicloud upgrade that renames these would silently undo the workarounds.
    assert callable(PyiCloudService._validate_sms_code)
    assert callable(PyiCloudService._supports_trusted_device_bridge)
    assert PyiCloudService._validate_sms_code._hme_repair_pending_ok is True


def test_sms_code_answered_with_412_counts_as_accepted(monkeypatch):
    install_with(monkeypatch, apple_error(412))
    PyiCloudService._validate_sms_code(object(), "123456")  # does not raise


def test_412_whose_body_says_invalid_still_fails(monkeypatch):
    install_with(monkeypatch, apple_error(412, body={"securityCode": {"valid": False}}))
    with pytest.raises(PyiCloudAPIResponseException):
        PyiCloudService._validate_sms_code(object(), "123456")


def test_412_without_repair_session_still_fails(monkeypatch):
    install_with(monkeypatch, apple_error(412, repair_session=False))
    with pytest.raises(PyiCloudAPIResponseException):
        PyiCloudService._validate_sms_code(object(), "123456")


@pytest.mark.parametrize("status", [400, 401, 409, 423])
def test_other_sms_verification_errors_still_fail(monkeypatch, status):
    install_with(monkeypatch, apple_error(status))
    with pytest.raises(PyiCloudAPIResponseException):
        PyiCloudService._validate_sms_code(object(), "123456")


def test_non_json_412_counts_as_accepted(monkeypatch):
    response = MagicMock(spec=requests.Response)
    response.status_code = 412
    response.headers = {"X-Apple-Repair-Session-Token": "repair"}
    response.json.side_effect = ValueError("not json")
    install_with(monkeypatch, requests.HTTPError("412", response=response))
    PyiCloudService._validate_sms_code(object(), "123456")


def test_sms_2fa_skips_the_trusted_device_bridge(monkeypatch, tmp_path):
    monkeypatch.setattr(PyiCloudService, "_supports_trusted_device_bridge", lambda _self: True)
    ICloudAccount(tmp_path / "session", sms_2fa=True)
    assert PyiCloudService._supports_trusted_device_bridge(object()) is False


def test_bridge_left_alone_by_default(monkeypatch, tmp_path):
    monkeypatch.setattr(PyiCloudService, "_supports_trusted_device_bridge", lambda _self: True)
    ICloudAccount(tmp_path / "session")
    assert PyiCloudService._supports_trusted_device_bridge(object()) is True
