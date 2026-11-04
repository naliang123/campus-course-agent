# 校园课程智能助手

基于 **Vue 3 + FastAPI + FastMCP + LangChain Agent + RAG(Chroma)** 的校园课程智能助手。

学生登录后可以：查询自己的课表、依据已上传的课程资料提问、生成并保存学习计划；管理员负责课程元数据、课表维护、用户管理与课程资料入库。系统通过 JWT 严格隔离本人数据，通过 MCP 工具把业务能力交给 ReAct Agent 调用，并通过 SSE 把工具过程与回答实时推送到页面。

> 本项目严格按参考文档 `参考.md`（第 01—14 节）实现。文档配图已归档到 [`docs/images/`](docs/images/)，逐图说明见 [`docs/使用文档.md`](docs/使用文档.md)。
>
> **功能范围说明**：参考文档定义的是「课程 / 课表 / 学习计划 / 文档知识库 / AI 助手」，并未包含选课退课、成绩记录、教师信息维护等模块，因此本项目未擅自增加这些与文档接口规范、数据模型不一致的功能。角色仅有 `student` 与 `admin` 两种，用户（含学生）信息维护由「用户管理」承担。

---

## 1. 系统架构

运行时需要同时启动 **四个进程**：

| 进程 | 默认地址 | 职责 |
| --- | --- | --- |
| 前端 | `http://127.0.0.1:5173` | 页面交互、SSE 对话 UI |
| FastAPI | `http://127.0.0.1:8000` | 业务 API、Agent 对话入口 |
| FastMCP | `http://127.0.0.1:8001/mcp` | 三个工具：查课表 / 检索资料 / 存计划 |
| Chroma | `http://127.0.0.1:8002` | 保存资料片段，供 FastAPI 与 MCP 共同读写 |

虚线框外的第三方服务：对话模型 API（默认 DeepSeek）、Embedding API（默认硅基流动 `BAAI/bge-m3`）。

![系统组件图](docs/images/image1.png)

**两条贯穿全系统的工程原则**：

1. **用户身份由系统传递，不由模型填写**：前端 JWT → FastAPI 原样转发 → MCP 工具再解析一次 JWT 并核对用户状态。课表、学习计划按 `user_id` 隔离；知识库文档全站共享，工具不接收 `user_id` 参数（见 [`image13`](docs/images/image13.png)）。
2. **检索不到就如实说，不许编造**：区分「检索服务失败」与「检索成功但无片段」，两种情况都不能假装已查阅资料。

## 2. 技术栈

| 层级 | 技术 |
| --- | --- |
| 前端 | Vue 3 + Element Plus + Vite + Axios；`marked` + `DOMPurify` 安全渲染 Markdown；`fetch` 读取 SSE |
| 后端业务 | FastAPI + SQLAlchemy + MySQL，统一返回 `{code, message, data}` 与全局异常处理 |
| 鉴权 | JWT（`get_current_user` / `get_current_admin`），bcrypt 密码哈希 |
| 工具协议 | FastMCP 独立进程，Streamable HTTP |
| 智能编排 | `langchain.create_agent`（LangGraph，ReAct 模式），`langchain-mcp-adapters` 加载工具 |
| 流式推送 | SSE，六种事件：`status` / `tool_start` / `tool_end` / `token` / `done` / `error` |
| 知识库 | 文本抽取（pypdf / python-docx）→ 500 字分块、50 字重叠 → Embedding → Chroma，检索 Top-3 |

## 3. 目录结构

