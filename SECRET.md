# SECRET.md — 敏感信息存放说明

本仓库**严禁**将任何敏感信息提交到 git（已在 `.gitignore` 中屏蔽）。本文档只说明敏感信息**存放位置**，**绝不在此文件中写入任何真实密钥、账号、密码、URL**。

## 存放位置

所有敏感信息统一存放在仓库根目录下的 `secrets/` 文件夹中（该文件夹整体被 `.gitignore` 忽略）：

```
secrets/
├── config.env              # 环境变量（API Key、图床 token 等）
├── image_host_credentials.txt   # 图床/云端存储的账号凭据（如需要）
└── accounts.txt            # 其他人工账号信息（如需要）
```

## 使用方式

1. 复制 `secrets/config.env.example` 为 `secrets/config.env`，填入真实值。
2. 程序与脚本一律从 `secrets/config.env`（或环境变量）读取，**禁止**将密钥硬编码进任何源码、测试、文档、commit message。
3. `secrets/` 中只能放**真实密钥文件**；其结构示例放在 `secrets.example/`（可入库，不含真实值）。

## 检查规则（Agent 与人工均须遵守）

- 提交前确认：`git status` 中不得出现 `secrets/`、`.env`、`*.key`、`*.pem`、含 token 的文件。
- 如发现敏感信息已提交：立即停止一切后续操作，通知人工处理（需要改写 git 历史并**吊销**该密钥），不可只做简单删除了事。
- 日志与测试中禁止打印密钥原文。

## 当前已知敏感项清单

| 敏感项 | 位置 | 备注 |
| --- | --- | --- |
| LLM API Key | `secrets/config.env` 的 `XIUMI_LLM_API_KEY` | 用于文本分级/Agent 对话 |
| 图床/云存储凭据 | `secrets/config.env` 的 `XIUMI_IMAGE_HOST_*` | 用于上传图片获取外链 |
| 其他人工账号 | `secrets/accounts.txt` | 按需添加，新增须在此登记位置 |
