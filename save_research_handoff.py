"""Save reviewable channel roster, video CSV, evidence and report locally."""
import csv
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
catalog = json.loads((HERE/'data/catalog.js').read_text(encoding='utf-8').removeprefix('window.RESEARCH_DATA = ').strip().rstrip(';'))
destinations = [
    Path(r'G:\マイドライブ\Youtube事業\【ずんだもん】\02_運営者専用（共有しない）\02_リサーチ\02_候補チャンネル・ベンチマーク選定\20261102_直接競合リサーチサイト'),
    Path(r'E:\Data\ObsidianVault\02_Channels\ずんだもん\research\20261102_直接競合リサーチサイト'),
]
channels = [c for c in catalog['channels'] if c['role'] in ('benchmark', 'competitor')]
videos = [v for v in catalog['videos'] if v['role'] in ('benchmark', 'competitor')]
report = '''# ずんだもん：直接競合リサーチサイト

更新日：2026-11-02

公開URL：https://japonismy.github.io/zunda-kikaku-research/

参考：https://japonismy.github.io/naresome-kikaku-research/

直接競合7チャンネルの動画375本を収録。通常表示では総集編を除いた361本。
指定の4チャンネルを先頭に並べ、初期表示・条件リセットとも直接競合だけを対象にする。
タイトル・保存済みサムネ文字での検索、公開時期・再生数・題材の絞り込み、再生数・公開日・中央値比等の並べ替え、最大4本の比較、CSV出力に対応。
既存のネタ元候補・形式参考は明示的な切り替え時だけ表示。Japan応援隊／じゃぱん応援隊は収録しない。

## 直接競合

|チャンネル|区分|通常動画数|YouTube|
|---|---|---:|---|
'''
for c in channels:
    report += f"|{c['name']}|{'指定ベンチマーク' if c['role']=='benchmark' else '追加直接競合'}|{c['sampleSize']}|{c['url']}|\n"
report += '''
## 選定と表記確認

- 新規チャンネルの方針は、既存の「現行チャンネル戦略と制作方針」（2026-10-11）を参照。国際情勢・企業・技術・住宅等を、日本との比較と人物の会話で理解できる作品。
- 追加候補は「20260927_れもん調査_一次分析.md」の会話劇比較先を参照。ニッポンすんだ村・天子のワダイ・えだまめじゃぽんは題材と会話劇形式が近いと判断した。視聴者の実測重複を確認したものではない。
- 提示URL @tenko-topic は天子のワダイ。世界まる見えずんだもんは UCXzt6u4VooLQcyc3-yIFIcw として別途収録。
- 「ずんだ実は」は公開名「ずんだ実話」、「ずんだ観測所／ずんだ社会観察所」は既存記録のチャンネルID UCEaNC-I0as6FhFHzBgWDxMw の公開名「すんだ観察所」に照合。
- 低再生側の比較資料だった裏中国統計局・中国アナトミアは形式参考に変更し、直接競合の初期表示から外した。

## 収録範囲と数値

2026-11-02のYouTube公開メタデータ。各チャンネルの直近50投稿と既存収録を統合し、180秒以下とライブを除外。全動画を網羅する取得ではない。サムネはYouTube公開画像を表示し、今回新規のOCRや本文解析は実行していない。
参考資料を含む全収録は563本。参考チャンネルの観測日は従来の2026-10-02等のまま。動画カードに各観測日を表示。
中央値比の対象は収録通常動画のみ。公開後平均再生／日は累計÷日数で、直近の速度ではない。複数観測のある動画だけ観測間の増加／日を算出。CTR・維持率・月間再生数は取得していない。
企画候補メモはブラウザ内保存で、JSONで移行可能。クラウド同期はない。

## 費用と検証

無料のYouTube Data API listクォータ16リクエスト。search.list・有料API・生成AI・OCR・BigQuery・追加クレジットは未使用。有料処理0件、追加費用0円、未確定の有料処理なし。
同日のデータ再整形は保存済みスナップショットで実行。定期実行は設定していない。
専用のヘッドレスChromeによる25項目のブラウザ確認が成功。検索・初期の直接競合限定・指定4チャンネル・世界まる見え追加・除外・比較上限・メモ保存・再読込・モバイル幅・実行時エラー等を確認。

## 保存物

- 直接競合チャンネル.csv：選定対象・ID・YouTube URL・理由・観測日・サンプル数
- 直接競合動画.csv：タイトル・チャンネル・公開日・再生数・観測日・尺・URL
- 公開メタデータ原本.json：今回の取得根拠。内部保管用でサイトへ配信しない。
- ブラウザ検証.json：動作確認記録

実装・更新スクリプト：E:\\Data\\ObsidianVault\\04_Tools\\zunda-kikaku-research
'''
for destination in destinations:
    destination.mkdir(parents=True, exist_ok=True)
    (destination/'00_直接競合リサーチサイト.md').write_text(report, encoding='utf-8-sig')
    for filename, rows, fields in [
        ('直接競合チャンネル.csv', channels, ['name','role','id','url','reason','sampleSize','medianViews','subscribers','observed']),
        ('直接競合動画.csv', [{**v,'url':f"https://www.youtube.com/watch?v={v['id']}"} for v in videos], ['id','title','channel','role','published','views','observed','seconds','compilation','url']),
    ]:
        with (destination/filename).open('w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore'); writer.writeheader(); writer.writerows(rows)
    shutil.copy2(HERE/'data_sources/direct_2026-11-02.json', destination/'公開メタデータ原本.json')
    shutil.copy2(HERE/'reports/browser-check.json', destination/'ブラウザ検証.json')
print(json.dumps({'saved': [str(p) for p in destinations], 'channels': len(channels), 'videos': len(videos)}, ensure_ascii=True))
