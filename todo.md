# 项目深度代码审阅与产品化升级方案
我已经做了深度代码审阅，结论很明确：这个项目**想法很强**，但当前实现还停留在**单体脚本式 agent runtime + 薄 API + 薄前端**的原型阶段；如果你要把它打造成简历杀手锏，重点不是再堆功能，而是把现有机制**产品化、内核化、可观测化**。

## 总体判断
你的亮点不是普通 Chat UI，而是这 4 件事的组合：**任务图 + 团队协作 + 上下文压缩 + 隔离执行**。这在个人项目里很少见，方向是对的。问题在于现在这些能力都挤在 `backend/agent/agent.py` 里，导致“能跑”但还不具备**可演进、可验证、可扩展**的工程说服力。

# 1. 架构重构蓝图
## 1.1 当前最核心的耦合点 / 坏味道
### 坏味道 A：God Object / 单文件承载全部核心能力
几乎所有核心逻辑都塞在 `backend/agent/agent.py`：
- 模型调用
- 工具分发
- Todo 管理
- 压缩
- 任务系统
- background job
- teammate 线程
- message bus
- REPL

这会直接带来：
- 无法做单元测试与组件替换
- CLI / Web / Subagent / Teammate 共享同一堆全局单例，状态污染风险高
- 未来接入更多执行后端、更多存储后端、更多压缩策略时，改动面会爆炸

### 坏味道 B：全局状态 + 文件状态 + 内存状态混用
例如：
- `_CHAT_SESSIONS` 在 `backend/agent/server.py:92`
- `shutdown_requests`, `plan_requests` 在 `backend/agent/agent.py:372-374`
- `TODO`, `TASK_MGR`, `BG`, `BUS`, `TEAM` 全局单例在 `backend/agent/agent.py:526-532`

这意味着：
- Web 多会话和 CLI 行为边界不清
- 重启丢失部分状态，部分状态又落盘，语义不一致
- 很难解释“哪些状态是 durable，哪些是 ephemeral”

### 坏味道 C：领域模型缺失，靠 dict 串起系统
任务、消息、工具结果、压缩摘要、审批请求，大量用 `dict/json` 裸传。
比如 `TaskManager`、`MessageBus` 都是弱 schema。

后果：
- 状态迁移难
- 协议演进难
- 难做版本兼容与审计

### 坏味道 D：接口层直接操作内部私有实现
`backend/agent/server.py:380-382` 直接调用 `TASK_MGR._save(updated)`。
这是典型“API 层绕过领域层”的信号，说明边界没立起来。

### 坏味道 E：执行模型太原型化
- `subprocess.run(shell=True)` 在 `backend/agent/agent.py:56` 和 `backend/agent/agent.py:321`
- teammate 用 thread loop 在 `backend/agent/agent.py:411`、`backend/agent/agent.py:420`
- inbox drain 语义直接清空文件 `backend/agent/agent.py:356-361`

这能 demo，但离“工业级 orchestrator”还有距离。

## 1.2 推荐的分层方案
我建议你把后端重构成 **Agent Kernel + Runtime Adapters + Control Plane API** 三层。

### 第一层：Domain / Kernel
纯业务内核，不依赖 FastAPI / Anthropic SDK / shell / filesystem 细节。
建议拆成：
```
domain/session.py
    Conversation
    Message
    CompactionSnapshot
domain/task_graph.py
    Task
    DependencyGraph
    Claim / Complete / Block / Unblock 规则
domain/team.py
    AgentIdentity
    ApprovalRequest
    MailMessage
    LifecycleState(FSM)
domain/events.py
    ToolCalled
    TaskClaimed
    TaskCompleted
    AgentIdled
    CompactionTriggered
```
这里面只放状态机与规则，不直接读写文件。

### 第二层：Application / Use Cases
用例层，负责 orchestrate：
- run_agent_turn
- claim_next_task
- approve_plan
- compact_conversation
- spawn_worker
- drain_inbox

