# 用户查询处理链路技术文档

## 1. 概述

本系统是一个基于 LLM 的 SQL Agent，接收用户的自然语言问题，通过多阶段 LangGraph 工作流将其转化为 SQL 查询并执行，最终以流式方式将结果和自然语言解释返回给前端。

**核心技术栈：**

| 层次 | 技术 |
|------|------|
| Web 框架 | FastAPI + SSE 流式响应 |
| 工作流编排 | LangGraph（有向无环图） |
| LLM 接入 | LangChain ChatOpenAI（对接 vLLM/Ollama） |
| 向量检索 | Milvus（HNSW 索引，余弦相似度） |
| 业务数据库 | PostgreSQL（SQLAlchemy） |
| 缓存 | Redis（RBAC 权限缓存） |
| 异步任务 | Celery（审计日志异步写入） |

---

## 2. 请求入口

**端点：** `GET /api/query`  
**文件：** [api/query.py](../backend/api/query.py)  
**协议：** HTTP Server-Sent Events（SSE），持久连接，逐步推送事件

**请求参数：**

| 参数 | 说明 |
|------|------|
| `question` | 用户自然语言问题 |
| `session_id` | 会话 ID（多轮对话上下文） |
| `run_id` | 本次请求唯一标识（用于取消） |
| `group_id` | （可选）表分组过滤 |

---

## 3. 完整处理链路

