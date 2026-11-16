# Contributing

这个仓库维护可安装、可审计、可回归验证的 Skill，而不是零散 Prompt。

## 新增 Skill

必须同时新增：

- `skills/<skill-name>/SKILL.md`
- `contracts/<skill-name>.json`
- `skill-registry.json` 条目
- 至少一个验证样例或测试

## 修改 Skill

- Patch：文字、示例、规则细化，不改变输入输出。
- Minor：新增向后兼容能力。
- Major：删除/改名核心输入输出或改变默认行为。

## 本地检查

```bash
make check
make stats
```

## 隐私

公共仓库禁止提交：

- Cookie / Token / API Key / 验证码
- 未授权账号ID、短链
- 真实私密Persona Evidence
- 用户本人原始照片/视频
- 内部业务资料

真实运行数据使用私有存储或被gitignore的目录。
