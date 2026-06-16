import { Alert, Button, Drawer, Spin, Typography } from "antd";
import { useCallback, useEffect, useState } from "react";
import RichContentViewer from "../../components/RichContentViewer";
import {
  getOutlineNodeContent,
  type OutlineNodeContentResult,
} from "../../services/bidOutlines";

type Props = {
  open: boolean;
  kbId?: string;
  bidOutlineId?: string;
  outlineNodeId?: string | null;
  onClose: () => void;
};

function sectionTitleLevel(level: number): 4 | 5 {
  return level <= 1 ? 4 : 5;
}

export default function OutlineNodeContentDrawer({
  open,
  kbId,
  bidOutlineId,
  outlineNodeId,
  onClose,
}: Props) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<OutlineNodeContentResult | null>(null);

  const reload = useCallback(async () => {
    if (!kbId || !bidOutlineId || !outlineNodeId) {
      setData(null);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await getOutlineNodeContent(kbId, bidOutlineId, outlineNodeId);
      setData(result);
    } catch (err) {
      setError((err as Error).message);
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [kbId, bidOutlineId, outlineNodeId]);

  useEffect(() => {
    if (open) void reload();
  }, [open, reload]);

  const hasAnyContent = data?.sections.some((section) => section.has_content) ?? false;

  return (
    <Drawer
      title={data ? `${data.title} — 章节内容` : "章节内容"}
      width={720}
      open={open}
      onClose={onClose}
      extra={<Button onClick={() => void reload()}>刷新</Button>}
    >
      {error ? (
        <Alert
          type="error"
          showIcon
          message={error}
          action={
            <Button size="small" onClick={() => void reload()}>
              重试
            </Button>
          }
        />
      ) : null}
      <Spin spinning={loading}>
        {data && !hasAnyContent ? (
          <Alert type="info" showIcon message="该目录下暂无正文内容" style={{ marginBottom: 16 }} />
        ) : null}
        {data?.sections.map((section, index) => (
          <div
            key={section.outline_node_id}
            style={{
              marginBottom: index < data.sections.length - 1 ? 24 : 0,
              paddingLeft: (section.level - 1) * 16,
            }}
          >
            {section.level >= 3 ? (
              <Typography.Text strong style={{ display: "block", marginBottom: 8 }}>
                {section.title}
              </Typography.Text>
            ) : (
              <Typography.Title level={sectionTitleLevel(section.level)} style={{ marginTop: 0 }}>
                {section.title}
              </Typography.Title>
            )}
            {section.empty_reason === "no_source_node" ? (
              <Typography.Text type="secondary">暂无关联正文</Typography.Text>
            ) : (
              <RichContentViewer kbId={kbId ?? ""} content={section.content} />
            )}
          </div>
        ))}
      </Spin>
    </Drawer>
  );
}
