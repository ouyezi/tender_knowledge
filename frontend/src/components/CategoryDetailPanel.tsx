import { Button, Card, Form, Input, Select, Space, Tag } from "antd";
import { useEffect } from "react";
import type { ProductCategoryDetail } from "../services/productCategoryApi";

interface CategoryDetailPanelProps {
  detail?: ProductCategoryDetail;
  readOnly?: boolean;
  saving?: boolean;
  isNew?: boolean;
  parentLabel?: string;
  onSave: (values: {
    category_name: string;
    category_code: string;
    description?: string;
    aliases: string[];
    status?: string;
  }) => void;
}

interface FormValues {
  category_name: string;
  category_code: string;
  description?: string;
  aliases: string[];
  status?: string;
}

const STATUS_OPTIONS = [
  { label: "启用", value: "active" },
  { label: "停用", value: "inactive" },
  { label: "归档", value: "archived" },
];

export default function CategoryDetailPanel({
  detail,
  readOnly = false,
  saving = false,
  isNew = false,
  parentLabel,
  onSave,
}: CategoryDetailPanelProps) {
  const [form] = Form.useForm<FormValues>();

  useEffect(() => {
    if (isNew) {
      form.setFieldsValue({
        category_name: "",
        category_code: "",
        description: "",
        aliases: [],
        status: "active",
      });
      return;
    }
    if (!detail) {
      form.resetFields();
      return;
    }
    form.setFieldsValue({
      category_name: detail.category_name,
      category_code: detail.category_code,
      description: detail.description,
      aliases: detail.aliases,
      status: detail.status,
    });
  }, [detail, form, isNew]);

  const disabled = readOnly || (!isNew && !detail);

  return (
    <Card
      title={
        isNew
          ? parentLabel
            ? `新建子分类（父：${parentLabel}）`
            : "新建分类"
          : "分类详情"
      }
      extra={
        detail?.breadcrumb?.length ? (
          <Space size={4} wrap>
            {detail.breadcrumb.map((item) => (
              <Tag key={item.category_id}>{item.category_name}</Tag>
            ))}
          </Space>
        ) : null
      }
    >
      <Form form={form} layout="vertical" disabled={disabled}>
        <Form.Item
          label="名称"
          name="category_name"
          rules={[{ required: true, message: "请输入分类名称" }]}
        >
          <Input placeholder="例如：福利产品" maxLength={128} />
        </Form.Item>
        <Form.Item
          label="编码"
          name="category_code"
          rules={[{ required: true, message: "请输入分类编码" }]}
        >
          <Input placeholder="例如：welfare" maxLength={64} disabled={!isNew || readOnly} />
        </Form.Item>
        <Form.Item label="描述" name="description">
          <Input.TextArea rows={3} placeholder="可选描述" />
        </Form.Item>
        <Form.Item label="别名" name="aliases">
          <Select
            mode="tags"
            tokenSeparators={[","]}
            placeholder="输入别名后回车"
            open={false}
          />
        </Form.Item>
        {!isNew && (
          <Form.Item label="状态" name="status">
            <Select options={STATUS_OPTIONS} disabled={readOnly || detail?.status === "merged"} />
          </Form.Item>
        )}
        <Form.Item>
          <Button
            type="primary"
            loading={saving}
            disabled={disabled}
            onClick={async () => {
              const values = await form.validateFields();
              onSave(values);
            }}
          >
            保存
          </Button>
        </Form.Item>
      </Form>
    </Card>
  );
}