这一层定义 Ports：
- LLMClientPort
- ToolExecutorPort
- TaskRepositoryPort
- MailboxPort
- TranscriptStorePort
- ExecutionSandboxPort
- TelemetryPort

### 第三层：Infrastructure / Adapters
具体实现：
- Anthropic client adapter
- FileTaskRepository
- JsonlMailbox
- LocalTranscriptStore
- LocalProcessExecutor
- GitWorktreeExecutor
- FastAPI controller

这样以后你就能自然支持：
- 文件存储 → SQLite/Postgres
- 本地线程 agent → 进程池 / 远程 worker
- 单 Anthropic backend → 多模型策略
- 本地 worktree → distributed sandbox runner

## 1.3 推荐引入的设计模式
1) **Ports and Adapters / Hexagonal Architecture**
这是最适合你项目的主骨架。
原因：你项目核心卖点是 orchestrator，不是 FastAPI，也不是某个 SDK。

2) **Strategy Pattern**
用于这些可插拔能力：
- 压缩策略：micro / rolling summary / hierarchical memory
- 调度策略：FIFO / dependency-aware / cost-aware / priority-aware
- 执行策略：inline / background / worktree / remote worker
- 工具选择策略：forced / heuristic / learned

3) **State Machine Pattern**
把 teammate 生命周期显式化：
- working
- idle
- awaiting_plan_approval
- awaiting_shutdown_ack
- terminated
- failed

你现在虽然有 FSM 意图，但实现分散在消息处理与线程循环里，例如 `backend/agent/agent.py:437-513`。
建议抽成独立状态机类，这会极大提升“工程成熟度”。

4) **Event Sourcing-lite**
不用全量 event sourcing，但强烈建议引入 domain event log。
每次：
- task created / claimed / completed
- plan approval requested / approved / rejected
- compact triggered
- background job started / finished
- teammate spawned / shutdown

都写统一事件流。这样你就有：
- 审计
- 回放
- Debugging timeline
- 可视化基础

这会非常像“真正的 agent orchestration platform”。

# 2. 核心机制如何从“简单实现”升级为生产级
## 2.1 三层 compact：从“压缩文本”升级为“可恢复上下文管理系统”
当前实现：
- `microcompact()` 清 tool_result 内容 `backend/agent/agent.py:197-208`
- `auto_compact()` 把历史 dump 到 jsonl，再让模型总结 `backend/agent/agent.py:210-240`

问题：
- 压缩后的信息不可结构化检索
- 丢失“为什么压缩、压了什么、还原点在哪”
- 没有 summary 质量验证
- 压缩是 token 超阈值驱动，不是语义驱动

建议升级为 3 层体系：
### L1：Ephemeral pruning
保留最近 N 轮完整 tool result，其余替换为摘要引用，不直接删成 `[cleared]`。
例如：
- 保留 tool name
- 参数 hash
- output digest
- artifact pointer

### L2：Structured episode summary
不是只存一段文本，而是输出结构化对象：
- goals
- decisions
- files_touched
- unresolved_questions
- open_tasks
- teammate_state
- referenced_artifacts

### L3：Long-term memory / transcript index
把 transcript summary 建成可索引资产：
- conversation_id
- episode_id
- time_range
- task_ids
- entities
- summary
- artifact_links

未来你可以继续做：
- 基于任务 / 文件 / agent 检索历史 episode
- “resume from compacted state”
- 跨会话 continuity

这会让 compact 不再只是“省 token”，而是“Agent memory architecture”。
简历价值会立刻提升。

## 2.2 JSONL 邮箱：从 drain mailbox 升级为可靠消息队列
当前 `read_inbox()` 是“读完清空” `backend/agent/agent.py:356-361`。
这是 demo 很顺手，但工程上有几个问题：
- 至少一次 / 至多一次语义不清
- 多消费者会丢消息
- 崩溃时 ACK 语义缺失
- 没有 message id、offset、dedupe key、retry policy