```text
campus-course-agent/
├── sql/
│   ├── campus-course-agent.sql   # 完整初始化：5 张表 + 演示数据（推荐导入）
│   └── backend.sql               # 脚手架原版（仅 users 表）
├── backend/
│   ├── app/
│   │   ├── api/                  # auth / user / files / course / schedule /
│   │   │                         # study_plan / document / mcp / chat
│   │   ├── services/             # course / schedule / study_plan / document /
│   │   │                         # rag / mcp_client / agent
│   │   ├── models/               # User / Course / Schedule / StudyPlan / KbDocument
│   │   ├── schemas/              # 请求与响应模型
│   │   ├── common/               # 统一返回、异常处理器
│   │   ├── dependencies/         # auth.py（JWT）、mcp_auth.py（MCP 侧 JWT）
│   │   ├── utils/                # jwt / password
│   │   ├── config.py             # 全部配置与常量
│   │   ├── database.py           # Base：id / create_time / update_time
│   │   └── main.py               # 建表、CORS、异常处理、静态挂载
│   ├── mcp_server.py             # 独立 FastMCP 进程，三个工具
│   ├── data/kb/                  # 课程资料原文件（运行时生成）
│   ├── data/chroma/              # Chroma 持久化目录（运行时生成）
│   ├── uploads/                  # 头像等公开静态文件
│   ├── requirements.txt
│   ├── .env.example
│   └── .env                      # 本地配置（勿提交真实密钥）
├── frontend/
│   ├── src/
│   │   ├── api/                  # axios 封装 + SSE fetch 封装
│   │   ├── views/                # 业务页面 + 课程助手
│   │   ├── layouts/              # 侧栏菜单（按角色显示）
│   │   ├── router/               # 路由与登录守卫
│   │   └── utils/                # request / auth / user
│   └── .env.development
├── docs/
│   ├── images/                   # 参考文档 14 张配图
│   └── 使用文档.md               # 分模块使用说明与图片索引
└── README.md
```

## 4. 环境要求与安装

- Node.js 22.18+（见 `frontend/package.json` 的 `engines`）
- Python 3.12+
- MySQL 8.0+

### 4.1 数据库

```sql
CREATE DATABASE campus_course_agent DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

```powershell
mysql -u root -p campus_course_agent < sql/campus-course-agent.sql
```

脚本会创建 `users` / `courses` / `schedules` / `study_plans` / `kb_documents`，并写入演示账号、3 门课程、aaa 的「今天 / 明天 / 后天」三条课表与两条学习计划。**注意脚本含 `DROP TABLE`，重复执行会清空业务数据。**

后端启动时仍会执行 `Base.metadata.create_all`；它只创建缺失的表，不会修改已有表结构。

### 4.2 后端依赖与配置

```powershell
cd backend
python -m venv .venv                 # 已有 .venv 且依赖齐全时直接跳过本行
.\.venv\Scripts\Activate.ps1
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

> **Windows 注意**：若 FastAPI / MCP / Chroma 正在后台运行，`.venv\Scripts\python.exe` 会被进程锁定，此时重复执行 `python -m venv .venv` 会报 `Unable to copy ... venvlauncher.exe to ... python.exe`。先停止四个服务（关闭对应的终端，或结束占用 8000 / 8001 / 8002 / 5173 端口的进程）再重建；`.venv` 已存在时通常无需重建，直接激活即可，重建也不会清掉 `site-packages` 里已安装的包。

复制 `.env.example` 为 `.env`（本项目已有一份，按需修改），关键配置：

```env
DATABASE_URL=mysql+pymysql://root:password@127.0.0.1:3306/campus_course_agent
JWT_SECRET_KEY=换成足够长的随机字符串

MCP_HOST=127.0.0.1
MCP_PORT=8001
MCP_PATH=/mcp

LLM_BASE_URL=https://api.deepseek.com
LLM_API_KEY=你的DeepSeekAPI-Key
LLM_MODEL_NAME=deepseek-flash
AGENT_RECURSION_LIMIT=14

EMBEDDING_API_KEY=你的向量模型密钥
EMBEDDING_BASE_URL=https://api.siliconflow.cn/v1
EMBEDDING_MODEL=BAAI/bge-m3
CHROMA_COLLECTION=course_docs
CHROMA_HOST=127.0.0.1
CHROMA_PORT=8002
```

> 对话模型与 Embedding 模型的地址、密钥、模型名**分别配置**，不要混用。更换 Embedding 模型时必须换用新的 `CHROMA_COLLECTION` 并把全部资料重新入库。

### 4.3 前端依赖

```powershell
cd frontend
npm install
```

`frontend/.env.development` 默认 `VITE_API_BASE_URL=http://127.0.0.1:8000`；Vite 已把 `/api`、`/uploads` 代理到后端，一般无需改动。

## 5. 启动（四个终端）

按 **Chroma → MCP → FastAPI → 前端** 的顺序启动，均在 `backend` 目录（除前端）：

