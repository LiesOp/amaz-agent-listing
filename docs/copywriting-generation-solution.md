# 文案生成规则化改造解决方案

## 1. 核心结论

当前系统应从“模型临场理解规则”改为“代码确定性装配规则，模型按规则生成，代码再强制校验”。

目标架构：

```text
产品 Brief
+ 后台 rules
+ 竞品聚合分析结果
        ↓
代码构造 policy_pack
        ↓
固定系统提示词声明 policy_pack 最高优先级
        ↓
模型生成结构化 Listing
        ↓
copy_validator 按 hard rules 校验
        ↓
失败则 repair
        ↓
再次失败则拒绝保存并返回具体违规项
```

核心原则：

1. 具体业务规则不应硬编码在内置提示词中。
2. 规则和竞品分析结果不应依赖模型调用 tool 获取。
3. 代码应在生成前完成规则、产品事实、竞品策略的封装。
4. 模型只消费 `policy_pack`，不负责临时查询规则。
5. 违反 hard rule 的结果不能保存。

## 2. 当前主要问题

### 2.1 内置提示词污染生成结果

当前项目中存在一些固定业务提示词，例如长描述结构、FEATURES 写法、标题要求、五点要求等。

这些提示词如果和后台录入规则冲突，会导致模型不知道优先遵循哪一套规则，最终出现：

1. 五点描述只是把核心卖点翻译成英文。
2. 长描述第一句照抄标题。
3. FEATURES 照抄五点描述。
4. 标题格式不符合业务要求。
5. 用户录入的 rules 无法稳定生效。

处理原则：

1. 固定 system prompt 只保留平台级原则。
2. 标题、五点、长描述、FEATURES、Search Terms 等具体业务规则迁移到 `rules`。
3. 错误、过时、与 rules 冲突的内置业务 prompt 应删除。
4. 无法删除的基础格式要求，应改为由 `policy_pack.output_contract` 控制。

### 2.2 生成阶段依赖 tool 获取规则和竞品分析

当前生成 agent 可调用 `listing_rules_tool` 和 `competitor_analysis_tool`。

这类设计不适合作为强规则来源，原因是：

1. 模型可能不调用 tool。
2. 模型可能调用 tool 后错误理解返回结果。
3. tool 结果和 `policy_pack` 可能发生冲突。
4. 规则和竞品分析本来可以由代码确定性读取。
5. 强规则不能依赖模型的自主行为。

正确方式：

1. 代码在生成前读取 active rules。
2. 代码读取当前 brief 对应的竞品聚合分析。
3. 代码统一封装成 `policy_pack`。
4. 生成阶段不再提供规则和竞品 tool。
5. 固定 system prompt 强制声明只能依据 `policy_pack`。

## 3. 目标设计

目标是建设一套“动态规则执行机制”，而不是继续堆叠提示词。

整体链路：

```text
load ProductBrief
        ↓
load active rules
        ↓
load CompetitorAnalysis
        ↓
build_policy_pack
        ↓
generate structured copy
        ↓
validate_against_policy_pack
        ↓
repair failed fields
        ↓
validate again
        ↓
save draft or return validation errors
```

## 4. 规则系统设计

现有 `rules` 表可以继续使用，但建议升级为“文本规则 + 结构化规则”。

现有字段继续保留：

```text
rule_category
rule_title
rule_content
rule_scope
rule_level
priority
is_active
```

建议新增字段：

```text
rule_schema JSON
marketplace
category
```

字段职责：

1. `rule_content`：给模型阅读的自然语言规则。
2. `rule_schema`：给代码校验器执行的结构化规则。
3. `rule_level`：建议统一为 `hard`、`soft`、`guideline`。
4. `priority`：规则冲突时优先级越小越高。

建议规则分类：

```text
global
title
bullets
description_text
search_terms
competitor_usage
output_contract
```

## 5. 关键规则建议

### 5.1 标题规则

自然语言规则：

```text
标题必须遵循：
品牌（不超过 8 个字符） + 核心大词 + 1-2 个最关键属性 + 变体属性。
核心大词必须来自已验证关键词或用户确认关键词。
属性和变体属性只能来自产品 Brief 中的已验证事实。
不得使用未提供的材质、尺寸、认证、功效或竞品事实。
```

结构化规则示例：

```json
{
  "type": "title_structure",
  "field": "title",
  "brand_max_chars": 8,
  "required_parts": [
    "brand",
    "core_keyword",
    "key_attributes",
    "variant_attributes"
  ],
  "attribute_source": "product_facts",
  "severity": "hard"
}
```

