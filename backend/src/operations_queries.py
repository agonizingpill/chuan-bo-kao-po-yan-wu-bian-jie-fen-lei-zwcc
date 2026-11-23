"""Business queries over authoritative project records."""

from .operations_reconciliation import RECONCILIATION_VIEWS

from .berth_occupancy import VIEW as BERTH_OCCUPANCY

VIEWS = {
    'tide-reserve': (
        '潮汐窗口余量',
        '按靠泊申请计算吃水余度和预计操作结束时的剩余分钟数，帮助调度选出潮窗余量最小的申请。',
        ['申请', '船舶', '潮窗', '吃水余度 m', '潮窗余量 分', '复核建议'],
        """
SELECT r.code,r.vessel,w.code,w.max_draft_m-r.draft_m,
       TIMESTAMPDIFF(MINUTE,r.eta,w.ends_at)-r.maneuver_minutes AS window_margin,
       CASE WHEN r.draft_m>w.max_draft_m OR r.eta<w.starts_at OR TIMESTAMPDIFF(MINUTE,r.eta,w.ends_at)<r.maneuver_minutes THEN '重排潮窗' ELSE '余量可核对' END
FROM berth_requests r JOIN tide_windows w ON w.code=r.window_code ORDER BY window_margin,r.code
""",
    ),
    'tug-turnaround': (
        '拖轮交接间隔',
        '以同一拖轮的下个未释放任务为界计算可交接分钟数，少于 15 分钟进入调度核对。',
        ['拖轮', '当前申请', '下个申请', '当前结束', '下个开始', '间隔 分', '调度建议'],
        """
SELECT tug_code,request_code,next_request,ends_at,next_start,TIMESTAMPDIFF(MINUTE,ends_at,next_start),
       CASE WHEN TIMESTAMPDIFF(MINUTE,ends_at,next_start)<15 THEN '交接间隔不足' ELSE '正常周转' END
FROM (SELECT a.*,LEAD(request_code) OVER (PARTITION BY tug_code ORDER BY starts_at,id) AS next_request,
       LEAD(starts_at) OVER (PARTITION BY tug_code ORDER BY starts_at,id) AS next_start
       FROM tug_assignments a WHERE released_at IS NULL) sequence
WHERE next_start IS NOT NULL ORDER BY next_start,tug_code,request_code
""",
    ),
    **RECONCILIATION_VIEWS,
    'berth-occupancy': BERTH_OCCUPANCY,
}
