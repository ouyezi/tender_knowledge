export const FIELD_LABELS: Record<string, string> = {
  title: "标题",
  content: "内容",
  summary: "摘要",
  knowledge_type: "形态",
  content_type: "内容类型",
  file_name: "文件名",
  block_type_code: "块类型编码",
  application_type_code: "应用类型编码",
  business_line_codes: "业务线编码",
  block_type_label: "知识类别",
  application_type_label: "应用方式",
  business_line_labels: "业务线",
  status: "状态",
  dynamic_type_code: "动态知识类型编码",
  dynamic_type_label: "动态知识类型",
  structured_data: "结构化数据",
  sync_status: "同步状态",
  source_chunk_id: "来源知识 ID",
  source_doc_id: "来源文档 ID",
  is_expired: "是否过期",
  last_synced_at: "最近同步时间",
  template_type: "模板类型",
  security_level: "安全级别",
  review_status: "审核状态",
  owner: "负责人",
  qualification_info: "资质信息",
  expire_date: "失效日期",
  tags: "标签",
  regions: "地区",
  page_start: "起始页",
  page_end: "结束页",
  char_start: "起始字符",
  char_end: "结束字符",
  catalog_path: "目录路径",
  is_template: "是否模板",
  keyword: "关键词",
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
  extracted_facts: "图片结构化事实",
  llm_summary: "LLM 摘要",
  table_summary: "表格摘要",
  table_schema: "表格结构",
  table_headers: "表头",
  table_rows: "表格行",
};

export const ENUM_LABELS: Record<string, Record<string, string>> = {
  knowledge_type: {
    fact: "事实",
    certificate: "证书",
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
    dynamic: "动态",
    contract: "合同",
    manual: "手册",
    wiki: "百科",
    case: "案例",
  },
  block_type_code: {},
  application_type_code: {},
  dynamic_type_code: {},
  sync_status: {
    pending: "待同步",
    synced: "已同步",
    failed: "同步失败",
  },
  status: {
    draft: "草稿",
    active: "生效",
    deprecated: "已废弃",
    disabled: "已禁用",
  },
  security_level: { public: "公开", internal: "内部", confidential: "机密" },
  review_status: { pending: "待审核", approved: "已通过", rejected: "已驳回" },
  template_type: {
    commitment: "承诺函",
    authorization: "授权书",
    response: "响应说明",
    technical_solution: "技术方案",
    implementation_plan: "实施方案",
    service_plan: "服务方案",
    quotation: "报价",
  },
  embedding_status: { pending: "待索引", indexing: "索引中", ready: "已索引", failed: "索引失败", skipped: "已跳过" },
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
