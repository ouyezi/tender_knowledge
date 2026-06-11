import { Button, Card, Form, Input, Select, Space, Tag } from "antd";
import { useEffect } from "react";
import type { ChapterTaxonomyDetail } from "../services/chapterTaxonomyApi";

export interface ProductCategoryOption {
  label: string;
  value: string;
}

interface TaxonomyDetailPanelProps {
  detail?: ChapterTaxonomyDetail;
  readOnly?: boolean;
  saving?: boolean;
  isNew?: boolean;
  productCategoryOptions: ProductCategoryOption[];
  onSave: (values: {
    standard_name: string;
    taxonomy_code: string;
    description?: string;
    synonyms: string[];
    product_category_ids: string[];
    status?: string;
  }) => void;
}

interface FormValues {
  standard_name: string;
  taxonomy_code: string;
  description?: string;
  synonyms: string[];
  product_category_ids: string[];
  status?: string;
}

const STATUS_OPTIONS = [
  { label: "启用", value: "active" },
  { label: "停用", value: "inactive" },
  { label: "归档", value: "archived" },
];

export default function TaxonomyDetailPanel({
  detail,
  readOnly = false,
  saving = false,
  isNew = false,
  productCategoryOptions,
  onSave,
}: TaxonomyDetailPanelProps) {
  const [form] = Form.useForm<FormValues>();

  useEffect(() => {
    if (isNew) {
      form.setFieldsValue({
        standard_name: "",
        taxonomy_code: "",
        description: "",
        synonyms: [],
        product_category_ids: [],
        status: "active",
      });
      return;
    }
    if (!detail) {
      form.resetFields();
      return;
    }
    form.setFieldsValue({
      standard_name: detail.standard_name,
      taxonomy_code: detail.taxonomy_code,
      description: detail.description,
      synonyms: detail.synonyms,
      product_category_ids: detail.product_category_ids,
      status: detail.status,
    });
  }, [detail, form, isNew]);

  const disabled = readOnly || (!isNew && !detail);

  return (
    <Card
      title={isNew ? "新建章节类型" : "章节类型详情"}
      extra={
        detail?.breadcrumb?.length ? (
          <Space size={4} wrap>
            {detail.breadcrumb.map((item) => (
              <Tag key={item.taxonomy_id}>{item.standard_name}</Tag>
            ))}
          </Space>
        ) : null
      }
    >
      <Form form={form} layout="vertical" disabled={disabled}>
        <Form.Item
          label="标准名称"
          name="standard_name"
          rules={[{ required: true, message: "请输入标准名称" }]}
        >
          <Input placeholder="例如：售后服务方案" maxLength={128} />
        </Form.Item>
        <Form.Item
          label="编码"
          name="taxonomy_code"
          rules={[{ required: true, message: "请输入编码" }]}
        >
          <Input placeholder="例如：after-sales" maxLength={64} disabled={!isNew || readOnly} />
        </Form.Item>
        <Form.Item label="描述" name="description">
          <Input.TextArea rows={3} placeholder="可选描述" />
        </Form.Item>
        <Form.Item label="同义名" name="synonyms">
          <Select
            mode="tags"
            tokenSeparators={[","]}
            placeholder="输入同义名后回车"
            open={false}
          />
        </Form.Item>
        <Form.Item label="关联产品分类" name="product_category_ids">
          <Select
            mode="multiple"
            allowClear
            placeholder="选择关联的产品分类"
            options={productCategoryOptions}
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
