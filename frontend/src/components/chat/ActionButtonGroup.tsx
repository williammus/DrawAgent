import { WandSparkles, SquarePen } from "lucide-react";

import { Button } from "../common/Button";

interface ActionButtonGroupProps {
  disabled?: boolean;
  onConfirm: () => void;
  onFeedback: () => void;
}

export function ActionButtonGroup({ disabled, onConfirm, onFeedback }: ActionButtonGroupProps) {
  return (
    <div className="mt-4 flex flex-wrap gap-3">
      <Button tone="primary" disabled={disabled} onClick={onConfirm}>
        <WandSparkles className="mr-2 h-4 w-4" />
        确认生成
      </Button>
      <Button tone="secondary" disabled={disabled} onClick={onFeedback}>
        <SquarePen className="mr-2 h-4 w-4" />
        有问题，我还要反馈
      </Button>
    </div>
  );
}
