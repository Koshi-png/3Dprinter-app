from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

# =========================================================
# 3Dプリンター使用状況管理アプリ
# - Streamlit Community Cloud でも動かしやすいように JSON 保存で実装
# - 機械IDは配置図に合わせて R1-R5, B1-B4 を初期登録
# =========================================================

APP_TITLE = "3Dプリンター使用状況ダッシュボード"
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
ASSET_DIR = BASE_DIR / "assets"
PRINTERS_FILE = DATA_DIR / "printers.json"
USERS_FILE = DATA_DIR / "users.json"
ACTIVE_FILE = DATA_DIR / "active_jobs.json"
HISTORY_FILE = DATA_DIR / "history.json"
LAYOUT_IMAGE = ASSET_DIR / "layout-1.png"
TIME_FMT = "%Y-%m-%d %H:%M"

DEFAULT_PRINTERS = ["R1", "R2", "R3", "R4", "R5", "B1", "B2", "B3", "B4"]
DEFAULT_USERS = ["田中", "佐藤", "鈴木", "山田"]


# ---------------------------
# データ入出力
# ---------------------------
def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        write_json(path, default)
        return default
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ---------------------------
# 初期データ作成
# ---------------------------
def init_sample_data() -> None:
    ensure_data_dir()

    if not PRINTERS_FILE.exists():
        write_json(PRINTERS_FILE, DEFAULT_PRINTERS)

    if not USERS_FILE.exists():
        write_json(USERS_FILE, DEFAULT_USERS)

    now = datetime.now().replace(second=0, microsecond=0)

    if not ACTIVE_FILE.exists():
        active_jobs = [
            {
                "job_id": "active-001",
                "printer_id": "R2",
                "user_name": "田中",
                "print_name": "ギアケース",
                "planned_minutes": 180,
                "start_time": (now - timedelta(minutes=55)).strftime(TIME_FMT),
                "end_time": (now + timedelta(minutes=125)).strftime(TIME_FMT),
            },
            {
                "job_id": "active-002",
                "printer_id": "B3",
                "user_name": "佐藤",
                "print_name": "治具A",
                "planned_minutes": 90,
                "start_time": (now - timedelta(minutes=20)).strftime(TIME_FMT),
                "end_time": (now + timedelta(minutes=70)).strftime(TIME_FMT),
            },
        ]
        write_json(ACTIVE_FILE, active_jobs)

    if not HISTORY_FILE.exists():
        history = [
            {
                "job_id": "hist-001",
                "printer_id": "R1",
                "user_name": "鈴木",
                "print_name": "センサーカバー",
                "planned_minutes": 120,
                "start_time": (now - timedelta(days=1, hours=5)).strftime(TIME_FMT),
                "end_time": (now - timedelta(days=1, hours=3)).strftime(TIME_FMT),
                "logged_at": (now - timedelta(days=1, hours=3)).strftime(TIME_FMT),
                "status": "completed",
            },
            {
                "job_id": "hist-002",
                "printer_id": "B1",
                "user_name": "山田",
                "print_name": "リンク部品",
                "planned_minutes": 75,
                "start_time": (now - timedelta(days=2, hours=2)).strftime(TIME_FMT),
                "end_time": (now - timedelta(days=2, hours=0, minutes=45)).strftime(TIME_FMT),
                "logged_at": (now - timedelta(days=2, hours=0, minutes=45)).strftime(TIME_FMT),
                "status": "completed",
            },
        ]
        write_json(HISTORY_FILE, history)


# ---------------------------
# 日時ユーティリティ
# ---------------------------
def parse_dt(value: str) -> datetime:
    return datetime.strptime(value, TIME_FMT)


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
def load_state() -> tuple[list[str], list[str], list[dict[str, Any]], list[dict[str, Any]]]:
    printers = read_json(PRINTERS_FILE, DEFAULT_PRINTERS)
    users = read_json(USERS_FILE, DEFAULT_USERS)
    active_jobs = read_json(ACTIVE_FILE, [])
    history = read_json(HISTORY_FILE, [])
    return printers, users, active_jobs, history


