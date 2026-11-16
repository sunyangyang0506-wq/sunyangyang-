# Skills Repository

这是一个独立维护的个人/业务 AI Skill 仓库，当前工程版本 **V3.5**。

## 当前 Skills

| Skill | Version | 用途 |
|---|---:|---|
| `xiaohongshu-alive-writer` | 3.4.0 | 小红书图文、资讯简报、标题/标签与发布包 |
| `alive-oral-scriptwriter` | 3.3.0 | 30秒–5分钟自然口播稿 |
| `personal-visual-storyteller` | 3.3.0 | 真人授权素材的封面、配图、分镜与视觉处理 |
| `douyin-persona-audit` | 1.2.0 | 抖音作品证据化表达审计 |
| `xiaohongshu-publish-orchestrator` | 1.0.0 | 发布检查、权限门禁、防重复与发布回执 |

## 工程结构

```text
skills/<skill-name>/SKILL.md
contracts/<skill-name>.json
schemas/
shared/
examples/
scripts/
tests/
.github/workflows/
skill-registry.json
```

每个 active Skill 必须有对应 Contract。

## 使用

列出可安装 Skill：

```bash
python3 scripts/install_skill.py --list
```

安装：

```bash
python3 scripts/install_skill.py xiaohongshu-alive-writer --target ./installed-skills
```

## 质量检查

```bash
make check
make stats
```

CI在push到main和Pull Request时自动检查：

- frontmatter完整性
- 名称与目录一致
- SemVer
- Registry版本一致性
- Contract存在与基本结构
- 私密目录误提交
- 明显Secret模式
- 单元测试

## 隐私边界

本仓库当前为 public：

- 不提交账号凭据、Cookie、Token、验证码。
- 不提交本人照片和真实私密Persona Evidence。
- 不提交未授权内部业务资料。
- 私有运行数据使用私有存储或gitignore目录。

## 版本

- Repository：3.5.0
- Skill：各自维护SemVer
- Contract：独立版本

详见 `VERSIONING.md` 与 `CHANGELOG.md`。
