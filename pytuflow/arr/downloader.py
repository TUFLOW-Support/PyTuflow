"""HTTP downloader used by :mod:`pytuflow.arr` to fetch data from the ARR Data Hub API.

Ported from the legacy ``ARR_legacy/downloader.py``. Two implementations are provided:

* :class:`DownloaderQGIS` - uses ``QgsNetworkAccessManager`` when running inside QGIS.
  This automatically inherits any proxy settings the user has configured in QGIS, so
  users don't need to configure proxy settings a second time for this tool.
* :class:`DownloaderRequests` - falls back to the ``requests`` library when QGIS
  libraries are not available (i.e. running outside of QGIS).

:class:`Downloader` is a factory - instantiating it will automatically return the
correct subclass based on whether QGIS libraries can be imported.
"""

import logging
from time import sleep
from typing import Optional

try:
    from qgis.core import QgsNetworkAccessManager
    from qgis.PyQt.QtNetwork import QNetworkRequest
    from qgis.PyQt.QtCore import QUrl, QSettings, QEventLoop
except ImportError:
    QgsNetworkAccessManager = None
    QNetworkRequest = None
    QUrl = None
    QSettings = None
    QEventLoop = None

import requests

logger = logging.getLogger('pytuflow.arr')

# Qt version compatibility - these attribute/enum locations changed between PyQt5 and PyQt6.
try:
    from qgis.PyQt.QtCore import QEventLoop as _QEventLoop
    QT_EVENT_LOOP_EXCLUDE_USER_INPUT_EVENTS = _QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents
except (ImportError, AttributeError):
    try:
        QT_EVENT_LOOP_EXCLUDE_USER_INPUT_EVENTS = QEventLoop.ExcludeUserInputEvents
    except AttributeError:
        QT_EVENT_LOOP_EXCLUDE_USER_INPUT_EVENTS = None

try:
    from qgis.PyQt.QtNetwork import QNetworkRequest as _QNetworkRequest
    QT_NETWORK_REQUEST_HTTP_STATUS_CODE_ATTRIBUTE = _QNetworkRequest.Attribute.HttpStatusCodeAttribute
except (ImportError, AttributeError):
    try:
        QT_NETWORK_REQUEST_HTTP_STATUS_CODE_ATTRIBUTE = QNetworkRequest.HttpStatusCodeAttribute
    except AttributeError:
        QT_NETWORK_REQUEST_HTTP_STATUS_CODE_ATTRIBUTE = None


class Downloader:
    """Downloader factory. Uses QGIS's ``QgsNetworkAccessManager`` (which inherits QGIS's
    configured proxy settings) when available, otherwise falls back to ``requests``.
    """

    def __new__(cls, url: str, headers: Optional[dict] = None):
        if Downloader.has_qgis_libs():
            cls = DownloaderQGIS
        else:
            cls = DownloaderRequests
        return object.__new__(cls)

    def __init__(self, url: str, headers: Optional[dict] = None) -> None:
        self.url = url
        self.headers = {} if headers is None else headers
        self.data = None
        self.ret_code = None
        self.error_string = ''

    @staticmethod
    def has_qgis_libs() -> bool:
        """Returns whether the QGIS/Qt network libraries required to use
        :class:`DownloaderQGIS` are importable."""
        return QgsNetworkAccessManager is not None and QNetworkRequest is not None and QUrl is not None

    def type(self) -> str:
        """Returns a human-readable name for which downloader implementation is being used."""
        raise NotImplementedError

    def ok(self) -> bool:
        """Returns whether the download was successful (HTTP 200)."""
        return self.ret_code == 200

    def download(self, **kwargs) -> None:
        """Performs the download, populating ``self.data``, ``self.ret_code``, and
        ``self.error_string``."""
        raise NotImplementedError


class DownloaderQGIS(Downloader):
    """Downloader implementation that uses QGIS's ``QgsNetworkAccessManager``, which
    inherits any proxy settings configured within QGIS."""

    def type(self) -> str:
        return 'QGIS'

    def download(self, retry_count: int = 5, retry_interval=range(5, 30, 5), validator=None) -> None:
        old_user_agent = None
        netman = QgsNetworkAccessManager.instance()
        req = QNetworkRequest(QUrl(self.url))
        for k, v in self.headers.items():
            req.setRawHeader(k.encode(), v.encode())
            if k == 'User-Agent':
                if QSettings().contains('/qgis/networkAndProxy/userAgent'):
                    old_user_agent = QSettings().value('/qgis/networkAndProxy/userAgent')
                QSettings().setValue('/qgis/networkAndProxy/userAgent', v)
        try_count = -1
        retry_interval = list(retry_interval)
        data = bytearray(b'')
        reply = None
        while True:
            try_count += 1
            reply = netman.get(req)
            evloop = QEventLoop()
            reply.finished.connect(evloop.quit)
            evloop.exec(QT_EVENT_LOOP_EXCLUDE_USER_INPUT_EVENTS)
            if old_user_agent:
                QSettings().setValue('/qgis/networkAndProxy/userAgent', old_user_agent)
            else:
                QSettings().remove('/qgis/networkAndProxy/userAgent')
            self.ret_code = reply.attribute(QT_NETWORK_REQUEST_HTTP_STATUS_CODE_ATTRIBUTE)
            if self.ret_code == 200:
                data = bytearray(reply.readAll())
            if self.ret_code != 200:
                logger.info('HTTP get failed with code: %s', self.ret_code)
                if try_count < retry_count:
                    t = retry_interval[try_count]
                    logger.info('Trying again in %s seconds...', t)
                    sleep(t)
                    logger.info('Retry attempt #%s', try_count + 1)
                    continue
                self.error_string = reply.errorString()
            elif validator is not None and not validator(data):
                if try_count < retry_count:
                    t = retry_interval[try_count]
                    logger.info('Trying again in %s seconds...', t)
                    sleep(t)
                    logger.info('Retry attempt #%s', try_count + 1)
                    QgsNetworkAccessManager.instance().cache().remove(QUrl(self.url))
                    continue
                self.ret_code = None
                self.error_string = 'Downloaded data is invalid or incomplete.'
            break
        if self.error_string:
            return
        content_type = reply.rawHeader(b'Content-Type')
        if b'zip' not in content_type:
            self.data = data.decode('utf-8')
        else:
            self.data = data


class DownloaderRequests(Downloader):
    """Downloader implementation using the ``requests`` library. Used when running
    outside of QGIS (proxy settings, if required, must be configured via the usual
    ``requests``/environment-variable mechanisms)."""

    def type(self) -> str:
        return 'Requests'

    def download(self, timeout: int = 20, **kwargs) -> None:
        r = requests.get(self.url, headers=self.headers, timeout=timeout)
        self.ret_code = r.status_code
        if not r.ok:
            self.error_string = r.text
            return
        content_type = r.headers.get('content-type', '')
        if 'zip' not in content_type and isinstance(r.content, bytes):
            self.data = r.content.decode('utf-8')
        else:
            self.data = r.content
