import { Card, Form, Input, Space, Tag, Typography } from "antd";

export interface TemplateVariableItem {
  key: string;
  label?: string;
  required?: boolean;
  default_value?: string;
  description?: string;
}

interface Props {
  variables: TemplateVariableItem[];
  values: Record<string, string>;
  onChange: (values: Record<string, string>) => void;
}

export function VariableFillPanel({ variables, values, onChange }: Props) {
  if (!variables.length) {
    return <Typography.Text type="secondary">当前建议未声明变量，可直接进入生成。</Typography.Text>;
  }

  return (
    <Space direction="vertical" size={12} style={{ width: "100%" }}>
      {variables.map((item) => (
        <Card key={item.key} size="small">
          <Form layout="vertical">
            <Form.Item
              label={
                <Space size={8}>
                  <span>{item.label || item.key}</span>
                  {item.required ? <Tag color="red">必填</Tag> : <Tag>可选</Tag>}
                </Space>
              }
              tooltip={item.description || item.key}
            >
              <Input
                value={values[item.key] ?? item.default_value ?? ""}
                placeholder={item.default_value ? `默认值：${item.default_value}` : "请输入变量值"}
                onChange={(event) => onChange({ ...values, [item.key]: event.target.value })}
              />
            </Form.Item>
          </Form>
        </Card>
      ))}
    </Space>
  );
}