### 5.2 五点描述规则

自然语言规则：

```text
五点描述不得只是翻译 core_features。
每条五点必须综合产品核心卖点和竞品分析结果，表达为：
已验证产品事实 + 市场需求/痛点/场景/差异化机会 + 买家利益。
竞品信息只能作为策略输入，不能把竞品事实写成自家产品事实。
五点之间不得重复表达同一卖点。
```

结构化规则示例：

```json
{
  "type": "bullet_synthesis",
  "field": "bullets",
  "count": 5,
  "required_sources": [
    "product_facts.core_features",
    "competitor_strategy"
  ],
  "forbid_direct_translation_only": true,
  "duplicate_similarity_max": 0.7,
  "severity": "hard"
}
```

### 5.3 长描述首句规则

自然语言规则：

```text
长描述第一句必须总结五点描述形成的一句话。
不得照抄标题。
不得与标题高度相似。
```

结构化规则示例：

```json
{
  "type": "description_opening",
  "field": "description_text",
  "must_summarize": "bullets",
  "forbid_same_as": "title",
  "similarity_max": 0.65,
  "severity": "hard"
}
```

### 5.4 FEATURES 规则

自然语言规则：

```text
FEATURES 部分不得照抄五点描述。
FEATURES 应补充五点以外的其他卖点，例如使用便利性、适用场景、包装数量、材质、维护方式、搭配方式等。
所有内容必须来自已验证产品事实，不能编造。
```

结构化规则示例：

```json
{
  "type": "features_distinct_from_bullets",
  "field": "description_text.features",
  "compare_to": "bullets",
  "similarity_max": 0.65,
  "source": "product_facts",
  "severity": "hard"
}
```

### 5.5 竞品使用规则

自然语言规则：

```text
竞品分析只能作为策略输入。
可以使用竞品分析中的市场需求、买家痛点、常见场景、差异化机会和风险提示。
不得复制竞品原文。
不得把竞品事实写成自家产品事实。
不得使用竞品品牌词。
```

结构化规则示例：

```json
{
  "type": "competitor_usage_policy",
  "field": "global",
  "allowed_uses": [
    "market_expectations",
    "pain_points",
    "use_scenarios",
    "differentiation_opportunities",
    "risk_notes"
  ],
  "forbidden_uses": [
    "competitor_product_facts",
    "competitor_brand_terms",
    "competitor_original_copy"
  ],
  "severity": "hard"
}
```

## 6. policy\_pack 设计

`policy_pack` 是本次生成的唯一规则载体，由代码构造，不由模型查询。

建议结构：

```json
{
  "product_facts": {},
  "field_rules": {
    "global": [
      {
        "content": "rule content",
        "level": "hard"
      }
    ],
    "title": [],
    "bullets": [],
    "description_text": [],
    "search_terms": [],
    "competitor_usage": [],
    "output_contract": []
  },
  "keyword_plan": {
    "must_use": [],
    "nice_to_have": [],
    "avoid": []
  },
  "competitor_strategy": {
    "positioning": "",
    "title_plan": [],
    "bullet_plan": [],
    "description_plan": [],
    "differentiators": [],
    "must_cover": [],
    "do_not_copy": true
  },
  "claims_policy": {
    "allowed_claims": [],
    "forbidden_claims": [],
    "requires_evidence": []
  },
  "output_contract": {
    "title": "one title",
    "bullets": "exactly five bullets",
    "description_text": "long description HTML",
    "search_terms": "backend search terms"
  }
}
```

注意：

1. `product_facts` 是产品事实唯一来源。
2. `competitor_strategy` 只放策略，不放大段竞品原文。
3. `field_rules` 是唯一规则入口，来自启用的 rules，并按字段分类。
4. `field_rules` 中每条规则包含 `content` 和 `level`，其中 `level=hard` 表示强制规则。
5. `custom_prompt` 只能影响语气和表达重点，不能覆盖规则。

## 7. 系统提示词改造

固定 system prompt 应该变短，只保留规则执行原则。

建议 system prompt：

```text
You generate Amazon US listing copy.

policy_pack is the mandatory source of truth for this generation.
policy_pack.field_rules contains the binding rules, not optional references.
Rules with level hard are non-negotiable.
Apply each field rule to its matching output field.

Use only verified product_facts for factual claims.
Competitor analysis is strategy input only. Do not treat competitor facts as facts about this product.
Do not copy competitor wording.

Do not invent product facts, dimensions, materials, certifications, warranties, or claims.

If user_custom_prompt conflicts with policy_pack, follow policy_pack.
Return structured output only.
```

