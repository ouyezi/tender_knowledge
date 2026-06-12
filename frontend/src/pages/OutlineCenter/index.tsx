import { Alert, Button, Card, Empty, Space } from "antd";
import { useKBContext } from "../../layout/KBContext";

export default function OutlineCenterPage() {
  const { selectedKbId, readOnly } = useKBContext();

  if (!selectedKbId) {
    return <Alert message="请先选择知识库" type="info" showIcon />;
  }

  return (
    <>
      <Card
        title="待处理"
        style={{ marginBottom: 16 }}
        extra={
          <Space>
            <Button type="primary" disabled={readOnly}>
              新建目录
            </Button>
          </Space>
        }
      >
        <Empty description="暂无待确认或失败的解析任务" />
      </Card>
      <Card title="目录">
        <Empty description="暂无目录" />
      </Card>
    </>
  );
}