def save_state(printers: list[str], users: list[str], active_jobs: list[dict[str, Any]], history: list[dict[str, Any]]) -> None:
    write_json(PRINTERS_FILE, printers)
    write_json(USERS_FILE, users)
    write_json(ACTIVE_FILE, active_jobs)
    write_json(HISTORY_FILE, history)


def archive_finished_jobs(active_jobs: list[dict[str, Any]], history: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    now = datetime.now().replace(second=0, microsecond=0)
    remaining_active = []
    updated_history = history[:]

    history_ids = {job["job_id"] for job in history}

    for job in active_jobs:
        end_time = parse_dt(job["end_time"])
        if end_time <= now:
            if job["job_id"] not in history_ids:
                archived = {
                    **job,
                    "logged_at": now.strftime(TIME_FMT),
                    "status": "completed",
                }
                updated_history.append(archived)
        else:
            remaining_active.append(job)

    updated_history.sort(key=lambda x: x.get("logged_at", x["end_time"]), reverse=True)
    return remaining_active, updated_history


def get_active_job_map(active_jobs: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {job["printer_id"]: job for job in active_jobs}


def register_job(
    printers: list[str],
    users: list[str],
    active_jobs: list[dict[str, Any]],
    printer_id: str,
    user_name: str,
    print_name: str,
    planned_minutes: int,
    start_time: datetime,
) -> tuple[list[str], list[str], list[dict[str, Any]]]:
    end_time = start_time + timedelta(minutes=planned_minutes)

    printer_set = set(printers)
    user_set = set(users)
    printer_set.add(printer_id)
    user_set.add(user_name)

    job = {
        "job_id": f"job-{int(datetime.now().timestamp())}",
        "printer_id": printer_id,
        "user_name": user_name,
        "print_name": print_name,
        "planned_minutes": planned_minutes,
        "start_time": start_time.strftime(TIME_FMT),
        "end_time": end_time.strftime(TIME_FMT),
    }

    updated_active = [j for j in active_jobs if j["printer_id"] != printer_id]
    updated_active.append(job)

    return sorted(printer_set), sorted(user_set), updated_active


def finish_job(printer_id: str, active_jobs: list[dict[str, Any]], history: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    now = datetime.now().replace(second=0, microsecond=0)
    remaining = []
    updated_history = history[:]

    for job in active_jobs:
        if job["printer_id"] == printer_id:
            finished = {
                **job,
                "end_time": now.strftime(TIME_FMT),
                "logged_at": now.strftime(TIME_FMT),
                "status": "manually_finished",
            }
            updated_history.append(finished)
        else:
            remaining.append(job)

    updated_history.sort(key=lambda x: x.get("logged_at", x["end_time"]), reverse=True)
    return remaining, updated_history


def delete_job(printer_id: str, active_jobs: list[dict[str, Any]], history: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any] | None]:
    now = datetime.now().replace(second=0, microsecond=0)
    remaining = []
    updated_history = history[:]
    deleted_job = None

    for job in active_jobs:
        if job["printer_id"] == printer_id:
            deleted_job = {
                **job,
                "logged_at": now.strftime(TIME_FMT),
                "status": "deleted",
            }
            updated_history.append(deleted_job)
        else:
            remaining.append(job)

    updated_history.sort(key=lambda x: x.get("logged_at", x["end_time"]), reverse=True)
    return remaining, updated_history, deleted_job



def user_is_active(user_name: str, active_jobs: list[dict[str, Any]]) -> bool:
    return any(job["user_name"] == user_name for job in active_jobs)



def delete_user(user_name: str, users: list[str], active_jobs: list[dict[str, Any]]) -> tuple[list[str], bool]:
    if user_is_active(user_name, active_jobs):
        return users, False
    updated_users = [name for name in users if name != user_name]
    return sorted(set(updated_users)), True


# ---------------------------
# UI部品
# ---------------------------
def render_summary(printers: list[str], active_jobs: list[dict[str, Any]]) -> None:
    active_map = get_active_job_map(active_jobs)
    total = len(printers)
    busy = len(active_map)
    free = total - busy

    col1, col2, col3 = st.columns(3)
    col1.metric("総機械数", total)
    col2.metric("使用中", busy)
    col3.metric("空き", free)


def render_printer_card(printer_id: str, active_job: dict[str, Any] | None) -> None:
    now = datetime.now().replace(second=0, microsecond=0)

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
        st.write(f"**開始時刻**: {active_job['start_time']}")
        st.write(f"**終了予定**: {active_job['end_time']}")
        st.write(f"**残り時間**: {format_remaining(remaining)}")
        st.progress(ratio, text=f"進捗 {int(ratio * 100)}%")


# ---------------------------
# メイン画面
# ---------------------------
def main() -> None:
    st.set_page_config(page_title=APP_TITLE, page_icon="🖨️", layout="wide")
    st.title(APP_TITLE)
    st.caption("3Dプリンターの空き状況、使用登録、履歴確認を一元管理できます。")

    init_sample_data()
    printers, users, active_jobs, history = load_state()

    # 予定終了を過ぎたものは自動で履歴へ移動
    active_jobs, history = archive_finished_jobs(active_jobs, history)
    save_state(printers, users, active_jobs, history)

    with st.sidebar:
        st.header("管理メニュー")
        auto_refresh = st.toggle("自動更新を有効化", value=False)
        if auto_refresh:
            st.caption("30秒ごとに再読込されます。")
            st.markdown(
                """
                <script>
                setTimeout(function(){ window.location.reload(); }, 30000);
                </script>
                """,
                unsafe_allow_html=True,
            )

        if st.button("データを初期サンプル状態に戻す"):
            for path in [PRINTERS_FILE, USERS_FILE, ACTIVE_FILE, HISTORY_FILE]:
                if path.exists():
                    path.unlink()
            init_sample_data()
            st.success("サンプルデータを再生成しました。ページを再読み込みしてください。")

        st.divider()
        st.write("**登録済み機械**")
        st.write(", ".join(printers))
        st.write("**登録済み使用者**")
        st.write(", ".join(users))

    page_options = ["ダッシュボード", "使用登録", "履歴ログ", "設定/マスタ管理"]

    # radioウィジェットのkeyを直接書き換えるとエラーになるため、
    # 表示中のページ状態とradioの選択状態を分けて管理する。
    redirect_page = st.session_state.pop("redirect_page", None)
    if "page" not in st.session_state:
        st.session_state["page"] = "ダッシュボード"
    if st.session_state["page"] not in page_options:
        st.session_state["page"] = "ダッシュボード"
    if "page_selector" not in st.session_state:
        st.session_state["page_selector"] = st.session_state["page"]
    if st.session_state["page_selector"] not in page_options:
        st.session_state["page_selector"] = st.session_state["page"]

    if redirect_page in page_options:
        st.session_state["page"] = redirect_page
        st.session_state["page_selector"] = redirect_page

    def sync_page_from_selector():
        st.session_state["page"] = st.session_state["page_selector"]

    st.radio(
        "表示ページ",
        options=page_options,
        horizontal=True,
        key="page_selector",
        label_visibility="collapsed",
        on_change=sync_page_from_selector,
    )
    page = st.session_state["page_selector"]
    st.session_state["page"] = page

    flash_message = st.session_state.pop("flash_message", None)
    flash_type = st.session_state.pop("flash_type", "success")
    if flash_message:
        getattr(st, flash_type)(flash_message)

    # ------------------
    # ダッシュボード
    # ------------------
    if page == "ダッシュボード":
        render_summary(printers, active_jobs)
        active_map = get_active_job_map(active_jobs)

        left, right = st.columns([1.1, 1.2], gap="large")

        with left:
            st.markdown("### 配置図")
            if LAYOUT_IMAGE.exists():
                st.image(str(LAYOUT_IMAGE), caption="3Dプリンター配置図", use_container_width=True)
            else:
                st.info("配置図画像が見つかりません。assets/layout-1.png を配置してください。")

        with right:
            st.markdown("### 機械ごとの状態")
            card_cols = st.columns(2)
            for idx, printer_id in enumerate(printers):
                with card_cols[idx % 2]:
                    render_printer_card(printer_id, active_map.get(printer_id))

        st.markdown("### 使用中機械の詳細")
        if active_jobs:
            rows = []
            now = datetime.now().replace(second=0, microsecond=0)
            for job in sorted(active_jobs, key=lambda x: x["end_time"]):
                start_time = parse_dt(job["start_time"])
                end_time = parse_dt(job["end_time"])
                ratio = progress_ratio(start_time, end_time, now)
                rows.append(
                    {
                        "機械": job["printer_id"],
                        "使用者": job["user_name"],
                        "印刷物": job["print_name"],
                        "開始時刻": job["start_time"],
                        "終了予定": job["end_time"],
                        "残り時間": format_remaining(end_time - now),
                        "進捗率": f"{int(ratio * 100)}%",
                    }
                )
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.success("現在、使用中の機械はありません。")

        st.markdown("### 登録の終了・削除")
        busy_printers = sorted([job["printer_id"] for job in active_jobs])
        if busy_printers:
            control_col1, control_col2 = st.columns(2)
            with control_col1:
                finish_printer = st.selectbox("終了する機械を選択", options=busy_printers, key="finish_printer")
                if st.button("選択した機械を終了扱いにする", type="secondary"):
                    active_jobs, history = finish_job(finish_printer, active_jobs, history)
                    save_state(printers, users, active_jobs, history)
                    st.session_state["flash_message"] = f"{finish_printer} を終了登録しました。"
                    st.session_state["flash_type"] = "success"
                    st.session_state.pop("delete_confirm_printer", None)
                    st.rerun()

            with control_col2:
                delete_printer = st.selectbox(
                    "削除する機械を選択",
                    options=busy_printers,
                    key="delete_printer",
                    help="誤登録や途中取り消し時に、現在の使用状況から削除します。",
                )

                delete_confirm_printer = st.session_state.get("delete_confirm_printer")
                if delete_confirm_printer == delete_printer:
                    st.warning(f"{delete_printer} の現在登録を削除します。よろしいですか？")
                    confirm_col1, confirm_col2 = st.columns(2)
                    with confirm_col1:
                        if st.button("はい、削除する", type="primary"):
                            active_jobs, history, deleted_job = delete_job(delete_printer, active_jobs, history)
                            save_state(printers, users, active_jobs, history)
                            st.session_state.pop("delete_confirm_printer", None)
                            if deleted_job:
                                st.session_state["flash_message"] = (
                                    f"{delete_printer} の現在登録を削除しました。履歴には status=deleted として記録しました。"
                                )
                                st.session_state["flash_type"] = "success"
                            else:
                                st.session_state["flash_message"] = f"{delete_printer} の削除対象が見つかりませんでした。"
                                st.session_state["flash_type"] = "warning"
                            st.rerun()
                    with confirm_col2:
                        if st.button("キャンセル", type="secondary"):
                            st.session_state.pop("delete_confirm_printer", None)
                            st.rerun()
                else:
                    if st.button("選択した機械の現在登録を削除する", type="primary"):
                        st.session_state["delete_confirm_printer"] = delete_printer
                        st.rerun()
        else:
            st.info("終了登録や削除が必要な使用中機械はありません。")

    # ------------------
    # 使用登録
    # ------------------
    elif page == "使用登録":
        st.markdown("### 新しい印刷ジョブを登録")
        active_map = get_active_job_map(active_jobs)
        available_printers = [p for p in printers if p not in active_map]

        with st.form("register_form"):
            use_new_printer = st.checkbox("新しい機械名を追加して登録する")
            if use_new_printer:
                printer_id = st.text_input("新しい機械名", placeholder="例: R6")
            else:
                printer_id = st.selectbox(
                    "使用する機械名",
                    options=available_printers if available_printers else printers,
                    help="使用中ではない機械が優先表示されます。",
                )

            use_new_user = st.checkbox("新しい使用者名を追加して登録する")
            if use_new_user:
                user_name = st.text_input("新しい使用者名", placeholder="例: 野山")
            else:
                user_name = st.selectbox("使用者名", options=users)

            print_name = st.text_input("印刷物名", placeholder="例: ローバ部品ケース")
            planned_minutes = st.number_input("印刷予定時間（分）", min_value=1, max_value=24 * 60, value=120, step=10)
            use_custom_start = st.checkbox("開始時刻を手動入力する")

            if use_custom_start:
                today = datetime.now()
                start_date = st.date_input("開始日", value=today.date())
                start_clock = st.time_input("開始時刻", value=today.time().replace(second=0, microsecond=0))
                start_time = datetime.combine(start_date, start_clock)
            else:
                start_time = datetime.now().replace(second=0, microsecond=0)
                st.info(f"開始時刻は現在時刻を使用します: {start_time.strftime(TIME_FMT)}")

            submitted = st.form_submit_button("使用登録する", type="primary")

        if submitted:
            printer_id = (printer_id or "").strip()
            user_name = (user_name or "").strip()
            print_name = (print_name or "").strip()

            if not printer_id or not user_name or not print_name:
                st.error("機械名、使用者名、印刷物名は必須です。")
            elif printer_id in active_map:
                st.error(f"{printer_id} は現在使用中です。別の機械を選択してください。")
            else:
                printers, users, active_jobs = register_job(
                    printers=printers,
                    users=users,
                    active_jobs=active_jobs,
                    printer_id=printer_id,
                    user_name=user_name,
                    print_name=print_name,
                    planned_minutes=int(planned_minutes),
                    start_time=start_time,
                )
                save_state(printers, users, active_jobs, history)
                st.session_state["flash_message"] = f"{printer_id} の使用を登録しました。ダッシュボードに戻りました。"
                st.session_state["flash_type"] = "success"
                st.session_state["redirect_page"] = "ダッシュボード"
                st.rerun()

    # ------------------
    # 履歴ログ
    # ------------------
    elif page == "履歴ログ":
        st.markdown("### 使用履歴ログ")
        if history:
            rows = []
            for job in sorted(history, key=lambda x: x.get("logged_at", x["end_time"]), reverse=True):
                rows.append(
                    {
                        "記録日時": job.get("logged_at", job["end_time"]),
                        "使用者": job["user_name"],
                        "印刷物": job["print_name"],
                        "使用機械": job["printer_id"],
                        "印刷時間(分)": job["planned_minutes"],
                        "開始時刻": job["start_time"],
                        "終了時刻": job["end_time"],
                        "状態": job.get("status", "completed"),
                    }
                )
            history_df = pd.DataFrame(rows)
            st.dataframe(history_df, use_container_width=True, hide_index=True)
            csv = history_df.to_csv(index=False).encode("utf-8-sig")
            st.download_button("履歴CSVをダウンロード", data=csv, file_name="printer_history.csv", mime="text/csv")
        else:
            st.info("まだ履歴がありません。")

    # ------------------
    # 設定/マスタ管理
    # ------------------
    elif page == "設定/マスタ管理":
        st.markdown("### マスタ管理")
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("#### 機械一覧")
            st.dataframe(pd.DataFrame({"機械ID": printers}), hide_index=True, use_container_width=True)
            new_master_printer = st.text_input("機械を追加", placeholder="例: R6", key="new_master_printer")
            if st.button("機械を追加する"):
                new_master_printer = new_master_printer.strip()
                if not new_master_printer:
                    st.error("機械名を入力してください。")
                elif new_master_printer in printers:
                    st.warning("その機械名はすでに登録されています。")
                else:
                    printers.append(new_master_printer)
                    printers = sorted(set(printers))
                    save_state(printers, users, active_jobs, history)
                    st.success(f"{new_master_printer} を追加しました。")
                    st.rerun()

        with col2:
            st.markdown("#### 使用者一覧")
            st.dataframe(pd.DataFrame({"使用者名": users}), hide_index=True, use_container_width=True)

            new_master_user = st.text_input("使用者を追加", placeholder="例: 野山", key="new_master_user")
            if st.button("使用者を追加する"):
                new_master_user = new_master_user.strip()
                if not new_master_user:
                    st.error("使用者名を入力してください。")
                elif new_master_user in users:
                    st.warning("その使用者名はすでに登録されています。")
                else:
                    users.append(new_master_user)
                    users = sorted(set(users))
                    save_state(printers, users, active_jobs, history)
                    st.success(f"{new_master_user} を追加しました。")
                    st.rerun()

            st.markdown("##### 登録済み使用者の削除")
            if users:
                user_to_delete = st.selectbox(
                    "削除する使用者名を選択",
                    options=users,
                    key="delete_user_name",
                    help="現在使用中のデータに含まれていない使用者名のみ削除できます。",
                )

                delete_confirm_user = st.session_state.get("delete_confirm_user")
                target_is_active = user_is_active(user_to_delete, active_jobs)

                if target_is_active:
                    st.warning(
                        f"{user_to_delete} は現在使用中のデータに含まれているため、今は削除できません。"
                        " 先に対象の使用登録を終了または削除してください。"
                    )
                    if delete_confirm_user == user_to_delete:
                        st.session_state.pop("delete_confirm_user", None)
                elif delete_confirm_user == user_to_delete:
                    st.warning(f"使用者名『{user_to_delete}』を候補一覧から削除します。よろしいですか？")
                    confirm_col1, confirm_col2 = st.columns(2)
                    with confirm_col1:
                        if st.button("はい、使用者を削除する", type="primary"):
                            users, deleted = delete_user(user_to_delete, users, active_jobs)
                            st.session_state.pop("delete_confirm_user", None)
                            if deleted:
                                save_state(printers, users, active_jobs, history)
                                st.session_state["flash_message"] = f"使用者名『{user_to_delete}』を削除しました。"
                                st.session_state["flash_type"] = "success"
                            else:
                                st.session_state["flash_message"] = (
                                    f"使用者名『{user_to_delete}』は現在使用中のため削除できませんでした。"
                                )
                                st.session_state["flash_type"] = "warning"
                            st.rerun()
                    with confirm_col2:
                        if st.button("キャンセル", type="secondary"):
                            st.session_state.pop("delete_confirm_user", None)
                            st.rerun()
                else:
                    if st.button("選択した使用者を削除する", type="secondary"):
                        st.session_state["delete_confirm_user"] = user_to_delete
                        st.rerun()
            else:
                st.info("登録済みの使用者はいません。")

        st.markdown("### 保存ファイル")
        st.code(
            "\n".join(
                [
                    f"- {PRINTERS_FILE.name}: 機械一覧",
                    f"- {USERS_FILE.name}: 使用者一覧",
                    f"- {ACTIVE_FILE.name}: 現在使用中の情報",
                    f"- {HISTORY_FILE.name}: 過去ログ",
                ]
            )
        )

        st.info(
            "Streamlit Community Cloud でもそのまま動かしやすい構成ですが、"
            "クラウド環境ではファイル保存が永続化されない場合があります。"
            "本格運用では Google Sheets / Supabase / SQLite などへの移行がおすすめです。"
        )


if __name__ == "__main__":
    main()
