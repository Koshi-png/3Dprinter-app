from __future__ import annotations

import json
import os
import shutil
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

# =========================================================
# 3Dプリンター使用状況管理アプリ
# - JSON 永続化
# - 機械IDは配置図に合わせて R1-R5, B1-B4 を初期登録
# - 再読み込み・時間経過後の再オープンでも状態が消えにくいように
#   保存先をユーザー領域へ分離し、原子的に保存する
# =========================================================

APP_TITLE = "3Dプリンター使用状況ダッシュボード"
BASE_DIR = Path(__file__).parent
LEGACY_DATA_DIR = BASE_DIR / "data"
ASSET_DIR = BASE_DIR / "assets"
LAYOUT_IMAGE = ASSET_DIR / "layout-1.png"
TIME_FMT = "%Y-%m-%d %H:%M"
DATA_DIR_ENV = "PRINTER_APP_DATA_DIR"
APP_DATA_SUBDIR = ".printer_dashboard_data"

DEFAULT_PRINTERS = ["R1", "R2", "R3", "R4", "R5", "B1", "B2", "B3", "B4"]
DEFAULT_USERS = ["田中", "佐藤", "鈴木", "山田"]


def get_data_dir() -> Path:
    """保存先ディレクトリを返す。

    優先順位:
    1. 環境変数 PRINTER_APP_DATA_DIR
    2. ユーザーホーム配下の .printer_dashboard_data

    これにより、アプリ本体のフォルダ差し替えや再起動の影響を受けにくくする。
    """
    custom_dir = os.environ.get(DATA_DIR_ENV, "").strip()
    if custom_dir:
        return Path(custom_dir).expanduser().resolve()
    return (Path.home() / APP_DATA_SUBDIR).resolve()


DATA_DIR = get_data_dir()
PRINTERS_FILE = DATA_DIR / "printers.json"
USERS_FILE = DATA_DIR / "users.json"
ACTIVE_FILE = DATA_DIR / "active_jobs.json"
HISTORY_FILE = DATA_DIR / "history.json"
DATA_FILES = [PRINTERS_FILE, USERS_FILE, ACTIVE_FILE, HISTORY_FILE]