建议改成：
### 最小生产化版本
每条消息包含：
- message_id
- thread_id
- sender
- recipient
- type
- created_at
- attempt
- status = pending | delivered | acked | dead_letter

读取语义改为：
- lease message
- consumer process
- ack / nack
- timeout 自动重投

存储仍然可以先用文件，但要有：
- append-only log
- consumer cursor
- ack ledger

这样你可以公开讲：
实现了类 MQ 的 agent mailbox，在本地文件系统上支持 lease/ack/retry/dead-letter 语义。
这比“JSONL 邮箱”高级一个层级。

### 进阶版
抽象 MailboxPort，后续挂 Redis Streams / NATS / Kafka adapter。
你不用真的全做完，但设计上要预留，面试里很加分。

## 2.3 FSM：从“隐式状态切换”升级为“可验证的协作协议”
你现在有 shutdown / plan approval 机制，但状态不完整，例如：
- `shutdown_requests` / `plan_requests` 只是 dict `backend/agent/agent.py:372-374`
- 状态迁移散落在 `_loop` 和 handler 中

建议升级为：
- 明确定义状态图
- 每个事件有合法迁移表
- 非法迁移写 telemetry + reject

例如：
### Worker lifecycle
- spawned
- booting
- working
- waiting_for_input
- waiting_for_approval
- idle
- shutting_down
- terminated
- failed

### Approval lifecycle
- requested
- under_review
- approved
- rejected
- expired
- cancelled

再加：
- timeout policy
- idempotent transition
- persisted state snapshot

这样你的“团队协调”就从“多线程 agent demo”升级为“multi-agent coordination protocol”。

## 2.4 worktree 并行：从“本地隔离执行”升级为统一 sandbox runtime
这是你项目里最值得深挖的点之一。
如果做得好，面试官会很有感觉，因为这比普通 agent 项目更接近真实 coding agent 基础设施。

建议方向：
### 抽象统一执行单元 ExecutionLease
字段：
- task_id
- agent_id
- workspace_id
- sandbox_type(local, worktree, container, remote)
- mount_path
- branch_name
- ttl
- status

### 执行生命周期
- allocate sandbox
- hydrate workspace
- run task
- collect artifacts
- emit result
- cleanup / preserve for debugging

### 关键增强点
worktree 生命周期治理
- orphan cleanup
- stale lease recovery
- crash-safe metadata

资源隔离与配额
- 并发 worktree 上限
- per-agent CPU/time quota
- disk usage tracking

结果归档
- patch/diff
- test output
- logs
- plan summary

冲突检测
- 多 agent 修改同文件时提前告警
- file ownership / optimistic locking

可替换后端
- worktree today
- container tomorrow
- remote runner later

如果你能把这块讲成：
设计了 sandbox runtime abstraction，当前用 git worktree 实现零成本隔离，接口兼容容器/远程执行器扩展
那项目档次会明显提升。

## 2.5 Task 图：从“文件任务板”升级为真正的 orchestration DAG
当前任务系统已经有雏形，尤其 blockedBy 很好。
但现在还缺：
- task priority / deadline / labels
- retries / backoff
- artifact outputs
- dependency reason
- execution history
- claim lease / heartbeat
- stale owner recovery

建议升级为：
- TaskSpec：目标、输入、约束
- TaskState：pending/running/completed/failed/blocked/cancelled
- TaskRun：每次执行的 attempt 记录
- TaskArtifact：日志、diff、summary、文件输出
- Scheduler：选择谁执行下一个任务

加分点是把依赖图真正可视化：
- DAG view
- critical path
- blocked reason
- per-agent throughput

这会让项目从“有任务文件”变成“有 orchestrator”。

# 3. 工程化与可观测性补足
这是你现在最缺、但最能拉开“原型 vs 高质量项目”的部分。

