# 船舶靠泊延误边界分类

东岬港引航协调组用潮窗和拖轮预约约束靠泊确认，再根据现场无线电观测分流延误案件。主管签署边界案件，并记录从指令下发到全缆系妥的实际经过。

## 工作现场

模拟的东岬港有三个泊位、三艘协作拖轮和一组引航协调人员。以前各班从水文通告、船代邮件、共享拖轮排班表和 VHF 纸单抄录。同一航次经常遇到三个问题。

1. 只比 ETA 与潮窗起止，没有检查整段操纵时长及申请吃水。
2. 两个泊位同时使用同一艘拖轮，各班在自己的表中都显示无冲突。
3. 延误不明确时用口头交接，下一班无法追溯分类意见与现场处置结果。

船代申请和水文通告进入靠泊计划，港区 VHF 事件进入延误流程。下游引航席与拖轮调度消费已确认计划及值班指令，交班主管查看结案纪要。模拟通告由主管录入，系统保留其引用名称。

| 账号 | 角色 | 页面和操作 |
|---|---|---|
| `operator` | 值班调度员 | 登记靠泊申请，修订未确认计划，预约拖轮，登记已确认申请的 VHF 延误 |
| `supervisor` | 调度主管 | 具备调度员操作，可发布潮窗、确认靠泊、重试、签署分类、发布指令及复盘结案 |
| `viewer` | 观察员 | 查询潮窗、申请、预约、案件、指令和审计记录 |

三个本地演示账号的口令均为 `Harbor1074!`。

## 2026 年 11 月 21 日早班

1. 07:25 起，主管按 `TIDE-EAST-1121-AM.pdf` 发布三处泊位的四段潮窗。
2. 首版 `BR-410` 把海岚 27 排在 B07 的 `TW-071`，08:50 起操纵 45 分钟，吃水 12.4 m。该潮窗 09:10 结束，吃水上限 11.8 m，确认被拒绝。
3. 调整到 `TW-072` 的 09:10–09:29，新潮窗吃水上限 13.2 m，作业结束后余量 76 分钟。
4. 请求使用 `TG12` 时，系统发现 `BR-411` 已预约该轮 09:25–10:20。改用 `TG23` 后，主管确认 `BR-410`。
5. 09:48，远桥 75 对应 `BR-413` 在 `VHF-12/0930-19` 报告拖轮回转区的延迟。冻结观测形成 `DL-413`，其中计划偏离 18 分钟、潮窗余量 25 分钟、风速 14 kn、拖轮等候 12 分钟。
6. worker 完成边界分类。该案件进入间隔带，常规动作审批暂停，主管依据二次通报签署优先处置。
7. 值班主管发布拖轮待命指令。10:15 全缆系妥，工作人员补录实绩和交班纪要，案件结案，关联申请置为完成。

业务时间统一以港区 UTC+08 录入，审计时间由数据库记录并在 API 中转换展示。

## 本地启动

```bash
cp .env.example .env
docker compose config --quiet
docker compose up -d --build --wait
docker compose exec -T backend python -m scripts.seed_demo
```

在项目目录执行以上命令。数据库和 Redis 由 Compose 启动，`SEED_DEMO=true` 会自动装载具名班次及三个岗位账号。手动 seed 维持已有现场修改。前端 `http://localhost:18273`，API 文档 `http://localhost:19273/docs`，MySQL `127.0.0.1:17773`。`docker compose down` 可停止本地栈并保留业务数据。

本地 Python 开发可只启动 `db` 和 `redis` 服务。在 `backend/` 用 Python 3.11 安装 `requirements.txt`，将 `MYSQL_HOST`、`MYSQL_PORT`、`REDIS_URL` 指向开发实例，再运行 `uvicorn src.main:app --reload --port 8000` 和 `python -m src.worker`。Redis 默认只开放容器网络，宿主机开发需提供本地 Redis 或另配开发端口。前端通过 Nginx 的 `/api/` 代理访问 API。

| 服务 | 技术与职责 |
|---|---|
| frontend | Nginx 与原生 HTML/CSS/JS，班次图、潮汐与拖轮、间隔带、调度复盘 |
| backend | FastAPI、SQLAlchemy、JWT 三角色、MySQL 事务与业务审计 |
| worker | 常驻 Python 进程、Redis 唤醒、持久待分类队列、scikit-learn |
| db | MySQL 8，实体、时段预约、模型快照、调度指令 |
| redis | Redis 7，传递案件已入队的唤醒事件 |

