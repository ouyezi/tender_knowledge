# Epic 1：来源导入与文件分类确认

来源：`docs/总需求.md` 的 5、14、15.1、16.1、17、18 Phase 1、19.1、19.2、20、22 相关内容。

## 目标

建立 V3.0 所有来源进入平台的统一入口：一个文件一次导入，生成 File Import 记录，完成文件用途、产品分类和章节类型的人工确认，再分流到后续处理链路。

## 开发定位

这是 V3.0-MVP 的第一个业务闭环。它只负责“收文件、识别建议、人工确认、分流”，不负责实际解析模板或实际标书正文。

## 范围

包含：

- 单文件上传。
- File Import 记录。
- 文件用途自动建议。
- 产品分类和章节类型自动建议。
- 文件用途人工确认。
- 文件分流规则。
- 文件去重与重导入规则。
- 导入任务日志。

不包含：

- 目录导入、文件夹扫描、批量导入。
- 模板文件解析。
- 实际标书目录抽取。
- 候选知识生成和确认。
- 招标文件完整解析。

## 核心对象

### File Import

表示一次单文件导入操作。

关键字段：

- `import_id`
- `kb_id`
- `file_name`
- `file_type`
- `file_size`
- `file_hash`
- `storage_path`
- `file_purpose`
- `product_category_ids`
- `chapter_taxonomy_id`
- `status`
- `created_by`
- `created_time`
- `updated_time`

`file_purpose` 支持：

- `actual_bid`
- `template_file`
- `qualification`
- `ppt_material`
- `cover_guide`
- `writing_guide`
- `wiki_source`
- `other`

## 主流程

```text
上传单个文件
  → 创建 File Import
  → 计算文件基础信息和 hash
  → 给出文件用途、产品分类、章节类型建议
  → 用户人工确认
  → 按 file_purpose 进入后续处理链路
```

## 文件用途确认

用户可确认：

- 文件用途。
- 产品分类。
- 章节类型。
- 是否进入解析。
- 目标对象类型：Document、Template Material、Manual Asset、Wiki、忽略。

确认规则：

- 文件导入后必须进入用途确认。
- 文件用途确认前，不进入后续解析任务。
- 被忽略文件不进入后续解析任务，但保留导入日志。
- 文件名可用于辅助推断分类，但必须允许人工覆盖。

## 分流规则

- `actual_bid`：进入 Document 解析、Bid Outline 抽取和 Candidate Knowledge 生成任务。
- `template_file`：进入 Template、Template Chapter、Template Material 解析任务，可同时生成 Candidate Knowledge。
- `qualification`：进入 Manual Asset 候选流程。
- `ppt_material`、`cover_guide`、`writing_guide`：进入 Template Material 或素材元数据管理流程。
- `wiki_source`：进入 Wiki 候选流程。
- `other`：保留为附件或忽略，不自动进入知识生产。

## 去重与重导入

去重规则：

- 优先使用 `file_hash` 判断重复文件。
- 若无法计算 hash，则使用 `file_name + file_size` 作为辅助判断。
- 重复文件默认不重复解析，但允许用户选择“作为新版本导入”。

重导入规则：

- 未处理或处理失败的 File Import 可重新处理。
- 已生成但未发布的 Candidate Knowledge 可删除或标记 rejected。
- 已发布对象不允许物理删除，只能走废弃流程。

## 任务中心

本 epic 需要的任务类型：

- `file_import`
- `file_purpose_classify`

任务要求：

- 所有任务支持日志查看。
- 任务结果可追溯到 File Import。
- 失败任务可重试。

## 管理后台

来源导入中心需要支持：

- 上传单个文件。
- 查看 File Import 列表。
- 查看处理状态。
- 查看导入任务日志。
- 文件用途人工确认。
- 忽略文件。
- 重新处理失败导入。

## API

至少需要：

- File Import API：上传单个文件、查询导入状态。
- File Purpose Confirm API：确认文件用途、分类和目标对象。

## 验收标准

1. 用户可以上传单个 docx、pdf、ppt、xlsx、image 文件。
2. 系统上传完成后快速返回 File Import ID。
3. 系统能根据文件名和内容摘要给出文件用途、产品分类和章节类型建议。
4. 用户可以确认文件用途并保存，保存 P95 小于 1 秒。
5. 文件用途确认后，系统按 `file_purpose` 创建对应后续任务。
6. 被忽略文件不会进入解析任务，但保留导入日志。
7. 重复文件能被识别，并允许用户选择跳过或作为新版本导入。

## 后续依赖

- Epic 2 消费 `template_file` 分流结果。
- Epic 3 消费 `actual_bid` 分流结果。
- Epic 4 消费后续链路生成的 Candidate Knowledge。
