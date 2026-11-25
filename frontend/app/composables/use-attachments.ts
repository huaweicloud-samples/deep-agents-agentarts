import { unref, type Ref } from "vue";
import { apiClient, getUserId } from "~/api/client";

export const DEFAULT_ACCEPTED_FILES =
  "image/*,application/pdf,.txt,.md,.markdown,.json,.csv,.py,.js,.ts,.html,.css,.doc,.docx";
export const DEFAULT_MAX_FILE_SIZE = 20 * 1024 * 1024; // 20MB

export type ThreadIdGetter = string | Ref<string | undefined> | (() => string | undefined);

export function useAttachments(getThreadId?: ThreadIdGetter, userId?: string) {
  const onUpload = async (file: File) => {
    const activeUserId = userId || getUserId();
    const resolvedThreadId =
      typeof getThreadId === "function"
        ? getThreadId()
        : unref(getThreadId);

    if (!resolvedThreadId) {
      throw new Error("请先选择或新建一个会话后再上传文件");
    }

    // 直接上传至沙箱环境工作区 (/home/user/uploads/...)
    const data = await apiClient.upload.file(file, resolvedThreadId, activeUserId);
    return {
      type: "url" as const,
      value: data.url,
      mimeType: data.mime_type || file.type,
      metadata: {
        filename: data.filename || file.name,
        sandbox_path: data.sandbox_path,
        size: data.size || file.size,
        threadId: data.thread_id || resolvedThreadId,
        userId: activeUserId,
      },
    };
  };

  const onUploadFailed = (error: { message: string; reason?: string }) => {
    console.error("附件处理失败:", error);
    alert(`附件上传失败: ${error.message} (${error.reason || "未知原因"})`);
  };

  return {
    attachmentsConfig: {
      enabled: true,
      accept: DEFAULT_ACCEPTED_FILES,
      maxSize: DEFAULT_MAX_FILE_SIZE,
      maxConcurrentUploads: 3,
      onUpload,
      onUploadFailed,
    },
  };
}
