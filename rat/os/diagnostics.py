"""Explicit isolated native startup session, with model and network guards."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import sys
import time
import uuid


def prepare_session(output_root):
    session = Path(output_root).expanduser().resolve() / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8])
    state = session / 'state'
    state.mkdir(parents=True)
    settings = dict(first_run_completed=True, indexed_directories=[], auto_watch=False,
                    llm_provider='offline', document_model_path='', document_model_preload=False,
                    memory_sentinel_enabled=False, launch_at_login=False)
    (state / 'config.json').write_text(json.dumps(settings, indent=2) + '\n')
    (state / 'club_schedules.json').write_text('[]\n')
    os.environ.update(RAT_STATE_DIR=str(state), RAT_DB_PATH=str(state / 'fixture.db'),
                      RAT_LOG_DIR=str(session / 'logs'), RAT_DOCUMENT_MODEL_PATH='',
                      RAT_DOCUMENT_MODEL_PRELOAD='0', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
    return session


def run_session(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output_root', type=Path)
    parser.add_argument('--seconds', type=int, default=0, help='auto-quit after this many seconds; 0 waits for Quit')
    args = parser.parse_args(argv)
    if not 0 <= args.seconds <= 600:
        parser.error('--seconds must be between 0 and 600')
    if 'rat.config' in sys.modules:
        raise RuntimeError('Diagnostic isolation must be configured before application imports')
    session = prepare_session(args.output_root)
    (session / 'logs').mkdir()
    logging.getLogger().addHandler(logging.FileHandler(session / 'logs/session.log', encoding='utf-8'))
    started = time.monotonic()
    blocked = []

    def guard(event, values):
        if event == 'import' and values[0].split('.')[0] in {'mlx', 'mlx_lm', 'fastembed', 'onnxruntime', 'transformers', 'torch'}:
            blocked.append({'operation': 'model_import', 'module': values[0]})
            raise RuntimeError('Model runtimes are disabled in the diagnostic session')
        if event == 'socket.connect':
            import socket
            if values[0].family != socket.AF_UNIX:
                blocked.append({'operation': 'network_connect'})
                raise PermissionError('Networking is disabled in the diagnostic session')
    sys.addaudithook(guard)

    from rat.config import config
    config.use_slm = False
    from rat.engine.app_resolver import ApplicationCatalog
    from rat.engine.slm import SLMEngine
    # Explicit fixture dependencies; no application or model catalog discovery.
    ApplicationCatalog.scan = classmethod(lambda cls, *a, **k: cls())
    SLMEngine.list_installed_models = lambda self: []
    SLMEngine.is_service_running = lambda self: False
    from PyQt6.QtCore import QTimer, qInstallMessageHandler
    from PyQt6.QtGui import QGuiApplication
    from rat.os import single_instance
    single_instance.SINGLE_INSTANCE_SERVER_NAME += f'_diagnostic_{os.getpid()}'
    from rat.os.permissions import accessibility_status, runtime_identity
    from rat.os.app import ResidentApplication
    from rat.os.crash_shield import install_crash_shield
    install_crash_shield()

    def qt_message(kind, context, message):
        with (session / 'qt_messages.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps({'kind': str(kind), 'message': message}, ensure_ascii=False) + '\n')
    previous_handler = qInstallMessageHandler(qt_message)
    app = QGuiApplication.instance() or QGuiApplication(sys.argv)
    app.setProperty('rat_diagnostic_session', str(session))
    identity = runtime_identity()
    (session / 'identity.json').write_text(json.dumps(identity, indent=2) + '\n')
    print(json.dumps({'diagnostic_session': str(session), 'identity': identity}), flush=True)
    resident = None
    last = None
    timer = QTimer()

    def snapshot():
        nonlocal last
        manager = resident.hotkey_manager if resident else None
        window = resident.desk_view if resident else None
        value = {'accessibility': accessibility_status().to_dict(),
                 'hotkey_status': getattr(manager, 'status', 'not_started'),
                 'hotkey_error': getattr(manager, 'last_error', None),
                 'window_visible': bool(window and window.isVisible())}
        if value != last:
            with (session / 'states.jsonl').open('a', encoding='utf-8') as stream:
                stream.write(json.dumps({'elapsed_seconds': time.monotonic() - started, **value}) + '\n')
            last = value
    timer.timeout.connect(snapshot)
    timer.start(500)
    if args.seconds:
        QTimer.singleShot(args.seconds * 1000, lambda: resident.request_quit() if resident else None)
    outcome = {'status': 'starting'}
    try:
        resident = ResidentApplication(mode='spotlight')
        code = resident.run()
        outcome = {'status': 'exited', 'exit_code': code}
        return code
    except Exception as exc:
        logging.getLogger('rat.diagnostics').exception('Native startup failed')
        outcome = {'status': 'startup_error', 'error_type': type(exc).__name__, 'error': str(exc)}
        raise
    finally:
        timer.stop()
        snapshot()
        from rat.engine.embedder import embedder
        outcome.update(identity=identity, qpa=app.platformName(), blocked_operations=blocked,
                       embedding_loaded=embedder.is_loaded, elapsed_seconds=time.monotonic() - started,
                       final_state=last, isolation='fixture state/database; empty app/model catalogs; no model/network access')
        (session / 'session.json').write_text(json.dumps(outcome, indent=2, ensure_ascii=False) + '\n')
        qInstallMessageHandler(previous_handler)


def collect_system_diagnostics() -> dict[str, any]:
    """Collect structured health and environment telemetry with deterministic schema."""
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "overall_status": "PASS",
        "checks": {},
        "exit_code": 0,
    }
    has_warning = False
    has_failure = False

    # 1. Environment Check
    env_info = {
        "python_version": sys.version.split()[0],
        "platform": sys.platform,
        "is_macos": sys.platform == "darwin",
    }
    if sys.platform == "darwin":
        import platform
        env_info["machine"] = platform.machine()
        env_info["is_apple_silicon"] = platform.machine().startswith("arm")

    if sys.version_info >= (3, 11):
        report["checks"]["environment"] = {"status": "PASS", "details": env_info}
    else:
        report["checks"]["environment"] = {
            "status": "FAIL",
            "details": env_info,
            "error": "Python >= 3.11 required",
        }
        has_failure = True

    # 2. Database & Storage Check
    from rat.config import config
    db_path = Path(config.db_path)
    db_info = {
        "path": str(db_path),
        "exists": db_path.is_file(),
    }
    if db_path.is_file():
        try:
            import sqlite3
            conn = sqlite3.connect(str(db_path))
            cur = conn.cursor()
            cur.execute("PRAGMA integrity_check;")
            integrity_row = cur.fetchone()
            integrity = integrity_row[0] if integrity_row else "unknown"
            cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table';")
            tables_count = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='documents';")
            has_documents = cur.fetchone()[0] > 0
            doc_count = 0
            if has_documents:
                cur.execute("SELECT count(*) FROM documents;")
                doc_count = cur.fetchone()[0]
            conn.close()

            db_info["integrity"] = integrity
            db_info["tables_count"] = tables_count
            db_info["total_documents"] = doc_count
            db_info["size_bytes"] = db_path.stat().st_size

            if integrity == "ok":
                report["checks"]["database"] = {"status": "PASS", "details": db_info}
            else:
                report["checks"]["database"] = {"status": "FAIL", "details": db_info, "error": f"Integrity check: {integrity}"}
                has_failure = True
        except Exception as e:
            db_info["error"] = str(e)
            report["checks"]["database"] = {"status": "FAIL", "details": db_info, "error": str(e)}
            has_failure = True
    else:
        report["checks"]["database"] = {
            "status": "WARN",
            "details": db_info,
            "message": "Index database not found. Run `python main.py index` to initialize.",
        }
        has_warning = True

    # 3. Configuration Check
    from rat.config import CONFIG_FILE
    cfg_info = {
        "config_path": str(CONFIG_FILE),
        "exists": CONFIG_FILE.is_file(),
        "default_profile": config.default_member_name,
        "indexed_directories": config.indexed_directories,
    }
    valid_dirs = [d for d in config.indexed_directories if os.path.exists(d)]
    cfg_info["active_directories_found"] = len(valid_dirs)
    if valid_dirs:
        report["checks"]["configuration"] = {"status": "PASS", "details": cfg_info}
    else:
        report["checks"]["configuration"] = {
            "status": "WARN",
            "details": cfg_info,
            "message": "No configured directories found on disk.",
        }
        has_warning = True

    # 4. Local Model Assets & Runtimes
    from rat.engine.slm import slm_engine
    model_info = {
        "provider": config.llm_provider,
        "use_slm": config.use_slm,
        "slm_model_installed": slm_engine.is_model_installed(),
    }
    report["checks"]["models"] = {"status": "PASS", "details": model_info}

    # 5. macOS Permissions & Identity
    from rat.os.permissions import accessibility_status, runtime_identity
    perm_status = accessibility_status(prompt=False)
    perm_info = {
        "trusted": perm_status.trusted,
        "state": perm_status.state,
        "identity": runtime_identity(),
    }
    if perm_status.trusted or sys.platform != "darwin":
        report["checks"]["permissions"] = {"status": "PASS", "details": perm_info}
    else:
        report["checks"]["permissions"] = {
            "status": "WARN",
            "details": perm_info,
            "message": "Accessibility permission not granted. Hotkeys may be restricted.",
        }
        has_warning = True

    # Compute overall status
    if has_failure:
        report["overall_status"] = "FAIL"
        report["exit_code"] = 1
    elif has_warning:
        report["overall_status"] = "WARN"
        report["exit_code"] = 0
    else:
        report["overall_status"] = "PASS"
        report["exit_code"] = 0

    return report
