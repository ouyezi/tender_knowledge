import { Alert, Button, Card, Space, Table, Upload, message } from "antd";
import type { ColumnsType } from "antd/es/table";
import type { RcFile } from "antd/es/upload/interface";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useKBContext } from "../../layout/KBContext";
import ConfirmDrawer from "./ConfirmDrawer";
import DuplicateFileModal from "./DuplicateFileModal";
import TaskLogDrawer from "./TaskLogDrawer";
import {
  retryImport,
  getFileImport,
  listFileImports,
  type FileImportListItem,
  uploadFile,
} from "../../services/fileImports";
import { ApiError } from "../../services/apiClient";

export default function FileImportCenterPage() {
  const { selectedKbId } = useKBContext();
  const [items, setItems] = useState<FileImportListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [selectedImportId, setSelectedImportId] = useState<string>();
  const [taskLogOpen, setTaskLogOpen] = useState(false);
  const [taskLogImportId, setTaskLogImportId] = useState<string>();
  const [pendingDuplicateFile, setPendingDuplicateFile] = useState<RcFile>();
  const [duplicateImportIds, setDuplicateImportIds] = useState<string[]>([]);
  const [duplicateHash, setDuplicateHash] = useState<string>();

  const loadData = useCallback(async () => {
    if (!selectedKbId) {
      setItems([]);
      setTotal(0);
      return;
    }
    setLoading(true);
    try {
      const result = await listFileImports(selectedKbId, { page, page_size: pageSize });
      setItems(result.items ?? []);
      setTotal(result.total ?? 0);
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, selectedKbId]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  useEffect(() => {
    setPage(1);
    setConfirmOpen(false);
    setSelectedImportId(undefined);
    setTaskLogOpen(false);
    setTaskLogImportId(undefined);
  }, [selectedKbId]);

  const columns = useMemo<ColumnsType<FileImportListItem>>(
    () => [
      {
        title: "文件名",
        dataIndex: "file_name",
        key: "file_name",
      },
      {
        title: "文件类型",
        dataIndex: "file_type",
        key: "file_type",
      },
      {
        title: "状态",
        dataIndex: "status",
        key: "status",
      },
      {
        title: "创建时间",
        dataIndex: "created_at",
        key: "created_at",
        render: (value?: string) => (value ? new Date(value).toLocaleString() : "-"),
      },
      {
        title: "操作",
        key: "actions",
        render: (_value, record) => (
          <Space>
            <Button
              size="small"
              onClick={(event) => {
                event.stopPropagation();
                if (record.status !== "need_confirm") {
                  return;
                }
                setSelectedImportId(record.import_id);
                setConfirmOpen(true);
              }}
            >
              确认
            </Button>
            <Button
              size="small"
              onClick={async (event) => {
                event.stopPropagation();
                if (!selectedKbId) {
                  return;
                }
                try {
                  const result = await retryImport(selectedKbId, record.import_id, "all");
                  message.success(`已触发重试：${result.tasks_enqueued.join(", ") || "无新任务"}`);
                  void loadData();
                } catch (error) {
                  message.error((error as Error).message);
                }
              }}
            >
              重试
            </Button>
            <Button
              size="small"
              onClick={(event) => {
                event.stopPropagation();
                setTaskLogImportId(record.import_id);
                setTaskLogOpen(true);
              }}
            >
              任务日志
            </Button>
          </Space>
        ),
      },
    ],
    [loadData, selectedKbId],
  );

  if (!selectedKbId) {
    return <Alert type="info" showIcon message="请先在顶栏选择一个知识库" />;
  }

  const handleUpload = async (file: RcFile) => {
    if (!selectedKbId) {
      return;
    }
    setUploading(true);
    try {
      const uploadResult = await uploadFile(selectedKbId, file);
      message.success(`上传成功：${uploadResult.file_name}`);
      void loadData();

      for (let i = 0; i < 12; i += 1) {
        await new Promise((resolve) => setTimeout(resolve, 1000));
        const detail = await getFileImport(selectedKbId, uploadResult.import_id);
        if (detail.status === "need_confirm") {
          message.success("文件用途建议已生成，可确认用途");
          break;
        }
      }
      void loadData();
    } catch (error) {
      if (error instanceof ApiError && error.code === "DUPLICATE_FILE") {
        const existingImportIds = (error.details?.existing_import_ids as string[] | undefined) ?? [];
        const fileHash = (error.details?.file_hash as string | undefined) ?? undefined;
        setPendingDuplicateFile(file);
        setDuplicateImportIds(existingImportIds);
        setDuplicateHash(fileHash);
      } else {
        message.error((error as Error).message);
      }
    } finally {
      setUploading(false);
    }
  };

  const handleDuplicateAction = async (action: "skip" | "new_version") => {
    if (!selectedKbId || !pendingDuplicateFile) {
      return;
    }
    setUploading(true);
    try {
      const uploadResult = await uploadFile(selectedKbId, pendingDuplicateFile, {
        duplicate_action: action,
        parent_import_id: action === "new_version" ? duplicateImportIds[0] : undefined,
      });
      message.success(`${action === "skip" ? "已复用已有记录" : "已创建新版本"}：${uploadResult.file_name}`);
      setPendingDuplicateFile(undefined);
      setDuplicateImportIds([]);
      setDuplicateHash(undefined);
      void loadData();
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setUploading(false);
    }
  };

  return (
    <Card title="来源导入">
      <Upload.Dragger
        multiple={false}
        showUploadList={false}
        disabled={uploading}
        beforeUpload={(file) => {
          void handleUpload(file as RcFile);
          return false;
        }}
        style={{ marginBottom: 16 }}
      >
        <p>拖拽文件到此处，或点击上传</p>
        <p>支持 docx / pdf / ppt / xlsx / image</p>
      </Upload.Dragger>
      <Table
        rowKey="import_id"
        loading={loading}
        dataSource={items}
        columns={columns}
        onRow={(record) => ({
          onClick: () => {
            if (record.status !== "need_confirm") {
              return;
            }
            setSelectedImportId(record.import_id);
            setConfirmOpen(true);
          },
        })}
        rowClassName={(record) => (record.status === "need_confirm" ? "clickable-row" : "")}
        pagination={{
          current: page,
          pageSize,
          total,
          showSizeChanger: true,
          onChange: (nextPage, nextPageSize) => {
            setPage(nextPage);
            setPageSize(nextPageSize);
          },
        }}
      />
      <ConfirmDrawer
        open={confirmOpen}
        kbId={selectedKbId}
        importId={selectedImportId}
        onClose={() => setConfirmOpen(false)}
        onSaved={loadData}
      />
      <DuplicateFileModal
        open={Boolean(pendingDuplicateFile)}
        existingImportIds={duplicateImportIds}
        fileHash={duplicateHash}
        loading={uploading}
        onCancel={() => {
          setPendingDuplicateFile(undefined);
          setDuplicateImportIds([]);
          setDuplicateHash(undefined);
        }}
        onSkip={() => {
          void handleDuplicateAction("skip");
        }}
        onNewVersion={() => {
          void handleDuplicateAction("new_version");
        }}
      />
      <TaskLogDrawer
        open={taskLogOpen}
        kbId={selectedKbId}
        importId={taskLogImportId}
        onClose={() => setTaskLogOpen(false)}
      />
    </Card>
  );
}