应删除或迁移的内容：

1. 固定写死的标题格式。
2. 固定写死的长描述模板业务规则。
3. 固定写死的 FEATURES 规则。
4. 固定写死的五点表达规则。
5. 任何和后台 rules 可能冲突的业务约束。

## 8. 生成流程改造

建议生成流程：

```text
generate_draft
  ↓
load brief
  ↓
load active rules
  ↓
load competitor analysis
  ↓
build_policy_pack
  ↓
generate copy without rule/competitor tools
  ↓
validate_against_policy_pack
  ↓
repair if failed
  ↓
validate again
  ↓
save or reject
```

生成阶段应移除：

```text
listing_rules_tool
competitor_analysis_tool
```

这些 tool 可以保留给调试、审核、后台管理，但不应作为文案生成链路中的规则来源。

## 9. 校验器改造

`copy_validator` 需要从“结构校验”升级为“规则驱动校验”。

建议增加以下校验能力：

```text
title_structure
brand_length
bullet_count
bullet_duplicate_similarity
bullet_core_feature_translation_check
description_opening_not_title
description_opening_summarizes_bullets
features_not_duplicate_bullets
forbidden_terms
missing_fact_claims
competitor_fact_misuse
```

相似度校验初期可以使用简单策略：

1. 小写化。
2. 去标点。
3. 分词。
4. 计算 Jaccard similarity。
5. 超过阈值判定为重复或高度相似。

后续可以升级为 embedding similarity。

## 10. 竞品分析使用规则

竞品分析不应该直接变成文案内容，而应该变成策略。

允许使用：

```text
市场常见需求
买家痛点
竞品常见表达结构
差异化机会
高频关键词
风险词
必须覆盖的类目预期
```

禁止使用：

```text
竞品独有事实
竞品材质
竞品尺寸
竞品认证
竞品 warranty
竞品原文句子
竞品品牌词
```

`policy_pack.competitor_strategy` 应只保存策略化结果，不保存大段竞品原文。

## 11. repair 机制

失败后不要让模型自由重写全部内容，而是只修复失败字段。

validator 错误示例：

```json
{
  "validator_errors": [
    {
      "field": "description_text",
      "code": "features_duplicate_bullets",
      "rule_id": "rule_xxx",
      "message": "FEATURES are too similar to bullet points."
    }
  ]
}
```

repair prompt 原则：

```text
Only fix fields listed in validator_errors.
Do not change fields that passed validation.
Do not add new product facts.
Return full structured output.
```

repair 后再次校验。

如果仍失败，返回错误，不保存草稿。

## 12. 实施阶段

### 阶段一：清理内置提示词

1. 删除错误业务 prompt。
2. 固定 system prompt 只保留 `policy_pack` 执行原则。
3. 文案生成 agent 移除规则和竞品 tool。
4. 确认所有规则由 `build_policy_pack` 注入。

### 阶段二：规则结构化

1. 给 rules 增加 `rule_schema`。
2. 后台支持录入结构化规则。
3. `build_policy_pack` 暂不把 `rule_schema` 注入提示词上下文。
4. 规则按字段分类进入 `field_rules`，每条规则只包含 `content` 和 `level`。

### 阶段三：文案质量校验

1. 增加标题结构校验。
2. 增加五点重复和直译校验。
3. 增加长描述首句校验。
4. 增加 FEATURES 与五点重复校验。
5. 校验失败进入 repair。

### 阶段四：审计和可追踪

1. 扩展 `compliance_trace`。
2. 保存每个字段使用的 rule\_id。
3. 保存竞品策略来源。
4. 前端展示失败原因和规则命中情况。

## 13. 最终验收标准

改造完成后，生成文案必须满足：

1. 标题符合：品牌 + 核心大词 + 1-2 个关键属性 + 变体属性。
2. 品牌不超过 8 个字符。
3. 五点不是 `core_features` 的英文直译。
4. 五点体现产品事实 + 竞品分析策略。
5. 长描述第一句总结五点，不照抄标题。
6. FEATURES 不照抄五点。
7. 竞品事实不会被写成自家产品事实。
8. 违反 hard rule 时不会保存草稿。
9. 每次生成结果可追踪使用了哪些规则和竞品策略。

## 14. 最终建议

应采纳以下两个方向：

1. 错误内置提示词删除，具体业务规则迁移到 `rules`。
2. 生成阶段不再让模型通过 tool 获取规则和竞品分析，而是由代码提前封装进 `policy_pack`。

这样系统才能从“提示词驱动”升级为“规则驱动”，文案生成结果才可控、可校验、可追踪。
