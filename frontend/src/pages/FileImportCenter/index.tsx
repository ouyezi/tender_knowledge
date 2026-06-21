import { Alert, Button, Card, Modal, Space, Table, Tag, Upload, message } from "antd";
import type { ColumnsType } from "antd/es/table";
import type { RcFile } from "antd/es/upload/interface";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useKBContext } from "../../layout/KBContext";
import ConfirmDrawer from "./ConfirmDrawer";
import DuplicateFileModal from "./DuplicateFileModal";
import TaskLogDrawer from "./TaskLogDrawer";
import OperationLogDrawer from "./OperationLogDrawer";
import {
  deleteFileImport,
  getFileImportPurgeImpact,
  purgeAllFileImports,
  retryDocumentParse,
  retryImport,
  getFileImport,
  listFileImports,
  type FileImportListItem,
  type ParseStatus,
  uploadFile,
} from "../../services/fileImports";
import { ApiError } from "../../services/apiClient";

const PARSE_STATUS_TAG: Record<string, { color: string; label: string }> = {
  running: { color: "processing", label: "解析中" },
  parsing: { color: "processing", label: "解析中" },
  parse_ready: { color: "warning", label: "待确认" },
  parse_confirmed: { color: "success", label: "已确认" },
  failed: { color: "error", label: "失败" },
  parse_failed: { color: "error", label: "失败" },
};