```
用户问题（HTTP GET /api/query）
        │
        ▼
┌───────────────────────────────────────────────┐
│           Step 1: 身份验证 & 权限获取           │
│  api/query.py                                 │
│  • 解析 JWT Token → 获取当前用户               │
│  • Redis 查权限缓存 → get_user_allowed_tables() │
│  • 未命中则查 DB，缓存 5 分钟                  │
│  • allowed_tables: None=管理员, List=白名单     │
└───────────────────────┬───────────────────────┘
                        │
                        ▼
┌───────────────────────────────────────────────┐
│         Step 2: 会话校验 & 历史加载            │
│  api/query.py + db/crud/messages.py           │
│  • 验证 session_id 归属当前用户                │
│  • 从 DB 加载历史消息                          │
│  • 格式化为: "用户: ...\n助手: ..." 字符串      │
└───────────────────────┬───────────────────────┘
                        │
                        ▼
┌───────────────────────────────────────────────┐
│         Step 3: 消息落库（占位）               │
│  db/crud/messages.py                          │
│  • 写入用户消息 (role='user')                  │
│  • 写入助手消息占位 (role='assistant',         │
│    status='streaming')                        │
└───────────────────────┬───────────────────────┘
                        │
                        ▼
┌───────────────────────────────────────────────┐
│   Step 4: 启动后台工作流 & 建立事件队列         │
│  graph/workflow.py                            │
│  • asyncio.Queue 作为事件通道                  │
│  • run_in_executor 在线程池中运行工作流         │
│  • SSE 主协程从队列消费并推送事件到前端          │
└───────────────────────┬───────────────────────┘
                        │
        ┌───────────────▼──────────────────────────────────────────────┐
        │                  LangGraph 工作流执行                         │
        │                  graph/workflow.py + graph/nodes.py           │
        └──────────────────────────────────────────────────────────────┘
                        │
                        ▼
        ┌───────────────────────────────┐
        │  Node 1: context_fusion_node  │
        │  graph/nodes.py               │
        │                               │
        │  输入: question +             │
        │        conversation_history   │
        │                               │
        │  LLM 判断问题类型:            │
        │  • standalone（独立问题）     │
        │  • continuation（追问）       │
        │  • ambiguous（歧义）          │
        │                               │
        │  融合置信度 < 0.6 → 保留原问  │
        │                               │
        │  输出: fused_question         │
        └───────────────┬───────────────┘
                        │
                        ▼
        ┌───────────────────────────────┐
        │  Node 2: retrieve_node        │
        │  graph/nodes.py               │
        │                               │
        │  Milvus 向量检索:             │
        │  • 对 fused_question 做嵌入   │
        │  • 搜索 "table_schemas" 集合  │
        │  • Top-K = config.retrieval_  │
        │    top_k（默认 5）            │
        │                               │
        │  权限过滤:                    │
        │  • group_table_filter 过滤    │
        │  • RBAC 白名单过滤            │
        │    (非管理员)                 │
        │                               │
        │  输出: retrieved_schemas      │
        └───────────────┬───────────────┘
                        │
                        ▼
        ┌───────────────────────────────┐
        │  Node 3: table_selection_node │
        │  graph/nodes.py               │
        │                               │
        │  LLM 从检索结果中挑选真正      │
        │  需要的表（含 selection_reason）│
        │                               │
        │  解析失败 → Fallback:         │
        │  使用全部检索到的表            │
        │                               │
        │  输出: selected_tables        │
        └───────────────┬───────────────┘
                        │
              ┌─────────▼─────────┐
              │ 表数量 > 1 ?       │
              └────┬──────────────┘
            是 │            │ 否
               ▼            ▼
  ┌────────────────────┐    │
  │ Node 4:            │    │
  │ join_planning_node │    │
  │ graph/nodes.py     │    │
  │                    │    │
  │ LLM 分析表关系:    │    │
  │ • 外键关联         │    │
  │ • JOIN 类型选择    │    │
  │ • JOIN 顺序规划    │    │
  │                    │    │
  │ 输出: join_plan    │    │
  └────────────┬───────┘    │
               └──────┬─────┘
                      ▼
        ┌───────────────────────────────┐
        │  Node 5: generate_sql_node    │
        │  graph/nodes.py               │
        │                               │
        │  LLM 生成 SELECT SQL:         │
        │  • 注入 selected_tables 结构  │
        │  • 注入 join_plan（多表时）   │
        │  • 注入历史错误上下文（重试）  │
        │  • 清洗 ```sql 代码块包装     │
        │                               │
        │  输出: generated_sql          │
        │  retry_count + 1              │
        └───────────────┬───────────────┘
                        │
                        ▼
        ┌───────────────────────────────┐
        │  Node 6: check_query_node     │
        │  graph/nodes.py               │
        │                               │
        │  4 层 SQL 校验:               │
        │  ① sqlparse 语法解析          │
        │  ② 危险关键字检测             │
        │     (DROP/DELETE/ALTER等)     │
        │  ③ 仅允许 SELECT 语句         │
        │  ④ AST 级 RBAC 表权限校验     │
        │     提取 SQL 引用的表名        │
        │     → 检查是否在白名单内       │
        │                               │
        │  输出: sql_valid              │
        └───────────────┬───────────────┘
                        │
          ┌─────────────▼──────────────┐
          │   路由判断                  │
          └─────────────────────────────┘
     sql_valid=True │   │ "无法生成SQL" │ retry < max
                    │   │               │
                    ▼   ▼               ▼
          ┌──────────┐ ┌────────────┐ ┌───────────────────┐
          │ execute  │ │ rewrite_   │ │ 回到 generate_sql │
          │ _node    │ │ question_  │ │ （带错误上下文）   │
          │          │ │ node       │ └───────────────────┘
          └──────────┘ └────────────┘
                │            │
                │      LLM 重写问题
                │      → 回到 retrieve_node
                │
                ▼
        ┌───────────────────────────────┐
        │  Node 7: execute_node         │
        │  graph/nodes.py               │
        │                               │
        │  SQLAlchemy 同步引擎执行 SQL   │
        │  → PostgreSQL                 │
        │                               │
        │  执行结果:                    │
        │  {                            │
        │    columns: [...],            │
        │    rows: [[...],...],         │
        │    row_count: N               │
        │  }                            │
        │                               │
        │  执行成功 & row_count == 0    │
        │  且未重写过 → rewrite_question│
        └───────────────┬───────────────┘
                        │
        ┌───────────────▼──────────────────────────────────────────────┐
        │              图执行结束，进入答案生成阶段                      │
        │              graph/workflow.py - generate_answer_stream()     │
        └──────────────────────────────────────────────────────────────┘
                        │
                        ▼
        ┌───────────────────────────────┐
        │  答案生成（图外，流式）        │
        │  graph/workflow.py            │
        │                               │
        │  执行成功分支:                │
        │  1. 将结果格式化为文本表格    │
        │  2. 生成 query_explanation    │
        │     （用了哪些表 & 原因）     │
        │  3. 流式生成自然语言答案      │
        │     → LLM .stream()           │
        │     → 逐 token 推送前端       │
        │                               │
        │  执行失败分支:                │
        │  → ERROR_ANSWER_PROMPT 解释   │
        │    失败原因                   │
        └───────────────┬───────────────┘
                        │
                        ▼
┌───────────────────────────────────────────────┐
│         Step 5: SSE 事件流输出                 │
│  api/query.py                                 │
│                                               │
│  事件类型:                                    │
│  {"type":"status",        "content":"..."}    │
│  {"type":"answer_chunk",  "content":"..."}    │
│  {"type":"explanation",   "content":"..."}    │
│  {"type":"result",        "data":{...}}       │
│  {"type":"done",          "state":{...}}      │
└───────────────────────┬───────────────────────┘
                        │
                        ▼
