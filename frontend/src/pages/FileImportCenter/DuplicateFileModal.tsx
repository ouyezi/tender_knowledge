import { Button, Modal, Space, Typography } from "antd";

interface DuplicateFileModalProps {
  open: boolean;
  fileHash?: string;
  existingImportIds: string[];
  onCancel: () => void;
  onSkip: () => void;
  onNewVersion: () => void;
  loading?: boolean;
}

export default function DuplicateFileModal({
  open,
  fileHash,
  existingImportIds,
  onCancel,
  onSkip,
  onNewVersion,
  loading = false,
}: DuplicateFileModalProps) {
  return (
    <Modal
      open={open}
      title="检测到重复文件"
      onCancel={onCancel}
      onOk={onNewVersion}
      confirmLoading={loading}
      okText="作为新版本继续"
      cancelText="取消"
      footer={(_, { OkBtn, CancelBtn }) => (
        <Space>
          <CancelBtn />
          <Button
            onClick={onSkip}
            loading={loading}
          >
            跳过并使用已有记录
          </Button>
          <OkBtn />
        </Space>
      )}
    >
      <Typography.Paragraph>
        系统发现相同内容文件已存在。你可以选择直接复用已有记录，或者创建一个新版本继续处理。
      </Typography.Paragraph>
      <Typography.Paragraph type="secondary">file_hash: {fileHash ?? "-"}</Typography.Paragraph>
      <Typography.Paragraph type="secondary">
        已存在导入记录: {existingImportIds.length > 0 ? existingImportIds.join(", ") : "-"}
      </Typography.Paragraph>
    </Modal>
  );
}
