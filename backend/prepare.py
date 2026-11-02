"""Prepare config, identical BQ schemas and UI from existing local sources."""
import json
import shutil
from pathlib import Path
from common import ROOT, write, read

source = ROOT.parent/'naresome-kikaku-research-ci-fix-20260915'
catalog = json.loads((ROOT/'data/catalog.js').read_text(encoding='utf-8').removeprefix('window.RESEARCH_DATA = ').strip().rstrip(';'))
selected = sorted([c for c in catalog['channels'] if c['role'] in ('benchmark','competitor')],key=lambda c:c['priority'])
config = {'project':'rugged-destiny-408613','dataset':'zunda_all','location':'asia-northeast1','bucket':'senior-share-staging-570862915709','gcs_prefix':'zunda_research','site_url':'https://japonismy.github.io/zunda-kikaku-research/','min_duration_seconds':120,'inactive_days':45,'max_youtube_requests':180,'max_videos':3000,'channels':[{'channel_id':c['id'],'channel_name':c['name'],'priority':c['priority'],'category':'direct_a' if c['role']=='benchmark' else 'direct_b','reason':c['reason']} for c in selected], 'excluded_names':['Japan応援隊','じゃぱん応援隊'],'cloud_activation':'pending_cost_approval','ocr_activation':'pending_separate_cost_approval'}
write(ROOT/'backend/config.json',config)
schemas = {}
for path in (ROOT/'reports/infrastructure').glob('naresome_all__*.json'):
    name = path.stem.split('__')[1]
    schemas[name] = read(path)['schema']['fields']
schemas['videos_archive'] = schemas['videos']
write(ROOT/'backend/schemas.json',schemas)
# Preserve the earlier lightweight site as a rollback; it is not deployed.
backup = ROOT/'reports/before_equivalent_site'
backup.mkdir(parents=True, exist_ok=True)
for name in ('index.html','app.js','styles.css'):
    if not (backup/name).exists():
        shutil.copy2(ROOT/name,backup/name)
html = (source/'index.html').read_text(encoding='utf-8')
html = html.replace('馴れ初め企画リサーチ','ずんだもん企画リサーチ').replace('馴れ初め 企画リサーチ','ずんだもん 企画リサーチ')
html = html.replace('例: 双子姉妹 美人母 再会','例: 中国撤退 コマツ 半導体').replace('例: お見合い 幼馴染 再会','例: 中国撤退 コマツ 半導体')
html = html.replace('<option value="date_desc">','<option value="date_desc" selected>')
# Add a visible, factual source status. Never imply an unconnected DB is live.
html = html.replace('<div class="status" id="status" aria-live="polite"></div>', '<div class="status" id="status" aria-live="polite"></div><div class="status" id="pipelineStatus"></div>')
html = html.replace('    init();', '    init();\n    const pipeline = window.PIPELINE_STATUS || {};\n    document.getElementById("pipelineStatus").textContent = pipeline.public_label || "";')
html = html.replace('<script src="data/channels.js"></script>','<script src="data/pipeline_status.js"></script>\n  <script src="data/channels.js"></script>')
# Metadata missing counts remain unknown instead of becoming invented zeros.
html = html.replace('v.observed_like_count || v.like_count || 0','v.observed_like_count ?? v.like_count ?? null').replace('v.observed_comment_count || v.comment_count || 0','v.observed_comment_count ?? v.comment_count ?? null')
html = html.replace('return Number(v.observed_like_count ?? v.like_count ?? null);','return v.observed_like_count ?? v.like_count ?? null;').replace('return Number(v.observed_comment_count ?? v.comment_count ?? null);','return v.observed_comment_count ?? v.comment_count ?? null;')
html = html.replace('v.script_asset_available || v.script_csv_url || transcriptById.has(v.video_id)', 'v.script_asset_available || v.script_csv_url || (transcriptById.has(v.video_id) && transcriptById.get(v.video_id).source !== "youtube_description")')
html = html.replace('fmt.format(likes)', '(likes == null ? "未取得" : fmt.format(likes))').replace('fmt.format(comments)', '(comments == null ? "未取得" : fmt.format(comments))')
html = html.replace('return views ? Number(count || 0) / Number(views || 0) : 0;', 'return count == null ? -1 : views ? Number(count) / Number(views) : 0;')
html = html.replace('return `${(rateValue(count, views) * 100).toFixed(2)}%`;', 'return count == null ? "未取得" : `${(rateValue(count, views) * 100).toFixed(2)}%`;')
html = html.replace('冒頭ダイジェスト', '概要欄・保存字幕ダイジェスト')
(ROOT/'index.html').write_text(html,encoding='utf-8')
print(json.dumps({'schemas':list(schemas),'channels':len(selected),'source_ui':str(source/'index.html')},ensure_ascii=True))