function ParseStatusCell({
  parseStatus,
  documentId,
  importStatus,
  retrying,
  onRetry,
}: {
  parseStatus?: ParseStatus;
  documentId?: string | null;
  importStatus?: string;
  retrying: boolean;
  onRetry: () => void;
}) {
  if (!parseStatus && importStatus !== "completed" && importStatus !== "failed") {
    return <>—</>;
  }

  const effectiveStatus =
    parseStatus ??
    (importStatus === "completed" ? "parse_confirmed" : importStatus === "failed" ? "failed" : null);

  if (!effectiveStatus) {
    return <>—</>;
  }

  const tagMeta = PARSE_STATUS_TAG[effectiveStatus] ?? {
    color: "default",
    label: effectiveStatus,
  };
  const isFailed = effectiveStatus === "failed" || effectiveStatus === "parse_failed";
  const canRetryParse =
    isFailed ||
    effectiveStatus === "parsing" ||
    effectiveStatus === "running" ||
    effectiveStatus === "parse_ready" ||
    importStatus === "completed" ||
    importStatus === "failed";

  return (
    <Space size="small">
      <Tag color={tagMeta.color}>{tagMeta.label}</Tag>
      {importStatus === "completed" && documentId ? (
        <Link to={`/knowledge/entry?docId=${documentId}`}>前往知识录入</Link>
      ) : null}
      {canRetryParse ? (
        <Button type="link" size="small" loading={retrying} onClick={onRetry}>
          重试解析
        </Button>
      ) : null}
    </Space>
  );
}

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
  const [retryingParseImportIds, setRetryingParseImportIds] = useState<Set<string>>(new Set());
  const [operationLogOpen, setOperationLogOpen] = useState(false);
  const [operationLogImportId, setOperationLogImportId] = useState<string>();
  const [purgingAll, setPurgingAll] = useState(false);
  const [deleteImpactLoading, setDeleteImpactLoading] = useState(false);
  const [deletingImportId, setDeletingImportId] = useState<string | null>(null);

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

  const handleRetryParse = useCallback(
    async (importId: string) => {
      if (!selectedKbId) {
        return;
      }
      setRetryingParseImportIds((prev) => new Set(prev).add(importId));
      try {
        const result = await retryDocumentParse(selectedKbId, importId);
        message.success(`已触发解析重试：${result.parse_task_id}`);
        void loadData();
      } catch (error) {
        message.error((error as Error).message);
      } finally {
        setRetryingParseImportIds((prev) => {
          const next = new Set(prev);
          next.delete(importId);
          return next;
        });
      }
    },
    [loadData, selectedKbId],
  );

  const handleDeleteClick = useCallback(
    async (record: FileImportListItem) => {
      if (!selectedKbId) {
        return;
      }
      setDeleteImpactLoading(true);
      setDeletingImportId(record.import_id);
      let impactText = "将删除导入文件、解析数据及已录入知识，不可恢复。";
      try {
        const impact = await getFileImportPurgeImpact(selectedKbId, record.import_id);
        const counts = impact.intermediate_counts;
        const parts = [
          counts.knowledge_chunks ? `${counts.knowledge_chunks} 条知识` : null,
          counts.documents ? `${counts.documents} 个文档` : null,
        ].filter(Boolean);
        if (parts.length > 0) {
          impactText = `将删除 ${parts.join("、")} 及导入文件，不可恢复。`;
        }
      } catch (error) {
        message.error((error as Error).message);
        return;
      } finally {
        setDeleteImpactLoading(false);
        setDeletingImportId(null);
      }
      Modal.confirm({
        title: "确定删除该导入记录？",
        content: impactText,
        okText: "删除",
        okButtonProps: { danger: true },
        cancelText: "取消",
        onOk: async () => {
          try {
            await deleteFileImport(selectedKbId, record.import_id);
            message.success("已删除");
            void loadData();
          } catch (error) {
            message.error((error as Error).message);
            throw error;
          }
        },
      });
    },
    [loadData, selectedKbId],
  );

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
        title: "解析状态",
        dataIndex: "parse_status",
        key: "parse_status",
        render: (value: ParseStatus | undefined, record) => (
          <ParseStatusCell
            parseStatus={value ?? null}
            documentId={record.document_id}
            importStatus={record.status}
            retrying={retryingParseImportIds.has(record.import_id)}
            onRetry={() => {
              void handleRetryParse(record.import_id);
            }}
          />
        ),
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
            <Button
              size="small"
              onClick={(event) => {
                event.stopPropagation();
                setOperationLogImportId(record.import_id);
                setOperationLogOpen(true);
              }}
            >
              操作日志
            </Button>
            <Button
              size="small"
              danger
              loading={deleteImpactLoading && deletingImportId === record.import_id}
              onClick={(event) => {
                event.stopPropagation();
                void handleDeleteClick(record);
              }}
            >
              删除
            </Button>
          </Space>
        ),
      },
    ],
    [deleteImpactLoading, deletingImportId, handleDeleteClick, handleRetryParse, retryingParseImportIds, loadData, selectedKbId],
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

  const handlePurgeAll = () => {
    if (!selectedKbId) {
      return;
    }
    Modal.confirm({
      title: "清空全部来源导入？",
      content: "将删除当前知识库下所有导入记录、上传文件及解析产物，不可恢复。",
      okText: "确认清空",
      okButtonProps: { danger: true },
      cancelText: "取消",
      onOk: async () => {
        setPurgingAll(true);
        try {
          const result = await purgeAllFileImports(selectedKbId);
          message.success(`已清空 ${result.purged_count} 条导入记录`);
          void loadData();
        } catch (error) {
          message.error((error as Error).message);
        } finally {
          setPurgingAll(false);
        }
      },
    });
  };

  return (
    <Card
      title="来源导入"
      extra={
        <Space>
          <Button onClick={() => { setOperationLogImportId(undefined); setOperationLogOpen(true); }}>
            操作日志
          </Button>
          <Button danger loading={purgingAll} onClick={handlePurgeAll}>
            清空全部
          </Button>
        </Space>
      }
    >
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
        <p>支持 docx / docm / pdf / ppt / xlsx / image</p>
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
      <OperationLogDrawer
        open={operationLogOpen}
        kbId={selectedKbId}
        importId={operationLogImportId}
        onClose={() => setOperationLogOpen(false)}
      />
    </Card>
  );
}