┌───────────────────────────────────────────────┐
│         Step 6: 持久化 & 异步审计             │
│                                               │
│  DB 更新:                                     │
│  UPDATE messages SET                          │
│    content = final_answer,                    │
│    metadata_ = {status:'done', sql:..., ...}  │
│  WHERE id = assistant_message_id              │
│                                               │
│  Celery 异步任务:                             │
│  write_audit_log_task.delay(                  │
│    user_id, session_id, question,             │
│    generated_sql, execution_success,          │
│    execution_time_ms, row_count, error        │
│  )                                            │
└───────────────────────────────────────────────┘
```

---

## 4. 核心模块说明

### 4.1 工作流状态（GraphState）

**文件：** [graph/state.py](../backend/graph/state.py)

所有节点共享同一个 `GraphState` TypedDict，贯穿整个工作流：

| 字段 | 类型 | 说明 |
|------|------|------|
| `question` | `str` | 原始用户问题 |
| `fused_question` | `str` | 上下文融合后的问题 |
| `conversation_history` | `str` | 历史对话字符串 |
| `retrieved_schemas` | `List[str]` | Milvus 检索到的表结构 |
| `selected_tables` | `List[TableSelectionItem]` | LLM 挑选的表 |
| `join_plan` | `Optional[JoinPlan]` | 多表 JOIN 规划 |
| `generated_sql` | `str` | 生成的 SQL |
| `sql_valid` | `bool` | SQL 校验结果 |
| `execution_result` | `Optional[Dict]` | 查询结果（columns/rows） |
| `execution_success` | `bool` | 执行是否成功 |
| `retry_count` | `int` | 当前重试次数 |
| `allowed_tables` | `Optional[List[str]]` | RBAC 白名单（None=管理员） |
| `group_table_filter` | `Optional[List[str]]` | 表分组过滤 |

### 4.2 LLM 调用一览

**文件：** [graph/nodes.py](../backend/graph/nodes.py)、[graph/prompts.py](../backend/graph/prompts.py)

| 调用点 | Prompt | 输入 | 输出 |
|--------|--------|------|------|
| context_fusion_node | `CONTEXT_FUSION_PROMPT` | 原始问题 + 历史 | 融合问题 + 类型 + 置信度 |
| table_selection_node | `TABLE_SELECTION_PROMPT` | 融合问题 + 检索到的表 | 挑选结果 + 理由 |
| join_planning_node | `JOIN_PLANNING_PROMPT` | 融合问题 + 选中的表 | JOIN 类型 + 顺序 + 条件 |
| generate_sql_node | `SQL_GENERATION_PROMPT` | 表结构 + 问题 + 错误上下文 | SELECT SQL |
| rewrite_question_node | `QUESTION_REWRITE_PROMPT` | 原始问题 | 重写后的问题 |
| generate_answer_stream | `ANSWER_PROMPT` | SQL + 结果 + 问题 | 流式自然语言答案 |
| generate_answer_stream | `QUERY_EXPLANATION_PROMPT` | 表结构 + SQL + 问题 | 引用说明 |

所有 LLM 调用均通过 `get_llm()` 获取单例 `ChatOpenAI` 实例，`temperature=0`，连接 `config.llm_base_url`（默认 `http://localhost:8000/v1`）。

### 4.3 SQL 安全校验（4 层）

**文件：** [graph/nodes.py](../backend/graph/nodes.py) - `check_query_node`

```
第 1 层：sqlparse 语法解析
         ↓ 失败 → sql_valid=False，携带错误原因
第 2 层：危险关键字检测
         DROP / DELETE / ALTER / TRUNCATE / INSERT / UPDATE / CREATE / EXEC
         ↓ 命中 → 拒绝
第 3 层：仅允许 SELECT
         解析 Statement 类型，非 SELECT 拒绝
         ↓
第 4 层：AST 级 RBAC 校验（非管理员）
         提取 SQL 中所有引用表名
         → 逐一检查是否在 allowed_tables 白名单内
         → 有越权访问 → 拒绝
```

### 4.4 重试与回退机制

```
SQL 生成失败 / 执行失败
        │
        ├─ retry_count < max_retry_count（默认 3）
        │      → 携带 error_context 重新生成 SQL
        │
        ├─ 返回 "无法生成SQL" 消息
        │      → 进入 rewrite_question_node
        │      → 重写问题后回到 retrieve_node 重新检索
        │
        ├─ 执行成功但 row_count == 0 且未重写过
        │      → 进入 rewrite_question_node（语义细化）
        │
        └─ 超出重试上限
               → 工作流结束，进入错误答案生成
```

### 
