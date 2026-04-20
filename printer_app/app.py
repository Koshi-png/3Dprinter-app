from __future__ import annotations

import json
import shutil
import time
from datetime import date, datetime, time as dt_time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

APP_TITLE = "3Dプリンター使用状況ダッシュボード"
TIME_FMT = "%Y-%m-%d %H:%M"
APP_TZ = ZoneInfo("Asia/Tokyo")
DEFAULT_PRINTERS = ["R1", "R2", "R3", "R4", "R5", "B1", "B2", "B3", "B4"]
DEFAULT_USERS = ["田中", "佐藤", "鈴木", "山田"]
BASE_DIR = Path(__file__).resolve().parent
LEGACY_DATA_DIR = BASE_DIR / "data"
DEFAULT_DATA_DIR = Path.home() / ".printer_dashboard_data"
LAYOUT_CANDIDATES = [
    BASE_DIR / "assets" / "layout-1.png",
    BASE_DIR / "layout-1.png",
    BASE_DIR / "assets" / "layout.png",
]


# ---------------------------
# パス・永続化
# ---------------------------
def get_data_dir() -> Path:
    secret_dir = None
    try:
        secret_dir = st.secrets.get("DATA_DIR", None)
    except Exception:
        secret_dir = None
    if secret_dir:
        return Path(secret_dir)
    return DEFAULT_DATA_DIR


def get_paths() -> dict[str, Path]:
    data_dir = get_data_dir()
    return {
        "data_dir": data_dir,
        "printers": data_dir / "printers.json",
        "users": data_dir / "users.json",
        "active": data_dir / "active_jobs.json",
        "history": data_dir / "history.json",
    }


def atomic_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    bak = path.with_suffix(path.suffix + ".bak")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    if path.exists():
        shutil.copy2(path, bak)
    tmp.replace(path)


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        atomic_write_json(path, default)
        return default
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        bak = path.with_suffix(path.suffix + ".bak")
        if bak.exists():
            with bak.open("r", encoding="utf-8") as f:
                return json.load(f)
        atomic_write_json(path, default)
        return default


def save_state(
    printers: list[str],
    users: list[str],
    active_jobs: list[dict[str, Any]],
    history: list[dict[str, Any]],
) -> None:
    paths = get_paths()
    atomic_write_json(paths["printers"], printers)
    atomic_write_json(paths["users"], users)
    atomic_write_json(paths["active"], active_jobs)
    atomic_write_json(paths["history"], history)


def load_state() -> tuple[list[str], list[str], list[dict[str, Any]], list[dict[str, Any]]]:
    paths = get_paths()
    printers = read_json(paths["printers"], DEFAULT_PRINTERS)
    users = read_json(paths["users"], DEFAULT_USERS)
    active_jobs = read_json(paths["active"], [])
    history = read_json(paths["history"], [])
    return printers, users, active_jobs, history


