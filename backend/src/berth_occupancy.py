"""靠泊实绩对下班泊位的影响."""

VIEW = (
    '靠泊实绩对下班泊位的影响',
    '按同泊位时序比较前船靠妥与后船预计到港。前船缺靠妥凭证时单列待确认，避免将计划间隔作为实绩。',
    ['泊位', '前船申请', '后船申请', '前船计划结束', '前船靠妥', '后船到港', '计划缓冲 分钟', '实绩缓冲 分钟', '影响判定'],
    """
WITH arrivals AS (
 SELECT berth_code,code,eta,DATE_ADD(eta,INTERVAL maneuver_minutes MINUTE) AS planned_end,
        LEAD(code) OVER (PARTITION BY berth_code ORDER BY eta,code) AS next_code,
        LEAD(eta) OVER (PARTITION BY berth_code ORDER BY eta,code) AS next_eta
 FROM berth_requests WHERE state IN ('confirmed','completed')
)
SELECT a.berth_code,a.code,a.next_code,a.planned_end,d.all_fast_at,a.next_eta,
       TIMESTAMPDIFF(MINUTE,a.planned_end,a.next_eta) AS planned_buffer,
       TIMESTAMPDIFF(MINUTE,d.all_fast_at,a.next_eta) AS observed_buffer,
       CASE WHEN d.all_fast_at IS NULL THEN '前船缺靠妥实绩，待值班确认'
            WHEN d.all_fast_at>a.next_eta THEN '后船已进入前船靠泊时段'
            WHEN a.planned_end>a.next_eta THEN '原计划间隔不足，实绩已缓解'
            ELSE '前船靠妥早于后船到港' END AS operational_impact
FROM arrivals a LEFT JOIN delay_incidents i ON i.request_code=a.code LEFT JOIN dispatch_reviews d ON d.incident_code=i.code
WHERE a.next_code IS NOT NULL ORDER BY a.next_eta,a.berth_code,a.code
""",
)
