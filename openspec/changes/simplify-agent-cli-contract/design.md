## Context

当前 `smart-search` CLI 同时暴露按任务命名的命令、按 provider 命名的命令、意图路由诊断、Deep Research 编排、配置管理和开发回归入口。底层多 provider 有利于覆盖率与容错，但公开命令面迫使 Agent 理解供应商差异，且与上层 Agent 自身的任务规划形成重复编排。

本变更涉及 CLI 参数、service 路由、配置结构、统一输出、测试、README 和两份同步发布的 Agent skill。现有 JSON/Markdown/content 输出属于用户可见契约，迁移必须显式处理兼容性；provider 凭据、个人配置和本地绝对路径不得进入仓库。

## Goals / Non-Goals

**Goals:**

- 将 Agent-facing 搜索接口稳定为 `search`、`docs search|tree|read`、`fetch`、`map`。
- 让配置文件决定 provider 可用性、顺序、超时与 fallback。
- 为不同 provider 建立统一能力适配和结果模型。
- 保留面向人类维护者的帮助、版本、配置、健康检查和专项诊断。
- 提供可测试、可回滚的旧 CLI 迁移路径，并同步 Agent skill 与 README。

**Non-Goals:**

- 除本期明确移除 AnySearch 外，不替换其他底层 provider，也不改变第三方 API 的认证方式。
- 不在 CLI 内重新实现一个 Deep Research Agent；任务分解、并行研究和最终写作由上层 Agent 负责。
- 不在本期引入 paper-search 或新的垂直搜索实现；该能力后续通过独立 change 扩展。
- 不要求首个实现周期新增 `map` provider；当前仍可只有 Tavily。
- 不把 provider 调试细节重新包装成新的 Agent 参数。

## Decisions

### 1. 公开接口按能力命名

默认帮助和 Agent skill 只把四类搜索能力作为工具入口。`docs` 是能力命名空间，通过 `search`、`tree`、`read` 三个 provider 无关的操作分别表达文档/仓库知识搜索、仓库目录读取和仓库文件读取；`fetch` 统一多种 Reader/Scrape 实现；`map` 保留站点级链接发现用途。

`map` 专指从网站入口发现站内页面 URL、路径和链接结构，不等同于单页结构化数据提取，也不等同于 GitHub 仓库目录树。单页内容或字段提取属于 `fetch`，仓库目录树属于 `docs tree`。

选择能力命令而不是 provider 命令，是因为能力名称表达 Agent 的真实意图，并允许后续替换 provider 而不修改 prompt 或 skill。备选方案是保留所有 provider 命令、只精简文档，但隐藏不彻底，Agent 仍可能从 help 或错误提示中学习并选择底层入口。

### 2. 使用配置化能力链

配置层增加四类公开能力对应的 provider 顺序和策略。对于包含多种操作的能力，配置和 provider profile 必须细化到 `capability.operation`；未配置、禁用或不支持目标操作的 provider 不进入候选链。

推荐的逻辑映射为：

| 公开能力/操作 | 内部 provider 候选 |
|---|---|
| `search` | 回答：xAI Responses、OpenAI-compatible；网页发现：Zhipu、Zhipu MCP、Tavily、Firecrawl |
| `docs search` | Context7、Exa、Zhipu MCP zread `search_doc` |
| `docs tree` | Zhipu MCP zread `get_repo_structure` |
| `docs read` | Zhipu MCP zread `read_file` |
| `fetch` | Jina、Tavily、Zhipu MCP Reader、Firecrawl |
| `map` | Tavily |

配置使用已有环境变量/本地配置机制扩展，避免引入新的运行时配置依赖。配置可表达优先顺序、禁用项、单能力超时和 fallback 开关，但 Agent skill 不展示这些键。

备选方案是继续通过 `--providers` 临时选择，优点是调试灵活，缺点是把运维策略交给 Agent，因此只允许诊断层读取或覆盖，不属于普通命令契约。

### 3. 简化搜索路径，避免二次 Agent 编排

命令和子命令已经声明能力与操作，因此 `docs`、`fetch`、`map` 不再运行 embedding 或 LLM classifier 来重新判断类型。`docs search` 可根据 `--source` 的中立来源标识判断是库/API 文档还是 `owner/repo` 仓库知识；`docs tree` 与 `docs read` 只选择实现同操作的 provider。`search` 可以在内部依据轻量规则决定是否补充实时网页来源，但不得把 router、validation 层级或 provider 选择暴露给 Agent。

原有 `deep` 和 `research` 的规划、证据循环、证据目录与综合实现从本期代码中移除；上层 Agent 使用四类原子能力自行编排。AnySearch provider、配置、命令和 `vertical_search` 路由同时移除，未来论文与垂直搜索由独立的 paper-search 扩展承担。`route`、`route-calibrate` 仅在内部测试或迁移期保留，不出现在默认命令面。

