"""
Machine lock for DennTech Crypto Suite.
Binds install to one PC (same model as Elite trial_manager).
Copying the app to another computer fails until re-activated on that machine.
Do not ship authorized_machine.json with customer builds.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
import uuid
from datetime import datetime
from typing import Optional, Tuple

AUTH_FILE_NAME = "authorized_machine.json"
LICENSE_FILE_NAME = "license.json"


def get_runtime_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def get_machine_id() -> Optional[str]:
    try:
        machine_uuid = str(uuid.getnode())
        system_info = f"{platform.system()}_{platform.machine()}"
        combined = f"{machine_uuid}_{system_info}"
        return hashlib.sha256(combined.encode()).hexdigest()[:32]
    except Exception:
        return None


def _auth_path() -> str:
    return os.path.join(get_runtime_dir(), AUTH_FILE_NAME)


def _license_path() -> str:
    return os.path.join(get_runtime_dir(), "data", LICENSE_FILE_NAME)


def is_authorized_machine() -> bool:
    path = _auth_path()
    if not os.path.exists(path):
        return False
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not data.get("bypass_locks", False):
            return False
        current = get_machine_id()
        if not current:
            return False
        expected = data.get("machine_id")
        if not expected and data.get("authorize_current_machine", False):
            data["machine_id"] = current
            data["authorize_current_machine"] = False
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            expected = current
        return current == expected
    except Exception:
        return False


def load_license() -> dict:
    path = _license_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_license(data: dict) -> bool:
    path = _license_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        return True
    except Exception:
        return False


def bind_current_machine(note: str = "Customer activation") -> Tuple[bool, str]:
    machine_id = get_machine_id()
    if not machine_id:
        return False, "Could not read machine ID"
    payload = {
        "machine_id": machine_id,
        "enable_machine_lock": True,
        "activated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "note": note,
        "product": "DennTech Crypto Suite",
    }
    if not save_license(payload):
        return False, "Could not write license file"
    return True, f"Licensed to machine {machine_id[:8]}..."


def check_machine_lock() -> Tuple[bool, str]:
    """
    Returns (ok, reason).
    First run with no license binds this PC.
    Later runs require the same machine_id.
    """
    if is_authorized_machine():
        return True, "Authorized developer machine"

    data = load_license()
    if not data.get("enable_machine_lock", True) and data.get("machine_id"):
        # Explicit unlock for internal testing only
        return True, "Machine lock disabled"

    stored = data.get("machine_id")
    current = get_machine_id()
    if not current:
        return False, "Could not read machine ID"

    if not stored:
        ok, msg = bind_current_machine()
        return ok, msg

    if stored != current:
        return False, "Machine does not match licensed computer"

    return True, "Machine lock valid"


def enforce_or_exit_gui() -> bool:
    """
    Call at Suite startup. Shows a blocking message and returns False if locked out.
    """
    ok, reason = check_machine_lock()
    if ok:
        return True
    try:
        from PyQt6.QtWidgets import QApplication, QMessageBox
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        QMessageBox.critical(
            None,
            "DennTech Crypto Suite — License",
            f"{reason}\n\n"
            "This copy is locked to another computer.\n"
            "Install and activate on the licensed PC, or contact support at cryptotradebot.info.",
        )
    except Exception:
        print(f"LICENSE ERROR: {reason}", file=sys.stderr)
    return False
