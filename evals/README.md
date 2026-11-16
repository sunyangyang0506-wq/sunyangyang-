# Golden Evaluations

当前：5个 active Skill × 3个 Case = **15个 Golden Cases**。

CI 默认只做数据集完整性/断言协议检查，不调用模型，因此不会把静态检查冒充模型质量评测。

外部执行器生成候选输出后，按 `<case-id>.txt` 存放到目录，再执行：

```bash
python3 scripts/eval_golden.py --candidates candidate-output
```

支持断言：
- contains_all
- contains_any
- not_contains

建议Release门槛：
- hard guard / not_contains：100%
- 总断言：>=90%
- 隐私、事实虚构、越权发布类失败：直接阻断
