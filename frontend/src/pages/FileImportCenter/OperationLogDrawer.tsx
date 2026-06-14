import { Drawer, Table } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useEffect, useState } from "react";
import { listImportAuditLogs, type ImportAuditLogItem } from "../../services/fileImports";

interface OperationLogDrawerProps {
  open: boolean;
  kbId?: string;
  importId?: string;
  onClose: () => void;
}

const ACTION_LABELS: Record<string, string> = {
  upload: "上传",
  suggest_ready: "建议就绪",
  confirm: "确认用途",
  ignore: "忽略",
  retry: "重试",
  duplicate_skip: "重复跳过",
  duplicate_new_version: "新版本",
  route: "路由分流",
  delete: "删除",
  purge_all: "清空全部",
};

export default function OperationLogDrawer({ open, kbId, importId, onClose }: OperationLogDrawerProps) {
  const [items, setItems] = useState<ImportAuditLogItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);

  useEffect(() => {
    if (!open || !kbId) {
      return;
    }
    setLoading(true);
    void listImportAuditLogs(kbId, { import_id: importId, page, page_size: 20 })
      .then((result) => {
        setItems(result.items ?? []);
        setTotal(result.total ?? 0);
      })
      .finally(() => setLoading(false));
  }, [open, kbId, importId, page]);

  const columns: ColumnsType<ImportAuditLogItem> = [
    {
      title: "时间",
      dataIndex: "created_at",
      key: "created_at",
      width: 180,
      render: (value: string) => new Date(value).toLocaleString(),
    },
    {
      title: "操作",
      dataIndex: "action",
      key: "action",
      width: 100,
      render: (value: string) => ACTION_LABELS[value] ?? value,
    },
    {
      title: "操作人",
      dataIndex: "operator_id",
      key: "operator_id",
      width: 100,
    },
    {
      title: "详情",
      dataIndex: "payload_summary",
      key: "payload_summary",
      render: (value: Record<string, unknown> | null) =>
        value ? JSON.stringify(value) : "—",
    },
  ];

  return (
    <Drawer
      title={importId ? "单条操作日志" : "来源导入操作日志"}
      open={open}
      onClose={onClose}
      width={720}
    >
      <Table
        rowKey="audit_id"
        loading={loading}
        dataSource={items}
        columns={columns}
        pagination={{
          current: page,
          pageSize: 20,
          total,
          onChange: setPage,
        }}
        size="small"
      />
    </Drawer>
  );
}