```powershell
# 终端 A：Chroma 向量库
cd backend
.\.venv\Scripts\Activate.ps1
chroma run --path data/chroma --host 127.0.0.1 --port 8002
```

```powershell
# 终端 B：FastMCP 工具服务
cd backend
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH = "."
python mcp_server.py
```

```powershell
# 终端 C：FastAPI 业务与 Agent
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

```powershell
# 终端 D：前端
cd frontend
npm.cmd run dev
```

入口：

- 页面：<http://127.0.0.1:5173>
- 健康检查：<http://127.0.0.1:8000/>
- 接口文档：<http://127.0.0.1:8000/docs>
- MCP 端点：<http://127.0.0.1:8001/mcp>

> 修改 `.env` 后重启 FastAPI 与 MCP；修改 MCP 工具定义后重启 MCP。MCP 未启动时助手无法调用工具，Chroma 未启动时资料入库与检索不可用。

### Swagger 授权

`dependencies/auth.py` 使用 `OAuth2PasswordBearer(tokenUrl="/api/auth/token")`，项目提供了符合 OAuth2 password 规范的 `POST /api/auth/token` 端点。点击 Swagger 右上角 **Authorize**，填用户名密码即可，`client_id` / `client_secret` 留空（见 [`image10`](docs/images/image10.png)）。前端仍走原来的 JSON 登录接口。

### MCP Inspector 调试

```powershell
npx @modelcontextprotocol/inspector
```

选择 `streamable-http`，Server ID 填 `campus-course-agent`，URL 填 `http://127.0.0.1:8001/mcp`，自定义 Header 加 `Authorization: Bearer <学生 token>`；调试保存工具时再加 `X-Chat-Turn-Id: <32 位小写十六进制>`（见 [`image9`](docs/images/image9.png)）。

## 6. 内置演示账号

| 账号 | 密码 | 角色 | 用途 |
| --- | --- | --- | --- |
| `admin` | `admin` | 管理员 | 课程管理、课表管理、文档管理、用户管理 |
| `aaa` | `123` | 学生 | 有课表、有计划，用于完整演示 |
| `bbb` | `123` | 学生 | 无课表，用于验证数据隔离 |

自行注册的账号角色固定为 `student`。

## 7. 接口一览

统一返回 `{ "code": 200, "message": "请求成功", "data": ... }`；业务异常为 HTTP 200 + 非 200 的 `code`，未登录为 HTTP 401，参数校验失败为 HTTP 422。分页接口的 `data` 为 `{ list, total }`。

| 分组 | 方法与路径 | 权限 |
| --- | --- | --- |
| 权限 | `POST /api/auth/login`、`POST /api/auth/register`、`POST /api/auth/token` | 公开 |
| 用户 | `GET/PUT /api/user/me`、`PUT /api/user/password` | 登录 |
| 用户 | `GET /api/user/list`、`POST /api/user`、`PUT/DELETE /api/user/{id}` | 管理员 |
| 文件 | `POST /api/files/upload` | 登录 |
| 课程 | `GET /api/courses`、`GET/POST /api/courses`、`GET/PUT/DELETE /api/courses/{id}` | 管理员 |
| 课表 | `GET /api/schedules`（`page` / `page_size` / `date` / `user_id`） | 登录（学生固定查本人） |
| 课表 | `POST /api/schedules`、`PUT/DELETE /api/schedules/{id}` | 管理员 |
| 学习计划 | `GET/POST /api/study-plans`、`DELETE /api/study-plans/{id}` | 登录（只操作本人） |
| 文档 | `GET/POST /api/documents`、`GET /api/documents/{id}/preview`、`POST /api/documents/{id}/reingest`、`DELETE /api/documents/{id}` | 管理员 |
| MCP 调试 | `GET /api/mcp/my-schedule?date=YYYY-MM-DD` | 登录 |
| 对话 | `POST /api/chat/ask`、`POST /api/chat/stream` | 登录 |

`/api/chat/stream` 请求体：`{ "question": "我明天有什么课？", "history": [{ "role": "user", "content": "..." }] }`；响应为 `data: JSON` 事件流，事件类型见 [`image14`](docs/images/image14.png)。

## 8. 三条助手主线

