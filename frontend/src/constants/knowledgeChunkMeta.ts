export const FIELD_LABELS: Record<string, string> = {
  title: "标题",
  content: "内容",
  summary: "摘要",
  knowledge_type: "知识类型",
  content_type: "内容类型",
  source_type: "来源类型",
  file_name: "文件名",
  project_name: "项目名称",
  category: "分类",
  status: "状态",
  quote_mode: "引用模式",
  template_type: "模板类型",
  security_level: "安全级别",
  review_status: "审核状态",
  owner: "负责人",
  issue_date: "生效日期",
  expire_date: "失效日期",
  tags: "标签",
  products: "产品",
  industries: "行业",
  customer_types: "客户类型",
  regions: "地区",
  page_start: "起始页",
  page_end: "结束页",
  char_start: "起始字符",
  char_end: "结束字符",
  parent_id: "父级 ID",
  retrieval_weight: "检索权重",
  edit_distance_avg: "平均编辑距离",
  catalog_path: "目录路径",
  variables: "变量",
  exclusion_rules: "排除规则",
  need_parent_context: "需要父级上下文",
  is_template: "是否模板",
  is_immutable: "是否不可变",
  winning_flag: "中标标记",
  keyword: "关键词",
  issue_date_from: "生效日期起",
  issue_date_to: "生效日期止",
  expire_date_from: "失效日期起",
  expire_date_to: "失效日期止",
  id: "ID",
  kb_id: "知识库 ID",
  knowledge_code: "知识编码",
  version: "版本",
  previous_version_id: "上一版本 ID",
  is_latest: "是否最新",
  doc_id: "文档 ID",
  primary_node_id: "主节点 ID",
  token_count: "Token 数",
  content_hash: "内容哈希",
  has_children: "是否有子节点",
  children_count: "子节点数",
  create_time: "创建时间",
  update_time: "更新时间",
  embedding_status: "向量状态",
  previous_version: "上一版本",
  asset_code: "资产编码",
  chunk_id: "知识块 ID",
  table_type: "表格类型",
  image_type: "图片类型",
  allow_row_filter: "允许行过滤",
  required_with_text: "与正文绑定",
  position_hint: "位置提示",
  image_caption: "图片说明",
  image_ocr_text: "图片 OCR",
  llm_summary: "LLM 摘要",
  table_summary: "表格摘要",
  table_schema: "表格结构",
  table_headers: "表头",
  table_rows: "表格行",
};

export const ENUM_LABELS: Record<string, Record<string, string>> = {
  knowledge_type: {
    fact: "事实",
    template: "模板",
    solution: "方案",
    case: "案例",
    table: "表格",
    image: "图片",
  },
  content_type: { text: "文本", mixed: "混合" },
  source_type: {
    bid: "标书",
    proposal: "投标方案",
    qualification: "资质",
    contract: "合同",
    manual: "手册",
    wiki: "百科",
    case: "案例",
  },
  category: {
    qualification: "资质",
    technical: "技术",
    business: "商务",
    legal: "法务",
    personnel: "人员",
    price: "报价",
    case: "案例",
    template: "模板",
  },
  status: {
    draft: "草稿",
    active: "生效",
    deprecated: "已废弃",
    disabled: "已禁用",
  },
  security_level: { public: "公开", internal: "内部", confidential: "机密" },
  review_status: { pending: "待审核", approved: "已通过", rejected: "已驳回" },
  quote_mode: { full: "全文引用", partial: "部分引用" },
  template_type: {
    commitment: "承诺函",
    authorization: "授权书",
    response: "响应说明",
    technical_solution: "技术方案",
    implementation_plan: "实施方案",
    service_plan: "服务方案",
    quotation: "报价",
  },
  embedding_status: { pending: "待处理", ready: "已完成", failed: "失败" },
};

export const ASSET_TYPE_LABELS: Record<string, string> = {
  image: "图片",
  table: "表格",
};

export const BOOLEAN_OPTIONS = [
  { value: "true", label: "是" },
  { value: "false", label: "否" },
] as const;

export function getFieldLabel(field: string): string {
  return FIELD_LABELS[field] ?? field;
}

export function getEnumLabel(field: string, value: string | null | undefined): string {
  if (!value) return "-";
  return ENUM_LABELS[field]?.[value] ?? value;
}

export function getEnumOptions(field: string): { value: string; label: string }[] {
  const labels = ENUM_LABELS[field];
  if (!labels) return [];
  return Object.entries(labels).map(([value, label]) => ({ value, label }));
}

export function formatBoolean(value: boolean | null | undefined): string {
  if (value === true) return "是";
  if (value === false) return "否";
  return "-";
}

export function getAssetTypeLabel(assetType: string): string {
  return ASSET_TYPE_LABELS[assetType] ?? assetType;
}
