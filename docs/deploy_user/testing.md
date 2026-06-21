# 测试规范

- [测试框架](#测试框架)
- [覆盖率要求](#覆盖率要求)
- [四类用例](#四类用例)
- [运行测试](#运行测试)
- [测试命名](#测试命名)

## 测试框架

- pytest
- pytest-cov（覆盖率）

## 覆盖率要求

- 整体覆盖率 >= 95%
- 核心模块覆盖率 >= 95%

## 四类用例

每个功能必须包含：
1. **正常值** - 标准输入，验证正确输出
2. **空入参** - 空/None输入，验证不崩溃
3. **边界极值** - 最小/最大值，验证边界处理
4. **非法格式** - 错误类型/范围，验证异常抛出

## 运行测试

```bash
# 全部测试
python -m pytest tests/ -v

# 覆盖率报告
python -m pytest tests/ --cov=src --cov-report=term-missing

# 单模块测试（示例：决策模块）
python -m pytest tests/left/action/decision/ -v

# 易用性测试
python -m pytest tests/test_u1_config_path_consistency.py tests/test_u2_cli_args.py -v
```

## 测试命名

- 测试类：`Test{ModuleName}`
- 测试方法：`test_{scenario}_{expected_result}`
