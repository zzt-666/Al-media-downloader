"""
Runtime patch for yt-dlp DouyinIE.

Official yt-dlp still hits HTTP 403 on Douyin's aweme/detail API
("Fresh cookies are needed"). Upstream PR #17826 adds
x-secsdk-web-signature; we apply the same approach at runtime so
Bilibili/YouTube keep using the installed yt-dlp release unchanged.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
import urllib.parse
import uuid

from yt_dlp.extractor.tiktok import DouyinIE
from yt_dlp.utils import ExtractorError
from yt_dlp.utils.traversal import traverse_obj

logger = logging.getLogger(__name__)

_APPLIED = False

_SEC_SALT = "A96D855A08C0A9707F8BEF0D9A527E4E"
_REQUIRED_COOKIES = (
    "passport_csrf_token",
    "ttwid",
)
_AID = 6383  # aweme_general


def _get_ttwid(self):
    self._request_webpage(
        f"{self._WEBPAGE_HOST}ttwid/register",
        None,
        data=json.dumps(
            {
                "aid": _AID,
                "service": "www.douyin.com",
            }
        ).encode(),
        headers={"content-type": "application/json"},
    )
    cookie = self._get_cookies(self._WEBPAGE_HOST).get("ttwid")
    return cookie.value if cookie else None


def _check_and_get_required_cookies(self):
    csrf = getattr(self, "_douyin_csrf", None) or uuid.uuid4().hex
    self._douyin_csrf = csrf
    for rc in _REQUIRED_COOKIES:
        if self._get_cookies(self._WEBPAGE_HOST).get(rc):
            continue
        if rc == "ttwid":
            cookie = _get_ttwid(self)
        else:
            cookie = csrf
        if not cookie:
            raise ExtractorError("Unable to generate required cookies")
        self._set_cookie(".douyin.com", rc, cookie)


def _get_uifid(self):
    uifid_cookie_names = (
        "uifid",
        "uifid_temp",
        "uifidtemp",
        "UIFID",
        "UIFID_TEMP",
        "UIFIDTEMP",
    )
    uifid = traverse_obj(
        self._get_cookies(self._WEBPAGE_HOST),
        (uifid_cookie_names, "value"),
        get_all=False,
    )
    if not uifid:
        urlh = self._request_webpage(self._WEBPAGE_HOST, None)
        return urlh.headers.get("x-tt-trace-host")
    return uifid


def _sign_query(self, query):
    uifid = _get_uifid(self)
    timestamp = str(int(time.time()))
    query = {**query, "uifid": uifid, "timestamp": timestamp}
    encoded_query = urllib.parse.urlencode(query)
    secsdk_signature = hashlib.md5(
        f"{uifid}_{timestamp}_{_SEC_SALT}_{encoded_query}".encode()
    ).hexdigest()
    return {**query, "x-secsdk-web-signature": secsdk_signature}


def _get_aweme_detail(self, video_id):
    return traverse_obj(
        self._download_json(
            "https://www.douyin.com/aweme/v1/web/aweme/detail/",
            video_id,
            "Downloading web detail JSON",
            "Failed to download web detail JSON",
            query=_sign_query(self, {"aweme_id": video_id, "aid": _AID}),
            fatal=False,
        ),
        ("aweme_detail", {dict}),
    )


def _real_extract_patched(self, url):
    video_id = self._match_id(url)
    _check_and_get_required_cookies(self)
    aweme_detail = _get_aweme_detail(self, video_id)
    if not aweme_detail:
        raise ExtractorError(
            "Fresh cookies (not necessarily logged in) are needed",
            expected=not self._get_cookies(self._WEBPAGE_HOST).get("s_v_web_id"),
        )
    return {
        **self._parse_aweme_video_app(aweme_detail),
        "http_headers": {"Referer": self._WEBPAGE_HOST},
    }


def apply_douyin_patch() -> None:
    global _APPLIED
    if _APPLIED:
        return
    DouyinIE._real_extract = _real_extract_patched  # type: ignore[method-assign]
    _APPLIED = True
    logger.info("Applied Douyin aweme/detail signature patch")
