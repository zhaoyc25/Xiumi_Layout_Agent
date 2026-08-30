# AGENTS.md — 本仓库 Agent 协作规范

本文件是所有 AI Agent（opencode / Codex / Claude 等）在本仓库工作时的**强制规范**。做任何事之前先读完本文件。

## 0. 项目一句话

XiuMi Layout Agent：把编辑部的新文字稿按层级（大标题/二级标题/…/正文/图片位）套用到既有秀米模板 HTML 上，生成可直接上传秀米的 `result.html`。业务背景见 `requirements.md`。

## 1. 铁律（违反任何一条即为严重事故）

1. **敏感信息绝不上 git**：`secrets/`、`.env`、`*.key`、`*.pem`、任何 API Key/token/密码不得出现在源码、测试、文档、日志、commit message 中。详见 `SECRET.md`。提交前必须检查 `git status` / `git diff --staged`。
2. **小步提交**：每次改动只做一件事，改动面尽量小（一次不超过 ~300 行或 3 个文件，除非是脚手架/文档初始化）。不要顺手重构无关代码，不要一次性大改。
3. **每步必有测试**：任何功能性改动（新函数/新模块/改逻辑）都必须附带或更新测试，并在结束前运行 `pytest`，全绿才算完成。纯文档改动可豁免。
4. **禁止随意输出 HTML**：生成的 HTML **必须**来自 `templates/` 下的模板，通过替换/复制/删除节点得到；Agent 不得凭空手写标签、属性、内联样式。替换逻辑只允许修改文本节点、图片 `src`，以及按模板既有节点进行复制/删除。
5. **不擅自改写原文**：文字稿内容一字不改（错别字也不改，可报告人工）；图片顺序不调换。这是编辑部的工作准则。

## 2. 技术栈与命令

- 语言：**Python 3.11+**（理由：LLM/Agent 生态最成熟、BeautifulSoup/lxml 处理 HTML 方便、编辑部场景无性能瓶颈、迭代最快）。
- HTML 解析：`beautifulsoup4` + `lxml`（禁止正则解析 HTML）。
- 配置：`python-dotenv`，读取 `secrets/config.env`。
- 测试：`pytest`。
- 质量检查（每次交付前运行）：
  ```bash
  pytest
  ruff check .
  ```
- 如需运行单个模块：`python -m xiumi_layout_agent.cli <cmd>`。

## 3. 目录结构（严格遵守）

```
src/xiumi_layout_agent/
├── normalize/   # 文字稿清洗与分级（txt/word→结构化，容忍脏输入）
├── template/    # 模板解析：文字稿层级 ↔ 模板HTML格式 的匹配、标准格式文件读写
├── replace/     # 核心替换：结构化新稿套用模板生成 result.html（复制/删除多余节点）
├── image/       # 图片位标记、图床上传获取外链（留修图/拼图接口）
├── storage/     # 模板库的存取与选用（扩展接口）
└── cli.py       # 命令行入口/Agent 对话入口
tests/           # 与 src 同构，每个模块一个测试文件
templates/       # 模板文字稿 + 模板HTML（入库，不含敏感信息）
workspace/       # 每次任务的输入输出（不入库）
secrets/         # 敏感信息（不入库，见 SECRET.md）
secrets.example/ # 敏感信息结构示例（入库）
scripts/         # 辅助脚本
```

## 4. 任务工作流（标准流程，按步执行）

1. 用户说"开新项目"→ 先清理上次残留：删除 `workspace/<task_id>/` 下的废料（上次任务若暴力中断，本次开工前必须清理）。
2. 索要模板文字稿 + 模板 HTML → 存入 `workspace/<task_id>/input/` → 生成"标准格式文件"（层级↔HTML 片段的映射，JSON）。
3. 索要新文字稿 + 图片 → 分级、标记图片插入位置 → 图片上传图床取外链。
4. 执行替换 → 生成 `workspace/<task_id>/output/result.html`。
5. 提醒人工上传秀米并手机端预览校验。

`<task_id>` 格式：`YYYYMMDD_短slug`。

## 5. 扩展接口（现在只留桩，不要提前实现）

- 模板库存取选用：`storage/` 模块接口（自设计模板、复用已存模板）。
- 修图/拼图：`image/` 模块预留 `ImageProcessor` 接口。

## 6. 沟通与汇报

- 修改文件后直接结束，不要长篇解释；用户问才答。
- 遇到需求模糊（如文字稿层级无法判断、模板匹配有歧义），停下来问人工，不要猜。
- 每完成一个"步"，报告：改了什么文件、测试结果（pytest 输出摘要）。
- 发现文字稿明显错误（错字、敏感词）不要擅自修改，列出问题请人工定夺。

## 7. Git 规范

- 不主动 commit/push，除非用户明确要求。
- commit message 用中文或英文均可，格式：`<scope>: <做了什么>`，如 `replace: 支持同级节点复制`。
- 提交前必须：`git status` + `git diff --staged` 自查，确认无敏感信息、无无关文件。
