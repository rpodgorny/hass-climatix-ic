"""Headless Climatix IC client (blocking; runs in an executor).

No browser: Azure B2C login + TOTP over requests, then reads datapoints from the
RemoteWeb `getDp` JSON endpoint. Nothing here imports Home Assistant, so it can be
unit-tested and reused standalone.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import struct
import time

import requests

WWW = "https://www.climatixic.com"
B2C = "https://login.climatixic.com"
EXTLOGIN = f"{WWW}/Account/ExternalLogin?provider=climatixid&locale=en-US&username="

# known-stable RemoteWeb id, only used if LaunchWebAccess stops advertising it
DEFAULT_REMOTE = "4d2424c8-6e1d-4680-9ba2-b9a53329faa4"


class ClimatixError(Exception):
    """Base error."""


class AuthError(ClimatixError):
    """Bad credentials or TOTP - not retryable without new input."""


class SessionExpired(ClimatixError):
    """The RemoteWeb/app session went stale; re-login and retry."""


def totp(secret: str) -> str:
    """Current 6-digit TOTP for a base32 secret."""
    # wait out the tail of a window so the code can't expire mid-login
    if time.time() % 30 > 27:
        time.sleep(4)
    key = base64.b32decode(secret)
    h = hmac.new(key, struct.pack(">Q", int(time.time() // 30)), hashlib.sha1).digest()
    o = h[-1] & 15
    return str((struct.unpack(">I", h[o : o + 4])[0] & 0x7FFFFFFF) % 10**6).zfill(6)


def describe(caption: str, value: str | None, unit: str) -> dict:
    """Map a datapoint to a HA entity descriptor from its unit and a sample value."""
    if unit:
        return {
            "component": "sensor",
            "unit": unit,
            "temperature": unit == "°C",
            "numeric": True,
        }
    if value in ("On", "Off"):
        return {"component": "binary_sensor"}
    return {"component": "sensor", "numeric": False}  # enum / status text


class ClimatixClient:
    """One plant's worth of Climatix access. Not thread-safe."""

    def __init__(self, user: str, passwd: str, totp_secret: str, plant_id: str | None = None):
        self.user = user
        self.passwd = passwd
        self.totp_secret = totp_secret
        self.plant_id = plant_id
        self.s: requests.Session | None = None
        self.base: str | None = None
        self.sid: str | None = None

    # --- login -------------------------------------------------------------

    @staticmethod
    def _settings(html: str):
        m = re.search(r"var SETTINGS = (\{.*?\});", html, re.S)
        return json.loads(m.group(1)) if m else None

    def _selfasserted(self, st, body):
        t, p = st["hosts"]["tenant"], st["hosts"]["policy"]
        r = self.s.post(
            f"{B2C}{t}/SelfAsserted?tx={st['transId']}&p={p}",
            data={"request_type": "RESPONSE", **body},
            headers={"X-CSRF-TOKEN": st["csrf"], "X-Requested-With": "XMLHttpRequest"},
        )
        r.raise_for_status()

    def _confirmed(self, st) -> str:
        t, p = st["hosts"]["tenant"], st["hosts"]["policy"]
        r = self.s.get(
            f"{B2C}{t}/api/{st['api']}/confirmed"
            f"?rememberMe=false&csrf_token={st['csrf']}&tx={st['transId']}&p={p}"
        )
        r.raise_for_status()
        return r.text

    def login(self) -> None:
        """Authenticate to the app (app cookie). Does not open a plant session.

        Raises AuthError for bad credentials/TOTP.
        """
        s = requests.Session()
        s.headers["User-Agent"] = "Mozilla/5.0"
        # warmup: ASP.NET_SessionId must exist before ExternalLogin, else the handoff is silently dropped
        s.get(f"{WWW}/")
        self.s = s
        st = self._settings(s.get(EXTLOGIN).text)
        if not st:
            raise ClimatixError("no B2C SETTINGS (login page changed?)")
        self._selfasserted(st, {"email": self.user, "password": self.passwd})
        st = self._settings(self._confirmed(st))
        if not st:
            raise AuthError("credentials rejected")
        try:
            code = totp(self.totp_secret)
        except Exception as e:  # bad base32 secret
            raise AuthError(f"invalid TOTP secret: {e}") from e
        self._selfasserted(st, {"otpCode": code})
        html = self._confirmed(st)
        idt = self._input_value(html, "id_token")
        if not idt:
            raise AuthError("TOTP rejected")
        s.post(f"{WWW}/signin-climatixid", data={"id_token": idt, "state": self._input_value(html, "state")})
        if ".AspNet.ApplicationCookie" not in [c.name for c in s.cookies]:
            raise ClimatixError("id_token exchange failed")

    @staticmethod
    def _input_value(html: str, name: str):
        m = re.search(name + r"['\"][^>]*\bvalue=['\"]([^'\"]+)", html)
        return m.group(1) if m else None

    # --- plants ------------------------------------------------------------

    def list_plants(self) -> list[dict]:
        """Plants this account can access: [{'id', 'name'}]. Requires login()."""
        me = self.s.get(f"{WWW}/clx/users/me").json()
        tenant = me.get("preferredTenantId")
        ids = [pid for res in me.get("assignedResources", []) for pid in res.get("Plants", {})]
        plants = []
        for pid in ids:
            name = pid
            try:
                d = self.s.get(f"{WWW}/clx/plants/{pid}?tenantId={tenant}&locale=en-US").json()
                name = d.get("name") or pid
            except Exception:  # name is cosmetic; fall back to id
                pass
            plants.append({"id": pid, "name": name})
        return plants

    # --- plant session -----------------------------------------------------

    def _open_remoteweb(self) -> None:
        r = self.s.get(
            f"{WWW}/Site/Site/LaunchWebAccess/{self.plant_id}/?inFrame=true&openEnergyIndicatorPage=false"
        )
        m = re.search(r"/Site/RemoteWeb/([0-9a-f-]{36})/web", r.text)
        remote = m.group(1) if m else DEFAULT_REMOTE
        fields = dict(re.findall(r'<input[^>]*name="([^"]+)"[^>]*value="([^"]*)"', r.text))
        self.base = f"{WWW}/Site/RemoteWeb/{remote}/web"
        self.s.post(self.base + "/", data=fields)  # proxySession
        self.s.get(self.base + "/")
        self.s.get(self.base + "/main.app")  # sets SessionId cookie
        self.sid = self.s.cookies.get("SessionId")
        if not self.sid:
            raise ClimatixError("no RemoteWeb SessionId")

    def _ensure(self) -> None:
        if self.s is None:
            self.login()
        if self.base is None:
            self._open_remoteweb()

    def _ajax(self, service: str, **params):
        q = "".join(f"{k}={v}&" for k, v in params.items())
        r = self.s.get(
            f"{self.base}/ajax.app?SessionId={self.sid}&service={service}&{q}_={int(time.time() * 1000)}",
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        if r.status_code == 401 or "application/json" not in r.headers.get("content-type", ""):
            raise SessionExpired(f"{service}: status {r.status_code}")
        return r.json()

    def _entry_page_id(self) -> str:
        html = self.s.get(self.base + "/main.app").text
        m = re.search(r'value="(\d+)"\s+id="plantItemId"', html)
        if not m:
            raise ClimatixError("could not find entry plantItemId in main.app")
        return m.group(1)

    def get_dp(self, pid: int) -> tuple[str | None, str]:
        """(value, unit). value is a stripped string, or None when there is no reading."""
        d = self._ajax("getDp", plantItemId=pid)
        v = d.get("value", "").strip()
        return (None if v in ("----", "---", "") else v), d.get("unit", "")

    # --- high level --------------------------------------------------------

    def discover(self) -> list[dict]:
        """Enumerate the plant's overview datapoints as HA entity descriptors.

        [{'pid', 'name', 'component', 'unit'?, 'temperature'?, 'numeric'?}]
        """
        self._ensure()
        data = self._ajax("getDiagramPage", plantItemId=self._entry_page_id())
        rows, seen = [], set()
        for e in data["DIE_Dp_Ary"]:
            dp = e["Dp_Obj"]
            pid = dp["PlantItemId"]
            if pid in seen:
                continue
            seen.add(pid)
            caption = (e.get("DpTxt_Obj", {}).get("Txt") or e.get("DpTxt_Obj", {}).get("TxtShort") or f"dp{pid}").strip()
            rows.append((pid, caption))
        captions = [c for _, c in rows]
        out = []
        for pid, caption in rows:
            value, unit = self.get_dp(pid)
            desc = describe(caption, value, unit)
            # captions are not unique across the plant; disambiguate the display name with the id
            desc["pid"] = pid
            desc["name"] = f"{caption} ({pid})" if captions.count(caption) > 1 else caption
            out.append(desc)
        return out

    def read_values(self, descriptors: list[dict]) -> dict[int, str | None]:
        """Read every descriptor's value, re-logging in once on session expiry."""
        for _ in range(2):
            try:
                self._ensure()
                return {d["pid"]: self.get_dp(d["pid"])[0] for d in descriptors}
            except SessionExpired:
                self.s = self.base = self.sid = None  # force a clean re-login
        raise SessionExpired("re-login did not recover session")
