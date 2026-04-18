# 3Dプリンター使用状況管理アプリ

Streamlit を用いた、3Dプリンターの使用状況を管理・可視化する Web アプリです。

## 主な機能
- 現在の空き / 使用中の一覧表示
- 使用者名、印刷物名、開始時刻、終了予定時刻、残り時間、進捗バー表示
- 新規使用登録
- 機械名 / 使用者名の追加登録
- 配置図表示
- 使用履歴ログ表示と CSV ダウンロード
- JSON による簡易永続保存

## ファイル構成
- `app.py` : アプリ本体
- `requirements.txt` : 必要ライブラリ
- `assets/layout-1.png` : 配置図画像
- `data/*.json` : 保存データ

## 実行方法
```bash
pip install -r requirements.txt
streamlit run app.py
```

## デプロイの考え方
Streamlit Community Cloud に配置する場合は、リポジトリに以下を含めてください。
- `app.py`
- `requirements.txt`
- `assets/layout-1.png`
- `data` フォルダ

注意: Community Cloud ではローカルファイル保存が永続化されない場合があります。
継続運用時は外部DBへの移行を推奨します。
