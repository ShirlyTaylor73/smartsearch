## ADDED Requirements

### Requirement: 帮助与版本入口
系统 SHALL 支持根命令和子命令级 `-h/--help`，并 SHALL 支持 `-v/--version` 输出可机器读取的产品名称与版本。

#### Scenario: 查看根帮助
- **WHEN** 用户运行 `smart-search -h`
- **THEN** 系统展示四个 Agent 搜索命令和面向维护者的功能性命令分组
- **AND** 不展示已隐藏的 provider 专用兼容命令

#### Scenario: 查看命令帮助
- **WHEN** 用户运行 `smart-search docs --help`
- **THEN** 系统展示 `search`、`tree`、`read` 三个 provider 无关子命令及其用途

#### Scenario: 查看版本
- **WHEN** 用户运行 `smart-search -v`
- **THEN** 标准输出只包含 `smart-search <version>` 形式的版本信息
- **AND** 进程成功退出

### Requirement: 初始化与配置管理
系统 SHALL 保留 `setup` 以及 `config path|list|set|unset`，供维护者配置凭据、能力链、超时和 fallback 策略；配置展示 SHALL 默认脱敏。

#### Scenario: 初始化配置
- **WHEN** 维护者运行 `smart-search setup`
- **THEN** 系统引导配置搜索、文档、抓取和站点探索所需能力
- **AND** 不要求为每个已支持 provider 都提供凭据

#### Scenario: 查看配置
- **WHEN** 维护者运行 `smart-search config list`
- **THEN** 系统展示有效配置和各能力链
- **AND** API key、token 等敏感值被隐藏

### Requirement: 健康检查与错误排查
系统 SHALL 提供 `doctor` 用于整体预检，并 SHALL 提供以公开能力为入口的 `diagnose [search|docs|fetch|map]` 专项排查。

#### Scenario: 运行整体健康检查
- **WHEN** 维护者运行 `smart-search doctor`
- **THEN** 系统报告四种公开能力是否至少有一个可用 provider
- **AND** 对 `docs.search`、`docs.tree`、`docs.read` 分别报告配置缺失、连接失败和降级状态

#### Scenario: 排查抓取失败
- **WHEN** 维护者运行 `smart-search diagnose fetch`
- **THEN** 系统逐项测试已配置的抓取 provider
- **AND** 输出脱敏后的失败阶段、错误类型、延迟和建议操作

#### Scenario: 排查文档子操作
- **WHEN** 维护者运行 `smart-search diagnose docs`
- **THEN** 系统分别测试 `docs.search`、`docs.tree`、`docs.read` 的已配置 provider
- **AND** 清楚标识只有单一 provider 或没有同操作 fallback 的情况

#### Scenario: Agent 收到错误
- **WHEN** 普通搜索命令返回不可恢复错误
- **THEN** 错误信息可以建议维护者运行对应的 `doctor` 或 `diagnose` 命令
- **AND** 不将诊断命令作为 Agent 自动管理 provider 的要求

### Requirement: Debug 与日志隔离
系统 SHALL 默认保持 Agent 输出简洁，并仅在显式 `--debug` 或维护者配置开启时输出 provider 尝试、路由细节和内部诊断信息。

#### Scenario: 默认调用
- **WHEN** Agent 未指定 debug 运行搜索命令
- **THEN** 输出不包含 provider 链、fallback 过程、模型 breaker 或内部路由评分

#### Scenario: 显式 debug
- **WHEN** 维护者使用 `--debug` 运行命令
- **THEN** 输出附加脱敏诊断元数据
- **AND** JSON 的核心公共字段保持不变

### Requirement: 辅助维护命令的可见性
`skills status|update` MAY 作为面向人类的安装维护命令保留，但 SHALL 与 Agent 搜索命令分组展示；离线回归和 provider 级测试 SHALL 通过开发测试入口或隐藏命令执行。

#### Scenario: 查看 skill 安装状态
- **WHEN** 维护者运行 `smart-search skills status`
- **THEN** 系统检查支持目标中的 skill 同步状态
- **AND** 该命令不被描述为搜索能力

#### Scenario: 开发者执行回归测试
- **WHEN** 开发者需要运行 CLI 回归或 provider 单测
- **THEN** 项目文档引导其使用测试脚本或开发入口
- **AND** Agent 默认帮助无需暴露 `regression` 或 provider 测试命令

### Requirement: 旧接口迁移
系统 SHALL 为仍有同等新操作的旧 provider 专用命令提供一个发布周期的隐藏兼容入口或明确迁移错误，并 SHALL 在兼容期结束后移除这些入口；AnySearch 与 Deep Research 命令不进入兼容转发层。

#### Scenario: 调用旧 provider 命令
- **WHEN** 用户在兼容期运行旧的 `exa-search`、`zhipu-search`、`context7-docs` 或同类命令
- **THEN** 系统输出弃用提示和对应的 `search`、`docs search|tree|read`、`fetch` 或 `map` 迁移方式
- **AND** 旧命令不出现在默认帮助或 Agent skill 中

#### Scenario: Deep Research 命令已移除
- **WHEN** 用户运行 `deep` 或 `research`
- **THEN** CLI 将其视为不存在的命令
- **AND** 发布迁移文档说明研究规划与综合已交由上层 Agent

#### Scenario: Research 配置与产物已移除
- **WHEN** 维护者查看 setup、config、doctor、help 或 skill
- **THEN** 系统不再展示 research budget、evidence directory、research provider override 或相关功能

#### Scenario: Research 实现已移除
- **WHEN** 项目完成本 change 的实现
- **THEN** service 中不再保留 Deep Research 计划构建、live research 执行或 evidence artifact 写入路径
- **AND** 对应测试和发布资源已删除或改写

#### Scenario: 调用旧 model 命令
- **WHEN** 用户运行 `model set` 或 `model current`
- **THEN** 系统引导使用 `config` 管理相应模型配置
