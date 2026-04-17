import { Paperclip, Trash2 } from "lucide-react";

import { formatFileSize } from "../../lib/format";
import type { StoredFileMeta } from "../../types/domain";

interface AttachmentTrayProps {
  files: StoredFileMeta[];
  selectedAttachmentIds: string[];
  onToggle: (fileId: string) => void;
  onDelete: (fileId: string) => void;
}

export function AttachmentTray({
  files,
  selectedAttachmentIds,
  onToggle,
  onDelete,
}: AttachmentTrayProps) {
  if (files.length === 0) {
    return (
      <div className="rounded-[20px] border border-dashed border-white/10 bg-black/10 px-4 py-3 text-sm text-slate-500">
        当前没有附件。上传后可在本轮消息中选择使用的文件。
      </div>
    );
  }

  const usingAll = selectedAttachmentIds.length === 0;

  return (
    <div className="space-y-3">
      <div className="rounded-[20px] border border-white/10 bg-black/10 px-4 py-3 text-xs leading-6 text-slate-400">
        {usingAll
          ? "当前未指定附件子集，本轮默认会带上所有已上传文件。"
          : `当前本轮仅使用 ${selectedAttachmentIds.length} 个附件。`}
      </div>
      <div className="space-y-2">
        {files.map((file) => {
          const selected = usingAll || selectedAttachmentIds.includes(file.file_id);
          return (
            <label
              key={file.file_id}
              className="flex items-center gap-3 rounded-[18px] border border-white/10 bg-white/[0.03] px-4 py-3"
            >
              <input
                checked={selected}
                className="h-4 w-4 rounded border-white/20 bg-transparent"
                onChange={() => onToggle(file.file_id)}
                type="checkbox"
              />
              <Paperclip className="h-4 w-4 text-slate-400" />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm text-slate-100">{file.original_name}</p>
                <p className="text-xs text-slate-500">{formatFileSize(file.size_bytes)}</p>
              </div>
              <button
                aria-label={`删除附件 ${file.original_name}`}
                className="rounded-full p-2 text-slate-500 hover:bg-white/5 hover:text-rose-200"
                onClick={(event) => {
                  event.preventDefault();
                  event.stopPropagation();
                  onDelete(file.file_id);
                }}
                type="button"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </label>
          );
        })}
      </div>
    </div>
  );
}
