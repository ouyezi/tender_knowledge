import { Button, Card, Input, Select, Space, Switch, Table, message } from "antd";
import { useMemo, useState } from "react";
import {
  createTemplateRule,
  createTemplateVariable,
  type TemplateRuleItem,
  type TemplateVariableItem,
  updateTemplateRule,
  updateTemplateVariable,
} from "../../services/templates";

type VariableRulePanelProps = {
  kbId: string;
  templateId: string;
  variables: TemplateVariableItem[];
  rules: TemplateRuleItem[];
  onReload: () => Promise<void>;
};

export default function VariableRulePanel({
  kbId,
  templateId,
  variables,
  rules,
  onReload,
}: VariableRulePanelProps) {
  const [newVariableKey, setNewVariableKey] = useState("");
  const [newRuleType, setNewRuleType] = useState("required");
  const variableColumns = useMemo(
    () => [
      { title: "变量 Key", dataIndex: "variable_key", key: "variable_key" },
      { title: "显示名", dataIndex: "display_name", key: "display_name" },
      { title: "类型", dataIndex: "value_type", key: "value_type" },
      {
        title: "必填",
        dataIndex: "required",
        key: "required",
        render: (value: boolean, record: TemplateVariableItem) => (
          <Switch
            size="small"
            checked={value}
            onChange={async (checked) => {
              await updateTemplateVariable(kbId, templateId, record.variable_id, { required: checked });
              await onReload();
            }}
          />
        ),
      },
      {
        title: "状态",
        dataIndex: "status",
        key: "status",
      },
      {
        title: "操作",
        key: "actions",
        render: (_: unknown, record: TemplateVariableItem) => (
          <Button
            danger
            type="link"
            onClick={async () => {
              await updateTemplateVariable(kbId, templateId, record.variable_id, { status: "inactive" });
              await onReload();
            }}
          >
            停用
          </Button>
        ),
      },
    ],
    [kbId, onReload, templateId],
  );

  const ruleColumns = useMemo(
    () => [
      { title: "规则类型", dataIndex: "rule_type", key: "rule_type" },
      { title: "动作", dataIndex: "action", key: "action" },
      { title: "提示", dataIndex: "message", key: "message" },
      {
        title: "状态",
        dataIndex: "status",
        key: "status",
      },
      {
        title: "操作",
        key: "actions",
        render: (_: unknown, record: TemplateRuleItem) => (
          <Button
            danger
            type="link"
            onClick={async () => {
              await updateTemplateRule(kbId, templateId, record.rule_id, { status: "inactive" });
              await onReload();
            }}
          >
            停用
          </Button>
        ),
      },
    ],
    [kbId, onReload, templateId],
  );

  return (
    <Space direction="vertical" style={{ width: "100%" }} size={16}>
      <Card
        size="small"
        title="变量"
        extra={
          <Space>
            <Input
              style={{ width: 220 }}
              value={newVariableKey}
              placeholder="变量 key，如 project_name"
              onChange={(event) => setNewVariableKey(event.target.value)}
            />
            <Button
              type="primary"
              onClick={async () => {
                if (!newVariableKey.trim()) {
                  message.warning("请输入变量 key");
                  return;
                }
                await createTemplateVariable(kbId, templateId, {
                  variable_key: newVariableKey.trim(),
                  value_type: "string",
                  required: false,
                });
                setNewVariableKey("");
                await onReload();
              }}
            >
              新增变量
            </Button>
          </Space>
        }
      >
        <Table rowKey="variable_id" size="small" pagination={false} columns={variableColumns} dataSource={variables} />
      </Card>
      <Card
        size="small"
        title="规则（MVP）"
        extra={
          <Space>
            <Select
              style={{ width: 180 }}
              value={newRuleType}
              options={[
                { label: "required", value: "required" },
                { label: "optional", value: "optional" },
                { label: "product_match", value: "product_match" },
              ]}
              onChange={(value) => setNewRuleType(value)}
            />
            <Button
              type="primary"
              onClick={async () => {
                await createTemplateRule(kbId, templateId, {
                  rule_type: newRuleType,
                  action: "enable",
                  message: "新增规则",
                });
                await onReload();
              }}
            >
              新增规则
            </Button>
          </Space>
        }
      >
        <Table rowKey="rule_id" size="small" pagination={false} columns={ruleColumns} dataSource={rules} />
      </Card>
    </Space>
  );
}
