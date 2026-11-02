# ずんだもん 企画リサーチ

公開URL：https://japonismy.github.io/zunda-kikaku-research/

馴れ初め版の「YouTube取得→BigQueryで現在値と日次履歴を保存→資産を動画IDで結合→静的データ生成→GitHub Pages表示」を移植する。

2026-11-02時点：直接競合7chから公開メタデータ2,280本を取得、120秒以上の2,271本を公開データへ生成。既存OCR69本、過去観測367件を再利用。サムネ2,268枚・約521MiBをローカル保全。追加課金0円。

**BigQueryへの実データ保存、GCS転送、Cloud Run / Schedulerの新規作成と日次稼働は費用未承認のため未実行。表示成功をクラウド接続成功と扱わない。** 公開画面にも状態を表示する。

## 構成・手順

[backend/README.md](backend/README.md) に本番の調査結果、移植内容、9テーブル、起動手順、費用承認後の反映順序、現在の不足を記載。

- backend/config.json：7チャンネルの固定ID台帳。Japan応援隊は除外。
- backend/collect.py：全uploadsの取得、現在値、冪等な日次履歴、削除時の過去値保持。
- backend/cloud_sync.py：BigQueryへの登録計画、承認後の書き込み、無料プレビュー読み出し。
- backend/build_portal.py：動画・チャンネル・OCR・サムネ・字幕資産・観測履歴を結合して静的JSを生成。
- backend/archive_thumbnails.py / upload_assets.py：ローカル保全、承認後のGCS保存。
- backend/run_daily.py / Dockerfile / deploy.ps1：日次ジョブ。コード準備済み、未デプロイ。
- .github/workflows/update-data.yml：BigQueryからページ用データを再生成。現在は手動起動のみ。
- .github/workflows/pages.yml：公開ファイルだけをGitHub Pagesへ反映。

画面は馴れ初め版のindex.htmlを移植。サムネ・タイトル・タグの検索、チャンネル・尺・公開日・再生数・OCR・保全状態の絞り込み、高評価・コメント・再生数・公開日・中央値比等の並べ替え、詳細・CSVに対応。概要欄ダイジェストは保存字幕と区別する。

## ローカル検証

```powershell
python .\backend\collect.py --cached
python .\backend\build_portal.py
python -m unittest discover -s tests -p 'test_pipeline.py' -v
node .\tests\portal_browser_test.js
```

バックエンド9件・ブラウザ18件が成功。専用ヘッドレスChromeを使用し、既存ブラウザのフォーカスを操作しない。

## 以前の版

app.js / styles.css / data/catalog.js / refresh_direct.py / build_data.py / refresh_youtube.py / save_research_handoff.py / tests/browser_test.js は以前の表示・比較中心の版の記録。現在の公開画面からは読み込まない。現在の更新にはbackend配下を使う。catalog.jsは既存OCR・過去観測の移行元として保持する。

原本とローカルwarehouseはdata_sources、検証結果はreports。どちらもGitと公開ページには含めない。認証情報・承認ファイル・APIキーも公開しない。

実装保存先：E:\Data\ObsidianVault\04_Tools\zunda-kikaku-research
