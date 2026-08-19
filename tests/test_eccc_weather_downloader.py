import os
import tempfile
import pytest
import urllib.request
from unittest import mock

from scripts.download_eccc_weather import (
    calculate_sha256,
    validate_csv_header,
    _resolve_dest_path,
    download_url,
)


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as tmp:
        yield tmp


def test_calculate_sha256(temp_dir):
    temp_file = os.path.join(temp_dir, "test.txt")
    with open(temp_file, "wb") as f:
        f.write(b"test data")
    expected = "916f0027a575074ce72a331777c3478d6513f786a591bd892da1a577bf2335f9"
    assert calculate_sha256(temp_file) == expected


def test_validate_csv_header():
    assert validate_csv_header(b"Header1,Header2\nvalue1,value2") is True
    assert validate_csv_header(b"<!DOCTYPE html><html></html>") is False
    assert validate_csv_header(b"<html lang='en'></html>") is False


def test_resolve_dest_path(temp_dir):
    # Case 1: dest_path is a file path
    file_dest = os.path.join(temp_dir, "output.csv")
    assert _resolve_dest_path(file_dest, "http://example.com/data", {}) == file_dest

    # Case 2: dest_path is a directory and Content-Disposition specifies filename
    dir_dest = os.path.join(temp_dir, "subdir")
    os.makedirs(dir_dest, exist_ok=True)
    headers = {"Content-Disposition": 'attachment; filename="weather_2009.csv"'}
    res = _resolve_dest_path(dir_dest, "http://example.com/data", headers)
    assert res == os.path.join(dir_dest, "weather_2009.csv")

    # Case 3: dest_path is a directory and no Content-Disposition header
    res_no_cd = _resolve_dest_path(dir_dest, "http://example.com/bulk_data_e.html?id=1", {})
    assert res_no_cd == os.path.join(dir_dest, "weather_data.csv")


@mock.patch("urllib.request.urlopen")
def test_download_url_success(mock_urlopen, temp_dir):
    dest_path = os.path.join(temp_dir, "test.csv")
    mock_response = mock.Mock()
    mock_response.headers = {"Content-Type": "text/csv"}
    mock_response.read.return_value = b"Date/Time,Temp\n2009-01-01,1.5"
    mock_urlopen.return_value.__enter__.return_value = mock_response

    final_dest, size, sha256 = download_url("http://example.com/weather.csv", dest_path, retries=1)
    assert final_dest == dest_path
    assert size == len(b"Date/Time,Temp\n2009-01-01,1.5")
    assert os.path.exists(dest_path)


@mock.patch("urllib.request.urlopen")
def test_download_url_rejects_html(mock_urlopen, temp_dir):
    dest_path = os.path.join(temp_dir, "test.csv")
    mock_response = mock.Mock()
    mock_response.headers = {"Content-Type": "text/html"}
    mock_response.read.return_value = b"<!DOCTYPE html><html>Error</html>"
    mock_urlopen.return_value.__enter__.return_value = mock_response

    with pytest.raises(
        RuntimeError, match="Download failed after exhausting all retries."
    ) as exc_info:
        download_url("http://example.com/weather.csv", dest_path, retries=1)
    assert isinstance(exc_info.value.__cause__, ValueError)
    assert "HTML response received instead of data." in str(exc_info.value.__cause__)
    # Ensure no file was written
    assert not os.path.exists(dest_path)


@mock.patch("urllib.request.urlopen")
def test_download_url_retry_exhaustion(mock_urlopen, temp_dir):
    dest_path = os.path.join(temp_dir, "test.csv")
    mock_urlopen.side_effect = Exception("Connection timed out")

    # We mock time.sleep to run quickly
    with mock.patch("time.sleep"):
        with pytest.raises(RuntimeError, match="Download failed after exhausting all retries."):
            download_url("http://example.com/weather.csv", dest_path, retries=2)
    assert not os.path.exists(dest_path)
