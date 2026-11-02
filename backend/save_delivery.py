"""Save the completed cloud pipeline and its evidence to G: and the Vault."""
import csv
import json
import shutil
import hashlib
from pathlib import Path
from common import ROOT, read, write, table, config, now

cfg=config();build=read(ROOT/'reports/equivalent_build.json');cost=read(ROOT/'reports/cost_ledger.json');manifest=read(ROOT/'data/thumbnail_manifest.json')
for vid,info in manifest.items():
    source=ROOT/'assets/thumbnails'/(vid+'.jpg')
    if hashlib.sha256(source.read_bytes()).hexdigest()!=info['sha256']:raise RuntimeError('Final public-copy hash mismatch: '+vid)
    target=ROOT/'data_sources/assets/thumbnails'/(vid+'.jpg')
    if not target.exists():shutil.copy2(source,target)
full_manifest=[{'video_id':vid,**info} for vid,info in manifest.items()]
write(ROOT/'reports/thumbnail_manifest.json',full_manifest)
archive={'observed_at':now(),'saved':len(manifest),'failed':0,'bytes':sum(r['bytes'] for r in manifest.values()),'original_bytes_preserved':True,'all_local_sha256_verified':True,'gcs_prefix':cfg['gcs_prefix'],'public_delivery':'GitHub Pages'}
write(ROOT/'reports/thumbnail_archive.json',archive)
report=f'''# ずんだもん：取得・保存・表示の本番接続

更新：{now()}

公開サイト：https://japonismy.github.io/zunda-kikaku-research/

## 完了した構成

YouTube API → Cloud Run → BigQueryの現在値・日次履歴 → GCSへサムネ保全 → GitHub ActionsでDBからサイト用データ生成 → GitHub Pages表示。
馴れ初めのindex.htmlと表示データ契約を移植し、タイトル・サムネ文字・タグ検索、尺・公開日・再生数・資産状態などの絞り込み、再生数・高評価・コメント等の並べ替え、詳細・CSVに対応。

- 対象は直接競合7ch。指定の4チャンネルを先頭に配置。Japan応援隊は除外。
- BigQueryの公開メタデータ2,283本、120秒以上の表示2,274本。
- サムネ2,274枚をGCSへ保全し、同一バイトの画像を公開用に保存。高解像度URLで失敗した3件はHQ URLへ取得先を変えて1回だけ補完。全公開用コピーのSHA256を照合済み。
- 保存済みOCR69件を再利用。有料OCR・生成AIは未使用。
- 保存字幕・台本を新たに生成したものではない。script_assetsは受け皿。概要欄ダイジェストを台本と扱わない。

## 毎日の取得・保存・表示

03:20 JST：Cloud Scheduler → Cloud Run Job zunda-daily-metadata。
全uploadsを取得し、BigQuery zunda_all の現在値・日次履歴を保存。削除・非公開になっても最後の観測値を消さない。新しいサムネをGCSへ保全。

03:50 JST：GitHub Actions update-data.yml。
BigQueryから無料のtabledata.listで読み出してPythonで結合し、channels.js / videos.js / transcripts_light.js等を生成。不足画像だけ上限付きで取得し、Pagesへ反映。

Project：rugged-destiny-408613
Dataset：zunda_all / asia-northeast1
テーブル：channels, videos, channel_snapshots, video_snapshots, videos_archive, thumbnail_assets, thumbnail_ocr, script_assets, youtube_metadata_update_runs
GCS：gs://senior-share-staging-570862915709/zunda_research/thumbnails/

元の馴れ初めDBへずんだもん動画を混ぜず、専用datasetとprefixで分離。元の馴れ初めデータと日次ジョブは変更していない。

## 実行と検証

- Cloud Build成功：912f94af-2e2c-4fa5-ad93-3959b535e785。1回、30秒。
- Cloud Run成功：zunda-daily-metadata-57rsp。実行ログ上の取得・保存は32秒、エラー0。
- 初回クラウド実行で新しい動画3本を検出しDBへ反映。
- GitHubの鍵なし認証→BQ読み取り→画像差分→再生成→公開も成功。
- ワークフロー：https://github.com/japonismy/zunda-kikaku-research/actions/runs/41422847523
- バックエンド9件、ヘッドレスブラウザの動作確認を実施。最新結果はブラウザ検証.json。

GitHub認証はリポジトリとmainブランチに限定したWorkload Identity Federation。サービスアカウント鍵の作成0件。YouTube APIキーと承認内容はSecret Manager参照。ページに認証情報は置かない。

## 費用と期限

ユーザー明示承認：初期構築＋30日分、総額300円以内。
対象期間：2026-11-02〜2026-12-01。Cloud Run最大30実行（初回実測を含む）、1CPU・512MiB・600秒、再試行0。
最終日の成功後に専用Schedulerを削除し、期間終了後はサイト再生成workflowも自己停止。

費用台帳の保守的な予約上限合計：{cost['estimated_used_and_reserved_jpy']:.2f}円。300円までの未予約残額：{cost['remaining_task_cap_jpy']:.2f}円。
**予約額は、将来の30日分の処理・保管も含む安全側の上限であり、支払済み金額ではない。実請求は未確定・未反映分あり。**

GCSは保全庫、公開配信はGitHub Pages。閲覧数に比例するGCS配信費を発生させない。初期画像はローカル原本を再利用し、以降のGCS取得は1回20枚、期間合計600MiB以内。
Pagesの一時artifactは公開成功後に削除。取得・保存・再生成の各処理を上限管理し、請求反映や予算アラートを停止判断に使わない。
更新を止めてもクラウド保管物の保存費は残るため、延長・整理時は承認範囲、残予算、保存方針を確認する。

公式料金根拠：
- https://cloud.google.com/bigquery/pricing
- https://cloud.google.com/storage/pricing
- https://cloud.google.com/run/pricing
- https://cloud.google.com/build/pricing
- https://cloud.google.com/scheduler/pricing
- https://docs.github.com/en/billing/concepts/product-billing/github-actions

## 保存先

実装：E:\\Data\\ObsidianVault\\04_Tools\\zunda-kikaku-research
ローカルDB：同フォルダ data_sources/warehouse/
原寸サムネ原本：同フォルダ data_sources/assets/thumbnails/
公開用コピー：同フォルダ assets/thumbnails/

原本、承認、費用台帳、検証記録をこのフォルダへ保存。認証情報・APIキー・サービスアカウント鍵は含めない。
'''
destinations=[Path(r'G:\マイドライブ\Youtube事業\【ずんだもん】\02_運営者専用（共有しない）\02_リサーチ\02_候補チャンネル・ベンチマーク選定\20261102_馴れ初め同等構成'),Path(r'E:\Data\ObsidianVault\02_Channels\ずんだもん\research\20261102_馴れ初め同等構成')]
for dest in destinations:
    dest.mkdir(parents=True,exist_ok=True)
    (dest/'00_仕組みの移植と現在の状態.md').write_text(report,encoding='utf-8-sig')
    for source,name in [(ROOT/'backend/README.md','構成と手順.md'),(ROOT/'backend/config.json','対象台帳と設定.json'),(ROOT/'backend/schemas.json','BigQueryテーブル定義.json'),(ROOT/'reports/cloud_receipt.json','BigQuery登録・読出し確認.json'),(ROOT/'reports/infrastructure/summary.json','既存本番の構成確認.json'),(ROOT/'reports/equivalent-browser-check.json','ブラウザ検証.json'),(ROOT/'reports/thumbnail_archive.json','サムネ保存結果.json'),(ROOT/'reports/thumbnail_manifest.json','サムネSHA256台帳.json'),(ROOT/'reports/cost_ledger.json','費用台帳.json'),(ROOT/'reports/daily_activation.json','日次ジョブ実行・有効化.json'),(ROOT/'backend/deployment_state.json','本番構成の状態.json'),(ROOT/'data_sources/warehouse/videos.json','BigQuery現在値_動画.json'),(ROOT/'data_sources/warehouse/video_snapshots.json','BigQuery観測履歴_動画.json'),(ROOT/'data_sources/warehouse/youtube_metadata_update_runs.json','BigQuery日次実行履歴.json')]:shutil.copy2(source,dest/name)
    with (dest/'直接競合チャンネル.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=['channel_id','channel_name','category','priority','reason']);writer.writeheader();writer.writerows(cfg['channels'])
print(json.dumps({'destinations':[str(p) for p in destinations],'display_videos':build['videos'],'preserved_thumbnails':len(manifest),'cloud_connected':True},ensure_ascii=True))