## 3.1 API 规范化
当前 API 能用，但还比较薄：
- 没有统一错误码
- 没有 request id / trace id
- 没有版本化策略
- 没有 streaming 正式协议
- 响应模型和内部领域模型割裂

建议：
### API 分层
- /api/v1/chat
- /api/v1/tasks
- /api/v1/agents
- /api/v1/inbox
- /api/v1/runs
- /api/v1/events

### 统一响应 envelope
```json
{
  "request_id": "...",
  "trace_id": "...",
  "data": {...},
  "error": null
}
```

### 正式流式协议
把现在的 fake streaming `frontend/src/services/stream.ts:22-52` 升级为真正 SSE：
- token delta
- tool_started
- tool_finished
- task_claimed
- teammate_message
- compact_triggered
- final_text

这会显著提升产品完成度。

## 3.2 可观测性：这是必做项
如果你想把它打成“高质量开源 + 面试亮点”，必须补 observability。

### 最少要有三类 telemetry
1) **Structured logs**
每个关键动作都输出 JSON log：
- request_id
- conversation_id
- agent_id
- task_id
- event_type
- latency_ms
- token_in / token_out
- tool_name
- status

2) **Metrics**
建议 Prometheus 风格：
- agent_turn_latency
- tool_call_latency
- task_queue_depth
- task_blocked_count
- compact_count
- compact_reduction_ratio
- mailbox_pending_count
- inbox_redelivery_count
- worktree_active_count
- worker_idle_time

3) **Tracing**
如果你能接 OpenTelemetry，会非常加分。
至少把一次 chat request 的链路串起来：
`HTTP request -> agent turn -> model call -> tool call -> task update -> mailbox event`

面试时你就能说：
为多智能体执行链路补齐 tracing，将模型调用、工具执行、任务状态变更统一挂到单条 trace 中，显著降低复杂流程的排障成本。
这句话杀伤力很强。

## 3.3 容错与可靠性
你现在很多地方是“异常就返回字符串”。例如工具执行、后台任务、teammate loop。
这对 demo 合理，但生产化需要：

### 必补机制
- 明确错误类型：user error / system error / transient error / policy error
- retry policy：仅 transient 重试
- timeout budget：不同工具不同 SLA
- circuit breaker：模型调用或某类工具连续失败时降级
- crash recovery：重启后恢复 running tasks / orphan background jobs / stale mailbox leases

### 特别建议
把 BackgroundManager 做成真正的 Job Runner：
- persistent job record
- status transitions
- result artifact path
- cancel support
- retry attempts
- start/end timestamps

## 3.4 测试体系
目前从代码结构看，测试不是主轴。
而一个“求职亮点项目”必须有测试 story。

建议至少补齐：
### 单元测试
- TaskGraph 状态迁移
- FSM 合法/非法迁移
- compact policy
- path safety
- message ack/retry

### 集成测试
- /api/chat 到 tool 执行的完整链路
- teammate 协作流程
- task claim + dependency release
- compaction 恢复
- worktree 分配与回收

### 混沌/故障注入测试
这非常加分：
- worker crash during task
- message duplicated
- partial write to task file
- model timeout
- worktree cleanup failure

你不需要做很多，但做 2~3 个代表性的 fault injection test，就很像“认真做系统的人”。

## 3.5 安全与治理
当前 `shell=True` + 简单关键词黑名单 `backend/agent/agent.py:51-61` 明显不够。

建议：
- command policy engine
- allowlist tool execution context
- no-shell mode for common commands
- per-tool permission scopes
- secret redaction in logs/transcripts
- artifact path sanitization
- multi-tenant boundary abstraction（哪怕暂时单租户）

这不仅是安全，也是工程成熟度信号。

## 3.6 前端补足
前端目前偏演示层，中心逻辑都在 `frontend/src/stores/chat.ts`。
想做成亮点，建议补 4 个面：

