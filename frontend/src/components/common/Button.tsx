import type { ButtonHTMLAttributes, PropsWithChildren } from "react";
import clsx from "clsx";

type ButtonProps = PropsWithChildren<
  ButtonHTMLAttributes<HTMLButtonElement> & {
    tone?: "primary" | "secondary" | "ghost" | "danger";
    loading?: boolean;
    block?: boolean;
  }
>;

export function Button({
  children,
  className,
  tone = "secondary",
  loading = false,
  disabled,
  block = false,
  ...props
}: ButtonProps) {
  return (
    <button
      className={clsx(
        "inline-flex h-11 items-center justify-center rounded-2xl border px-4 text-sm font-medium transition",
        block && "w-full",
        tone === "primary" &&
          "border-emerald-400/20 bg-emerald-400 text-slate-950 hover:bg-emerald-300 disabled:bg-emerald-400/60",
        tone === "secondary" &&
          "border-white/10 bg-white/5 text-white hover:bg-white/10 disabled:text-slate-500",
        tone === "ghost" &&
          "border-transparent bg-transparent text-slate-300 hover:bg-white/5 disabled:text-slate-600",
        tone === "danger" &&
          "border-rose-400/20 bg-rose-400/10 text-rose-200 hover:bg-rose-400/15 disabled:text-rose-400/60",
        "disabled:cursor-not-allowed disabled:opacity-70",
        className
      )}
      disabled={disabled || loading}
      {...props}
    >
      {loading ? "处理中..." : children}
    </button>
  );
}
