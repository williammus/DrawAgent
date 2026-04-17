import { Download } from "lucide-react";

import { API_BASE_URL } from "../../lib/constants";
import { Button } from "../common/Button";

interface ImageResultCardProps {
  imageUrl: string;
}

export function ImageResultCard({ imageUrl }: ImageResultCardProps) {
  const resolvedUrl = imageUrl.startsWith("http") ? imageUrl : `${API_BASE_URL}${imageUrl}`;

  return (
    <section className="rounded-[24px] border border-white/10 bg-white/[0.03] p-5">
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.24em] text-slate-500">Image Result</p>
          <h3 className="mt-2 text-lg font-semibold text-white">最终图片</h3>
        </div>
        <Button tone="secondary" onClick={() => window.open(resolvedUrl, "_blank", "noopener,noreferrer")}>
          <Download className="mr-2 h-4 w-4" />
          下载图片
        </Button>
      </div>
      <div className="mt-4 overflow-hidden rounded-[20px] border border-white/10 bg-black/20">
        <img alt="生成后的科研图" className="block w-full object-cover" src={resolvedUrl} />
      </div>
    </section>
  );
}
