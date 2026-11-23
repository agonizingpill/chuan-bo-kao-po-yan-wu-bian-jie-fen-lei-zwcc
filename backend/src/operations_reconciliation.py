"""Additional operational reconciliation rules for this project."""

RECONCILIATION_VIEWS = {
    'all-fast-evidence': (
        '靠泊完成凭证对账',
        '将调度复盘、靠妥时间与预计操作结束对齐，发现已关闭但缺凭证或时间倒置的记录。',
        ['靠泊申请', '事件号', '发令时间', '预计操作结束', '靠妥时间', '偏差 分', '复盘关闭时间', '凭证结论'],
        """
SELECT r.code,i.code,d.issued_at,DATE_ADD(r.eta,INTERVAL r.maneuver_minutes MINUTE),d.all_fast_at,
       TIMESTAMPDIFF(MINUTE,DATE_ADD(r.eta,INTERVAL r.maneuver_minutes MINUTE),d.all_fast_at),d.closed_at,
       CASE WHEN d.closed_at IS NOT NULL AND d.all_fast_at IS NULL THEN '已关闭，待补靠妥凭证'
            WHEN d.all_fast_at IS NULL THEN '待记录靠妥'
            WHEN d.all_fast_at<i.observed_at THEN '时间顺序待核查'
            WHEN d.closed_at IS NULL THEN '已靠妥，待关闭复盘'
            ELSE '已关闭，凭证齐备' END
FROM dispatch_reviews d JOIN delay_incidents i ON i.code=d.incident_code
JOIN berth_requests r ON r.code=i.request_code ORDER BY d.issued_at DESC,r.code
""",
    ),
}
