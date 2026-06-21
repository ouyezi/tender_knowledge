import {
  Alert,
  Button,
  Descriptions,
  Drawer,
  Form,
  Select,
  Space,
  Switch,
  message,
} from "antd";
import { useCallback, useEffect, useState } from "react";
import { ApiError } from "../../services/apiClient";
import {
  confirmFileImport,
  getFileImport,
  ignoreFileImport,
  type FileImportDetail,
} from "../../services/fileImports";

interface ConfirmDrawerProps {
  open: boolean;
  kbId?: string;
  importId?: string;
  onClose: () => void;
  onSaved: () => Promise<void> | void;
}

interface ConfirmFormValues {
  file_purpose: string;
  enter_parsing: boolean;
}

const FILE_PURPOSE_OPTIONS = [
  { label: "实际标书", value: "actual_bid" },
  { label: "模板文件", value: "template_file" },
];

export default function ConfirmDrawer({ open, kbId, importId, onClose, onSaved }: ConfirmDrawerProps) {
  const [form] = Form.useForm<ConfirmFormValues>();
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [detail, setDetail] = useState<FileImportDetail>();

  const refreshDetail = useCallback(async () => {
    if (!kbId || !importId) {
      return;
    }
    const next = await getFileImport(kbId, importId);
    setDetail(next);
    form.setFieldsValue({
      file_purpose: next.file_purpose ?? next.suggestion?.suggested_purpose ?? undefined,
      enter_parsing: next.enter_parsing ?? true,
    });
  }, [form, importId, kbId]);

  useEffect(() => {
    if (!open || !kbId || !importId) {
      return;
    }
    setLoading(true);
    refreshDetail()
      .catch((error: unknown) => {
        message.error((error as Error).message);
      })
      .finally(() => {
        setLoading(false);
      });
  }, [open, kbId, importId, refreshDetail]);

  const handleConfirm = async () => {
    if (!kbId || !importId || !detail) {
      return;
    }
    const values = await form.validateFields();
    setSubmitting(true);
    try {
      await confirmFileImport(kbId, importId, {
        expected_version: detail.version,
        file_purpose: values.file_purpose,
        enter_parsing: values.enter_parsing,
      });
      message.success("确认成功");
      await onSaved();
      onClose();
    } catch (error) {
      if (error instanceof ApiError && error.code === "CONFLICT") {
        message.warning("记录已被其他人更新，已刷新最新版本，请确认后重试");
        await refreshDetail();
      } else {
        message.error((error as Error).message);
      }
    } finally {
      setSubmitting(false);
    }
  };

  const handleIgnore = async () => {
    if (!kbId || !importId || !detail) {
      return;
    }
    setSubmitting(true);
    try {
      await ignoreFileImport(kbId, importId, detail.version);
      message.success("已忽略该文件");
      await onSaved();
      onClose();
    } catch (error) {
      if (error instanceof ApiError && error.code === "CONFLICT") {
        message.warning("记录版本冲突，已刷新最新数据");
        await refreshDetail();
      } else {
        message.error((error as Error).message);
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Drawer
      title="确认文件用途"
      width={560}
      open={open}
      onClose={onClose}
      destroyOnHidden
      extra={
        <Space>
          <Button onClick={handleIgnore} disabled={submitting}>
            忽略
          </Button>
          <Button type="primary" onClick={handleConfirm} loading={submitting}>
            确认并保存
          </Button>
        </Space>
      }
    >
      {loading && <Alert type="info" showIcon message="正在加载确认数据..." style={{ marginBottom: 16 }} />}
      {detail?.suggestion && (
        <Alert
          type="info"
          showIcon
          message="系统建议（只读）"
          description={
            <Descriptions size="small" column={1}>
              <Descriptions.Item label="建议用途">
                {detail.suggestion.suggested_purpose ?? "-"}
              </Descriptions.Item>
              <Descriptions.Item label="置信度">
                {detail.suggestion.purpose_confidence ?? "-"}
              </Descriptions.Item>
              <Descriptions.Item label="建议依据">
                {detail.suggestion.rationale ?? "-"}
              </Descriptions.Item>
            </Descriptions>
          }
          style={{ marginBottom: 16 }}
        />
      )}

      <Form form={form} layout="vertical" initialValues={{ enter_parsing: true }}>
        <Form.Item
          label="文件用途"
          name="file_purpose"
          rules={[{ required: true, message: "请选择文件用途" }]}
        >
          <Select options={FILE_PURPOSE_OPTIONS} placeholder="请选择文件用途" />
        </Form.Item>

        <Form.Item label="进入解析" name="enter_parsing" valuePropName="checked">
          <Switch />
        </Form.Item>
      </Form>
    </Drawer>
  );
}
