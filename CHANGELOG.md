# Changelog

## 3.8.0 - 2026-11-24
- 小红书发布编排 v1.11.0：通用首次配置表、原生权限核验、私人配置模板与缺项检查器。
- 按用户/账号/栏目隔离授权；仅制作免登录，持续发布复用唯一任务，待首篇验证不计作权限已获。
- 去除通用 Mac 默认时间与提交默认时区；保留现有用户配置，无需重新授权同一范围。
- 补充初始化权限、撤权、跨账号/设备、来源扩大及配置隐私回归与评测案例。

## 3.7.0 - 2026-11-24
- 明确 Mac 唯一发布端、云端制稿交接和完整原稿模式；六个注册 Skill 同步渠道边界与版本。
- 修复预约及旧版中文状态去重、清单尺寸冲突、空正文与空核验证据处理。
- 发布脚本回归进入 CI；新增 Mac 全流程锁与验收说明，区分代码验证和实际定时公开回执。
- README、Registry、Skill 版本同步。

## 3.6.0 - 2026-11-16
### Added
- 15个Golden Cases
- Golden Eval Runner与candidate断言评测
- 一键全部安装、检查更新、升级
- 安装时携带Contract与Shared Dependencies
- Release打包器与SHA256
- Tag驱动GitHub Release
- V3.6回归测试
- Evaluation / Release文档
### Changed
- Registry增加evals与shared_dependencies
- CI增加Golden Eval与Package dry-run
- Repository版本升级到3.6.0

## 3.5.0 - 2026-11-16
- Schema、Contract、Validator、Installer、Tests、CI。

## 3.4.0 - 2026-11-16
- 标准skills目录、小红书发布编排、抖音证据审计。