# ---------------------------
# データ入出力
# ---------------------------
def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def atomic_write_json(path: Path, data: Any) -> None:
    """JSON を一時ファイル経由で保存する。

    途中でアプリが再実行・終了しても、空ファイルや破損ファイルになりにくいようにする。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", delete=False, dir=str(path.parent), encoding="utf-8") as tmp:
        json.dump(data, tmp, ensure_ascii=False, indent=2)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp_name = tmp.name
    os.replace(tmp_name, path)


def write_json(path: Path, data: Any) -> None:
    atomic_write_json(path, data)


def create_backup(path: Path) -> None:
    if path.exists():
        backup_path = path.with_suffix(path.suffix + ".bak")
        shutil.copy2(path, backup_path)


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        write_json(path, default)
        return default

    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        # 破損していても即初期化せず、バックアップからの復旧を試みる
        backup_path = path.with_suffix(path.suffix + ".bak")
        if backup_path.exists():
            with backup_path.open("r", encoding="utf-8") as f:
                recovered = json.load(f)
            write_json(path, recovered)
            return recovered
        write_json(path, default)
        return default


# ---------------------------
# 永続化の初期化 / 移行
# ---------------------------
def legacy_file_for(path: Path) -> Path:
    return LEGACY_DATA_DIR / path.name


def migrate_legacy_data_if_needed() -> None:
    """旧保存先(BASE_DIR/data)から新保存先へデータを移行する。"""
    ensure_data_dir()
    for current_path in DATA_FILES:
        legacy_path = legacy_file_for(current_path)
        if not current_path.exists() and legacy_path.exists():
            shutil.copy2(legacy_path, current_path)


def bootstrap_persistent_data() -> None:
    """初回のみ保存ファイルを作成する。

    以前の実装では、アプリ起動ごとに sample 初期化関数を通していたため、
    保存先が消えた/変わったときに初期状態へ戻りやすかった。
    ここでは、保存ファイルが存在しない時だけ最小限の初期データを作る。
    """
    ensure_data_dir()
    migrate_legacy_data_if_needed()

    if not PRINTERS_FILE.exists():
        write_json(PRINTERS_FILE, DEFAULT_PRINTERS)
    if not USERS_FILE.exists():
        write_json(USERS_FILE, DEFAULT_USERS)
    if not ACTIVE_FILE.exists():
        write_json(ACTIVE_FILE, [])
    if not HISTORY_FILE.exists():
        write_json(HISTORY_FILE, [])

    # 初回起動時だけサンプルを入れるためのマーカー
    first_run_marker = DATA_DIR / ".seeded"
    if not first_run_marker.exists():
        printers = read_json(PRINTERS_FILE, DEFAULT_PRINTERS)
        users = read_json(USERS_FILE, DEFAULT_USERS)
        active_jobs = read_json(ACTIVE_FILE, [])
        history = read_json(HISTORY_FILE, [])

        if not active_jobs and not history:
            now = datetime.now().replace(second=0, microsecond=0)
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
            save_state(printers, users, active_jobs, history)

        first_run_marker.write_text("seeded", encoding="utf-8")


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
def normalize_state(
    printers: Any,
    users: Any,
    active_jobs: Any,
    history: Any,
) -> tuple[list[str], list[str], list[dict[str, Any]], list[dict[str, Any]]]:
    printers = [str(x).strip() for x in (printers or []) if str(x).strip()]
    users = [str(x).strip() for x in (users or []) if str(x).strip()]
    active_jobs = [x for x in (active_jobs or []) if isinstance(x, dict)]
    history = [x for x in (history or []) if isinstance(x, dict)]

    if not printers:
        printers = DEFAULT_PRINTERS[:]
    if not users:
        users = DEFAULT_USERS[:]

    return sorted(set(printers)), sorted(set(users)), active_jobs, history


def load_state() -> tuple[list[str], list[str], list[dict[str, Any]], list[dict[str, Any]]]:
    printers = read_json(PRINTERS_FILE, DEFAULT_PRINTERS)
    users = read_json(USERS_FILE, DEFAULT_USERS)
    active_jobs = read_json(ACTIVE_FILE, [])
    history = read_json(HISTORY_FILE, [])
    return normalize_state(printers, users, active_jobs, history)


def save_state(
    printers: list[str],
    users: list[str],
    active_jobs: list[dict[str, Any]],
    history: list[dict[str, Any]],
) -> None:
    printers, users, active_jobs, history = normalize_state(printers, users, active_jobs, history)

    # 直前状態を簡易バックアップ
    for path in DATA_FILES:
        create_backup(path)

    write_json(PRINTERS_FILE, printers)
    write_json(USERS_FILE, users)
    write_json(ACTIVE_FILE, active_jobs)
    write_json(HISTORY_FILE, history)


def archive_finished_jobs(
    active_jobs: list[dict[str, Any]], history: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], bool]:
    now = datetime.now().replace(second=0, microsecond=0)
    remaining_active = []
    updated_history = history[:]
    changed = False

    history_ids = {job["job_id"] for job in history if "job_id" in job}

    for job in active_jobs:
        end_time = parse_dt(job["end_time"])
        if end_time <= now:
            changed = True
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
    return remaining_active, updated_history, changed


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


def finish_job(
    printer_id: str, active_jobs: list[dict[str, Any]], history: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
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

    bootstrap_persistent_data()
    printers, users, active_jobs, history = load_state()

    # 予定終了を過ぎたものは自動で履歴へ移動
    active_jobs, history, archived_changed = archive_finished_jobs(active_jobs, history)
    if archived_changed:
        save_state(printers, users, active_jobs, history)

    with st.sidebar:
        st.header("管理メニュー")

        if "auto_refresh_enabled" not in st.session_state:
            st.session_state["auto_refresh_enabled"] = False

        auto_refresh = st.toggle(
            "自動更新を有効化",
            value=st.session_state["auto_refresh_enabled"],
            key="auto_refresh_toggle",
        )
        st.session_state["auto_refresh_enabled"] = auto_refresh

        if auto_refresh:
            st.caption("30秒ごとに保存済みデータを再読込します。")
            st.markdown(
                """
                <script>
                setTimeout(function(){ window.location.reload(); }, 30000);
                </script>
                """,
                unsafe_allow_html=True,
            )

        if st.button("データを初期サンプル状態に戻す"):
            for path in DATA_FILES:
                if path.exists():
                    path.unlink()
                backup_path = path.with_suffix(path.suffix + ".bak")
                if backup_path.exists():
                    backup_path.unlink()
            marker = DATA_DIR / ".seeded"
            if marker.exists():
                marker.unlink()
            bootstrap_persistent_data()
            st.success("サンプルデータを再生成しました。ページを再読み込みしてください。")

        st.divider()
        st.write("**登録済み機械**")
        st.write(", ".join(printers))
        st.write("**登録済み使用者**")
        st.write(", ".join(users))

        st.divider()
        st.caption(f"保存先: {DATA_DIR}")

    tab1, tab2, tab3, tab4 = st.tabs(["ダッシュボード", "使用登録", "履歴ログ", "設定/マスタ管理"])

    # ------------------
    # ダッシュボード
    # ------------------
    with tab1:
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

        st.markdown("### 手動で終了登録")
        busy_printers = sorted([job["printer_id"] for job in active_jobs])
        if busy_printers:
            finish_printer = st.selectbox("終了する機械を選択", options=busy_printers, key="finish_printer")
            if st.button("選択した機械を終了扱いにする", type="secondary"):
                active_jobs, history = finish_job(finish_printer, active_jobs, history)
                save_state(printers, users, active_jobs, history)
                st.success(f"{finish_printer} を終了登録しました。")
                st.rerun()
        else:
            st.info("終了登録が必要な使用中機械はありません。")

    # ------------------
    # 使用登録
    # ------------------
    with tab2:
        st.markdown("### 新しい印刷ジョブを登録")
        active_map = get_active_job_map(active_jobs)
        available_printers = [p for p in printers if p not in active_map]

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
        start_time = datetime.now().replace(second=0, microsecond=0)
        st.caption(f"開始時刻は現在時刻を自動入力します: {start_time.strftime(TIME_FMT)}")
        st.caption(f"終了予定時刻: {(start_time + timedelta(minutes=int(planned_minutes))).strftime(TIME_FMT)}")

        if st.button("使用登録する", type="primary"):
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
                st.success(f"{printer_id} の使用を登録しました。")
                st.rerun()

    # ------------------
    # 履歴ログ
    # ------------------
    with tab3:
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
    with tab4:
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

        st.markdown("### 保存ファイル")
        st.code(
            "\n".join(
                [
                    f"保存先ディレクトリ: {DATA_DIR}",
                    f"- {PRINTERS_FILE.name}: 機械一覧",
                    f"- {USERS_FILE.name}: 使用者一覧",
                    f"- {ACTIVE_FILE.name}: 現在使用中の情報",
                    f"- {HISTORY_FILE.name}: 過去ログ",
                ]
            )
        )

        st.info(
            "今回の修正では、データ保存先をアプリ本体フォルダから分離し、"
            "再読み込み時は保存済みJSONを読み直す構成に変更しています。"
        )


if __name__ == "__main__":
    main()