- **Run timeline 面板**
  模型调用、工具调用、teammate 消息、compaction、task 状态变更
- **Task DAG 可视化**
  blockedBy、owner、runtime、artifact links
- **Agent/Worker 状态页**
  idle/working/waiting approval、inbox backlog、current sandbox/worktree
- **Replay / Debug UI**
  回放一轮 agent run 的事件轨迹

这会把项目从“聊天壳子”升级为“orchestrator console”。

# 4. 落地路线图
不要一次性大改，按“简历价值最大化”排序：

## Phase 1：先拆内核边界
目标：把 `backend/agent/agent.py` 拆为：
```
runtime/orchestrator.py
domain/tasks.py
domain/team_fsm.py
infra/file_task_repo.py
infra/jsonl_mailbox.py
infra/local_executor.py
adapters/anthropic_client.py
```
这一阶段就已经能明显提升代码观感。

## Phase 2：补事件流与可观测性
加：
- structured events
- run ids / trace ids
- metrics
- timeline API

这一阶段最能提升“工业感”。

## Phase 3：升级 mailbox + task DAG + sandbox runtime
加：
- ack/retry/dead-letter
- task attempt / lease / heartbeat
- sandbox abstraction + worktree metadata

这是技术含金量最高的一段。

## Phase 4：前端做 console 化
加：
- event timeline
- DAG 视图
- worker 状态面板
- replay/debug

这是展示效果最强的一段。

# 5. 简历亮点提炼（STAR 风格）
下面这 3 条是我建议你最终打磨后的版本，不是照搬当前状态，而是基于上述重构方案提炼。

## 亮点 1：多智能体编排内核
**S/T**：针对传统 coding agent 难以稳定处理长链路、多子任务协作的问题，设计多智能体任务编排内核。
**A**：将任务依赖图、队友消息协议、审批 FSM、上下文压缩从原型脚本重构为可插拔的 domain kernel，支持任务 claim、阻塞解除、计划审批与自治式 worker 协同。
**R**：显著提升复杂任务拆解与并行执行能力，使系统从单轮对话 agent 升级为具备持续协作能力的 agent orchestration platform。

## 亮点 2：上下文压缩与可恢复记忆系统
**S/T**：针对长对话场景中 token 开销高、历史上下文易失真的问题，构建分层上下文管理机制。
**A**：实现 micro-pruning、episode summary、transcript index 三层 compact pipeline，并将任务状态、关键决策、文件改动与未决问题结构化持久化，支持压缩后连续执行与历史回放。
**R**：在保持多轮连续性的同时降低上下文成本，并增强复杂 agent 会话的可恢复性与可调试性。

## 亮点 3：隔离执行与可观测 Agent Runtime
**S/T**：针对多 agent 并行修改代码时的环境冲突、执行不可见和排障困难问题，设计统一执行运行时。
**A**：基于 git worktree 抽象出 sandbox runtime，配合事件流、结构化日志、链路追踪和任务时间线，实现 agent/tool/task/workspace 全链路观测与隔离执行。
**R**：提升并行执行安全性与问题定位效率，使项目具备接近工业级 coding agent 基础设施的工程完整度。

# 6. 直白判断
这个项目很有潜力成为强简历项目，因为你选的不是“再做一个聊天机器人”，而是“做一个 agent runtime / orchestration system”。这条路线天然更稀缺。

但要真正有竞争力，你接下来最该做的是：
- 把单文件大泥球拆成有边界的内核
- 把隐式行为变成显式协议、状态机、事件流
- 把 demo 功能补成可观测、可恢复、可验证的工程系统

如果你愿意，我下一步可以直接继续帮你做两件事之一：
A. 给你输出一版“工业级目录重构方案 + 文件拆分清单”
B. 直接基于当前仓库，先设计第一阶段重构（含具体模块接口草图）

如果你要，我建议我直接做 B。