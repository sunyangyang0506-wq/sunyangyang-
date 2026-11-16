# Versioning

仓库采用三层版本。

## Repository Version
位于 `skill-registry.json -> repository_version`，描述目录规范、CI、Schema和共享工具链。

## Skill Version
位于每个 `SKILL.md` frontmatter 的 `version`，使用 SemVer。

## Contract Version
位于 `contracts/<skill>.json -> contract_version`。只有输入、输出和硬门禁发生协议级变化时才升级。

Registry状态：
- `experimental`
- `active`
- `deprecated`

deprecated Skill 不应被新的自动化任务选择。
