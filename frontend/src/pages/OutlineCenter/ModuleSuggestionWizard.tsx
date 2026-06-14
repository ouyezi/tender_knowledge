import {
  Alert,
  Button,
  Drawer,
  Input,
  List,
  Radio,
  Space,
  Steps,
  Tag,
  Typography,
  message,
} from "antd";
import { useMemo, useState } from "react";
import {
  createModuleSuggestion,
  patchSuggestionAdoption,
  type ModuleSuggestionItem,
} from "../../services/moduleSuggestions";
import { createDraft } from "../../services/generation";
import type { OutlineNodePayload } from "../../services/retrieval";
import { createTenderRequirement, type TenderRequirementCreatePayload } from "../../services/tenderRequirements";
import { ChapterDraftPanel } from "./ChapterDraftPanel";
import { TenderRequirementForm } from "./TenderRequirementForm";
import { VariableFillPanel, type TemplateVariableItem } from "./VariableFillPanel";

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
  const [savingRequirement, setSavingRequirement] = useState(false);
  const [suggestions, setSuggestions] = useState<ModuleSuggestionItem[]>([]);
  const [adoptionReason, setAdoptionReason] = useState("");
  const [selectedSuggestionId, setSelectedSuggestionId] = useState<string>();
  const [variableValues, setVariableValues] = useState<Record<string, string>>({});
  const [taskId, setTaskId] = useState<string | null>(null);
  const [requirementContextId, setRequirementContextId] = useState<string>();
  const [requirementDraft, setRequirementDraft] = useState<TenderRequirementCreatePayload | null>(null);

  const canRun = useMemo(() => Boolean(kbId) && outlineNodes.length > 0, [kbId, outlineNodes.length]);
  const selectedSuggestion = useMemo(
    () => suggestions.find((item) => item.suggestion_id === selectedSuggestionId),
    [selectedSuggestionId, suggestions],
  );

  const extractedVariables = useMemo<TemplateVariableItem[]>(() => {
    const organizationHint = selectedSuggestion?.organization_hint;
    if (!organizationHint || typeof organizationHint !== "object") {
      return [];
    }
    const hint = organizationHint as Record<string, unknown>;
    const raw = hint.template_variables;
    if (Array.isArray(raw) && raw.length > 0) {
      return raw.reduce<TemplateVariableItem[]>((acc, item) => {
        if (!item || typeof item !== "object") return acc;
        const row = item as Record<string, unknown>;
        const key = String(row.key ?? row.variable_key ?? "").trim();
        if (!key) return acc;
        acc.push({
          key,
          label: String(row.label ?? key),
          required: Boolean(row.required),
          default_value: row.default_value ? String(row.default_value) : undefined,
          description: row.description ? String(row.description) : undefined,
        });
        return acc;
      }, []);
    }
    return [];
  }, [selectedSuggestion?.organization_hint]);

  const runSuggestion = async () => {
    if (!canRun || !requirementContextId) return;
    setRunning(true);
    try {
      const data = await createModuleSuggestion(kbId, {
        requirement_context_id: requirementContextId,
        product_category_ids: productCategoryIds,
        requirement_text: requirementDraft?.title ?? "",
        outline_nodes: outlineNodes,
        tender_requirement_context: {
          outline_title: requirementDraft?.title ?? "",
          score_points: (requirementDraft?.score_points ?? []).map((item) => item.text),
          rejection_clauses: requirementDraft?.rejection_clauses ?? [],
        },
        retrieval_options: { top_k: 10 },
        return_options: {
          include_trace: true,
          include_score_detail: true,
          include_conflict_flags: true,
        },
      });
      setSuggestions(data.module_suggestions);
      setSelectedSuggestionId(data.module_suggestions[0]?.suggestion_id);
      setStep(2);
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setRunning(false);
    }
  };

  const reset = () => {
    setStep(0);
    setSuggestions([]);
    setAdoptionReason("");
    setSelectedSuggestionId(undefined);
    setVariableValues({});
    setTaskId(null);
    setRequirementContextId(undefined);
    setRequirementDraft(null);
    onClose();
  };

  const targetOutlineNode = useMemo<OutlineNodePayload | null>(() => {
    if (!selectedSuggestion?.target_outline_node || typeof selectedSuggestion.target_outline_node !== "object") {
      return null;
    }
    const node = selectedSuggestion.target_outline_node as Record<string, unknown>;
    const title = String(node.title ?? "").trim();
    if (!title) return null;
    return {
      title,
      level: Number(node.level ?? 1),
      sort_order: Number(node.sort_order ?? 0),
    };
  }, [selectedSuggestion?.target_outline_node]);

  return (
    <Drawer title="模块建议向导" open={open} width={640} onClose={reset}>
      <Steps
        current={step}
        style={{ marginBottom: 16 }}
        items={[
          { title: "约束" },
          { title: "建议" },
          { title: "采纳" },
          { title: "变量" },
          { title: "生成" },
          { title: "草稿" },
        ]}
      />
      {!canRun ? <Alert type="info" showIcon message="当前目录为空，无法生成模块建议" /> : null}
      {step === 0 ? (
        <TenderRequirementForm
          loading={savingRequirement}
          defaultOutlineNodes={outlineNodes}
          onSubmit={async (payload) => {
            if (!canRun) return;
            setSavingRequirement(true);
            try {
              const created = await createTenderRequirement(kbId, payload);
              setRequirementContextId(created.requirement_context_id);
              setRequirementDraft(payload);
              message.success("约束已保存");
              setStep(1);
            } catch (error) {
              message.error((error as Error).message);
            } finally {
              setSavingRequirement(false);
            }
          }}
        />
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
            <Button
              type="primary"
              loading={running}
              disabled={!canRun || !requirementContextId}
              onClick={() => void runSuggestion()}
            >
              生成建议
            </Button>
          </Space>
        </Space>
      ) : null}
      {step === 2 ? (
        <Space direction="vertical" style={{ width: "100%" }} size={12}>
          <Typography.Text type="secondary">请选择并采纳一条建议后进入变量填写。</Typography.Text>
          <List
            size="small"
            bordered
            dataSource={suggestions}
            locale={{ emptyText: "未返回建议" }}
            renderItem={(item) => (
              <List.Item
                onClick={() => setSelectedSuggestionId(item.suggestion_id)}
                style={{ cursor: "pointer", background: selectedSuggestionId === item.suggestion_id ? "#f6ffed" : undefined }}
              >
                <Space direction="vertical" size={4} style={{ width: "100%" }}>
                  <Radio checked={selectedSuggestionId === item.suggestion_id}>
                    建议ID: {item.suggestion_id.slice(0, 8)}
                  </Radio>
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
          <TextArea
            rows={3}
            value={adoptionReason}
            onChange={(event) => setAdoptionReason(event.target.value)}
            placeholder="采纳理由（可选）"
          />
          <Space>
            <Button onClick={() => setStep(1)}>上一步</Button>
            <Button
              type="primary"
              disabled={!selectedSuggestionId}
              onClick={async () => {
                if (!selectedSuggestionId) return;
                setRunning(true);
                try {
                  await patchSuggestionAdoption(kbId, selectedSuggestionId, {
                    status: "adopted",
                    adoption_reason: adoptionReason || undefined,
                  });
                  message.success("建议已采纳");
                  setStep(3);
                } catch (error) {
                  message.error((error as Error).message);
                } finally {
                  setRunning(false);
                }
              }}
            >
              采纳并继续
            </Button>
          </Space>
        </Space>
      ) : null}
      {step === 3 ? (
        <Space direction="vertical" style={{ width: "100%" }} size={12}>
          <VariableFillPanel variables={extractedVariables} values={variableValues} onChange={setVariableValues} />
          <Space>
            <Button onClick={() => setStep(2)}>上一步</Button>
            <Button type="primary" onClick={() => setStep(4)}>
              下一步
            </Button>
          </Space>
        </Space>
      ) : null}
      {step === 4 ? (
        <Space direction="vertical" style={{ width: "100%" }} size={12}>
          <Alert
            type="info"
            showIcon
            message="确认生成参数"
            description={
              <Space direction="vertical">
                <Typography.Text>约束ID：{requirementContextId || "-"}</Typography.Text>
                <Typography.Text>建议ID：{selectedSuggestionId || "-"}</Typography.Text>
                <Typography.Text>目标章节：{targetOutlineNode?.title ?? "-"}</Typography.Text>
              </Space>
            }
          />
          <Space>
            <Button onClick={() => setStep(3)}>上一步</Button>
            <Button
              type="primary"
              loading={running}
              disabled={!requirementContextId || !selectedSuggestionId || !targetOutlineNode}
              onClick={async () => {
                if (!requirementContextId || !selectedSuggestionId || !targetOutlineNode) return;
                setRunning(true);
                try {
                  const task = await createDraft(kbId, {
                    requirement_context_id: requirementContextId,
                    suggestion_id: selectedSuggestionId,
                    target_outline_node: targetOutlineNode,
                    product_category_ids: productCategoryIds,
                    variable_values: variableValues,
                    confirm_adoption: true,
                  });
                  setTaskId(task.task_id);
                  message.success(`已触发生成任务：${task.task_id}`);
                  setStep(5);
                } catch (error) {
                  message.error((error as Error).message);
                } finally {
                  setRunning(false);
                }
              }}
            >
              开始生成
            </Button>
          </Space>
        </Space>
      ) : null}
      {step === 5 ? (
        <Space direction="vertical" style={{ width: "100%" }} size={12}>
          <ChapterDraftPanel kbId={kbId} taskId={taskId} variableValues={variableValues} />
          <Space>
            <Button onClick={() => setStep(4)}>返回生成配置</Button>
            <Button type="primary" onClick={reset}>
              完成
            </Button>
          </Space>
        </Space>
      ) : null}
    </Drawer>
  );
}