| 用户提问 | Agent 工具 | 数据来源 |
| --- | --- | --- |
| 「我明天有什么课？」 | `get_my_schedules` | 按 JWT 查本人课表（MySQL） |
| 「实验需要预习吗？」 | `search_course_docs` | 全站共享资料（Chroma，Top-3） |
| 「生成一份学习计划并保存」 | `save_study_plan` | 按 JWT 写入本人计划（MySQL） |

同一轮可组合使用多个工具；只有用户**明确要求保存**时才写库，且数据库对 `(user_id, turn_id)` 建唯一约束，保证同一轮最多成功保存一次。

## 9. 冒烟验证

1. 导入 SQL，启动四个服务；`admin/admin` 登录，侧栏出现「课程管理 / 课表管理 / 文档管理 / 用户管理」，且无「我的课表 / 学习计划」。
2. 课程管理新增「数据结构 / DS101」，重复代码应提示已存在；已排课的课程删除应被拒绝。
3. 管理员上传一份含独有信息的 `.md` 资料，列表「已入库」为「是」；重新入库两次，向量片段数不累加。
4. `aaa/123` 登录，「我的课表」看到 3 条；日期筛「明天」只剩数据结构；`bbb` 登录列表为空。
5. 「课程助手」依次问课表 → 问资料 → 要求保存计划，过程区依次出现「查询我的课表 / 检索课程资料 / 保存学习计划」，`done` 后回答完整。
6. 「学习计划」页新增一条与对话保存正文一致的记录；`bbb` 看不到。
7. Swagger / Inspector 下验证：无 token 调用接口返回 401，学生调用管理员接口返回 `code=403`，同一轮次 ID 重复保存只成功一次。

更详细的分模块操作与截图见 [`docs/使用文档.md`](docs/使用文档.md)。

## 10. 常见问题

| 现象 | 排查 |
| --- | --- |
| 后端启动报数据库连接错误 | MySQL 是否启动、库是否创建、`.env` 的 `DATABASE_URL` 是否正确 |
| 前端 401 | 后端是否启动、localStorage 中是否有过期 token，可清站点数据后重登 |
| 助手提示「加载课程工具失败」 | MCP 进程是否运行、`MCP_HOST/PORT/PATH` 是否一致；看 MCP 终端日志 |
| 助手提示「未配置 LLM_API_KEY」 | 填 `.env` 后重启 FastAPI |
| 资料上传失败并整批撤销 | 检查 `EMBEDDING_API_KEY`、Chroma 服务、文件是否为零字节 / 扫描版 PDF / 非 UTF-8 文本 |
| 资料问题回答「检索不可用」 | Chroma 服务与 Embedding 配置；这与「知识库中没有检索到相关内容」是两种情况 |
| 文档管理页面无数据 | 需管理员账号；学生直接打开页面会显示管理员提示且不加载资料 |
| Swagger Authorize 失败 | 使用 `/api/auth/token` 端点，`client_id` / `client_secret` 留空 |
| MCP 启动报 `KeyError: 'websockets-sansio'` | FastMCP 2.13 需要 `uvicorn>=0.35`；本项目已固定 `uvicorn==0.38.0`，旧环境请升级后重启 MCP |
| `python -m venv` 报 `Unable to copy ... venvlauncher.exe` | 后台服务占用了 `.venv\Scripts\python.exe`；停止占用 8000 / 8001 / 8002 / 5173 的进程后重试。已有 `.venv` 时可直接跳过该命令 |
| `pip install` 依赖冲突 | 保持 `requirements.txt` 中的 `starlette>=0.46,<0.47` 与 `websockets==15.0.1`，勿升到 starlette 1.x |

## 11. 维护与扩展

新增业务功能的标准套路（与脚手架一致）：

```text
models 建表 → schemas 定格式 → services 写业务 → api 暴露接口 → 前端 api / views 对接 → 菜单与路由
```

新增模型后记得在 `app/models/__init__.py` 的 `__all__` 中导出，`main.py` 的 `from app.models import *` 才会注册进 `Base.metadata`。`create_all` 只建新表，改已有表结构需手写 `ALTER TABLE` 迁移脚本。

安全约定：新增的敏感接口必须挂 `get_current_user` / `get_current_admin`；新增 MCP 工具只能从 JWT 取身份，不要接受模型填写的 `user_id`。前端隐藏菜单只负责体验，后端校验才负责安全。
