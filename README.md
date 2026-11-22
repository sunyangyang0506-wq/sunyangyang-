# Skills Repository

个人/业务 AI Skill 工程仓库，当前 Repository **V3.6.0**。

## Teach English in China — Job Finder

[Find English teaching jobs in China or online from abroad](standalone-skills/teach-english-in-china-job-finder/SKILL.md), with pay, requirements and checked application links. Choose in-person teaching, online teaching, or both.

中文：去中国教英语｜岗位检索。原名：`find-china-english-teaching-jobs`。

## 注册的 6 个 Skills

- [赴华医疗英文 X 资讯与咨询](skills/publish-china-care-updates/SKILL.md) 1.0.0
- xiaohongshu-alive-writer 3.4.0
- alive-oral-scriptwriter 3.3.0
- personal-visual-storyteller 3.3.0
- douyin-persona-audit 1.2.0
- xiaohongshu-publish-orchestrator 1.6.0

## 当前工程能力

- Skill Registry
- Metadata / Contract Schema
- 6个输入输出Contract
- **17个Golden Cases**
- Repository Validator
- Golden Eval Runner
- 单元/回归测试
- 一键安装、全部安装、检查更新、升级
- Release打包与SHA256
- GitHub Actions CI
- Tag驱动自动GitHub Release
- 隐私/Secret基础检查

## 一键使用

```bash
./bin/skills --list
./bin/skills xiaohongshu-alive-writer --target ./workspace
./bin/skills --all --target ./workspace
./bin/skills --check-updates --target ./workspace
./bin/skills xiaohongshu-alive-writer --target ./workspace --upgrade
```

安装后的Workspace保持：

```text
workspace/
  skills/<name>/SKILL.md
  contracts/<name>.json
  shared/...  # 仅需要时
```

因此Skill内部相对引用不会失效。

## 质量与评测

```bash
make check
make stats
make package
```

CI默认只校验Golden数据集，不调用模型；有候选输出时：

```bash
python3 scripts/eval_golden.py --candidates candidate-output
```

详见 docs/EVALUATION.md。

## Release

推送 `vX.Y.Z` tag 后自动创建GitHub Release并上传zip与SHA256。

详见 docs/RELEASE.md。

## 隐私

仓库为public：不提交账号凭据、Cookie、Token、验证码、本人原始照片、真实私密Persona Evidence或未授权内部资料。
