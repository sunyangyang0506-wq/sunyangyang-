# Evaluation Strategy

CI层：Registry / Contract / Frontmatter / Golden数据完整性 / 单测 / 打包 / 隐私检查。

这层不调用模型，因此不冒充生成质量分。

外部模型执行器生成 `<case-id>.txt` 后：

```bash
python3 scripts/eval_golden.py --candidates candidate-output
```

门槛建议：
- not_contains类硬门禁100%通过
- 总断言>=90%
- 隐私、事实虚构、越权发布失败直接阻断Release

后续可扩展多模型、多温度、token、延迟、费用与回归差异。