def bootstrap_persistent_data() -> None:
    paths = get_paths()
    paths["data_dir"].mkdir(parents=True, exist_ok=True)

    legacy_files = {
        "printers": LEGACY_DATA_DIR / "printers.json",
        "users": LEGACY_DATA_DIR / "users.json",
        "active": LEGACY_DATA_DIR / "active_jobs.json",
        "history": LEGACY_DATA_DIR / "history.json",
    }
    for key, legacy_path in legacy_files.items():
        new_path = paths[key]
        if not new_path.exists() and legacy_path.exists():
            new_path.write_text(legacy_path.read_text(encoding="utf-8"), encoding="utf-8")

    now = now_floor_minute()
    defaults: dict[str, Any] = {
        "printers": DEFAULT_PRINTERS,
        "users": DEFAULT_USERS,
        "active": [
            {
                "job_id": "active-001",
                "printer_id": "R2",
                "user_name": "田中",
                "print_name": "ギアケース",
                "planned_minutes": 180,
                "start_time": format_dt(now - timedelta(minutes=55)),
                "end_time": format_dt(now + timedelta(minutes=125)),
            },
            {
                "job_id": "active-002",
                "printer_id": "B3",
                "user_name": "佐藤",
                "print_name": "治具A",
                "planned_minutes": 90,
                "start_time": format_dt(now - timedelta(minutes=20)),
                "end_time": format_dt(now + timedelta(minutes=70)),
            },
        ],
        "history": [
            {
                "job_id": "hist-001",
                "printer_id": "R1",
                "user_name": "鈴木",
                "print_name": "センサーカバー",
                "planned_minutes": 120,
                "start_time": format_dt(now - timedelta(days=1, hours=5)),
                "end_time": format_dt(now - timedelta(days=1, hours=3)),
                "logged_at": format_dt(now - timedelta(days=1, hours=3)),
                "status": "completed",
            },
            {
                "job_id": "hist-002",
                "printer_id": "B1",
                "user_name": "山田",
                "print_name": "リンク部品",
                "planned_minutes": 75,
                "start_time": format_dt(now - timedelta(days=2, hours=2)),
                "end_time": format_dt(now - timedelta(days=2, minutes=45)),
                "logged_at": format_dt(now - timedelta(days=2, minutes=45)),
                "status": "completed",
            },
        ],
    }

    for key in ["printers", "users", "active", "history"]:
        if not paths[key].exists():
            atomic_write_json(paths[key], defaults[key])


# ---------------------------
# 日時ユーティリティ（常に JST）
# ---------------------------
def now_floor_minute() -> datetime:
    return datetime.now(APP_TZ).replace(second=0, microsecond=0)


def parse_dt(value: str) -> datetime:
    return datetime.strptime(value, TIME_FMT).replace(tzinfo=APP_TZ)


def format_dt(value: datetime) -> str:
    return value.astimezone(APP_TZ).strftime(TIME_FMT)


def combine_date_time(d: date, t: dt_time) -> datetime:
    return datetime.combine(d, t).replace(second=0, microsecond=0, tzinfo=APP_TZ)


def format_remaining(delta: timedelta) -> str:
    total_seconds = int(delta.total_seconds())
    if total_seconds <= 0:
        return "完了予定時刻を過ぎています"
    hours, remainder = divmod(total_seconds, 3600)
    minutes = remainder // 60
    if hours > 0:
        return f"{hours}時間{minutes}分"
    return f"{minutes}分"


def progress_ratio(start_time: datetime, end_time: datetime, now: datetime) -> float:
    total = max((end_time - start_time).total_seconds(), 1)
    done = (now - start_time).total_seconds()
    return max(0.0, min(done / total, 1.0))


# ---------------------------
# データロジック
# ---------------------------
def get_active_job_map(active_jobs: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {job["printer_id"]: job for job in active_jobs}


def archive_finished_jobs(
    active_jobs: list[dict[str, Any]], history: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], bool]:
    now = now_floor_minute()
    remaining_active: list[dict[str, Any]] = []
    updated_history = history[:]
    history_ids = {job["job_id"] for job in history}
    changed = False

    for job in active_jobs:
        end_time = parse_dt(job["end_time"])
        if end_time <= now:
            if job["job_id"] not in history_ids:
                updated_history.append(
                    {
                        **job,
                        "logged_at": format_dt(now),
                        "status": "completed",
                    }
                )
                changed = True
        else:
            remaining_active.append(job)

    updated_history.sort(key=lambda x: x.get("logged_at", x["end_time"]), reverse=True)
    if len(remaining_active) != len(active_jobs):
        changed = True
    return remaining_active, updated_history, changed


