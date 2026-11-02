import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
import common
import collect
import cloud_sync

class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.patch=patch.object(common,'WAREHOUSE',Path(self.temp.name));self.patch.start();self.addCleanup(self.patch.stop)
        self.cfg=common.config();self.cid=self.cfg['channels'][0]['channel_id']
        self.channel={'id':self.cid,'snippet':{'title':'fixture','publishedAt':'2023-01-01T00:00:00Z'},'statistics':{'videoCount':'1','viewCount':'100'},'contentDetails':{'relatedPlaylists':{'uploads':'uploads'}}}
        self.video={'id':'testVideo01','snippet':{'channelId':self.cid,'title':'fixture','publishedAt':'2026-10-01T00:00:00Z','description':'digest','tags':['test']},'statistics':{'viewCount':'100'},'contentDetails':{'duration':'PT12M30S'}}
        self.status=patch.object(collect,'write');self.status.start();self.addCleanup(self.status.stop)
    def test_daily_snapshots_are_idempotent(self):
        collect.ingest([self.channel],[self.video],'2026-11-02T12:00:00+09:00',True)
        collect.ingest([self.channel],[self.video],'2026-11-02T13:00:00+09:00',True)
        self.assertEqual(len(common.table('video_snapshots')),1)
        self.assertEqual(len(common.table('channel_snapshots')),1)
    def test_new_day_keeps_history(self):
        collect.ingest([self.channel],[self.video],'2026-11-01T12:00:00+09:00',True)
        self.video['statistics']['viewCount']='200'
        collect.ingest([self.channel],[self.video],'2026-11-02T12:00:00+09:00',True)
        self.assertEqual([r['view_count'] for r in common.table('video_snapshots')],[100,200])
        self.assertEqual(common.table('videos')[0]['view_count'],200)
    def test_unavailable_video_keeps_last_value(self):
        collect.ingest([self.channel],[self.video],'2026-11-01T12:00:00+09:00',True)
        collect.ingest([self.channel],[],'2026-11-02T12:00:00+09:00',True)
        self.assertEqual(common.table('videos')[0]['view_count'],100)
    def test_missing_statistics_stay_unknown(self):
        collect.ingest([self.channel],[self.video],'2026-11-02T12:00:00+09:00',True)
        self.assertIsNone(common.table('videos')[0]['like_count'])
        self.assertIsNone(common.table('channels')[0]['subscriber_count'])
    def test_channel_outside_registry_is_rejected(self):
        with self.assertRaises(ValueError):common.validate_scope([{'channel_id':'UC-unapproved'}])
    def test_cloud_write_requires_explicit_approval(self):
        with patch.dict(os.environ,{'ZUNDA_COST_APPROVAL_FILE':''}):
            with self.assertRaisesRegex(RuntimeError,'Explicit cost approval'):cloud_sync.authorize('bigquery_storage')
    def test_example_is_not_authorization(self):
        with patch.dict(os.environ,{'ZUNDA_COST_APPROVAL_FILE':str(common.ROOT/'backend/cost_approval.example.json')}):
            with self.assertRaisesRegex(RuntimeError,'Explicit cost approval'):cloud_sync.authorize('bigquery_storage')
    def test_registry_is_exactly_selected_seven(self):
        self.assertEqual(len(self.cfg['channels']),7)
        self.assertTrue(any(c['channel_id']=='UCXzt6u4VooLQcyc3-yIFIcw' for c in self.cfg['channels']))
        self.assertFalse(any('応援隊' in c['channel_name'] for c in self.cfg['channels']))
    def test_bigquery_timestamps_roundtrip_in_local_mirror(self):
        common.save_table('youtube_metadata_update_runs',[{'run_id':'fixture','started_at':datetime(2026,11,2,tzinfo=timezone.utc)}])
        self.assertEqual(common.table('youtube_metadata_update_runs')[0]['started_at'],'2026-11-02T00:00:00+00:00')

if __name__=='__main__':unittest.main()
