import {
  Alert,
  Button,
  Card,
  Col,
  Descriptions,
  Empty,
  Popconfirm,
  Row,
  Space,
  Spin,
  Tag,
  Typography,
  message,
} from "antd";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import BlueprintEditor from "../../components/Blueprint/BlueprintEditor";
import BlueprintNodeDetailPanel from "../../components/Blueprint/BlueprintNodeDetailPanel";
import BlueprintOutlineTreeReadonly from "../../components/Blueprint/BlueprintOutlineTreeReadonly";
import { useKBContext } from "../../layout/KBContext";
import {
  deleteBlueprint,
  getBlueprint,
  updateBlueprint,
  type BlueprintDraft,
  type BlueprintNode,
} from "../../services/blueprints";

const { Paragraph, Text } = Typography;

function getNodeByPath(nodes: BlueprintNode[], path?: string): BlueprintNode | undefined {
  if (!path) return undefined;
  const parts = path.split("-").map((part) => Number(part));
  let current = nodes;
  let node: BlueprintNode | undefined;
  for (const index of parts) {
    node = current[index];
    if (!node) {
      return undefined;
    }
    current = node.children ?? [];
  }
  return node;
}

function formatDateTime(value?: string | null) {
  return value ? new Date(value).toLocaleString() : "-";
}

function renderTagList(items?: string[]) {
  if (!items?.length) {
    return "-";
  }
  return (
    <Space size={[4, 4]} wrap>
      {items.map((item) => (
        <Tag key={item}>{item}</Tag>
      ))}
    </Space>
  );
}

