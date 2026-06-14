import { apiRequest } from "./apiClient";

export interface ChapterPatternMiningTask {
  mining_task_id: string;
  status: string;
  trace_id?: string;
}

export interface TriggerChapterPatternMiningPayload {
  min_frequency?: number;
  include_template_chapters?: boolean;
}

export async function triggerChapterPatternMining(
  kbId: string,
  payload: TriggerChapterPatternMiningPayload = {},
): Promise<ChapterPatternMiningTask> {
  return apiRequest<ChapterPatternMiningTask>(`/api/v1/kbs/${kbId}/chapter-patterns/mine`, {
    method: "POST",
    body: payload,
  });
}
