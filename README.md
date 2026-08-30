# XiuMi Layout Agent

把编辑部的新文字稿按层级（大标题/二级标题/…/正文/图片位）自动套用到既有秀米模板 HTML 上，生成可直接上传秀米的 `result.html`。

> 背景：秀米内置编辑器难用且无法导出，但可通过 Edge 插件获取"图文"的 HTML。编辑部工作的核心是**复用旧模板 + 换新内容**，因此本项目把这一过程自动化。完整需求见 [requirements.md](requirements.md)。

## 工作原理（标准流程）

1. **开新项目**：对话中说明，Agent 生成 `<task_id>`（格式 `YYYYMMDD_短slug`）并清理上次残留。
2. **入库模板**：提供 模板文字稿 + 模板 HTML → Agent 将文字层级与 HTML 格式一一匹配，生成"标准格式文件"（JSON 映射）。
3. **提交新稿**：提供 新文字稿（txt/word，可为脏格式）+ 图片 → Agent 自动清洗、分级、标记图片插入位置，并上传图床获取外链。
4. **替换生成**：Agent 按模板格式做文本替换 / 节点复制 / 节点删除，产出 `workspace/<task_id>/output/result.html`。
5. **人工校验**：上传秀米，手机端扫码预览（手机预览是最终校验标准）。

**原则**：文字稿一字不改、图片顺序不调换；HTML 只能由模板节点替换/复制/删除得到，绝不凭空手写。

## 技术选型

- **Python 3.11+**：LLM/Agent 生态最成熟，`BeautifulSoup4 + lxml` 处理 HTML 可靠方便，编辑部场景无性能瓶颈，迭代最快。
- 配置 `python-dotenv`（读 `secrets/config.env`），测试 `pytest`，Lint `ruff`。

## 目录结构

```
src/xiumi_layout_agent/
├── chat/         # 对话主管（先建）：LLM 适配、Agent 循环、工具注册表、
│                 #   固定问答引导（收材料零 LLM）、状态机、TUI
├── normalize/    # 文字稿清洗与分级（txt/word→结构化，容忍脏输入）（桩）
├── template/     # 模板解析：层级↔HTML格式匹配、标准格式文件读写（桩）
├── replace/      # 核心替换：新稿套用模板生成 result.html（桩）
├── image/        # 图片位标记、图床上传外链（留修图/拼图接口）（桩）
├── storage/      # 模板库存取选用（扩展接口）（桩）
└── cli.py        # 命令行入口
tests/           # 与 src 同构
inbox/           # 客户唯一投递处（一次一个文件，助手引导归档）
templates/       # 模板文字稿 + 模板 HTML（入库）
workspace/       # 每次任务的输入输出（不入库）
secrets/         # 敏感信息（不入库，见 SECRET.md）
secrets.example/ # 敏感信息结构示例（入库）
scripts/         # 辅助脚本
```

实施计划见 [PLAN.md](PLAN.md)（先建主管后写工具，当前进度 M2）。

## 快速开始

```bash
# 1. 装依赖（Python 3.11+）
uv venv .venv --python 3.11
uv pip install --python .venv/bin/python -e ".[dev]"

# 2. 配置 LLM（不配也能跑，会进离线演示模式）
cp secrets.example/config.env.example secrets/config.env
#    编辑 secrets/config.env，按注释填空即可

# 3. 启动
.venv/bin/xiumi chat
```

### 常用指令

| 指令 | 作用 |
| --- | --- |
| `.venv/bin/xiumi chat` | 启动对话（默认命令，`xiumi` 不带参数同样生效） |
| `.venv/bin/xiumi clean` | 一键清空 inbox/ 与 workspace/ 下所有任务文件（清测试垃圾用） |
| `.venv/bin/python -m pytest` | 跑测试 |
| `.venv/bin/python -m ruff check .` | Lint |

## 使用方法（对话流程）

启动后开场白固定为"按 y 开始新项目"。收材料阶段是**固定问答，不耗 LLM**：

```
排版小助手：按 y 开始新项目
你：y
助手：接下来请您把【模板文字稿】放进 inbox 文件夹，放好后输入 y
      接下来请您把【模板网页文件】放进 inbox 文件夹，放好后输入 y
你：（把文件拖进仓库根目录的 inbox/ 文件夹，格式不限）
你：y
助手：收到 2 个文件（…）。本阶段材料齐了！
（材料已存到 workspace/<任务号>/input/）
助手：接下来请您把【新文字稿】放进 inbox 文件夹……如果您有【要用的图片】……
你：y / 没有
（接下来：材料收齐，AI 开始检查处理，请稍候……）
（AI 正在思考……）
助手：（LLM 接管，开始干活）
```

### AI 接手后的三个阶段

材料收齐后由 LLM 主管接手，严格按以下三步走，每步没完成不进下一步：

1. **检查材料**：核对文件齐不齐（模板文字稿、模板网页文件、新文字稿；图片可选）。缺了就找你补，直到补齐；齐了直接开工，不反复确认。
2. **分级展示**：把模板稿和新稿分别按 大标题/二级标题/正文/图片位置 分级，分级结果写成展示文件放进 `outbox/` 文件夹供你查看，并逐条念给你听；你有意见就改，反复交流直到你确认。
3. **生成成品**：套用模板生成成品放进 `outbox/`；你看了不满意就调整再生成，直到满意为止。最后提醒你上传秀米并手机扫码预览。

文件夹约定：

| 文件夹 | 用途 |
| --- | --- |
| `inbox/` | 你投材料的地方（一次一个文件，格式不限） |
| `outbox/` | AI 产出物（分级展示、最终成品）都放这里 |

### 小贴士

- 没放文件就说 **没有**；图片是可选项，说 **没有** 可跳过
- Windows 的 `xxx:Zone.Identifier` 等系统垃圾文件会被自动忽略并清掉
- 材料没做齐功能时 AI 会如实说"现在还没有这个工具，功能还没做好"
- 输入 **退出** 结束；想清空重来跑 `.venv/bin/xiumi clean`

## 开发

```bash
.venv/bin/python -m pytest          # 测试，全绿才算完成
.venv/bin/python -m ruff check .    # Lint
```

Agent 协作规范见 [AGENTS.md](AGENTS.md)，敏感信息说明见 [SECRET.md](SECRET.md)。

## 路线图

- [x] 需求与架构设计
- [ ] normalize：文字稿清洗与分级
- [ ] template：标准格式文件（层级↔HTML 片段映射）
- [ ] replace：模板套用替换，生成 result.html
- [ ] image：图床上传外链
- [ ] storage：模板库存取选用（自设计模板、复用已存模板）
- [ ] image：修图/拼图接口（`ImageProcessor`）
- [ ] UI 封装（远期）