`.env.example` 包含 `COMPOSE_PROJECT_NAME`、`FRONTEND_PORT`、`BACKEND_PORT`、`DB_PORT`、`MYSQL_DATABASE`、`MYSQL_USER`、`MYSQL_PASSWORD`、`MYSQL_ROOT_PASSWORD`、`JWT_SECRET` 与 `SEED_DEMO`。本地连接还可配置 `MYSQL_HOST`、`MYSQL_PORT`、`REDIS_URL`。默认凭据用于演示环境。`database`、`queue`、`artifacts` 为命名卷，数据库保存模型与业务记录，`artifacts` 为 API 与 worker 的共享产物目录。

## 算法和排程规则

- 确认靠泊要求整个操纵区间都落在潮窗内、吃水不超限、拖轮预约与计划吻合、同泊位无其他已确认的重叠操纵。区间采用左闭右开口径。改期释放之前的拖轮预约，并保留历史记录。
- 四项模型输入为引航偏离、潮窗结束余量、实测风速、拖轮等候。创建案件时冻结输入并生成 SHA-256。固定种子 `1074` 生成 720 条训练样本与独立生成的 240 条验证样本。`StandardScaler` 将训练特征中心化、缩放，再以 `SVC(kernel='rbf', C=1.7, gamma='scale')` 拟合。二分类用 `decision_function` 的符号提供建议，`|f(x)| ≤ 0.30` 进入人工复核。平衡准确率为两类召回率的均值。模型结果保留支持向量数、合成验证指标、参数和版本。
- worker 使用 MySQL 待处理状态和行锁领取案件，Redis 唤醒丢失时继续扫描。计算失败写入错误，主管可以沿用冻结摘要重试。成功后原模型建议持续保留，模型签署与人工签署有不同的记录字段。
- 已确认的计划冻结。调度指令支持跟踪、待命、通知改期。改期指令是发给引航席的交班记录，现场后续排程由引航席另行协调。模型指标源于合成数据，现场岗位发布的动作和实绩通过表单登记。

## 代码位置

- `backend/src/models.py` 定义实体与数据库约束，`schemas.py` 定义操作数据。`main.py` 首次启动建表，`backend/migrations/README.md` 记录建库入口。
- `planning.py` 处理资源预约、撤销与确认，`incidents.py` 处理案件、签署、调度与复盘。`routes.py` 接入 JWT 权限和事务。`main.py` 提供请求跟踪、响应策略及全局业务错误处理。
- `classifier.py` 和 `worker.py` 完成异步分类。`backend/scripts/seed_demo.py` 建立可演示班次。
- `frontend/src/api.js` 对接接口，`store.js` 保存值班会话和班次数据，`planning.js` 和 `incidents.js` 提供业务页面，`ui.js` 复用状态标签、编辑表单、交班时间线和格式化函数。
- 角色、申请状态、案件状态、分类和动作枚举在 `backend/src/models.py` 与 `frontend/src/store.js` 定义。后端 `schemas.py`、`security.py`、`routes.py`、`planning.py`、`incidents.py`、`worker.py` 与 `seed_demo.py` 消费上述枚举，分类器持久化两类预测标签。前端 `app.js`、`planning.js` 与 `incidents.js` 消费相同的 API 值。

License: MIT，见 `LICENSE`。


## 业务核验模块

登录后打开页面右下角的「业务核验」。可从实时业务台账筛选记录、导出所选结果，主管可对当前证据签认并填写说明。

- **潮汐窗口余量** 按靠泊申请计算吃水余度和预计操作结束时的剩余分钟数，帮助调度选出潮窗余量最小的申请。
- **拖轮交接间隔** 以同一拖轮的下个未释放任务为界计算可交接分钟数，少于 15 分钟进入调度核对。

### 二次扩展核验

- **靠泊完成凭证对账** 将调度复盘、靠妥时间与预计操作结束对齐，发现已关闭但缺凭证或时间倒置的记录。

## 专项业务核对

登录后打开「业务核验」，可以筛选和导出记录，主管可签认指定证据。

- **靠泊实绩对下班泊位的影响** 按同泊位时序比较前船靠妥与后船预计到港。前船缺靠妥凭证时单列待确认，避免将计划间隔作为实绩。