def register_job(
    printers: list[str],
    users: list[str],
    active_jobs: list[dict[str, Any]],
    printer_id: str,
    user_name: str,
    print_name: str,
    planned_minutes: int,
    start_time: datetime,
) -> tuple[list[str], list[str], list[dict[str, Any]], dict[str, Any]]:
    end_time = start_time + timedelta(minutes=planned_minutes)
    printer_set = set(printers)
    user_set = set(users)
    printer_set.add(printer_id)
    user_set.add(user_name)

    job = {
        "job_id": f"job-{int(time.time() * 1000)}",
        "printer_id": printer_id,
        "user_name": user_name,
        "print_name": print_name,
        "planned_minutes": planned_minutes,
        "start_time": format_dt(start_time),
        "end_time": format_dt(end_time),
    }

    updated_active = [j for j in active_jobs if j["printer_id"] != printer_id]
    updated_active.append(job)
    return sorted(printer_set), sorted(user_set), updated_active, job


def finish_job(
    printer_id: str, active_jobs: list[dict[str, Any]], history: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    now = now_floor_minute()
    remaining = []
    updated_history = history[:]
    for job in active_jobs:
        if job["printer_id"] == printer_id:
            updated_history.append(
                {
                    **job,
                    "end_time": format_dt(now),
                    "logged_at": format_dt(now),
                    "status": "manually_finished",
                }
            )
        else:
            remaining.append(job)
    updated_history.sort(key=lambda x: x.get("logged_at", x["end_time"]), reverse=True)
    return remaining, updated_history


def delete_job(
    printer_id: str, active_jobs: list[dict[str, Any]], history: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any] | None]:
    now = now_floor_minute()
    remaining = []
    updated_history = history[:]
    deleted_job = None
    for job in active_jobs:
        if job["printer_id"] == printer_id:
            deleted_job = {
                **job,
                "logged_at": format_dt(now),
                "status": "deleted",
            }
            updated_history.append(deleted_job)
        else:
            remaining.append(job)
    updated_history.sort(key=lambda x: x.get("logged_at", x["end_time"]), reverse=True)
    return remaining, updated_history, deleted_job


# ---------------------------
# UI部品
# ---------------------------
def render_summary(printers: list[str], active_jobs: list[dict[str, Any]]) -> None:
    active_map = get_active_job_map(active_jobs)
    total = len(printers)
    busy = len(active_map)
    free = total - busy
    c1, c2, c3 = st.columns(3)
    c1.metric("総機械数", total)
    c2.metric("使用中", busy)
    c3.metric("空き", free)


def render_printer_card(printer_id: str, active_job: dict[str, Any] | None) -> None:
    now = now_floor_minute()
    with st.container(border=True):
        st.subheader(printer_id)
        if active_job is None:
            st.success("空き")
            st.write("**使用者**: -")
            st.write("**印刷物**: -")
            st.write("**残り時間**: -")
            st.progress(0.0, text="待機中")
            return

        start_time = parse_dt(active_job["start_time"])
        end_time = parse_dt(active_job["end_time"])
        remaining = end_time - now
        ratio = progress_ratio(start_time, end_time, now)

        st.error("使用中")
        st.write(f"**使用者**: {active_job['user_name']}")
        st.write(f"**印刷物**: {active_job['print_name']}")
        st.write(f"**開始時刻**: {active_job['start_time']} JST")
        st.write(f"**終了予定**: {active_job['end_time']} JST")
        st.write(f"**残り時間**: {format_remaining(remaining)}")
        st.progress(ratio, text=f"進捗 {int(ratio * 100)}%")


def render_layout_help() -> None:
    st.markdown("### 配置対応図")
    st.caption("レイアウト図の機械ID: R1〜R5, B1〜B4")
    layout_path = next((path for path in LAYOUT_CANDIDATES if path.exists()), None)
    if layout_path is not None:
        st.image(str(layout_path), caption="3Dプリンター配置図", use_container_width=True)
        return

    st.warning("配置図画像が見つからなかったため、簡易レイアウトを表示しています。")
    grid_rows = [
        ["R5", "", ""],
        ["R2", "R1", ""],
        ["R3", "R4", ""],
        ["B1", "", ""],
        ["B2", "", ""],
        ["B3", "", ""],
        ["B4", "", ""],
    ]
    st.dataframe(pd.DataFrame(grid_rows), hide_index=True, use_container_width=True)


