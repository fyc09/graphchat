# GraphChat MVP

基于问答逻辑的动态知识网状图学习助手（MVP）。

## 项目结构

- `.` 是 Python 项目根（`pyproject.toml` 在根目录）。
- `graphchat/` 是唯一 Python 包。
- `graphchat/web/` 是前端源码（Vue3 + TS）。
- `graphchat/static/` 是前端构建产物目录（由 Vite build 生成）。

## 配置

服务启动时读取执行目录（`cwd`）下的 `config.json`：

- 若不存在，会自动复制 `config.example.json` 为 `config.json`。
- 需要在 `config.json` 里填写真实 LLM 参数：
  - `llm.base_url`
  - `llm.api_key`
  - `llm.model`

## Makefile 命令

```bash
make py-install    # 安装 Python 包（editable）
make web-install   # 安装前端依赖
make web-build     # 构建前端到 graphchat/static
make web-dev       # 单独启动前端开发服务(5173)
make build         # 一次执行 py-install + web-install + web-build
make run           # 启动服务（graphchat-server）
make dev           # uvicorn reload 开发模式
make clean         # 清理构建与数据产物
```

## 运行

```bash
make build
make run
```

启动后访问 `http://127.0.0.1:8000`，后端会直接提供打包后的前端静态页面。

## 关键行为

- 初始化主题时，后端先调用 LLM 生成“单节点完整描述”，并要求按 Markdown `## 标题` 分点组织内容。
- 后续自由提问同样要求按 `## 标题` 分点回答，图上每个节点可按标题折叠查看段落。
- 初始化与提问使用普通请求返回，生成完成后更新图节点内容。
- 如果 `config.json` 里的 LLM 配置不正确（例如 `api_key` 仍是 `replace_me`），服务会在启动时直接报错并退出。

若你选择前后端分离开发：

1. `make dev` 启动后端
2. `make web-dev` 启动前端（已配置 `/api` 代理到 `8000`）
