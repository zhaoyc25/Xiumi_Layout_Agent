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
├── normalize/   # 文字稿清洗与分级（txt/word→结构化，容忍脏输入）
├── template/    # 模板解析：层级↔HTML格式匹配、标准格式文件读写
├── replace/     # 核心替换：新稿套用模板生成 result.html
├── image/       # 图片位标记、图床上传外链（留修图/拼图接口）
├── storage/     # 模板库存取选用（扩展接口）
└── cli.py       # 命令行入口 / Agent 对话入口
tests/           # 与 src 同构
templates/       # 模板文字稿 + 模板 HTML（入库）
workspace/       # 每次任务的输入输出（不入库）
secrets/         # 敏感信息（不入库，见 SECRET.md）
secrets.example/ # 敏感信息结构示例（入库）
scripts/         # 辅助脚本
```

## 快速开始

```bash
# 1. 安装依赖
pip install -e .   # 或按 pyproject.toml 手动安装

# 2. 配置敏感信息
cp secrets.example/config.env.example secrets/config.env
#    编辑 secrets/config.env，填入 LLM API Key、图床 token 等

# 3. 跑测试
pytest

# 4. 命令行使用（开发中）
python -m xiumi_layout_agent.cli --help
```

## 开发

```bash
pytest          # 测试，全绿才算完成
ruff check .    # Lint
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
