from unittest.mock import patch
import pytest
from app.security import UnsafeURL, validate_url, normalize_url, same_site

@pytest.mark.parametrize('url',[
  'file:///etc/passwd','ftp://example.com','http://127.0.0.1','http://192.168.1.1',
  'http://169.254.169.254/latest/meta-data/','http://user:pass@example.com',
  'https://example.com:9000','http://[::1]','javascript:alert(1)'
])
def test_reject_unsafe_urls(url,monkeypatch):
    monkeypatch.delenv('ALLOW_PRIVATE_NETWORK',raising=False)
    with pytest.raises(UnsafeURL):validate_url(url)

def test_url_normalizer():
    assert normalize_url('https://example.com/a/?utm_source=x&lang=en#top')=='https://example.com/a?lang=en'
    assert same_site('https://example.com/a','https://example.com/')
    assert not same_site('https://notexample.com','https://example.com')

def test_public_host_validation_without_network():
    assert validate_url('https://example.com/path#anchor',resolve=False)=='https://example.com/path'