# ---------------------------
# 画面状態
# ---------------------------
def init_view_state() -> None:
    if "page_selector" not in st.session_state:
        st.session_state["page_selector"] = "ダッシュボード"
    if "redirect_page" not in st.session_state:
        st.session_state["redirect_page"] = None
    if "dashboard_notice" not in st.session_state:
        st.session_state["dashboard_notice"] = None
    if "auto_refresh" not in st.session_state:
        st.session_state["auto_refresh"] = False


def apply_redirect_if_needed() -> str:
    redirect_page = st.session_state.get("redirect_page")
    if redirect_page:
        st.session_state["page_selector"] = redirect_page
        st.session_state["redirect_page"] = None
    return st.session_state.get("page_selector", "ダッシュボード")


# ---------------------------
# メイン画面
# ---------------------------
def main() -> None:
    st.set_page_config(page_title=APP_TITLE, page_icon="🖨️", layout="wide")
    st.title(APP_TITLE)
    st.caption("3Dプリンターの空き状況、使用登録、履歴確認を一元管理できます。")

    init_view_state()
    bootstrap_persistent_data()
    printers, users, active_jobs, history = load_state()

    active_jobs, history, archived_changed = archive_finished_jobs(active_jobs, history)
    if archived_changed:
        save_state(printers, users, active_jobs, history)

    current_page = apply_redirect_if_needed()

    with st.sidebar:
        st.markdown("### 画面切替")
        st.radio(
            "表示するページ",
            options=["ダッシュボード", "使用登録", "履歴ログ", "設定/マスタ管理"],
            key="page_selector",
            label_visibility="collapsed",
        )
        st.toggle("自動更新を有効化", key="auto_refresh")
        st.caption(f"現在時刻基準: {format_dt(now_floor_minute())} JST")
        st.caption(f"保存先: {get_paths()['data_dir']}")

    if current_page == "ダッシュボード":
        notice = st.session_state.get("dashboard_notice")
        if notice:
            st.success(notice)
            st.session_state["dashboard_notice"] = None

        render_summary(printers, active_jobs)
        st.markdown("### 現在の使用状況")
        active_map = get_active_job_map(active_jobs)

        left, right = st.columns([1, 2])
        with left:
            render_layout_help()
        with right:
            cols = st.columns(3)
            for idx, printer_id in enumerate(printers):
                with cols[idx % 3]:
                    render_printer_card(printer_id, active_map.get(printer_id))

        st.markdown("### 使用中データの操作")
        busy_printers = sorted(active_map.keys())
        if busy_printers:
            op_col1, op_col2 = st.columns(2)
            with op_col1:
                finish_printer = st.selectbox("終了する機械を選択", options=busy_printers, key="finish_printer")
                if st.button("選択した機械を終了扱いにする", type="secondary"):
                    active_jobs, history = finish_job(finish_printer, active_jobs, history)
                    save_state(printers, users, active_jobs, history)
                    st.session_state["dashboard_notice"] = f"{finish_printer} を終了登録しました。"
                    st.session_state["redirect_page"] = "ダッシュボード"
                    st.rerun()
            with op_col2:
                delete_printer = st.selectbox("削除する機械を選択", options=busy_printers, key="delete_printer")
                confirm_delete_job = st.checkbox("削除前の確認: 本当に現在の使用中データを削除する", key="confirm_delete_job")
                if st.button("現在登録を削除する", type="secondary"):
                    if not confirm_delete_job:
                        st.warning("削除する前に確認チェックをオンにしてください。")
                    else:
                        active_jobs, history, deleted_job = delete_job(delete_printer, active_jobs, history)
                        save_state(printers, users, active_jobs, history)
                        deleted_name = deleted_job["print_name"] if deleted_job else "対象ジョブ"
                        st.session_state["dashboard_notice"] = f"{delete_printer} の登録（{deleted_name}）を削除しました。"
                        st.session_state["redirect_page"] = "ダッシュボード"
                        st.rerun()
        else:
            st.info("操作対象の使用中機械はありません。")

    elif current_page == "使用登録":
        st.markdown("### 新しい印刷ジョブを登録")
        active_map = get_active_job_map(active_jobs)
        available_printers = [p for p in printers if p not in active_map]

        use_new_printer = st.checkbox("新しい機械名を追加して登録する", key="use_new_printer")
        if use_new_printer:
            printer_id = st.text_input("新しい機械名", placeholder="例: R6", key="register_new_printer")
        else:
            printer_id = st.selectbox(
                "使用する機械名",
                options=available_printers if available_printers else printers,
                help="使用中ではない機械が優先表示されます。",
                key="register_printer",
            )

        use_new_user = st.checkbox("新しい使用者名を追加して登録する", key="use_new_user")
        if use_new_user:
            user_name = st.text_input("新しい使用者名", placeholder="例: 野山", key="register_new_user")
        else:
            user_name = st.selectbox("使用者名", options=users, key="register_user")

        print_name = st.text_input("印刷物名", placeholder="例: ローバ部品ケース", key="register_print_name")
        planned_minutes = st.number_input(
            "印刷予定時間（分）", min_value=1, max_value=24 * 60, value=120, step=10, key="register_planned_minutes"
        )

        preview_now = now_floor_minute()
        use_custom_start = st.checkbox(
            "開始時刻を手動入力する",
            help="オフのときは、登録ボタンを押した時点の現在時刻（JST）を自動で使います。",
            key="use_custom_start",
        )
        if use_custom_start:
            manual_date = st.date_input("開始日", value=preview_now.date(), key="manual_start_date")
            manual_time = st.time_input("開始時刻", value=preview_now.time(), key="manual_start_time")
            start_time_preview = combine_date_time(manual_date, manual_time)
            st.info(f"開始時刻: 手動入力モード ({format_dt(start_time_preview)} JST)")
        else:
            start_time_preview = preview_now
            st.info(f"開始時刻: 自動取得モード（登録時の現在時刻を使用）\n目安: {format_dt(start_time_preview)} JST")

        end_preview = start_time_preview + timedelta(minutes=int(planned_minutes))
        st.caption(f"終了予定時刻の目安: {format_dt(end_preview)} JST")

        if st.button("使用登録する", type="primary"):
            printer_id = (printer_id or "").strip()
            user_name = (user_name or "").strip()
            print_name = (print_name or "").strip()
            start_time_to_use = combine_date_time(manual_date, manual_time) if use_custom_start else now_floor_minute()
            active_map = get_active_job_map(active_jobs)

            if not printer_id or not user_name or not print_name:
                st.error("機械名、使用者名、印刷物名は必須です。")
            elif printer_id in active_map:
                st.error(f"{printer_id} は現在使用中です。別の機械を選択してください。")
            else:
                printers, users, active_jobs, _ = register_job(
                    printers=printers,
                    users=users,
                    active_jobs=active_jobs,
                    printer_id=printer_id,
                    user_name=user_name,
                    print_name=print_name,
                    planned_minutes=int(planned_minutes),
                    start_time=start_time_to_use,
                )
                save_state(printers, users, active_jobs, history)
                st.session_state["dashboard_notice"] = (
                    f"{printer_id} の使用を登録しました。開始時刻: {format_dt(start_time_to_use)} JST"
                )
                st.session_state["redirect_page"] = "ダッシュボード"
                st.rerun()

    elif current_page == "履歴ログ":
        st.markdown("### 使用履歴ログ")
        if history:
            rows = []
            for job in sorted(history, key=lambda x: x.get("logged_at", x["end_time"]), reverse=True):
                rows.append(
                    {
                        "記録日時": f"{job.get('logged_at', job['end_time'])} JST",
                        "使用者": job["user_name"],
                        "印刷物": job["print_name"],
                        "使用機械": job["printer_id"],
                        "印刷時間(分)": job["planned_minutes"],
                        "開始時刻": f"{job['start_time']} JST",
                        "終了時刻": f"{job['end_time']} JST",
                        "状態": job.get("status", "completed"),
                    }
                )
            history_df = pd.DataFrame(rows)
            st.dataframe(history_df, use_container_width=True, hide_index=True)
            csv = history_df.to_csv(index=False).encode("utf-8-sig")
            st.download_button("履歴CSVをダウンロード", data=csv, file_name="printer_history.csv", mime="text/csv")
        else:
            st.info("まだ履歴がありません。")

    elif current_page == "設定/マスタ管理":
        st.markdown("### マスタ管理")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### 機械一覧")
            st.dataframe(pd.DataFrame({"機械ID": printers}), hide_index=True, use_container_width=True)
            new_master_printer = st.text_input("機械を追加", placeholder="例: R6", key="new_master_printer")
            if st.button("機械を追加する", key="add_master_printer"):
                new_master_printer = new_master_printer.strip()
                if not new_master_printer:
                    st.error("機械名を入力してください。")
                elif new_master_printer in printers:
                    st.warning("その機械名はすでに登録されています。")
                else:
                    printers = sorted(set(printers + [new_master_printer]))
                    save_state(printers, users, active_jobs, history)
                    st.success(f"{new_master_printer} を追加しました。")
                    st.rerun()

        with col2:
            st.markdown("#### 使用者一覧")
            st.dataframe(pd.DataFrame({"使用者名": users}), hide_index=True, use_container_width=True)
            new_master_user = st.text_input("使用者を追加", placeholder="例: 野山", key="new_master_user")
            if st.button("使用者を追加する", key="add_master_user"):
                new_master_user = new_master_user.strip()
                if not new_master_user:
                    st.error("使用者名を入力してください。")
                elif new_master_user in users:
                    st.warning("その使用者名はすでに登録されています。")
                else:
                    users = sorted(set(users + [new_master_user]))
                    save_state(printers, users, active_jobs, history)
                    st.success(f"{new_master_user} を追加しました。")
                    st.rerun()

            st.markdown("#### 登録済み使用者の削除")
            if users:
                delete_user_name = st.selectbox("削除する使用者を選択", options=users, key="delete_user_name")
                confirm_delete_user = st.checkbox("削除前の確認: 本当にこの使用者を削除する", key="confirm_delete_user")
                if st.button("使用者を削除する", key="delete_user_button"):
                    active_user_names = {job["user_name"] for job in active_jobs}
                    if delete_user_name in active_user_names:
                        st.warning("この使用者は現在使用中データに含まれています。先に使用登録を終了または削除してください。")
                    elif not confirm_delete_user:
                        st.warning("削除する前に確認チェックをオンにしてください。")
                    else:
                        users = [u for u in users if u != delete_user_name]
                        save_state(printers, users, active_jobs, history)
                        st.success(f"{delete_user_name} を使用者候補一覧から削除しました。")
                        st.rerun()

        st.markdown("### 保存ファイル")
        paths = get_paths()
        st.code(
            "\n".join(
                [
                    f"保存先ディレクトリ: {paths['data_dir']}",
                    f"- {paths['printers'].name}: 機械一覧",
                    f"- {paths['users'].name}: 使用者一覧",
                    f"- {paths['active'].name}: 現在使用中の情報",
                    f"- {paths['history'].name}: 過去ログ",
                ]
            )
        )
        st.info(
            "時刻はすべて Asia/Tokyo（JST）で扱います。"
            "自動取得時は『使用登録する』ボタンを押した時点の JST 現在時刻を使います。"
            "手動入力をオンにした場合のみ、画面上で指定した JST 日時を開始時刻として使います。"
        )

    if st.session_state.get("auto_refresh"):
        time.sleep(30)
        st.rerun()


if __name__ == "__main__":
    main()
