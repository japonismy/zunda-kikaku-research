"""Save the architecture, import plan, evidence and validation to G: and Vault."""
import csv
import json
import shutil
from pathlib import Path
from common import ROOT, read, config

destinations=[Path(r'G:\マイドライブ\Youtube事業\【ずんだもん】\02_運営者専用（共有しない）\02_リサーチ\02_候補チャンネル・ベンチマーク選定\20261102_馴れ初め同等構成'),Path(r'E:\Data\ObsidianVault\02_Channels\ずんだもん\research\20261102_馴れ初め同等構成')]
build=read(ROOT/'reports/equivalent_build.json');images=read(ROOT/'reports/thumbnail_archive.json');plan=read(ROOT/'reports/cloud_import_plan.json');cfg=config()
report=f'''# ずんだもん：馴れ初めの取得・保存・表示を移植

2026-11-02。表示だけの前回版から作業範囲を修正した。

公開画面：https://japonismy.github.io/zunda-kikaku-research/

## 現在の実装と状態

- 対象：直接競合7ch。全公開アップロード一覧を走査し2,280本を取得。参考サイトと同じ120秒以上の表示条件で{build['videos']:,}本。
- メタデータ：タイトル、概要欄、公開日、尺、再生数、高評価、コメント、タグ。取得・保存・絞り込み・詳細表示へ接続。
- 履歴：当日スナップショット2,280行と既存の過去観測367行。再実行で同日行を二重計上せず、動画が消えても過去値を保持。
- OCR：既存69件を再利用。追加の有料OCRなし。
- サムネ：{images['saved']:,}枚、{images['bytes']:,}バイトをローカルへ原寸で保存。3件は失敗として記録。同一ファイルの再生成・画像加工はしていない。
- スキーマ：馴れ初め本番の定義から9テーブル。登録予定データ量は{plan['total_bytes']:,}バイト。
- 表示：馴れ初めのindex.htmlとJSデータ契約を移植。100件ずつ表示、サムネ・タイトル・タグ検索、チャンネル・尺・公開日・再生数・OCR・公開状態・資産状態の条件、再生数・高評価・コメント・率・中央値比等の並べ替え、詳細、CSVに対応。
- 試験：バックエンド9件、専用ヘッドレスChromeの18項目が成功。
- **BigQueryへの実登録・GCS転送・Cloud Run/Schedulerの実稼働は未実行。費用承認待ち。** 公開ページにも未接続と表示し、成功したと扱わない。

## 本番構成の調査

馴れ初めはrugged-destiny-408613.naresome_allを使用。Cloud Run Job naresome-daily-metadataとSchedulerは03:20 JST、GitHub Actionsのサイト更新は03:50 JST。
現在値はchannels/videos、履歴はchannel_snapshots/video_snapshots、OCRはthumbnail_ocr、画像はthumbnail_assets、字幕・台本はscript_assetsで動画ID結合。GCSへ画像・CSV等を保管し、公開ページは静的JSと資産URLを読む。
既存本番にSQL・有料解析・設定変更を送っていない。datasets/tablesのGET/LISTとCloud Run/Schedulerの構成GET/LISTのみで調査した。
ずんだもん版はzunda_allとzunda_research/を専用領域とし、馴れ初めへ混入させない。BigQueryからの読み出し・結合は無料のtabledata.listとローカルPythonで実装し、課金SQLを使わない。

## 構成と反映手順

詳細は「構成と手順.md」。API取得・同日キャッシュ、現在値と日次履歴、削除後保持、資産の格納、DBの読み出し、公開データ生成、Cloud Run設定、サイト再生成ワークフローをコードとして用意。
承認後はアカウントと保存クラス・リージョン等を照合し、BigQuery初期登録→GCS保全→資産URI登録→DBから再生成→Cloud Run→日次実行→公開実測確認の順に行う。未承認のサンプル承認ファイルでは書き込み前に拒否されることを確認済み。
script_assetsの受け皿はあるが、保存字幕・台本を新たに生成したものではない。概要欄を台本として扱わない。

## 費用承認案（未承認）

対象：BigQuery保存50MiB以内、GCS保存1GiB・3,000オブジェクト以内、Cloud Build1回20分以内、Cloud Run最大30日・1日1回・1CPU/512MiB/600秒・再試行0、Scheduler1件、関連するSecret/Artifact保存。
無料枠の残量を前提にせず、換算を1USD=170円と置く保守概算150〜220円。**初期構築と30日分の総額上限案300円**。有料OCR・生成AI・追加クレジットは含めない。現時点の追加課金0円・有料呼び出し0件。
GCSの不特定多数向け画像配信は、この保存・取得処理の見積に含めない。公開保全URLは転送量上限と配信方式を確定するまで有効化しない。
30日経過後の計算処理は承認更新まで継続しない。停止だけでは保存・Scheduler・Artifact等の維持費が消えないため、保存継続とジョブ維持／削除も実行前の承認条件として確定する。

公式料金根拠（2026-11-02確認）：

- BigQuery：https://cloud.google.com/bigquery/pricing
- GCS：https://cloud.google.com/storage/pricing
- Cloud Run：https://cloud.google.com/run/pricing
- Cloud Build：https://cloud.google.com/build/pricing
- Scheduler：https://cloud.google.com/scheduler/pricing

## 保存先

実装：E:\\Data\\ObsidianVault\\04_Tools\\zunda-kikaku-research
ローカルDBミラー：同フォルダのdata_sources/warehouse/
保存サムネ：同フォルダのdata_sources/assets/thumbnails/
認証・承認ファイル、原本、ローカルDB、レポートはGitHubへ公開しない。
'''
for dest in destinations:
    dest.mkdir(parents=True,exist_ok=True)
    (dest/'00_仕組みの移植と現在の状態.md').write_text(report,encoding='utf-8-sig')
    for source,name in [(ROOT/'backend/README.md','構成と手順.md'),(ROOT/'backend/config.json','対象台帳と設定.json'),(ROOT/'backend/schemas.json','BigQueryテーブル定義.json'),(ROOT/'reports/cloud_import_plan.json','BigQuery初期登録計画.json'),(ROOT/'reports/infrastructure/summary.json','既存本番の構成確認.json'),(ROOT/'reports/equivalent-browser-check.json','ブラウザ検証.json'),(ROOT/'reports/thumbnail_archive.json','サムネ保存結果.json'),(ROOT/'reports/thumbnail_manifest.json','サムネSHA256台帳.json'),(ROOT/'data_sources/full_youtube_2026-11-02.json','YouTube取得原本.json')]:shutil.copy2(source,dest/name)
    with (dest/'直接競合チャンネル.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=['channel_id','channel_name','category','priority','reason']);writer.writeheader();writer.writerows(cfg['channels'])
print(json.dumps({'destinations':[str(p) for p in destinations],'cloud_paid_calls':0},ensure_ascii=True))
