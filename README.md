# Personal Content Skills

一组面向中文个人内容创作的可安装 Skill，覆盖：

- `xiaohongshu-alive-writer`：小红书图文/资讯搬运/口播包装，强调真实表达、事实核验和去 AI 味。
- `alive-oral-scriptwriter`：30 秒至 5 分钟口播稿，强调自然口语、思考过程和时长控制。
- `personal-visual-storyteller`：本人真实素材优先的封面、配图、分镜与视频视觉方案。
- `douyin-persona-audit`：在用户授权和平台允许范围内，对本人抖音作品做证据化表达审计。
- `xiaohongshu-publish-orchestrator`：把已完成内容编排成小红书发布包，执行发布前校验；只有在明确授权且存在可用发布通道时才发布。

## 核心原则

1. **真实优先**：不虚构用户经历、数据、来源、热搜或个人画像。
2. **事实与判断分离**：资讯内容必须保留时间、来源和未知项。
3. **读取权限与发布权限分离**：能访问素材不等于可以公开发布。
4. **个人证据私有**：账号 ID、短链、本人照片观察、私密人设证据不进入公共仓库。
5. **发布可回溯**：发布成功记录时间、平台、笔记链接/ID；失败保留素材，不自动重复发。

## 目录

```text
personal-content-skills/
├── xiaohongshu-alive-writer/
│   └── SKILL.md
├── alive-oral-scriptwriter/
│   └── SKILL.md
├── personal-visual-storyteller/
│   └── SKILL.md
├── douyin-persona-audit/
│   └── SKILL.md
├── xiaohongshu-publish-orchestrator/
│   └── SKILL.md
├── shared/
│   ├── douyin-full-account-protocol.md
│   ├── douyin-work-ledger-template.csv
│   └── persona-evidence.example.md
└── examples/
    └── reward-script-validation.md
```

## 版本

Public-safe source package: **V3.4**.

V3.4 在 V3.3 基础上新增小红书发布编排 Skill，并把个人账号凭据、本人素材证据从公共代码中剥离。

> 私有运行时证据建议保存在 `shared/private/` 或外部私有存储中；该目录已加入 `.gitignore`。
