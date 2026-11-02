# ずんだもん 企画リサーチ

公開URL：https://japonismy.github.io/zunda-kikaku-research/

馴れ初め版の「YouTube取得→BigQueryで現在値と日次履歴を保存→資産を動画IDで結合→サイト用データ生成→GitHub Pages表示」を、ずんだもん専用領域へ移植。

2026-11-02にクラウド登録と実行を完了。直接競合7ch、公開メタデータ2,283本、120秒以上の表示2,274本、保全サムネ2,274枚。既存OCR69本を再利用。追加の有料OCR・生成AIは実行していない。

## 更新経路

1. 毎日03:20 JST、Cloud SchedulerがCloud Run Job `zunda-daily-metadata`を起動。
2. 全uploadsをページ末尾まで取得し、BigQuery `rugged-destiny-408613.zunda_all` の現在値と日次履歴を更新。
3. 新しいサムネをGCS `gs://senior-share-staging-570862915709/zunda_research/thumbnails/` へ保全。
4. 毎日03:50 JST、GitHub ActionsがBigQueryを無料のtabledata.listで読み、Pythonで動画・チャンネル・履歴・OCR・画像・字幕資産を結合。
5. 新しい保全画像だけを上限付きで取得し、静的JSと画像をGitHub Pagesへ公開。公開ページの閲覧時にはBigQueryもGCSも直接呼ばない。

GCSは保全庫、画像配信はGitHub Pages。閲覧数に比例するGCS転送費を避ける。初期画像はローカル保全原本を同一バイトで再利用。以降のGCS読み出しは1回20枚・承認期間合計600MiB以内。

## 保存先と認証

- DB：`rugged-destiny-408613.zunda_all`。馴れ初めのDBへ混入させない。
- テーブル：channels / videos / channel_snapshots / video_snapshots / videos_archive / thumbnail_assets / thumbnail_ocr / script_assets / youtube_metadata_update_runs。
- GitHubのDB読み取りは、リポジトリとmainブランチに限定したWorkload Identity Federation。サービスアカウント鍵は作成・配置しない。
- Cloud Runは専用サービスアカウント、YouTube APIキーと承認内容はSecret Managerの参照で渡す。
- 台本・字幕を新規生成したものではない。script_assetsは既存資産の受け皿。概要欄ダイジェストを台本として扱わない。

## 費用と稼働期間

ユーザーの明示承認：初期構築＋30日分、総額300円以内。有料OCR・生成AI・無制限のGCS画像配信は対象外。

稼働対象日は2026-11-02〜2026-12-01。Cloud Runは1CPU・512MiB・600秒上限、再試行0、成功済み同日の二重更新を防止。最終日の成功後に専用Schedulerを削除し、サイト再生成も期間終了後に自己停止する。

費用台帳は非公開のreports/cost_ledger.json。保守的な予約額と確定請求を区別し、請求反映を待たず送信前に上限を管理する。停止後もクラウド保管物の保存費は残るため、継続時は台帳と保存方針を確認する。

## 検証

Cloud Run実行 `zunda-daily-metadata-57rsp` 成功。GitHubのDB読み出し・画像差分取得・再生成・公開ワークフローも成功。バックエンド9件、専用ヘッドレスChromeで20項目を確認。

[構成と運用手順](backend/README.md)

実装保存先：E:\Data\ObsidianVault\04_Tools\zunda-kikaku-research

原本・承認ファイル・ローカルDBミラー・検証記録はdata_sourcesとreportsへ保存し、GitHubへ公開しない。app.js / styles.css / catalog.js等の以前の表示版は移行元の記録で、現在の画面からは読み込まない。
