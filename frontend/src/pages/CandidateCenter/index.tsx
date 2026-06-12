import { Alert, Card, Empty } from "antd";
import { useKBContext } from "../../layout/KBContext";

export default function CandidateCenterPage() {
  const { selectedKbId } = useKBContext();

  if (!selectedKbId) {
    return <Alert message="请先选择知识库" type="info" showIcon />;
  }

  return (
    <Card title="候选知识">
      <Empty description="暂无候选知识" />
    </Card>
  );
}
