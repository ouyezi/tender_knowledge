import { Button, Drawer, Space, Table, Tag } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useNavigate } from "react-router-dom";
import type { BatchOperationResult, BatchResultItem } from "../../services/candidates";

export interface BatchResultDrawerProps {
  open: boolean;
  result?: BatchOperationResult;
  onClose: () => void;
}

export default function BatchResultDrawer({ open, result, onClose }: BatchResultDrawerProps) {
  const navigate = useNavigate();

  const columns: ColumnsType<BatchResultItem> = [
    {
      title: "候选 ID",
      dataIndex: "candidate_id",
      key: "candidate_id",
      ellipsis: true,
      width: 200,
    },
    {
      title: "状态",
      dataIndex: "status",
      key: "status",
      width: 100,
      render: (value: string) => {
        const color =
          value === "published" || value === "rejected"
            ? "success"
            : value === "pending"
              ? "warning"
              : "default";
        return <Tag color={color}>{value}</Tag>;
      },
    },
    {
      title: "错误",
      key: "error",
      ellipsis: true,
      render: (_value, record) => record.error?.message ?? "-",
    },
    {
      title: "操作",
      key: "actions",
      width: 100,
      render: (_value, record) =>
        record.error ? (
          <Button
            type="link"
            size="small"
            onClick={() => navigate(`/candidates/confirm/${record.candidate_id}`)}
          >
            重试
          </Button>
        ) : null,
    },
  ];

  return (
    <Drawer
      title="批量操作结果"
      width={720}
      open={open}
      onClose={onClose}
      destroyOnClose
      extra={
        result ? (
          <Space>
            <span>成功 {result.succeeded}</span>
            <span>失败 {result.failed}</span>
          </Space>
        ) : null
      }
    >
      {result ? (
        <Table
          rowKey="candidate_id"
          size="small"
          pagination={false}
          columns={columns}
          dataSource={result.results}
        />
      ) : null}
    </Drawer>
  );
}
