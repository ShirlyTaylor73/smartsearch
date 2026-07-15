## ADDED Requirements

### Requirement: 帮助与版本入口
系统 SHALL 支持根命令和各层子命令的 `-h/--help`，并 SHALL 支持 `-v/--version` 输出机器可读的产品名称与版本。

#### Scenario: 查看根帮助
- **WHEN** 用户运行 `smart-search -h`
- **THEN** 系统分组展示四大 Agent 查询能力、维护命令和开发命令
- **AND** 不展示隐藏的 provider 兼容命令

#### Scenario: 查看能力帮助
- **WHEN** 用户运行 `smart-search search --help`、`docs --help`、`fetch --help` 或 `map --help`
- **THEN** 系统展示对应 operation、用途和 provider 无关参数

#### Scenario: 查看版本
- **WHEN** 用户运行 `smart-search -v`
- **THEN** 标准输出只包含 `smart-search <version>`
- **AND** 进程成功退出

### Requirement: 初始化与配置管理
系统 SHALL 保留 `setup` 与 `config path|list|set|unset`，供维护者配置凭据、operation 链、feature、超时和 fallback；配置展示 SHALL 默认脱敏。

#### Scenario: 初始化配置
- **WHEN** 维护者运行 `smart-search setup`
- **THEN** 系统引导配置四大能力的 operation
- **AND** 不要求每个 operation 都有多个 provider

#### Scenario: 查看配置
- **WHEN** 维护者运行 `smart-search config list`
- **THEN** 系统展示有效 operation 链和状态
- **AND** API key、token 等敏感值被隐藏

### Requirement: Doctor 健康检查
系统 SHALL 保留 `doctor`，并按每个公开 operation 报告配置、连接、feature 和 fallback 状态。

#### Scenario: 运行整体健康检查
- **WHEN** 维护者运行 `smart-search doctor`
- **THEN** 系统分别报告全部 search/docs/fetch/map operation
- **AND** 标识缺失、失败、降级和单点 operation

### Requirement: 完整 Diagnose 命令树
系统 SHALL 提供 `diagnose search|docs|fetch|map|provider|route|route-calibrate|smoke` 命令树，集中承载能力、provider 和路由排查。

#### Scenario: 排查 capability operation
- **WHEN** 维护者运行 `diagnose search [answer|sources|similar]`、`diagnose docs [resolve|search|tree|read]`、`diagnose fetch [content|extract]` 或 `diagnose map [site]`
- **THEN** 系统测试指定 operation 的配置、feature 和 provider 链
- **AND** 未指定 operation 时依次测试该 capability 的全部 operation

#### Scenario: 排查 OpenAI-compatible
- **WHEN** 维护者运行 `smart-search diagnose provider openai-compatible`
- **THEN** 系统执行现有 OpenAI-compatible 普通、stream=false 和 stream=true 搜索形态检查

#### Scenario: 查看路由决策
- **WHEN** 维护者运行 `smart-search diagnose route QUERY`
- **THEN** 系统解释路由结果但不执行搜索 provider

#### Scenario: 校准路由
- **WHEN** 维护者运行 `smart-search diagnose route-calibrate`
- **THEN** 系统执行现有 embedding 路由校准并输出 threshold/margin 建议

#### Scenario: 运行 smoke
- **WHEN** 维护者运行 `smart-search diagnose smoke --mode mock|live`
- **THEN** 系统执行现有 mock 或 live provider/fallback smoke 检查

### Requirement: 开发命令命名空间
系统 SHALL 提供 `smart-search dev regression` 执行离线 CLI 回归，并 SHALL NOT 将其描述为 Agent 查询能力。

#### Scenario: 运行开发回归
- **WHEN** 开发者运行 `smart-search dev regression`
- **THEN** 系统执行现有离线 regression 行为
- **AND** 命令位于开发功能分组

### Requirement: Skills 管理
系统 SHALL 保留 `skills status|update`，用于检查和同步各 AI 工具目标中的 skill 副本。

#### Scenario: 查看 skill 状态
- **WHEN** 维护者运行 `smart-search skills status`
- **THEN** 系统检查所选目标的 skill 同步状态
- **AND** 不将该命令列为查询能力

### Requirement: Debug 与日志隔离
系统 SHALL 默认保持 Agent 输出简洁，并仅在显式 `--debug` 或维护者配置开启时输出 provider、feature、fallback 和内部诊断信息。

#### Scenario: 默认调用
- **WHEN** Agent 未启用 debug 运行查询 operation
- **THEN** 输出不包含 provider 链、模型 breaker、路由评分或内部堆栈

#### Scenario: 显式 debug
- **WHEN** 维护者使用 `--debug`
- **THEN** 输出附加脱敏诊断 metadata
- **AND** 公共 JSON 字段保持不变

### Requirement: 旧接口无损迁移
系统 SHALL 为有同等新 operation 的旧 provider 命令提供一个发布周期的隐藏兼容入口，并 SHALL 在兼容期后移除；AnySearch 和 Deep Research 不进入兼容层。

#### Scenario: 迁移搜索命令
- **WHEN** 用户运行旧 `search`、`exa-search`、`exa-similar`、`zhipu-search` 或 `zhipu-mcp-search`
- **THEN** 系统提示迁移到 `search answer|sources|similar` 并执行可无损转发的 operation

#### Scenario: 迁移文档命令
- **WHEN** 用户运行旧 Context7 或 Zhipu MCP zread 命令
- **THEN** 系统提示并映射到 `docs resolve|search|tree|read`

#### Scenario: 迁移 fetch 与 map
- **WHEN** 用户运行旧 `fetch` 或 `map`
- **THEN** 系统提示并映射到 `fetch content` 或 `map site`

#### Scenario: 迁移诊断和开发命令
- **WHEN** 用户运行旧 `diagnose openai-compatible`、`route`、`route-calibrate`、`smoke` 或 `regression`
- **THEN** 系统提示对应的 `diagnose ...` 或 `dev regression` 新位置

### Requirement: 移除 Deep Research
系统 SHALL 删除 `deep`、`research`、计划构建、live research、evidence artifact、research 配置和相关测试/资源。

#### Scenario: 调用旧研究命令
- **WHEN** 用户运行 `deep` 或 `research`
- **THEN** CLI 将其视为不存在的命令
- **AND** 迁移文档说明研究编排由上层 Agent 负责

#### Scenario: 查看配置与帮助
- **WHEN** 维护者查看 setup、config、doctor、help 或 skill
- **THEN** 系统不展示任何 Deep Research 功能或配置

### Requirement: Model 配置归一
系统 SHALL 使用 `config` 管理 XAI 与 OpenAI-compatible 模型，不再提供有效的独立 `model set` 行为。

#### Scenario: 调用旧 model 命令
- **WHEN** 用户运行旧 `model set` 或 `model current`
- **THEN** 系统引导使用对应 `config` 键
