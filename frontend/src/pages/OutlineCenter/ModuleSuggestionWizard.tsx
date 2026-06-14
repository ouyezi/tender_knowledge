import {
  Alert,
  Button,
  Drawer,
  Input,
  List,
  Space,
  Steps,
  Tag,
  Typography,
  message,
} from "antd";
import { useMemo, useState } from "react";
import {
  createModuleSuggestion,
  type ModuleSuggestionItem,
} from "../../services/moduleSuggestions";
import type { OutlineNodePayload } from "../../services/retrieval";

const { TextArea } = Input;

interface Props {
  open: boolean;
  kbId: string;
  outlineNodes: OutlineNodePayload[];
  productCategoryIds: string[];
  onClose: () => void;
}

export default function ModuleSuggestionWizard({
  open,
  kbId,
  outlineNodes,
  productCategoryIds,
  onClose,
}: Props) {
  const [step, setStep] = useState(0);
  const [running, setRunning] = useState(false);
  const [scorePointsText, setScorePointsText] = useState("");
  const [rejectionText, setRejectionText] = useState("");
  const [result, setResult] = useState<ModuleSuggestionItem[]>([]);

  const canRun = useMemo(() => Boolean(kbId) && outlineNodes.length > 0, [kbId, outlineNodes.length]);
  const scorePoints = useMemo(
    () => scorePointsText.split("\n").map((item) => item.trim()).filter(Boolean),
    [scorePointsText],
  );
  const rejectionClauses = useMemo(
    () => rejectionText.split("\n").map((item) => item.trim()).filter(Boolean),
    [rejectionText],
  );

  const runSuggestion = async () => {
    if (!canRun) return;
    setRunning(true);
    try {
      const data = await createModuleSuggestion(kbId, {
        product_category_ids: productCategoryIds,
        outline_nodes: outlineNodes,
        tender_requirement_context: {
          score_points: scorePoints,
          rejection_clauses: rejectionClauses,
        },
        retrieval_options: { top_k: 10 },
        return_options: {
          include_trace: true,
          include_score_detail: true,
          include_conflict_flags: true,
        },
      });
      setResult(data.module_suggestions);
      setStep(2);
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setRunning(false);
    }
  };

  const reset = () => {
    setStep(0);
    setResult([]);
    setScorePointsText("");
    setRejectionText("");
    onClose();
  };

  return (
    <Drawer title="模块建议向导" open={open} width={640} onClose={reset}>
      <Steps
        current={step}
        style={{ marginBottom: 16 }}
        items={[
          { title: "步骤1", description: "输入约束" },
          { title: "步骤2", description: "确认目录" },
          { title: "步骤3", description: "查看建议" },
        ]}
      />
      {!canRun ? <Alert type="info" showIcon message="当前目录为空，无法生成模块建议" /> : null}
      {step === 0 ? (
        <Space direction="vertical" style={{ width: "100%" }} size={12}>
          <TextArea
            rows={4}
            placeholder="评分点（每行一个）"
            value={scorePointsText}
            onChange={(event) => setScorePointsText(event.target.value)}
          />
          <TextArea
            rows={4}
            placeholder="废标/冲突约束（每行一个）"
            value={rejectionText}
            onChange={(event) => setRejectionText(event.target.value)}
          />
          <Space>
            <Button type="primary" disabled={!canRun} onClick={() => setStep(1)}>
              下一步
            </Button>
          </Space>
        </Space>
      ) : null}
      {step === 1 ? (
        <Space direction="vertical" style={{ width: "100%" }} size={12}>
          <Typography.Text type="secondary">将基于当前目录节点生成建议：</Typography.Text>
          <List
            size="small"
            bordered
            dataSource={outlineNodes}
            renderItem={(item) => (
              <List.Item>
                <Typography.Text>
                  L{item.level} · {item.title}
                </Typography.Text>
              </List.Item>
            )}
          />
          <Space>
            <Button onClick={() => setStep(0)}>上一步</Button>
            <Button type="primary" loading={running} disabled={!canRun} onClick={() => void runSuggestion()}>
              生成建议
            </Button>
          </Space>
        </Space>
      ) : null}
      {step === 2 ? (
        <Space direction="vertical" style={{ width: "100%" }} size={12}>
          <List
            size="small"
            bordered
            dataSource={result}
            locale={{ emptyText: "未返回建议" }}
            renderItem={(item) => (
              <List.Item>
                <Space direction="vertical" size={4} style={{ width: "100%" }}>
                  <Typography.Text strong>
                    {(item.target_outline_node?.title as string) ?? "未命名节点"}
                  </Typography.Text>
                  <Space wrap>
                    <Tag color="blue">匹配分: {item.match_score}</Tag>
                    <Tag color="green">覆盖率: {item.coverage_rate}</Tag>
                    <Tag>模板章节: {item.suggested_template_chapter_ids.length}</Tag>
                    <Tag>KU: {item.suggested_ku_ids.length}</Tag>
                    <Tag color={item.risk_flags.length ? "red" : "default"}>
                      风险: {item.risk_flags.length}
                    </Tag>
                  </Space>
                </Space>
              </List.Item>
            )}
          />
          <Space>
            <Button onClick={() => setStep(1)}>返回修改条件</Button>
            <Button type="primary" onClick={reset}>
              完成
            </Button>
          </Space>
        </Space>
      ) : null}
    </Drawer>
  );
}
