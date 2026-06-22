import { Alert, Button, Drawer, Empty, Input, Space, Spin, Typography, message } from "antd";
import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "../../services/apiClient";
import {
  suggestBlueprintOutline,
  type SuggestOutlineResult,
} from "../../services/blueprints";
import BlueprintOutlineSuggestTree from "./BlueprintOutlineSuggestTree";

const { Paragraph, Text } = Typography;
const { TextArea } = Input;
const MAX_REQUIREMENT_LEN = 2000;

interface BlueprintOutlineSuggestDrawerProps {
  open: boolean;
  kbId?: string;
  blueprintId?: string;
  onClose: () => void;
}

export default function BlueprintOutlineSuggestDrawer({
  open,
  kbId,
  blueprintId,
  onClose,
}: BlueprintOutlineSuggestDrawerProps) {
  const [requirement, setRequirement] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SuggestOutlineResult>();
  const [errorText, setErrorText] = useState<string>();
  const openRef = useRef(open);

  useEffect(() => {
    openRef.current = open;
  }, [open]);

  useEffect(() => {
    if (!open) {
      setRequirement("");
      setResult(undefined);
      setErrorText(undefined);
      setLoading(false);
    }
  }, [open]);

  const handleGenerate = useCallback(async () => {
    const trimmed = requirement.trim();
    if (!trimmed) {
      message.warning("请输入目录需求描述");
      return;
    }
    if (!kbId || !blueprintId) {
      return;
    }

    setLoading(true);
    setErrorText(undefined);
    setResult(undefined);
    try {
      const data = await suggestBlueprintOutline(kbId, {
        blueprint_ids: [blueprintId],
        requirement_description: trimmed,
      });
      if (!openRef.current) {
        return;
      }
      setResult(data);
    } catch (error) {
      if (!openRef.current) {
        return;
      }
      if (error instanceof ApiError) {
        if (error.code === "outline_suggest_timeout") {
          setErrorText("生成超时，请精简需求后重试");
        } else {
          setErrorText(error.message || "生成失败，请稍后重试");
        }
      } else {
        setErrorText((error as Error).message || "生成失败，请稍后重试");
      }
    } finally {
      if (openRef.current) {
        setLoading(false);
      }
    }
  }, [blueprintId, kbId, requirement]);

  return (
    <Drawer
      title="目录建议"
      placement="right"
      width="50%"
      open={open}
      onClose={onClose}
      destroyOnClose
    >
      <Space direction="vertical" size={16} style={{ width: "100%" }}>
        <div>
          <Text strong>目录需求描述</Text>
          <TextArea
            rows={6}
            maxLength={MAX_REQUIREMENT_LEN}
            showCount
            value={requirement}
            onChange={(event) => setRequirement(event.target.value)}
            placeholder="描述项目背景、招标要求、希望突出的章节、评分关注点等……"
            disabled={loading}
          />
        </div>
        <Button type="primary" onClick={() => void handleGenerate()} loading={loading}>
          生成建议
        </Button>

        <div style={{ minHeight: 240 }}>
          {errorText ? <Alert type="error" message={errorText} showIcon /> : null}
          {loading ? <Spin style={{ display: "block", marginTop: 24 }} /> : null}
          {!loading && !result && !errorText ? (
            <Empty description="填写需求后点击「生成建议」" />
          ) : null}
          {result ? (
            <Space direction="vertical" size={12} style={{ width: "100%" }}>
              <div>
                <Text strong>{result.outline_title}</Text>
                <Paragraph type="secondary" style={{ marginBottom: 0 }}>
                  {result.summary}
                </Paragraph>
              </div>
              <BlueprintOutlineSuggestTree nodes={result.nodes} />
            </Space>
          ) : null}
        </div>
      </Space>
    </Drawer>
  );
}