### 4. 统一公共结果与诊断元数据

四类命令共享核心 envelope：`ok`、`capability`、`operation`、`content`、`sources`、`elapsed_ms`，失败时增加 `error_type` 和 `error`。`docs tree` 可在 `entries` 中返回路径、类型和层级，`docs read` 在 `content` 中返回文件正文；`sources` 统一为 `title`、`url`、`snippet`，其他命令特有信息放在稳定的可选字段中。

`provider_attempts`、内部 provider 名称、模型 fallback、breaker、路由评分和异常细节移动到 debug metadata。普通 JSON 默认不输出；`--debug`、`doctor`、`diagnose` 和日志可读取脱敏版本。

备选方案是继续把所有字段放入 JSON 并让 Agent 忽略，但这会持续占用上下文，也会使内部实现被误认为稳定契约。

### 5. 诊断按能力组织

`doctor` 报告四种能力是否可用以及配置/连接概况；`diagnose search|docs|fetch|map` 深入测试该能力下的候选 provider。诊断结果可显示 provider，因为目标用户是维护者，但这些命令在帮助中与 Agent 搜索命令分组，Agent skill 不将其作为正常路由手段。

### 6. 分阶段迁移旧命令

首个兼容发布中，仍有明确替代操作的旧 provider 命令从 help 和 Agent skill 隐藏，调用时输出弃用信息并尽量转发到新能力；无法无损转发的高级参数返回明确迁移说明。AnySearch、`deep`、`research` 不进入兼容转发层，直接从 parser、service、配置、测试和文档中删除。`model` 等其他旧入口返回面向新职责边界的迁移指引。下一个破坏性发布删除剩余兼容解析器和旧测试契约。

这种方式比立即删除降低现有脚本断裂风险，同时保证新 Agent 不再看到旧接口。

## Risks / Trade-offs

- [统一命令可能失去 provider 特有高级参数] → 只保留跨 provider、任务级的通用参数；特有能力通过配置或维护者诊断入口处理。
- [`docs` 子操作当前 provider 覆盖不均衡] → fallback 严格限定为同操作；`tree`/`read` 只有一个 provider 时明确报告单点能力状态，不用 `search` 结果冒充。
- [自动 fallback 可能掩盖坏配置并增加延迟] → 记录脱敏尝试信息，按错误类型决定是否继续，并为能力设置总超时预算。
- [一个发布周期同时维护新旧入口增加实现复杂度] → 兼容层只做薄转发和弃用提示，不复制 provider 逻辑，并预先写明删除版本。
- [移除 Deep Research CLI 可能影响人类用户] → 在迁移说明中提供由 `search/docs/fetch/map` 组合完成研究的示例；如未来需要人类研究产品，应作为独立界面重新设计。
- [移除 AnySearch 会暂时降低垂直领域覆盖] → 明确本期不提供替代 fallback，避免保留弱能力；后续通过独立 paper-search change 恢复论文等垂直搜索。
- [`search` 同时涉及答案生成与来源发现] → 内部拆分 answer 与 discovery 子能力，但保持一个公开命令和统一总超时。
- [默认隐藏 provider 信息降低问题定位效率] → `--debug`、`doctor`、`diagnose` 和日志继续提供完整脱敏溯源。

## Migration Plan

1. 先补充新版 CLI、`docs` 子操作、AnySearch/Research 删除行为和统一输出的失败测试。
2. 删除 AnySearch provider、配置、命令、垂直路由及 Deep Research 规划/执行路径。
3. 增加细化到 `capability.operation` 的配置链，实现 `docs search|tree|read`，并将 `search`、`fetch`、`map` 接入统一 executor。
4. 增加能力/操作级 `doctor`、`diagnose` 和 debug metadata，验证同操作 fallback。
5. 更新默认 help、README 和两份 Agent skill，只公开四类搜索能力。
6. 将其他旧 provider 命令改为隐藏兼容入口并增加弃用测试；在后续破坏性版本删除剩余兼容入口。

回滚时可恢复旧 parser 的默认可见性和直接 service 调用；能力 executor 与 provider adapter 可继续复用，不需要回滚 provider 实现或用户凭据。

## Open Questions

- 兼容入口的具体删除版本需在实施时结合当前包版本和发布节奏写入 README；规格要求至少保留一个发布周期，不要求固定版本号。
- `docs search --source` 首版是否同时支持 library ID、`owner/repo` 和普通 URL，需要在实现调查中基于现有 Context7/zread 参数归一化规则确定，但不得暴露 provider 名称。