export default function BlueprintDetailPage() {
  const { selectedKbId, readOnly } = useKBContext();
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [editing, setEditing] = useState(false);
  const [selectedPath, setSelectedPath] = useState<string>();
  const [draft, setDraft] = useState<BlueprintDraft>();

  const loadDetail = useCallback(async () => {
    if (!selectedKbId || !id) {
      setDraft(undefined);
      return;
    }
    setLoading(true);
    try {
      const result = await getBlueprint(selectedKbId, id);
      setDraft(result);
      setSelectedPath(undefined);
    } catch (error) {
      message.error((error as Error).message);
      setDraft(undefined);
    } finally {
      setLoading(false);
    }
  }, [id, selectedKbId]);

  useEffect(() => {
    void loadDetail();
  }, [loadDetail]);

  const handleSave = useCallback(async () => {
    if (!selectedKbId || !id || !draft) {
      return;
    }
    const name = draft.name?.trim();
    if (!name) {
      message.warning("请输入蓝图名称");
      return;
    }
    setSaving(true);
    try {
      await updateBlueprint(selectedKbId, id, { ...draft, name });
      message.success("目录蓝图已更新");
      setEditing(false);
      await loadDetail();
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setSaving(false);
    }
  }, [draft, id, loadDetail, selectedKbId]);

  const handleDelete = useCallback(async () => {
    if (!selectedKbId || !id) {
      return;
    }
    setDeleting(true);
    try {
      await deleteBlueprint(selectedKbId, id);
      message.success("目录蓝图已删除");
      navigate("/knowledge/blueprints");
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setDeleting(false);
    }
  }, [id, navigate, selectedKbId]);

  const selectedNode = useMemo(
    () => getNodeByPath(draft?.nodes ?? [], selectedPath),
    [draft?.nodes, selectedPath],
  );

  if (!selectedKbId) {
    return <Alert message="请先选择知识库" type="info" showIcon />;
  }

  if (!id) {
    return <Alert message="缺少蓝图 ID" type="error" showIcon />;
  }

  if (loading) {
    return (
      <Card>
        <Spin />
      </Card>
    );
  }

  if (!draft) {
    return (
      <Card>
        <Empty description="未找到目录蓝图" />
      </Card>
    );
  }

  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      <Card
        title={`目录蓝图：${draft.name || "-"}`}
        extra={
          <Space>
            <Button onClick={() => navigate("/knowledge/blueprints")}>返回列表</Button>
            {editing ? (
              <Button onClick={() => setEditing(false)} disabled={saving}>
                退出编辑
              </Button>
            ) : (
              <Button type="primary" onClick={() => setEditing(true)} disabled={readOnly}>
                编辑
              </Button>
            )}
            <Popconfirm
              title="确认删除该目录蓝图吗？"
              okText="删除"
              cancelText="取消"
              onConfirm={handleDelete}
              disabled={readOnly}
            >
              <Button danger loading={deleting} disabled={readOnly}>
                删除
              </Button>
            </Popconfirm>
          </Space>
        }
      >
        <Descriptions column={2} size="small" bordered>
          <Descriptions.Item label="蓝图 ID">{id}</Descriptions.Item>
          <Descriptions.Item label="版本">{draft.version ?? "-"}</Descriptions.Item>
          <Descriptions.Item label="来源文档">{draft.source_doc_id || "-"}</Descriptions.Item>
          <Descriptions.Item label="来源节点">{draft.source_node_id || "-"}</Descriptions.Item>
          <Descriptions.Item label="来源章节" span={2}>
            {draft.source_chapter_title || "-"}
          </Descriptions.Item>
          <Descriptions.Item label="状态">{draft.status || "-"}</Descriptions.Item>
          <Descriptions.Item label="最近更新时间">
            {formatDateTime((draft as { updated_at?: string | null }).updated_at)}
          </Descriptions.Item>
          <Descriptions.Item label="蓝图描述" span={2}>
            <Paragraph style={{ marginBottom: 0 }}>{draft.description || "-"}</Paragraph>
          </Descriptions.Item>
          <Descriptions.Item label="产品标签" span={2}>
            {renderTagList(draft.product_tags)}
          </Descriptions.Item>
          <Descriptions.Item label="行业标签" span={2}>
            {renderTagList(draft.industry_tags)}
          </Descriptions.Item>
          <Descriptions.Item label="场景标签" span={2}>
            {renderTagList(draft.scenario_tags)}
          </Descriptions.Item>
          <Descriptions.Item label="适用项目类型" span={2}>
            {renderTagList(draft.applicable_project_type)}
          </Descriptions.Item>
          <Descriptions.Item label="建议目录结构" span={2}>
            {draft.suggested_structure_md?.trim() ? (
              <Paragraph style={{ whiteSpace: "pre-wrap", marginBottom: 0 }}>
                {draft.suggested_structure_md}
              </Paragraph>
            ) : (
              "—"
            )}
          </Descriptions.Item>
        </Descriptions>
      </Card>

      {editing ? (
        <BlueprintEditor
          mode="edit"
          value={draft}
          loading={saving}
          readOnly={readOnly}
          onChange={setDraft}
          onSave={() => void handleSave()}
          sourceInfo={{ chapterTitle: draft.source_chapter_title ?? "", documentName: draft.source_doc_id }}
        />
      ) : (
        <Row gutter={12}>
          <Col xs={24} lg={11}>
            <Card title="目录大纲" bodyStyle={{ minHeight: 420, maxHeight: "calc(100vh - 360px)", overflow: "auto" }}>
              <BlueprintOutlineTreeReadonly
                nodes={draft.nodes ?? []}
                selectedPath={selectedPath}
                onSelectNode={setSelectedPath}
              />
            </Card>
          </Col>
          <Col xs={24} lg={13}>
            <Card title="节点详情" bodyStyle={{ minHeight: 420, maxHeight: "calc(100vh - 360px)", overflow: "auto" }}>
              {selectedNode ? (
                <BlueprintNodeDetailPanel node={selectedNode} readOnly onChange={() => undefined} />
              ) : (
                <Text type="secondary">请选择目录节点查看详情</Text>
              )}
            </Card>
          </Col>
        </Row>
      )}
    </Space>
  );
}
