# Skills Repository

这是一个独立维护的个人/业务 AI Skill 仓库。

## 当前 Skills

| Skill | Version | 用途 |
|---|---:|---|
| `xiaohongshu-alive-writer` | 3.4.0 | 小红书图文、资讯简报、标题/标签与发布包 |
| `alive-oral-scriptwriter` | 3.3.0 | 30秒–5分钟自然口播稿 |
| `personal-visual-storyteller` | 3.3.0 | 真人授权素材的封面、配图、分镜与视觉处理 |
| `douyin-persona-audit` | 1.2.0 | 抖音作品证据化表达审计 |
| `xiaohongshu-publish-orchestrator` | 1.0.0 | 小红书发布检查、权限门禁、防重复与发布回执 |

## 仓库规范

```text
.
├── skills/
│   ├── <skill-name>/
│   │   └── SKILL.md
├── shared/
│   ├── common protocols / templates
├── examples/
│   └── validation cases
├── skill-registry.json
└── README.md
```

### 安装单元

每个 `skills/<skill-name>/` 都是独立 Skill 单元，入口固定为：

```text
skills/<skill-name>/SKILL.md
```

需要共享协议时由 Skill 显式引用 `shared/`。

## 版本管理

- Skill 自己维护 `version`。
- 仓库维护 `skill-registry.json` 作为索引。
- 行为发生变化时升级 Skill 版本。
- 仅文案、注释、示例修订可按 patch 处理。
- 重大工作流或输入输出协议变化按 minor/major 升级。

## 隐私边界

该仓库当前为 **public**，因此：

- 不提交账号ID、短链、Cookie、Token、验证码。
- 不提交本人照片、人像观察、真实私密 Persona Evidence。
- 不提交未授权的内部工作资料。
- 私有运行时数据放在 `shared/private/` 或外部私有存储。
- `.gitignore` 已屏蔽常见私密目录和媒体文件。

## 当前协作链

```text
想法 / 语音 / 资讯
        ↓
xiaohongshu-alive-writer
        ↓
alive-oral-scriptwriter（需要口播时）
        ↓
personal-visual-storyteller（需要视觉时）
        ↓
xiaohongshu-publish-orchestrator
        ↓
发布 / 待手动发布 / 失败回执
```

抖音历史作品的真实表达校准由：

```text
douyin-persona-audit
        ↓
证据化反馈到 writer / oral / visual skills
```

## 当前版本

Repository: **V3.4**

本版本完成：
- 独立 Skill 仓库标准化；
- `skills/<name>/SKILL.md` 目录规范；
- 小红书发布编排 Skill；
- 抖音证据审计协议；
- 公共和私人 Persona Evidence 分离。
